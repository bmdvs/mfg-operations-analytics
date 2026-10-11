"""Capacity, constraints and setups: the report.

Usage: python -m analytics.reports.capacity_constraints_and_setups
"""
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
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
    d = HALL[(HALL["hot_weeks"] > 0) & (HALL.index != "hardware")]
    f, ax = fig(h=3.8)
    paired_columns(ax, [WC[w] for w in d.index], list(d["queue_hot"]), list(d["queue_other"]), ("Weeks at or above 95%", "Other weeks"), decimals=2)
    ax.set_ylabel("Queue time in days")
    f.legend(*ax.get_legend_handles_labels(), frameon=False, fontsize=9, ncol=2, loc="lower center")
    f.tight_layout(rect=(0, 0.06, 1, 1))
    return save(f, "capacity_queue_in_hot_weeks_year", "Queue Time in Weeks at or Above 95% Utilization vs. Other Weeks")


def fig_queue_days():
    d = (ALL_QDAYS / ALL_QDAYS.sum()).sort_values(ascending=False)
    x = np.arange(len(d))
    v = sig(d.to_numpy(dtype=float) * 100)
    f, ax = fig(h=3.5)
    ax.bar(x, v, width=0.62, color=[BRAND_BLUE if w == "press_brake" else LIGHT_BLUE for w in d.index])
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


LOAD = ["press_brake", "robotic_weld", "assembly", "weld", "laser", "punch"]
SCHEDULE = SC.LIST_CENTERS + ["powder_coat"]
DRIVER = {**{w: "Load-driven" for w in LOAD}, **{w: "Schedule-driven" for w in SCHEDULE}}
DRIVER_COLOR = {"Load-driven": BRAND_BLUE, "Schedule-driven": AMBER}
FIRST_OPS = SC.first_operation_queue_days(X)
ALL_QDAYS = pd.concat([QDAYS["queue_days"], FIRST_OPS]).sort_values()
ALL_SHARE = ALL_QDAYS / ALL_QDAYS.sum()               # the lasers and the punch on their first-operation queue
DIST = SC.queue_distribution(X)
BRAKE_DIST = SC.brake_distribution(X)
FIRST_OP_LABEL = {w: f"{WC[w]} (first operation)" for w in ("laser", "punch")}


def boxes(ax, d, colors):
    """A box for each row of d, the first row at the top: 25th to 75th percentile, the median inside it, whiskers to the 5th and 95th, the mean marked."""
    d = d.iloc[::-1]
    y = np.arange(len(d))
    v = {c: sig(d[c].to_numpy(dtype=float)) for c in ("median", "mean", "p5", "p25", "p75", "p95")}
    span = float(v["p95"].max())
    ax.hlines(y, v["p5"], v["p95"], color="#555555", linewidth=1.1, zorder=2)
    for xs in (v["p5"], v["p95"]):
        ax.vlines(xs, y - 0.14, y + 0.14, color="#555555", linewidth=1.1, zorder=2)
    ax.barh(y, v["p75"] - v["p25"], left=v["p25"], height=0.52, color=colors[::-1], zorder=3)
    ax.vlines(v["median"], y - 0.26, y + 0.26, color="white", linewidth=2.0, zorder=4)
    ax.plot(v["mean"], y, linestyle="none", marker="D", markersize=5.5, color="white", markeredgecolor="#222222", markeredgewidth=0.9, zorder=5)
    for yi, m_, p_ in zip(y, v["median"], v["p95"]):
        ax.text(m_, yi + 0.3, f"{m_:.2f}", ha="center", va="bottom", fontsize=8)
        ax.text(p_ + span * 0.012, yi, f"{p_:.1f}", ha="left", va="center", fontsize=8)
    ax.set_yticks(y)
    ax.set_xlim(0, span * 1.07)
    ax.set_ylim(-0.6, len(d) - 0.25)
    ax.set_xlabel("Working days per operation")
    return d


BOX_KEYS = [Line2D([], [], color="#999999", linewidth=5, marker="|", markersize=11, markeredgecolor="white", markeredgewidth=2.0),
            Line2D([], [], linestyle="none", marker="D", markersize=5.5, color="white", markeredgecolor="#222222", markeredgewidth=0.9),
            Line2D([], [], color="#555555", linewidth=1.1, marker="|", markersize=7)]
