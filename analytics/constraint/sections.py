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


def fig_curve(name="constraint_brake_queue_curve", h=3.9):
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


def fig_robot(name="constraint_robotic_weld_weekly", h=3.3):
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
