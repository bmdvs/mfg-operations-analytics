"""The constraint, utilization and variability: the data, tables and figures of its part of the report.

Built by analytics.reports.capacity_constraints_and_setups.
"""
import numpy as np
import pandas as pd

from analytics.db import q
from analytics.constraint import analysis as A
from analytics.style.style import ACCENT, AMBER, BRAND_BLUE, DOCS, GREY, LIGHT_BLUE, RED, fig, pct, save_conformed as save, sig, table

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
    f, ax = fig(h=3.6)
    x = np.arange(len(d))
    for dx, col, color, lab in ((-0.2, "utilization", BRAND_BLUE, "Utilization"), (0.2, "uptime", LIGHT_BLUE, "Machine uptime")):
        v = sig(d[col].to_numpy(dtype=float) * 100)
        ax.bar(x + dx, v, width=0.38, color=color, label=lab)
        for xi, vi in zip(x, v):
            ax.text(xi + dx, vi, f"{vi:.0f}%", ha="center", va="bottom", fontsize=7)
    ax.set_xticks(x)
    ax.set_xticklabels([WC[w] for w in d.index], rotation=20, ha="right")
    ax.set_ylim(0, 108)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.legend(frameon=False, ncol=2, loc="upper right")
    f.tight_layout()
    return save(f, "constraint_utilization_uptime", "Utilization and machine uptime by work center")


# ── tables ──────────────────────────────────────────────────────────────────
def p0(x):
    return f"{x * 100:.0f}%"


def p1(x):
    return f"{x * 100:.1f}%"


def t_machines():
    rows = []
    for mid in BRAKES + ["R1"]:
        y, r = MY.loc[mid], MR.loc[mid]
        rows.append([MACHINE.get(mid, mid), n0(y["crewed_shifts"]), p1(y["utilization"]), d2(y["queue_mean"]), d2(y["queue_median"]), d1(y["queue_p90"]),
                     p1(r["utilization"]), d2(r["queue_mean"]), d2(r["queue_median"]), d1(r["queue_p90"])])
    return table(pd.DataFrame(rows, columns=["Machine", "Crewed shifts", f"Utilization, {YEAR}", "Queue time, mean", "Median", "90th percentile",
                                             f"Utilization, {REST}", f"Queue time, mean, {REST}", f"Median, {REST}", f"90th percentile, {REST}"]))


def t_bins():
    rows = [[r.band, n0(r.weeks), d2(r.queue_mean), d2(r.queue_median)] for r in BINS.itertuples()]
    return table(pd.DataFrame(rows, columns=["Brake utilization in the week", "Weeks", "Queue time, mean of weeks", "Median"]))


def t_var():
    rows = [[r.source, r.measure, d2(r.value)] for r in VAR.itertuples()]
    return table(pd.DataFrame(rows, columns=["Source", "Measure", f"Value, {YEAR}"]))


def t_util():
    started = D["ops"].groupby("work_center").size()
    rows = []
    for w in UY.sort_values("utilization", ascending=False).index:
        y, r = UY.loc[w], UR.loc[w]
        rows.append([WC[w], n0(y["machines"]), n0(started[w]), n0(y["scheduled"]), n0(y["machine"]), n0(y["down"]), n0(y["scheduled"] - y["down"]),
                     p0(y["utilization"]), p0(y["uptime"]), d2(y["queue_mean"]) if y["queue_mean"] == y["queue_mean"] else "", p0(r["utilization"]), p0(r["uptime"]),
                     d2(r["queue_mean"]) if r["queue_mean"] == r["queue_mean"] else ""])
    return table(pd.DataFrame(rows, columns=["Work center", "Machines", "Operations", "Scheduled hours", "Machine hours", "Downtime hours", "Available hours",
                                             "Utilization", "Uptime", "Queue time, mean", f"Utilization, {REST}", f"Uptime, {REST}", f"Queue time, mean, {REST}"]))


