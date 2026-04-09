"""The scenario runs against current practice and against the record: outcomes with intervals, verdicts, and cost and return at the shop's rates."""
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from analytics.db import q
from analytics.release_control.model import REPORT_YEAR, Inputs, hours
from analytics.release_control.validate import TOLERANCE, measured

ROOT = Path(__file__).resolve().parents[1]
RC, TR = Path(__file__).resolve().parent / "results", ROOT / "technology_roi" / "results"
ASSUME = yaml.safe_load((ROOT / "technology_roi_assumptions.yaml").read_text(encoding="utf8"))
YEAR = REPORT_YEAR
ALL = pd.concat([pd.read_csv(RC / "scenario_runs.csv"), pd.read_csv(TR / "scenario_runs.csv")], ignore_index=True)
CUST = pd.concat([pd.read_csv(RC / "customer_delivery.csv"), pd.read_csv(TR / "customer_delivery.csv")], ignore_index=True)
WC, LEAD, WK, VQ = (pd.read_csv(RC / f) for f in ("diagnostics_work_centers.csv", "diagnostics_lead_time.csv", "diagnostics_weekly.csv", "validation_quarters.csv"))
TOWER_WEEKS = pd.read_csv(TR / "laser_queue_november_2024.csv")
INP = Inputs()

CURRENT, PACKAGE = "Current practice", "Operating package"
NAME = {
    "S0 Current practice": CURRENT, "S1 WIP cap 240": "WIP cap: 240 jobs", "S1 WIP cap 210": "WIP cap: 210 jobs", "S1 WIP cap 180": "WIP cap: 180 jobs",
    "S2 Constraint-paced release (3 days of brake work)": "Brake constraint-paced release", "S3 Earliest due date": "Earliest due date", "S3 Critical ratio": "Due-date ratio",
    "S3 Shortest processing time, brakes only": "Shortest processing time at the brakes",
    "S4 Light work first on B1 and B2 when the B3 to B5 queue exceeds 2 days": "Prioritize light work at B1 and B2", "S6 Third weekly color day for black": "Third color day for black",
    "S8 Setup reduction": "Brake setup program", "S7 Planned Saturday brake shift, November to February": "Add'l Saturdays (one brake)",
    "S7 Planned Saturday brake shift on both brakes, November to February": "Add'l Saturdays (both brakes)", "S5 Second shift on the robotic weld cell": "Second shift: robotic weld",
    "T Tool changer on B3": "Replace press brake B3", "T Laser tower on L2": "Automated sheet tower (L2)", "T Robotic bending cell": "New robotic bending cell",
    "Package Setup reduction + planned Saturdays on both brakes": PACKAGE, "N Package + tool changer on B3": "Package + tool changer",
    "N Package + laser tower on L2": "Package + laser tower", "N Package + robotic bending cell": "Package + robotic cell", "Package + earliest due date": "Package + earliest due date"}
KEY = {v: k for k, v in NAME.items()}
assert set(ALL["scenario"]) == set(NAME), set(ALL["scenario"]) ^ set(NAME)
RELEASE = ["WIP cap: 240 jobs", "WIP cap: 210 jobs", "WIP cap: 180 jobs", "Brake constraint-paced release", "Earliest due date", "Due-date ratio", "Shortest processing time at the brakes",
           "Prioritize light work at B1 and B2", "Third color day for black"]
CAPACITY = ["Brake setup program", "Add'l Saturdays (one brake)", "Add'l Saturdays (both brakes)", "Second shift: robotic weld", "Replace press brake B3", "Automated sheet tower (L2)",
            "New robotic bending cell"]
