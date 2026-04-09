"""Discrete event simulation of on-time delivery: the report.

Usage: python -m analytics.reports.options_tested
"""
import re

import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle

from analytics.db import q
from analytics.release_control import analysis as A
from analytics.reports.combine import REPORTS
from analytics.reports.layout import RT, Tables, block, chart, link, page, titled
from analytics.style.style import AMBER, BRAND_BLUE, DOCS, GREEN, GREY, LIGHT_BLUE, RED, fig, save_conformed as save, sig, table

YEAR = A.YEAR
CURRENT, PACKAGE = A.CURRENT, A.PACKAGE
SETUP, SAT_ONE, SAT_BOTH, WELD, CHANGER, TOWER, CELL, EDD = ("Brake setup program", "Add'l Saturdays (one brake)", "Add'l Saturdays (both brakes)", "Second shift: robotic weld",
                                                             "Replace press brake B3", "Automated sheet tower (L2)", "New robotic bending cell", "Earliest due date")
P_CHANGER, P_TOWER, P_CELL, P_EDD = A.COMBOS
RATIO = "Due-date ratio"
PERIODS = (("year", f"{YEAR}"), ("rest", RT))
COLOR = {"Works": BRAND_BLUE, "No effect": GREY, "Makes it worse": RED}
WORD = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]
# the rows of the cost and return table: a scenario and what it is measured against
RETURN = [(SETUP, CURRENT), (SAT_BOTH, CURRENT), (PACKAGE, CURRENT), (WELD, CURRENT), (P_CELL, PACKAGE), (P_CHANGER, PACKAGE)]
RETURN_ALL = [(SETUP, CURRENT), (SAT_BOTH, CURRENT), (WELD, CURRENT), (CHANGER, CURRENT), (CELL, CURRENT), (PACKAGE, CURRENT), (P_CHANGER, PACKAGE), (P_TOWER, PACKAGE), (P_CELL, PACKAGE)]
LABEL = {P_CELL: "Robotic cell, on top of the package", P_CHANGER: "Tool changer, on top of the package", P_TOWER: "Laser tower, on top of the package"}


def n0(x):
    return f"{x:,.0f}"


def d1(x):
    return f"{x:,.1f}"


def d2(x):
    return f"{x:,.2f}"


def pc(x, d=1):
    return f"{x * 100:.{d}f}%"


def usd(x):
    return ("-" if x < 0 else "") + f"${abs(x):,.0f}"


def musd(x):
    return ("-" if x < 0 else "") + f"${abs(x) / 1e6:.2f}M"


def sg(x, d=1):
    return f"{x:+,.{d}f}"


def band(t, d=1, scale=1.0):
    return f"{sg(t[0] * scale, d)} ({sg(t[1] * scale, d)} to {sg(t[2] * scale, d)})"


def pts(sc, per="year", ref=CURRENT):
    """A change in on-time delivery in points with its interval."""
    t = A.diff(sc, "on_time_delivery", per, ref)
    return f"{sg(t[0] * 100)} points ({sg(t[1] * 100)} to {sg(t[2] * 100)})"


def ptsb(sc, per="year", ref=CURRENT):
    """The same inside a parenthesis."""
    t = A.diff(sc, "on_time_delivery", per, ref)
    return f"{sg(t[0] * 100)} points, {sg(t[1] * 100)} to {sg(t[2] * 100)}"


def chg(sc, m, per="year", ref=CURRENT):
    return A.diff(sc, m, per, ref)[0]


def name(sc):
    return LABEL.get(sc, sc)


def week(t):
    return f"{t:%B} {t.day}"


# ── figures ─────────────────────────────────────────────────────────────────
def fig_ten(ten):
    """The ten measures set before the model was run: the model's difference from measured as a share of its tolerance, with its 95% interval and the two values."""
    f, ax = fig(h=4.4, grid="x")
    t = ten.reset_index(drop=True)
    order = ["lead_time_median", "wip_mean", "brake_utilization", "robotic_weld_utilization", "on_time_delivery"]
    t = t.assign(rank=[order.index(m) * 2 + (0 if per == "year" else 1) for m, per in zip(t["measure"], t["period"])]).sort_values("rank").reset_index(drop=True)
    y = np.arange(len(t))[::-1]
    ax.axvspan(-100, 100, color="#EEF2F6", lw=0)
    ax.axvline(0, color="#333333", lw=1)
    labels = []
    for yi, r in zip(y, t.itertuples()):
        tol_ = A.TOLERANCE[r.measure][1]
        share = lambda v: ((v / r.measured - 1) if r.kind == "relative" else (v - r.measured)) / tol_ * 100
        f_ = pc if r.measure == "on_time_delivery" else (lambda x: f"{x:.3f}") if "utilization" in r.measure else d2
        ax.plot([share(r.low), share(r.high)], [yi, yi], color=BRAND_BLUE, lw=1.8)
        ax.scatter([share(r.model)], [yi], color=BRAND_BLUE, s=30, zorder=3)
        ax.annotate(f"{f_(r.measured)} vs {f_(r.model)}", (share(r.high), yi), textcoords="offset points", xytext=(6, 0), va="center", fontsize=8.2)
        labels.append(f"{MEASURE[r.measure]}, {YEAR if r.period == 'year' else RT}")
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8.8)
    ax.set_xlim(-100, 100)
    ax.set_xticks([-100, -50, 0, 50, 100])
    ax.set_xticklabels(["-100%", "-50%", "0%", "+50%", "+100%"])
    ax.set_xlabel("Model less measured, as a share of the tolerance (points show measured vs model)")
    f.tight_layout()
    return save(f, "model_against_measured_ten_measures", "")


def fig_work_centers(w):
    f, axes = fig(h=4.0, ncols=2, grid="x", sharey=True)
    y = np.arange(len(w))[::-1]
    for ax, a, b, lab in ((axes[0], "utilization_measured", "utilization_model", "Utilization"), (axes[1], "queue_measured", "queue_model", "Queue time per operation (working days)")):
        for yi, m, s in zip(y, w[a], w[b]):
            ax.plot([m, s], [yi, yi], color=GREY, lw=1.5, zorder=1)
        ax.scatter(w[a], y, color=AMBER, s=34, zorder=2, label="Measured")
        ax.scatter(w[b], y, color=BRAND_BLUE, s=34, zorder=3, label="Model")
        ax.set_xlabel(lab)
        ax.set_yticks(y)
        ax.set_yticklabels(w["work_center"], fontsize=9)
    axes[0].set_xlim(0.5, 1.0)
    axes[0].legend(frameon=False, fontsize=9, ncol=2)
    f.tight_layout()
    return save(f, "model_work_centers", "")


def fig_lead(pct, curve):
    f, axes = fig(h=3.6, ncols=2, sharey=True)
    for ax, (per, lab) in zip(axes, PERIODS):
        c = curve[per]
        c = c[c["days"] <= 45]
        ax.plot(c["days"], c["measured"] * 100, color=AMBER, lw=1.8, label="Measured")
        ax.plot(c["days"], c["model"] * 100, color=BRAND_BLUE, lw=1.8, ls="--", label="Model")
        p = pct[pct["period"] == per].set_index("percentile")
        for k, word in ((50, "Median"), (90, "90th percentile")):
            ax.axhline(k, color=GREY, lw=0.8, ls=":")
            ax.annotate(f"{word}: {p.loc[k, 'measured']:.1f} measured, {p.loc[k, 'model']:.1f} model", (45, k), textcoords="offset points", xytext=(0, -10), ha="right", fontsize=7.5)
        ax.set_title(lab, fontsize=10)
        ax.set_xlabel("Lead time (working days)")
    axes[0].set_ylabel("Jobs shipped within (%)")
    axes[0].legend(frameon=False, fontsize=9, ncol=2)
    f.tight_layout()
    return save(f, "model_lead_time", "")


def fig_build(w):
    f, axes = fig(h=5.0, nrows=2, sharex=True)
    for ax, a, b, lab in ((axes[0], "wip_measured", "wip_model", "Floor WIP (jobs)"), (axes[1], "brake_queue_measured", "brake_queue_model", "Brake queue time per operation" + "\n" + "(working days)")):
        ax.axvspan(pd.Timestamp(f"{YEAR - 1}-12-01"), pd.Timestamp(f"{YEAR}-03-31"), color=GREY, alpha=0.15, lw=0)
        ax.plot(w.index, w[a], color=AMBER, lw=1.8, label="Measured")
        ax.plot(w.index, w[b], color=BRAND_BLUE, lw=1.8, ls="--", label="Model")
        ax.set_ylabel(lab)
        ax.set_ylim(0, None)
    hs, ls = axes[0].get_legend_handles_labels()
    axes[0].legend(hs + [Patch(color=GREY, alpha=0.15, lw=0)], ls + ["December to March"], frameon=False, fontsize=9, ncol=3)
    axes[1].set_xlabel("Week")
    f.tight_layout()
    return save(f, "model_year_end_build", "")


IMPACT = {"Positive Impact": BRAND_BLUE, "No effect": GREY, "Negative Impact": RED}

def impact(t, up_is_good=True):
    """Positive or negative where the whole interval lies on one side of zero; no effect where it takes in zero."""
    return "No effect" if t[1] <= 0 <= t[2] else ("Positive Impact" if (t[0] > 0) == up_is_good else "Negative Impact")


