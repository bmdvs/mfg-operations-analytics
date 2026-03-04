"""Validation of the shop model under current practice against the measured report year.

Usage: python -m analytics.p5_release_control.validate [replications]
"""
import sys
import time

import numpy as np
import pandas as pd

from analytics.db import q
from analytics.p5_release_control.model import REPORT_YEAR, Inputs, Shop, measures

TOLERANCE = {"lead_time_median": ("relative", 0.10), "wip_mean": ("relative", 0.10), "brake_utilization": ("points", 0.03),
             "robotic_weld_utilization": ("points", 0.03), "on_time_delivery": ("points", 0.03), "lead_time_p90": (None, None)}


def measured(first_quarter):
    j = q(f"select lead_time_wd, on_time from marts.mart_job_lead_time where year(ship_date) = {REPORT_YEAR} and quarter(ship_date) >= {first_quarter}")
    w = q(f"select calendar_date, sum(jobs) as wip from marts.mart_wip_daily where year(calendar_date) = {REPORT_YEAR} and quarter(calendar_date) >= {first_quarter} group by 1")
    u = q(f"""select work_center, sum(machine_hours) / sum(scheduled_hours - downtime_hours) as u from marts.mart_utilization_weekly
              where week_year = {REPORT_YEAR} and week_quarter >= {first_quarter} group by 1""").set_index("work_center")["u"]
    return dict(jobs_shipped=len(j), lead_time_median=float(j["lead_time_wd"].median()), lead_time_p90=float(j["lead_time_wd"].quantile(0.9)),
                wip_mean=float(w["wip"].mean()), on_time_delivery=float(j["on_time"].mean()), brake_utilization=float(u["press_brake"]),
                robotic_weld_utilization=float(u["robotic_weld"]))


def validate(reps=10):
    inp = Inputs()
    runs = {1: [], 2: []}
    ot = []
    for k in range(reps):
        t0 = time.time()
        shop = Shop(inp, seed=100 + k).run()
        for fq in (1, 2):
            runs[fq].append(measures(shop, fq))
        ot.append(shop.overtime)
        print(f"replication {k + 1}: {time.time() - t0:.0f} s, shipped {len(shop.results):,}", flush=True)
    rows = []
    for fq, label in ((1, f"{REPORT_YEAR}"), (2, f"{REPORT_YEAR} Q2 to Q4")):
        m = measured(fq)
        d = pd.DataFrame(runs[fq])
        for k in ("lead_time_median", "lead_time_p90", "wip_mean", "brake_utilization", "robotic_weld_utilization", "on_time_delivery", "jobs_shipped"):
            mean, sd = d[k].mean(), d[k].std(ddof=1) if len(d) > 1 else 0.0
            half = 1.96 * sd / np.sqrt(len(d))
            kind, tol = TOLERANCE.get(k, (None, None))
            if kind == "relative":
                diff, ok = mean / m[k] - 1, abs(mean / m[k] - 1) <= tol
            elif kind == "points":
                diff, ok = mean - m[k], abs(mean - m[k]) <= tol
            else:
                diff, ok = mean / m[k] - 1, None
            rows.append(dict(period=label, measure=k, measured=m[k], model=mean, low=mean - half, high=mean + half, difference=diff,
                             tolerance=("within 10%" if kind == "relative" else "within 3 points" if kind == "points" else "reported"),
                             result="" if ok is None else ("within" if ok else "outside")))
    return pd.DataFrame(rows), pd.DataFrame(ot), inp


def quarters(reps=30):
    """Jobs shipped, on-time delivery and median lead time by quarter shipped, per replication of current practice."""
    from pathlib import Path
    from analytics.p5_release_control.model import hours
    inp = Inputs()
    rows = []
    for k in range(reps):
        shop = Shop(inp, seed=100 + k).run()
        r = pd.DataFrame(shop.results)
        r["ship_date"] = r["ship_ts"].dt.normalize()
        r["lead"] = [inp.W(hours(s) + 15) - inp.W(hours(a) + 10) for s, a in zip(r["ship_date"], r["release_date"])]
        r["on_time"] = r["ship_date"] <= pd.to_datetime(r["due_date"])
        g = r[r["ship_date"] >= "2024-07-01"].groupby(r["ship_date"].dt.to_period("Q")).agg(jobs_shipped=("lead", "size"), on_time_delivery=("on_time", "mean"),
                                                                                           lead_time_median=("lead", "median")).reset_index()
        g["seed"] = 100 + k
        g["peak_brake_queue"] = pd.DataFrame(shop.daily)["press_brake"].max()
        rows.append(g.rename(columns={"ship_date": "quarter"}))
    out = pd.concat(rows)
    out["quarter"] = out["quarter"].astype(str)
    out.to_csv(Path(__file__).resolve().parent / "results" / "validation_quarters.csv", index=False)
    return out


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[2] == "quarters":
        quarters(int(sys.argv[1]))
        sys.exit(0)
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    t, ot, inp = validate(n)
    pd.set_option("display.width", 220)
    print(t.round(3).to_string(index=False))
    print(ot.mean().round(1).to_dict(), "p_saturday", inp.p_saturday.round(2), "p_extended", inp.p_extended.round(2), "availability", round(inp.brake_availability, 3))