BOX_NAMES = ["Median", "Mean", "5th to 95th percentile"]


def fig_queue_distribution():
    """Queue time per operation by work center, each box in the colour of the work center's driver."""
    f, ax = fig(h=5.2, grid="x")
    d = boxes(ax, DIST, [DRIVER_COLOR[DRIVER[w]] for w in DIST.index])
    ax.set_yticklabels([FIRST_OP_LABEL.get(w, WC[w]) for w in d.index])
    f.legend([Patch(color=c) for c in DRIVER_COLOR.values()] + BOX_KEYS, list(DRIVER_COLOR) + BOX_NAMES, frameon=False, fontsize=8.5, ncol=5, loc="lower center")
    f.tight_layout(rect=(0, 0.06, 1, 1))
    return save(f, "capacity_queue_time_distribution", f"Queue Time per Operation by Work Center, {YEAR}")


def fig_brake_distribution():
    """Queue time per operation at each of the five brakes, with the brake's utilization for the year beside its name."""
    f, ax = fig(h=3.6, grid="x")
    d = boxes(ax, BRAKE_DIST, [BRAND_BLUE] * len(BRAKE_DIST))
    ax.set_yticklabels([f"{m}, {P(C.MY.loc[m, 'utilization'])}" for m in d.index])
    f.legend([Patch(color=BRAND_BLUE)] + BOX_KEYS, ["25th to 75th percentile"] + BOX_NAMES, frameon=False, fontsize=8.5, ncol=4, loc="lower center")
    f.tight_layout(rect=(0, 0.08, 1, 1))
    return save(f, "capacity_queue_time_by_brake", f"Queue Time per Operation by Brake, {YEAR}")


def pair_title(centers, first_operation=False):
    names = " and ".join(f"{WC[w]} ({machines_of(w)[1]})" for w in centers)
    return f"{'First-Operation ' if first_operation else ''}Queue Time Against Utilization: {names}, 2023 to 2025"


def fig_pair(centers, name, first_operation=False):
    """Two work centers on shared axes: the weekly record, the mean of each utilization band, and the fitted curve over the range it was fitted on."""
    f, axes = fig(h=4.4, ncols=2, sharex=True, sharey=True)
    record = {wc: SC.full_weeks(X, wc) for wc in centers}
    xmin = float(np.floor(min(w["utilization"].min() for w in record.values()) * 10) * 10)
    top = max(float(w["queue_mean"].max()) for w in record.values()) * 1.32          # room above the points for the box of figures
    for ax, wc in zip(axes, centers):
        r = C.FITS.set_index("work_center").loc[wc]
        m, k, lo, hi = int(r["machines"]), float(r["k"]), float(r["u_min"]), float(r["u_max"])
        weekly_points(ax, wc)
        stepped(ax, wc, xmin)
        u = np.linspace(lo, hi, 160)
        ax.plot(u * 100, sig(k * CA.vut_factor(u, m)), color=BRAND_BLUE, linewidth=2.2, label="Curve fitted on 13-week windows")
        for at in (0.85, 0.90):
            if lo <= at <= hi:
                y = float(sig(k * float(CA.vut_factor(at, m))))
                ax.plot([at * 100], [y], marker="o", color=RED, markersize=6)
                ax.annotate(f"{y:.2f}", (at * 100, y), textcoords="offset points", xytext=(-26, 6), fontsize=9, color=RED)
        g = SC.band_means(X, wc)["queue"]
        n, _ = SC.weeks_above(X, wc, 0.80)
        ax.set_title(f"{WC[wc]} ({machines_of(wc)[1]})", fontsize=10.5)
        ax.text(0.03, 0.97, f"Fit on 13-week windows: R² {r['r2']:.2f}, rank correlation {r['rank_correlation']:.2f}" + "\n"
                            f"Below 80%: {g.iloc[0]:.2f} days; 95% and above: {g.iloc[-1]:.2f} days" + "\n"
                            f"{n} weeks at or above 80% in {YEAR}",
                transform=ax.transAxes, ha="left", va="top", fontsize=7.8, linespacing=1.45, bbox=dict(facecolor="white", edgecolor="#DDDDDD", boxstyle="round,pad=0.35"))
        ax.set_xlim(xmin, 101)
        ax.set_ylim(0, top)
        ax.xaxis.set_major_formatter(lambda t, _: f"{t:.0f}%")
        ax.set_xlabel("Utilization")
    axes[0].set_ylabel("First-operation queue time," + "\n" + "working days per operation" if first_operation else QUEUE_AXIS, fontsize=10)
    f.legend(*axes[0].get_legend_handles_labels(), frameon=False, fontsize=9, ncol=4, loc="lower center")
    f.tight_layout(rect=(0, 0.07, 1, 1))
    return save(f, name, pair_title(centers, first_operation))