def t_machine_basis():
    rows = []
    for mid in BRAKES + ["R1"]:
        y, r = MY.loc[mid], MR.loc[mid]
        rows.append([MACHINE.get(mid, mid), n0(y["scheduled"]), n0(y["overtime_scheduled"]), n0(y["machine"]), n0(y["down"]), p1(y["utilization"]),
                     p1(y["utilization_weekday_basis"]), p0(y["uptime"]), n0(y["operations"]), p1(r["utilization"]), p1(r["utilization_weekday_basis"])])
    return table(pd.DataFrame(rows, columns=["Machine", "Weekday scheduled hours", "Saturday and extended hours", "Machine hours", "Downtime hours",
                                             "Utilization", "Utilization, weekday basis", "Uptime", "Operations", f"Utilization, {REST}",
                                             f"Weekday basis, {REST}"]))


def t_fits():
    rows = []
    a, b = FITS.set_index("work_center"), FITS1.set_index("work_center")
    for w in a.sort_values("r2", ascending=False).index:
        r = a.loc[w]
        rows.append([WC[w], n0(r["machines"]), d3(r["k"]), d2(r["r2"]), d2(r["rank_correlation"]), f"{p0(r['u_min'])} to {p0(r['u_max'])}", d2(b.loc[w, "r2"]),
                     d2(r["queue_at_0.75"]), d2(r["queue_at_0.85"]), d2(r["queue_at_0.90"]), d2(r["queue_at_0.92"])])
    return table(pd.DataFrame(rows, columns=["Work center", "Machines (m)", "Scale k", "R-squared, 13-week", "Rank correlation", "Utilization range fitted",
                                             "R-squared, single weeks", "Queue time at 75%", "At 85%", "At 90%", "At 92%"]))


def t_pos():
    rows = []
    for w in PY.sort_values("utilization", ascending=False).index:
        y, r = PY.loc[w], PR.loc[w]
        rows.append([WC[w], p0(y["utilization"]), d2(y["queue_measured"]), d2(y["queue_on_curve"]), f"{int(y['weeks_at_0_95'])} of {int(y['weeks'])}",
                     p0(r["utilization"]), d2(r["queue_measured"]), d2(r["queue_on_curve"]), f"{int(r['weeks_at_0_95'])} of {int(r['weeks'])}"])
    return table(pd.DataFrame(rows, columns=["Work center", "Utilization", "Queue time measured", "Queue time on curve", "Weeks at or above 95%",
                                             f"Utilization, {REST}", f"Queue time measured, {REST}", f"Queue time on curve, {REST}", f"Weeks at or above 95%, {REST}"]))


def t_laser():
    rows = [[pd.Timestamp(r.week_start).strftime("%Y-%m-%d"), n0(r.weekdays), p0(r.utilization), n0(r.operations), d2(r.queue_mean), d1(r.queue_p90)]
            for r in LAS_NOV.itertuples()]
    return table(pd.DataFrame(rows, columns=["Week starting", "Working weekdays", "Laser utilization", "First operations started", "First-operation queue time, mean",
                                             "90th percentile"]))


def t_setup():
    rows = [[f"{YEAR}" if p == "year" else f"{YEAR} {REST}", p1(r["utilization"]), d2(r["queue_on_curve"]), d2(r["queue_with_half_setup_spread"]),
             p1(r["utilization_at_same_queue"]), d1(r["hours_per_week_released"])] for p, r in SV.iterrows()]
    t = table(pd.DataFrame(rows, columns=["Period", "Brake utilization", "Queue time on the curve", "Queue time with setup spread halved",
                                          "Utilization giving the same queue time", "Brake hours a week released"]))
    inp = [["Setup time per operation, coefficient of variation", d2(PAR["setup_cv"])],
           ["Setup and run per operation, squared coefficient of variation", d2(PAR["setup_run_cv2"])],
           ["The same with setup spread halved", d2(PAR["setup_run_cv2_half"])],
           ["Daily arrivals at the brakes, variance over mean", d2(PAR["arrival_dispersion"])],
           ["Curve scale k", d3(PAR["curve_scale"])], ["Curve scale with setup spread halved", d3(PAR["curve_scale_half"])],
           ["Setup share of brake hours", pct(PAR["setup_share_of_brake_hours"])],
           ["Scheduled brake hours a week net of downtime", n0(PAR["net_hours_per_week"])]]
    return t + table(pd.DataFrame(inp, columns=["Input", "Value"]))
