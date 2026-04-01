"""P3 the constraint, utilization and variability: report, A3 and figures.

Usage: python -m analytics.p3_constraint.build
"""
import numpy as np
import pandas as pd

from analytics.db import q
from analytics.p3_constraint import analysis as A
from analytics.style.style import ACCENT, AMBER, BRAND_BLUE, DOCS, GREY, LIGHT_BLUE, RED, a3_shell, fig, pct, save, sig, report_shell, table

YEAR, REST = A.YEAR, "Q2 to Q4"
WC = {"press_brake": "Press brake", "grind_deburr": "Grind and deburr", "inspection_pack": "Inspection and pack", "hardware": "Hardware", "weld": "Weld",
      "robotic_weld": "Robotic weld", "assembly": "Assembly", "powder_coat": "Powder coat", "laser": "Laser", "punch": "Punch"}
MACHINE = {"R1": "Robotic weld cell"}


def d1(x):
    return f"{x:.1f}"


def d2(x):
    return f"{x:.2f}"


def d3(x):
    return f"{x:.3f}"


def n0(x):
    return f"{x:,.0f}"


def rng(lo, hi, f=d2):
    return f"{f(lo)} to {f(hi)}"


D = A.load()
U = A.utilization(D)
UY, UR = U[U["period"] == "year"].set_index("work_center"), U[U["period"] == REST].set_index("work_center")
M = A.machines(D)
MY, MR = M[M["period"] == "year"].set_index("machine_id"), M[M["period"] == REST].set_index("machine_id")
FITS, POS = A.curves(D, 13)
FITS1, _ = A.curves(D, 1)
FB, FB1 = FITS.set_index("work_center").loc["press_brake"], FITS1.set_index("work_center").loc["press_brake"]
PY, PR = POS[POS["period"] == "year"].set_index("work_center"), POS[POS["period"] == REST].set_index("work_center")
BINS = A.brake_bins(D)
VAR = A.variability(D)
POW = A.powder(D).set_index("period")
LAS_ANN, LAS_NOV = A.laser(D)
ROB = A.robot(D).set_index("period")
SV, PAR = A.setup_variability(D, FITS, POS)
SV = SV.set_index("period")
BQ = A.brake_quarters(D).set_index("start_quarter")
LW_N, LW_ALL, LW_LIST = A.laser_weeks_at(D)
COLORS = q("select color, days_per_week from marts.mart_powder_color_days order by days_per_week desc, color")
BRAKES = ["B1", "B2", "B3", "B4", "B5"]


def var(source):
    return float(VAR[VAR["source"].str.startswith(source)]["value"].iloc[0])


# ── figures ─────────────────────────────────────────────────────────────────
def fig_util():
    d = UY.sort_values("utilization", ascending=False)
    f, ax = fig(h=3.4)
    x = np.arange(len(d))
    ax.bar(x - 0.2, d["utilization"], width=0.38, color=BRAND_BLUE, label="Utilization")
    ax.bar(x + 0.2, d["uptime"], width=0.38, color=LIGHT_BLUE, label="Machine uptime")
    ax.set_xticks(x)
    ax.set_xticklabels([WC[w] for w in d.index], rotation=20, ha="right")
    ax.set_ylim(0, 1.08)
    ax.legend(frameon=False, ncol=2, loc="upper right")
    f.tight_layout()
    return save(f, "p3_utilization_uptime", "Utilization and machine uptime by work center")


def fig_curve(name="p3_brake_queue_curve", h=3.9):
    w = D["uw"][(D["uw"]["work_center"] == "press_brake") & (D["uw"]["weekdays"] == 5) & D["uw"]["queue_mean"].notna()].sort_values("week_start")
    m, k = int(FB["machines"]), float(FB["k"])
    f, ax = fig(h=h)
    old, cur = w[w["week_year"] != YEAR], w[w["week_year"] == YEAR]
    ax.scatter(sig(old["utilization"]), sig(old["queue_mean"]), s=14, color=GREY, alpha=0.7, label="Week, 2023 and 2024")
    ax.scatter(sig(cur["utilization"]), sig(cur["queue_mean"]), s=16, color=ACCENT, label=f"Week, {YEAR}")
    u = np.linspace(0.5, 0.96, 200)
    ax.plot(u, sig(k * A.vut_factor(u, m)), color=BRAND_BLUE, linewidth=2.2, label="Curve fitted on 13-week windows")
    for x in A.QUEUE_AT:
        y = float(sig(k * float(A.vut_factor(x, m))))
        ax.plot([x], [y], marker="o", color=RED, markersize=6)
        ax.annotate(f"{y:.2f}", (x, y), textcoords="offset points", xytext=(-26, 6), fontsize=9, color=RED)
    ax.set_xlim(0.5, 1.02)
    ax.set_xlabel("Brake utilization")
    ax.set_ylabel("Queue per operation (working days)")
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    f.tight_layout()
    return save(f, name, "Brake queue against utilization")


