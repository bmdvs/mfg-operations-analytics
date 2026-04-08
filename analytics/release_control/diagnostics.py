"""The shop model under current practice against the record: work centers, the lead-time distribution and the floor by week.

Each run is the current-practice run of the scenario file (same seed), with every operation start and every stretch of machine time kept.

Usage: python -m analytics.release_control.diagnostics [replications] [workers]
"""
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from analytics.release_control.model import REPORT_YEAR, T0, Inputs, Shop, generator_seed, hours

S0 = "S0 Current practice"
RES = Path(__file__).resolve().parent / "results"
WORK_CENTERS, LEAD, WEEKLY = RES / "diagnostics_work_centers.csv", RES / "diagnostics_lead_time.csv", RES / "diagnostics_weekly.csv"
FIRST_OPERATION = "first operation"                  # the lasers and the punch together, on the queue ahead of a job's first operation
PERCENTILES = (0.10, 0.25, 0.50, 0.75, 0.90, 0.95)
LEAD_DAYS = 80                                       # the cumulative curve is kept to this many working days


class Traced(Shop):
    """The shop, keeping each stretch of machine time."""

    def __init__(self, inp, seed):
        self.busy_log = []
        super().__init__(inp, seed)

    def note_work(self, m, start, machine_hours):
        self.busy_log.append((m.wc, m.id, start, machine_hours))


def week_of(ts):
    ts = pd.to_datetime(ts)
    return (ts - pd.to_timedelta(ts.dt.weekday, unit="D")).dt.normalize()