COMBOS = ["Package + tool changer", "Package + laser tower", "Package + robotic cell", "Package + earliest due date"]
EVERY = RELEASE + CAPACITY + [PACKAGE] + COMBOS
PERIOD = {"year": "year", "rest": "Q2 to Q4", "second half": "Q3 to Q4"}
OUTCOMES = [("on_time_delivery", "On-time delivery (points)", 1, True), ("late_jobs", "Late jobs", 0, False), ("days_late", "Days late", 0, False),
            ("brake_queue_mean", "Queue per brake operation (days)", 2, False), ("wip_mean", "Floor WIP (jobs)", 1, False), ("brake_utilization", "Brake utilization (points)", 1, True)]
FURTHER = [("lead_time_median", "Median lead time (days)", 2, False), ("lead_time_p90", "90th-percentile lead time (days)", 2, False),
           ("queue_mean_all", "Queue per operation, all work centers (days)", 2, False), ("robotic_weld_utilization", "Robotic weld utilization (points)", 1, True),
           ("laser_utilization", "Laser utilization (points)", 1, True), ("jobs_shipped", "Jobs shipped", 0, False)]


def col(sc, m, per="year"):
    return ALL[(ALL["scenario"] == KEY[sc]) & (ALL["period"] == PERIOD[per])].set_index("replication")[m].sort_index()


def ci(x):
    x = np.asarray(x, dtype=float)
    h = 1.96 * x.std(ddof=1) / np.sqrt(len(x))
    return float(x.mean()), float(x.mean() - h), float(x.mean() + h)


def mean(sc, m, per="year"):
    return float(col(sc, m, per).mean())


def diff(sc, m, per="year", ref=CURRENT):
    """Mean and 95% interval of the scenario less the reference, run for run."""
    return ci(col(sc, m, per) - col(ref, m, per))


def verdict(sc):
    a, b = diff(sc, "on_time_delivery", "year"), diff(sc, "on_time_delivery", "rest")
    if a[1] > 0 or b[1] > 0:
        return "Works"
    if (a[2] < 0 and not b[1] > 0) or (b[2] < 0 and not a[1] > 0):
        return "Makes it worse"
    return "No effect"


VERDICT = {sc: verdict(sc) for sc in EVERY}

# ── the model against the record ────────────────────────────────────────────
WORK_CENTERS = {"press_brake": "Press brake", "robotic_weld": "Robotic weld", "weld": "Manual weld", "grind_deburr": "Grind and deburr", "hardware": "Hardware", "assembly": "Assembly",
                "inspection_pack": "Inspection and pack", "powder_coat": "Powder coat", "laser": "Laser (first operation)", "punch": "Punch (first operation)"}


def tolerance():
    rows = []
    for fq, per in ((1, "year"), (2, "rest")):
        m = measured(fq)
        for key in ("lead_time_median", "wip_mean", "brake_utilization", "robotic_weld_utilization", "on_time_delivery"):
            t = ci(col(CURRENT, key, per))
            kind, tol = TOLERANCE[key]
            d = t[0] / m[key] - 1 if kind == "relative" else t[0] - m[key]
            rows.append(dict(period=per, measure=key, measured=m[key], model=t[0], low=t[1], high=t[2], difference=d, kind=kind, within=bool(abs(d) <= tol)))
        for key in ("lead_time_p90", "jobs_shipped"):
            t = ci(col(CURRENT, key, per))
            rows.append(dict(period=per, measure=key, measured=m[key], model=t[0], low=t[1], high=t[2], difference=t[0] / m[key] - 1, kind=None, within=None))
    return pd.DataFrame(rows)