def fig_effects(names, file, head):
    """The change in on-time delivery of the given scenarios against the status quo, for the year and for the ordinary quarters, largest first, under a heading."""
    names = sorted(names, key=lambda s: chg(s, "on_time_delivery"))
    h = 2.05 + 0.3 * len(names)
    f, axes = fig(h=h, ncols=2, grid="x", sharey=True)
    y = np.arange(len(names))
    for ax, (per, lab) in zip(axes, PERIODS):
        ax.axvline(0, color="#333333", lw=1)
        for yi, s in zip(y, names):
            t = [v * 100 for v in A.diff(s, "on_time_delivery", per)]
            ax.barh(yi, t[0], 0.62, color=IMPACT[impact(t)])
            ax.plot([t[1], t[2]], [yi, yi], color="#222222", lw=1.2)
            ax.annotate(sg(t[0]), (t[2] if t[0] >= 0 else t[1], yi), textcoords="offset points", xytext=(4 if t[0] >= 0 else -4, 0), va="center",
                        ha="left" if t[0] >= 0 else "right", fontsize=7.5)
        lo, hi = ax.get_xlim()
        ax.set_xlim(lo - (hi - lo) * 0.12, hi + (hi - lo) * 0.12)
        ax.set_title(lab, fontsize=10)
    axes[0].set_yticks(list(y) + [len(names)])
    axes[0].set_yticklabels(names + [head], fontsize=8.5)
    axes[0].get_yticklabels()[-1].set_fontweight("bold")
    axes[0].get_yticklabels()[-1].set_color("black")
    axes[0].yaxis.get_major_ticks()[-1].tick1line.set_visible(False)
    axes[0].set_ylim(-0.6, len(names) + 0.4)
    f.tight_layout(rect=(0, 0.78 / h, 1, 1))
    middle = float(sig((axes[0].get_position().x0 + axes[1].get_position().x1) / 2, 4))
    f.text(middle, 0.52 / h, "Change in on-time delivery vs. Status Quo (points)", ha="center", va="center", fontsize=10)
    f.legend([Patch(color=c) for c in IMPACT.values()], list(IMPACT), frameon=False, fontsize=9, ncol=3, loc="lower center", bbox_to_anchor=(middle, 0.0))
    return save(f, file, "")


WORKING = [SETUP, SAT_BOTH, SAT_ONE, WELD, CHANGER, CELL, EDD]
# the outcomes of the chart of changes that work: measure, panel title, decimals, in points, and whether a rise is good for delivery
PANELS = [("on_time_delivery", "On-time delivery" + chr(10) + "(points)", 1, True, True), ("brake_utilization", "Brake utilization" + chr(10) + "(points)", 1, True, False),
          ("brake_queue_mean", "Brake queue time" + chr(10) + "(days)", 2, False, False), ("wip_mean", "Floor WIP" + chr(10) + "(jobs)", 0, False, False),
          ("late_jobs", "Late jobs" + chr(10), 0, False, False), ("days_late", "Days late" + chr(10), 0, False, False)]
# the panels under each heading: first and last, by position
HEADS = [("Delivery Mechanisms", 1, 3), ("Delivery Outcomes", 4, 5)]


def fig_changes():
    combos = [PACKAGE, P_CELL, P_CHANGER, P_TOWER]
    names = WORKING + combos
    h = 5.6
    f, axes = fig(h=h, w=9.2, ncols=len(PANELS), grid=None, sharey=True)
    y = [len(names) - k - 0.4 for k in range(len(WORKING))] + [len(combos) - 1.0 - k for k in range(len(combos))]              # the combinations set apart at the bottom
    for ax, (m, title, d, points, up_is_good) in zip(axes, PANELS):
        ax.grid(False)
        ax.axvline(0, color="#888888", lw=1)
        ax.axhline(len(combos) - 0.2, color=GREY, lw=0.6, ls=":")
        for yi, s in zip(y, names):
            t = [v * (100 if points else 1) for v in A.diff(s, m)]
            color = IMPACT[impact(t, up_is_good)]
            ax.plot([t[1], t[2]], [yi, yi], color=color, lw=1.6)
            ax.scatter([t[0]], [yi], color=color, s=22, zorder=3)
            lab = sg(t[0], d)
            ax.annotate(lab.lstrip("+-") if float(lab.replace(",", "")) == 0 else lab, (t[0], yi), textcoords="offset points", xytext=(0, 5), ha="center", fontsize=6.6)
        lo, hi = ax.get_xlim()
        ax.set_xlim(lo - (hi - lo) * 0.14, hi + (hi - lo) * 0.14)
        ax.set_title(title, fontsize=7.8)
        ax.tick_params(axis="x", labelsize=6.5)
        ax.locator_params(axis="x", nbins=3)
        for side in ax.spines.values():
            side.set_visible(True)
            side.set_color("black")
            side.set_linewidth(0.8)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(names, fontsize=8.2)
    axes[0].set_ylim(-0.7, max(y) + 0.9)
    f.legend([Line2D([], [], color=c, marker="o", lw=1.6) for c in (IMPACT["Positive Impact"], IMPACT["Negative Impact"], IMPACT["No effect"])],
             ["Positive Impact", "Negative Impact", "No effect"], frameon=False, fontsize=8.5, ncol=3, loc="lower center")
    f.tight_layout(rect=(0, 0.28 / h, 1, 1 - 0.46 / h), w_pad=0.6)
    for text, a, z in HEADS:
        x0, x1 = float(sig(axes[a].get_position().x0, 4)), float(sig(axes[z].get_position().x1, 4))
        f.patches.append(Rectangle((x0, 1 - 0.39 / h), x1 - x0, 0.25 / h, transform=f.transFigure, facecolor=BRAND_BLUE, edgecolor="none"))
        f.text((x0 + x1) / 2, 1 - 0.265 / h, text, ha="center", va="center", fontsize=8.6, fontweight="bold", color="white")
    return save(f, "changes_that_work", "")


KIND = {SETUP: "Permanent capacity at the brakes", CHANGER: "Permanent capacity at the brakes", CELL: "Permanent capacity at the brakes",
        SAT_BOTH: "Seasonal capacity at the brakes", SAT_ONE: "Seasonal capacity at the brakes", WELD: "Capacity elsewhere", TOWER: "Capacity elsewhere"}
KIND_COLOR = {"Permanent capacity at the brakes": BRAND_BLUE, "Seasonal capacity at the brakes": LIGHT_BLUE, "Capacity elsewhere": GREEN, "Release and dispatch rule": AMBER}


def fig_summary_effects():
    """Every single scenario's change in on-time delivery for the year, sorted, filled by the kind of change."""
    names = sorted(A.RELEASE + A.CAPACITY, key=lambda s: chg(s, "on_time_delivery"))
    f, ax = fig(h=5.0, grid="x")
    y = np.arange(len(names))
    for yi, s in zip(y, names):
        v = chg(s, "on_time_delivery") * 100
        ax.barh(yi, v, 0.66, color=KIND_COLOR[KIND.get(s, "Release and dispatch rule")])
        ax.annotate(sg(v), (v, yi), textcoords="offset points", xytext=(4 if v >= 0 else -4, 0), va="center", ha="left" if v >= 0 else "right", fontsize=8.5)
    ax.axvline(0, color="#333333", lw=1)
    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=9)
    lo, hi = ax.get_xlim()
    ax.set_xlim(lo - 1.2, hi + 1.2)
    ax.set_xlabel("Change in on-time delivery (points)")
    f.legend([Patch(color=c) for c in KIND_COLOR.values()], list(KIND_COLOR), frameon=False, fontsize=8.5, ncol=2, loc="lower center")
    f.tight_layout(rect=(0, 0.1, 1, 1))
    return save(f, "summary_effects", "")


def fig_summary_steps(package, cell):
    """On-time delivery from the status quo to the package and the package with the robotic cell, each with its cost and return under the bar."""
    f, ax = fig(h=3.7)
    base, pk, pc_ = (A.mean(s, "on_time_delivery") * 100 for s in (CURRENT, PACKAGE, P_CELL))
    short = lambda x: musd(x) if abs(x) >= 1e6 else f"${x / 1e3:,.0f}K"
    back = lambda y: f"{y * 12:.0f} months" if y < 1 else f"{y:.1f} years"
    lines = lambda m: [f"Initial investment: {short(m['one_time'])}", f"Annual cost: {short(m['added'])}", f"Net present value: {short(m['npv'][0])}", f"Payback period: {back(m['payback'])}"]
    steps = [("Status Quo", [], base, None, GREY), ("Operating Package", lines(package), pk, pk - base, BRAND_BLUE),
             ("Operating Package + Robotic Bending Cell", lines(cell), pc_, pc_ - pk, GREEN)]
    floor = 70.0
    for k, (head, under, v, step, color) in enumerate(steps):
        prev = steps[k - 1][2] if k else floor
        if k:
            ax.bar(k, prev - floor, 0.62, bottom=floor, color="#E6E6E6")
        ax.bar(k, v - (prev if k else floor), 0.62, bottom=prev if k else floor, color=color)
        ax.annotate(f"{v:.1f}%" + ("" if step is None else chr(10) + f"{sg(step)} points"), (k, v), textcoords="offset points", xytext=(0, 3), ha="center", fontsize=9)
        for n, text in enumerate([head] + under):
            ax.annotate(text, (k, 0), xycoords=ax.get_xaxis_transform(), textcoords="offset points", xytext=(0, -8 - 12 * n), ha="center", va="top", fontsize=8.5,
                        fontweight="bold" if n == 0 else None)
    ax.set_xticks(range(len(steps)))
    ax.set_xticklabels(["" for _ in steps])
    ax.set_ylim(floor, 96)
    ax.set_yticks(range(70, 100, 5))
    ax.set_yticklabels([f"{v}%" for v in range(70, 100, 5)])
    ax.set_ylabel("On-time delivery")
    f.subplots_adjust(left=0.08, right=0.99, top=0.95, bottom=0.31)
    return save(f, "summary_steps", "")


