"""The shop-wide screen: hot weeks by work center, the dispatch-list work centers, the powder line by color, the robotic weld cell,
assembly and the lasers, read from the marts."""
import numpy as np
import pandas as pd

from analytics.db import q

YEAR = 2025
PERIODS = (("year", 1), ("Q2 to Q4", 2))
HOT = 0.95
SERIES_START = "2023-01-30"                     # weekly series leave out the first four weeks, when jobs already in process raise the queue
LIST_CENTERS = ["grind_deburr", "inspection_pack", "hardware", "weld"]
HOUR_BANDS = [0, 6, 8, 10, 12, 14, 16, 24]
HOUR_LABELS = ["Before 06:00", "06:00 to 08:00", "08:00 to 10:00", "10:00 to 12:00", "12:00 to 14:00", "14:00 to 16:00", "After 16:00"]
UTIL_BANDS = ["below 0.80", "0.80 to 0.85", "0.85 to 0.90", "0.90 to 0.95", "0.95 and above"]


def load():
    uw = q("select * from marts.mart_utilization_weekly order by work_center, week_start")
    uw["week_start"] = pd.to_datetime(uw["week_start"])
    arr = q(f"select * from marts.mart_operation_arrivals where start_year = {YEAR} order by job_id, op_seq")
    arr["week_start"], arr["arrival_week"] = pd.to_datetime(arr["week_start"]), pd.to_datetime(arr["arrival_week"])
    return dict(
        uw=uw, arr=arr,
        ops=q(f"select * from marts.mart_operations where start_year = {YEAR} order by job_id, op_seq"),
        shipped=q(f"select quarter(ship_date) as ship_quarter, count(*) as jobs from marts.mart_job_lead_time where year(ship_date) = {YEAR} group by 1 order by 1"),
        next_day=q(f"select quarter(ship_date) as ship_quarter, sum(queue_net_wd) as days, count(*) as operations from marts.mart_operation_arrivals "
                   f"where year(ship_date) = {YEAR} and working_days_to_start = 1 and work_center in ('grind_deburr', 'inspection_pack', 'hardware', 'weld') "
                   f"group by 1 order by 1"),
        first=q(f"select o.work_center, count(*) as jobs from intermediate.int_operation_queue o join marts.mart_job_lead_time j using (job_id) "
                f"where o.is_first_op and year(j.ship_date) = {YEAR} group by 1 order by 1"),
        shifts=q(f"select work_center, max(shifts) as shifts, max(machines) as machines from staging.stg_erp__work_center_calendar "
                 f"where year(calendar_date) = {YEAR} group by 1 order by 1"),
        laser_first=q(f"select o.job_id, o.first_start, sum(case when s.stage = 'first-operation queue' then s.days else 0 end) as queue_days, "
                      f"sum(case when s.stage = 'material wait at first operation' then s.days else 0 end) as material_wait "
                      f"from intermediate.int_operation_queue o join intermediate.int_job_stage_days s using (job_id, op_seq) "
                      f"where o.is_first_op and o.work_center = 'laser' and year(o.first_start) = {YEAR} group by 1, 2 order by 1"),
        machines=q(f"select machine_id, week_quarter, sum(machine_hours) as machine, sum(scheduled_hours) as scheduled, sum(downtime_hours) as down "
                   f"from marts.mart_machine_weekly where work_center = 'laser' and week_year = {YEAR} group by 1, 2 order by 1, 2"),
        laser_run=q(f"select machine_id, sum(run_hours) as run_hours, sum(run_std_hours) as standard_hours from marts.mart_run_standards "
                    f"where work_center = 'laser' and start_year = {YEAR} group by 1 order by 1"),
        setups=q(f"select work_center, count(*) as setups, sum(setup_hours) as hours, sum(setup_std) as standard from marts.mart_setups "
                 f"where setup_year = {YEAR} group by 1 order by 1"),
        runs=q(f"select work_center, sum(run_hours) as hours, sum(run_std_hours) as standard from marts.mart_run_standards where start_year = {YEAR} group by 1 order by 1"),
        colors=q("select color, days_per_week, weekdays from marts.mart_powder_color_days order by color"),
    )


def weighted_queue(w):
    w = w.dropna(subset=["queue_mean"])
    return float((w["queue_mean"] * w["operations"]).sum() / w["operations"].sum()) if w["operations"].sum() else np.nan


def pooled_utilization(w):
    return float(w["machine_hours"].sum() / (w["scheduled_hours"].sum() - w["downtime_hours"].sum())) if len(w) else np.nan


def hot_weeks(D):
    """Weeks at or above 0.95 utilization by work center: how many, the queue in them against the other weeks, and their share of machine hours."""
    rows = []
    for per, fq in PERIODS:
        y = D["uw"][(D["uw"]["week_year"] == YEAR) & (D["uw"]["week_quarter"] >= fq)]
        for wc, w in y.groupby("work_center"):
            hot, other = w[w["utilization"] >= HOT], w[w["utilization"] < HOT]
            rows.append(dict(period=per, work_center=wc, utilization=pooled_utilization(w), weeks=len(w), hot_weeks=len(hot),
                             hot_full_weeks=int((hot["weekdays"] == 5).sum()), queue_hot=weighted_queue(hot), queue_other=weighted_queue(other),
                             utilization_hot=pooled_utilization(hot), utilization_other=pooled_utilization(other),
                             hours_share_hot=float(hot["machine_hours"].sum() / w["machine_hours"].sum())))
    return pd.DataFrame(rows).sort_values(["period", "utilization"], ascending=[False, False])