def work_centers():
    """Utilization and queue time per operation by work center, measured against model, for the report year. Queue runs from the end of the previous
    operation to the start; for the lasers and the punch, the first-operation queue. The model's queue days are net of the wait for the powder color day."""
    u = q(f"select work_center, sum(machine_hours) / sum(scheduled_hours - downtime_hours) as u from marts.mart_utilization_weekly where week_year = {YEAR} group by 1").set_index("work_center")["u"]
    o = q(f"select work_center, prev_end, first_start from intermediate.int_operation_queue where not is_first_op and year(first_start) = {YEAR} and work_center <> 'outside_processing'")
    o["queue"] = [INP.W(hours(s)) - INP.W(hours(p)) for p, s in zip(o["prev_end"], o["first_start"])]
    later = o.groupby("work_center")["queue"].mean()
    first = q(f"""select s.work_center, sum(s.days) / count(distinct s.job_id) as d from intermediate.int_job_stage_days s
                  join intermediate.int_operation_queue o on o.job_id = s.job_id and o.op_seq = s.op_seq
                  where s.stage = 'first-operation queue' and year(o.first_start) = {YEAR} group by 1""").set_index("work_center")["d"]
    g = WC.groupby("work_center")[["utilization", "queue_mean"]].mean()
    days, model_days = o.groupby("work_center")["queue"].sum(), WC.groupby("work_center")["queue_days_net"].mean()      # the model's, less the color-day wait
    rows = [dict(work_center=lab, utilization_measured=float(u[wc]), utilization_model=float(g.loc[wc, "utilization"]),
                 queue_measured=float(first[wc] if wc in ("laser", "punch") else later[wc]), queue_model=float(g.loc[wc, "queue_mean"]),
                 queue_days_measured=float(days.get(wc, np.nan)) if wc not in ("laser", "punch") else np.nan,
                 queue_days_model=float(model_days[wc]) if wc not in ("laser", "punch") else np.nan) for wc, lab in WORK_CENTERS.items()]
    return pd.DataFrame(rows)


def lead_times():
    """Percentiles and the cumulative share of jobs shipped by working days of lead time, measured against model, for the year and the ordinary quarters."""
    jl = q(f"select lead_time_wd, quarter(ship_date) as qq from marts.mart_job_lead_time where year(ship_date) = {YEAR}")
    pct, curve = [], {}
    days = [int(c.split("_")[1]) for c in LEAD.columns if c.startswith("within_")]
    for per, label, sel in (("year", "year", jl), ("Q2 to Q4", "rest", jl[jl["qq"] >= 2])):
        m = LEAD[LEAD["period"] == per]
        for p in (10, 25, 50, 75, 90, 95):
            pct.append(dict(period=label, percentile=p, measured=float(sel["lead_time_wd"].quantile(p / 100)), model=float(m[f"p{p}"].mean())))
        curve[label] = pd.DataFrame({"days": days, "measured": [float((sel["lead_time_wd"] <= d).mean()) for d in days], "model": [float(m[f"within_{d}"].mean()) for d in days]})
    return pd.DataFrame(pct), curve


def weekly(start="2024-09-30", end="2025-06-23"):
    """The floor by week, measured against model (the mean over the runs)."""
    w = WK.copy()
    w["week_start"] = pd.to_datetime(w["week_start"])
    m = w.groupby("week_start").mean(numeric_only=True)
    f = q("select * from marts.mart_weekly_floor order by week_start")
    f["week_start"] = pd.to_datetime(f["week_start"])
    f = f.set_index("week_start")
    b = q("select week_start, machine_hours, scheduled_hours - downtime_hours as crewed, queue_mean from marts.mart_utilization_weekly where work_center = 'press_brake'")
    b["week_start"] = pd.to_datetime(b["week_start"])
    b = b.set_index("week_start")
    sat = q("select week_start, sum(saturday_hours) as h from marts.mart_machine_weekly where work_center = 'press_brake' group by 1")
    sat["week_start"] = pd.to_datetime(sat["week_start"])
    out = pd.DataFrame({
        "releases_measured": f["releases"], "releases_model": m["releases"], "releases_low": w.groupby("week_start")["releases"].min(), "releases_high": w.groupby("week_start")["releases"].max(),
        "shipped_measured": f["jobs_shipped"], "shipped_model": m["jobs_shipped"], "wip_measured": f["wip_mean"], "wip_model": m["wip_mean"], "wip_peak_model": m["wip_peak"],
        "brake_queue_measured": b["queue_mean"], "brake_queue_model": m["brake_queue_mean"], "laser_utilization_measured": f["laser_utilization"],
        "laser_utilization_model": m["laser_hours"] / m["laser_crewed_hours"], "brake_utilization_measured": f["brake_utilization"],
        "brake_utilization_model": (m["brake_hours_weekday"] + m["brake_hours_saturday"] + m["brake_hours_extended"]) / m["brake_crewed_hours"],
        "brake_hours_measured": b["machine_hours"], "brake_saturday_hours_measured": sat.set_index("week_start")["h"], "brake_hours_weekday_model": m["brake_hours_weekday"],
        "brake_hours_saturday_model": m["brake_hours_saturday"], "brake_hours_extended_model": m["brake_hours_extended"], "brake_crewed_measured": b["crewed"],
        "brake_crewed_model": m["brake_crewed_hours"], "saturday_shifts_measured": f["brake_saturday_shifts"], "saturday_shifts_model": m["saturday_shifts"],
        "extended_hours_measured": f["brake_extended_hours"], "extended_hours_model": m["extended_shifts"] * 4.0})
    return out[(out.index >= start) & (out.index <= end)]


