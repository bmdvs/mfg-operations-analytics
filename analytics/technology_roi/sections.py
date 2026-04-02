"""Technology ROI: the data, tables and figures of its part of the report, from the scenario runs, the marts and the assumptions file.

Built by analytics.reports.options_tested.
The scenario runs come from analytics.technology_roi.scenarios (results/scenario_runs.csv and results/laser_queue_november_2024.csv).
"""
import numpy as np
import pandas as pd

from analytics.db import q
from analytics.technology_roi import analysis as A
from analytics.technology_roi.scenarios import ASSUME, PACKAGE, QUEUE, S0
from analytics.style.style import AMBER, BRAND_BLUE, DOCS, GREEN, GREY, RED, fig, pct, save_conformed as save, sig, table

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
    return save(f, "technology_roi_option_effects", "Change in on-time delivery and 90th-percentile lead time by option")


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
    return save(f, "technology_roi_laser_queue_november_2024", "Jobs waiting at the lasers by day, November and December 2024")


def fig_npv(name="technology_roi_npv_by_share_sold", h=3.4):
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
        ["Brake utilization", f"{M['brake_utilization']:.3f}", "[[N:capacity]]"],
        ["Brake setup hours per week", d1(M["brake_setup_hours_per_week"]), "[[N:capacity]]"],
        ["of which tool change, at the assumed share", f"{M['tool_change_hours_per_week']:.1f} ({a['tool_change_share_of_setup']:.0%} of setup, assumption)", "[[N:capacity]], assumption"],
        ["Setup hours per week on B3", f"{M['b3_setup_hours_per_week']:.1f} ({pct(M['b3_share_of_setup_hours'])} of brake setup hours)", "[[N:capacity]]"],
        ["Brake hours per week released by the setup levers", d1(M["setup_levers_hours_per_week"]), "[[N:capacity]]"],
        ["Laser utilization", f"{M['laser_utilization']:.3f}", "[[N:capacity]]"],
        ["Laser utilization, weeks of November 11, 18 and 25, 2024", ", ".join(f"{x:.2f}" for x in nv["laser_utilization"]) +
         f" ({join_and([n0(x) for x in nv['wip_at_laser']])} jobs waiting)", "[[N:lead]]"],
        ["Robotic weld utilization", f"{M['robotic_weld_utilization']:.3f}", "[[N:capacity]]"],
        ["Saturday brake shifts and extended hours", f"{n0(M['saturday_shifts'])} shifts, {n0(M['extended_hours'])} hours", "[[N:quoting]]"],
        [f"Revenue of jobs shipped in {YEAR}", usd(M["revenue"]), "ERP"],
        ["Crewed brake hours worked", n0(M["brake_hours"]), "[[N:capacity]]"],
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
