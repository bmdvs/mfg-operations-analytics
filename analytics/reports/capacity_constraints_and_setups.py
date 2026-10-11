"""Capacity, constraints and setups: the report.

Usage: python -m analytics.reports.capacity_constraints_and_setups
"""
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

from analytics.constraint import analysis as CA
from analytics.constraint import screen as SC
from analytics.constraint import sections as C
from analytics.db import q
from analytics.reports.layout import Tables, block, chart, join_and, link, page, titled
from analytics.setups import analysis as SA
from analytics.setups import sections as S
from analytics.style.style import ACCENT, AMBER, BRAND_BLUE, GREY, LIGHT_BLUE, RED, fig, paired_columns, pct, save_conformed as save, sig, table

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
HALL = SC.hot_weeks_all(X)
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
ACTIVITY = pd.DataFrame({"operations": X["ops"].groupby("work_center").size(), "hours": C.UY["machine"], "machines": C.UY["machines"]})
ACTIVITY["ops_per_week"] = ACTIVITY["operations"] / SA.WEEKS
ACTIVITY["ops_per_machine_week"] = ACTIVITY["ops_per_week"] / ACTIVITY["machines"]
ACTIVITY["weekdays"] = X["uw"][X["uw"]["week_year"] == YEAR].groupby("work_center")["weekdays"].sum()
ACTIVITY["ops_per_machine_day"] = ACTIVITY["operations"] / ACTIVITY["machines"] / ACTIVITY["weekdays"]
ACTIVITY["ops_per_day"] = ACTIVITY["operations"] / ACTIVITY["weekdays"]
ACTIVITY["hours_per_operation"] = ACTIVITY["hours"] / ACTIVITY["operations"]
QUEUE_AXIS = "Queue time, working days per operation"
P = lambda x: pct(x, 0)


def note(text):
    return f"<div class='caption'>{text}</div>"


LEAD_TWO = ["press_brake", "robotic_weld"]                                # drawn in the darker blue wherever work centers are compared
shade = lambda w: BRAND_BLUE if w in LEAD_TWO else LIGHT_BLUE
QUARTERLY = (X["uw"].assign(quarter=lambda d: d["week_year"].astype(int).astype(str) + " Q" + d["week_quarter"].astype(int).astype(str))
             .groupby(["quarter", "work_center"])[["machine_hours", "scheduled_hours", "downtime_hours"]].sum()
             .pipe(lambda g: g["machine_hours"] / (g["scheduled_hours"] - g["downtime_hours"])).unstack())
QDAYS = q("select work_center, operations, queue_days, share_of_queue from marts.mart_queue_by_work_center where period = 'year' order by queue_days desc").set_index("work_center")


TREND_COLORS = ["#A8C0D1", "#E3B98A", "#A9CDB3", "#C9B3D6", "#E0A8A8", "#D8CFA0", "#9FD0CF", "#C4C4C4"]          # light, one for each of the other work centers


WELD_CELL = "#9A5B0E"                      # the robotic weld cell's line: dark, and apart from the brakes' blue


def darker(color, by=0.62):
    r, g, b_ = (int(color[k:k + 2], 16) for k in (1, 3, 5))
    return "#{:02X}{:02X}{:02X}".format(int(r * by), int(g * by), int(b_ * by))