# the rows of the two return charts: a scenario, what it is measured against, and its label
CHARTED = [(SETUP, CURRENT, "Brake setup program"), (SAT_BOTH, CURRENT, "Planned Saturdays (both brakes)"), (PACKAGE, CURRENT, "Operating package"),
           (CHANGER, CURRENT, "Replace brake B3, alone"), (P_CHANGER, PACKAGE, "Replace brake B3, on top of the package"),
           (CELL, CURRENT, "Robotic bending cell, alone"), (P_CELL, PACKAGE, "Robotic bending cell, on top of the package")]
# the rows of the table of what is measured and not priced
NOT_PRICED = [(SETUP, CURRENT), (SAT_BOTH, CURRENT), (PACKAGE, CURRENT), (P_CELL, PACKAGE), (P_CHANGER, PACKAGE)]


def fig_npv(money):
    f, ax = fig(h=4.0, grid="x")
    y = np.arange(len(CHARTED))[::-1]
    for yi, (sc, ref, _) in zip(y, CHARTED):
        m = money[sc]
        left = 0.0
        annual = (m["added"] - m["avoided"]) * A.ANNUITY                  # the annual cost net of overtime avoided
        assert annual > 0
        for v, c in ((m["one_time"], RED), (annual, AMBER)):
            ax.barh(yi, -v / 1e6, 0.55, left=left, color=c)
            left -= v / 1e6
        right = m["throughput"] * A.ANNUITY / 1e6
        ax.barh(yi, right, 0.55, color=BRAND_BLUE)
        t = [v / 1e6 for v in m["npv"]]
        ax.plot([t[1], t[2]], [yi, yi], color="#111111", lw=1.4, zorder=4)
        ax.scatter([t[0]], [yi], marker="D", color="#111111", s=34, zorder=5)
        ax.annotate(musd(m["npv"][0]), (max(right, t[2]), yi), textcoords="offset points", xytext=(6, 0), va="center", fontsize=8.5)
    ax.axvline(0, color="#333333", lw=1)
    ax.set_yticks(y)
    ax.set_yticklabels([lab for _, _, lab in CHARTED], fontsize=9)
    ax.set_xlabel(f"Present value over {A.F['horizon_years']} years at {A.F['discount_rate']:.0%} ($ million)")
    lo, hi = ax.get_xlim()
    ax.set_xlim(lo, hi + (hi - lo) * 0.08)
    ax.legend([Patch(color=RED), Patch(color=AMBER), Patch(color=BRAND_BLUE), Line2D([], [], color="#111111", marker="D", lw=1.4)],
              ["One-time cost", "Annual Cost", "Throughput value (50% sold)", "NPV, with 95% interval"], frameon=False, fontsize=8.5, ncol=4)
    f.tight_layout()
    return save(f, "return_npv_parts", "")


def fig_sold(money):
    f, ax = fig(h=4.2)
    x = np.linspace(0, 1, 41)
    colors = {SETUP: LIGHT_BLUE, PACKAGE: BRAND_BLUE, P_CELL: GREEN, CELL: GREEN, P_CHANGER: AMBER, CHANGER: AMBER, SAT_BOTH: RED}
    for sc, ref, lab in CHARTED:
        m = money[sc]
        v = np.array([A.npv_at(m, s) for s in x]) / 1e6
        even = m["share"] == m["share"] and 0 < m["share"] < 1
        ax.plot(x * 100, v[:, 0], color=colors[sc], lw=1.8, ls="--" if sc in (CELL, CHANGER) else "-", label=lab)
        ax.fill_between(x * 100, v[:, 1], v[:, 2], color=colors[sc], alpha=0.15, lw=0)
        if even:
            ax.scatter([m["share"] * 100], [0], color=colors[sc], s=30, zorder=5)
    ax.axhline(0, color="#333333", lw=1)
    ax.axvline(A.SOLD * 100, color=GREY, lw=1, ls="--")
    ax.annotate("50% assumed", (A.SOLD * 100, ax.get_ylim()[1]), textcoords="offset points", xytext=(4, -10), fontsize=8, color="#555555")
    ax.set_xlabel("Share of freed brake hours sold (%)")
    ax.set_ylabel("NPV ($ million)")
    f.legend(*ax.get_legend_handles_labels(), frameon=False, fontsize=8.5, ncol=2, loc="lower center")
    f.tight_layout(rect=(0, 0.19, 1, 1))
    return save(f, "return_npv_by_share_sold", "")


# ── tables ──────────────────────────────────────────────────────────────────
MEASURE = {"lead_time_median": "Median lead time (days)", "wip_mean": "Mean floor WIP (jobs)", "brake_utilization": "Brake utilization", "robotic_weld_utilization": "Robotic weld utilization",
           "on_time_delivery": "On-time delivery", "lead_time_p90": "90th-percentile lead time (days)", "jobs_shipped": "Jobs shipped"}


def t_tolerance(t):
    rows = []
    for r in t.itertuples():
        f_ = pc if r.measure == "on_time_delivery" else (lambda x: f"{x:.3f}") if "utilization" in r.measure else n0 if r.measure == "jobs_shipped" else d2
        diff_ = f"{r.difference * 100:+.1f}%" if r.kind != "points" else f"{r.difference * 100:+.1f} points"
        rows.append([f"{YEAR}" if r.period == "year" else RT, MEASURE[r.measure], f_(r.measured), f"{f_(r.model)} ({f_(r.low)} to {f_(r.high)})", diff_,
                     {"relative": "within 10%", "points": "within 3 points"}.get(r.kind, "reported"), "" if r.within is None or r.within != r.within else ("within" if r.within else "outside")])
    return table(pd.DataFrame(rows, columns=["Period", "Measure", "Measured", "Model (95% interval)", "Difference", "Tolerance", "Result"]))


def t_work_centers(w):
    rows = [[r.work_center, f"{r.utilization_measured:.3f}", f"{r.utilization_model:.3f}", sg((r.utilization_model - r.utilization_measured) * 100), d2(r.queue_measured), d2(r.queue_model),
             f"{(r.queue_model / r.queue_measured - 1) * 100:+.0f}%"] for r in w.itertuples()]
    return table(pd.DataFrame(rows, columns=["Work center", "Utilization, measured", "Utilization, model", "Difference (points)", "Queue per operation, measured (days)",
                                             "Queue per operation, model", "Difference"]))


def t_lead(pct):
    rows = [[f"{YEAR}" if r.period == "year" else RT, f"{r.percentile}th", d1(r.measured), d1(r.model), f"{(r.model / r.measured - 1) * 100:+.1f}%"] for r in pct.itertuples()]
    return table(pd.DataFrame(rows, columns=["Period", "Percentile", "Measured (days)", "Model", "Difference"]))


def t_weeks(w):
    rows = [[f"{i:%Y-%m-%d}", n0(r.releases_measured), n0(r.releases_model), n0(r.shipped_measured), n0(r.shipped_model), n0(r.wip_measured), n0(r.wip_model), d2(r.brake_queue_measured),
             d2(r.brake_queue_model), d2(r.laser_utilization_measured), d2(r.laser_utilization_model), d2(r.brake_utilization_measured), d2(r.brake_utilization_model),
             n0(r.brake_hours_measured), n0(r.brake_hours_weekday_model + r.brake_hours_saturday_model + r.brake_hours_extended_model), n0(r.brake_saturday_hours_measured),
             n0(r.brake_hours_saturday_model), n0(r.saturday_shifts_measured), d1(r.saturday_shifts_model), n0(r.extended_hours_measured), d1(r.extended_hours_model)] for i, r in w.iterrows()]
    pairs = ["Jobs released", "Jobs shipped", "Floor WIP", "Brake queue per operation (days)", "Laser utilization", "Brake utilization", "Brake hours worked", "of which Saturday",
             "Saturday shifts called", "Extended hours scheduled"]
    head = ("<tr><th rowspan='2'>Week of</th>" + "".join(f"<th colspan='2' style='text-align:center'>{p}</th>" for p in pairs) + "</tr><tr>" + "<th>Measured</th><th>Model</th>" * len(pairs) + "</tr>")
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div style="overflow-x:auto"><table class="data"><thead>{head}</thead><tbody>{body}</tbody></table></div>'


def t_quarters(qt):
    rows = [[k[:4] + " " + k[4:], n0(r.jobs_shipped), n0(r.jobs_shipped_model), pc(r.on_time_delivery), pc(r.on_time_delivery_model), sg((r.on_time_delivery_model - r.on_time_delivery) * 100),
             d1(r.lead_time_median), d1(r.lead_time_median_model)] for k, r in qt.iterrows()]
    return table(pd.DataFrame(rows, columns=["Quarter shipped", "Jobs shipped, measured", "Jobs shipped, model", "On time, measured", "On time, model", "Difference (points)",
                                             "Median lead time, measured", "Median lead time, model"]))


def t_results(per, outcomes, names, verdicts=True):
    rows = []
    for sc in names:
        rows.append([sc] + ([A.VERDICT[sc]] if verdicts else []) + [band(A.diff(sc, m, per), d, 100 if p else 1) for m, _, d, p in outcomes])
    return table(pd.DataFrame(rows, columns=["Scenario"] + (["Verdict"] if verdicts else []) + [x[1] for x in outcomes]))