def build():
    """The year-end build: its peak, its clearing and the brake hours behind it, measured against model."""
    w = weekly("2024-10-01", "2025-06-30")
    d = q("select calendar_date, sum(jobs) as wip from marts.mart_wip_daily where calendar_date between date '2024-10-01' and date '2025-06-30' group by 1 order by 1")
    d["calendar_date"] = pd.to_datetime(d["calendar_date"])
    top = d.loc[d["wip"].idxmax()]
    peak_week = top["calendar_date"] - pd.Timedelta(days=int(top["calendar_date"].weekday()))
    model_week = w["wip_peak_model"].idxmax()

    def below(s, level, after):
        s = s[s.index > after]
        return s[s < level].index.min()

    months = w[(w.index >= "2024-12-02") & (w.index <= "2025-03-24")]
    model_hours = months[["brake_hours_weekday_model", "brake_hours_saturday_model", "brake_hours_extended_model"]].sum()
    return dict(peak_measured=int(top["wip"]), peak_day=top["calendar_date"], peak_week=peak_week, peak_model=float(w.loc[model_week, "wip_peak_model"]), peak_week_model=model_week,
                below={lv: (below(w["wip_measured"], lv, peak_week), below(w["wip_model"], lv, model_week)) for lv in (300, 250, 220)},
                brake_hours_measured=float(months["brake_hours_measured"].sum()), brake_hours_model=float(model_hours.sum()),
                saturday_hours_measured=float(months["brake_saturday_hours_measured"].sum()), saturday_hours_model=float(model_hours.iloc[1]),
                extended_hours_model=float(model_hours.iloc[2]), crewed_measured=float(months["brake_crewed_measured"].sum()), crewed_model=float(months["brake_crewed_model"].sum()))


def quarters():
    d = q("select quarter_start, jobs_shipped, on_time_delivery, lead_time_median from marts.mart_delivery_by_quarter where quarter_start >= date '2024-07-01' order by 1")
    v = VQ.groupby("quarter")[["jobs_shipped", "on_time_delivery", "lead_time_median"]].mean()
    d["quarter"] = [f"{pd.Timestamp(t).year}Q{pd.Timestamp(t).quarter}" for t in d["quarter_start"]]
    return d.set_index("quarter").join(v, rsuffix="_model").drop(columns="quarter_start")


def tower_weeks():
    t = TOWER_WEEKS.copy()
    t["day"] = pd.to_datetime(t["day"])
    t["week"] = t["day"] - pd.to_timedelta(t["day"].dt.weekday, unit="D")
    t["scenario"] = t["scenario"].map(NAME)
    return t.groupby(["week", "scenario"])["jobs_waiting_at_lasers"].mean().unstack()