def fig_activity():
    """Operations a working day at the work center (left axis) and machine hours per operation (right axis), work centers in routing order."""
    d = ACTIVITY.loc[ROUTING]
    x = np.arange(len(d))
    f, ax = fig(h=4.0)
    ax2 = ax.twinx()
    ops, hrs = sig(d["ops_per_day"].to_numpy(dtype=float)), sig(d["hours_per_operation"].to_numpy(dtype=float))
    ax.bar(x - 0.2, ops, width=0.38, color=LIGHT_BLUE, label="Operations per day (left)")
    ax2.bar(x + 0.2, hrs, width=0.38, color=BRAND_BLUE, label="Machine hours per operation (right)")
    for xi, vi in zip(x, ops):
        ax.text(xi - 0.2, vi, f"{vi:.1f}", ha="center", va="bottom", fontsize=8)
    for xi, vi in zip(x, hrs):
        ax2.text(xi + 0.2, vi, f"{vi:.2f}" if vi < 1 else f"{vi:.1f}", ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{WC[w]} ({int(d.loc[w, 'machines'])}{' machines' if w == 'laser' else ''})" for w in d.index], rotation=25, ha="right")
    ax.set_ylabel("Operations per day")
    ax2.set_ylabel("Machine hours per operation")
    ax.set_ylim(0, float(ops.max()) * 1.12)
    ax2.set_ylim(0, float(hrs.max()) * 1.12)
    ax2.grid(False)
    ax2.spines["top"].set_visible(False)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    f.legend(h1 + h2, l1 + l2, frameon=False, fontsize=9, ncol=2, loc="lower center")
    f.tight_layout(rect=(0, 0.06, 1, 1))
    return save(f, "capacity_floor_activity", f"Daily Floor Activity by Work Center, {YEAR}")


def fig_utilization_trend():
    """Monthly utilization for each work center as a three-month trailing average, each line named beside the plot where it ends."""
    w = X["uw"].assign(month=lambda d: (d["week_start"] + pd.Timedelta(days=3)).dt.to_period("M"))
    g = w.groupby(["month", "work_center"])[["machine_hours", "scheduled_hours", "downtime_hours"]].sum().unstack()
    # hours pooled over the month and the two before it, so each point is the utilization of a quarter-long window ending in that month
    r = g.rolling(3, min_periods=1).sum()                # the first two months of the record stand on the months there are
    d = (r["machine_hours"] / (r["scheduled_hours"] - r["downtime_hours"]) * 100)
    d = d[d.index >= pd.Period("2023-01")].dropna()
    x = np.arange(len(d))
    f, ax = fig(h=3.9)
    others = [c for c in C.UY.sort_values("utilization", ascending=False).index if c not in LEAD_TWO]
    color = dict(zip(others, TREND_COLORS), press_brake=BRAND_BLUE, robotic_weld=WELD_CELL)
    for c in others + LEAD_TWO:
        ax.plot(x, sig(d[c].to_numpy(dtype=float)), color=color[c], linewidth=2.4 if c in LEAD_TWO else 1.6, zorder=3 if c in LEAD_TWO else 2)
    ax.set_xlim(-0.6, x[-1] + 0.4)
    ax.set_ylim(30, 100)
    # the names sit to the right of the plot area, clear of the gridlines, moved apart where two lines end close together
    ends = d.iloc[-1].sort_values()
    placed, gap = [], 3.6
    for c, v in ends.items():
        y = float(v) if not placed else max(float(v), placed[-1] + gap)
        placed.append(y)
        ax.text(x[-1] + 0.9, y, f"{WC[c]}, {v:.0f}%", ha="left", va="center", fontsize=8.5, color=color[c] if c in LEAD_TWO else darker(color[c]),
                fontweight="bold" if c in LEAD_TWO else None, clip_on=False)
    ticks = [k for k in x if d.index[k].month in (1, 7)] + [int(x[-1])]
    ax.set_xticks(ticks)
    ax.set_xticklabels([d.index[k].strftime("%b %Y") for k in ticks])
    ax.yaxis.set_major_formatter(lambda t, _: f"{t:.0f}%")
    f.subplots_adjust(left=0.07, right=0.80, top=0.97, bottom=0.12)
    return save(f, "capacity_utilization_trend", "Average monthly utilization by work center, 2023 to 2025")


def fig_hot_share():
    d = (HY["hot_weeks"] / HY["weeks"]).sort_values(ascending=False)
    x = np.arange(len(d))
    v = sig(d.to_numpy(dtype=float) * 100)
    f, ax = fig(h=3.5)
    ax.bar(x, v, width=0.62, color=[shade(w) for w in d.index])
    for xi, vi in zip(x, v):
        ax.text(xi, vi, f"{vi:.0f}%", ha="center", va="bottom", fontsize=8.5)
    ax.set_xticks(x)
    ax.set_xticklabels([WC[w] for w in d.index], rotation=20, ha="right")
    ax.set_ylim(0, float(v.max()) * 1.12)
    ax.yaxis.set_major_formatter(lambda t, _: f"{t:.0f}%")
    f.tight_layout()
    return save(f, "capacity_hot_week_share", f"Share of weeks at or above 95% utilization, {YEAR}")


def fig_hot_year():
    """Queue time in the weeks at or above 95% utilization against the other weeks of 2023 to 2025, for the work centers that had one."""
    d = HALL[HALL["hot_weeks"] > 0]
    f, ax = fig(h=3.8)
    paired_columns(ax, [WC[w] for w in d.index], list(d["queue_hot"]), list(d["queue_other"]), ("Weeks at or above 95%", "Other weeks"), decimals=2)
    ax.set_ylabel("Queue time in days")
    f.legend(*ax.get_legend_handles_labels(), frameon=False, fontsize=9, ncol=2, loc="lower center")
    f.tight_layout(rect=(0, 0.06, 1, 1))
    return save(f, "capacity_queue_in_hot_weeks_year", "Queue Time in Weeks at or Above 95% Utilization vs. Other Weeks, 2023 to 2025")


def fig_queue_days():
    d = QDAYS["share_of_queue"]
    x = np.arange(len(d))
    v = sig(d.to_numpy(dtype=float) * 100)
    f, ax = fig(h=3.5)
    ax.bar(x, v, width=0.62, color=[shade(w) for w in d.index])
    for xi, vi in zip(x, v):
        ax.text(xi, vi, f"{vi:.0f}%", ha="center", va="bottom", fontsize=8.5)
    ax.set_xticks(x)
    ax.set_xticklabels([WC[w] for w in d.index], rotation=20, ha="right")
    ax.set_ylim(0, float(v.max()) * 1.12)
    ax.yaxis.set_major_formatter(lambda t, _: f"{t:.0f}%")
    f.tight_layout()
    return save(f, "capacity_share_of_queue_days", f"Share of queue days by work center, {YEAR}")


def stepped(ax, wc, xmin):
    """The mean queue time of each utilization band as a horizontal segment across the band."""
    g = SC.band_means(X, wc)
    edges = [xmin, 80, 85, 90, 95, 101]
    first = True
    for (lo, hi), (_, r) in zip(zip(edges[:-1], edges[1:]), g.iterrows()):
        if r["weeks"] > 0 and hi > lo:
            ax.plot([lo, hi], [float(sig(r["queue"]))] * 2, color=AMBER, linewidth=2.4, solid_capstyle="butt", label="Mean by utilization band" if first else None)
            first = False


def weekly_points(ax, wc):
    w = SC.full_weeks(X, wc)
    old, cur = w[w["week_year"] != YEAR], w[w["week_year"] == YEAR]
    ax.scatter(sig(old["utilization"] * 100), sig(old["queue_mean"]), s=13, color=GREY, alpha=0.7, linewidths=0, label="Week, 2023 and 2024")
    ax.scatter(sig(cur["utilization"] * 100), sig(cur["queue_mean"]), s=15, color=ACCENT, linewidths=0, label=f"Week, {YEAR}")
    return w


def machines_of(wc):
    m = int(C.FITS.set_index("work_center").loc[wc, "machines"])
    return m, f"{m} machine{'s' if m > 1 else ''}"


def curve_title(wc):
    return f"Queue Time Against Utilization: {WC[wc]} ({machines_of(wc)[1]}), 2023 to 2025"


def fig_curve(wc):
    """One work center's weekly record, its band means and its fitted curve over the range it was fitted on."""
    r = C.FITS.set_index("work_center").loc[wc]
    m, k, lo, hi = int(r["machines"]), float(r["k"]), float(r["u_min"]), float(r["u_max"])
    f, ax = fig(h=4.3)
    w = weekly_points(ax, wc)
    xmin = float(np.floor(w["utilization"].min() * 10) * 10)
    stepped(ax, wc, xmin)
    u = np.linspace(lo, hi, 160)
    ax.plot(u * 100, sig(k * CA.vut_factor(u, m)), color=BRAND_BLUE, linewidth=2.2, label="Curve fitted on 13-week windows")
    for at in CA.QUEUE_AT:
        if lo <= at <= hi:
            y = float(sig(k * float(CA.vut_factor(at, m))))
            ax.plot([at * 100], [y], marker="o", color=RED, markersize=6)
            ax.annotate(f"{y:.2f}", (at * 100, y), textcoords="offset points", xytext=(-26, 6), fontsize=9, color=RED)
    top = float(w["queue_mean"].max()) * 1.06
    ax.text(0.015, 0.97, f"Fit on 13-week windows: R² {r['r2']:.2f}, rank correlation {r['rank_correlation']:.2f}\n"
                         f"On the curve: {r['queue_at_0.85']:.1f} days at 85%, {r['queue_at_0.90']:.1f} at 90%\n"
                         f"{YEAR}: {C.PY.loc[wc, 'queue_measured']:.1f} days measured, {C.PY.loc[wc, 'queue_on_curve']:.1f} on the curve",
            transform=ax.transAxes, ha="left", va="top", fontsize=8.5, linespacing=1.5, bbox=dict(facecolor="white", edgecolor="#DDDDDD", boxstyle="round,pad=0.4"))
    ax.set_xlim(xmin, 101)
    ax.set_ylim(0, top)
    ax.xaxis.set_major_formatter(lambda t, _: f"{t:.0f}%")
    ax.set_xlabel("Utilization")
    ax.set_ylabel(QUEUE_AXIS)
    f.legend(*ax.get_legend_handles_labels(), frameon=False, fontsize=9, ncol=4, loc="lower center")
    f.tight_layout(rect=(0, 0.06, 1, 1))
    return save(f, f"capacity_queue_curve_{wc}", curve_title(wc))


SETS = {"press_brake": "Load, sustained", "robotic_weld": "Load, sustained", "assembly": "Load, at full capacity only", "weld": "Load, at full capacity only",
        "punch": "Load, at full capacity only", "laser": "Load, at full capacity only", "grind_deburr": "Dispatch list", "inspection_pack": "Dispatch list",
        "hardware": "Dispatch list", "powder_coat": "Color schedule"}
SET_COLOR = {"Load, sustained": BRAND_BLUE, "Load, at full capacity only": ACCENT, "Dispatch list": AMBER, "Color schedule": GREY}
FIRST_OPS = SC.first_operation_queue_days(X)
ALL_QDAYS = pd.concat([QDAYS["queue_days"], FIRST_OPS]).sort_values()


def fig_queue_days_by_kind():
    """Queue days at every work center, each bar in the colour of what sets its wait; shares are of the queue days after the first operation."""
    d = ALL_QDAYS
    y = np.arange(len(d))
    f, ax = fig(h=4.2, grid="x")
    ax.barh(y, sig(d.to_numpy(dtype=float)), height=0.62, color=[SET_COLOR[SETS[w]] for w in d.index])
    total = float(QDAYS["queue_days"].sum())
    for yi, (w, v) in zip(y, d.items()):
        label = f"{v:,.0f} ({v / total * 100:.0f}%)" if w in QDAYS.index else f"{v:,.0f} (first operation)"
        ax.text(v + float(d.max()) * 0.012, yi, label, ha="left", va="center", fontsize=8.5)
    ax.set_yticks(y)
    ax.set_yticklabels([WC[w] for w in d.index])
    ax.set_xlim(0, float(d.max()) * 1.2)
    ax.set_xlabel(f"Queue days, {YEAR}")
    kinds = list(SET_COLOR)
    f.legend([Patch(color=SET_COLOR[k]) for k in kinds], kinds, frameon=False, fontsize=9, ncol=4, loc="lower center")
    f.tight_layout(rect=(0, 0.06, 1, 1))
    return save(f, "capacity_queue_days_by_kind", f"Queue Days by Work Center and What Sets the Wait, {YEAR}")


def fig_levers():
    """Brake hours a week: the setup overrun, and what each measured lever releases of it."""
    cf = S.HCF.iloc[1]
    rows = [("Brake setup overrun", float(S.ST["brake_overrun_per_week"]), LIGHT_BLUE), ("Top 12 part-operations at standard", float(S.ST["top_hours_per_week"]), BRAND_BLUE),
            ("Repeat setups to a familiar operator", float(S.ASG_ANY["hours_released_per_week"]), BRAND_BLUE),
            ("Shift-handover standard", float(cf["hours_per_week"]), BRAND_BLUE), ("The three together", float(S.LEVERS), BRAND_BLUE)][::-1]
    y = np.arange(len(rows))
    v = sig(np.array([r[1] for r in rows]))
    f, ax = fig(h=3.0, grid="x")
    ax.barh(y, v, height=0.6, color=[r[2] for r in rows])
    for yi, (name, val, _) in zip(y, rows):
        ax.text(val + float(v.max()) * 0.012, yi, f"{val:.0f}" if name == "Brake setup overrun" else f"{val:.1f}", ha="left", va="center", fontsize=8.5)
    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows])
    ax.set_xlim(0, float(v.max()) * 1.1)
    ax.set_xlabel("Brake hours a week")
    f.tight_layout()
    return save(f, "capacity_brake_hours_by_lever", f"Brake Hours a Week Released by Setup Lever, {YEAR}")