def t_levels(per):
    f_ = lambda m, d, p: (pc(A.mean(CURRENT, m, per)) if p else f"{A.mean(CURRENT, m, per):,.{d}f}")
    rows = [[lab.replace(" (points)", ""), f_(m, d, p)] for m, lab, d, p in A.OUTCOMES + A.FURTHER]
    return table(pd.DataFrame(rows, columns=["Outcome", "Current practice"]))


def t_scenarios(rows):
    return table(pd.DataFrame([r[:4] for r in rows], columns=["Scenario", "The change", "Cost", "Potential impact on on-time delivery"]))


def t_hold():
    rows = [[sc, d2(A.mean(sc, "release_hold_days")), band(A.diff(sc, "on_time_delivery"), 1, 100), band(A.diff(sc, "wip_mean"), 1), band(A.diff(sc, "brake_queue_mean"), 2),
             band(A.diff(sc, "lead_time_median"), 2)] for sc in A.RELEASE[:4]]
    return table(pd.DataFrame(rows, columns=["Scenario", "Mean working days held before release", "On-time delivery (points)", "Floor WIP (jobs)", "Queue per brake operation (days)",
                                             "Median lead time (days)"]))


def t_tower(t):
    rows = [[f"{i:%B} {i.day}, {i.year}", n0(r[CURRENT]), n0(r[TOWER])] for i, r in t.iterrows()]
    return table(pd.DataFrame(rows, columns=["Week of", "Jobs waiting at the lasers at the end of the day, current practice", "With the tower on L2"]))


def cost_row(m):
    brk = (f"{m['share']:.0%} ({n0(m['hours'])} hours)" if m["share"] == m["share"] and 0 <= m["share"] <= 1 else "none needed" if m["share"] == m["share"] and m["share"] < 0
           else "over 100%" if m["share"] == m["share"] else "no hours freed")
    return [usd(m["one_time"]), usd(m["added"]), usd(m["avoided"]), usd(m["throughput"]), usd(m["net"]), f"{m['payback']:.1f} years" if m["payback"] == m["payback"] else "none",
            f"{musd(m['npv'][0])} ({musd(m['npv'][1])} to {musd(m['npv'][2])})", brk]


COST_HEAD = ["One-time cost", "Added cost a year", "Overtime avoided a year", "Throughput value a year (assumption: 50% sold at 40% margin)", "Net a year", "Payback",
             "NPV (95% interval)", "Break-even share sold (hours a year)"]


def t_cost(rows, variant="year"):
    out = [[name(sc), ref if ref != CURRENT else "Current practice"] + cost_row(A.money(sc, ref, variant)) for sc, ref in rows]
    return table(pd.DataFrame(out, columns=["Change", "Measured against"] + COST_HEAD))


def t_cost_parts(rows, variant="year"):
    out = []
    for sc, ref in rows:
        m = A.money(sc, ref, variant)
        out.append([name(sc), usd(m["upkeep"]), usd(m["weld"]), usd(m["cell"]), usd(m["added_overtime"]), n0(m["freed"]), usd(m["net_without"]), musd(m["npv_without"])])
    return table(pd.DataFrame(out, columns=["Change", "Upkeep a year", "Weld second-shift labor", "Robotic cell operator", "Overtime added", "Constraint hours freed",
                                            "Net a year without throughput value", "NPV without throughput value"]))


def t_measures(rows):
    out = []
    for sc, ref in [(CURRENT, CURRENT)] + rows:
        v = lambda m: A.mean(sc, m)
        m = A.money(sc, ref) if sc != ref else None
        c90, c95 = A.lifted(sc, 0.90), A.lifted(sc, 0.95)
        out.append([name(sc), n0(m["freed"]) if m else "", d1(v("saturday_shifts")), n0(v("extended_hours")), n0(v("saturday_hours") + v("extended_hours")),
                    n0(v("weld_second_shift_hours")), n0(v("cell_hours")), n0(-chg(sc, "b3_setup_hours", "year", ref)) if m else "", n0(-chg(sc, "brake_setup_hours", "year", ref)) if m else "",
                    n0(-chg(sc, "brake_hours", "year", ref)) if m else "", n0(v("wip_mean")), n0(v("wip_standard_hours_worked")), n0(v("jobs_shipped")), musd(v("revenue_shipped")),
                    f"{c90[0]} ({musd(c90[1])})", f"{c95[0]} ({musd(c95[1])})", d1(v("saturday_hours_winter") / A.M["operators"])])
    return table(pd.DataFrame(out, columns=["Scenario", "Constraint hours freed", "Saturday shifts called", "Extended hours scheduled", "Overtime operator hours", "Weld second-shift hours",
                                            "Robotic cell hours", "B3 setup hours saved", "Brake setup hours saved", "Manual brake hours displaced", "Mean WIP (jobs)",
                                            "Mean WIP (standard hours worked)", "Jobs shipped", "Revenue shipped", f"Customers at or above 90% on time, of {len(A.REVENUE)} (their revenue)",
                                            "At or above 95% (their revenue)", "Weekend hours per brake operator, November to February"]))


def t_customers(scs):
    names = q("select customer_id, customer_name from staging.stg_erp__customers").set_index("customer_id")["customer_name"]
    r = pd.concat([A.customers(sc) for sc in scs], axis=1)
    rows = [[names[c], musd(A.REVENUE[c])] + [pc(r.loc[c, sc]) for sc in scs] for c in A.REVENUE.index]
    return table(pd.DataFrame(rows, columns=["Customer", f"Revenue shipped, {YEAR}"] + [name(sc) for sc in scs]))


def t_assumptions():
    M, O, L, F, NC, RH = A.M, A.O, A.L, A.F, A.NC, A.RH
    a = [["Brake utilization", f"{M['brake_utilization']:.3f}", "the capacity report"], ["Brake share of queue time", pc(M["brake_share_of_queue"], 0), "the capacity report"],
         ["Brake setups over standard", f"{n0(M['setups_over_per_week'])} hours a week", "the capacity report"], ["Brake setup hours", f"{n0(M['brake_setup_hours'])}, of which B3 {n0(M['b3_setup_hours'])}", "the marts"],
         ["Robotic weld utilization and queue per operation", f"{M['weld_utilization']:.3f}; {d2(M['weld_queue'])} days", "the capacity report"],
         ["Share of brake standard hours a robotic cell can run", pc(M["cell_share"], 0), "the marts (light, repeat parts in lots of 25 or more)"],
         ["Revenue shipped and brake machine hours", f"{usd(M['revenue'])}; {n0(M['brake_hours'])}", "the marts"], ["Revenue per brake hour", usd(M["revenue_per_brake_hour"]), "the marts"]]
    b = [[SETUP, usd(NC["setup_program_one_time"]), usd(NC["setup_program_annual"]), "Tooling carts, setup sheets and engineering time for the top 12 part-operations"],
         [CHANGER, usd(A.COSTS["changer"][0]), usd(A.COSTS["changer"][1]), f"Removes {O['press_brake_atc']['tool_change_reduction']:.0%} of tool changing, "
          f"{O['press_brake_atc']['tool_change_share_of_setup']:.0%} of a setup's hours, on B3"],
         [TOWER, usd(A.COSTS["tower"][0]), usd(A.COSTS["tower"][1]), f"{O['laser_tower']['added_laser_hours_per_week']} unattended laser hours a week after second shift"],
         [CELL, usd(A.COSTS["cell"][0]), usd(A.COSTS["cell"][1]), f"{O['robotic_bending_cell']['added_crewed_hours_per_week']} brake hours a week; an operator for "
          f"{O['robotic_bending_cell']['tending_labor_per_cell_hour']:.0%} of its hours"]]
    c = [["Labor rate, loaded", f"${L['labor_rate']:.0f} an hour"], ["Overtime", f"{1 + L['overtime_premium']:.1f} times the labor rate"], ["Second-shift differential", f"{NC['shift_differential']:.0%}"],
         ["Discount rate and horizon", f"{F['discount_rate']:.0%} over {F['horizon_years']} years, before tax, no residual value"],
         ["Freed brake hours sold", f"{RH['utilization_of_released_hours']:.0%}"], ["Margin on revenue per brake hour", f"{RH['contribution_margin_share']:.0%}"]]
    return (block(f"Measured inputs for {YEAR}", table(pd.DataFrame(a, columns=["Measured input", f"{YEAR}", "From"])))
            + block("Option costs, supplied by the shop", table(pd.DataFrame(b, columns=["Option", "One-time cost", "Upkeep a year", "What it does"])))
            + block("Rates, supplied by the shop", table(pd.DataFrame(c, columns=["Rate", "Value"]))))