def fig_robot(name="p3_robotic_weld_weekly", h=3.3):
    w = D["uw"][(D["uw"]["work_center"] == "robotic_weld") & (D["uw"]["week_year"] == YEAR)].sort_values("week_start")
    x = pd.to_datetime(w["week_start"])
    f, ax = fig(h=h)
    ax.bar(x, w["utilization"], width=5, color=LIGHT_BLUE, label="Utilization (left)")
    ax.axhline(0.95, color=GREY, linewidth=1, linestyle="--")
    ax.set_ylabel("Utilization")
    ax.set_ylim(0, 1.3)
    ax2 = ax.twinx()
    ax2.plot(x, w["queue_mean"], color=AMBER, linewidth=1.8, marker="o", markersize=3, label="Queue per operation (right)")
    ax2.set_ylabel("Working days")
    ax2.spines["top"].set_visible(False)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, frameon=False, fontsize=9, ncol=2, loc="upper left")
    f.tight_layout()
    return save(f, name, "Robotic weld cell weekly utilization and queue")


# ── tables ──────────────────────────────────────────────────────────────────
def t_machines():
    rows = []
    for mid in BRAKES + ["R1"]:
        y, r = MY.loc[mid], MR.loc[mid]
        rows.append([MACHINE.get(mid, mid), n0(y["crewed_shifts"]), d3(y["utilization"]), d2(y["queue_mean"]), d2(y["queue_median"]), d1(y["queue_p90"]),
                     d3(r["utilization"]), d2(r["queue_mean"]), d2(r["queue_median"]), d1(r["queue_p90"])])
    return table(pd.DataFrame(rows, columns=["Machine", "Crewed shifts", f"Utilization, {YEAR}", "Queue mean", "Median", "90th percentile",
                                             f"Utilization, {REST}", f"Queue mean, {REST}", f"Median, {REST}", f"90th percentile, {REST}"]))


def t_bins():
    rows = [[r.band, n0(r.weeks), d2(r.queue_mean), d2(r.queue_median)] for r in BINS.itertuples()]
    return table(pd.DataFrame(rows, columns=["Brake utilization in the week", "Weeks", "Mean queue per operation", "Median"]))


def t_var():
    rows = [[r.source, r.measure, d2(r.value)] for r in VAR.itertuples()]
    return table(pd.DataFrame(rows, columns=["Source", "Measure", f"Value, {YEAR}"]))


def t_util():
    rows = []
    for w in UY.sort_values("utilization", ascending=False).index:
        y, r = UY.loc[w], UR.loc[w]
        rows.append([WC[w], n0(y["machines"]), n0(y["scheduled"]), n0(y["machine"]), n0(y["down"]), d3(y["utilization"]), d3(y["uptime"]),
                     d2(y["queue_mean"]) if y["queue_mean"] == y["queue_mean"] else "", d3(r["utilization"]), d3(r["uptime"]),
                     d2(r["queue_mean"]) if r["queue_mean"] == r["queue_mean"] else ""])
    return table(pd.DataFrame(rows, columns=["Work center", "Machines", "Scheduled hours", "Machine hours", "Downtime hours", "Utilization", "Uptime", "Queue mean",
                                             f"Utilization, {REST}", f"Uptime, {REST}", f"Queue mean, {REST}"]))