PEAK, PEAK_RATIO, SATURDAY_HOURS = SC.peak(X)


def fig_peak():
    """Brake standard hours released each week against crewed brake capacity, with the Saturday and extended hours worked added."""
    d = PEAK
    f, ax = fig(h=3.9)
    ax.bar(d["week_start"], sig(d["released"].to_numpy(dtype=float)), width=5, color=LIGHT_BLUE, label="Brake standard hours released")
    ax.plot(d["week_start"], sig(d["capacity"].to_numpy(dtype=float)), color=BRAND_BLUE, linewidth=2.0, label="Crewed brake capacity net of downtime")
    ax.plot(d["week_start"], sig(d["capacity_with_extra"].to_numpy(dtype=float)), color=AMBER, linewidth=1.8, linestyle="--",
            label="With Saturday and extended hours worked")
    b_ = d[d["build"]]
    ax.axvspan(b_["week_start"].min() - pd.Timedelta(days=3.5), b_["week_start"].max() + pd.Timedelta(days=3.5), color="#EFEFEF", zorder=0)
    ax.set_ylabel("Standard hours a week")
    ax.set_ylim(0, float(d["released"].max()) * 1.12)
    f.legend(*ax.get_legend_handles_labels(), frameon=False, fontsize=9, ncol=3, loc="lower center")
    f.tight_layout(rect=(0, 0.06, 1, 1))
    return save(f, "capacity_brake_hours_released", "Brake Hours Released Against Capacity by Week, Q4 2024 to Q1 2025")


