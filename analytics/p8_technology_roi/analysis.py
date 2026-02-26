"""P8 technology ROI: measured inputs from the marts, the capital options on the shop model, and payback and NPV under the stated assumptions."""
import numpy as np
import pandas as pd

from analytics.db import q
from analytics.p8_technology_roi.scenarios import ASSUME, OUT, PACKAGE, S0

YEAR = 2025
WEEKS = 52
MEASURES = ["on_time_delivery", "lead_time_p90", "lead_time_median", "wip_mean", "saturday_shifts", "extended_hours", "brake_utilization", "laser_utilization",
            "robotic_weld_utilization", "jobs_shipped", "brake_hours", "cell_hours", "brake_setup_hours", "b3_setup_hours", "weld_second_shift_hours",
            "laser_queue_nov_2024", "on_time_released_nov_2024", "lead_time_released_nov_2024"]
LABELS = {S0: "Current practice", PACKAGE: "No-capital package", "T Tool changer on B3": "Press brake with automatic tool changing, in place of B3",
          "T Laser tower on L2": "Second automated laser tower, on L2", "T Robotic bending cell": "Robotic bending cell",
          "T Tool changing at every brake setup (upper bound)": "Sensitivity: tool changing at every brake setup, same price (upper bound)"}
OPTION_OF = {"tool changer on B3": "press_brake_atc", "tool changing at every brake setup (upper bound)": "press_brake_atc", "laser tower on L2": "laser_tower",
             "robotic bending cell": "robotic_bending_cell"}


def label(name):
    if name in LABELS:
        return LABELS[name]
    suffix = name[len("N No-capital package + "):].lower()
    lab = next(v for k, v in LABELS.items() if k.startswith("T ") and k[2:].lower() == suffix)
    return "No-capital package + " + lab[0].lower() + lab[1:]


def runs():
    return pd.read_csv(OUT)


def summarize(df, reference=S0):
    """Mean and 95% interval per scenario and period, and the paired difference from the reference scenario."""
    base = df[df["scenario"] == reference].set_index(["period", "replication"])
    out = []
    for (name, period), g in df.groupby(["scenario", "period"], sort=False):
        g = g.set_index("replication")
        b = base.loc[period].reindex(g.index)
        for m in MEASURES:
            half = 1.96 * g[m].std(ddof=1) / np.sqrt(len(g))
            d = g[m] - b[m]
            dh = 1.96 * d.std(ddof=1) / np.sqrt(len(g))
            out.append(dict(scenario=name, period=period, measure=m, mean=g[m].mean(), low=g[m].mean() - half, high=g[m].mean() + half,
                            diff=d.mean(), diff_low=d.mean() - dh, diff_high=d.mean() + dh))
    return pd.DataFrame(out).set_index(["scenario", "period", "measure"])


# ── measured inputs ─────────────────────────────────────────────────────────
def measured():
    from analytics.p4_setups import analysis as P4
    from analytics.p5_release_control.model import Inputs
    u = q(f"""select work_center, sum(machine_hours) as machine_hours, sum(scheduled_hours - downtime_hours) as available_hours,
                     sum(saturday_shifts) as saturday_shifts, sum(extended_hours) as extended_hours
              from marts.mart_utilization_weekly where week_year = {YEAR} group by 1""").set_index("work_center")
    su = q(f"select machine_id, sum(setup_hours) as h, count(*) as n from marts.mart_setups where work_center = 'press_brake' and setup_year = {YEAR} group by 1").set_index("machine_id")
    nov = q("select week_start, laser_utilization, wip_at_laser from marts.mart_weekly_floor where week_start between '2024-11-11' and '2024-11-25' order by 1")
    rev = float(q(f"""select sum(ol.unit_price * ol.qty) from staging.stg_erp__jobs j join staging.stg_erp__order_lines ol using (order_line_id)
                      where year(j.ship_date) = {YEAR}""").iloc[0, 0])
    brake_hours = float(q(f"select sum(machine_hours) from marts.mart_machine_weekly where work_center = 'press_brake' and week_year = {YEAR}").iloc[0, 0])
    ot = q(f"select overtime_type, sum(labor_hours) as h from marts.mart_overtime_hours where work_center = 'press_brake' and year(week_start) = {YEAR} group by 1").set_index("overtime_type")["h"]
    D4 = P4.load()
    top, st = P4.smed(D4)
    levers = float(st["top_hours_per_week"] + P4.assignment(D4).iloc[2]["hours_released_per_week"] + P4.handover_counterfactual(D4).iloc[1]["hours_per_week"])
    inp = Inputs()
    j = inp.jobs[pd.to_datetime(inp.jobs["release_date"]).dt.year == YEAR]
    std = pd.Series({k: sum(o["setup_std"] + o["run_std_hours"] for o in v if o["work_center"] == "press_brake") for k, v in inp.ops.items()})
    h = j["job_id"].map(std).fillna(0.0)
    a = ASSUME["options"]["press_brake_atc"]
    return dict(
        brake_utilization=u.loc["press_brake", "machine_hours"] / u.loc["press_brake", "available_hours"],
        laser_utilization=u.loc["laser", "machine_hours"] / u.loc["laser", "available_hours"],
        robotic_weld_utilization=u.loc["robotic_weld", "machine_hours"] / u.loc["robotic_weld", "available_hours"],
        brake_setup_hours_per_week=su["h"].sum() / WEEKS, tool_change_hours_per_week=su["h"].sum() / WEEKS * a["tool_change_share_of_setup"],
        b3_setup_hours_per_week=su.loc["B3", "h"] / WEEKS, b3_share_of_setup_hours=su.loc["B3", "h"] / su["h"].sum(), b3_setups=int(su.loc["B3", "n"]),
        p4_levers_hours_per_week=levers, november_weeks=nov,
        revenue=rev, brake_hours=brake_hours, revenue_per_brake_hour=rev / brake_hours,
        saturday_shifts=float(u.loc["press_brake", "saturday_shifts"]), extended_hours=float(u.loc["press_brake", "extended_hours"]),
        overtime_labor_hours=float(ot.sum()),
        cell_share_of_brake_standard_hours=float(h[j["cell_ok"]].sum() / h.sum()), cell_share_of_jobs=float(j["cell_ok"].mean()))