def t_machine_basis():
    rows = []
    for mid in BRAKES + ["R1"]:
        y, r = MY.loc[mid], MR.loc[mid]
        rows.append([MACHINE.get(mid, mid), n0(y["scheduled"]), n0(y["overtime_scheduled"]), n0(y["machine"]), n0(y["down"]), d3(y["utilization"]),
                     d3(y["utilization_weekday_basis"]), d3(y["uptime"]), n0(y["operations"]), d3(r["utilization"]), d3(r["utilization_weekday_basis"])])
    return table(pd.DataFrame(rows, columns=["Machine", "Weekday scheduled hours", "Saturday and extended hours", "Machine hours", "Downtime hours",
                                             "Utilization", "Utilization, weekday basis", "Uptime", "Operations", f"Utilization, {REST}",
                                             f"Weekday basis, {REST}"]))


def t_fits():
    rows = []
    a, b = FITS.set_index("work_center"), FITS1.set_index("work_center")
    for w in a.sort_values("r2", ascending=False).index:
        r = a.loc[w]
        rows.append([WC[w], n0(r["machines"]), d3(r["k"]), d2(r["r2"]), d2(r["rank_correlation"]), rng(r["u_min"], r["u_max"]), d2(b.loc[w, "r2"]),
                     d2(r["queue_at_0.75"]), d2(r["queue_at_0.85"]), d2(r["queue_at_0.90"]), d2(r["queue_at_0.92"])])
    return table(pd.DataFrame(rows, columns=["Work center", "Machines (m)", "Scale k", "R-squared, 13-week", "Rank correlation", "Utilization range fitted",
                                             "R-squared, single weeks", "Queue at 0.75", "At 0.85", "At 0.90", "At 0.92"]))


def t_pos():
    rows = []
    for w in PY.sort_values("utilization", ascending=False).index:
        y, r = PY.loc[w], PR.loc[w]
        rows.append([WC[w], d3(y["utilization"]), d2(y["queue_measured"]), d2(y["queue_on_curve"]), f"{int(y['weeks_at_0_95'])} of {int(y['weeks'])}",
                     d3(r["utilization"]), d2(r["queue_measured"]), d2(r["queue_on_curve"]), f"{int(r['weeks_at_0_95'])} of {int(r['weeks'])}"])
    return table(pd.DataFrame(rows, columns=["Work center", "Utilization", "Queue measured", "Queue on curve", "Weeks at 0.95 or above",
                                             f"Utilization, {REST}", f"Queue measured, {REST}", f"Queue on curve, {REST}", f"Weeks at 0.95 or above, {REST}"]))


def t_laser():
    rows = [[pd.Timestamp(r.week_start).strftime("%Y-%m-%d"), n0(r.weekdays), d2(r.utilization), n0(r.operations), d2(r.queue_mean), d1(r.queue_p90)]
            for r in LAS_NOV.itertuples()]
    return table(pd.DataFrame(rows, columns=["Week starting", "Working weekdays", "Laser utilization", "First operations started", "First-operation queue, mean",
                                             "90th percentile"]))


def t_setup():
    rows = [[f"{YEAR}" if p == "year" else f"{YEAR} {REST}", d3(r["utilization"]), d2(r["queue_on_curve"]), d2(r["queue_with_half_setup_spread"]),
             d3(r["utilization_at_same_queue"]), d1(r["hours_per_week_released"])] for p, r in SV.iterrows()]
    t = table(pd.DataFrame(rows, columns=["Period", "Brake utilization", "Queue on the curve", "Queue with setup spread halved",
                                          "Utilization giving the same queue", "Brake hours a week released"]))
    inp = [["Setup time per operation, coefficient of variation", d2(PAR["setup_cv"])],
           ["Setup and run per operation, squared coefficient of variation", d2(PAR["setup_run_cv2"])],
           ["The same with setup spread halved", d2(PAR["setup_run_cv2_half"])],
           ["Daily arrivals at the brakes, variance over mean", d2(PAR["arrival_dispersion"])],
           ["Curve scale k", d3(PAR["curve_scale"])], ["Curve scale with setup spread halved", d3(PAR["curve_scale_half"])],
           ["Setup share of brake hours", pct(PAR["setup_share_of_brake_hours"])],
           ["Scheduled brake hours a week net of downtime", n0(PAR["net_hours_per_week"])]]
    return t + table(pd.DataFrame(inp, columns=["Input", "Value"]))


