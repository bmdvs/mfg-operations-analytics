"""P8 technology ROI: report, A3 and figures, from the scenario runs, the marts and the assumptions file.

Usage: python -m analytics.p8_technology_roi.build
The scenario runs come from analytics.p8_technology_roi.scenarios (results/scenario_runs.csv and results/laser_queue_november_2024.csv).
"""
import numpy as np
import pandas as pd

from analytics.db import q
from analytics.p8_technology_roi import analysis as A
from analytics.p8_technology_roi.scenarios import ASSUME, PACKAGE, QUEUE, S0
from analytics.style.style import AMBER, BRAND_BLUE, DOCS, GREEN, GREY, RED, a3_shell, fig, pct, save, shell, sig, table

YEAR, REST = A.YEAR, "Q2 to Q4"
df = A.runs()
S, SP = A.summarize(df), A.summarize(df, PACKAGE)
M = A.measured()
REPS = int(df["replication"].nunique())
NAMES = list(dict.fromkeys(df["scenario"]))
ATC, TOWER, CELL, ATC_ALL = "T Tool changer on B3", "T Laser tower on L2", "T Robotic bending cell", "T Tool changing at every brake setup (upper bound)"
N_ATC, N_TOWER, N_CELL, N_ALL = [n for n in NAMES if n.startswith("N ")]
BASE = [ATC, TOWER, CELL]
ON_PKG = [N_ATC, N_TOWER, N_CELL]
SHORT = {ATC: "Tool changer on B3", TOWER: "Laser tower on L2", CELL: "Robotic bending cell", PACKAGE: "No-capital package", ATC_ALL: "Tool changing at every setup",
         N_ATC: "Package + tool changer on B3", N_TOWER: "Package + laser tower on L2", N_CELL: "Package + robotic bending cell",
         N_ALL: "Package + tool changing at every setup", S0: "Current practice"}
E = {n: A.economics(S, M, n, S0) for n in NAMES if n != S0}
EP = {n: A.economics(S, M, n, PACKAGE) for n in NAMES if n.startswith("N ")}
F, L, R, O, NC = ASSUME["finance"], ASSUME["labor"], ASSUME["released_hours"], ASSUME["options"], ASSUME["no_capital_package"]
HORIZON = F["horizon_years"]
required = float(q("select max(required_otd_pct) from marts.mart_job_lead_time where key_account").iloc[0, 0]) / 100
batch = q("select export_batch_id from marts.mart_job_lead_time limit 1").iloc[0, 0]


def v(sc, m, period="year", col="mean", s=None):
    return float((S if s is None else s).loc[(sc, period, m), col])


def sg(x, f="{:+.1f}"):
    t = f.format(x)
    return t.replace("-", "+") if float(t.replace(",", "")) == 0 else t


def ci(r, scale=1, f="{:+.1f}"):
    return f"{sg(r['diff'] * scale, f)} ({sg(r['diff_low'] * scale, f)} to {sg(r['diff_high'] * scale, f)})"


def byp(r):
    """A change in points followed by its interval, for running text."""
    f = lambda x: sg(x * 100, "{:.1f}").replace("+", "")
    return f"{f(r['diff'])} points ({f(r['diff_low'])} to {f(r['diff_high'])})"


def pts(sc, period="year", s=None):
    return f"{v(sc, 'on_time_delivery', period, 'diff', s) * 100:.1f}"


def usd(x):
    return ("-" if x < 0 else "") + f"${abs(x):,.0f}"


def k(x):
    """Dollars to the nearest thousand, for running text."""
    return ("-" if x < 0 else "") + f"${abs(round(x, -3)):,.0f}"


def n0(x):
    return f"{x:,.0f}"


def d1(x):
    return f"{x:.1f}"


def payback(x, body=True):
    if pd.isna(x):
        return "none"
    return f"beyond {HORIZON} years" if body and x > HORIZON else f"{x:.1f}"


def breakeven(e, hours=True):
    if e["released_constraint_hours"] <= 0 or pd.isna(e["breakeven_share"]):
        return "not reached"
    return f"{e['breakeven_share']:.0%}" + (f" ({n0(e['breakeven_hours'])} hours a year)" if hours else "")


def join_and(xs):
    xs = list(xs)
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