def dispatch(D):
    """Operations at the dispatch-list work centers by the working day they start after arriving, and arrivals by hour, the brakes beside them."""
    a = D["arr"]
    rows = []
    for per, fq in PERIODS:
        x = a[(a["start_quarter"] >= fq) & a["work_center"].isin(LIST_CENTERS)]
        for wc, g in x.groupby("work_center"):
            r = dict(period=per, work_center=wc, operations=len(g), after_10=float((g["arrival_hour"] >= 10).mean()), after_14=float((g["arrival_hour"] >= 14).mean()))
            for key, m in (("same", g["working_days_to_start"] == 0), ("next", g["working_days_to_start"] == 1), ("later", g["working_days_to_start"] > 1)):
                r[f"{key}_share"], r[f"{key}_queue"] = float(m.mean()), float(g.loc[m, "queue_net_wd"].mean())
            rows.append(r)
    by_start = pd.DataFrame(rows)

    def hours(g):
        band = pd.cut(g["arrival_hour"], HOUR_BANDS, right=False, labels=HOUR_LABELS)
        t = g.groupby(band, observed=False).agg(arrivals=("job_id", "size"), same_day=("working_days_to_start", lambda v: float((v == 0).mean())),
                                               queue=("queue_net_wd", "mean"))
        t["share"] = t["arrivals"] / t["arrivals"].sum()
        return t
    return by_start, hours(a[a["work_center"].isin(LIST_CENTERS)]), hours(a[a["work_center"] == "press_brake"])


def next_day_wait(D):
    """Working days of next-day queue at the dispatch-list work centers per job shipped, for the year and the ordinary quarters."""
    out = {}
    for per, fq in PERIODS:
        out[per] = float(D["next_day"].loc[D["next_day"]["ship_quarter"] >= fq, "days"].sum() / D["shipped"].loc[D["shipped"]["ship_quarter"] >= fq, "jobs"].sum())
    return out


def powder(D):
    p = D["arr"][D["arr"]["work_center"] == "powder_coat"]
    g = p.groupby("powder_color").agg(operations=("job_id", "size"), wait_mean=("scheduling_wait_wd", "mean"),
                                      day_or_more=("scheduling_wait_wd", lambda v: float((v >= 1).mean())), wait_days=("scheduling_wait_wd", "sum"))
    g["share_of_operations"] = g["operations"] / g["operations"].sum()
    g["share_of_wait"] = g["wait_days"] / g["wait_days"].sum()
    g = g.join(D["colors"].set_index("color")).sort_values("operations", ascending=False)
    total = dict(operations=len(p), wait_mean=float(p["scheduling_wait_wd"].mean()), day_or_more=float((p["scheduling_wait_wd"] >= 1).mean()))
    return g, total


def bands(D, work_center):
    w = D["uw"][(D["uw"]["work_center"] == work_center) & (D["uw"]["week_year"] == YEAR)]
    band = pd.cut(w["utilization"], [0, 0.8, 0.85, 0.9, HOT, 9], right=False, labels=UTIL_BANDS)
    rows = [dict(band=k, weeks=len(g), full_weeks=int((g["weekdays"] == 5).sum()), operations=g["operations"].sum(), queue=weighted_queue(g))
            for k, g in w.groupby(band, observed=False)]
    return pd.DataFrame(rows).set_index("band")


def families(D, work_center):
    o = D["ops"][D["ops"]["work_center"] == work_center]
    hours = o["setup_hours"] + o["run_hours"]
    g = pd.DataFrame({"operations": o.groupby("family").size(), "hours": hours.groupby(o["family"]).sum(), "queue": o.groupby("family")["queue_net_wd"].mean()})
    g["share"] = g["hours"] / g["hours"].sum()
    return g.sort_values("hours", ascending=False)


def against_standard(D, work_center):
    s, r = D["setups"].set_index("work_center").loc[work_center], D["runs"].set_index("work_center").loc[work_center]
    return dict(setups=int(s["setups"]), setup_hours=float(s["hours"]), setup_standard=float(s["standard"]), setup_ratio=float(s["hours"] / s["standard"]),
                run_hours=float(r["hours"]), run_standard=float(r["standard"]), run_ratio=float(r["hours"] / r["standard"]))