# ── report ──────────────────────────────────────────────────────────────────
HEADER_META = (f"Custom sheet-metal fabrication job shop, about 120 employees, one plant. Operations started in {YEAR}, whole year and {REST}; "
               f"records from January 2023 to December 2025.<br>"
               f"Sources: ERP, shop-floor data collection, maintenance and attendance exports (batch {D['batch']}). "
               f"Queue in working days per operation, scheduled Saturdays counted.")


def report():
    others = UY.drop(["press_brake", "robotic_weld", "laser", "powder_coat"])
    tail = MY.loc[["B3", "B4", "B5"]]
    lo, hi = BINS.iloc[:2], BINS.iloc[2:]
    below = float((lo["queue_mean"] * lo["weeks"]).sum() / lo["weeks"].sum())
    step = float(BINS.iloc[2]["queue_mean"])
    two_day = COLORS[COLORS["days_per_week"] > 1.5]["color"].tolist()
    nov3 = LAS_NOV[(LAS_NOV["week_start"] >= "2024-11-11") & (LAS_NOV["week_start"] <= "2024-11-25")]
    top_y = MY.loc[BRAKES, "utilization"].sort_values(ascending=False).index.tolist()
    b = []
    b.append("<h2 id='f1'>1. Load against uptime</h2>")
    b.append(f"<p>The brakes run at {d2(UY.loc['press_brake', 'utilization'])} of scheduled hours net of downtime, the robotic weld cell at "
             f"{d2(UY.loc['robotic_weld', 'utilization'])}, the lasers at {d2(UY.loc['laser', 'utilization'])}, assembly through hardware at "
             f"{rng(others['utilization'].min(), others['utilization'].max())} and the powder line at {d2(UY.loc['powder_coat', 'utilization'])}. "
             f"Machine uptime is {rng(UY['uptime'].min(), UY['uptime'].max())} at every work center and does not distinguish the constraint.</p>")
    b.append(fig_util())
    b.append(f"<div class='caption'>Figure 1. Utilization and machine uptime by work center, {YEAR}.</div>")

    b.append("<h2 id='f2'>2. The constraint, machine by machine</h2>")
    b.append(f"<p>B1 and B2 run at {d3(MY.loc['B1', 'utilization'])} and {d3(MY.loc['B2', 'utilization'])} for the year and "
             f"{d3(MR.loc['B1', 'utilization'])} and {d3(MR.loc['B2', 'utilization'])} in {REST}, with the shortest queues of the five "
             f"(mean {d1(MY.loc['B1', 'queue_mean'])} and {d1(MY.loc['B2', 'queue_mean'])} days): precision work goes to them first and the hot list sends "
             f"expedited work to them. B3 to B5 carry the tail: mean {rng(tail['queue_mean'].min(), tail['queue_mean'].max(), d1)} days and 90th percentile "
             f"{rng(tail['queue_p90'].min(), tail['queue_p90'].max(), d1)}. "
             + (f"Over all hours worked, {top_y[0]} carries the highest load of the five for the year; in {REST} B1 and B2 do." if top_y[0] not in ("B1", "B2") else "")
             + "</p>")
    b.append(t_machines())
    b.append(f"<div class='caption'>Table 1. Utilization and queue per operation for the five brakes and the robotic weld cell, {YEAR} and {REST}.</div>")

    b.append("<h2 id='f3'>3. Queue against load</h2>")
    b.append(f"<p>On the fitted curve the brake queue is {d2(FB['queue_at_0.75'])} days per operation at 0.75 utilization, {d2(FB['queue_at_0.85'])} at 0.85, "
             f"{d2(FB['queue_at_0.90'])} at 0.90 and {d2(FB['queue_at_0.92'])} at 0.92; the measured queue is {d2(PY.loc['press_brake', 'queue_measured'])} at "
             f"{d3(PY.loc['press_brake', 'utilization'])} for the year and {d2(PR.loc['press_brake', 'queue_measured'])} at "
             f"{d3(PR.loc['press_brake', 'utilization'])} in {REST}. Week by week, the brake queue steps from about {d1(below)} days below 0.85 utilization "
             f"to {d1(step)} above it and does not settle back.</p>")
    b.append(fig_curve())
    b.append("<div class='caption'>Figure 2. Weekly brake queue against weekly utilization, 2023 to 2025, with the curve fitted on 13-week windows and its "
             "values at 0.75, 0.85, 0.90 and 0.92.</div>")
    b.append(t_bins())
    b.append("<div class='caption'>Table 2. Weekly brake queue by utilization band, full weeks 2023 to 2025.</div>")
    b.append("<p>The curve does not describe hardware, grind and deburr, inspection and pack, or the powder line: their queues follow the daily dispatch list and "
             "the color schedule, not load.</p>")

    b.append("<h2 id='f4'>4. The secondary constraint</h2>")
    b.append(f"<p>In {REST} the robotic weld cell has the longest queue in the shop: {d1(ROB.loc[REST, 'queue_mean'])} days per operation against "
             f"{d1(UR.loc['press_brake', 'queue_mean'])} at the brakes, on one shift at {d2(ROB.loc[REST, 'utilization'])} utilization. It ran at or above 0.95 in "
             f"{int(ROB.loc[REST, 'weeks_at_0_95'])} of {int(ROB.loc[REST, 'weeks'])} weeks, and enclosures are {pct(ROB.loc[REST, 'enclosure_share_of_hours'], 0)} "
             f"of its hours.</p>")
    b.append(fig_robot())
    b.append(f"<div class='caption'>Figure 3. Robotic weld cell weekly utilization and queue per operation, {YEAR}; the dashed line is 0.95.</div>")

    b.append("<h2 id='f5'>5. The scheduling constraint</h2>")
    b.append(f"<p>The powder line runs at {d2(POW.loc['year', 'utilization'])} and still holds jobs {d2(POW.loc['year', 'color_day_wait_mean'])} days on average "
             f"for the color day; {pct(POW.loc['year', 'share_waiting_a_day_or_more'], 0)} of operations wait a day or more "
             f"({d2(POW.loc[REST, 'color_day_wait_mean'])} days and {pct(POW.loc[REST, 'share_waiting_a_day_or_more'], 0)} in {REST}).</p>")

    b.append("<h2 id='f6'>6. Variability</h2>")
    b.append(f"<p>Halving the spread of brake setup time releases {d1(SV.loc['year', 'hours_per_week_released'])} brake hours a week and cuts the queue on the curve "
             f"from {d2(SV.loc['year', 'queue_on_curve'])} to {d2(SV.loc['year', 'queue_with_half_setup_spread'])} days. The variability at the brakes is in arrivals "
             f"(daily coefficient of variation {d2(var('Arrivals: jobs released per working day'))}, Mondays {d2(var('Arrivals: Monday'))} times the daily mean, "
             f"the top customer's month-end {d2(var('Arrivals: top customer'))} times) and in run time (coefficient of variation "
             f"{d2(var('Brake run time'))} against {d2(var('Brake setup time'))} for setup). This is the spread of setup time, not its mean; the mean is the subject of P4. "
             f"Second-shift absence is {pct(var('Absence, second shift: share'), 0)} against {pct(var('Absence, first shift: share'), 0)} on first shift.</p>")
    b.append(t_var())
    b.append(f"<div class='caption'>Table 3. Variability sources, {YEAR}.</div>")

    b.append("<h2 id='f7'>7. The lasers at the peak</h2>")
    b.append(f"<p>The lasers ran at {d2(UY.loc['laser', 'utilization'])} for the year and at {rng(nov3['utilization'].min(), nov3['utilization'].max())} for three weeks "
             f"in November 2024, with the first-operation queue rising from {d1(LAS_NOV.iloc[0]['queue_mean'])} to {d1(LAS_NOV.iloc[-1]['queue_mean'])} days by "
             f"mid-December. They reached 0.95 in {LW_N} of {LW_ALL} full weeks in three years.</p>")

    b.append("<h2 id='rec'>Recommendation</h2>")
    b.append(f"<p>The brake queue is set by arrival variability and by load above 0.85, so capacity at the constraint (the P4 setup reduction, P5) is the first lever; release leveling and dispatch rules do not help (P5), and reducing the "
             f"spread of setup time is not one. A second shift on the robotic weld cell is an unstaffed shift on the shop's secondary constraint; P5 tests it and P8 prices it. The color "
             f"schedule is a scheduling choice to revisit: {', '.join(two_day[:-1])} and {two_day[-1]} already run two days a week, and a third day for black is a P5 "
             f"scenario. Mean setup time at the brakes is P4.</p>")

    b.append("<h2 id='method'>Method and data</h2>")
    b.append(f"<p>Coverage: {n0(len(D['ops']))} operations started in {YEAR}, {n0((D['ops']['start_quarter'] >= 2).sum())} in {REST}; curves fitted on 2023 to 2025. "
             f"Utilization is machine time (the union of labor transaction intervals on a machine) over scheduled hours net of downtime, Saturday and extended shifts "
             f"included; uptime is one less downtime over scheduled hours. On crewed weekday shifts only, B1 and B2 read {d3(MY.loc['B1', 'utilization_weekday_basis'])} "
             f"and {d3(MY.loc['B2', 'utilization_weekday_basis'])} for the year.<br>"
             f"Queue is the previous operation's end to this operation's first start, operations after the first, less the powder color-day wait; for the lasers it is "
             f"traveler print to first cut less material wait.<br>"
             f"Curve: queue = k x u^(sqrt(2(m+1)) - 1) / (m(1 - u)), m the number of machines, k fitted by least squares on rolling 13-week windows with utilization "
             f"between 0.3 and 0.98; the windows include the year-end builds. For the brakes R-squared is {d2(FB['r2'])} and the rank correlation "
             f"{d2(FB['rank_correlation'])} on 13-week windows, against an R-squared of {d2(FB1['r2'])} on single weeks: a week's queue carries the backlog of the weeks "
             f"before it. Bands in Table 2 are full five-day weeks by that week's utilization.<br>"
             f"Setup spread: each setup time is moved halfway to the mean setup time; the curve scale is multiplied by (arrival dispersion + new squared coefficient of "
             f"variation of setup and run) over (arrival dispersion + current), where arrival dispersion is the variance over the mean of daily arrivals at the brakes; "
             f"hours released are the utilization giving the same queue on the new curve, less current utilization, times scheduled hours net of downtime.</p>")

    b.append("<h2 id='appendix'>Appendix</h2>")
    b.append("<h3>Table 4. Utilization and machine uptime by work center</h3>" + t_util())
    b.append("<h3>Table 5. The brakes and the robotic weld cell: hours and utilization on both bases</h3>" + t_machine_basis())
    b.append("<h3>Table 6. Fitted queue curve by work center</h3>" + t_fits())
    b.append("<h3>Table 7. Position of each work center on its curve</h3>" + t_pos())
    b.append("<h3>Table 8. Laser weeks, November and December 2024</h3>" + t_laser())
    b.append("<h3>Table 9. Brake queue with the spread of setup time halved, and the inputs</h3>" + t_setup())
    b.append("<div class='glossary'>Utilization: machine time over scheduled hours net of downtime. Uptime: scheduled hours not lost to downtime. "
             "Color-day wait: the wait at the powder line for the next scheduled day of the job's color.</div>")
    toc = [("f1", "Load against uptime"), ("f2", "The brakes"), ("f3", "Queue against load"), ("f4", "Robotic weld"), ("f5", "Powder line"),
           ("f6", "Variability"), ("f7", "Lasers"), ("rec", "Recommendation"), ("method", "Method and data"), ("appendix", "Appendix")]
    (DOCS / "reports").mkdir(parents=True, exist_ok=True)
    (DOCS / "reports" / "p3_constraint.html").write_text(report_shell("The constraint, utilization and variability", "Project 3 report", HEADER_META, "\n".join(b), toc),
                                                         encoding="utf8")