# ── figures ─────────────────────────────────────────────────────────────────
def fig_effects():
    scen = BASE + [PACKAGE] + ON_PKG
    f, axes = fig(h=4.0, ncols=2, grid="x", sharey=True)
    y = np.arange(len(scen))[::-1]
    for ax, m, scale, xl in ((axes[0], "on_time_delivery", 100, "On-time delivery (points)"), (axes[1], "lead_time_p90", 1, "90th-percentile lead time (days)")):
        for period, off, color, lab in (("year", 0.17, BRAND_BLUE, f"{YEAR}"), (REST, -0.17, AMBER, REST)):
            r = [S.loc[(s_, period, m)] for s_ in scen]
            x = np.array([i["diff"] for i in r]) * scale
            lo, hi = np.array([i["diff_low"] for i in r]) * scale, np.array([i["diff_high"] for i in r]) * scale
            ax.errorbar(x, y + off, xerr=[x - lo, hi - x], fmt="o", color=color, markersize=4, capsize=2, linewidth=1.2, label=lab)
        ax.axvline(0, color=GREY, linewidth=1)
        ax.set_xlabel(xl, fontsize=9.5)
        ax.set_yticks(y)
        ax.set_yticklabels([SHORT[s_] for s_ in scen], fontsize=9)
    hs, ls = axes[0].get_legend_handles_labels()
    f.legend(hs, ls, frameon=False, fontsize=9, loc="lower center", ncols=2)
    f.tight_layout(rect=(0, 0.06, 1, 1))
    return save(f, "p8_option_effects", "Change in on-time delivery and 90th-percentile lead time by option")


def fig_laser():
    d = pd.read_csv(QUEUE)
    g = d.groupby(["scenario", "day"])["jobs_waiting_at_lasers"].mean().unstack("scenario")
    g.index = pd.to_datetime(g.index)
    f, ax = fig(h=3.0, w=6.8)
    ax.plot(g.index, g[S0], color=BRAND_BLUE, marker="o", markersize=3, label="Current practice")
    ax.plot(g.index, g[TOWER], color=AMBER, marker="o", markersize=3, label="Laser tower on L2")
    ax.axvspan(pd.Timestamp("2024-11-11"), pd.Timestamp("2024-12-01"), color=GREY, alpha=0.15, linewidth=0)
    ax.set_ylabel("Jobs waiting at the lasers")
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    ax.tick_params(axis="x", labelsize=8.5)
    f.tight_layout()
    return save(f, "p8_laser_queue_november_2024", "Jobs waiting at the lasers by day, November and December 2024")


def fig_npv(name="p8_npv_by_share_sold", h=3.4):
    f, ax = fig(h=h, w=6.8)
    x = np.linspace(0, 1, 101)
    ax.set_ylim(-2.4, 5.6)
    for n, color in ((CELL, BRAND_BLUE), (ATC, AMBER), (PACKAGE, GREEN), (TOWER, GREY)):
        e = E[n]
        base = e["net_without_throughput"]
        npv = -e["one_time"] + (base + e["released_constraint_hours"] * x * e["value_per_released_hour_sold"]) * e["annuity"]
        ax.plot(x * 100, sig(npv / 1e6), color=color, linewidth=1.8, label=SHORT[n])
        if e["breakeven_share"] == e["breakeven_share"]:
            ax.plot(sig([e["breakeven_share"] * 100]), [0], marker="o", color=color, markersize=6, zorder=5)
            ax.annotate(f"{e['breakeven_share']:.0%}, {e['breakeven_hours']:,.0f} h", (float(sig(e["breakeven_share"] * 100)), 0), textcoords="offset points",
                        xytext=(-6, (-0.42 * h * 16) if n != CELL else 7), fontsize=8, color=color, ha="left" if n != CELL else "right",
                        arrowprops=dict(arrowstyle="-", color=color, linewidth=0.6) if n != CELL else None)
    ax.axhline(0, color=RED, linewidth=1, linestyle="--")
    ax.axvline(R["utilization_of_released_hours"] * 100, color=GREY, linewidth=1, linestyle=":")
    ax.annotate(f"assumption: {R['utilization_of_released_hours']:.0%} sold", (R["utilization_of_released_hours"] * 100, ax.get_ylim()[1]), textcoords="offset points",
                xytext=(4, -10), fontsize=8)
    ax.set_xlabel("Share of released brake hours sold (%)")
    ax.set_ylabel(f"NPV over {HORIZON} years ($ million)")
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    f.tight_layout()
    return save(f, name, "NPV against the share of released brake hours sold")