# ── money ───────────────────────────────────────────────────────────────────
def annuity(rate, years):
    return (1 - (1 + rate) ** -years) / rate


def economics(S, M, name, reference=S0):
    """One line of the payback table: the scenario against the reference for the report year, at the stated assumptions."""
    L, F, R, N = ASSUME["labor"], ASSUME["finance"], ASSUME["released_hours"], ASSUME["no_capital_package"]
    rate, crew = L["labor_rate"], L["brake_crew_per_shift"]

    def v(sc, m):
        return float(S.loc[(sc, "year", m), "mean"])

    def d(m):
        return v(reference, m) - v(name, m)

    has_package = name == PACKAGE or name.startswith("N ")
    ref_package = reference == PACKAGE
    opt = next((k for s_, k in OPTION_OF.items() if name.lower().endswith(s_.lower())), None)
    cell, tower = opt == "robotic_bending_cell", opt == "laser_tower"

    overtime_hours = d("saturday_shifts") * 8 * crew + d("extended_hours") * crew / 2
    overtime = overtime_hours * rate * (1 + L["overtime_premium"])
    setup_saved, manual_displaced, cell_hours = d("brake_setup_hours"), d("brake_hours"), v(name, "cell_hours")
    if cell:
        labor = (manual_displaced - ASSUME["options"]["robotic_bending_cell"]["tending_labor_per_cell_hour"] * cell_hours) * rate
    else:
        labor = setup_saved * rate
    if tower:
        labor += ASSUME["options"]["laser_tower"]["operator_hours_saved_per_week"] * WEEKS * rate
    weld_hours = v(name, "weld_second_shift_hours") - v(reference, "weld_second_shift_hours")
    labor -= weld_hours * N["weld_second_shift_operators"] * rate * (1 + N["shift_differential"])
    released = 0.0 if tower and not (has_package and not ref_package) else manual_displaced
    throughput = released * R["utilization_of_released_hours"] * R["contribution_margin_share"] * M["revenue_per_brake_hour"]
    one_time = maintenance = 0.0
    if opt:
        o = ASSUME["options"][opt]
        one_time += o["equipment_cost"] + o["installation_and_tooling"]
        maintenance += o["annual_maintenance"]
    if has_package and not ref_package:
        one_time += N["setup_program_one_time"]
        maintenance += N["setup_program_annual"]
    af = annuity(F["discount_rate"], F["horizon_years"])
    out = dict(scenario=name, reference=reference, one_time=one_time, maintenance=maintenance, overtime_hours_avoided=overtime_hours, overtime=overtime,
               setup_hours_saved=setup_saved, manual_brake_hours_displaced=manual_displaced, cell_hours=cell_hours, weld_second_shift_hours=weld_hours, labor=labor,
               released_constraint_hours=released, throughput=throughput)
    # the share of released constraint hours that must be sold for NPV to reach zero over the horizon
    per_hour = R["contribution_margin_share"] * M["revenue_per_brake_hour"]
    need = one_time / af - (overtime + labor - maintenance)
    share = need / (released * per_hour) if released > 0 else np.inf
    out.update(value_per_released_hour_sold=per_hour, annuity=af, breakeven_share=max(share, 0.0) if share <= 1 else np.nan,
               breakeven_hours=max(share, 0.0) * released if share <= 1 else np.nan)
    for key, net in (("without_throughput", overtime + labor - maintenance), ("with_throughput", overtime + labor + throughput - maintenance)):
        out[f"net_{key}"] = net
        out[f"payback_{key}"] = one_time / net if net > 0 and one_time > 0 else np.nan
        out[f"npv_{key}"] = -one_time + net * af
    for m in ("on_time_delivery", "lead_time_p90", "jobs_shipped"):
        out[m] = v(name, m) - v(reference, m)
    return out