def kind(t):
    """Weekday, Saturday or extended machine time, by when it starts; the extended shift runs from 22:30 to 00:30."""
    h, day = t % 24, int(t // 24)
    if h >= 22.5 - 1e-9:
        return "extended", day
    if h < 0.5 - 1e-9:
        return "extended", day - 1
    return ("saturday" if (T0 + pd.Timedelta(days=day)).weekday() == 5 else "weekday"), day


def window_hours(shop):
    """Crewed hours net of downtime by work center and day, with the Saturday and extended brake hours the rule called."""
    rows = [(wc, int(a // 24), b - a) for wc, ms in shop.machines.items() for m in ms for a, b, _ in m.windows]
    # a Saturday called counts the calendar's 16 scheduled brake hours, as brake utilization does; an extended shift its hours
    rows += [("press_brake", (pd.Timestamp(d) - T0).days, 16.0 if k == "saturday" else h) for d, k, h in shop.ot_log]
    w = pd.DataFrame(rows, columns=["work_center", "day", "hours"])
    w["date"] = T0 + pd.to_timedelta(w["day"], unit="D")
    return w


def one(rep):
    global _INP
    if "_INP" not in globals() or _INP is None:
        _INP = Inputs()
    inp = _INP
    shop = Traced(inp, generator_seed(S0, rep)).run()
    first = {j: o[0]["op_seq"] for j, o in inp.ops.items()}

    ops = pd.DataFrame(shop.op_log, columns=["work_center", "job_id", "op_seq", "arrival", "start", "end", "standard_hours", "previous_end"])
    # queue from the end of the previous operation, as the record's queue figures are measured
    ops["queue"] = [inp.W(s) - inp.W(a) for a, s in zip(ops["previous_end"], ops["start"])]
    ops["first"] = [first[j] == o for j, o in zip(ops["job_id"], ops["op_seq"])]
    # the powder queue less the wait for the color day, as the record splits it: from the end of the previous operation to 06:00 on the first
    # scheduled day of the job's color on or after that day
    color = inp.jobs.set_index("job_id")["powder_color"]
    ops["queue_net"] = ops["queue"]
    for i, r in ops[ops["work_center"] == "powder_coat"].iterrows():
        d = int(r["previous_end"] // 24)
        while color[r["job_id"]] not in inp.color_days.get((T0 + pd.Timedelta(days=d)).date(), ()) and d < len(inp.flag) - 1:
            d += 1
        ready = max(r["previous_end"], 24 * d + 6.0)
        ops.at[i, "queue_net"] = max(r["queue"] - (inp.W(ready) - inp.W(r["previous_end"])), 0.0)
    ops["date"] = T0 + pd.to_timedelta(ops["start"], unit="h")
    busy = pd.DataFrame(shop.busy_log, columns=["work_center", "machine_id", "t", "hours"])
    k = [kind(t) for t in busy["t"]]
    busy["kind"], busy["date"] = [x[0] for x in k], [T0 + pd.Timedelta(days=x[1]) for x in k]
    win = window_hours(shop)

    # work centers, the report year
    yo, yb, yw = ops[ops["date"].dt.year == REPORT_YEAR], busy[busy["date"].dt.year == REPORT_YEAR], win[win["date"].dt.year == REPORT_YEAR]
    later, head = yo[~yo["first"]], yo[yo["first"] & yo["work_center"].isin(["laser", "punch"])]
    util = yb.groupby("work_center")["hours"].sum() / yw.groupby("work_center")["hours"].sum()
    wc = pd.DataFrame({"utilization": util, "queue_mean": later.groupby("work_center")["queue"].mean(), "queue_days": later.groupby("work_center")["queue"].sum(),
                       "queue_days_net": later.groupby("work_center")["queue_net"].sum(),
                       "operations": later.groupby("work_center").size()})
    for w_ in ("laser", "punch"):                                       # every operation at the lasers and the punch is a first operation
        g = head[head["work_center"] == w_]
        wc.loc[w_, ["queue_mean", "queue_days", "operations"]] = [g["queue"].mean(), g["queue"].sum(), len(g)]
    wc.loc[FIRST_OPERATION, ["queue_mean", "queue_days", "operations"]] = [head["queue"].mean(), head["queue"].sum(), len(head)]
    wc = wc.rename_axis("work_center").reset_index().assign(replication=rep)

    # lead time of jobs shipped
    r = pd.DataFrame(shop.results)
    r["ship_date"] = r["ship_ts"].dt.normalize()
    r["lead"] = [inp.W(hours(s) + 15.0) - inp.W(hours(a) + 10.0) for s, a in zip(r["ship_date"], r["release_date"])]
    r["on_time"] = r["ship_date"] <= pd.to_datetime(r["due_date"])
    lead = []
    for fq, label in ((1, "year"), (2, "Q2 to Q4")):
        y = r[(r["ship_date"].dt.year == REPORT_YEAR) & (r["ship_date"].dt.quarter >= fq)]
        row = dict(replication=rep, period=label, jobs=len(y), on_time_delivery=float(y["on_time"].mean()))
        row.update({f"p{int(p * 100)}": float(y["lead"].quantile(p)) for p in PERCENTILES})
        row.update({f"within_{d}": float((y["lead"] <= d).mean()) for d in range(LEAD_DAYS + 1)})
        lead.append(row)

    # the floor by week
    rel = np.sort(pd.to_datetime(inp.jobs["release_date"]).values)
    shp = np.sort(r["ship_date"].values)
    days = pd.DataFrame({"date": [d for d, f in zip(inp.days, inp.flag) if f and d <= inp.cal["calendar_date"].max()]})
    days["wip"] = [np.searchsorted(rel, np.datetime64(d), side="right") - np.searchsorted(shp, np.datetime64(d), side="right") for d in days["date"]]
    b = busy[busy["work_center"] == "press_brake"]
    waiting = pd.DataFrame(shop.daily)
    waiting["date"] = T0 + pd.to_timedelta(waiting["t"] - 1.0, unit="h")                  # the count is taken at the end of the day
    waiting = waiting[waiting["date"].dt.normalize().isin(set(days["date"]))]
    ot = pd.DataFrame(shop.ot_log, columns=["date", "kind", "hours"])
    ot["date"] = pd.to_datetime(ot["date"])
    wk = pd.DataFrame({
        "wip_mean": days.groupby(week_of(days["date"]))["wip"].mean(),
        "wip_peak": days.groupby(week_of(days["date"]))["wip"].max(),
        "brake_queue_mean": ops[ops["work_center"] == "press_brake"].groupby(week_of(ops["date"]))["queue"].mean(),
        "brake_hours_weekday": b[b["kind"] == "weekday"].groupby(week_of(b["date"]))["hours"].sum(),
        "brake_hours_saturday": b[b["kind"] == "saturday"].groupby(week_of(b["date"]))["hours"].sum(),
        "brake_hours_extended": b[b["kind"] == "extended"].groupby(week_of(b["date"]))["hours"].sum(),
        "saturday_shifts": ot[ot["kind"] == "saturday"].groupby(week_of(ot["date"])).size(),
        "extended_shifts": ot[ot["kind"] == "extended"].groupby(week_of(ot["date"])).size(),
        "brake_crewed_hours": win[win["work_center"] == "press_brake"].groupby(week_of(win["date"]))["hours"].sum(),
        "laser_hours": busy[busy["work_center"] == "laser"].groupby(week_of(busy["date"]))["hours"].sum(),
        "laser_crewed_hours": win[win["work_center"] == "laser"].groupby(week_of(win["date"]))["hours"].sum(),
        "waiting_at_brakes": waiting.groupby(week_of(waiting["date"]))["press_brake"].mean(),
        "waiting_at_lasers": waiting.groupby(week_of(waiting["date"]))["laser"].mean(),
        "releases": inp.jobs.groupby(week_of(inp.jobs["release_date"])).size(),
        "jobs_shipped": r.groupby(week_of(r["ship_date"])).size(),
    }).fillna({c: 0 for c in ("brake_hours_weekday", "brake_hours_saturday", "brake_hours_extended", "saturday_shifts", "extended_shifts", "releases", "jobs_shipped")})
    wk = wk[(wk.index >= "2024-07-01") & (wk.index <= "2025-12-29")].rename_axis("week_start").reset_index().assign(replication=rep)
    return wc, pd.DataFrame(lead), wk


def run(reps=30, workers=6):
    wc, lead, wk = [], [], []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for k, (a, b, c) in enumerate(ex.map(one, range(1, reps + 1))):
            wc.append(a)
            lead.append(b)
            wk.append(c)
            print(f"{k + 1} of {reps} runs", flush=True)
    pd.concat(wc).to_csv(WORK_CENTERS, index=False)
    pd.concat(lead).to_csv(LEAD, index=False)
    pd.concat(wk).to_csv(WEEKLY, index=False)


if __name__ == "__main__":
    if len(sys.argv) > 3:                                     # a second run writes its files to the folder given
        WORK_CENTERS, LEAD, WEEKLY = (Path(sys.argv[3]) / f.name for f in (WORK_CENTERS, LEAD, WEEKLY))
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 30, int(sys.argv[2]) if len(sys.argv) > 2 else 6)
    print("wrote", WORK_CENTERS.name, LEAD.name, WEEKLY.name)