# ── tables ──────────────────────────────────────────────────────────────────
def t_measured(short=False):
    nv = M["november_weeks"]
    a = O["press_brake_atc"]
    rows = [
        ["Brake utilization", f"{M['brake_utilization']:.3f}", "P3"],
        ["Brake setup hours per week", d1(M["brake_setup_hours_per_week"]), "P4"],
        ["of which tool change, at the assumed share", f"{M['tool_change_hours_per_week']:.1f} ({a['tool_change_share_of_setup']:.0%} of setup, assumption)", "P4, assumption"],
        ["Setup hours per week on B3", f"{M['b3_setup_hours_per_week']:.1f} ({pct(M['b3_share_of_setup_hours'])} of brake setup hours)", "P4"],
        ["Brake hours per week released by the P4 levers", d1(M["p4_levers_hours_per_week"]), "P4"],
        ["Laser utilization", f"{M['laser_utilization']:.3f}", "P3"],
        ["Laser utilization, weeks of November 11, 18 and 25, 2024", ", ".join(f"{x:.2f}" for x in nv["laser_utilization"]) +
         f" ({join_and([n0(x) for x in nv['wip_at_laser']])} jobs waiting)", "P1"],
        ["Robotic weld utilization", f"{M['robotic_weld_utilization']:.3f}", "P3"],
        ["Saturday brake shifts and extended hours", f"{n0(M['saturday_shifts'])} shifts, {n0(M['extended_hours'])} hours", "P6"],
        [f"Revenue of jobs shipped in {YEAR}", usd(M["revenue"]), "ERP"],
        ["Crewed brake hours worked", n0(M["brake_hours"]), "P3"],
        ["Revenue per brake hour", usd(M["revenue_per_brake_hour"]), "the two lines above"],
        ["Brake standard hours a robotic cell can run", f"{pct(M['cell_share_of_brake_standard_hours'])} (light, repeat parts, lots of 25 or more)", "ERP routings"],
    ]
    if short:
        rows = [r for k_, r in enumerate(rows) if k_ not in (2, 4, 8, 9, 10)]
    return table(pd.DataFrame(rows, columns=["Measured input", f"{YEAR}", "From"]))


EFFECT = [("on_time_delivery", 100, "{:+.1f}", "On time (points)"), ("lead_time_p90", 1, "{:+.1f}", "90th-percentile lead time (days)"), ("wip_mean", 1, "{:+.0f}", "Mean WIP"),
          ("saturday_shifts", 1, "{:+.1f}", "Saturday shifts"), ("extended_hours", 1, "{:+.0f}", "Extended hours"),
          ("brake_utilization", 100, "{:+.1f}", "Brake utilization (points)"), ("laser_utilization", 100, "{:+.1f}", "Laser utilization (points)"),
          ("jobs_shipped", 1, "{:+.0f}", "Jobs shipped")]
LEVEL = [("on_time_delivery", "{:.1%}", "On time"), ("lead_time_p90", "{:.1f}", "90th-percentile lead time"), ("wip_mean", "{:.0f}", "Mean WIP"),
         ("saturday_shifts", "{:.1f}", "Saturday shifts"), ("extended_hours", "{:.0f}", "Extended hours"), ("brake_utilization", "{:.3f}", "Brake utilization"),
         ("laser_utilization", "{:.3f}", "Laser utilization"), ("jobs_shipped", "{:,.0f}", "Jobs shipped")]


def t_effects(scen, period, s=None, measures=EFFECT):
    s = S if s is None else s
    rows = [[SHORT[n]] + [ci(s.loc[(n, period, m)], sc, f) for m, sc, f, _ in measures] for n in scen]
    return table(pd.DataFrame(rows, columns=["Option"] + [c for _, _, _, c in measures]))


def t_effects_body():
    ms = [EFFECT[0], EFFECT[1], EFFECT[3], EFFECT[7]]
    rows = []
    for n in BASE + [PACKAGE]:
        rows.append([SHORT[n]] + [ci(S.loc[(n, "year", m)], sc, f) for m, sc, f, _ in ms] + [ci(S.loc[(n, REST, m)], sc, f) for m, sc, f, _ in ms[:2]])
    return table(pd.DataFrame(rows, columns=["Option"] + [f"{c}, {YEAR}" for _, _, _, c in ms] + [f"{c}, {REST}" for _, _, _, c in ms[:2]]))


def t_levels(period):
    rows = [[SHORT[n]] + [f.format(v(n, m, period)) for m, f, _ in LEVEL] for n in NAMES]
    return table(pd.DataFrame(rows, columns=["Scenario"] + [c for _, _, c in LEVEL]))


THRU = f"Throughput value of released constraint hours (assumption: {R['utilization_of_released_hours']:.0%} sold at {R['contribution_margin_share']:.0%} margin)"