def fig_powder():
    """Mean wait for the color day by color, with the share of operations waiting a day or more on a second axis."""
    d = POWDER.sort_values("wait_mean")
    y = np.arange(len(d))
    v = sig(d["wait_mean"].to_numpy(dtype=float))
    once = (d["days_per_week"] <= 1.5).to_numpy()
    f, ax = fig(h=3.5, grid="x")
    ax.barh(y, v, height=0.6, color=[BRAND_BLUE if o else LIGHT_BLUE for o in once])
    for yi, vi, o in zip(y, v, once):
        ax.text(vi / 2, yi, f"{vi:.2f}", ha="center", va="center", fontsize=8.5, color="white" if o else "#222222")
    ax.set_yticks(y)
    week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    days = lambda t: ", ".join(sorted(t.split(", "), key=week.index))
    ax.set_yticklabels([f"{k.capitalize()} ({days(r['weekdays'])})" for k, r in d.iterrows()])
    span = float(v.max()) * 1.25
    ax.set_xlim(0, span)
    ax.set_xlabel("Mean wait for the color day, working days per operation")
    ax2 = ax.twiny()
    share = sig(d["day_or_more"].to_numpy(dtype=float) * 100)
    ax2.plot(share, y, linestyle="none", marker="D", markersize=7, color=AMBER)
    for yi, si, vi, o in zip(y, share, v, once):
        over_dark = o and (si + 8) / 100 * span < vi          # the label falls on a dark bar
        ax2.text(si + 2.0, yi, f"{si:.0f}%", ha="left", va="center", fontsize=8.5, color="white" if over_dark else "#8A5A10")
    ax2.set_xlim(0, 100)
    ax2.xaxis.set_major_formatter(lambda t, _: f"{t:.0f}%")
    ax2.set_xlabel("Share of operations waiting a day or more")
    ax2.grid(False)
    for sp in ("right",):
        ax2.spines[sp].set_visible(False)
    marker = Line2D([], [], linestyle="none", marker="D", markersize=7, color=AMBER)
    f.legend([Patch(color=BRAND_BLUE), Patch(color=LIGHT_BLUE), Patch(color="#BBBBBB"), marker],
             ["One day a week", "Two days a week", "Mean wait, days (bars)", "Waiting a day or more (markers)"], frameon=False, fontsize=8.5, ncol=4, loc="lower center")
    f.tight_layout(rect=(0, 0.07, 1, 1))
    return save(f, "capacity_powder_wait_by_color", f"Powder Color-Day Wait by Color, {YEAR}")


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
    d = ALL_QDAYS.sort_values(ascending=False)
    started = X["ops"].groupby("work_center").size()
    rows = [[FIRST_OP_LABEL.get(w, WC[w]), DRIVER[w], n0(QDAYS.loc[w, "operations"] if w in QDAYS.index else started[w]), n0(v), pct(v / d.sum(), 0)] for w, v in d.items()]
    rows.append(["All", "", "", n0(d.sum()), "100%"])
    return table(pd.DataFrame(rows, columns=["Work center", "Driver of queue time", "Operations", "Queue days", "Share"]))


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


# ── the new appendix tables ─────────────────────────────────────────────────
def blank(v, f=d2):
    return f(v) if v == v else ""