def t_qdays():
    total = float(QDAYS["queue_days"].sum())
    rows = [[WC[w], SETS[w], n0(r["operations"]), n0(r["queue_days"]), pct(r["queue_days"] / total, 0)] for w, r in QDAYS.iterrows()]
    rows.append(["All", "", n0(QDAYS["operations"].sum()), n0(total), "100%"])
    a = table(pd.DataFrame(rows, columns=["Work center", "What sets the wait", "Operations after the first", "Queue days", "Share"]))
    rows = [[WC[w], SETS[w], n0(v)] for w, v in FIRST_OPS.sort_values(ascending=False).items()]
    return a + block("First operations, outside the count above", table(pd.DataFrame(rows, columns=["Work center", "What sets the wait", "First-operation queue days"])))


def t_peak():
    d = PEAK[PEAK["build"]]
    rows = [[r.week_start.strftime("%Y-%m-%d"), n0(r.weekdays), n0(r.released), n0(r.capacity), n0(r.released - r.capacity), n0(r.saturday_shifts), n0(r.extended_hours),
             n0(r.extra_hours)] for r in d.itertuples()]
    rows.append(["A week, on average", "", n0(d["released"].mean()), n0(d["capacity"].mean()), n0((d["released"] - d["capacity"]).mean()),
                 n0(d["saturday_shifts"].sum()) + " in all", n0(d["extended_hours"].sum()) + " in all", n0(d["extra_hours"].sum()) + " in all"])
    return table(pd.DataFrame(rows, columns=["Week starting", "Working weekdays", "Brake standard hours released", "Crewed capacity net of downtime, standard hours",
                                             "Shortfall", "Saturday brake shifts", "Extended hours", "Saturday and extended machine hours"]))


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


# ── the new appendix tables ─────────────────────────────────────────────────
def blank(v, f=d2):
    return f(v) if v == v else ""


def t_bands():
    """Queue time by utilization band for every work center, the brakes first, with the manual weld bays split at 85%."""
    rows = []
    for wc in ["press_brake"] + [w for w in C.UY.sort_values("utilization", ascending=False).index if w != "press_brake"]:
        for band, r in SC.band_means(X, wc).iterrows():
            if r["weeks"] > 0:
                rows.append([WC[wc], band, n0(r["weeks"]), d2(r["queue"]), d2(r["median"])])
    a = table(pd.DataFrame(rows, columns=["Work center", "Utilization in the week", "Weeks", "Queue time, mean of weeks", "Median"]))
    s = SC.band_split(X, "weld")
    n, of = SC.weld_weeks_above(X)
    b_ = table(pd.DataFrame([["Below 85%", n0(s["weeks_below"]), d2(s["below"])], ["At or above 85%", n0(s["weeks_above"]), d2(s["above"])],
                             [f"Weeks of {YEAR} at or above 85%", f"{n} of {of}", ""]], columns=["Manual weld", "Weeks", "Queue time, mean of weeks"]))
    return a + block("Manual weld, split at 85% utilization, full weeks 2023 to 2025", b_)