def t_money(pairs, body=True, summary=S):
    head = ("<tr><th rowspan='2'>Option</th><th rowspan='2'>One-time cost</th><th rowspan='2'>Maintenance a year</th><th rowspan='2'>Overtime avoided</th>"
            "<th rowspan='2'>Labor</th><th colspan='3' style='text-align:center'>Overtime and labor alone</th>"
            f"<th colspan='4' style='text-align:center'>With the {THRU[0].lower() + THRU[1:]}</th>"
            "<th rowspan='2'>Share of released brake hours sold for NPV of zero</th><th rowspan='2'>Jobs shipped in the model</th></tr>"
            "<tr><th>Net a year</th><th>Payback (years)</th><th>NPV</th><th>Throughput value</th><th>Net a year</th><th>Payback (years)</th><th>NPV</th></tr>")
    rows = ""
    for n, e in pairs:
        js = summary.loc[(n, "year", "jobs_shipped")]
        cells = [SHORT[n], usd(e["one_time"]), usd(e["maintenance"]), usd(e["overtime"]), usd(e["labor"]), usd(e["net_without_throughput"]),
                 payback(e["payback_without_throughput"], body), usd(e["npv_without_throughput"]), usd(e["throughput"]), usd(e["net_with_throughput"]),
                 payback(e["payback_with_throughput"], body), usd(e["npv_with_throughput"]), breakeven(e), ci(js, 1, "{:+.0f}")]
        rows += "<tr>" + "".join(f"<td class='{'num' if k_ else ''}'>{c}</td>" for k_, c in enumerate(cells)) + "</tr>"
    return f"<table class='data' style='font-size:12px'><thead>{head}</thead><tbody>{rows}</tbody></table>"


def t_hours(scen):
    rows = []
    for n in scen:
        e = E[n]
        rows.append([SHORT[n], n0(e["overtime_hours_avoided"]), n0(e["setup_hours_saved"]), n0(e["manual_brake_hours_displaced"]), n0(e["cell_hours"]),
                     n0(e["weld_second_shift_hours"]), n0(e["released_constraint_hours"]), pct(v(n, "b3_setup_hours") / v(n, "brake_setup_hours"))])
    return table(pd.DataFrame(rows, columns=["Option", "Overtime operator hours avoided", "Brake setup hours saved", "Manual brake hours displaced", "Robotic cell hours",
                                             "Weld second-shift hours added", "Released constraint hours carrying throughput value", "B3 share of brake setup hours"]))


def t_november():
    rows = []
    for n in [S0, TOWER, PACKAGE, N_TOWER]:
        y = lambda m: S.loc[(n, "year", m)]
        rows.append([SHORT[n], n0(y("laser_queue_nov_2024")["mean"]), "" if n == S0 else ci(y("laser_queue_nov_2024"), 1, "{:+.0f}"),
                     pct(y("on_time_released_nov_2024")["mean"]), "" if n == S0 else ci(y("on_time_released_nov_2024"), 100),
                     d1(y("lead_time_released_nov_2024")["mean"]), "" if n == S0 else ci(y("lead_time_released_nov_2024"))])
    return table(pd.DataFrame(rows, columns=["Scenario", "Jobs waiting at the lasers, daily mean", "Against current practice", "On time, jobs released in the weeks",
                                             "Against current practice (points)", "Median lead time, jobs released in the weeks", "Against current practice (days)"]))


UNITS = [
    ("options.press_brake_atc.equipment_cost", "Press brake with automatic tool changing: equipment", "USD"),
    ("options.press_brake_atc.installation_and_tooling", "installation, tooling and training", "USD"),
    ("options.press_brake_atc.annual_maintenance", "maintenance", "USD a year"),
    ("options.press_brake_atc.tool_change_share_of_setup", "share of a brake setup that is tool change", "share"),
    ("options.press_brake_atc.tool_change_reduction", "share of the tool change the changer removes", "share"),
    ("options.press_brake_atc.replaces", "brake it replaces; the reduction applies to the setups on that machine", ""),
    ("options.laser_tower.equipment_cost", "Second automated laser tower: equipment", "USD"),
    ("options.laser_tower.installation_and_tooling", "installation", "USD"),
    ("options.laser_tower.annual_maintenance", "maintenance", "USD a year"),
    ("options.laser_tower.added_laser_hours_per_week", "unattended laser hours added", "hours a week"),
    ("options.laser_tower.laser_fitted", "laser fitted", ""),
    ("options.laser_tower.operator_hours_saved_per_week", "operator hours saved", "hours a week"),
    ("options.robotic_bending_cell.equipment_cost", "Robotic bending cell: equipment", "USD"),
    ("options.robotic_bending_cell.installation_and_tooling", "installation, tooling and programming", "USD"),
    ("options.robotic_bending_cell.annual_maintenance", "maintenance", "USD a year"),
    ("options.robotic_bending_cell.added_crewed_hours_per_week", "brake hours added", "hours a week"),
    ("options.robotic_bending_cell.share_of_part_mix", "share of brake standard hours it can run", "share"),
    ("options.robotic_bending_cell.eligible_parts", "parts it can run", ""),
    ("options.robotic_bending_cell.tending_labor_per_cell_hour", "operator hours per cell hour", "hours"),
    ("no_capital_package.setup_program_one_time", "No-capital package: setup program, one time", "USD"),
    ("no_capital_package.setup_program_annual", "setup program upkeep", "USD a year"),
    ("no_capital_package.weld_second_shift_operators", "operators on the weld cell's second shift", "operators"),
    ("no_capital_package.shift_differential", "second-shift differential", "share of the labor rate"),
    ("labor.labor_rate", "Labor rate, loaded", "USD an hour"),
    ("labor.overtime_premium", "Overtime premium", "share of the labor rate"),
    ("labor.brake_crew_per_shift", "Operators on a Saturday or extended brake shift", "operators"),
    ("finance.discount_rate", "Discount rate", "a year"),
    ("finance.horizon_years", "Horizon", "years"),
    ("finance.residual_value_share", "Residual value", "share of equipment cost"),
    ("finance.taxes_and_depreciation", "Taxes and depreciation", ""),
    ("released_hours.utilization_of_released_hours", "Share of released constraint hours sold", "share"),
    ("released_hours.contribution_margin_share", "Contribution margin on revenue per brake hour", "share"),
    ("released_hours.laser_hours_carry_throughput_value", "Laser hours carry throughput value", ""),
]