COUNTERMEASURES = [
    ("Take the P4 setup reduction and planned Saturday brake shifts as the capacity levers (P5); release leveling and dispatch rules were tested on the shop "
     "model and do not help", "Plant manager", "April 2026"),
    ("Trial a second shift on the robotic weld cell (P5, P8)", "Production manager", "April 2026"),
    ("Review the powder color schedule; a third day for black if the weld shift is not enough (P5)", "Powder line lead", "March 2026"),
    ("Reduce mean setup time at the brakes (P4)", "Brake supervisor", "March 2026"),
]


def a3():
    by = UY.loc["press_brake"]
    worst_q = int(BQ["queue_p90"].idxmax())
    left, right = [], []
    left.append(f"<section><h2>Background and problem</h2><p>The brakes run at {d2(by['utilization'])} of scheduled hours with a queue of {d1(by['queue_mean'])} days "
                f"per operation and a 90th percentile of {d1(by['queue_p90'])} days ({d1(UR.loc['press_brake', 'queue_mean'])} and "
                f"{d1(UR.loc['press_brake', 'queue_p90'])} in {REST}).<br>Machine uptime is {rng(UY['uptime'].min(), UY['uptime'].max())} at every work center and "
                f"does not show where the load is.</p></section>")
    left.append(f"<section><h2>Current condition</h2>{fig_curve('p3_a3_brake_queue_curve', 4.2)}"
                f"<div class='caption'>Weekly brake queue against weekly utilization, 2023 to 2025, with the curve fitted on 13-week windows.</div></section>")
    met = [k for k in sorted(BQ.index) if BQ.loc[k, "queue_p90"] < 5]
    missed = [k for k in sorted(BQ.index) if BQ.loc[k, "queue_p90"] >= 5]
    lab = lambda ks: " and ".join(f"Q{k}" for k in ks)
    val = lambda ks: " and ".join(d1(BQ.loc[k, "queue_p90"]) for k in ks)
    left.append(f"<section><h2>Target</h2><p>Brake queue 90th percentile under 5 days in every quarter, the first included. Met in {lab(met)} {YEAR} "
                f"({val(met)} days), not in {lab(missed)} ({val(missed)}).</p></section>")
    right.append(
        f"<section><h2>Analysis</h2>{fig_robot('p3_a3_robotic_weld_weekly', 2.9)}<div class='caption'>Robotic weld cell weekly utilization and queue per operation, {YEAR}.</div><ul>"
        f"<li>B1 and B2 carry precision and expedited work with the shortest queues; B3 to B5 carry the tail (90th percentile "
        f"{rng(MY.loc[['B3', 'B4', 'B5'], 'queue_p90'].min(), MY.loc[['B3', 'B4', 'B5'], 'queue_p90'].max(), d1)} days).</li>"
        f"<li>On the fitted curve the brake queue is {d2(FB['queue_at_0.85'])} days at 0.85 utilization, {d2(FB['queue_at_0.90'])} at 0.90 and "
        f"{d2(FB['queue_at_0.92'])} at 0.92.</li>"
        f"<li>In {REST} the robotic weld cell has the longest queue: {d1(ROB.loc[REST, 'queue_mean'])} days on one shift at {d2(ROB.loc[REST, 'utilization'])}, "
        f"at or above 0.95 in {int(ROB.loc[REST, 'weeks_at_0_95'])} of {int(ROB.loc[REST, 'weeks'])} weeks.</li>"
        f"<li>The powder line runs at {d2(POW.loc['year', 'utilization'])} and holds jobs {d2(POW.loc['year', 'color_day_wait_mean'])} days for the color day.</li>"
        f"<li>Halving the spread of brake setup time releases {d1(SV.loc['year', 'hours_per_week_released'])} hours a week; the variability is in arrivals and "
        f"run time.</li></ul></section>")
    right.append(f"<section><h2>Countermeasures</h2>{table(pd.DataFrame(COUNTERMEASURES, columns=['Action', 'Owner', 'When']))}</section>")
    right.append(f"<section><h2>Results</h2><p>Measured baseline for {YEAR}: brake utilization {d2(by['utilization'])}, queue {d1(by['queue_mean'])} days per operation, "
                 f"90th percentile {d1(by['queue_p90'])}; robotic weld queue {d1(ROB.loc['year', 'queue_mean'])} days at {d2(ROB.loc['year', 'utilization'])}. "
                 f"Results of the countermeasures are reported in P4 and P5.</p></section>")
    right.append("<section><h2>Follow-up</h2><p>Weekly utilization and queue by work center on the operations dashboard.</p></section>")
    (DOCS / "a3").mkdir(parents=True, exist_ok=True)
    (DOCS / "a3" / "p3_constraint.html").write_text(a3_shell("The constraint, utilization and variability", "Project 3 A3", HEADER_META, "\n".join(left),
                                                             "\n".join(right)), encoding="utf8")


def main():
    report()
    a3()
    print("wrote docs/reports/p3_constraint.html and docs/a3/p3_constraint.html")


if __name__ == "__main__":
    main()