def assembly(D):
    w = D["uw"][D["uw"]["work_center"] == "assembly"]
    years = pd.DataFrame([dict(year=int(y), utilization=pooled_utilization(g), queue=weighted_queue(g), hot_weeks=int((g["utilization"] >= HOT).sum()),
                               weeks=len(g), operations=int(g["operations"].sum())) for y, g in w.groupby("week_year")]).set_index("year")
    wy = w[w["week_year"] == YEAR]
    first = w[(w["week_year"] == YEAR - 2) & (w["week_start"] >= SERIES_START)]
    a = D["arr"][D["arr"]["work_center"] == "assembly"].copy()
    a["origin"] = np.where(a["has_robotic_weld"], "Robotic weld cell", np.where(a["has_manual_weld"], "Manual weld bays", "No weld"))
    o = D["ops"][D["ops"]["work_center"] == "assembly"].assign(hours=lambda d: d["setup_hours"] + d["run_hours"])
    a = a.merge(o[["job_id", "op_seq", "hours"]], on=["job_id", "op_seq"], how="left")
    origin = a.groupby("origin").agg(operations=("job_id", "size"), hours=("hours", "sum"), queue=("queue_net_wd", "mean"), p90=("queue_net_wd", lambda v: v.quantile(0.9)))
    origin["share_of_hours"] = origin["hours"] / origin["hours"].sum()
    previous = (a["previous_work_center"].value_counts() / len(a)).rename("share")
    hot_set = set(wy.loc[wy["utilization"] >= HOT, "week_start"])
    arrivals = a.groupby("arrival_week").agg(arrivals=("job_id", "size"), robot=("has_robotic_weld", "sum"))
    wk = wy.set_index("week_start").join(arrivals).fillna({"arrivals": 0, "robot": 0})
    wk["hot"] = wk["utilization"] >= HOT
    o = o.assign(hot=pd.to_datetime(o["week_start"]).isin(hot_set))
    compare = {}
    for name, flag in (("hot", True), ("other", False)):
        g = wk[wk["hot"] == flag]
        compare[name] = dict(weeks=len(g), utilization=pooled_utilization(g), queue=weighted_queue(g), arrivals=float(g["arrivals"].mean()),
                             robot_arrivals=float(g["robot"].mean()), robot_share=float(g["robot"].sum() / g["arrivals"].sum()),
                             hours_per_operation=float(o.loc[o["hot"] == flag, "hours"].mean()))
    robot = D["uw"][(D["uw"]["work_center"] == "robotic_weld") & (D["uw"]["week_year"] == YEAR)].set_index("week_start")["machine_hours"].reindex(wk.index)
    corr = {"Assembly utilization and assembly queue": wk["utilization"].corr(wk["queue_mean"]),
            "Assembly utilization and arrivals in the week": wk["utilization"].corr(wk["arrivals"]),
            "Assembly utilization and arrivals from robotic weld routings": wk["utilization"].corr(wk["robot"]),
            "Assembly utilization and robotic weld cell hours, same week": wk["utilization"].corr(robot),
            "The same, robotic weld cell hours one week earlier": wk["utilization"].corr(robot.shift(1)),
            "The same, two weeks earlier": wk["utilization"].corr(robot.shift(2))}
    backlog_weeks = int((wk["hot"] & (wk["week_quarter"] == 1)).sum())
    return dict(years=years, first_year_queue_from_start=weighted_queue(first), compare=compare, origin=origin, previous=previous, corr={k: float(v) for k, v in corr.items()}, families=families(D, "assembly"),
                backlog_weeks=backlog_weeks, p90=float(o["queue_net_wd"].quantile(0.9)))


def lasers(D):
    f = D["laser_first"].copy()
    f["month"] = pd.to_datetime(f["first_start"]).dt.month
    month = f.groupby("month").agg(first_operations=("job_id", "size"), queue=("queue_days", "mean"), p90=("queue_days", lambda v: v.quantile(0.9)),
                                   material_wait=("material_wait", "mean"), with_wait=("material_wait", lambda v: float((v > 0).mean())))
    lw = D["uw"][(D["uw"]["work_center"] == "laser") & (D["uw"]["week_year"] == YEAR)]
    month["utilization"] = [pooled_utilization(g) for _, g in lw.groupby((lw["week_start"] + pd.Timedelta(days=3)).dt.month)]
    period = {}
    for per, fq in PERIODS:
        v = f[pd.to_datetime(f["first_start"]).dt.quarter >= fq]
        period[per] = dict(first_operations=len(v), queue=float(v["queue_days"].mean()), median=float(v["queue_days"].median()), p90=float(v["queue_days"].quantile(0.9)),
                           material_wait=float(v["material_wait"].mean()), with_wait=float((v["material_wait"] > 0).mean()),
                           wait_where_any=float(v.loc[v["material_wait"] > 0, "material_wait"].mean()))
    m = D["machines"].groupby("machine_id")[["machine", "scheduled", "down"]].sum()
    m["share_of_hours"] = m["machine"] / m["machine"].sum()
    m["utilization"] = m["machine"] / (m["scheduled"] - m["down"])
    m["uptime"] = 1 - m["down"] / m["scheduled"]
    m = m.join(D["laser_run"].set_index("machine_id"))
    m["run_ratio"] = m["run_hours"] / m["standard_hours"]
    m["share_of_standard"] = m["standard_hours"] / m["standard_hours"].sum()
    return dict(month=month, period=period, machines=m)