def t_assumptions():
    def get(path):
        d = ASSUME
        for p_ in path.split("."):
            d = d[p_]
        return d
    rows = []
    for path, name, unit in UNITS:
        x = get(path)
        rows.append([name, f"{x:,}" if isinstance(x, (int, float)) and not isinstance(x, bool) else {True: "yes", False: "no"}.get(x, str(x)), unit, "Supplied by the shop"])
    return table(pd.DataFrame(rows, columns=["Assumption", "Value", "Unit", "Source"]))


# ── report ──────────────────────────────────────────────────────────────────
HEADER_META = (f"Custom sheet-metal fabrication job shop, about 120 employees, one plant. Three capital options and the no-capital package on the shop model, jobs "
               f"shipped in {YEAR}, whole year and {REST}.<br>Sources: ERP, shop-floor data collection, maintenance exports (batch {batch}); costs and rates supplied "
               f"by the shop; {REPS} replications per scenario, 95% intervals. Payback and NPV are expected values under the stated assumptions.")


def report():
    ea, et, ec, epk = E[ATC], E[TOWER], E[CELL], E[PACKAGE]
    b = []
    b.append("<h2 id='f1'>1. Measured inputs</h2>")
    b.append(f"<p>The brakes ran at {M['brake_utilization']:.3f} in {YEAR} with {d1(M['brake_setup_hours_per_week'])} setup hours a week, {pct(M['b3_share_of_setup_hours'])} "
             f"of them on B3; the lasers ran at {M['laser_utilization']:.3f} and the robotic weld cell at {M['robotic_weld_utilization']:.3f}. Jobs shipped in {YEAR} "
             f"carried {usd(M['revenue'])} of revenue over {n0(M['brake_hours'])} crewed brake hours, {usd(M['revenue_per_brake_hour'])} a brake hour.</p>")
    b.append(t_measured())
    b.append(f"<div class='caption'>Table 1. Measured inputs for {YEAR}, from the marts.</div>")

    b.append("<h2 id='f2'>2. What each option does on the floor</h2>")
    b.append(f"<p>For the year the robotic bending cell raises on-time delivery by {pts(CELL)} points, the tool changer on B3 by {pts(ATC)}, the laser tower by "
             f"{pts(TOWER)} and the no-capital package by {pts(PACKAGE)}. In {REST} every capital option adds under a point ({pts(ATC, REST)}, {pts(TOWER, REST)} and "
             f"{pts(CELL, REST)}) against {pts(PACKAGE, REST)} for the package.</p>")
    b.append(t_effects_body())
    b.append(f"<div class='caption'>Table 2. Each option against current practice, {YEAR} and {REST}, with 95% intervals.</div>")
    b.append(fig_effects())
    b.append(f"<div class='caption'>Figure 1. Change in on-time delivery and 90th-percentile lead time against current practice, by option alone and on the no-capital "
             f"package, {YEAR} and {REST}, with 95% intervals.</div>")

    b.append("<h2 id='f3'>3. The tool changer on B3</h2>")
    b.append(f"<p>A press brake with automatic tool changing in place of B3 raises on-time delivery by {byp(S.loc[(ATC, 'year', 'on_time_delivery')])} for "
             f"the year and shortens the 90th percentile by {d1(-v(ATC, 'lead_time_p90', col='diff'))} days; it saves {d1(ea['setup_hours_saved'] / A.WEEKS)} setup "
             f"hours a week, against {d1(epk['setup_hours_saved'] / A.WEEKS)} for the no-capital package. Covering every brake setup at the same price would match "
             f"the robotic cell ({sg(v(ATC_ALL, 'on_time_delivery', col='diff') * 100)} points, {d1(E[ATC_ALL]['setup_hours_saved'] / A.WEEKS)} setup hours a week); "
             f"one machine covers B3's {pct(v(S0, 'b3_setup_hours') / v(S0, 'brake_setup_hours'), 0)} of setup hours.</p>")

    b.append("<h2 id='f4'>4. The robotic bending cell</h2>")
    b.append(f"<p>The cell raises on-time delivery by {byp(S.loc[(CELL, 'year', 'on_time_delivery')])} for the year, shortens the 90th percentile by "
             f"{d1(-v(CELL, 'lead_time_p90', col='diff'))} days and removes {d1(-v(CELL, 'saturday_shifts', col='diff'))} of {d1(v(S0, 'saturday_shifts'))} Saturday "
             f"shifts. The parts it can run are {pct(M['cell_share_of_brake_standard_hours'])} of brake standard hours; it works {n0(ec['cell_hours'] / A.WEEKS)} hours "
             f"a week and takes {n0(ec['manual_brake_hours_displaced'] / A.WEEKS)} hours a week off the manual brakes, whose setup hours rise by "
             f"{n0(-ec['setup_hours_saved'])} a year. On top of the package it reaches {pct(v(N_CELL, 'on_time_delivery'))} on time for the year and "
             f"{pct(v(N_CELL, 'on_time_delivery', REST))} in {REST}, with brake utilization at {v(N_CELL, 'brake_utilization'):.2f}.</p>")

    b.append("<h2 id='f5'>5. The laser tower</h2>")
    b.append(f"<p>The tower clears the laser queue and changes nothing downstream: in the three weeks from November 11, 2024 the jobs waiting at the lasers fall from "
             f"{n0(v(S0, 'laser_queue_nov_2024'))} to {n0(v(TOWER, 'laser_queue_nov_2024'))} a day and the jobs released in those weeks ship "
             f"{pct(v(TOWER, 'on_time_released_nov_2024'))} on time against {pct(v(S0, 'on_time_released_nov_2024'))}; the package alone lifts those jobs to "
             f"{pct(v(PACKAGE, 'on_time_released_nov_2024'))}. For the year the tower's effect is {byp(S.loc[(TOWER, 'year', 'on_time_delivery')])} and in "
             f"{REST} {byp(S.loc[(TOWER, REST, 'on_time_delivery')])}.</p>")
    b.append(fig_laser())
    b.append("<div class='caption'>Figure 2. Jobs waiting at the lasers at the end of each day, November 4 to December 13, 2024, current practice against the laser "
             "tower; the shaded weeks are those from November 11.</div>")

    b.append("<h2 id='f6'>6. Payback and NPV</h2>")
    b.append(f"<p>On overtime and labor alone no option pays back within the {HORIZON}-year horizon, and the no-capital package is net negative "
             f"({k(-epk['net_without_throughput'])} a year, the weld cell's second shift). If half the released brake hours are sold at the stated margin the robotic "
             f"cell pays back in {d1(ec['payback_with_throughput'])} years, the tool changer on B3 in {d1(ea['payback_with_throughput'])}, the tower not at all, and "
             f"the package in {d1(epk['payback_with_throughput'])}. NPV reaches zero when {breakeven(ec, False)} of the cell's released brake hours are sold "
             f"({n0(ec['breakeven_hours'])} hours a year), {breakeven(ea, False)} of the tool changer's ({n0(ea['breakeven_hours'])}) and {breakeven(epk, False)} of the "
             f"package's ({n0(epk['breakeven_hours'])}); the tower releases no constraint hours.</p>")
    b.append(t_money([(n, E[n]) for n in BASE + [PACKAGE]]))
    b.append(f"<div class='caption'>Table 3. Payback and NPV against current practice at {F['discount_rate']:.0%} over {HORIZON} years, before tax: overtime and labor "
             f"alone, and with the throughput value of released constraint hours.</div>")
    b.append(fig_npv())
    b.append(f"<div class='caption'>Figure 3. NPV over {HORIZON} years against the share of released brake hours sold, with the zero line and the 50% assumption "
             f"marked.</div>")

    b.append("<h2 id='f7'>7. Added to the package</h2>")
    b.append(f"<p>On top of the no-capital package the robotic cell adds {pts(N_CELL, s=SP)} points for the year, the tool changer on B3 {pts(N_ATC, s=SP)} and the "
             f"laser tower {pts(N_TOWER, s=SP)}. At its own cost against what it adds, the cell reaches an NPV of zero at {breakeven(EP[N_CELL])} of released brake "
             f"hours sold and the tool changer at {breakeven(EP[N_ATC])}.</p>")
    b.append(t_money([(n, EP[n]) for n in ON_PKG], summary=SP))
    b.append("<div class='caption'>Table 4. Each option added to the no-capital package: its own cost against what it adds beyond the package.</div>")

    b.append("<h2 id='f8'>8. The package against the machines</h2>")
    b.append(f"<p>The no-capital package delivers more on-time improvement than the tool changer on B3 ({pts(PACKAGE)} against {pts(ATC)} points) and "
             f"{pct(v(PACKAGE, 'on_time_delivery', col='diff') / v(CELL, 'on_time_delivery', col='diff'), 0)} of the robotic cell's ({pts(CELL)}), for "
             f"{usd(epk['one_time'])} against {usd(ea['one_time'])} and {usd(ec['one_time'])}.</p>")

    b.append("<h2 id='rec'>Recommendation</h2>")
    b.append(f"<p>Implement the no-capital package first. The robotic bending cell is the capital option with the largest effect and the lowest break-even: take it up "
             f"when the shop can show that {n0(EP[N_CELL]['breakeven_hours'])} of the released brake hours a year will be sold "
             f"({n0(ec['breakeven_hours'])} without the package). Take the tool changer on B3 only if {breakeven(ea, False)} of its released hours "
             f"({n0(ea['breakeven_hours'])} a year) will be sold. Do not buy the laser tower.</p>")

    b.append("<h2 id='method'>Method and data</h2>")
    alone_js = max(abs(v(n, "jobs_shipped", col="diff")) for n in BASE + [ATC_ALL])
    b.append(f"<p>The options run on the P5 shop model, {REPS} replications each; current practice and the no-capital package are the P5 runs. The tool changer "
             f"multiplies the setups that run on B3 by {1 - O['press_brake_atc']['tool_change_share_of_setup'] * O['press_brake_atc']['tool_change_reduction']:.4f}, "
             f"dispatch unchanged; the laser tower adds 6 unattended hours after second shift on L2; the robotic cell is a sixth brake on two shifts at "
             f"{O['robotic_bending_cell']['added_crewed_hours_per_week'] / 80:.3f} availability that runs light, repeat parts in lots of 25 or more.<br>"
             f"Overtime is the model's Saturday shifts and extended hours against current practice at a two-operator crew, the labor rate and the premium. Labor "
             f"lines value hours saved or added at the loaded rate whether or not headcount changes: setup hours saved, manual brake hours displaced less the "
             f"cell's own hours at {O['robotic_bending_cell']['tending_labor_per_cell_hour']} operator, the weld cell's second-shift hours with the differential, and "
             f"the tower's operator hours.<br>"
             f"The throughput line assumes the released hours are sold; the model, replaying the {YEAR} orders, ships within {n0(alone_js)} jobs of current practice "
             f"under every option alone. Only brake hours carry throughput value. The robotic cell raises setup hours on the manual brakes by "
             f"{n0(-E[CELL]['setup_hours_saved'])} a year because it takes the long runs and leaves the short lots.<br>"
             f"Payback is the one-time cost over the net annual benefit; NPV discounts {HORIZON} years of that benefit at {F['discount_rate']:.0%}, with no residual "
             f"value, before tax.</p>")
    b.append(t_assumptions())
    b.append("<div class='caption'>Table 5. Assumptions.</div>")

    b.append("<h2 id='appendix'>Appendix</h2>")
    k_ = 6
    for period, pl in (("year", f"{YEAR}"), (REST, f"{YEAR} {REST}")):
        b.append(f"<h3>Table {k_}. Scenario results, {pl}</h3>" + t_levels(period))
        b.append(f"<h3>Table {k_ + 1}. Difference from current practice, {pl}</h3>" + t_effects([n for n in NAMES if n != S0], period))
        b.append(f"<h3>Table {k_ + 2}. On top of the no-capital package: difference from the package, {pl}</h3>" + t_effects(ON_PKG + [N_ALL], period, SP))
        k_ += 3
    b.append(f"<h3>Table {k_}. Hours behind the money lines, per year, against current practice</h3>" + t_hours([n for n in NAMES if n != S0]))
    b.append(f"<h3>Table {k_ + 1}. The laser tower in the weeks of November 11 to December 1, 2024</h3>" + t_november())
    b.append(f"<h3>Table {k_ + 2}. Payback and NPV against current practice, every scenario</h3>" + t_money([(n, E[n]) for n in NAMES if n != S0], body=False))
    b.append(f"<h3>Table {k_ + 3}. Each option added to the no-capital package, with the sensitivity</h3>" +
             t_money([(n, EP[n]) for n in ON_PKG + [N_ALL]], body=False, summary=SP))
    toc = [("f1", "Measured inputs"), ("f2", "On the floor"), ("f3", "Tool changer"), ("f4", "Robotic cell"), ("f5", "Laser tower"), ("f6", "Payback and NPV"),
           ("f7", "Added to the package"), ("f8", "Package against machines"), ("rec", "Recommendation"), ("method", "Method and data"), ("appendix", "Appendix")]
    (DOCS / "reports").mkdir(parents=True, exist_ok=True)
    (DOCS / "reports" / "p8_technology_roi.html").write_text(shell("Technology ROI", "Project 8 report", HEADER_META, "\n".join(b), toc), encoding="utf8")