def t_bands():
    """Queue time by utilization band for every work center, the brakes first, with the weeks of the year at or above 80% and 95%."""
    order = ["press_brake"] + [w for w in C.UY.sort_values("utilization", ascending=False).index if w != "press_brake"]
    rows = []
    for wc in order:
        for band, r in SC.band_means(X, wc).iterrows():
            if r["weeks"] > 0:
                rows.append([WC[wc], band, n0(r["weeks"]), d2(r["queue"]), d2(r["median"])])
    a = table(pd.DataFrame(rows, columns=["Work center", "Utilization in the week", "Weeks", "Queue time, mean of weeks", "Median"]))
    rows = [[WC[wc], n0(SC.weeks_above(X, wc, 0.80)[0]), n0(SC.weeks_above(X, wc, SC.HOT)[0]), n0(SC.weeks_above(X, wc, 0.80)[1])] for wc in order]
    b_ = table(pd.DataFrame(rows, columns=["Work center", "Weeks at or above 80%", "Weeks at or above 95%", "Weeks in the year"]))
    return a + block(f"Weeks of {YEAR} at or above 80% and 95% utilization", b_)


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
    T.add("qdays", f"Queue days by work center and driver of queue time, {YEAR}", t_qdays())
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
    b.append("<h2 id='f1'>1. Capacity and Constraints</h2>")
    act = ACTIVITY
    assert UY["machine"].idxmax() == "press_brake"
    b.append(f"<p>The shop's floor consists of {n0(act['machines'].sum())} machines across ten work centers. The press brakes are the busiest, with "
             f"{n0(UY.loc['press_brake', 'machine'])} machine hours in {YEAR} ({P(UY.loc['press_brake', 'machine'] / UY['machine'].sum())} of total). Machine hours "
             f"break into operations per day and hours per operation, shown in routing order below.</p>")
    b.append(chart(f"Daily Floor Activity by Work Center, {YEAR}", fig_activity()))
    all_years = X["uw"][X["uw"]["week_year"].between(YEAR - 2, YEAR)]
    avg = {w: SC.pooled_utilization(all_years[all_years["work_center"] == w]) for w in UY.index}
    assert sorted(avg, key=avg.get, reverse=True)[:2] == LEAD_TWO
    shop = {y: SC.pooled_utilization(X["uw"][X["uw"]["week_year"] == y]) for y in (YEAR - 2, YEAR)}
    rel = q("select year(quarter_start) as y, sum(releases) as releases, sum(brake_std_hours) as brake_hours "
                                           "from marts.mart_releases_by_quarter group by 1 order by 1").set_index("y")
    b.append(f"<p>The press brakes consistently run at the highest utilization of any work center (average of {P(avg['press_brake'])} 2023-2025), followed by the "
             f"robotic weld cell ({P(avg['robotic_weld'])}). Across all work centers, average utilization increased from {P(shop[YEAR - 2])} in {YEAR - 2} to "
             f"{P(shop[YEAR])} in {YEAR} as released work grew {P(rel.loc[YEAR, 'releases'] / rel.loc[YEAR - 2, 'releases'] - 1)} "
             f"({n0(rel.loc[YEAR - 2, 'releases'])} to {n0(rel.loc[YEAR, 'releases'])} jobs a year; brake standard hours up "
             f"{P(rel.loc[YEAR, 'brake_hours'] / rel.loc[YEAR - 2, 'brake_hours'] - 1)}) across the same set of machines and shifts.</p>")
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
             f"{P(hot_share['press_brake'])} and {P(hot_share['robotic_weld'])} of weeks in {YEAR}, far more often than any other work center. Average queue time rises sharply when a work center is operating near maximum utilization. "
             f"This is explored in more detail in Section 2. {T.see('hot')}</p>")
    b.append(chart(f"Share of weeks at or above 95% utilization, {YEAR}", fig_hot_share()))
    b.append(chart("Queue Time in Weeks at or Above 95% Utilization vs. Other Weeks", fig_hot_year()))
    all_share = ALL_QDAYS / ALL_QDAYS.sum()
    assert all_share.idxmax() == "press_brake" and all_share["robotic_weld"] < 0.05
    total_ops = len(ops)
    b.append(f"<p>Throughout {YEAR}, jobs spent {n0(ALL_QDAYS.sum())} days waiting in queue at a work center. The press brake station accounted for "
             f"{P(all_share['press_brake'])} of those days, which is a function of its consistently high utilization, as well as its volume of operations. There "
             f"were {n0(QDAYS.loc['press_brake', 'operations'])} press brake operations in {YEAR} "
             f"({P(QDAYS.loc['press_brake', 'operations'] / total_ops)} of total). The robotic weld cell, which also ran at high utilization, accounted for "
             f"less than 5% of queue days, because only {n0(QDAYS.loc['robotic_weld', 'operations'])} operations "
             f"({pct(QDAYS.loc['robotic_weld', 'operations'] / total_ops)} of total) passed through it.</p>")
    b.append(chart(f"Share of queue days by work center, {YEAR}", fig_queue_days()))
    b.append("<p>The press brakes are therefore the shop's primary constraint on three counts: the highest utilization with the least buffer, the most weeks spent at "
             "maximum utilization, and nearly half of all queue days. The robotic weld cell shares the first two and constrains the enclosure work that crosses "
             "it. These stations are examined in more detail throughout this report.</p>")

    # 2 ── load and queue time
    b.append("<h2 id='f2'>2. Load and Queue Time</h2>")
    fits = C.FITS.set_index("work_center")
    at90 = fits["queue_at_0.90"]
    held = ALL_SHARE
    weeks = int(HY["weeks"].iloc[0])
    w80 = {w: SC.weeks_above(X, w, 0.80)[0] for w in LOAD}
    hot = {w: int(HY.loc[w, "hot_weeks"]) for w in UY.index}
    band = {w: SC.band_means(X, w) for w in LOAD}
    low = {w: float(band[w]["queue"].iloc[0]) for w in LOAD}
    full = {w: float(band[w]["queue"].iloc[-1]) for w in LOAD}
    rest_load = LOAD[2:]
    assert LOAD[:2] == LEAD_TWO and all(w80[w] > weeks / 2 for w in LEAD_TWO) and all(w80[w] < weeks / 2 for w in rest_load)
    assert all(full[w] > 2 * low[w] for w in LOAD) and all(hot[w] <= 2 for w in SCHEDULE)
    b.append(f"<p><a href='#f1'>Section 1</a> showed that when a work center runs near maximum utilization its queue time rises sharply. Across the floor, queue time "
             f"has one of two drivers. At six work centers it is load: queue time is flat at low utilization and rises past a knee at about 80% to 85%, steeply above "
             f"it. The press brakes and the robotic weld cell run above that knee most weeks; assembly, the manual weld bays, the laser and the punch are above it in "
             f"{min(w80[w] for w in rest_load)} to {max(w80[w] for w in rest_load)} weeks of {weeks}. At the other four, grind and deburr, inspection and pack, "
             f"hardware and the powder line, queue time is set by a schedule the shop runs, the daily dispatch list or the weekly color rotation, and does not move "
             f"with load; they are rarely near full. The chart below shows the distribution of each work center's queue time per operation in {YEAR} by driver; "
             f"the two subsections take the drivers in turn.</p>")
    b.append(chart(f"Queue Time per Operation by Work Center, {YEAR}", fig_queue_distribution()))

    b.append("<h3 id='f2_1'>Load-driven: the press brakes, the robotic weld cell, assembly, the manual weld bays, the laser and the punch</h3>")
    b.append("<p>At the six load-driven work centers the relationship is fitted as a curve on rolling 13-week windows from 2023 to 2025, drawn only over the range of "
             "utilization each has run at; windows rather than single weeks because a week's queue carries the backlog of the weeks before it. The three charts "
             "below pair the work centers by how often they are above the knee, with the mean queue time by utilization band drawn as steps over the weekly "
             "points.</p>")
    lo = C.BINS.iloc[:2]
    below = float((lo["queue_mean"] * lo["weeks"]).sum() / lo["weeks"].sum())
    step = float(C.BINS.iloc[2]["queue_mean"])
    record = SC.full_weeks(X, "press_brake")
    light = int((record["utilization"] < 0.70).sum())
    assert light < len(record) / 4
    assert at90["robotic_weld"] > at90["press_brake"] and PY.loc["robotic_weld", "queue_measured"] > PY.loc["robotic_weld", "queue_on_curve"]
    b.append(f"<p>The press brakes and the robotic weld cell are the two work centers above the knee most weeks: at or above 80% utilization in "
             f"{w80['press_brake']} and {w80['robotic_weld']} weeks of {weeks} in {YEAR}, and at or above 95% in {hot['press_brake']} and {hot['robotic_weld']}. "
             f"On the curve, brake queue time is {d2(FB['queue_at_0.85'])} days per operation at 85% and {d2(FB['queue_at_0.90'])} at 90%; the measured figure is "
             f"{d2(PY.loc['press_brake', 'queue_measured'])} days at {P(PY.loc['press_brake', 'utilization'])} for {YEAR} and "
             f"{d2(PR.loc['press_brake', 'queue_measured'])} in {REST}, and week by week it steps from about {d1(below)} days below 85% to {d1(step)} above and does "
             f"not settle back. The brakes seldom run light, so their panel has few points below 70% ({light} of {len(record)} weeks); the weld cell, one machine "
             f"on one shift, swings between idle and saturated weeks ({n0(ROBOT_BANDS.loc['below 80%', 'weeks'])} below 80%, "
             f"{n0(ROBOT_BANDS.loc['at or above 95%', 'weeks'])} at or above 95%), climbs faster with load ({d1(at90['robotic_weld'])} days on the curve at 90%) "
             f"and ran above its curve in {YEAR} ({d2(PY.loc['robotic_weld', 'queue_measured'])} days measured against "
             f"{d2(PY.loc['robotic_weld', 'queue_on_curve'])}). {T.see('bins', 'fits', 'pos')}</p>")
    b.append(chart(pair_title(LEAD_TWO), fig_pair(LEAD_TWO, "capacity_queue_curve_brake_robotic_weld")))
    BD = BRAKE_DIST
    lead, rest = BD.loc[["B1", "B2"]], BD.loc[["B3", "B4", "B5"]]
    b12 = MY.loc[["B1", "B2"], "utilization"]
    assert P(b12.min()) == P(b12.max()) and lead["median"].max() < rest["median"].min() and lead["p95"].max() < rest["p95"].min()
    b.append(f"<p>The brake queue is not one queue. Precision work is routed to B1 and B2 and the hot list, the shop's daily list of expedited jobs, is run on them "
             f"first, so these two machines, at {P(b12.max())} utilization, have the shortest and tightest waits (median {d2(BD.loc['B1', 'median'])} and "
             f"{d2(BD.loc['B2', 'median'])} days, 95th percentile {d1(BD.loc['B1', 'p95'])} and {d1(BD.loc['B2', 'p95'])}), while jobs without a priority queue on B3 to "
             f"B5, where the median is {rng(rest['median'].min(), rest['median'].max())} days and the 95th percentile "
             f"{rng(rest['p95'].min(), rest['p95'].max(), d1)}. The long brake waits that make jobs late are concentrated on the three machines the hot list does "
             f"not protect. {T.see('machines', 'basis')}</p>")
    b.append(chart(f"Queue Time per Operation by Brake, {YEAR}", fig_brake_distribution()))

    pair = ["assembly", "weld"]
    mid = {}
    for w in pair:
        r = SC.full_weeks(X, w)
        mid[w] = float(r[(r["utilization"] >= 0.80) & (r["utilization"] < SC.HOT)]["queue_mean"].mean())
        assert 1.7 <= mid[w] / low[w] <= 2.6, (w, mid[w] / low[w])
    upper = pd.concat([band[w]["weeks"].iloc[1:] for w in pair])
    ah = ASM["compare"]["hot"]
    pv = ASM["previous"]
    assert list(pv.index[:2]) == ["powder_coat", "outside_processing"]
    assert abs(fits.loc["assembly", "rank_correlation"] - FB["rank_correlation"]) < 0.05 < FB["rank_correlation"] - fits.loc["weld", "rank_correlation"]
    b.append(f"<p>Assembly and the manual weld bays follow the same shape with a different operating point. Below 80% utilization their queue time is flat at "
             f"{d2(low['assembly'])} and {d2(low['weld'])} days per operation; from 80% to 95% it roughly doubles; at or above 95% it is {d2(full['assembly'])} and "
             f"{d2(full['weld'])} days, each band above 80% resting on {int(upper.min())} to {int(upper.max())} weeks. They were at or above 80% in {w80['assembly']} "
             f"and {w80['weld']} weeks of {weeks} in {YEAR} and at or above 95% in {hot['assembly']} and {hot['weld']}, and hold {P(held[pair].sum())} of queue "
             f"days between them. The curve fits assembly about as well as the brakes (rank correlation {d2(fits.loc['assembly', 'rank_correlation'])}) and the "
             f"weld bays less well ({d2(fits.loc['weld', 'rank_correlation'])}), whose six machines pool arrivals until the last few points of load. Assembly's "
             f"loaded weeks are its own doing, more arrivals and larger jobs, {ASM['backlog_weeks']} of the {int(ah['weeks'])} in the first-quarter backlog; it "
             f"receives {P(pv['powder_coat'])} of its work from the powder line and {P(pv['outside_processing'])} from outside processing, both of which release "
             f"work in batches. {T.see('qdays', 'assembly', again=('bins', 'pos'))}</p>")
    b.append(chart(pair_title(pair), fig_pair(pair, "capacity_queue_curve_assembly_weld")))
    nov = C.LAS_NOV
    first = ["laser", "punch"]
    b.append(f"<p>The laser and the punch are first operations, so their queue is measured from traveler print to first cut, less any wait for material. Both rise "
             f"past the same knee. The punch, one machine running about {n0(ACTIVITY.loc['punch', 'ops_per_week'])} operations a week, fills on a few large jobs: at "
             f"or above 80% in {w80['punch']} weeks of {weeks} in {YEAR} and at or above 95% in {hot['punch']}, taking its wait from {d2(low['punch'])} to "
             f"{d2(full['punch'])} days per operation. The lasers pool three machines over about {n0(ACTIVITY.loc['laser', 'ops_per_week'])} operations a week and "
             f"reach the knee only when releases surge: at or above 80% in {w80['laser']} weeks and at or above 95% in {hot['laser']} in {YEAR}, and in the six "
             f"weeks of the Q4 2024 build, when the first-operation queue rose from {d1(nov.iloc[0]['queue_mean'])} to {d1(nov.iloc[-1]['queue_mean'])} days "
             f"({link('lead')}). {T.see('laser_weeks', 'lasers', again=('bins', 'pos'))}</p>")
    b.append(chart(pair_title(first, True), fig_pair(first, "capacity_queue_curve_laser_punch", first_operation=True)))

    b.append("<h3 id='f2_2'>Schedule-driven: grind and deburr, inspection and pack, hardware and the powder line</h3>")
    early, mid_day, late = HOURS.iloc[:3], HOURS.iloc[3:5], HOURS.iloc[5:]
    same = lambda g: float((g["same_day"] * g["arrivals"]).sum() / g["arrivals"].sum())
    assert 0.85 <= same(early) < 0.95 and 0.25 <= same(mid_day) < 0.35 and 0.45 <= mid_day["share"].sum() <= 0.55
    assert set(X["shifts"].set_index("work_center").loc[SC.LIST_CENTERS, "shifts"]) == {1}          # one shift at each, so no crew for a list at 14:00
    lu = UY.loc[SC.LIST_CENTERS, "utilization"]
    assert hot["inspection_pack"] == 0 and hot["hardware"] == 0 and SC.weeks_above(X, "powder_coat", 0.80)[0] == 0
    b.append(f"<p>At grind and deburr, inspection and pack, hardware and the powder line, queue time does not move with load. The first three run at {P(lu.min())} to "
             f"{P(lu.max())} for the year and were at or above 95% in {hot['grind_deburr']} weeks of {weeks} at grind and deburr and never at the other two; the "
             f"powder line runs at {P(UY.loc['powder_coat', 'utilization'])} and is never near full. Their wait is set by a schedule: the daily dispatch list at "
             f"the first three, the weekly color rotation at powder.</p>")
    b.append(f"<p>At the three dispatch-list work centers, {P(held[SC.LIST_CENTERS].sum())} of queue days, whether an operation starts the day it arrives depends on "
             f"the hour of arrival: work arriving before 10:00 starts the same day nine times in ten; work arriving between 10:00 and 14:00, half of all arrivals, "
             f"starts the same day about three times in ten and otherwise waits for the next morning; the {P(late['share'].sum())} arriving after the shift ends "
             f"always waits. The brakes show no such break. {T.see('dispatch')}</p>")
    b.append(chart(f"Same-Day Start by Hour of Arrival, Dispatch-List Work Centers Against the Brakes, {YEAR}", fig_same_day()))
    refresh = SC.midday_wait(X)
    assert refresh >= 0.3
    b.append(f"<p>These next-day starts add {d1(NEXT_DAY['year'])} working days of lead time to a shipped job ({d1(NEXT_DAY[REST])} in {REST}). The lever is the list, "
             f"not capacity: a midday refresh of the day's list lets the arrivals between 10:00 and 12:00, {P(HOURS.iloc[3]['share'])} of the total, start the same "
             f"afternoon, recovering up to {d1(refresh)} of those days; what arrives after the shift ends can only start the next morning.</p>")
    two, once = POWDER[POWDER["days_per_week"] > 1.5], POWDER[POWDER["days_per_week"] <= 1.5]
    assert len(two) == 3 and len(once) == 3
    wmean = lambda g: float(g["wait_days"].sum() / g["operations"].sum())
    assert wmean(once) / wmean(two) > 2
    b.append(f"<p>At the powder line the wait is for the color day, {d2(POWDER_ALL['wait_mean'])} days per operation. The three colors run once a week wait more than "
             f"twice as long as the three run twice a week and account for {P(once['share_of_wait'].sum())} of the wait on "
             f"{P(once['share_of_operations'].sum())} of operations. A third day for black is tested in {link('options')}. {T.see('powder')}</p>")
    b.append(chart(f"Powder Color-Day Wait by Color, {YEAR}", fig_powder()))

    b.append(f"<p>Of the two drivers, load at the brakes is the one that costs the shop delivery: the brakes hold {P(held['press_brake'])} of queue days and their "
             f"queue is the largest attributed cause of late shipments (the flow report). <a href='#f3'>Section 3</a> measures the brake hours behind it.</p>")

    # 3 ── brake hours
    b.append("<h2 id='f3'>3. Brake Hours: Setups, Standards and the Peak</h2>")
    b.append(f"<p>The brake queue is set by uneven arrivals and by load above 85%, so what matters at the brakes is hours: how many are lost to setups over standard "
             f"and how many of those can be recovered, whether the standards the schedule is planned on are right, how far released work exceeds brake capacity at "
             f"the year-end peak, and where a crewed shift is open. This section measures each from the record. {link('options')} takes these measured hours as inputs "
             f"and tests, on the shop model, what changing them does to on-time delivery, alongside release and dispatch rules. The variability at the brakes is in arrivals and "
             f"run times, not setups (coefficients of variation {d2(C.var('Arrivals: jobs released per working day'))} for daily arrivals and "
             f"{d2(C.var('Brake run time'))} for run time against {d2(C.var('Brake setup time'))} for setup time; {T.cite('var', 'spread')}), so halving the spread "
             f"of setup time (each setup moved halfway to the mean, the curve rescaled) releases only {d1(C.SV.loc['year', 'hours_per_week_released'])} brake hours "
             f"a week; the mean setup time is where the hours are.</p>")
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
             f"{int(HY.loc['robotic_weld', 'hot_weeks'])} weeks of {int(HY.loc['robotic_weld', 'weeks'])}; its second shift is uncrewed. Enclosures are "
             f"{P(ROBOT_FAMILIES.loc['enclosure', 'share'])} of its hours, so a second shift would serve the enclosure customers first. The options report tests "
             f"and prices crewing it. {T.see('robot')}</p>")

    b.append("<h2 id='appendix'>Appendix</h2>")
    b.append(T.appendix())
    toc = [("f1", "1. Capacity and Constraints"), ("f2", "2. Load and Queue Time"), ("f3", "3. Brake Hours: Setups, Standards and the Peak")]
    print(f"wrote {page('capacity', chr(10).join(b), toc)}: 3 sections, {len(T.order)} appendix tables")
    return T.order


def main():
    build()


if __name__ == "__main__":
    main()