# ── the report ──────────────────────────────────────────────────────────────
def build():
    T = Tables()
    M = A.M
    tol, wcs, (pct, curve), wk, bd, qt = A.tolerance(), A.work_centers(), A.lead_times(), A.weekly(), A.build(), A.quarters()
    money = {sc: A.money(sc, ref) for sc, ref in RETURN_ALL}
    ordinary = {sc: A.money(sc, ref, "ordinary") for sc, ref in RETURN_ALL}
    measured_otd = {per: float(tol[(tol["period"] == per) & (tol["measure"] == "on_time_delivery")]["measured"].iloc[0]) for per in ("year", "rest")}
    model_otd = {per: A.mean(CURRENT, "on_time_delivery", per) for per in ("year", "rest")}
    ten = tol[tol["within"].notna()]
    flow, capacity = link("lead"), link("capacity")
    sat_cost = {sc: A.money(sc)["added_overtime"] for sc in (SAT_ONE, SAT_BOTH)}
    # figures the page states from the record and from the capacity report as published
    laser_build = float(q(f"select avg(laser_utilization) from marts.mart_weekly_floor where week_start between date '{YEAR - 1}-11-18' and date '{YEAR - 1}-12-23'").iloc[0, 0])
    punch_ops = int(q(f"select count(*) from intermediate.int_operation_queue where is_first_op and work_center = 'punch' and year(first_start) = {YEAR}").iloc[0, 0])
    both_saturdays = int(q("""select count(*) from (select cast(t.start_ts as date) as d from intermediate.int_machine_time t
                              join staging.stg_erp__work_center_calendar c on c.calendar_date = cast(t.start_ts as date) and c.work_center = 'press_brake' and c.saturday
                              where t.work_center = 'press_brake' group by 1 having count(distinct t.machine_id) >= 2)""").iloc[0, 0])
    late_rest = int(q(f"select count(*) from marts.mart_job_lead_time where year(ship_date) = {YEAR} and quarter(ship_date) >= 2 and not on_time").iloc[0, 0])
    cap_text = re.sub(r"<[^>]+>", "", (DOCS / "reports" / f"{REPORTS['capacity'][0]}.html").read_text(encoding="utf8"))
    sat_one, sat_share, sat_two, sat_two_share = re.search(r"supplies ([\d.]+) machine hours, (\d+)% of the weekly gap; one with both B1 and B2 crewed supplies about (\d+), (\d+)%",
                                                           cap_text).groups()
    assert "these two machines have the shortest queue times" in cap_text

    T.add("tolerance", f"The model under current practice against measured {YEAR}, with the tolerances set before the model was run", t_tolerance(tol))
    T.add("shop", "The model against the shop: work centers, lead-time percentiles, quarters shipped and the weeks of the year-end build",
          block(f"Work centers, {YEAR}", t_work_centers(wcs)) + block("Lead time of jobs shipped", t_lead(pct)) + block("By quarter shipped", t_quarters(qt))
          + block(f"By week, October {YEAR - 1} to June {YEAR}", t_weeks(wk))
          + "<p>Queue is working days from the end of the previous operation to the start; for the lasers and the punch, the first-operation queue. The powder coat queue includes "
            "the wait for the color day. The record does not separate extended-shift brake hours from weekday hours.</p>")
    T.add("assume", "Measured inputs and option assumptions", t_assumptions())
    T.add("modelled", "How Each Scenario Is Modelled", "")
    T.add("hold", "Release hold under the WIP caps and constraint-paced release", t_hold())
    T.add("year", f"Scenario results, {YEAR}: current practice, and each scenario as a difference from it with 95% intervals",
          block("Current practice", t_levels("year")) + block("Primary and supporting outcomes", t_results("year", A.OUTCOMES, A.EVERY))
          + block("Further outcomes", t_results("year", A.FURTHER, A.EVERY, False)))
    T.add("rest", f"Scenario results, {RT}: current practice, and each scenario as a difference from it with 95% intervals",
          block("Current practice", t_levels("rest")) + block("Primary and supporting outcomes", t_results("rest", A.OUTCOMES, A.EVERY))
          + block("Further outcomes", t_results("rest", A.FURTHER, A.EVERY, False)))
    T.add("tower", f"Jobs waiting at the lasers with and without the laser tower, weeks of November 4 to December 9, {YEAR - 1}", t_tower(A.tower_weeks()))
    T.add("measures", f"Measures behind the return, {YEAR}", t_measures(RETURN_ALL)
          + f"<p>Constraint hours freed are the manual brake machine hours of the reference less the scenario's, counted for the changes that take brake hours off the work. The "
            f"{len(A.REVENUE)} customers make up 80% of {YEAR} revenue. Weekend hours are Saturday brake hours crewed from November {YEAR - 1} to February {YEAR} over the "
            f"{M['operators']} brake operators.</p>")
    T.add("cost", f"Cost and return, every scenario that works, {YEAR} and an ordinary year",
          block(f"{YEAR}", t_cost(RETURN_ALL)) + block(f"{YEAR}, the parts of the added cost and the result without the throughput value", t_cost_parts(RETURN_ALL))
          + block("An ordinary year (the second half of the year, twice)", t_cost(RETURN_ALL, "ordinary"))
          + "<p>Capital options on top of the package are measured against the package. Earliest due date and planned Saturdays as crewed today carry no cost line of their own "
            "beyond overtime and are in the results tables.</p>")
    T.add("customers", f"On-time delivery by customer, {YEAR}: the customers making up 80% of revenue", t_customers([CURRENT, PACKAGE, WELD, P_CHANGER, P_CELL]))

    b = ["<h2 id='summary'>Executive Summary</h2>"]
    _pk, _cell = A.money(PACKAGE), A.money(P_CELL, PACKAGE)
    assert ten["within"].all() and bd["peak_week"] == bd["peak_week_model"]
    assert _pk["payback"] * 12 < 5 and _cell["npv"][0] > max(_pk["npv"][0], A.money(P_CHANGER, PACKAGE)["npv"][0], A.money(P_TOWER, PACKAGE)["npv"][0])
    b.append("<p>A discrete event simulation of the shop floor was built to test a range of scenarios aimed at raising on-time delivery. "
             f"The model replays every job released from January {YEAR - 1} through the shop's own routings, shift calendars, crewing, recorded downtime, and dispatch rules, "
             "and draws setup, run, move, and material times from the shop's recorded performance. "
             "This lets us measure the impact that each scenario has on on-time delivery and related measures: brake utilization and queue time, floor WIP, late jobs, and days late.</p>")
    b.append(f"<p>The model's accuracy was checked with a baseline run of every job with no changes, replicating the shop as it actually operated (the &quot;Status Quo&quot; scenario). "
             f"It reproduced {pc(ten['within'].mean(), 0)} of measures within tolerance, including {YEAR} on-time delivery of {pc(model_otd['year'])} against {pc(measured_otd['year'])} measured and a "
             f"year-end peak of {n0(bd['peak_model'])} jobs on the floor against {n0(bd['peak_measured'])} measured. <a href='#f4'>Section 4</a> gives the full validation.</p>")
    b.append("<p>We tested scenarios in two categories: (i) release and dispatch rules governing when work is released and the order in which it is run, and (ii) capacity changes that add "
             "machine hours. As shown below, the changes that add brake hours raised on-time delivery the most, while changes to release and dispatch had a neutral or negative impact.</p>")
    b.append(titled(fig_summary_effects(), f"Scenario Results: Change in On-time Delivery vs. Status Quo, {YEAR}"))
    b.append(f"<p>We compared the results of the scenarios individually and in specific combinations alongside their cost of implementation, NPV and payback periods. We found that the "
             f"<b>&quot;Operating Package&quot; (brake setup program + additional Saturday shifts on both brakes)</b> increased {YEAR} on-time delivery by "
             f"{chg(PACKAGE, 'on_time_delivery') * 100:.1f} points to {pc(A.mean(PACKAGE, 'on_time_delivery'))} without significant capital investment. Adding a robotic bending cell on top of "
             f"the Operating Package generated the highest return of all capital-intensive options tested, increasing on-time delivery another "
             f"{(A.mean(P_CELL, 'on_time_delivery') - A.mean(PACKAGE, 'on_time_delivery')) * 100:.1f} points to {pc(A.mean(P_CELL, 'on_time_delivery'))}. "
             f"<a href='#f2'>Sections 2</a> and <a href='#f3'>3</a> detail these results and ROI.</p>")
    b.append(titled(fig_summary_steps(_pk, _cell), f"On-time Delivery, Status Quo vs. Recommended Scenarios, {YEAR}"))
    b.append(f"<div class='caption'>Note: net present value and payback period assume {A.SOLD:.0%} of the freed brake hours are sold.</div>")
    # 1 ── the scenarios
    b.append("<h2 id='f1'>1. Simulations Tested</h2>")
    queue_days_share = re.search(r"the highest utilization with the least buffer, and (\d+)% of all queue days", cap_text).group(1)
    runs = A.ALL["replication"].nunique()
    assert runs == 30
    b.append("<p>We considered two broad categories of simulations intended to raise on-time delivery:</p>")
    b.append("<p><b>Release and dispatch scenarios</b> change the rules that govern how work enters and moves through the floor. These changes cost nothing to implement. If late jobs come "
             "from too much work on the floor, or from the wrong job going next at the brakes, these should move on-time delivery.</p>")
    b.append(f"<p><b>Capacity scenarios</b> add machine hours through operating changes or new equipment. These changes cost labor and/or capital. "
             f"{link('capacity', 'The capacity report')} finds that the brakes are the shop's primary constraint: they operate at the highest utilization with the least buffer, and hold "
             f"{queue_days_share}% of all queue days. Given this, we expect scenarios that add brake hours to move on-time delivery.</p>")
    b.append(f"<p>Each scenario changes only the inputs listed for it in the tables below; everything else stays as the shop operates today (the Status Quo). Each scenario and the "
             f"Status Quo were run {runs} times, each run with its own draws of setup, run, move and material times. <a href='#f2'>Section 2</a> presents the results. "
             f"{T.see('assume', 'modelled')}</p>")
    # late jobs against on-time jobs by stage, for the year (the flow report's stage table)
    _st = q("select stage, job_class, mean_days from marts.mart_lead_time_by_stage where period = 'year' and job_class in ('on time', 'late')").pivot(index="stage", columns="job_class", values="mean_days")
    _gap = _st["late"] - _st["on time"]
    assert _gap.idxmax() == "queue: press brake" and (_gap > 0).mean() > 0.5 and not (_gap > 0).all()
    wip_now = float(tol[(tol["period"] == "year") & (tol["measure"] == "wip_mean")]["measured"].iloc[0])
    cap_r, flow_r = "capacity report", "flow report"
    release = [
        ["WIP cap: 240, 210, and 180 jobs", "A job is released only when fewer jobs than the cap are on the floor.", "None", f"The floor carried {n0(wip_now)} jobs on average in {YEAR} ({flow_r}); fewer "
         f"jobs on the floor could mean shorter waits.", "Non-rush jobs wait at a release gate, in release order, until a job ships; rush jobs pass."],
        ["Brake constraint-paced release", "A job with brake work is released only when the brakes have 3 days of work or less waiting.", "None", f"The brakes hold {pc(M['brake_share_of_queue'], 0)} of "
         f"queue time ({cap_r}); pacing release to them could keep work from building there.", "Jobs with brake work wait at the gate while the brake backlog is over 3 days."],
        [EDD, "Every work center takes the job with the earliest due date next.", "None", f"Late jobs have longer lead times across most stages and most notably at the brakes ({flow_r}); taking the most urgent job first should "
         f"ship more of them on time.", "Rush first, then earliest due date, at every work center."],
        [RATIO, "Every work center takes rush jobs first, then the job with the lowest ratio of working days to its due date over standard hours of work remaining.", "None",
         "Earliest due date ignores how much work a job has left. The ratio moves jobs with the most work remaining against their due date to the front.",
         "Rush first, then the lowest ratio of time to the due date over standard hours remaining."],
        ["Shortest processing time at the brakes", "The brakes take the shortest job next.", "None", "Short jobs clear the queue fastest, which lowers the average wait.",
         "Rush first, then the least standard hours, at the brakes only."],
        ["Prioritize light work at B1 and B2", "B1 and B2 take light parts ahead of heavy ones when the other brakes are backed up.", "None",
         f"Precision and expedited work goes to B1 and B2, which have the shortest brake queues ({cap_r}); light work could use that room.", "When over 2 days of light and heavy work waits, B1 and B2 take light parts before heavy."],
        ["Third color day for black", "The powder line runs black on a third day each week.", "None", f"Powder coat operations wait {d1(M['powder_wait'])} days on average for their color day "
         f"({flow_r}).", "Black is added to the color schedule on Fridays."]]
    b.append(chart("Release and Dispatch Scenarios", t_scenarios(release)))
    cp = A.O["press_brake_atc"]
    capacity_rows = [
        [SETUP, "Setup standards, carts and sheets for the 12 part-operations with the most setup hours over standard; repeat setups assigned to the operators who know the part; a "
         "handover standard at shift change. Detailed in Section 3 of the capacity report.", f"{usd(A.COSTS['setup'][0])} once and {usd(A.COSTS['setup'][1])} a year", f"Brake setups run {n0(M['setups_over_per_week'])} hours a week over "
         f"standard, the largest single driver of elevated brake utilization.", "The 12 part-operations set up at standard; the other brake setups shorter by the assignment and handover hours measured."],
        ["Additional Saturday shifts", "A Saturday brake shift every week from November to February (historically the months with the recurring build). Two variants: as crewed today (one brake) and both B1 and B2 crewed.",
         f"Overtime of the added shifts: {usd(round(sat_cost[SAT_ONE], -2))} a year with one crew, {usd(round(sat_cost[SAT_BOTH], -2))} with both brakes",
         f"A Saturday shift as worked today supplies {sat_one} brake machine hours, {sat_share}% of the weekly gap in the build; with both brakes crewed "
         f"{sat_two_share}% ({cap_r}).",
         f"A Saturday shift every week from November through February: one brake at the Saturday yield, or B1 and B2 at the weekday yield."],
        [WELD, "A second shift on the robotic weld cell.", f"{usd(round(A.money(WELD)['weld'], -2))} a year of labor", f"The cell runs at {M['weld_utilization']:.2f} of its one shift with "
         f"{d1(M['weld_queue'])} days of queue per operation ({cap_r}).", "The cell is crewed for a second shift every working day."],
        [CHANGER, "A press brake with automatic tool changing in place of B3.", f"{usd(A.COSTS['changer'][0])} and {usd(A.COSTS['changer'][1])} a year", f"B3 ran {n0(M['b3_setup_hours'])} "
         f"setup hours in {YEAR}, and loading and unloading tooling is {cp['tool_change_share_of_setup']:.0%} of a setup.", f"Setups on B3 shorter by {cp['tool_change_share_of_setup'] * cp['tool_change_reduction']:.0%}."],
        [TOWER, "A second automated sheet tower, on L2.", f"{usd(A.COSTS['tower'][0])} and {usd(A.COSTS['tower'][1])} a year", f"The lasers ran at {laser_build:.2f} of crewed hours through the year-end "
         f"build ({flow_r}).", "L2 cuts unattended for 6 hours after second shift on every working day."],
        [CELL, "A robotic bending cell beside the five brakes.", f"{usd(A.COSTS['cell'][0])}, {usd(A.COSTS['cell'][1])} a year and an operator for half its hours",
         f"{pc(M['cell_share'], 0)} of brake standard hours are light, repeat parts in lots of 25 or more, which a cell can run.", "A sixth brake on two shifts at 70 hours a week that takes only those parts."],
        ["Operating package (combination)", "The setup program and planned Saturdays with both brakes crewed, together.",
         f"{usd(A.COSTS['setup'][0])} once, and {usd(round(A.COSTS['setup'][1] + sat_cost[SAT_BOTH], -2))} a year", "The two operating changes that add brake hours without capital.", "Both changes in one run."]]
    b.append(chart("Capacity Scenarios", t_scenarios(capacity_rows)))
    T.held["modelled"] = (T.held["modelled"][0], table(pd.DataFrame([[r[0], r[4]] for r in release + capacity_rows], columns=["Scenario", "How it is modelled"])))

    # 2 ── results
    b.append("<h2 id='f2'>2. Results</h2>")
    works_cap = [s for s in (SETUP, SAT_BOTH, CHANGER, CELL) if A.VERDICT[s] == "Works"]
    assert len(works_cap) == 4 and A.VERDICT[EDD] == "Works" and A.VERDICT[WELD] == "Works" and A.VERDICT[SAT_ONE] == "Works" and A.VERDICT[TOWER] == "No effect"
    assert [s for s in A.RELEASE if A.VERDICT[s] == "Works"] == [EDD] and all(A.VERDICT[s] == "Makes it worse" for s in A.RELEASE[:3] + [RATIO, "Shortest processing time at the brakes"])
    edd_late, edd_days = A.diff(EDD, "late_jobs"), A.diff(EDD, "days_late")
    assert edd_late[2] < 0 and edd_days[1] < 0 < edd_days[2]
    cap180 = A.RELEASE[2]
    b.append(f"<p>Each scenario was evaluated based on its impact on on-time delivery rates in {YEAR} and {RT}. As detailed in {link('lead', 'the flow report')}, this {RT} period "
             f"excludes the significant capacity constraints and backlog build in Q1, and so presents a view of the scenario's performance in more normalized operating periods.</p>")
    b.append(f"<p>Each result in this section is a scenario's average over its {runs} runs less the Status Quo's average over its {runs} runs, with a 95% confidence interval: the range "
             f"the true effect likely falls in. An effect is denoted positive or negative when the whole interval lies on one side of zero, and shows as no effect when the interval "
             f"crosses zero.</p>")
    b.append(f"<p>Among the release and dispatch rules, only earliest due date improved on-time delivery. The other release and dispatch scenarios had a neutral to negative impact. "
             f"The three WIP caps, the due-date ratio and shortest processing time at the brakes make on-time delivery worse, with the cap at 180 jobs reducing it by "
             f"{d1(-chg(cap180, 'on_time_delivery') * 100)} points, because the caps move the wait from the brakes to the release gate ({d1(A.mean(cap180, 'release_hold_days'))} days held) "
             f"without adding machine hours. {T.see('hold')}</p>")
    b.append(titled(fig_effects(A.RELEASE, "effects_release_dispatch", "Release and Dispatch"), "Release and Dispatch Scenarios: Change in On-Time Delivery vs. Status Quo"))

    low_cost = {d1(chg(s, "on_time_delivery") * 100) for s in (SETUP, SAT_BOTH)}
    assert len(low_cost) == 1 and max(chg(s, "on_time_delivery") for s in (WELD, TOWER)) < min(chg(s, "on_time_delivery") for s in (SETUP, SAT_BOTH, SAT_ONE, CHANGER, CELL))
    b.append(f"<p>Scenarios that added brake capacity improved on-time delivery. The lower cost options, the brake setup program detailed in {link('capacity', 'the capacity report')} and "
             f"additional Saturday shifts on both brakes, added {low_cost.pop()} points each to on-time delivery. The more capital intensive options, the robotic bending cell and "
             f"replacing brake B3, also yielded improvements ({d1(chg(CELL, 'on_time_delivery') * 100)} and {d1(chg(CHANGER, 'on_time_delivery') * 100)} points); they're analyzed in "
             f"more detail in <a href='#f3'>Section 3</a>. The scenarios impacting capacity at the robotic weld and laser cutting centers yielded less improvement in on-time delivery, "
             f"further validating the brakes as the shop's primary constraint.</p>")
    b.append(titled(fig_effects(A.CAPACITY, "effects_capacity", "Capacity"), "Capacity Scenarios: Change in On-Time Delivery vs. Status Quo"))

    on_top = {s: chg(s, "on_time_delivery", "year", PACKAGE) for s in (P_CELL, P_CHANGER, P_TOWER)}
    assert max(on_top, key=on_top.get) == P_CELL
    b.append(f"<p>Different combinations of scenarios were modelled, and one in particular yielded the best results. The &quot;Operating Package&quot; combines the brake setup program "
             f"and additional Saturday shifts on both brakes, the two low cost capacity scenarios. This combination added {d1(chg(PACKAGE, 'on_time_delivery') * 100)} points to on-time "
             f"delivery. On top of the Operating Package, the more capital-intensive scenarios were considered, with the robotic bending cell yielding the most significant further "
             f"improvement to on-time delivery.</p>")
    b.append(titled(fig_effects([PACKAGE, P_CELL, P_CHANGER, P_TOWER], "effects_combinations", "Combinations"), "Combination Scenarios: Change in On-Time Delivery vs. Status Quo"))

    b.append("<h3 id='f2_1'>Scenarios with Positive Impact on On-time Delivery</h3>")
    assert all(impact(A.diff(s, m), up) == "Positive Impact" for s in (SETUP, CHANGER, CELL) for m, _, _, _, up in PANELS)
    assert all(impact(A.diff(s, "brake_utilization"), False) == "No effect" for s in (SAT_BOTH, SAT_ONE))
    assert impact(edd_late, False) == "Positive Impact" and impact(edd_days, False) == "No effect" and chg(EDD, "on_time_delivery") < min(chg(s, "on_time_delivery") for s in (SETUP, SAT_BOTH, CHANGER, CELL))
    shown = pd.DataFrame({"gain": [chg(s, "on_time_delivery") for s in WORKING + [PACKAGE, P_CELL, P_CHANGER, P_TOWER]],
                          "queue": [chg(s, "brake_queue_mean") for s in WORKING + [PACKAGE, P_CELL, P_CHANGER, P_TOWER]]}).rank()
    assert shown["gain"].corr(shown["queue"]) < -0.9
    b.append(f"<p>Scenarios that improved on-time delivery are shown below alongside their impact on other delivery mechanism and outcome metrics. Changes that free brake capacity "
             f"(brake setup program, replacing press brake B3, and the new robotic bending cell) saw improvements across the board: decreased brake utilization, lower queue times per "
             f"operation, reduced floor WIP, and improvements in both number of late jobs and total days late. Additional Saturdays reach a similar result by adding hours rather than "
             f"removing work, so the brakes stay as busy as before and utilization is unchanged. Earliest due date reorders work without adding capacity, so its gain is smaller: it moves "
             f"jobs about to miss ahead of jobs due later, which removes late jobs but not days late, as the jobs it delays are later when they miss. Across all scenarios, the gain in "
             f"on-time delivery follows the cut in brake queue time. {T.see('year', 'rest', 'tower')}</p>")
    b.append(titled(fig_changes(), f"Scenario Analysis: Improvements vs. Status Quo, {YEAR}, With 95% Intervals"))

    pk, pkr = A.diff(PACKAGE, "on_time_delivery"), A.diff(PACKAGE, "on_time_delivery", "rest")

    # 3 ── return
    b.append("<h2 id='f3'>3. ROI & Other Considerations</h2>")
    mp, mc, mt, mw = money[PACKAGE], money[P_CELL], money[P_CHANGER], money[WELD]
    ms, mca, mta = money[SETUP], money[CELL], money[CHANGER]
    assert all(money[sc]["net_without"] < 0 for sc, _ in RETURN) and mt["npv"][2] < 0 and mc["npv"][1] > 0
    five = (SETUP, SAT_BOTH, CHANGER, CELL, PACKAGE)
    assert all(impact(A.diff(s, m), up) == "Positive Impact" for s in five for m, _, _, _, up in PANELS if m != "brake_utilization")
    assert money[SAT_BOTH]["freed"] == 0 and money[SAT_BOTH]["npv"][2] < 0 and ms["npv"][0] > mp["npv"][0] and mta["npv"][1] < 0 < mta["npv"][2]
    gain = lambda s: f"{sg(chg(s, 'on_time_delivery') * 100)}"
    b.append(f"<p>Five changes improved on-time delivery in {YEAR} and moved the delivery mechanisms and outcomes with it: the brake setup program ({gain(SETUP)} points), planned "
             f"Saturdays on both brakes ({gain(SAT_BOTH)}), the tool-changing brake ({gain(CHANGER)}), the robotic bending cell ({gain(CELL)}), and the operating package, which combines "
             f"the first two ({gain(PACKAGE)}). Each shortened the brake queue, took jobs off the floor, and cut both late jobs and days late.</p>")
    b.append(f"<p>This section lays out the costs and expected return of each change. The return is the brake hours a change frees, valued at half of them sold at a "
             f"{A.RH['contribution_margin_share']:.0%} margin, plus overtime avoided, less what the change costs to run; NPV is that value over {A.F['horizon_years']} years discounted at "
             f"{A.F['discount_rate']:.0%}, less the one-time cost, before tax. On-time delivery itself is not priced, so a change that adds hours rather than freeing them, such as planned "
             f"Saturdays, shows a cost and no return. {T.see('measures', 'cost')}</p>")
    assert A.SOLD == 0.5
    b.append(titled(fig_npv(money), f"What Makes Up Each Option's NPV, {YEAR}"))

    # the share of freed hours at which each option breaks even, and at which the cell on top of the package passes the package
    low, high = sorted((ms["share"], mp["share"]))
    line = lambda m: (-m["one_time"] + m["net_without"] * A.ANNUITY, m["freed"] * A.VALUE_PER_HOUR * A.ANNUITY)
    (p0, p1), (c0, c1) = line(mp), line(mc)
    passes = (p0 - c0) / (c1 - p1)
    assert 0.2 < min(mc["share"], mca["share"]) and max(mc["share"], mca["share"]) < 0.27 and 0.275 < passes < 0.325 and min(mt["share"], mta["share"]) > 0.495
    b.append(f"<p>The setup program and the operating package pay for themselves if even {low * 100:.0f} to {pc(high, 0)} of the brake hours they free are sold. The robotic bending cell "
             f"needs about a quarter of its freed hours sold to break even, and returns more than the package once the shop sells roughly {round(passes * 20) * 5}%, while the "
             f"tool-changing brake needs half or more.</p>")
    b.append(titled(fig_sold(money), "NPV Against the Share of Freed Brake Hours Sold"))
    b.append(f"<p><b>The operating package is recommended first</b>: it raises on-time delivery {d1(chg(PACKAGE, 'on_time_delivery') * 100)} points; the {usd(mp['one_time'])} initial "
             f"investment and {usd(round(mp['added'], -2))} a year pay back in {d1(mp['payback'])} years and return {musd(mp['npv'][0])}. It returns less than the setup program alone "
             f"({musd(ms['npv'][0])}) because its Saturday shifts add overtime costs and free no machine hours, but adds "
             f"{d1((chg(PACKAGE, 'on_time_delivery') - chg(SETUP, 'on_time_delivery')) * 100)} more points of on-time delivery than the setup program alone. "
             f"<b>The robotic bending cell is the recommended capital investment option</b>: on top of the package it adds {d1(chg(P_CELL, 'on_time_delivery', 'year', PACKAGE) * 100)} "
             f"points and returns {musd(mc['npv'][0])} with a {d1(mc['payback'])}-year payback.</p>")

    b.append("<h3 id='f3_1'>Other Considerations</h3>")
    b.append(f"<p>Several effects of these changes are measured but not priced, and some are not measured at all. {T.see('customers')}</p>")
    base90 = A.lifted(CURRENT, 0.90)

    def freed_hours(sc, ref):
        """Operator hours freed with no change in hours paid: setup hours saved, or for the cell the manual brake hours displaced less its own operator's."""
        new = A.parts(sc) - A.parts(ref)
        if "cell" in new:
            h = -chg(sc, "brake_hours", "year", ref) - A.O["robotic_bending_cell"]["tending_labor_per_cell_hour"] * A.mean(sc, "cell_hours")
        elif new & {"setup", "changer"}:
            h = -chg(sc, "brake_setup_hours", "year", ref)
        else:
            return ""
        return f"Operator hours freed: {n0(h)}"

    def unpriced(sc, ref):
        """What is measured for a change and shown nowhere else: the chart of scenarios with positive impact carries on-time delivery, late jobs, days late and floor WIP."""
        c90, c95 = A.lifted(sc, 0.90), A.lifted(sc, 0.95)
        per = "rest" if sc == WELD else "year"
        lab = RT if sc == WELD else f"{YEAR}"
        items = [f"90th-percentile lead time, {lab}: {sg(chg(sc, 'lead_time_p90', per, ref), 1)} days",
                 f"Top customers at or above 90% on time: {c90[0]} of {len(A.REVENUE)} ({musd(c90[1])} of revenue), against {base90[0]} today",
                 f"Top customers at or above 95% on time: {c95[0]}",
                 freed_hours(sc, ref),
                 f"Weekend hours per brake operator, November to February: {d1(A.mean(sc, 'saturday_hours_winter') / M['operators'])}"]
        return "<ul style='margin:0;padding-left:18px'>" + "".join(f"<li>{x}</li>" for x in items if x) + "</ul>"

    sats = A.mean(SAT_BOTH, "saturday_hours_winter") / 8 / M["operators"]
    sats_now = A.mean(CURRENT, "saturday_hours_winter") / 8 / M["operators"]
    added_setup, added_setup_alone = chg(P_CELL, "brake_setup_hours", "year", PACKAGE), chg(CELL, "brake_setup_hours")
    cell_note = lambda h: (f"Runs only light, repeat parts in lots of 25 or more, so its value depends on that work staying {pc(M['cell_share'], 0)} of brake hours. Adds {n0(h)} setup hours a "
                           f"year to the manual brakes. Needs in-house programming skills. Gives headroom to quote more work. It is the largest sum at risk and cannot be reversed.")
    changer_note = "B3 is out of service while it is replaced. The effect is limited to B3's setups. One vendor maintains it."
    consider = {
        SETUP: "Depends on repeat setups going to the operators who know the part, and on a handover standard being kept. It narrows cross-training. It can be stopped at no cost.",
        SAT_BOTH: f"About {d1(sats)} Saturdays per brake operator from November to February, against {d1(sats_now)} today. Sustained weekend work raises fatigue, absence and turnover risk, "
                  f"while a planned shift is easier to staff than one called at short notice. The record has only {WORD[both_saturdays]} Saturdays with both brakes crewed.",
        PACKAGE: "Both of the above.",
        WELD: "One operator alone on the shift, with no programming or quality support on hand. The shop must hire for it and keep the post filled.",
        CELL: cell_note(added_setup_alone), P_CELL: cell_note(added_setup), CHANGER: changer_note, P_CHANGER: changer_note}
    assert added_setup > 0 and added_setup_alone > 0
    widths = "<colgroup><col style='width:17%'><col style='width:48%'><col style='width:35%'></colgroup>"
    b.append(chart("Measured but Not Priced, and Other Considerations",
                   table(pd.DataFrame([["Replace brake B3, on top of the package" if sc == P_CHANGER else name(sc), unpriced(sc, ref), consider[sc]] for sc, ref in NOT_PRICED], columns=["Change", "Measured, not priced", "Considerations"])
                         ).replace("<thead>", widths + "<thead>", 1)))


    # 4 ── model accuracy and validation
    b.append("<h2 id='f4'>4. Model Accuracy & Validation</h2>")
    b.append("<h3 id='f4_1'>How the model works</h3>")
    b.append(f"<p>The model takes each job as the shop released it and moves it through its routing, machine by machine, under the shop's shift calendars and dispatch rules. The "
             f"model uses actual production data for release dates, routings, standards, due dates, rush flags, and machine downtime. What varies from job to job, how long each setup "
             f"and run takes and how long a job waits for material, a move or outside processing, is drawn from the shop's {YEAR} distributions.</p>")
    ps = M["p_saturday"]
    TAKEN, DRAWN, ESTIMATED = "Taken from the record", f"Drawn from the shop's {YEAR} distributions", "Estimated from the record"
    rows = [
        ["Jobs", "Every job released from January 2024: release date, routing, setup and run standards, quantity, due date, rush flag and planned operation dates.", TAKEN],
        ["Machines and calendars", "Shift calendars by work center and day, the shifts each machine is crewed, every recorded downtime event and the powder color schedule.", TAKEN],
        ["Dispatch", "Rush first, then jobs due within 2 working days, then planned start. Brake classes by machine, setups grouped on the same tooling up to three in a row, and the "
         "10:00 daily list at the single-shift work centers.", TAKEN],
        ["Laser sheet grouping", "A job of two or more sheets is cut on arrival; a single-sheet job waits for a second job on its sheet or for 2 working days before its planned start.", ESTIMATED],
        ["Setup and run time", "Actual over standard by work center and size of operation; at the brakes by whether the setup is grouped and by lot size.", DRAWN],
        ["Waits between operations", "Material wait at the first operation by routing class; move and hold time by work center; outside processing time; complete to ship.", DRAWN],
        ["Brake hours worked", f"{M['brake_yield']:.3f} of crewed hours on an ordinary weekday, {M['holiday_yield']:.3f} in a holiday week, fitted on weeks with work waiting.", ESTIMATED],
        ["Saturday and extended brake shifts", f"A Saturday is called on {pc(ps[0], 0)} to {pc(ps[4], 0)} of Fridays by the jobs at the brakes, and worked on {pc(M['saturday_worked'], 0)} of those, "
         f"on one brake at {M['saturday_yield']:.3f} of its hours. An extended shift yields {M['extended_yield']:.3f} of its hours. All fitted on the record's shifts.", ESTIMATED],
        ["Laser hours worked", f"{M['laser_yield']:.3f} of crewed hours, fitted on weeks with over 90 jobs at the lasers.", ESTIMATED],
        ["Operator familiarity", "A reduction in brake setup time in proportion to the hours measured in the capacity report.", ESTIMATED]]
    b.append(chart("What the Model Uses", table(pd.DataFrame(rows, columns=["Element", "How it is modelled", "Source"]))))
    b.append("<p>Not modelled: scrap and rework as events, operator absence and assignment by name, holds as events, nests and sheets, quoting, and the customer's response to delivery; "
             "orders and due dates are those of the record under every scenario.</p>")

    b.append("<h3 id='f4_2'>Model accuracy</h3>")
    dq = (wcs["queue_model"] / wcs["queue_measured"] - 1)
    out_q = wcs[dq.abs() > 0.10].set_index("work_center")
    dp = (pct["model"] / pct["measured"] - 1)
    out_p = pct[dp.abs() > 0.10]
    assert list(out_q.index) == ["Laser (first operation)", "Punch (first operation)"] and len(out_p) == 1 and ten["within"].all() and len(ten) == 10
    assert (wcs["utilization_model"] / wcs["utilization_measured"] - 1).abs().max() < 0.10 and tol["difference"].abs().max() < 0.10
    op, punch_q, laser_q = out_p.iloc[0], out_q.loc["Punch (first operation)"], out_q.loc["Laser (first operation)"]
    assert op["percentile"] == 10 and op["period"] == "year"
    b.append(f"<p>The model reproduces the shop within tolerance on all ten measures set before it was run. Outside those ten, queue time at the punch ({d2(punch_q['queue_model'])} days "
             f"against {d2(punch_q['queue_measured'])}) and at the lasers ({d2(laser_q['queue_model'])} against {d2(laser_q['queue_measured'])}) and the 10th-percentile lead time for "
             f"{YEAR} ({d1(op['model'])} days against {d1(op['measured'])}) are the only figures more than 10% from measured. {T.see('tolerance', 'shop')}</p>")
    b.append(titled(fig_ten(ten), "Model Against Measured, the Ten Measures Set Before the Model Was Run"))
    b.append(f"<p>The brakes and the robotic weld cell, the two work centers that hold a queue, sit within {d1((wcs['utilization_model'] - wcs['utilization_measured']).iloc[:2].abs().max() * 100)} "
             f"points of measured utilization and {abs(dq.iloc[:2]).max() * 100:.0f}% of measured queue time.</p>")
    b.append(titled(fig_work_centers(wcs), f"Utilization and Queue Time by Work Center, Measured Against Model, {YEAR}"))
    p50, p90 = pct[(pct["period"] == "year") & (pct["percentile"] == 50)].iloc[0], pct[(pct["period"] == "year") & (pct["percentile"] == 90)].iloc[0]
    b.append(f"<p>The model's curve lies on the shop's in both periods: the {YEAR} median is {d1(p50['model'])} days against {d1(p50['measured'])} and the 90th percentile "
             f"{d1(p90['model'])} against {d1(p90['measured'])}.</p>")
    b.append(titled(fig_lead(pct, curve), "Lead Time of Jobs Shipped, Measured Against Model"))

    q1 = qt.loc[f"{YEAR}Q1"]
    q4 = qt.loc[f"{YEAR - 1}Q4"]
    lo300, lo250, lo220 = bd["below"][300], bd["below"][250], bd["below"][220]
    assert lo300[0] == lo300[1] and lo250[0] == lo250[1] and bd["peak_week"] == bd["peak_week_model"]
    oct_ = wk[(wk.index >= f"{YEAR - 1}-10-07") & (wk.index <= f"{YEAR - 1}-10-28")]
    b.append(f"<p>Through the year-end build, the model builds and clears the backlog as the shop did. Floor WIP peaks at {n0(bd['peak_model'])} jobs against {n0(bd['peak_measured'])}, both in the week of "
             f"{week(bd['peak_week'])}, falls below 300 in the week of {week(lo300[0])} and below 250 in the week of {week(lo250[0])} in both, and below 220 in the week of "
             f"{week(lo220[1])} against {week(lo220[0])}. The brakes worked {n0(bd['brake_hours_model'])} hours from December through March against {n0(bd['brake_hours_measured'])}, "
             f"{n0(bd['saturday_hours_model'])} of them on Saturdays against {n0(bd['saturday_hours_measured'])}, and jobs shipped in the first quarter were "
             f"{pc(q1['on_time_delivery_model'])} on time against {pc(q1['on_time_delivery'])}. The model enters the autumn heavier than the shop, with {n0(oct_['wip_model'].min())} to "
             f"{n0(oct_['wip_model'].max())} jobs on the floor in October against {n0(oct_['wip_measured'].min())} to {n0(oct_['wip_measured'].max())}, and ships {YEAR - 1} Q4 at "
             f"{pc(q4['on_time_delivery_model'])} on time against {pc(q4['on_time_delivery'])}; it has converged by the week of November 18.</p>")
    b.append(titled(fig_build(wk), f"Weekly WIP and Brake Queue Time Through the Year-End Build, Measured Against Model, October {YEAR - 1} to June {YEAR}"))


    b.append("<h2 id='appendix'>Appendix</h2>")
    b.append(T.appendix())
    toc = [("summary", "Executive Summary"), ("f1", "1. Simulations Tested"), ("f2", "2. Results"), ("f3", "3. ROI & Other Considerations"),
           ("f4", "4. Model Accuracy & Validation")]
    print(f"wrote {page('options', chr(10).join(b), toc, heading=REPORTS['options'][1])}: a summary and 4 sections, {len(T.order)} appendix tables")


def main():
    build()


if __name__ == "__main__":
    main()