# ── measured inputs the scenarios rest on ───────────────────────────────────
def inputs():
    s = q(f"select machine_id, sum(setup_hours) as h, sum(setup_hours - setup_std) as over, count(*) as n from marts.mart_setups where work_center = 'press_brake' and setup_year = {YEAR} group by 1").set_index("machine_id")
    share = q(f"select work_center, share_of_queue, mean_queue_days from marts.mart_queue_by_work_center where period = 'year'").set_index("work_center")
    u = q(f"""select work_center, sum(machine_hours) as h, sum(machine_hours) / sum(scheduled_hours - downtime_hours) as u from marts.mart_utilization_weekly
              where week_year = {YEAR} group by 1""").set_index("work_center")
    rev = float(q(f"select sum(ol.unit_price * ol.qty) from staging.stg_erp__jobs j join staging.stg_erp__order_lines ol using (order_line_id) where year(j.ship_date) = {YEAR}").iloc[0, 0])
    j = INP.jobs[pd.to_datetime(INP.jobs["release_date"]).dt.year == YEAR]
    std = pd.Series({k: sum(o["setup_std"] + o["run_std_hours"] for o in v if o["work_center"] == "press_brake") for k, v in INP.ops.items()})
    h = j["job_id"].map(std).fillna(0.0)
    operators = int(q("select count(*) from staging.stg_hr__employees where home_work_center = 'press_brake' and termination_date is null").iloc[0, 0])
    powder = q(f"select sum(scheduling_wait_wd) / count(*) from marts.mart_operations where work_center = 'powder_coat' and start_year = {YEAR}").iloc[0, 0]
    return dict(brake_share_of_queue=float(share.loc["press_brake", "share_of_queue"]), setups_over_per_week=float(s["over"].sum() / 52), brake_setup_hours=float(s["h"].sum()),
                b3_setup_hours=float(s.loc["B3", "h"]), b3_setups=int(s.loc["B3", "n"]), brake_utilization=float(u.loc["press_brake", "u"]), brake_hours=float(u.loc["press_brake", "h"]),
                weld_utilization=float(u.loc["robotic_weld", "u"]), weld_queue=float(share.loc["robotic_weld", "mean_queue_days"]), laser_utilization=float(u.loc["laser", "u"]),
                revenue=rev, revenue_per_brake_hour=rev / float(u.loc["press_brake", "h"]), cell_share=float(h[j["cell_ok"]].sum() / h.sum()), operators=operators,
                powder_wait=float(powder), no_setup_share=float(INP.no_setup_share["press_brake"]), laser_yield=float(INP.laser_availability), brake_yield=float(INP.brake_availability),
                saturday_yield=float(INP.saturday_yield), saturday_worked=float(INP.saturday_with_time), extended_yield=float(INP.extended_yield), holiday_yield=float(INP.holiday_yield),
                p_saturday=[float(x) for x in INP.p_saturday])


M = inputs()

# ── cost and return ─────────────────────────────────────────────────────────
L, F, RH, NC, O = ASSUME["labor"], ASSUME["finance"], ASSUME["released_hours"], ASSUME["no_capital_package"], ASSUME["options"]
RATE = L["labor_rate"]
ANNUITY = (1 - (1 + F["discount_rate"]) ** -F["horizon_years"]) / F["discount_rate"]
VALUE_PER_HOUR = RH["contribution_margin_share"] * M["revenue_per_brake_hour"]
SOLD = RH["utilization_of_released_hours"]
COSTS = {"setup": (NC["setup_program_one_time"], NC["setup_program_annual"]),
         "changer": (O["press_brake_atc"]["equipment_cost"] + O["press_brake_atc"]["installation_and_tooling"], O["press_brake_atc"]["annual_maintenance"]),
         "tower": (O["laser_tower"]["equipment_cost"] + O["laser_tower"]["installation_and_tooling"], O["laser_tower"]["annual_maintenance"]),
         "cell": (O["robotic_bending_cell"]["equipment_cost"] + O["robotic_bending_cell"]["installation_and_tooling"], O["robotic_bending_cell"]["annual_maintenance"])}