COUNTERMEASURES = [
    ("Implement the no-capital package: setup program (May 2026), weld cell second shift (April 2026), planned Saturdays (November 2026), as in the P5 A3",
     "Brake supervisor, production manager, plant manager", "April to November 2026"),
    ("Prepare the robotic bending cell case with a sold-hours test", "Plant manager, sales manager", "June 2026"),
    ("Decline the laser tower", "Plant manager", "January 2026"),
]


def a3():
    ea, et, ec, epk = E[ATC], E[TOWER], E[CELL], E[PACKAGE]
    left, right = [], []
    left.append(f"<section><h2>Background and problem</h2><p>The no-capital package takes on-time delivery to {pct(v(PACKAGE, 'on_time_delivery'))} for the year "
                f"against the {pct(required, 0)} target.<br>Three capital options are before the shop: a press brake with automatic tool changing "
                f"({usd(ea['one_time'])}), a second automated laser tower ({usd(et['one_time'])}) and a robotic bending cell ({usd(ec['one_time'])}).</p></section>")
    left.append(f"<section><h2>Current condition</h2>{t_measured(short=True)}<div class='caption'>Measured inputs for {YEAR}.</div></section>")
    left.append(f"<section><h2>Target</h2><p>{pct(required, 0)} on time in every quarter.</p></section>")
    right.append(
        f"<section><h2>Analysis</h2>{fig_npv('p8_a3_npv_by_share_sold', 2.4)}<div class='caption'>NPV over {HORIZON} years against the share of released brake hours "
        f"sold.</div><ul>"
        f"<li>On overtime and labor alone no option pays back within {HORIZON} years; the package is net negative by {k(-epk['net_without_throughput'])} a year.</li>"
        f"<li>NPV reaches zero at {breakeven(ec, False)} of released brake hours sold for the cell, {breakeven(ea, False)} for the tool changer on B3 and "
        f"{breakeven(epk, False)} for the package; the tower releases none.</li>"
        f"<li>The cell raises on-time delivery {pts(CELL)} points for the year, the tool changer {pts(ATC)}, the package {pts(PACKAGE)}; every capital option adds "
        f"under a point in {REST}.</li>"
        f"<li>The tower cuts the November 2024 laser queue from {n0(v(S0, 'laser_queue_nov_2024'))} to {n0(v(TOWER, 'laser_queue_nov_2024'))} jobs and leaves those "
        f"jobs' delivery at {pct(v(TOWER, 'on_time_released_nov_2024'))}.</li></ul></section>")
    right.append(f"<section><h2>Countermeasures</h2>{table(pd.DataFrame(COUNTERMEASURES, columns=['Action', 'Owner', 'When']))}</section>")
    right.append(f"<section><h2>Expected results</h2><p>Expected from the model: the robotic cell on the package raises on-time delivery by "
                 f"{byp(S.loc[(N_CELL, 'year', 'on_time_delivery')])} to {pct(v(N_CELL, 'on_time_delivery'))} for the year; its NPV reaches zero when "
                 f"{n0(EP[N_CELL]['breakeven_hours'])} released brake hours a year are sold ({breakeven(EP[N_CELL], False)}). No option reaches the target on the promises as made; "
                 f"quoted lead times are P7.</p></section>")
    right.append("<section><h2>Follow-up</h2><p>Released brake hours sold tracked monthly against the break-even once the package is in place.</p></section>")
    (DOCS / "a3").mkdir(parents=True, exist_ok=True)
    (DOCS / "a3" / "p8_technology_roi.html").write_text(a3_shell("Technology ROI", "Project 8 A3", HEADER_META, "\n".join(left), "\n".join(right)), encoding="utf8")


def main():
    report()
    a3()
    print("wrote docs/reports/p8_technology_roi.html and docs/a3/p8_technology_roi.html")


if __name__ == "__main__":
    main()
