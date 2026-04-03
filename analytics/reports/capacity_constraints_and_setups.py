"""Capacity, constraints and setups: the report.

Usage: python -m analytics.reports.capacity_constraints_and_setups
"""
import numpy as np
import pandas as pd
from matplotlib.ticker import MaxNLocator

from analytics.constraint import analysis as CA
from analytics.constraint import screen as SC
from analytics.constraint import sections as C
from analytics.db import q
from analytics.reports.layout import Tables, block, chart, join_and, link, page, titled
from analytics.setups import analysis as SA
from analytics.setups import sections as S
from analytics.style.style import ACCENT, AMBER, BRAND_BLUE, GREY, LIGHT_BLUE, fig, paired_columns, pct, save_conformed as save, sig, table

YEAR, REST, RT = SC.YEAR, "Q2 to Q4", "Q2-Q4"
WC = C.WC
NAME = {"press_brake": "the brakes", "robotic_weld": "the robotic weld cell", "assembly": "assembly", "punch": "the punch", "laser": "the lasers",
        "weld": "the manual weld bays", "grind_deburr": "grind and deburr", "inspection_pack": "inspection and pack", "hardware": "hardware",
        "powder_coat": "the powder line"}
NUMBER = {3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight"}
TIMES = {3: "three", 4: "four", 5: "five", 6: "six"}
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
d1, d2, d3, n0, rng = C.d1, C.d2, C.d3, C.n0, C.rng

X = SC.load()
HOT = SC.hot_weeks(X).set_index(["period", "work_center"])
HY, HR = HOT.loc["year"], HOT.loc[REST]
BY_START, HOURS, BRAKE_HOURS = SC.dispatch(X)
START_Y, START_R = BY_START[BY_START["period"] == "year"].set_index("work_center"), BY_START[BY_START["period"] == REST].set_index("work_center")
NEXT_DAY = SC.next_day_wait(X)
POWDER, POWDER_ALL = SC.powder(X)
ROBOT_BANDS, ROBOT_FAMILIES, ROBOT_STD = SC.bands(X, "robotic_weld"), SC.families(X, "robotic_weld"), SC.against_standard(X, "robotic_weld")
ASM = SC.assembly(X)
LAS = SC.lasers(X)
QSHARE = q("select work_center, share_of_queue from marts.mart_queue_by_work_center where period = 'year'").set_index("work_center")["share_of_queue"]


# ── figures ─────────────────────────────────────────────────────────────────
HOT_ORDER = ["press_brake", "robotic_weld", "assembly", "punch", "laser", "weld", "grind_deburr"]          # by hot weeks in the year
HOT_SIX = HOT_ORDER[:6]                                                                                 # those with a hot week in the ordinary quarters
ROUTING = ["laser", "punch", "press_brake", "hardware", "weld", "robotic_weld", "grind_deburr", "powder_coat", "assembly", "inspection_pack"]
DOWN_ORDER = ["breakdown", "PM", "no operator", "waiting for program"]
DOWN_LABEL = {"breakdown": "Unplanned Breakdowns", "PM": "Planned Maintenance", "no operator": "No Operator", "waiting for program": "Waiting for Program"}
DOWN = X["downtime"].pivot(index="work_center", columns="cause", values="hours").fillna(0.0)[DOWN_ORDER]
ACTIVITY = pd.DataFrame({"operations": X["ops"].groupby("work_center").size(), "hours": C.UY["machine"], "machines": C.UY["machines"]})
ACTIVITY["ops_per_week"] = ACTIVITY["operations"] / SA.WEEKS
ACTIVITY["ops_per_machine_week"] = ACTIVITY["ops_per_week"] / ACTIVITY["machines"]
ACTIVITY["hours_per_operation"] = ACTIVITY["hours"] / ACTIVITY["operations"]
QUEUE_AXIS = "Queue time, working days per operation"
P = lambda x: pct(x, 0)


def note(text):
    return f"<div class='caption'>{text}</div>"


def fig_activity():
    """Operations per machine a week (left axis) and machine hours per operation (right axis), work centers in routing order."""
    d = ACTIVITY.loc[ROUTING]
    x = np.arange(len(d))
    f, ax = fig(h=4.0)
    ax2 = ax.twinx()
    ops, hrs = sig(d["ops_per_machine_week"].to_numpy(dtype=float)), sig(d["hours_per_operation"].to_numpy(dtype=float))
    ax.bar(x - 0.2, ops, width=0.38, color=LIGHT_BLUE, label="Operations per machine a week (left)")
    ax2.bar(x + 0.2, hrs, width=0.38, color=BRAND_BLUE, label="Machine hours per operation (right)")
    for xi, vi in zip(x, ops):
        ax.text(xi - 0.2, vi, f"{vi:.0f}", ha="center", va="bottom", fontsize=8)
    for xi, vi in zip(x, hrs):
        ax2.text(xi + 0.2, vi, f"{vi:.2f}" if vi < 1 else f"{vi:.1f}", ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{WC[w]} ({int(d.loc[w, 'machines'])}{' machines' if w == 'laser' else ''})" for w in d.index], rotation=25, ha="right")
    ax.set_ylabel("Operations per machine a week")
    ax2.set_ylabel("Machine hours per operation")
    ax.set_ylim(0, float(ops.max()) * 1.12)
    ax2.set_ylim(0, float(hrs.max()) * 1.12)
    ax2.grid(False)
    ax2.spines["top"].set_visible(False)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    f.legend(h1 + h2, l1 + l2, frameon=False, fontsize=9, ncol=2, loc="lower center")
    f.tight_layout(rect=(0, 0.06, 1, 1))
    return save(f, "capacity_floor_activity", f"Floor Activity by Work Center, {YEAR}")


def fig_downtime():
    """Downtime hours by work center, each column split by source with the source's share of the column inside it."""
    d = DOWN.loc[DOWN.sum(axis=1).sort_values(ascending=False).index]
    x = np.arange(len(d))
    colors = dict(zip(DOWN_ORDER, (BRAND_BLUE, ACCENT, LIGHT_BLUE, AMBER)))
    f, ax = fig(h=4.2)
    bottom = np.zeros(len(d))
    total = d.sum(axis=1).to_numpy(dtype=float)
    for k in DOWN_ORDER:
        v = sig(d[k].to_numpy(dtype=float))
        ax.bar(x, v, width=0.66, bottom=bottom, color=colors[k], label=DOWN_LABEL[k])
        for xi, vi, bi, ti in zip(x, v, bottom, total):
            if vi >= total.max() * 0.045:
                ax.text(xi, bi + vi / 2, f"{vi / ti * 100:.0f}%", ha="center", va="center", fontsize=7.5, color="white" if k in ("breakdown", "PM") else "#222222")
        bottom += v
    for xi, ti in zip(x, total):
        ax.text(xi, ti, f"{ti:,.0f}", ha="center", va="bottom", fontsize=8.5)
    ax.set_xticks(x)
    ax.set_xticklabels([WC[w] for w in d.index], rotation=20, ha="right")
    ax.set_ylabel("Downtime Hours")
    ax.set_ylim(0, float(total.max()) * 1.08)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    f.legend(*ax.get_legend_handles_labels(), frameon=False, fontsize=9, ncol=4, loc="lower center")
    f.tight_layout(rect=(0, 0.06, 1, 1))
    return save(f, "capacity_downtime_by_driver", f"Machine Downtime Hours and Sources by Work Center, {YEAR}")


def fig_hot_share():
    d = (HY["hot_weeks"] / HY["weeks"]).sort_values(ascending=False)
    x = np.arange(len(d))
    v = sig(d.to_numpy(dtype=float) * 100)
    f, ax = fig(h=3.5)
    ax.bar(x, v, width=0.62, color=BRAND_BLUE)
    for xi, vi in zip(x, v):
        ax.text(xi, vi, f"{vi:.0f}%", ha="center", va="bottom", fontsize=8.5)
    ax.set_xticks(x)
    ax.set_xticklabels([WC[w] for w in d.index], rotation=20, ha="right")
    ax.set_ylabel("Share of weeks at or above 95% utilization")
    ax.set_ylim(0, float(v.max()) * 1.12)
    ax.yaxis.set_major_formatter(lambda t, _: f"{t:.0f}%")
    f.tight_layout()
    return save(f, "capacity_hot_week_share", f"Share of hot weeks by work station, {YEAR}")


def fig_hot():
    """Queue time and jobs at the work center in hot weeks against the other weeks of the ordinary quarters."""
    d = HR.loc[HOT_SIX]
    f, axes = fig(h=3.9, ncols=2)
    names = ("Weeks at or above 95%", "Other weeks")
    paired_columns(axes[0], [WC[w] for w in d.index], list(d["queue_hot"]), list(d["queue_other"]), names, decimals=2)
    axes[0].set_ylabel(QUEUE_AXIS)
    paired_columns(axes[1], [WC[w] for w in d.index], list(d["wip_hot"]), list(d["wip_other"]), names, decimals=0)
    axes[1].set_ylabel("Jobs at the work center, daily mean")
    f.legend(*axes[0].get_legend_handles_labels(), frameon=False, fontsize=9, ncol=2, loc="lower center")
    f.tight_layout(rect=(0, 0.06, 1, 1))
    return save(f, "capacity_queue_in_hot_weeks", "Queue Time and Jobs at the Work Center in Hot Weeks and Other Weeks, Q2-Q4 2025")


PANEL_COUNTS = {}


def fig_panels(centers, name, title, curve, ymax):
    """Weekly queue time against weekly utilization for four work centers on shared axes, with the fitted curve or the year's mean queue time."""
    fits = C.FITS.set_index("work_center")
    f, axes = fig(h=5.6, nrows=2, ncols=2, sharex=True, sharey=True)
    above = below = 0
    for ax, wc in zip(axes.ravel(), centers):
        w = X["uw"][(X["uw"]["work_center"] == wc) & (X["uw"]["weekdays"] == 5) & X["uw"]["queue_mean"].notna()]
        above += int((w["queue_mean"] > ymax).sum())
        below += int((w["utilization"] < 0.4).sum())
        ax.scatter(sig(w["utilization"] * 100), sig(w["queue_mean"].clip(upper=ymax)), s=11, color=ACCENT, alpha=0.45, linewidths=0)
        m = int(fits.loc[wc, "machines"])
        if curve:
            k, lo, hi = float(fits.loc[wc, "k"]), float(fits.loc[wc, "u_min"]), float(fits.loc[wc, "u_max"])
            u = np.linspace(lo, hi, 120)
            ax.plot(u * 100, sig(k * CA.vut_factor(u, m)), color=BRAND_BLUE, linewidth=2.0)
            u = np.linspace(hi, 0.98, 60)
            ax.plot(u * 100, sig(k * CA.vut_factor(u, m)), color=BRAND_BLUE, linewidth=1.6, linestyle="--")
        else:
            mean = float(sig(C.PY.loc[wc, "queue_measured"]))
            ax.axhline(mean, color=BRAND_BLUE, linewidth=1.6)
            ax.text(41, mean + ymax * 0.02, f"{mean:.2f}", ha="left", va="bottom", fontsize=8.5, color=BRAND_BLUE)
        ax.set_title(f"{WC[wc]} ({m} machine{'s' if m > 1 else ''})", fontsize=10.5)
        ax.set_xlim(40, 100)
        ax.set_ylim(0, ymax)
        ax.xaxis.set_major_formatter(lambda t, _: f"{t:.0f}%")
    for ax in axes[1]:
        ax.set_xlabel("Utilization")
    f.supylabel(QUEUE_AXIS, fontsize=11)
    f.tight_layout()
    PANEL_COUNTS[name] = (above, below)
    return save(f, name, title)


def fig_same_day():
    """Arrivals by hour at the dispatch-list work centers, and the share starting the same working day there and at the brakes."""
    x = np.arange(len(HOURS))
    f, ax = fig(h=3.9)
    share = sig(HOURS["share"].to_numpy(dtype=float) * 100)
    ax.bar(x, share, width=0.62, color=LIGHT_BLUE, label="Share of arrivals (left)")
    for xi, vi in zip(x, share):
        ax.text(xi, vi, f"{vi:.0f}%", ha="center", va="bottom", fontsize=8)
    ax.axvline(2.5, color="#CCCCCC", linewidth=1.0)
    ax.set_xticks(x)
    ax.set_xticklabels(list(HOURS.index), rotation=20, ha="right")
    ax.set_ylabel("Share of arrivals")
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(lambda t, _: f"{t:.0f}%")
    ax2 = ax.twinx()
    ax2.plot(x, sig(HOURS["same_day"].to_numpy(dtype=float) * 100), color=BRAND_BLUE, linewidth=2.0, marker="o", markersize=5,
             label="Dispatch-list work centers: same-day start (right)")
    ax2.plot(x, sig(BRAKE_HOURS["same_day"].to_numpy(dtype=float) * 100), color=AMBER, linewidth=2.0, marker="s", markersize=5, label="Press brake: same-day start (right)")
    ax2.set_ylabel("Start the same working day")
    ax2.set_ylim(0, 100)
    ax2.yaxis.set_major_formatter(lambda t, _: f"{t:.0f}%")
    ax2.grid(False)
    ax2.spines["top"].set_visible(False)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    f.legend(h1 + h2, l1 + l2, frameon=False, fontsize=8.5, ncol=3, loc="lower center")
    f.tight_layout(rect=(0, 0.06, 1, 1))
    return save(f, "capacity_same_day_start", f"Same-Day Start by Hour of Arrival, Dispatch-List Work Centers Against the Brakes, {YEAR}")


def fig_brakes():
    """Utilization and mean queue time for each brake and the robotic weld cell."""
    ids = C.BRAKES + ["R1"]
    d = C.MY.loc[ids]
    x = np.arange(len(d))
    f, ax = fig(h=3.7)
    u = sig(d["utilization"].to_numpy(dtype=float) * 100)
    ax.bar(x, u, width=0.56, color=LIGHT_BLUE, label="Utilization (left)")
    for xi, vi in zip(x, u):
        ax.text(xi, vi / 2, f"{vi:.0f}%", ha="center", va="center", fontsize=8.5)
    ax.set_xticks(x)
    ax.set_xticklabels([C.MACHINE.get(i, i) for i in ids])
    ax.set_ylabel("Utilization")
    ax.set_ylim(0, 105)
    ax.yaxis.set_major_formatter(lambda t, _: f"{t:.0f}%")
    ax2 = ax.twinx()
    qm = sig(d["queue_mean"].to_numpy(dtype=float))
    ax2.plot(x, qm, color=BRAND_BLUE, linestyle="none", marker="D", markersize=7, label="Queue time, mean (right)")
    for xi, vi in zip(x, qm):
        ax2.text(xi + 0.12, vi, f"{vi:.1f}", ha="left", va="center", fontsize=8.5, color=BRAND_BLUE)
    ax2.set_ylabel(QUEUE_AXIS)
    ax2.set_ylim(0, float(qm.max()) * 1.25)
    ax2.grid(False)
    ax2.spines["top"].set_visible(False)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    f.legend(h1 + h2, l1 + l2, frameon=False, fontsize=9, ncol=2, loc="lower center")
    f.tight_layout(rect=(0, 0.06, 1, 1))
    return save(f, "capacity_utilization_and_queue_by_brake", f"Utilization and Queue Time by Brake, {YEAR}")


def fig_laser_months():
    m = LAS["month"]
    x = np.arange(len(m))
    f, ax = fig(h=3.6)
    v = sig(m["queue"].to_numpy(dtype=float))
    ax.bar(x, v, width=0.62, color=LIGHT_BLUE, label="First-operation queue time, mean")
    for xi, vi in zip(x, v):
        ax.text(xi, vi, f"{vi:.2f}", ha="center", va="bottom", fontsize=8)
    ax.plot(x, sig(m["material_wait"].to_numpy(dtype=float)), color=BRAND_BLUE, linewidth=2.0, marker="o", markersize=5, label="Material wait, mean")
    ax.set_xticks(x)
    ax.set_xticklabels([MONTHS[k - 1][:3] for k in m.index])
    ax.set_ylabel("Working days per operation")
    ax.set_ylim(0, float(v.max()) * 1.12)
    f.legend(*ax.get_legend_handles_labels(), frameon=False, fontsize=9, ncol=2, loc="lower center")
    f.tight_layout(rect=(0, 0.06, 1, 1))
    return save(f, "capacity_laser_first_operation_by_month", f"First-Operation Queue Time and Material Wait by Month, {YEAR}")


def fig_assembly():
    w = X["uw"][(X["uw"]["work_center"] == "assembly") & (X["uw"]["week_start"] >= SC.SERIES_START)].sort_values("week_start")
    f, ax = fig(h=3.3)
    ax.bar(w["week_start"], w["utilization"], width=5, color=LIGHT_BLUE, label="Utilization (left)")
    ax.axhline(0.95, color=GREY, linewidth=1, linestyle="--")
    ax.set_ylabel("Utilization")
    ax.set_ylim(0, 1.3)
    ax.yaxis.set_major_formatter(lambda t, _: f"{t * 100:.0f}%")
    ax2 = ax.twinx()
    ax2.plot(w["week_start"], w["queue_mean"], color=AMBER, linewidth=1.4, label="Queue time (right)")
    ax2.set_ylabel(QUEUE_AXIS)
    ax2.spines["top"].set_visible(False)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, frameon=False, fontsize=9, ncol=2, loc="upper left")
    f.tight_layout()
    return save(f, "capacity_assembly_weekly", "Assembly Weekly Utilization and Queue Time")


# ── the new appendix tables ─────────────────────────────────────────────────
def blank(v, f=d2):
    return f(v) if v == v else ""


def t_hot():
    out = ""
    for per, H in ((f"{YEAR}", HY), (f"{YEAR} {REST}", HR)):
        rows = [[WC[w], P(r["utilization"]), f"{int(r['hot_weeks'])} of {int(r['weeks'])}", n0(r["hot_full_weeks"]), blank(r["queue_hot"]), d2(r["queue_other"]),
                 blank(r["wip_hot"], d1), d1(r["wip_other"]), pct(r["hours_share_hot"], 0)] for w, r in H.sort_values("utilization", ascending=False).iterrows()]
        out += block(per, table(pd.DataFrame(rows, columns=["Work center", "Utilization", "Weeks at or above 95%", "Of which full five-day weeks",
                                                             "Queue time in those weeks", "Queue time in the other weeks", "Jobs at the work center in those weeks, daily mean",
                                                             "Jobs at the work center in the other weeks, daily mean", "Share of machine hours in those weeks"])))
    BQ = C.BQ
    return out + block(f"Brake queue 90th percentile by quarter, {YEAR}",
                       table(pd.DataFrame([[d1(BQ.loc[k, "queue_p90"]) for k in (1, 2, 3, 4)]], columns=["Q1", "Q2", "Q3", "Q4"])))


def t_dispatch():
    out = ""
    for per, T in ((f"{YEAR}", START_Y), (f"{YEAR} {REST}", START_R)):
        rows = [[WC[w], n0(r["operations"]), pct(r["same_share"], 0), d2(r["same_queue"]), pct(r["next_share"], 0), d2(r["next_queue"]), pct(r["later_share"], 0),
                 d2(r["later_queue"]), pct(r["after_10"], 0), pct(r["after_14"], 0)] for w, r in T.loc[SC.LIST_CENTERS].iterrows()]
        out += block(per, table(pd.DataFrame(rows, columns=["Work center", "Operations", "Start the same working day", "Queue time, same day", "Start the next working day", "Queue time, next day",
                                                             "Start later", "Queue time, later", "Arrive after 10:00", "Arrive after 14:00"])))
    rows = [[k, pct(r["share"], 0), pct(r["same_day"], 0), d2(r["queue"]), pct(BRAKE_HOURS.loc[k, "same_day"], 0)] for k, r in HOURS.iterrows()]
    out += block(f"The four work centers together by hour of arrival, {YEAR}, with the brakes beside them",
                 table(pd.DataFrame(rows, columns=["Arrival", "Share of arrivals", "Start the same day", "Queue time", "Press brake, for comparison: start the same day"])))
    return out + block("Next-day wait per shipped job, working days",
                       table(pd.DataFrame([[d1(NEXT_DAY["year"]), d1(NEXT_DAY[REST])]], columns=[f"{YEAR}", f"{YEAR} {REST}"])))


def t_powder():
    rows = [[k.capitalize(), n0(r["operations"]), d1(r["days_per_week"]), r["weekdays"], d2(r["wait_mean"]), pct(r["day_or_more"], 0), pct(r["share_of_wait"], 0)]
            for k, r in POWDER.iterrows()]
    rows.append(["All", n0(POWDER_ALL["operations"]), "", "", d2(POWDER_ALL["wait_mean"]), pct(POWDER_ALL["day_or_more"], 0), "100%"])
    return table(pd.DataFrame(rows, columns=["Color", "Operations", "Scheduled days a week", "Days", "Wait for the color day, mean", "Waiting a day or more",
                                             "Share of the color-day wait"]))


def t_robot():
    rows = [[k, n0(r["weeks"]), n0(r["full_weeks"]), n0(r["operations"]), blank(r["queue"])] for k, r in ROBOT_BANDS.iterrows()]
    a = table(pd.DataFrame(rows, columns=["Utilization in the week", "Weeks", "Of which full five-day weeks", "Operations", "Queue time"]))
    rows = [[k.capitalize(), n0(r["operations"]), n0(r["hours"]), pct(r["share"], 0), d2(r["queue"])] for k, r in ROBOT_FAMILIES.iterrows()]
    b = table(pd.DataFrame(rows, columns=["Part family", "Operations", "Machine hours", "Share of hours", "Queue time"]))
    s = ROBOT_STD
    c = table(pd.DataFrame([["Setup", n0(s["setup_hours"]), n0(s["setup_standard"]), d2(s["setup_ratio"])], ["Run", n0(s["run_hours"]), n0(s["run_standard"]), d2(s["run_ratio"])]],
                           columns=["", "Hours", "Standard hours", "Hours over standard"]))
    return block(f"Weeks by utilization band, {YEAR}", a) + block(f"Hours by part family, {YEAR}", b) + block(f"Setup and run against standard, {YEAR}", c)


def t_assembly():
    rows = [[str(y), P(r["utilization"]), d2(r["queue"]), f"{int(r['hot_weeks'])} of {int(r['weeks'])}", n0(r["operations"])] for y, r in ASM["years"].iterrows()]
    assert abs(ASM["years"].loc[YEAR - 2, "queue"] - ASM["first_year_queue_from_start"]) > 0.1
    rows[0][0] += "*"
    a = table(pd.DataFrame(rows, columns=["Year", "Utilization", "Queue time", "Weeks at or above 95%", "Operations"]))
    a += (f"<p>* {YEAR - 2} includes the first four weeks of the record, when jobs already in process raise the queue time; from the week of January 30 the "
          f"{YEAR - 2} queue time is {d2(ASM['first_year_queue_from_start'])} days per operation.</p>")
    h, o = ASM["compare"]["hot"], ASM["compare"]["other"]
    rows = [["Weeks", n0(h["weeks"]), n0(o["weeks"])], ["Utilization", P(h["utilization"]), P(o["utilization"])], ["Queue time", d2(h["queue"]), d2(o["queue"])],
            ["Arrivals a week", d1(h["arrivals"]), d1(o["arrivals"])],
            ["Arrivals a week on jobs routed through the robotic weld cell", d1(h["robot_arrivals"]), d1(o["robot_arrivals"])],
            ["Robotic weld cell share of arrivals", pct(h["robot_share"], 0), pct(o["robot_share"], 0)],
            ["Machine hours per operation", d2(h["hours_per_operation"]), d2(o["hours_per_operation"])]]
    b = table(pd.DataFrame(rows, columns=["", "Weeks at or above 95%", "Other weeks"]))
    rows = [[k, n0(r["operations"]), pct(r["share_of_hours"], 0), d2(r["queue"]), d1(r["p90"])] for k, r in ASM["origin"].sort_values("operations", ascending=False).iterrows()]
    c = table(pd.DataFrame(rows, columns=["Weld on the job's routing", "Operations", "Share of assembly hours", "Queue time", "90th percentile"]))
    rows = [[WC.get(k, "Outside processing" if k == "outside_processing" else k), pct(v, 0)] for k, v in ASM["previous"].items()]
    d = table(pd.DataFrame(rows, columns=["Operation before assembly", "Share of assembly operations"]))
    rows = [[k.capitalize(), n0(r["operations"]), n0(r["hours"]), pct(r["share"], 0)] for k, r in ASM["families"].iterrows()]
    e = table(pd.DataFrame(rows, columns=["Part family", "Operations", "Machine hours", "Share of hours"]))
    g = table(pd.DataFrame([[k, d2(v)] for k, v in ASM["corr"].items()], columns=[f"Across the weeks of {YEAR}", "Correlation"]))
    return (block("By year", a) + block(f"Weeks at or above 95% against the other weeks, {YEAR}", b) + block(f"Where assembly's work comes from, {YEAR}", c + d)
            + block(f"Hours by part family, {YEAR}", e) + block("Weekly correlations", g))


def t_lasers():
    rows = [[MONTHS[m - 1], n0(r["first_operations"]), d2(r["queue"]), d1(r["p90"]), d2(r["material_wait"]), pct(r["with_wait"], 0), P(r["utilization"])]
            for m, r in LAS["month"].iterrows()]
    for per, label in (("year", f"{YEAR}"), (REST, f"{YEAR} {REST}")):
        r = LAS["period"][per]
        rows.append([label, n0(r["first_operations"]), d2(r["queue"]), d1(r["p90"]), d2(r["material_wait"]), pct(r["with_wait"], 0), ""])
    a = table(pd.DataFrame(rows, columns=["Month of the first cut", "First operations", "First-operation queue time, mean", "90th percentile", "Material wait, mean",
                                          "First operations with a material wait", "Laser utilization"]))
    rows = [[k, n0(r["scheduled"]), n0(r["machine"]), pct(r["share_of_hours"], 0), P(r["utilization"]), P(r["uptime"]), n0(r["run_hours"]), n0(r["standard_hours"]),
             d2(r["run_ratio"]), pct(r["share_of_standard"], 0)] for k, r in LAS["machines"].iterrows()]
    m = LAS["machines"]
    rows.append(["All", n0(m["scheduled"].sum()), n0(m["machine"].sum()), "100%", "", "", n0(m["run_hours"].sum()), n0(m["standard_hours"].sum()),
                 d2(m["run_hours"].sum() / m["standard_hours"].sum()), "100%"])
    b = table(pd.DataFrame(rows, columns=["Laser", "Scheduled hours", "Machine hours", "Share of laser hours", "Utilization", "Uptime", "Run hours",
                                          "Run standard hours", "Run hours over standard", "Share of laser standard hours"]))
    return block(f"By month, {YEAR}", a) + block(f"The three machines, {YEAR}", b)


# ── the report ──────────────────────────────────────────────────────────────
def build():
    T = Tables()
    T.add("util", "Utilization and machine uptime by work center", C.t_util())
    T.add("pos", "Position of each work center on its curve", C.t_pos())
    T.add("hot", "Weekly utilization at or above 95% by work center: weeks, queue time, jobs at the work center and share of hours", t_hot())
    T.add("bins", "Weekly brake queue time by utilization band, full weeks 2023 to 2025", C.t_bins())
    T.add("fits", "Fitted queue time curve by work center", C.t_fits())
    T.add("dispatch", "The dispatch-list work centers: start day, queue time and hour of arrival", t_dispatch())
    T.add("powder", "The powder line by color", t_powder())
    T.add("var", f"Variability sources, {YEAR}", C.t_var())
    T.add("spread", "Brake queue time with the spread of setup time halved, and the inputs", C.t_setup())
    T.add("machines", f"Utilization and queue time for the five brakes and the robotic weld cell, {YEAR} and {REST}", C.t_machines())
    T.add("basis", "The brakes and the robotic weld cell: hours and utilization on both bases", C.t_machine_basis())
    T.add("robot", "The robotic weld cell: weeks by utilization band, hours by part family, setup and run against standard", t_robot())
    T.add("assembly", "Assembly: hot weeks, where its work comes from, and the weekly correlations", t_assembly())
    T.add("laser_weeks", "Laser weeks, November and December 2024", C.t_laser())
    T.add("lasers", "The lasers: first-operation queue time and material wait by month, and the three machines", t_lasers())
    T.add("bywc", "Setup against standard by work center", S.t_by(S.BYWC.rename(index=S.WC), "Work center", rest=False))
    T.add("period", "Brake setup against standard by period", S.t_by(S.OV, "Period", {"year": f"{YEAR}", REST: f"{YEAR} {REST}", "Q1": f"{YEAR} Q1"}, rest=False))
    T.add("handover", "Brake setups handed over at a shift boundary, and by time left in the shift at the start", S.t_handover() + S.t_start())
    T.add("lot", "Brake setups by lot-size band", S.t_by(S.LOT, "Lot size"))
    T.add("familiarity", "Brake setups by the operator's prior setups of the part", S.t_by(S.FML, "Prior setups"))
    T.add("family", "Brake setups by part family", S.t_by(S.FAM, "Family"))
    T.add("tenure", "Brake setups by operator tenure, and the tenure effect as controls are added", S.t_by(S.TEN, "Tenure") + S.t_tenure())
    T.add("assign", "First setups of repeat parts where another operator had set the part up", S.t_assign())
    T.add("grouping", "Same-tooling grouping by brake", S.t_grouping())
    T.add("top12", f"The top {SA.TOP_N} setup reduction candidates by overrun hours times work center utilization, {YEAR}", S.t_top())
    T.add("top20", "Setup reduction candidates, top 20", S.t_top20())
    T.add("released", "Brake hours released: the handover and the candidate list", S.t_cf())
    T.add("run", "Run actual against standard by work center and laser", S.t_run())
    T.add("stale", "Stale-standard parts against refreshed parts", S.t_stale())
    T.add("planned", "Planned operation hours with standards refreshed", S.t_planned())
    T.add("quoted", "Standard hours per job with standards refreshed, by routing class", S.t_quoted())

    UY, UR, MY, MR, PY, PR, FB = C.UY, C.UR, C.MY, C.MR, C.PY, C.PR, C.FB
    ops = C.D["ops"]
    y = S.OV.loc["year"]
    others_setup = S.BYWC.drop("press_brake")
    other_run = S.RWC[S.RWC["work_center"] != "laser"]["run_ratio"]
    newer = " and ".join(S.NEWER)
    b = []

    # 1 ── capacity across the shop
    b.append("<h2 id='f1'>1. Capacity Across the Shop</h2>")
    act = ACTIVITY
    busy, slow = act.sort_values("ops_per_machine_week", ascending=False).index[:3], act.sort_values("ops_per_machine_week").index[:3]
    assert set(busy) == set(act.sort_values("hours_per_operation").index[:3]) == {"grind_deburr", "inspection_pack", "powder_coat"}
    assert set(slow) == set(act.sort_values("hours_per_operation", ascending=False).index[:3]) == {"weld", "assembly", "robotic_weld"}
    b.append(f"<p>The shop's floor consists of ten work centers and {n0(act['machines'].sum())} machines. The floor activity (operations per machine a week and "
             f"hours per operation) in routing order is shown below. The grind and deburr, inspection and pack, and powder coat stations run the highest number of "
             f"operations per machine a week while averaging the shortest amount of time per operation "
             f"({rng(act.loc[busy, 'hours_per_operation'].min(), act.loc[busy, 'hours_per_operation'].max())} hours), and the manual weld bays, assembly and the "
             f"robotic weld cell run the fewest operations while averaging the longest time "
             f"({rng(act.loc[slow, 'hours_per_operation'].min(), act.loc[slow, 'hours_per_operation'].max(), d1)} hours).</p>")
    b.append(chart(f"Floor Activity by Work Center, {YEAR}", fig_activity()))

    b.append("<h3 id='f1_1'>Machine Utilization and Uptime</h3>")
    sched, down, mach = UY["scheduled"].sum(), UY["down"].sum(), UY["machine"].sum()
    b.append(f"<p>In {YEAR}, there were {n0(len(ops))} machine operations across ten work centers. This translates to {n0(sched)} scheduled hours, "
             f"{n0(sched - down)} available hours, and {n0(mach)} machine hours over the course of the year, as defined below:</p>"
             f"<ul><li>Scheduled hours: the hours the machine was crewed</li><li>Available hours: scheduled hours less recorded downtime</li>"
             f"<li>Machine hours: hours the machine was actually running jobs (both setup and run)</li><li>Uptime: available hours / scheduled hours</li>"
             f"<li>Utilization: machine hours / available hours</li></ul>")
    mid = UY.drop(["press_brake", "robotic_weld", "laser", "powder_coat"])
    gap = round(UY["uptime"] * 100) - round(UY["utilization"] * 100)
    assert gap.idxmin() == "press_brake"
    b.append(f"<p>In {YEAR}, the brakes ran at {P(UY.loc['press_brake', 'utilization'])} utilization against {P(UY.loc['press_brake', 'uptime'])} uptime, a "
             f"{gap['press_brake']:.0f}-point gap that is the smallest production capacity buffer of any work center. The robotic weld cell ran at "
             f"{P(UY.loc['robotic_weld', 'utilization'])} utilization, the laser cutting stations at {P(UY.loc['laser', 'utilization'])} and the assembly through "
             f"hardware work centers at {P(mid['utilization'].min())} to {P(mid['utilization'].max())}. The powder line ran at just "
             f"{P(UY.loc['powder_coat', 'utilization'])} utilization. Uptime is {P(UY['uptime'].min())} to {P(UY['uptime'].max())} at every work center. "
             f"{T.see('util')}</p>")
    b.append(titled(C.fig_util(), "Utilization and Machine Uptime by Work Center"))
    cause = DOWN.sum() / DOWN.values.sum()
    assert list(cause.sort_values(ascending=False).index) == DOWN_ORDER
    b.append(f"<p>Machine uptime figures above treat setup as part of running time, not downtime; setup is counted within utilization for the purposes of this "
             f"report. Across all work centers, the sources of machine downtime were unplanned breakdowns ({P(cause['breakdown'])}), planned maintenance "
             f"({P(cause['PM'])}), no operator present ({P(cause['no operator'])}) and waiting for a program ({P(cause['waiting for program'])}). The chart below "
             f"details machine downtime by work center.</p>")
    b.append(chart(f"Machine Downtime Hours and Sources by Work Center, {YEAR}", fig_downtime()))

    # 2 ── load, queue time and WIP
    b.append("<h2 id='f2'>2. Load, Queue Time and WIP</h2>")
    b.append("<h3 id='f2_1'>Queue time against load</h3>")
    lo = C.BINS.iloc[:2]
    below = float((lo["queue_mean"] * lo["weeks"]).sum() / lo["weeks"].sum())
    step = float(C.BINS.iloc[2]["queue_mean"])
    fits = C.FITS.set_index("work_center")
    four = ["press_brake", "robotic_weld", "laser", "assembly"]
    at90 = fits["queue_at_0.90"]
    assert at90["assembly"] > at90["robotic_weld"] > at90["laser"] > at90["press_brake"]
    onc = lambda w: f"{d2(PY.loc[w, 'queue_measured'])} against {d2(PY.loc[w, 'queue_on_curve'])}"
    T.reserve("bins", "fits")
    b.append(f"<p>The curve is the queue time expected at each level of utilization for the number of machines at the work center, fitted on rolling 13-week "
             f"windows from 2023 to 2025; for the brakes the fit explains {P(FB['r2'])} of the variation in the windowed queue time with a rank correlation of "
             f"{d2(FB['rank_correlation'])}, while a single week's queue time carries the backlog of the weeks before it. On the fitted curve the brake queue time is "
             f"{d2(FB['queue_at_0.75'])} days per operation at 75% utilization, {d2(FB['queue_at_0.85'])} at 85%, {d2(FB['queue_at_0.90'])} at 90% and "
             f"{d2(FB['queue_at_0.92'])} at 92%; the measured queue time is {d2(PY.loc['press_brake', 'queue_measured'])} at "
             f"{P(PY.loc['press_brake', 'utilization'])} for the year and {d2(PR.loc['press_brake', 'queue_measured'])} at {P(PR.loc['press_brake', 'utilization'])} "
             f"in {REST}. Week by week, the brake queue time steps from about {d1(below)} days below 85% utilization to {d1(step)} above it and does not settle "
             f"back. The same curve is fitted for every work center; it describes the brakes, the robotic weld cell, the lasers and assembly (rank correlation "
             f"{rng(fits.loc[four, 'rank_correlation'].min(), fits.loc[four, 'rank_correlation'].max())}) and not the dispatch-list work centers or the powder line "
             f"({T.plain('fits')}). On their curves at 90% utilization the wait is {d1(at90['assembly'])} days per operation at assembly's two benches and "
             f"{d1(at90['robotic_weld'])} at the single-machine weld cell, against {d1(at90['laser'])} at the three lasers and {d1(at90['press_brake'])} at the five "
             f"brakes. The brakes and lasers run on their curves ({onc('press_brake')} days measured against on the curve, and {onc('laser')}); the weld cell and "
             f"assembly run above theirs ({onc('robotic_weld')}, and {onc('assembly')}), so part of their wait is not explained by load, which the batched arrivals "
             f"from the powder line and outside processing described under Assembly account for in part. {T.see('bins', 'fits')}</p>")
    b.append(chart("Queue Time Against Utilization, Four Work Centers, 2023 to 2025",
                   fig_panels(four, "capacity_queue_against_utilization", "Queue Time Against Utilization, Four Work Centers, 2023 to 2025", True, 12))
             + note("Points are full weeks; the curve is the fitted queue time at each utilization."))
    b.append("<p>The curve does not describe hardware, grind and deburr, inspection and pack, or the powder line: their queue times follow the daily dispatch list "
             "and the color schedule, not load.</p>")
    BQ = C.BQ
    b.append(f"<p>The brake queue time's 90th percentile was {d1(BQ.loc[1, 'queue_p90'])} and {d1(BQ.loc[2, 'queue_p90'])} days in Q1 and Q2 {YEAR} and "
             f"{d1(BQ.loc[3, 'queue_p90'])} and {d1(BQ.loc[4, 'queue_p90'])} in Q3 and Q4; under 5 days in every quarter is the mark the levers in this report are "
             f"measured against.</p>")
    b.append("<p>The brake queue is set by arrival variability and by load above 85%, so capacity at the constraint is the lever: the setup program of "
             f"<a href='#f3'>Section 3</a> and planned Saturday brake shifts for the peak, both tested in {link('options')}. Release leveling and dispatch rules do "
             "not help this shop, and reducing the spread of setup time is not a lever.</p>")

    b.append("<h3 id='f2_2'>Hot weeks</h3>")
    hot_y = HY[HY["hot_weeks"] > 0].sort_values("hot_weeks", ascending=False)
    rank = UY["utilization"].rank(ascending=False)
    assert list(hot_y.index) == HOT_ORDER and rank["laser"] == 3 and rank["punch"] == len(rank) - 2
    assert set(HR[HR["hot_weeks"] > 0].index) == set(HOT_SIX)
    assert all(HR.loc[w, "queue_hot"] > HR.loc[w, "queue_other"] and HR.loc[w, "wip_hot"] > HR.loc[w, "wip_other"] for w in HOT_SIX)
    assert all(HR.loc[w, "wip_hot"] / HR.loc[w, "wip_other"] < HR.loc[w, "queue_hot"] / HR.loc[w, "queue_other"] for w in HOT_SIX)
    assert HY.loc["press_brake", "queue_hot"] < HY.loc["press_brake", "queue_other"]
    pair = lambda w: f"{d2(HR.loc[w, 'queue_hot'])} against {d2(HR.loc[w, 'queue_other'])}"
    jobs = lambda w, f=n0: f"{f(HR.loc[w, 'wip_hot'])} jobs at {NAME[w]} against {f(HR.loc[w, 'wip_other'])} in other weeks"
    b.append(f"<p>A hot week is one in which a work center ran at or above 95% utilization. As seen below, {NUMBER[len(hot_y)].lower()} work centers recorded at "
             f"least one hot week in {YEAR}, with the brakes recording the most, followed by the robotic weld cell and assembly. The punch recorded the third lowest "
             f"average utilization yet {int(HY.loc['punch', 'hot_weeks'])} hot weeks, because it is a single machine running about "
             f"{n0(act.loc['punch', 'ops_per_week'])} operations a week, so a few large jobs fill a week. The lasers recorded the third highest utilization yet only "
             f"{int(HY.loc['laser', 'hot_weeks'])} hot weeks, because they pool three machines over about {n0(act.loc['laser', 'ops_per_week'])} operations a week and "
             f"go hot only when releases surge, as they did in the six weeks of the Q4 2024 build ({T.plain('laser_weeks')}) that formed the backlog detailed in "
             f"{link('lead')}. In {REST} a hot week shows as a longer wait at each of the six that had one: {d2(HR.loc['press_brake', 'queue_hot'])} days per "
             f"operation at the brakes against {d2(HR.loc['press_brake', 'queue_other'])} in the other weeks, {pair('robotic_weld')} at the robotic weld cell, "
             f"{pair('assembly')} at assembly, {pair('punch')} at the punch, {pair('laser')} at the lasers and {pair('weld')} at the manual weld bays. For the full "
             f"year the brakes read the other way ({d2(HY.loc['press_brake', 'queue_hot'])} against {d2(HY.loc['press_brake', 'queue_other'])}) because the "
             f"first-quarter backlog kept the wait long whatever the week's utilization. The count of jobs at the work center rises too, though by less than the wait "
             f"does: {jobs('press_brake')} and {d1(HR.loc['robotic_weld', 'wip_hot'])} against {d1(HR.loc['robotic_weld', 'wip_other'])} at the robotic weld cell. "
             f"Hot weeks carry {P(HR.loc['press_brake', 'hours_share_hot'])} of brake hours and {P(HR.loc['robotic_weld', 'hours_share_hot'])} of the weld cell's in "
             f"{REST}, {P(HR.loc['punch', 'hours_share_hot'])} of the punch's and {P(HR.loc['assembly', 'hours_share_hot'])} of assembly's. {T.see('pos', 'hot')}</p>")
    b.append(chart(f"Share of hot weeks by work station, {YEAR}", fig_hot_share()))
    b.append(chart("Queue Time and Jobs at the Work Center in Hot Weeks and Other Weeks, Q2-Q4 2025", fig_hot()))

    b.append("<h3 id='f2_3'>The five brakes</h3>")
    tail = MY.loc[["B3", "B4", "B5"]]
    top_y = MY.loc[C.BRAKES, "utilization"].sort_values(ascending=False).index.tolist()
    u1 = lambda x: f"{x * 100:.1f}%"
    b.append(f"<p>The brakes run at {P(UY.loc['press_brake', 'utilization'])} and carry {P(QSHARE['press_brake'])} of all queue time (the flow report). "
             f"B1 and B2 run at {u1(MY.loc['B1', 'utilization'])} and {u1(MY.loc['B2', 'utilization'])} for the year and "
             f"{u1(MR.loc['B1', 'utilization'])} and {u1(MR.loc['B2', 'utilization'])} in {REST}, with the shortest queue times of the five "
             f"(mean {d1(MY.loc['B1', 'queue_mean'])} and {d1(MY.loc['B2', 'queue_mean'])} days): precision work goes to them first and the hot list sends "
             f"expedited work to them. B3 to B5 carry the tail: mean {rng(tail['queue_mean'].min(), tail['queue_mean'].max(), d1)} days and 90th percentile "
             f"{rng(tail['queue_p90'].min(), tail['queue_p90'].max(), d1)}. "
             + (f"Over all hours worked, {top_y[0]} carries the highest load of the five for the year; in {REST} B1 and B2 do. " if top_y[0] not in ("B1", "B2") else "")
             + f"On crewed weekday shifts only, B1 and B2 run at {u1(MY.loc['B1', 'utilization_weekday_basis'])} and {u1(MY.loc['B2', 'utilization_weekday_basis'])} "
             f"for the year. {T.see('machines', 'basis')}</p>")
    SV, var = C.SV, C.var
    b.append(f"<p>Halving the spread of brake setup time (each setup time moved halfway to the mean, the curve rescaled for the lower variability of setup and run) "
             f"releases {d1(SV.loc['year', 'hours_per_week_released'])} brake "
             f"hours a week and cuts the queue time on the curve from {d2(SV.loc['year', 'queue_on_curve'])} to {d2(SV.loc['year', 'queue_with_half_setup_spread'])} days. "
             f"The variability at the brakes is in arrivals (daily coefficient of variation {d2(var('Arrivals: jobs released per working day'))}, Mondays "
             f"{d2(var('Arrivals: Monday'))} times the daily mean, the top customer's month-end {d2(var('Arrivals: top customer'))} times) and in run time "
             f"(coefficient of variation {d2(var('Brake run time'))} against {d2(var('Brake setup time'))} for setup). This is the spread of setup time, not its mean; "
             f"the mean is the subject of <a href='#f3'>Section 3</a>. Second-shift absence is {P(var('Absence, second shift: share'))} against "
             f"{P(var('Absence, first shift: share'))} on first shift. {T.see('var', 'spread')}</p>")
    b.append(chart(f"Utilization and Queue Time by Brake, {YEAR}", fig_brakes()))

    b.append("<h3 id='f2_4'>The robotic weld cell</h3>")
    ROB = C.ROB
    assert PR["queue_measured"].idxmax() == "robotic_weld"
    rf = ROBOT_FAMILIES
    assert list(rf.index[:3]) == ["enclosure", "weldment", "chassis"]
    b.append(f"<p>The robotic weld cell runs at {P(UY.loc['robotic_weld', 'utilization'])} on one shift and has the longest queue time in the shop in {REST}, "
             f"{d1(ROB.loc[REST, 'queue_mean'])} days per operation against {d1(UR.loc['press_brake', 'queue_mean'])} at the brakes.</p>")
    b.append(f"<p>The cell runs at or above 95% in {n0(ROBOT_BANDS.loc['at or above 95%', 'weeks'])} weeks of {n0(ROBOT_BANDS['weeks'].sum())} and below 80% in "
             f"{n0(ROBOT_BANDS.loc['below 80%', 'weeks'])}, alternating between idle and saturated weeks rather than running steadily hot; its queue time is "
             f"{d2(ROBOT_BANDS.loc['below 80%', 'queue'])} days per operation in the weeks below 80% and "
             f"{d2(ROBOT_BANDS.loc['at or above 95%', 'queue'])} in the weeks at or above 95%. Enclosures are {P(rf.loc['enclosure', 'share'])} of its hours, "
             f"weldments {P(rf.loc['weldment', 'share'])} and chassis {P(rf.loc['chassis', 'share'])}. Its setups run at {d2(ROBOT_STD['setup_ratio'])} of "
             f"standard and its run time at {d2(ROBOT_STD['run_ratio'])}, so the cell's queue time is load, not standards. {T.see('robot')}</p>")
    b.append("<p>A second shift on the robotic weld cell is the open shift on the secondary constraint; the options report tests and prices it.</p>")

    b.append("<h3 id='f2_5'>Assembly</h3>")
    ah, ao = ASM["compare"]["hot"], ASM["compare"]["other"]
    yr, og, pv = ASM["years"], ASM["origin"], ASM["previous"]
    assert list(pv.index[:2]) == ["powder_coat", "outside_processing"] and og["p90"].idxmax() == "No weld"
    quiet = max(abs(v) for k, v in ASM["corr"].items() if "robotic weld cell hours" in k or "earlier" in k)
    assert quiet < 0.2, quiet
    b.append(f"<p>Assembly runs at {P(UY.loc['assembly', 'utilization'])} for the year but at {P(ah['utilization'])} in its {int(ah['weeks'])} hot weeks, when "
             f"operations wait {TIMES[round(ah['queue'] / ao['queue'])]} times as long as in other weeks. Its two benches ran at {P(yr.loc[YEAR, 'utilization'])} in "
             f"{YEAR}, up from {P(yr.loc[YEAR - 2, 'utilization'])} in {YEAR - 2} and "
             f"{P(yr.loc[YEAR - 1, 'utilization'])} in {YEAR - 1}, with {int(yr.loc[YEAR, 'hot_weeks'])} hot weeks against "
             f"{'none' if yr.loc[YEAR - 2, 'hot_weeks'] == 0 else int(yr.loc[YEAR - 2, 'hot_weeks'])} in {YEAR - 2} and {int(yr.loc[YEAR - 1, 'hot_weeks'])} in "
             f"{YEAR - 1}. In the hot weeks utilization is {P(ah['utilization'])} and the queue time {d2(ah['queue'])} days per operation against {P(ao['utilization'])} "
             f"and {d2(ao['queue'])} in the other {int(ao['weeks'])}; {ASM['backlog_weeks']} of the {int(ah['weeks'])} are the first-quarter backlog. The hot weeks "
             f"are assembly's own: arrivals run {d1(ah['arrivals'])} a week against {d1(ao['arrivals'])} and operations are "
             f"{P(ah['hours_per_operation'] / ao['hours_per_operation'] - 1)} larger ({d2(ah['hours_per_operation'])} machine hours against "
             f"{d2(ao['hours_per_operation'])}), while the robotic weld cell's share of arrivals barely moves ({P(ah['robot_share'])} against "
             f"{P(ao['robot_share'])}) and assembly utilization does not follow the cell's output in the same week or the two before it. Assembly receives "
             f"{P(pv['powder_coat'])} of its work from the powder line and {P(pv['outside_processing'])} from outside processing, the two stages that "
             f"release work on their own schedules, and the longest assembly queue times are on jobs with no weld operation at all (90th percentile "
             f"{d1(og.loc['No weld', 'p90'])} days against {d1(og.loc['Manual weld bays', 'p90'])} and {d1(og.loc['Robotic weld cell', 'p90'])}). "
             f"{T.see('assembly')}</p>")
    b.append(chart("Assembly Weekly Utilization and Queue Time", fig_assembly()))

    b.append("<h3 id='f2_6'>The lasers</h3>")
    nov = C.LAS_NOV
    six = nov[nov["week_start"] >= "2024-11-11"]
    three = six.iloc[:3]
    assert len(six) == 6
    b.append(f"<p>The lasers run at {P(UY.loc['laser', 'utilization'])} and matter at the year-end peak. Over the six weeks from November 11, 2024 they ran at "
             f"{P(six['utilization'].min())} to {P(six['utilization'].max())}, and at {P(three['utilization'].min())} to {P(three['utilization'].max())} in the first "
             f"three, with the first-operation queue time rising from {d1(nov.iloc[0]['queue_mean'])} to {d1(nov.iloc[-1]['queue_mean'])} days by mid-December. They "
             f"reached 95% in {C.LW_N} of {C.LW_ALL} full weeks in three years. {T.see('laser_weeks')}</p>")
    mo, lm, lp = LAS["month"], LAS["machines"], LAS["period"]
    builds = mo.loc[[1, 12]]
    ordinary = mo.drop([1, 12])
    assert builds["queue"].min() > ordinary["queue"].max()
    over = float((lm.loc[S.NEWER, "standard_hours"] - lm.loc[S.NEWER, "run_hours"]).sum())
    b.append(f"<p>In an ordinary month the first-operation queue time is under a day and a half ({rng(ordinary['queue'].min(), ordinary['queue'].max())} on the monthly "
             f"mean) and its 90th percentile no more than {d1(ordinary['p90'].max())} days; January ({d2(mo.loc[1, 'queue'])}) and December ({d2(mo.loc[12, 'queue'])}) "
             f"are the two builds. Material wait is steady through the year: {P(lp['year']['with_wait'])} of first operations wait for material, "
             f"{rng(mo['material_wait'].min(), mo['material_wait'].max(), d1)} days on the monthly mean across all jobs and "
             f"{rng(min(lp[REST]['wait_where_any'], lp['year']['wait_where_any']), max(lp[REST]['wait_where_any'], lp['year']['wait_where_any']), d1)} days where "
             f"there is a wait. The work center's {P(UY.loc['laser', 'utilization'])} hides a split by machine: L1 runs one shift at "
             f"{P(lm.loc['L1', 'utilization'])}, {newer} run two shifts at {P(lm.loc[S.NEWER[0], 'utilization'])} and {P(lm.loc[S.NEWER[1], 'utilization'])}. "
             f"{newer} carry {P(lm.loc[S.NEWER, 'share_of_standard'].sum())} of laser standard hours and run them in "
             f"{d2(lm.loc[S.NEWER, 'run_hours'].sum() / lm.loc[S.NEWER, 'standard_hours'].sum())} of the standard time, so planned laser hours on the two are "
             f"overstated by {n0(over)} for the year ({n0(lm['standard_hours'].sum())} standard against {n0(lm['run_hours'].sum())} actual across the three "
             f"machines); <a href='#f4'>Section 4</a> takes this up. {T.see('lasers')}</p>")
    b.append(chart(f"First-Operation Queue Time and Material Wait by Month, {YEAR}", fig_laser_months()) + note("December counts jobs shipped by the end of the record."))

    b.append("<h3 id='f2_7'>Queues set by the list, not by load</h3>")
    listed = PY.loc[SC.LIST_CENTERS, "queue_measured"]
    b.append(chart("Queue Time Against Utilization, Dispatch-List Work Centers, 2023 to 2025",
                   fig_panels(SC.LIST_CENTERS, "capacity_queue_against_utilization_list", "Queue Time Against Utilization, Dispatch-List Work Centers, 2023 to 2025",
                              False, 4))
             + note(f"Points are full weeks, on a scale of 0 to 4 days. No curve is drawn: queue time at these work centers does not rise with utilization "
                    f"({T.plain('fits')}). The line is the {YEAR} mean queue time."))
    share = lambda Tb, c: f"{P(Tb[c].min())} to {P(Tb[c].max())}"
    early, mid_day, late = HOURS.iloc[:3], HOURS.iloc[3:5], HOURS.iloc[5:]
    same = lambda g: float((g["same_day"] * g["arrivals"]).sum() / g["arrivals"].sum())
    assert 0.85 <= same(early) < 0.95 and 0.25 <= same(mid_day) < 0.35, (same(early), same(mid_day))
    assert set(X["shifts"].set_index("work_center").loc[SC.LIST_CENTERS, "shifts"]) == {1}          # one shift at each, so no crew for a list at 14:00
    brake_day = BRAKE_HOURS.iloc[1:5]["same_day"]
    next_queue = float((START_Y["next_queue"] * START_Y["next_share"] * START_Y["operations"]).sum() / (START_Y["next_share"] * START_Y["operations"]).sum())
    b.append(f"<p>At the four work centers the curve does not describe, queue time is flat across the range of utilization the shop has run them at, and sits at "
             f"{rng(listed.min(), listed.max())} days per operation for the year whatever the week's load. At grind and deburr, inspection and pack, hardware and "
             f"the manual weld bays, {share(START_Y, 'next_share')} of operations start on the working day "
             f"after they arrive and wait about {d1(next_queue)} days to do so; {share(START_Y, 'same_share')} start the same day, within half a day; "
             f"{share(START_Y, 'later_share')} wait longer. The split is the same in {REST} ({share(START_R, 'next_share')} next day). What decides it is the hour of "
             f"arrival, not the load: work arriving before 10:00 starts the same day nine times in ten, work arriving between 10:00 and 14:00 "
             f"({P(mid_day['share'].sum())} of arrivals) starts the same day about three times in ten, and the {P(late['share'].sum())} arriving after the "
             f"shift ends starts the next morning. The brakes show no such break; {P(brake_day.min())} to {P(brake_day.max())} of their arrivals start the "
             f"same day in every band from 06:00 to 14:00. Across a shipped job, these next-day waits add {d1(NEXT_DAY['year'])} working days of lead time "
             f"({d1(NEXT_DAY[REST])} in {REST}). {T.see('dispatch')}</p>")
    b.append(chart(f"Same-Day Start by Hour of Arrival, Dispatch-List Work Centers Against the Brakes, {YEAR}", fig_same_day()))
    b.append(f"<p>The lever is the list, not capacity. A midday refresh of the day's list at these four work centers lets the arrivals between 10:00 and 12:00, "
             f"{P(HOURS.iloc[3]['share'])} of the total, start the same afternoon; what arrives after the shift ends can only start the next morning.</p>")
    two, once = POWDER[POWDER["days_per_week"] > 1.5], POWDER[POWDER["days_per_week"] <= 1.5]
    assert list(two.index) == ["black", "white", "gray"] and sorted(once.index) == ["beige", "blue", "red"]
    b.append(f"<p>The powder line's color-day wait is {d2(POWDER_ALL['wait_mean'])} days per operation and {P(POWDER_ALL['day_or_more'])} of operations wait a day "
             f"or more. Black, white and gray run two days a week and wait {rng(two['wait_mean'].min(), two['wait_mean'].max())} days; beige, blue and red run once a "
             f"week, wait {rng(once['wait_mean'].min(), once['wait_mean'].max(), d1)} days, and {share(once, 'day_or_more')} of their operations wait a day or more. The "
             f"three once-a-week colors are {P(once['share_of_operations'].sum())} of operations and {P(once['share_of_wait'].sum())} of the wait; black is "
             f"{P(POWDER.loc['black', 'share_of_wait'])} of the wait on volume alone. A third day for black was tested in the options report and does not move "
             f"on-time delivery. {T.see('powder')}</p>")

    # 3 ── setups against standard
    b.append("<h2 id='f3'>3. Setups Against Standard</h2>")
    ST, MH_WEEK = S.ST, S.MH_WEEK
    b.append(f"<p>{n0(len(S.D['s']))} setups at all work centers in {YEAR}, {n0(y['setups'])} of them at the brakes. A setup's ratio is its setup machine hours over "
             f"the setup standard on the job operation; hours over standard is total setup hours over total standard hours. Every work center except the brakes runs "
             f"its setups at a median of {rng(others_setup['median_ratio'].min(), others_setup['median_ratio'].max())} of standard and within "
             f"{n0(others_setup['overrun_hours'].max())} overrun hours for the year; the brakes ran {n0(y['setup_hours'])} hours against {n0(y['standard_hours'])} "
             f"standard, {n0(y['overrun_hours'])} over, {n0(ST['brake_overrun_per_week'])} a week, {pct(ST['brake_overrun_per_week'] / MH_WEEK, 0)} of brake machine "
             f"time. The median brake setup runs at {d2(y['median_ratio'])} of standard and the 90th percentile at {d2(y['p90_ratio'])}. Setup ratios do not move "
             f"with the 2024 year-end build: the median is {d2(S.OV.loc['Q1', 'median_ratio'])} in the first quarter and {d2(S.OV.loc[REST, 'median_ratio'])} in "
             f"{REST}. {T.see('bywc', 'period')}</p>")

    b.append("<h3 id='f3_1'>Where the overrun sits</h3>")
    ho, nho, small, LOT, FML, FAM = S.HO.loc["Handed over at a shift boundary"], S.HO.loc["Not handed over"], S.LOT.loc["under 25"], S.LOT, S.FML, S.FAM
    bump = small["median_ratio"] / LOT.drop("under 25")["median_ratio"].mean() - 1
    b.append(f"<p>Setups handed over at a shift boundary (setup transactions by different operators one after the other across the 14:00 or 22:30 shift boundary; two operators at the same time is a two-person "
             f"setup, not a handover) are {pct(ho['share_of_setups'], 0)} of setups "
             f"and {pct(ho['share_of_overrun'], 0)} of the overrun hours, median {d2(ho['median_ratio'])} against {d2(nho['median_ratio'])}; most of those hours are "
             f"long setups that reached the boundary rather than the handover itself (<a href='#f3_4'>The setup reduction list and the handover</a>). Lots under 25 "
             f"are {pct(small['setups'] / y['setups'], 0)} of setups and {pct(ST['small_lot_overrun_share'], 0)} of the overrun, median {d2(small['median_ratio'])} "
             f"against {d2(LOT.loc['100 and over', 'median_ratio'])} to {d2(LOT.loc['25 to 99', 'median_ratio'])} on larger lots: the setup standards under-plan "
             f"small lots. First setups of a part by the operator run at {d2(FML.loc['none', 'median_ratio'])} against {d2(FML.loc['1 or 2', 'median_ratio'])}. "
             f"Enclosures and chassis run at {d2(FAM.loc['enclosure', 'median_ratio'])} and {d2(FAM.loc['chassis', 'median_ratio'])}; panels and brackets at "
             f"{d2(FAM.loc['panel', 'median_ratio'])} and {d2(FAM.loc['bracket', 'median_ratio'])}. {T.see('handover', 'lot', 'familiarity', 'family')}</p>")
    b.append(titled(S.fig_conditions(), "Brake Setup Overrun Hours by Condition"))
    b.append(f"<p>The setup standard on lots under 25 pieces should be raised by {pct(bump, 0)}, so the schedule and the quote stop under-planning them.</p>")

    b.append("<h3 id='f3_2'>Operator tenure and familiarity</h3>")
    TM, MIX, PLACE, WHO, ANY, SAME = S.TM, S.MIX, S.PLACE, S.WHO, S.ASG_ANY, S.ASG_SAME
    b.append(f"<p>Operators with under 12 months run {pct(TM['tenure_effect_pct'].iloc[0], 0)} above tenured operators before controls and "
             f"{pct(TM['tenure_effect_pct'].iloc[-1], 0)} after familiarity, grouping, machine, lot size, bend count and shift handover. Their "
             f"{n0(MIX.loc[1, 'setups'])} setups of {n0(y['setups'])} were made by {len(WHO)} operators, {n0(WHO.iloc[0])} by one, and "
             f"{pct(PLACE.loc['B4', 1], 0)} were on B4. The tenure effect is mostly what new operators are given, not who they are. {T.see('tenure')}</p>")
    b.append(titled(S.fig_tenure(), "Tenure Effect on Brake Setup Ratio as Controls Are Added"))
    b.append(f"<p>{n0(ANY['count'])} first setups of a repeat part were made while another current brake operator had set the part up in the "
             f"previous 24 months. They ran at {d2(ANY['hours_weighted_ratio'])} of standard against {d2(ANY['ratio_with_familiarity'])} for setups with prior "
             f"familiarity in the same lot band and family: {d1(ANY['hours_released_per_week'])} brake hours a week ({d1(SAME['hours_released_per_week'])} "
             f"where that operator was on the same shift). This is a matched comparison, not a start-time test, so part of it may be selection. Repeat setups should "
             f"go to an operator who has set the part up before. {T.see('assign')}</p>")

    b.append("<h3 id='f3_3'>Grouping</h3>")
    GRP = S.GRP
    ga, b12, b345 = GRP.loc["all brakes"], GRP.loc[["B1", "B2"], "share_grouped"], GRP.loc[["B3", "B4", "B5"], "share_grouped"]
    b.append(f"<p>{pct(ga['share_grouped'], 0)} of brake setups follow a job on the same tooling set and run at {d2(ga['ratio_grouped'])} of standard against "
             f"{d2(ga['ratio_not_grouped'])}, saving {d1(ga['hours_saved_per_week'])} hours a week. B1 and B2 group {pct(b12.min(), 0)} to {pct(b12.max(), 0)} of their "
             f"setups against {pct(b345.min(), 0)} to {pct(b345.max(), 0)} on B3 to B5: precision work and the hot list come first there. {T.see('grouping')}</p>")
    b.append(titled(S.fig_grouping(), "Same-tooling Grouping by Brake"))

    b.append("<h3 id='f3_4'>The setup reduction list and the handover</h3>")
    cf_naive, cf_start, late, early_med = S.HCF.iloc[0], S.HCF.iloc[1], S.HST.iloc[0], S.HST.iloc[2:]["median_ratio"]
    b.append(f"<p>The top {SA.TOP_N} part-operations release {d1(ST['top_hours_per_week'])} brake hours a week at standard: {pct(ST['top_share_of_brake_overrun'], 0)} of "
             f"the overrun and {pct(ST['top_hours_per_week'] / MH_WEEK)} of brake machine time. The overrun is spread across {n0(ST['brake_part_operations'])} "
             f"part-operations, so no short list captures most of it. {T.see('top12', 'top20')}</p>")
    b.append(f"<p>Handed-over setups carry {d1(cf_naive['hours_per_week'])} hours a week above the ratio of setups finished by the operator who started them, but most "
             f"of that is length, not handover: a long setup is the one that reaches the end of the shift. Setups started in the last 30 minutes of a shift are handed "
             f"over {pct(late['share_handed_over'], 0)} of the time and run at a median {d2(late['median_ratio'])} against {d2(early_med.min())} to "
             f"{d2(early_med.max())} for setups started with more than an hour left. On that comparison the handover itself costs "
             f"{d1(cf_start['hours_per_week'])} brake hours a week. {T.see('released')}</p>")
    b.append(f"<p>Three levers release {d1(S.LEVERS)} brake hours a week, {pct(S.LEVERS / MH_WEEK)} of brake machine time: the top {SA.TOP_N} part-operations run at "
             f"standard ({d1(ST['top_hours_per_week'])} hours a week), repeat setups assigned to an operator who has set the part up before "
             f"({d1(ANY['hours_released_per_week'])}), and a shift-handover standard at the brakes, the operator who starts a setup finishing it or leaving a written "
             f"handover at the machine ({d1(cf_start['hours_per_week'])}). {link('options')} carries these hours as the setup program.</p>")

    # 4 ── run standards
    b.append("<h2 id='f4'>4. Run Standards</h2>")
    POP, gap = S.POP, S.SRAT["run_gap"]
    b.append(f"<p>{newer} run at {d2(S.LF[S.NEWER].mean())} of the run standard and L1 at {d2(S.LF['L1'])}; every other work center runs at "
             f"{d2(other_run.min())} to {d2(other_run.max())}. {n0(POP['stale_parts'])} of {n0(POP['active_parts_with_routing'])} active parts "
             f"({pct(POP['stale_share'], 0)}) carry a stale standard (one dated at the part's first quote) and run {pct(gap.min(), 0)} to {pct(gap.max(), 0)} further "
             f"above standard than refreshed parts at the same work center. {T.see('run', 'stale')}</p>")
    b.append(titled(S.fig_run(), "Run Actual Over Standard by Work Center"))
    swc = S.SWC.set_index("work_center")
    sall, lall = S.SRC.set_index("routing_class").loc["all"], S.LRC.set_index("routing_class").loc["all"]
    b.append(f"<p>With the stale standards refreshed, planned hours rise {pct(swc.loc['press_brake', 'change'])} at the brakes and "
             f"{pct(swc['change'].min())} to {pct(swc['change'].max())} elsewhere; standard hours per job rise {pct(sall['change_stale_jobs'], 0)} on jobs for those parts "
             f"({pct(sall['jobs_on_stale_parts'] / sall['jobs'], 0)} of jobs) and {pct(sall['change_all_jobs'])} overall. With the {newer} run standards set "
             f"to measured, planned laser hours fall {pct(-S.LWC['change'].iloc[1])} and standard hours per job fall {pct(-lall['change_laser'])}. Both together move "
             f"standard hours per job by {S.sp(lall['change_both'])}. The {n0(POP['stale_parts'])} stale standards should be refreshed and the {newer} run standards "
             f"set to measured, with the effect on standard hours per job going to estimating ({link('quoting')}). {T.see('planned', 'quoted')}</p>")

    b.append("<h2 id='appendix'>Appendix</h2>")
    b.append(T.appendix())
    toc = [("f1", "1. Capacity Across the Shop"), ("f2", "2. Load, Queue Time and WIP"), ("f3", "3. Setups Against Standard"), ("f4", "4. Run Standards")]
    print(f"wrote {page('capacity', chr(10).join(b), toc)}: 4 sections, {len(T.order)} appendix tables")
    return T.order


def main():
    build()


if __name__ == "__main__":
    main()