def parts(sc):
    k, p = KEY[sc], set()
    if "Setup reduction" in k or "Package" in k:
        p.add("setup")
    if "ool changer" in k:
        p.add("changer")
    if "tower" in k:
        p.add("tower")
    if "bending cell" in k:
        p.add("cell")
    return p


def money(sc, ref=CURRENT, variant="year"):
    """Cost and return of a scenario against its reference at the shop's rates, run by run. The ordinary year is the second half of the report year, twice.
    Constraint hours freed are the manual brake machine hours of the reference less the scenario's, counted for levers that take brake hours off the work."""
    per, k = ("year", 1.0) if variant == "year" else ("second half", 2.0)
    d = lambda m: (col(ref, m, per) - col(sc, m, per)) * k
    new = parts(sc) - parts(ref)
    freed = d("brake_hours") if new & {"setup", "changer", "cell"} else d("brake_hours") * 0.0
    overtime = d("saturday_hours") + d("extended_hours")                    # overtime operator hours avoided; negative where the scenario adds them
    cost = RATE * (1 + L["overtime_premium"])
    avoided, added_overtime = overtime.clip(lower=0) * cost, (-overtime).clip(lower=0) * cost
    weld = -d("weld_second_shift_hours") * NC["weld_second_shift_operators"] * RATE * (1 + NC["shift_differential"])
    cell = -d("cell_hours") * O["robotic_bending_cell"]["tending_labor_per_cell_hour"] * RATE
    one_time, upkeep = float(sum(COSTS[p][0] for p in new)), float(sum(COSTS[p][1] for p in new))
    added = upkeep + weld + cell + added_overtime
    base = avoided - added
    throughput = freed * SOLD * VALUE_PER_HOUR
    net = base + throughput
    need = one_time / ANNUITY - base.mean()
    share = need / (freed.mean() * VALUE_PER_HOUR) if freed.mean() > 0 else np.nan
    return dict(scenario=sc, reference=ref, one_time=one_time, upkeep=upkeep, weld=float(weld.mean()), cell=float(cell.mean()), added_overtime=float(added_overtime.mean()),
                added=float(added.mean()), avoided=float(avoided.mean()), freed=float(freed.mean()), throughput=float(throughput.mean()), net_without=float(base.mean()),
                net=float(net.mean()), payback=one_time / float(net.mean()) if net.mean() > 0 and one_time > 0 else np.nan, npv=ci(-one_time + net * ANNUITY),
                npv_without=float(-one_time + base.mean() * ANNUITY), share=float(share), hours=float(share * freed.mean()) if share == share else np.nan,
                overtime_hours=float(-overtime.mean()), base_runs=base, freed_runs=freed)


def npv_at(m, share):
    """NPV with its 95% interval when a given share of the freed brake hours is sold."""
    return ci(-m["one_time"] + (m["base_runs"] + m["freed_runs"] * share * VALUE_PER_HOUR) * ANNUITY)


def customers(sc):
    """On-time delivery by customer over the runs pooled, for the customers that make up 80% of the year's revenue."""
    c = CUST[(CUST["scenario"] == KEY[sc]) & (CUST["period"] == "year")].groupby("customer_id")[["jobs", "on_time"]].sum()
    return (c["on_time"] / c["jobs"]).rename(sc)


REVENUE = q(f"""select j.customer_id, sum(ol.unit_price * ol.qty) as revenue from staging.stg_erp__jobs j join staging.stg_erp__order_lines ol using (order_line_id)
                where year(j.ship_date) = {YEAR} group by 1""").set_index("customer_id")["revenue"].reindex(list(INP.top_customers))


def lifted(sc, level):
    """Customers at or above a level of on-time delivery under the scenario, and their revenue."""
    r = customers(sc)
    at = r[r >= level].index
    return len(at), float(REVENUE.reindex(at).sum())