def t_hot():
    out = ""
    for per, H in ((f"{YEAR}", HY), (f"{YEAR} {REST}", HR)):
        rows = [[WC[w], P(r["utilization"]), f"{int(r['hot_weeks'])} of {int(r['weeks'])}", n0(r["hot_full_weeks"]), blank(r["queue_hot"]), d2(r["queue_other"]),
                 blank(r["wip_hot"], d1), d1(r["wip_other"]), pct(r["hours_share_hot"], 0)] for w, r in H.sort_values("utilization", ascending=False).iterrows()]
        out += block(per, table(pd.DataFrame(rows, columns=["Work center", "Utilization", "Weeks at or above 95%", "Of which full five-day weeks",
                                                             "Queue time in those weeks", "Queue time in the other weeks", "Jobs at the work center in those weeks, daily mean",
                                                             "Jobs at the work center in the other weeks, daily mean", "Share of machine hours in those weeks"])))
    rows = [[WC[w], f"{int(r['hot_weeks'])} of {int(r['weeks'])}", blank(r["queue_hot"]), d2(r["queue_other"])] for w, r in HALL.iterrows()]
    out += block("2023 to 2025", table(pd.DataFrame(rows, columns=["Work center", "Weeks at or above 95%", "Queue time in those weeks", "Queue time in the other weeks"])))
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
    T.add("bins", "Weekly queue time by utilization band and work center, full weeks 2023 to 2025", t_bands())
    T.add("fits", "Fitted queue time curve by work center", C.t_fits())
    T.add("dispatch", "The dispatch-list work centers: start day, queue time and hour of arrival", t_dispatch())
    T.add("powder", "The powder line by color", t_powder())
    T.add("qdays", f"Queue days by work center and what sets the wait, {YEAR}", t_qdays())
    T.add("peak", "Brake standard hours released against crewed brake capacity, the six weeks from November 11, 2024", t_peak())
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
    b.append(f"<p>The shop's floor consists of {n0(act['machines'].sum())} machines across ten work centers. The daily floor activity (operations per day and hours "
             f"per operation) in routing order is shown below.</p>")
    b.append(chart(f"Daily Floor Activity by Work Center, {YEAR}", fig_activity()))
    all_years = X["uw"][X["uw"]["week_year"].between(YEAR - 2, YEAR)]
    avg = {w: SC.pooled_utilization(all_years[all_years["work_center"] == w]) for w in UY.index}
    assert sorted(avg, key=avg.get, reverse=True)[:2] == LEAD_TWO
    shop = {y: SC.pooled_utilization(X["uw"][X["uw"]["week_year"] == y]) for y in (YEAR - 2, YEAR)}
    rel = q("select year(quarter_start) as y, sum(releases) as releases, sum(brake_std_hours) as brake_hours "
                                           "from marts.mart_releases_by_quarter group by 1 order by 1").set_index("y")
    b.append(f"<p>The press brakes consistently run at the highest utilization of any work center (average of {P(avg['press_brake'])} 2023-2025), followed by the "
             f"robotic weld cell ({P(avg['robotic_weld'])}). Released work grew {P(rel.loc[YEAR, 'releases'] / rel.loc[YEAR - 2, 'releases'] - 1)} from {YEAR - 2} to "
             f"{YEAR} ({n0(rel.loc[YEAR - 2, 'releases'])} to {n0(rel.loc[YEAR, 'releases'])} jobs a year; brake standard hours up "
             f"{P(rel.loc[YEAR, 'brake_hours'] / rel.loc[YEAR - 2, 'brake_hours'] - 1)}) across the same set of machines and shifts, resulting in average machine "
             f"utilization increasing {(shop[YEAR] - shop[YEAR - 2]) * 100:.0f} points over the past three years, from {P(shop[YEAR - 2])} in {YEAR - 2} to "
             f"{P(shop[YEAR])} in {YEAR}.</p>")
    b.append(chart("Average monthly utilization by work center, 2023 to 2025", fig_utilization_trend()))

    b.append("<h3 id='f1_1'>Capacity Constraints</h3>")
    gap = round(UY["uptime"] * 100) - round(UY["utilization"] * 100)
    assert list(gap.sort_values().index[:2]) == LEAD_TWO and P(UY.loc["press_brake", "uptime"]) == P(UY.loc["robotic_weld", "uptime"])
    b.append(f"<p>In {YEAR}, the press brakes ran at {P(UY.loc['press_brake', 'utilization'])} average utilization and the robotic weld cell at "
             f"{P(UY.loc['robotic_weld', 'utilization'])}. Against their {P(UY.loc['press_brake', 'uptime'])} uptime, the average production capacity buffer was only "
             f"{gap['press_brake']:.0f} points for the press brakes and {gap['robotic_weld']:.0f} points for the robotic weld cell, the smallest of all work centers. "
             f"{T.see('util')}</p>")
    b.append(titled(C.fig_util(), "Utilization and Machine Uptime by Work Center"))
    hot_share = (HY["hot_weeks"] / HY["weeks"]).sort_values(ascending=False)
    assert list(hot_share.index[:2]) == LEAD_TWO and hot_share.iloc[1] > 1.5 * hot_share.iloc[2]
    b.append(f"<p>With so little buffer, an ordinary heavy week can take the brakes and the weld cell to maximum utilization: they ran at or above 95% utilization in "
             f"{P(hot_share['press_brake'])} and {P(hot_share['robotic_weld'])} of weeks in {YEAR}, far more often than any other work center. {T.see('hot')}</p>")
    b.append(chart(f"Share of weeks at or above 95% utilization, {YEAR}", fig_hot_share()))
    assert QDAYS.index[0] == "press_brake" and QDAYS.loc["robotic_weld", "share_of_queue"] < 0.05 and QDAYS.loc["press_brake", "share_of_queue"] > 0.5
    total_ops = len(ops)
    b.append(f"<p>Throughout {YEAR}, jobs spent {n0(QDAYS['queue_days'].sum())} days waiting in queue at a work center (first operations at the lasers and the "
             f"punch aside). The press brake station accounted for {P(QDAYS.loc['press_brake', 'share_of_queue'])} of those days, which is a function of its "
             f"consistently high utilization, as well as its volume of operations. There were {n0(QDAYS.loc['press_brake', 'operations'])} press brake operations in "
             f"{YEAR}, {P(QDAYS.loc['press_brake', 'operations'] / total_ops)} of total across all work centers. The robotic weld cell, which saw similar high "
             f"utilization and queue times as the press brakes, accounted for less than 5% of queue days, because only "
             f"{n0(QDAYS.loc['robotic_weld', 'operations'])} operations, {pct(QDAYS.loc['robotic_weld', 'operations'] / total_ops)} of the total, passed through "
             f"it.</p>")
    b.append(chart(f"Share of queue days by work center, {YEAR}", fig_queue_days()))
    b.append("<p>The press brakes are therefore the shop's primary constraint on three counts: the highest utilization with the least buffer, the most weeks spent at "
             "maximum utilization, and more than half of all queue days. The robotic weld cell shares the first two and constrains the enclosure work that crosses "
             "it. The next section examines these stations in more detail.</p>")

    # 2 ── load and queue time
    b.append("<h2 id='f2'>2. Load and Queue Time</h2>")
    fits = C.FITS.set_index("work_center")
    at90 = fits["queue_at_0.90"]
    hall = HALL[HALL["hot_weeks"] > 0]
    rise = hall["queue_hot"] / hall["queue_other"]
    assert (rise > 1.3).all() and rise.idxmin() == "press_brake"
    rest_of = X["uw"][X["uw"]["utilization"] < SC.HOT]
    other_load = {w: SC.pooled_utilization(rest_of[rest_of["work_center"] == w]) for w in hall.index}
    assert max(other_load, key=other_load.get) == "press_brake"
    b.append(f"<p>At each station, average queue time was sharply higher when it was operating near maximum utilization compared to the other weeks of the year. The "
             f"gap is smallest at the press brakes ({d1(hall.loc['press_brake', 'queue_hot'])} days against {d1(hall.loc['press_brake', 'queue_other'])}, "
             f"{rise['press_brake']:.1f}x) not because their wait is least sensitive to load but because their other weeks are also heavily loaded, so the comparison "
             f"is narrower than other work centers. This section lays out the sensitivity of queue time against load at the press brakes and robotic "
             f"weld stations.</p>")
    b.append(chart("Queue Time in Weeks at or Above 95% Utilization vs. Other Weeks, 2023 to 2025", fig_hot_year()))
    b.append(f"<p><a href='#f1'>Section 1</a> showed that queue time rises when a work center is full and that the press brakes and the robotic weld cell are the two "
             f"that are full most often and carry the waiting that costs the shop days. This section shows how queue time builds at each as load rises, and what that "
             f"makes the lever. The curve is the queue time expected at each level of utilization for the number of machines at the work center, fitted on rolling "
             f"13-week windows from 2023 to 2025 and drawn only over the range of utilization the work center has run at in those windows; for the brakes the fit "
             f"explains {P(FB['r2'])} of the variation in the windowed queue with a rank correlation of {d2(FB['rank_correlation'])}, while a single week's queue "
             f"carries the backlog of the weeks before it, which is why the fit is made on windows rather than weeks.</p>")

    b.append("<h3 id='f2_1'>The press brakes</h3>")
    lo = C.BINS.iloc[:2]
    below = float((lo["queue_mean"] * lo["weeks"]).sum() / lo["weeks"].sum())
    step = float(C.BINS.iloc[2]["queue_mean"])
    BQ = C.BQ
    b.append(f"<p>On the fitted curve the brake queue time is {d2(FB['queue_at_0.75'])} days per operation at 75% utilization, {d2(FB['queue_at_0.85'])} at 85%, "
             f"{d2(FB['queue_at_0.90'])} at 90% and {d2(FB['queue_at_0.92'])} at 92%; the measured queue time is {d2(PY.loc['press_brake', 'queue_measured'])} at "
             f"{P(PY.loc['press_brake', 'utilization'])} for the year and {d2(PR.loc['press_brake', 'queue_measured'])} at {P(PR.loc['press_brake', 'utilization'])} "
             f"in {REST}. Week by week, the brake queue time steps from about {d1(below)} days below 85% utilization to {d1(step)} above it and does not settle "
             f"back. The brake queue time's 90th percentile was {d1(BQ.loc[1, 'queue_p90'])} and {d1(BQ.loc[2, 'queue_p90'])} days in Q1 and Q2 {YEAR} and "
             f"{d1(BQ.loc[3, 'queue_p90'])} and {d1(BQ.loc[4, 'queue_p90'])} in Q3 and Q4; under 5 days in every quarter is the mark the levers in this report are "
             f"measured against. {T.see('bins', 'fits', 'pos')}</p>")
    b.append(chart(curve_title("press_brake"), fig_curve("press_brake")))
    tail = MY.loc[["B3", "B4", "B5"]]
    top_y = MY.loc[C.BRAKES, "utilization"].sort_values(ascending=False).index.tolist()
    u1 = lambda x: f"{x * 100:.1f}%"
    b.append(f"<p>The brakes run at {P(UY.loc['press_brake', 'utilization'])} and carry {P(QSHARE['press_brake'])} of all queue time ({link('lead')}). "
             f"B1 and B2 run at {u1(MY.loc['B1', 'utilization'])} and {u1(MY.loc['B2', 'utilization'])} for the year and "
             f"{u1(MR.loc['B1', 'utilization'])} and {u1(MR.loc['B2', 'utilization'])} in {REST}, with the shortest queue times of the five "
             f"(mean {d1(MY.loc['B1', 'queue_mean'])} and {d1(MY.loc['B2', 'queue_mean'])} days): precision work goes to them first and the hot list sends "
             f"expedited work to them. B3 to B5 carry the tail: mean {rng(tail['queue_mean'].min(), tail['queue_mean'].max(), d1)} days and 90th percentile "
             f"{rng(tail['queue_p90'].min(), tail['queue_p90'].max(), d1)}. "
             + (f"Over all hours worked, {top_y[0]} carries the highest load of the five for the year; in {REST} B1 and B2 do. " if top_y[0] not in ("B1", "B2") else "")
             + f"On crewed weekday shifts only, B1 and B2 run at {u1(MY.loc['B1', 'utilization_weekday_basis'])} and {u1(MY.loc['B2', 'utilization_weekday_basis'])} "
             f"for the year. {T.see('machines', 'basis')}</p>")
    b.append(chart(f"Utilization and Queue Time by Brake, {YEAR}", fig_brakes()))
    SV, var = C.SV, C.var
    b.append(f"<p>The brake queue carries over from week to week because arrivals are uneven and run times vary: daily arrivals have a coefficient of variation of "
             f"{d2(var('Arrivals: jobs released per working day'))}, Mondays bring {d2(var('Arrivals: Monday'))} times the daily mean and the top customer's "
             f"month-end {d2(var('Arrivals: top customer'))} times, and run time per operation varies far more than setup time (coefficient of variation "
             f"{d2(var('Brake run time'))} against {d2(var('Brake setup time'))}). Second-shift absence is {P(var('Absence, second shift: share'))} against "
             f"{P(var('Absence, first shift: share'))} on first shift. {T.see('var', 'spread')}</p>")

    b.append("<h3 id='f2_2'>The robotic weld cell</h3>")
    ROB = C.ROB
    assert PR["queue_measured"].idxmax() == "robotic_weld" and at90["robotic_weld"] > at90["press_brake"]
    assert PY.loc["robotic_weld", "queue_measured"] > PY.loc["robotic_weld", "queue_on_curve"]
    rf = ROBOT_FAMILIES
    assert list(rf.index[:3]) == ["enclosure", "weldment", "chassis"]
    b.append(f"<p>The robotic weld cell runs at {P(UY.loc['robotic_weld', 'utilization'])} on one shift and has the longest queue time in the shop in {REST}, "
             f"{d1(ROB.loc[REST, 'queue_mean'])} days per operation against {d1(UR.loc['press_brake', 'queue_mean'])} at the brakes. As a single machine its wait "
             f"climbs faster with load than the brakes': {d1(at90['robotic_weld'])} days on the curve at 90% against {d1(at90['press_brake'])} at the five brakes. It "
             f"runs at or above 95% in {n0(ROBOT_BANDS.loc['at or above 95%', 'weeks'])} weeks of {n0(ROBOT_BANDS['weeks'].sum())} and below 80% in "
             f"{n0(ROBOT_BANDS.loc['below 80%', 'weeks'])}, alternating between idle and saturated weeks rather than running steadily hot, and in {YEAR} it ran above "
             f"its curve ({d2(PY.loc['robotic_weld', 'queue_measured'])} days measured against {d2(PY.loc['robotic_weld', 'queue_on_curve'])}).</p>")
    b.append(chart(curve_title("robotic_weld"), fig_curve("robotic_weld")))
    b.append(f"<p>Enclosures are {P(rf.loc['enclosure', 'share'])} of its hours, weldments {P(rf.loc['weldment', 'share'])} and chassis "
             f"{P(rf.loc['chassis', 'share'])}. Its setups run at {d2(ROBOT_STD['setup_ratio'])} of standard and its run time at {d2(ROBOT_STD['run_ratio'])}, so the "
             f"cell's queue is load, not standards. {T.see('robot')}</p>")

    b.append("<h3 id='f2_3'>The other work centers</h3>")
    held = QDAYS["share_of_queue"]
    stepc = ["assembly", "weld", "punch"]
    assert "punch" not in held.index                 # the punch is a first operation, outside the count of queue days
    rest_share = 1 - held["press_brake"] - held["robotic_weld"]
    b.append(f"<p>The other work centers hold {P(rest_share)} of queue days between them, and the wait at each is set in one of three ways. At grind and deburr, "
             f"inspection and pack and hardware ({P(held[SC.LIST_CENTERS].sum())} of queue days) the wait does not change with load; it is set by the daily dispatch "
             f"list. At assembly, the manual weld bays and the punch ({P(held['assembly'] + held['weld'])} of queue days at the first two; the punch is a first "
             f"operation and outside that count) the wait is flat until the machines are full and steps up only then ({T.plain('bins')}), which they reach in "
             f"{int(HY.loc['assembly', 'hot_weeks'])}, {int(HY.loc['weld', 'hot_weeks'])} and {int(HY.loc['punch', 'hot_weeks'])} weeks of {int(HY['weeks'].iloc[0])}; "
             f"the lasers behave the same way and reach full load only at the year-end build (Flow and On-time Delivery). At the powder line "
             f"({P(held['powder_coat'])} of queue days) the wait is the color schedule. {T.see('qdays', 'assembly', 'laser_weeks', 'lasers')}</p>")
    b.append(chart(f"Queue Days by Work Center and What Sets the Wait, {YEAR}", fig_queue_days_by_kind())
             + note(f"Shares are of the {n0(QDAYS['queue_days'].sum())} queue days after the first operation; the lasers' and the punch's first-operation queue days "
                    f"are shown beside them and are not in that total."))
    early, mid_day, late = HOURS.iloc[:3], HOURS.iloc[3:5], HOURS.iloc[5:]
    same = lambda g: float((g["same_day"] * g["arrivals"]).sum() / g["arrivals"].sum())
    assert 0.85 <= same(early) < 0.95 and 0.25 <= same(mid_day) < 0.35 and 0.45 <= mid_day["share"].sum() <= 0.55
    assert set(X["shifts"].set_index("work_center").loc[SC.LIST_CENTERS, "shifts"]) == {1}          # one shift at each, so no crew for a list at 14:00
    b.append(f"<p>At the three dispatch-list work centers, whether an operation starts the day it arrives depends on the hour of arrival and not on how busy the work "
             f"center is. Work arriving before 10:00 starts the same day nine times in ten; work arriving between 10:00 and 14:00, half of all arrivals, starts the "
             f"same day about three times in ten and otherwise waits for the next morning; the {P(late['share'].sum())} arriving after the shift ends always waits. "
             f"The brakes show no such break. These next-day starts add {d1(NEXT_DAY['year'])} working days of lead time to a shipped job ({d1(NEXT_DAY[REST])} in "
             f"{REST}). {T.see('dispatch')}</p>")
    b.append(chart(f"Same-Day Start by Hour of Arrival, Dispatch-List Work Centers Against the Brakes, {YEAR}", fig_same_day()))
    once = POWDER[POWDER["days_per_week"] <= 1.5]
    assert sorted(once.index) == ["beige", "blue", "red"]
    b.append(f"<p>The powder line's wait is {d2(POWDER_ALL['wait_mean'])} days per operation for the color day, {rng(once['wait_mean'].min(), once['wait_mean'].max(), d1)} "
             f"days for the three colors run once a week; a third day for black was tested in {link('options')} and does not move on-time delivery. "
             f"{T.see('powder')}</p>")

    # 3 ── brake hours
    b.append("<h2 id='f3'>3. Brake Hours: Setups, Standards and the Peak</h2>")
    b.append(f"<p>The brake queue is set by uneven arrivals and by load above 85%, so what matters at the brakes is hours: how many are lost to setups over standard "
             f"and how many of those can be recovered, whether the standards the schedule is planned on are right, how far released work exceeds brake capacity at "
             f"the year-end peak, and where a crewed shift is open. This section measures each from the record. {link('options')} takes these measured hours as inputs "
             f"and tests, on the shop model, what changing them does to on-time delivery, alongside release and dispatch rules. One measured quantity is set aside "
             f"here: halving the spread of setup time (each setup time moved halfway to the mean, the curve rescaled for the lower variability of setup and run) "
             f"releases {d1(C.SV.loc['year', 'hours_per_week_released'])} brake hours a week and cuts the queue time on the curve from "
             f"{d2(C.SV.loc['year', 'queue_on_curve'])} to {d2(C.SV.loc['year', 'queue_with_half_setup_spread'])} days. The mean setup time is a different matter, and "
             f"is where the hours are.</p>")
    b.append("<h3 id='f3_1'>Brake setups</h3>")
    ST, MH_WEEK = S.ST, S.MH_WEEK
    b.append(f"<p>{n0(len(S.D['s']))} setups at all work centers in {YEAR}, {n0(y['setups'])} of them at the brakes. A setup's ratio is its setup machine hours over "
             f"the setup standard on the job operation; hours over standard is total setup hours over total standard hours. Every work center except the brakes runs "
             f"its setups at a median of {rng(others_setup['median_ratio'].min(), others_setup['median_ratio'].max())} of standard and within "
             f"{n0(others_setup['overrun_hours'].max())} overrun hours for the year; the brakes ran {n0(y['setup_hours'])} hours against {n0(y['standard_hours'])} "
             f"standard, {n0(y['overrun_hours'])} over, {n0(ST['brake_overrun_per_week'])} a week, {pct(ST['brake_overrun_per_week'] / MH_WEEK, 0)} of brake machine "
             f"time. The median brake setup runs at {d2(y['median_ratio'])} of standard and the 90th percentile at {d2(y['p90_ratio'])}. Setup ratios do not move "
             f"with the 2024 year-end build: the median is {d2(S.OV.loc['Q1', 'median_ratio'])} in the first quarter and {d2(S.OV.loc[REST, 'median_ratio'])} in "
             f"{REST}. {T.see('bywc', 'period')}</p>")

    b.append("<p id='f3_1_1'><b>Where the overrun sits</b></p>")
    ho, nho, small, LOT, FML, FAM = S.HO.loc["Handed over at a shift boundary"], S.HO.loc["Not handed over"], S.LOT.loc["under 25"], S.LOT, S.FML, S.FAM
    bump = small["median_ratio"] / LOT.drop("under 25")["median_ratio"].mean() - 1
    b.append(f"<p>Setups handed over at a shift boundary (setup transactions by different operators one after the other across the 14:00 or 22:30 shift boundary; two operators at the same time is a two-person "
             f"setup, not a handover) are {pct(ho['share_of_setups'], 0)} of setups "
             f"and {pct(ho['share_of_overrun'], 0)} of the overrun hours, median {d2(ho['median_ratio'])} against {d2(nho['median_ratio'])}; most of those hours are "
             f"long setups that reached the boundary rather than the handover itself (<a href='#f3_1_4'>The setup reduction list and the handover</a>). Lots under 25 "
             f"are {pct(small['setups'] / y['setups'], 0)} of setups and {pct(ST['small_lot_overrun_share'], 0)} of the overrun, median {d2(small['median_ratio'])} "
             f"against {d2(LOT.loc['100 and over', 'median_ratio'])} to {d2(LOT.loc['25 to 99', 'median_ratio'])} on larger lots: the setup standards under-plan "
             f"small lots. First setups of a part by the operator run at {d2(FML.loc['none', 'median_ratio'])} against {d2(FML.loc['1 or 2', 'median_ratio'])}. "
             f"Enclosures and chassis run at {d2(FAM.loc['enclosure', 'median_ratio'])} and {d2(FAM.loc['chassis', 'median_ratio'])}; panels and brackets at "
             f"{d2(FAM.loc['panel', 'median_ratio'])} and {d2(FAM.loc['bracket', 'median_ratio'])}. {T.see('handover', 'lot', 'familiarity', 'family')}</p>")
    b.append(titled(S.fig_conditions(), "Brake Setup Overrun Hours by Condition"))
    b.append(f"<p>The setup standard on lots under 25 pieces should be raised by {pct(bump, 0)}, so the schedule and the quote stop under-planning them.</p>")

    b.append("<p id='f3_1_2'><b>Operator tenure and familiarity</b></p>")
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

    b.append("<p id='f3_1_3'><b>Grouping</b></p>")
    GRP = S.GRP
    ga, b12, b345 = GRP.loc["all brakes"], GRP.loc[["B1", "B2"], "share_grouped"], GRP.loc[["B3", "B4", "B5"], "share_grouped"]
    b.append(f"<p>{pct(ga['share_grouped'], 0)} of brake setups follow a job on the same tooling set and run at {d2(ga['ratio_grouped'])} of standard against "
             f"{d2(ga['ratio_not_grouped'])}, saving {d1(ga['hours_saved_per_week'])} hours a week. B1 and B2 group {pct(b12.min(), 0)} to {pct(b12.max(), 0)} of their "
             f"setups against {pct(b345.min(), 0)} to {pct(b345.max(), 0)} on B3 to B5: precision work and the hot list come first there. {T.see('grouping')}</p>")
    b.append(titled(S.fig_grouping(), "Same-tooling Grouping by Brake"))

    b.append("<p id='f3_1_4'><b>The setup reduction list and the handover</b></p>")
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
             f"handover at the machine ({d1(cf_start['hours_per_week'])}). The options report carries these hours as the setup program.</p>")
    b.append(chart(f"Brake Hours a Week Released by Setup Lever, {YEAR}", fig_levers()))

    b.append("<h3 id='f3_2'>Planning standards</h3>")
    POP, gap = S.POP, S.SRAT["run_gap"]
    b.append(f"<p>The standards the schedule and the quote are built on are wrong in two known directions. {newer} run at {d2(S.LF[S.NEWER].mean())} of the run standard and L1 at {d2(S.LF['L1'])}; every other work center runs at "
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

    b.append("<h3 id='f3_3'>The peak and the open shift</h3>")
    pk = PEAK[PEAK["build"]]
    assert len(pk) == 6
    a_, b2 = float(pk["released"].mean()), float(pk["capacity"].mean())
    assert a_ > b2
    g_ = SATURDAY_HOURS / PEAK_RATIO
    b.append(f"<p>The year-end build is a brake-hours gap. In the six weeks from November 11, 2024 the shop released {n0(a_)} brake standard hours a week against "
             f"{n0(b2)} hours of crewed brake capacity net of downtime (weekday shifts, in standard hours at the brakes' {d2(PEAK_RATIO)} actual-over-standard ratio "
             f"for 2024), a shortfall of {n0(a_ - b2)} hours a week that the queue absorbed; the shop ran {n0(pk['saturday_shifts'].sum())} queue-triggered Saturday "
             f"brake shifts and {n0(pk['extended_hours'].sum())} extended hours over the period, supplying {n0(pk['extra_hours'].sum() / PEAK_RATIO)} standard hours. "
             f"One Saturday brake shift on B1 and B2 supplies {n0(g_)} standard hours ({n0(SATURDAY_HOURS)} machine hours), {P(g_ / (a_ - b2))} of the weekly gap; "
             f"the options report tests a planned Saturday shift every week from November through February against the queue-triggered practice. "
             f"{T.see('peak')}</p>")
    b.append(chart("Brake Hours Released Against Capacity by Week, Q4 2024 to Q1 2025", fig_peak()))
    b.append(f"<p>The robotic weld cell runs one shift at {P(UY.loc['robotic_weld', 'utilization'])} utilization and is at or above 95% in "
             f"{int(HY.loc['robotic_weld', 'hot_weeks'])} weeks of {int(HY.loc['robotic_weld', 'weeks'])}; its second shift is uncrewed. The options report tests "
             f"and prices crewing it.</p>")

    b.append("<h3 id='f3_4'>The dispatch list</h3>")
    mid = SC.midday_wait(X)
    b.append(f"<p>At grind and deburr, inspection and pack and hardware the lever is the list, not capacity. A midday refresh of the day's dispatch list lets the "
             f"arrivals between 10:00 and 12:00, {P(HOURS.iloc[3]['share'])} of the total, start the same afternoon; what arrives after the shift ends can only start "
             f"the next morning" + (f". The gain is lead time rather than on-time delivery, up to {d1(mid)} of the {d1(NEXT_DAY['year'])} working days a shipped job "
                                    f"spends in next-day starts.</p>" if mid >= 0.3 else ".</p>"))

    b.append("<h2 id='appendix'>Appendix</h2>")
    b.append(T.appendix())
    toc = [("f1", "1. Capacity Across the Shop"), ("f2", "2. Load and Queue Time"), ("f3", "3. Brake Hours: Setups, Standards and the Peak")]
    print(f"wrote {page('capacity', chr(10).join(b), toc)}: 3 sections, {len(T.order)} appendix tables")
    return T.order


def main():
    build()


if __name__ == "__main__":
    main()
