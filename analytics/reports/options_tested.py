"""What moves on-time delivery: the report.

Usage: python -m analytics.reports.options_tested
"""
import re

import numpy as np
import pandas as pd

from analytics.release_control import sections as R
from analytics.reports.combine import REPORTS
from analytics.reports.layout import Tables, block, chart, link, page, titled
from analytics.technology_roi import analysis as KA
from analytics.technology_roi import sections as K
from analytics.style.style import ACCENT, AMBER, BRAND_BLUE, GREY, LIGHT_BLUE, RED, fig, pct, save_conformed as save, sig, table

YEAR, REST = R.YEAR, R.REST
WORD = {5: "five", 7: "seven", 10: "ten"}
S0, S8, CHRONIC, NOCAP, SINGLE, PY, PR = R.S0, R.S8, R.CHRONIC, R.NOCAP, R.SINGLE, R.PY, R.PR
CAPS = SINGLE[:3]
PACED, EDD, CR, SPT, LIGHT, SHIFT, BLACK, SATURDAY = SINGLE[3:11]
ATC, TOWER, CELL, PACKAGE = K.ATC, K.TOWER, K.CELL, K.PACKAGE
TARGET = R.required * 100
RELEASE_ROWS = [("WIP cap 240", CAPS[0]), ("WIP cap 210", CAPS[1]), ("WIP cap 180", CAPS[2]), ("Constraint-paced release", PACED), ("Earliest due date", EDD),
                ("Critical ratio", CR), ("Shortest processing time at the brakes", SPT), ("Light work ahead of heavy on B1 and B2", LIGHT),
                ("Third color day for black", BLACK)]
CAPACITY_ROWS = [("Setup program", S8), ("Planned Saturday brake shifts" + "\n" + "(November to February)", SATURDAY), ("Second shift on the robotic weld cell", SHIFT),
                 ("Setup program and second shift", CHRONIC), ("Full package", NOCAP)]
PANELS = ((PY, f"{YEAR}"), (PR, f"Q2-Q4 {YEAR}"))


def otd(p, sc, col="mean"):
    return float(p.loc[(sc, "on_time_delivery"), col]) * 100


def signed(x):
    return R.sg(x)


def interval(r, scale=100):
    """The 95% interval of a difference: signed where it reaches below zero, plain where it does not."""
    lo, hi = float(sig(r["diff_low"] * scale)), float(sig(r["diff_high"] * scale))
    f = signed if round(lo, 1) < 0 else (lambda x: f"{abs(x):.1f}")
    return f"{f(lo)} to {f(hi)}"


def change(r):
    """A change in points with its sign, followed by its interval."""
    return f"{signed(r['diff'] * 100)} points ({interval(r)})"


# ── figures ─────────────────────────────────────────────────────────────────
def fig_model():
    """On-time delivery and median lead time by quarter shipped, measured and modelled, with the first quarter of the year marked."""
    d = R.QT
    x = np.arange(len(d))
    names = [f"{t[:4]} {t[4:]}" for t in d["quarter"]]
    k = int(d.index[d["quarter"] == f"{YEAR}Q1"][0])
    f, axes = fig(h=3.9, ncols=2, sharex=True)
    for ax, a, b_, scale, label, fmt in ((axes[0], "otd_m", "otd_s", 100, "On-time delivery", "{:.0f}%"), (axes[1], "med_m", "med_s", 1, "Median lead time, working days", "{:.1f}")):
        ax.axvspan(k - 0.5, k + 0.5, color=GREY, alpha=0.18, linewidth=0)
        m, s = sig(d[a].to_numpy(dtype=float) * scale), sig(d[b_].to_numpy(dtype=float) * scale)
        ax.plot(x, m, color=BRAND_BLUE, marker="o", linewidth=2.0, label="Measured")
        ax.plot(x, s, color=AMBER, marker="o", linewidth=2.0, label="Modelled")
        for v_, c, dx in ((m[k], BRAND_BLUE, -1), (s[k], AMBER, 1)):
            ax.annotate(fmt.format(v_), (k, v_), textcoords="offset points", xytext=(11 * dx, -3), ha="right" if dx < 0 else "left", fontsize=8.5, color=c)
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=25, ha="right")
        ax.set_ylabel(label)
        if scale == 100:
            ax.yaxis.set_major_formatter(lambda t, _: f"{t:.0f}%")
            ax.set_ylim(30, 100)
        else:
            ax.set_ylim(0, float(max(m.max(), s.max())) * 1.2)
    axes[0].text(0.56, 0.05, "First-quarter backlog:" + "\n" + "the model clears it faster" + "\n" + "than the shop did", transform=axes[0].transAxes, ha="left", va="bottom",
                 fontsize=8.5, color="#444444", linespacing=1.4)
    f.legend(*axes[0].get_legend_handles_labels(), frameon=False, fontsize=9, ncol=2, loc="lower center")
    f.tight_layout(rect=(0, 0.07, 1, 1))
    return save(f, "options_model_against_shop_by_quarter", f"The Model Against the Shop by Quarter, {names[0]} to {names[-1]}")


DOT_RANGE = [f(otd(p, sc, c) for p, _ in PANELS for _, sc in RELEASE_ROWS + CAPACITY_ROWS for c in ("diff_low", "diff_high")) for f in (min, max)]


def fig_dots(rows, name, title, h):
    """The change in on-time delivery for each scenario as a dot with its 95% interval, the year and the ordinary quarters side by side."""
    f, axes = fig(h=h, ncols=2, grid="x", sharey=True, sharex=True)
    y = np.arange(len(rows))[::-1]
    for ax, (p, label) in zip(axes, PANELS):
        x = sig([otd(p, sc, "diff") for _, sc in rows])
        lo, hi = sig([otd(p, sc, "diff_low") for _, sc in rows]), sig([otd(p, sc, "diff_high") for _, sc in rows])
        ax.axvline(0, color="#666666", linewidth=1.0)
        ax.hlines(y, lo, hi, color=ACCENT, linewidth=2.6, zorder=2)
        ax.plot(x, y, linestyle="none", marker="o", markersize=6.5, color=BRAND_BLUE, zorder=3)
        for xi, yi in zip(x, y):
            ax.text(xi, yi + 0.2, signed(float(xi)), ha="center", va="bottom", fontsize=8.5)
        ax.set_title(label, fontsize=10.5)
        ax.set_xlim(DOT_RANGE[0] - 1.5, DOT_RANGE[1] + 1.5)
        ax.set_ylim(-0.6, len(rows) - 0.3)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels([n for n, _ in rows])
    f.supxlabel("Change in on-time delivery, points", fontsize=10.5)
    f.tight_layout()
    return save(f, name, title)


def build_up(p):
    """On-time delivery under current practice, the points each lever adds as the package takes it on, and the package."""
    start = otd(p, S0)
    steps = [("Setup program", otd(p, S8, "diff")), ("Second shift", otd(p, CHRONIC, "diff") - otd(p, S8, "diff")),
             ("Planned Saturdays", otd(p, NOCAP, "diff") - otd(p, CHRONIC, "diff"))]
    assert abs(sum(s for _, s in steps) - otd(p, NOCAP, "diff")) < 1e-9 and abs(start + otd(p, NOCAP, "diff") - otd(p, NOCAP)) < 0.05
    return start, steps, otd(p, NOCAP)


FLOOR = 70          # the on-time axis of the column charts starts here, so that steps of a point can be read


def target_line(ax, n):
    ax.axhline(TARGET, color=RED, linewidth=1.2, linestyle="--")
    ax.text(n - 0.45, TARGET + 0.4, "Target", ha="right", va="bottom", fontsize=8.5, color=RED)
    ax.set_ylim(FLOOR, 100)
    ax.yaxis.set_major_formatter(lambda t, _: f"{t:.0f}%")


def fig_build_up():
    f, axes = fig(h=4.3, ncols=2, sharey=True)
    for ax, (p, label) in zip(axes, PANELS):
        start, steps, end = build_up(p)
        names = ["Current" + "\n" + "practice," + "\n" + "model"] + [n.replace(" ", "\n") + "\n" + signed(s) for n, s in steps] + ["Package"]
        ax.bar([0], [float(sig(start)) - FLOOR], bottom=FLOOR, width=0.6, color=LIGHT_BLUE)
        level = start
        for k, (_, s) in enumerate(steps, 1):
            ax.bar([k], [float(sig(s))], bottom=float(sig(level)), width=0.6, color=ACCENT)
            ax.plot([k - 1.3, k + 0.3], [float(sig(level))] * 2, color="#888888", linewidth=0.8)
            level += s
        ax.bar([len(steps) + 1], [float(sig(end)) - FLOOR], bottom=FLOOR, width=0.6, color=BRAND_BLUE)
        ax.text(0, start + 0.4, f"{start:.1f}%", ha="center", va="bottom", fontsize=9)
        ax.text(len(steps) + 1, end + 0.4, f"{end:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold")
        ax.set_xticks(range(len(names)))
        ax.set_xticklabels(names, fontsize=8.5)
        ax.set_title(label, fontsize=10.5)
        target_line(ax, len(names))
    axes[0].set_ylabel("On-time delivery")
    f.tight_layout()
    return save(f, "options_build_up_to_package", f"From Current Practice to the Operating Package, {YEAR} and Q2-Q4")


def closing_steps(fq, p):
    return [(f"Measured" + "\n" + f"{YEAR}", R.measured(fq)["on_time_delivery"] * 100), ("Model," + "\n" + "current practice", otd(p, S0)),
            ("With the" + "\n" + "package", otd(p, NOCAP)), ("With the" + "\n" + "package and" + "\n" + "quote table", R.v(p, NOCAP, "on_time_delivery_quote_table") * 100)]


def fig_steps():
    f, axes = fig(h=4.3, ncols=2, sharey=True)
    for ax, fq, (p, label) in zip(axes, (1, 2), PANELS):
        c = closing_steps(fq, p)
        x = np.arange(len(c))
        v = sig([r[1] for r in c])
        ax.bar(x, v - FLOOR, bottom=FLOOR, width=0.6, color=[GREY, LIGHT_BLUE, ACCENT, BRAND_BLUE])
        for xi, vi in zip(x, v):
            ax.text(xi, vi + 0.4, f"{vi:.1f}%", ha="center", va="bottom", fontsize=9)
        for k in range(1, len(c)):
            ax.text(k - 0.5, FLOOR + 2.2, signed(float(v[k] - v[k - 1])), ha="center", va="center", fontsize=8.5, color="#333333",
                    bbox=dict(facecolor="white", edgecolor="#CCCCCC", boxstyle="round,pad=0.25"))
        ax.set_xticks(x)
        ax.set_xticklabels([r[0] for r in c], fontsize=8.5)
        ax.set_title(label, fontsize=10.5)
        target_line(ax, len(c))
    axes[0].set_ylabel("On-time delivery")
    f.tight_layout()
    return save(f, "options_measured_to_target", f"From Measured to Target: What Each Step Closes, {YEAR} and Q2-Q4")


def fig_cost():
    """Change in on-time delivery for the year against one-time cost, the package and the three capital options."""
    rows = [("Operating package", PACKAGE, BRAND_BLUE), ("Tool changer on B3", ATC, ACCENT), ("Laser tower on L2", TOWER, GREY), ("Robotic bending cell", CELL, AMBER)]
    f, ax = fig(h=4.0, grid="both")
    for name, sc, color in rows:
        r = K.S.loc[(sc, "year", "on_time_delivery")]
        x, y = K.E[sc]["one_time"] / 1000, float(sig(r["diff"] * 100))
        lo, hi = float(sig(r["diff_low"] * 100)), float(sig(r["diff_high"] * 100))
        ax.vlines([x], [lo], [hi], color=color, linewidth=2.6)
        ax.plot([x], [y], marker="o", markersize=8, color=color)
        ax.annotate(f"{name}" + "\n" + f"{signed(y)} points, {K.usd(K.E[sc]['one_time'])}", (x, y), textcoords="offset points", xytext=(10, -4), fontsize=8.5, linespacing=1.4)
    ax.axhline(0, color="#666666", linewidth=1.0)
    ax.set_xlim(0, max(K.E[sc]["one_time"] for _, sc, _ in rows) / 1000 * 1.3)
    ax.xaxis.set_major_formatter(lambda t, _: f"${t * 1000:,.0f}")
    ax.set_xlabel("One-time cost")
    ax.set_ylabel("Change in on-time delivery, points")
    f.tight_layout()
    return save(f, "options_effect_against_cost", f"Effect on On-time Delivery Against One-time Cost, {YEAR}")


# ── the scenarios, for the appendix ─────────────────────────────────────────
def t_scenarios():
    O = K.O
    a = O["press_brake_atc"]
    rows = [
        ["Current practice", "Release at order entry; the daily dispatch list with rush and hot-list precedence; Saturday and extended brake shifts triggered by the "
                             "brake queue."],
        ["WIP cap 240, 210 and 180", "Non-rush jobs held in release order until the floor is below the cap; lead time still runs from the release date."],
        ["Constraint-paced release", "Jobs with brake work held while the work waiting at the brakes exceeds 3 days of crewed brake capacity."],
        ["Earliest due date", "After rush jobs, every work center runs the waiting job with the earliest promised date."],
        ["Critical ratio", "After rush jobs, every work center runs the waiting job with the least time to its promised date for the standard hours it has left."],
        ["Shortest processing time at the brakes", "After rush jobs, the brakes run the waiting job with the fewest standard hours; the other work centers keep "
                                                   "the dispatch list."],
        ["Light work ahead of heavy on B1 and B2", "B1 and B2 take light work after precision work when the B3 to B5 queue exceeds 2 days."],
        ["Third color day for black", "A third weekly color day for black at the powder line."],
        ["Setup program", f"The top 12 part-operations at standard, and the assignment and handover hours of the capacity report taken off the other brake setups "
                          f"in proportion: {K.d1(K.M['setup_levers_hours_per_week'])} brake hours a week."],
        ["Planned Saturday brake shifts", "A Saturday brake shift every week from November through February."],
        ["Second shift on the robotic weld cell", "The robotic weld cell crewed for a second shift."],
        ["Setup program and second shift", "The two together."],
        ["Operating package", "The setup program, the second shift on the robotic weld cell and the planned Saturday brake shifts together."],
        ["Tool changer on B3", f"A press brake with automatic tool changing in place of B3: setups on B3 multiplied by "
                               f"{1 - a['tool_change_share_of_setup'] * a['tool_change_reduction']:.4f}."],
        ["Laser tower on L2", "A second automated tower: 6 unattended hours after second shift on L2."],
        ["Robotic bending cell", f"A sixth brake on two shifts at {O['robotic_bending_cell']['added_crewed_hours_per_week'] / 80:.3f} availability that runs light, "
                                 f"repeat parts in lots of 25 or more."],
        ["Load-based quote table", "Promised dates restated from the quote table of the quoting report (routing class and brake backlog at release, never below the "
                                   "fixed quote); the floor is unchanged."],
    ]
    return table(pd.DataFrame(rows, columns=["Scenario", "How it is modelled"]))


def sources(html):
    """The report a measured input comes from, by its short name."""
    return re.sub(r"\[\[N:(\w+)\]\]", lambda m: REPORTS[m.group(1)][2], html)


def build():
    T = Tables()
    v, pts, d1, n0 = R.v, R.pts, R.d1, R.n0
    allsc = [S0] + SINGLE + [CHRONIC, NOCAP] + R.CAPCOMBO
    T.add("validation", f"The model under current practice against measured {YEAR}, with tolerances", R.t_validation())
    T.add("quarters", "The model against measured, by quarter shipped", R.t_quarters())
    T.add("scenarios", "Scenarios tested and how each is modelled", t_scenarios())
    T.add("hold", "Release hold under the WIP cap and constraint-paced release", R.t_hold())
    T.add("full_y", f"Scenario results, {YEAR}", R.t_full(PY, allsc))
    T.add("diff_y", f"Difference from current practice, {YEAR}", R.t_diff(PY, allsc[1:]))
    T.add("full_r", f"Scenario results, {YEAR} {REST}", R.t_full(PR, allsc))
    T.add("diff_r", f"Difference from current practice, {YEAR} {REST}", R.t_diff(PR, allsc[1:]))
    T.add("rules", "On-time delivery at the two promise rules", R.t_promise())
    T.add("packages", f"The packages against current practice and against the setup program alone, {YEAR} and {REST}", R.t_packages())
    E, EP, S, SP, M, F, RH = K.E, K.EP, K.S, K.SP, K.M, K.F, K.R
    N_ATC, N_CELL, N_ALL, ATC_ALL = K.N_ATC, K.N_CELL, K.N_ALL, K.ATC_ALL
    kv, kpts, usd, k, kn0, kd1, breakeven = K.v, K.pts, K.usd, K.k, K.n0, K.d1, K.breakeven
    options = [n for n in K.NAMES if n != K.S0]
    T.add("inputs", "Measured inputs and option assumptions",
          block(f"Measured inputs for {YEAR}, from the marts", sources(K.t_measured())) + block("Assumptions", K.t_assumptions()))
    T.add("effects", f"Each option against current practice, {YEAR} and {REST}, with 95% intervals", K.t_effects_body())
    for period, pl, tag in (("year", f"{YEAR}", "y"), (REST, f"{YEAR} {REST}", "r")):
        T.add(f"k_levels_{tag}", f"Capital options: scenario results, {pl}", K.t_levels(period))
        T.add(f"k_diff_{tag}", f"Capital options: difference from current practice, {pl}", K.t_effects(options, period))
        T.add(f"k_pkg_{tag}", f"On top of the operating package: difference from the package, {pl}", K.t_effects(K.ON_PKG + [N_ALL], period, SP))
    T.add("november", "The laser tower in the weeks of November 11 to December 1, 2024", K.t_november())
    T.add("money", f"Payback and NPV against current practice at {F['discount_rate']:.0%} over {K.HORIZON} years, before tax: overtime and labor alone, and with the "
                   f"throughput value of freed constraint hours", K.t_money([(n, E[n]) for n in K.BASE + [PACKAGE]]))
    T.add("money_pkg", "Each option added to the operating package: its own cost against what it adds beyond the package",
          K.t_money([(n, EP[n]) for n in K.ON_PKG], summary=SP))
    T.add("hours", "Hours behind the money lines, per year, against current practice", K.t_hours(options))
    T.add("money_all", "Payback and NPV against current practice, every scenario", K.t_money([(n, E[n]) for n in options], body=False))
    T.add("money_pkg_all", "Each option added to the operating package, with the sensitivity", K.t_money([(n, EP[n]) for n in K.ON_PKG + [N_ALL]], body=False, summary=SP))

    Q1 = R.Q1
    row = lambda p, sc, m="on_time_delivery": p.loc[(sc, m)]
    epk, ea, ec = E[PACKAGE], E[ATC], E[CELL]
    measured_year = R.measured(1)
    b = []

    # 1 ── the shop model
    b.append("<h2 id='f1'>1. The Shop Model</h2>")
    b.append(f"<p>On-time delivery is {pct(measured_year['on_time_delivery'], 0)} against a {TARGET:.0f}% target because jobs wait at the brakes and because jobs are "
             f"released late ({link('lead')}; {link('capacity')}). This report tests what the shop could do about the first cause, on a model of the shop: which "
             f"levers move on-time delivery, by how much, and at what cost. The model replays every job released from January 2024 to December {YEAR} with its "
             f"routing, standards, due date, rush flag, shift calendar, recorded downtime and the powder color schedule, drawing setup, run, material, move, hold, "
             f"outside-processing and ship times from their {YEAR} distributions. Each scenario runs {R.REPS} times; its effect is the paired difference from "
             f"current practice, reported with a 95% interval, in working days with scheduled Saturdays counted.</p>")
    hotter = v(PY, S0, "brake_utilization") - measured_year["brake_utilization"]
    assert R.V_TOL - R.V_IN == 1 and Q1["otd_s"] > Q1["otd_m"] and hotter > 0
    b.append(f"<p>The model reproduces {YEAR} within tolerance on {R.V_IN} of {R.V_TOL} measures. Its one miss is the first-quarter backlog, which it clears faster than "
             f"the shop did ({pct(Q1['otd_s'])} on time in Q1 against {pct(Q1['otd_m'])} measured; every other quarter within {R.OTHER_GAP * 100:.1f} points), so "
             f"effects on the first-quarter event are lower bounds. Its brakes run {hotter * 100:.0f} points hotter than measured "
             f"({pct(v(PY, S0, 'brake_utilization'), 0)} against {pct(measured_year['brake_utilization'], 0)}), so the effects of capacity levers in ordinary quarters "
             f"are slightly overstated. {T.see('validation', 'quarters')}</p>")
    model_title = f"The Model Against the Shop by Quarter, {R.QT['quarter'].iloc[0][:4]} {R.QT['quarter'].iloc[0][4:]} to {R.QT['quarter'].iloc[-1][:4]} {R.QT['quarter'].iloc[-1][4:]}"
    b.append(chart(model_title, fig_model()))

    # 2 ── release and dispatch
    b.append("<h2 id='f2'>2. Holding Work Back and Reordering It Does Not Help</h2>")
    assert all(row(p, c)["diff_high"] < 0 for p in (PY, PR) for c in CAPS + [PACED])
    b.append(f"<p>Capping release makes delivery worse at every level tested: a WIP cap at 240, 210 and 180 jobs lowers on-time delivery by {pts(PR, CAPS[0])}, "
             f"{pts(PR, CAPS[1])} and {pts(PR, CAPS[2])} points in {REST} ({pts(PY, CAPS[0])}, {pts(PY, CAPS[1])} and {pts(PY, CAPS[2])} for the year) and lengthens "
             f"the 90th-percentile lead time by {d1(v(PR, CAPS[0], 'lead_time_p90', 'diff'))} to {d1(v(PR, CAPS[2], 'lead_time_p90', 'diff'))} days. The floor "
             f"already carries less work than the quoted lead times allow in an ordinary quarter (the flow report), so a cap does not relieve the brakes; it moves "
             f"the wait to the release gate, where jobs sat {d1(R.hold(CAPS[0]))} to {d1(R.hold(CAPS[2]))} days. Pacing release to the brake backlog is "
             f"{pts(PR, PACED)} points worse in {REST} for the same reason. {T.see('scenarios', 'hold')}</p>")
    release_title = "Change in On-time Delivery by Release and Dispatch Scenario, With 95% Intervals"
    b.append(chart(release_title, fig_dots(RELEASE_ROWS, "options_release_and_dispatch_effects", release_title, 5.4)))
    b.append(titled(R.fig_cap(), "On-time Delivery Against Release Hold Under a WIP Cap"))
    ey, ly, by_ = row(PY, EDD), row(PY, LIGHT), row(PY, BLACK)
    assert ey["diff_low"] <= 0.0005 and row(PR, EDD)["diff_high"] < 0 and all(r["diff_low"] < 0 < r["diff_high"] for r in (ly, by_))
    assert all(row(p, sc)["diff_high"] < 0 for p in (PY, PR) for sc in (CR, SPT))
    b.append(f"<p>Reordering the work does not help either. Earliest due date is indistinguishable from the current list for the year "
             f"({signed(ey['diff'] * 100)} points, interval {interval(ey)}) and {pts(PR, EDD)} points worse in {REST}; critical ratio is {pts(PR, CR)} to "
             f"{pts(PY, CR)} points worse; shortest processing time at the brakes shortens the median and is {pts(PY, SPT)} to {pts(PR, SPT)} points worse on time, "
             f"shipping {n0(-v(PY, SPT, 'jobs_shipped', 'diff'))} fewer jobs. Running light work ahead of heavy on B1 and B2 ({signed(ly['diff'] * 100)}, interval "
             f"{interval(ly)}) and a third weekly color day for black ({signed(by_['diff'] * 100)}, {interval(by_)}) move nothing beyond their intervals. The shop's "
             f"dispatch list, with rush and hot-list precedence, is as good as any rule tested; release should not be capped and the list stays. "
             f"{T.span('full_y', 'diff_y', 'full_r', 'diff_r')}</p>")

    # 3 ── brake hours
    b.append("<h2 id='f3'>3. Adding Hours at the Brakes Does</h2>")
    sy, sr, sat, wr, wy, py_, pr_ = row(PY, S8), row(PR, S8), row(PY, SATURDAY), row(PR, SHIFT), row(PY, SHIFT), row(PY, NOCAP), row(PR, NOCAP)
    assert sy["diff_low"] > 0 and sat["diff_low"] > 0 and wr["diff_low"] > 0 and sr["diff_low"] < 0 < sr["diff_high"]
    b.append(f"<p>Every lever that adds or recovers brake hours raises on-time delivery, and three of them together, for {usd(epk['one_time'])}, take the year from "
             f"{pct(v(PY, S0, 'on_time_delivery'))} to {pct(v(PY, NOCAP, 'on_time_delivery'))}. The setup program of "
             f"{link('capacity', 'the capacity report')} (the top 12 part-operations at standard, repeat setups to a familiar operator, a handover standard: "
             f"{kd1(M['setup_levers_hours_per_week'])} brake hours a week) is the largest single lever: {change(sy)} for the year, a 90th-percentile lead time "
             f"{d1(-v(PY, S8, 'lead_time_p90', 'diff'))} days shorter, {n0(-v(PY, S8, 'wip_mean', 'diff'))} fewer jobs in WIP, and Saturday shifts down from "
             f"{n0(v(PY, S0, 'saturday_shifts'))} to {n0(v(PY, S8, 'saturday_shifts'))}. In {REST} it shortens the 90th percentile by "
             f"{d1(-v(PR, S8, 'lead_time_p90', 'diff'))} day but leaves on-time delivery where it was ({signed(sr['diff'] * 100)}, interval {interval(sr)}), because "
             f"the late jobs of an ordinary quarter were released late rather than held at the brakes. A planned Saturday brake shift every week from November "
             f"through February adds {change(sat)} for the year, a lower bound given the model's faster clearing of the backlog, for "
             f"{d1(v(PY, SATURDAY, 'saturday_shifts') - v(PY, S0, 'saturday_shifts'))} more Saturday shifts than the queue-triggered practice produced. A second "
             f"shift on the robotic weld cell adds {change(wr)} in {REST}, the one lever that moves an ordinary quarter, and {signed(wy['diff'] * 100)} "
             f"({interval(wy)}) for the year. {T.see('packages')}</p>")
    capacity_title = "Change in On-time Delivery by Capacity Lever, With 95% Intervals"
    b.append(chart(capacity_title, fig_dots(CAPACITY_ROWS, "options_capacity_lever_effects", capacity_title, 3.9)))
    alone = sum(otd(PY, sc, "diff") for sc in (S8, SHIFT, SATURDAY))
    sat_rest = otd(PR, NOCAP, "diff") - otd(PR, CHRONIC, "diff")
    fewer = sorted(-v(PR, sc, "jobs_shipped", "diff") for sc in (CHRONIC, NOCAP))
    assert all(PY.loc[(sc, "jobs_shipped"), "diff_low"] <= 0 <= PY.loc[(sc, "jobs_shipped"), "diff_high"] for sc in (CHRONIC, NOCAP))
    assert abs(sat_rest) < 0.1 and abs(alone - otd(PY, NOCAP, "diff")) < 1.5
    b.append(f"<p>The three levers are close to additive, which is why they make a package: singly they sum to {signed(alone)} points for the year, together they "
             f"deliver {signed(py_['diff'] * 100)} ({interval(py_)}), reaching {pct(v(PY, NOCAP, 'on_time_delivery'))} on time with a 90th-percentile lead time of "
             f"{d1(v(PY, NOCAP, 'lead_time_p90'))} days against {d1(v(PY, S0, 'lead_time_p90'))}. In {REST} the package reaches "
             f"{pct(v(PR, NOCAP, 'on_time_delivery'))} ({signed(pr_['diff'] * 100)}, {interval(pr_)}) and {d1(v(PR, NOCAP, 'lead_time_p90'))} days, and all of that "
             f"gain is the weld cell's second shift; planned Saturdays add nothing in those quarters because the peak they cover falls in Q4 and Q1. The package "
             f"ships the same number of jobs for the year as current practice and {n0(fewer[0])} to {n0(fewer[-1])} fewer in {REST}, because the first-quarter "
             f"backlog ships earlier under it. {T.see(again=('packages',))}</p>")
    b.append(chart(f"From Current Practice to the Operating Package, {YEAR} and Q2-Q4", fig_build_up()))
    b.append(f"<p>The package is three operating changes and {usd(epk['one_time'])}: the setup program, a crewed second shift on the robotic weld cell, and a planned "
             f"Saturday brake shift every week from November through February. It goes in first.</p>")

    # 4 ── capital options
    b.append("<h2 id='f4'>4. The Capital Options Against the Package</h2>")
    cy, ay, ty = S.loc[(CELL, "year", "on_time_delivery")], S.loc[(ATC, "year", "on_time_delivery")], S.loc[(TOWER, "year", "on_time_delivery")]
    assert all(kv(sc, "on_time_delivery", REST, "diff") < 0.01 for sc in K.BASE) and kv(PACKAGE, "on_time_delivery", col="diff") > kv(ATC, "on_time_delivery", col="diff")
    b.append(f"<p>Three capital options were run on the same model: a press brake with automatic tool changing in place of B3 ({usd(ea['one_time'])}), a second "
             f"automated laser tower on L2 ({usd(E[TOWER]['one_time'])}) and a robotic bending cell as a sixth brake ({usd(ec['one_time'])}). For the year the robotic "
             f"cell raises on-time delivery by {kpts(CELL)} points ({interval(cy)}), the tool changer by {kpts(ATC)} ({interval(ay)}) and the tower by {kpts(TOWER)} "
             f"({interval(ty)}), against {kpts(PACKAGE)} for the {usd(epk['one_time'])} package; in {REST} every capital option adds under a point "
             f"({kpts(ATC, REST)}, {kpts(TOWER, REST)} and {kpts(CELL, REST)}) against {kpts(PACKAGE, REST)} for the package. The package delivers more than the tool "
             f"changer and {pct(kv(PACKAGE, 'on_time_delivery', col='diff') / kv(CELL, 'on_time_delivery', col='diff'), 0)} of the cell's effect for "
             f"{pct(epk['one_time'] / ec['one_time'], 0)} of the cell's price. "
             f"{T.span('inputs', 'effects', 'k_levels_y', 'k_diff_y', 'k_levels_r', 'k_diff_r')}</p>")
    b.append(chart(f"Effect on On-time Delivery Against One-time Cost, {YEAR}", fig_cost()))
    on_tower, on_s0 = kv(TOWER, "on_time_released_nov_2024"), kv(K.S0, "on_time_released_nov_2024")
    assert abs(on_tower - on_s0) < 0.005 and abs(kv(ATC_ALL, "on_time_delivery", col="diff") - kv(CELL, "on_time_delivery", col="diff")) < 0.015
    either = f"{pct(on_tower)} on time either way" if pct(on_tower) == pct(on_s0) else f"{pct(on_tower)} on time against {pct(on_s0)}"
    b.append(f"<p>Each machine does one thing. The tool changer removes tool-change time on one brake: {kd1(ea['setup_hours_saved'] / KA.WEEKS)} setup hours a week, "
             f"about what the whole operating package recovers ({kd1(epk['setup_hours_saved'] / KA.WEEKS)}); covering all five brakes at the same price per machine "
             f"would match the cell. The robotic cell adds a sixth brake for the light, repeat work in lots of 25 or more, "
             f"{pct(M['cell_share_of_brake_standard_hours'], 0)} of brake standard hours; it works {kn0(ec['cell_hours'] / KA.WEEKS)} hours a week, takes "
             f"{kn0(ec['manual_brake_hours_displaced'] / KA.WEEKS)} a week off the manual brakes, removes {kd1(-kv(CELL, 'saturday_shifts', col='diff'))} of "
             f"{kn0(kv(K.S0, 'saturday_shifts'))} Saturday shifts and shortens the 90th-percentile lead time by {kd1(-kv(CELL, 'lead_time_p90', col='diff'))} days, "
             f"while adding {kn0(-ec['setup_hours_saved'])} setup hours a year to the manual brakes, which keep the short lots. The laser tower clears the laser "
             f"queue and changes nothing downstream: in the three weeks of the Q4 2024 build the jobs waiting at the lasers fall from "
             f"{kn0(kv(K.S0, 'laser_queue_nov_2024'))} to {kn0(kv(TOWER, 'laser_queue_nov_2024'))} a day and the jobs released in those weeks ship {either}, because "
             f"they then wait at the brakes; the package alone lifts those same jobs to {pct(kv(PACKAGE, 'on_time_released_nov_2024'))}. {T.see('november')}</p>")
    b.append(titled(K.fig_laser(), "Jobs Waiting at the Lasers by Day, November and December 2024"))
    assert RH["utilization_of_released_hours"] == 0.5 and epk["net_without_throughput"] < 0
    assert all(not (E[n]["payback_without_throughput"] <= K.HORIZON) for n in K.BASE)
    b.append(f"<p>On overtime and labor savings alone, no option pays back within {WORD[K.HORIZON]} years and the package is net negative "
             f"({k(-epk['net_without_throughput'])} a year, the second shift's labor). The case for any of them is the brake hours they free and whether those hours "
             f"are sold. If half the freed brake hours are sold at a {RH['contribution_margin_share']:.0%} margin, the robotic cell pays back in "
             f"{kd1(ec['payback_with_throughput'])} years, the tool changer in {kd1(ea['payback_with_throughput'])} and the package in "
             f"{kd1(epk['payback_with_throughput'])}; the tower frees no brake hours and never pays back. The break-even is low for the cell and the package and "
             f"high for the tool changer: NPV reaches zero at {breakeven(ec, False)} of the cell's freed hours sold ({kn0(ec['breakeven_hours'])} a year), "
             f"{breakeven(epk, False)} of the package's ({kn0(epk['breakeven_hours'])}) and {breakeven(ea, False)} of the tool changer's "
             f"({kn0(ea['breakeven_hours'])}). On top of the package, the cell adds {kpts(N_CELL, s=SP)} points for the year and the tool changer "
             f"{kpts(N_ATC, s=SP)}, with break-evens of {breakeven(EP[N_CELL], False)} ({kn0(EP[N_CELL]['breakeven_hours'])} hours a year) and "
             f"{breakeven(EP[N_ATC], False)} ({kn0(EP[N_ATC]['breakeven_hours'])}). Payback is the one-time cost over the net annual benefit; NPV discounts "
             f"{WORD[K.HORIZON]} years at {F['discount_rate']:.0%}, before tax, no residual value; rates and prices are the shop's. "
             f"{T.span('money', 'hours', 'money_all', 'money_pkg', 'k_pkg_y', 'k_pkg_r', 'money_pkg_all')}</p>")
    b.append(titled(K.fig_npv(), "NPV Against the Share of Freed Brake Hours Sold"))
    b.append(f"<p>Order of decisions: the package first. The robotic bending cell when the shop can show that {kn0(EP[N_CELL]['breakeven_hours'])} of the brake hours "
             f"it frees will be sold each year ({kn0(ec['breakeven_hours'])} without the package); it is the capital option with the largest effect and the lowest "
             f"break-even. The tool changer on B3 only if {breakeven(EP[N_ATC], False)} of its freed hours will be sold. The laser tower is not bought.</p>")

    # 5 ── the quote
    b.append("<h2 id='f5'>5. What the Floor Cannot Fix</h2>")
    qy, qr = v(PY, NOCAP, "on_time_delivery_quote_table"), v(PR, NOCAP, "on_time_delivery_quote_table")
    short = TARGET - otd(PR, NOCAP)
    assert qy > v(PY, NOCAP, "on_time_delivery") and qr > v(PR, NOCAP, "on_time_delivery") and 0 < short
    b.append(f"<p>With the package in place the year is at {pct(v(PY, NOCAP, 'on_time_delivery'))} and {REST} at {pct(v(PR, NOCAP, 'on_time_delivery'))}, "
             f"{short:.0f} points short of the {TARGET:.0f}% target in an ordinary quarter. The remaining late jobs were released late, and no capacity lever reaches "
             f"them: on the same floor, quoting from the load-based table of {link('quoting')} (routing class and brake backlog at release, never below the fixed "
             f"quote) lifts the year to {pct(qy)} and {REST} to {pct(qr)}, with {pct(v(PY, NOCAP, 'promises_longer_quote_table'), 0)} and "
             f"{pct(v(PR, NOCAP, 'promises_longer_quote_table'), 0)} of non-rush promised lead times longer than the fixed quote, and does so without changing "
             f"anything on the floor. Capacity closes the first-quarter gap; the quote closes most of what is left. {T.see('rules')}</p>")
    b.append(chart(f"From Measured to Target: What Each Step Closes, {YEAR} and Q2-Q4", fig_steps()))
    assert round(otd(PY, NOCAP, "diff")) == 6 and round((qy - v(PY, NOCAP, "on_time_delivery")) * 100) == 3
    b.append(f"<p>Three operating changes for {usd(epk['one_time'])} lift on-time delivery six points for the year; the quote table lifts it three more; the robotic "
             f"cell is the one capital purchase worth making once its freed hours can be sold. Holding work back, reordering it, and clearing the laser queue do not "
             f"move delivery, because the constraint is brake hours.</p>")

    b.append("<h2 id='appendix'>Appendix</h2>")
    b.append(T.appendix())
    toc = [("f1", "1. The Shop Model"), ("f2", "2. Holding Work Back and Reordering It Does Not Help"), ("f3", "3. Adding Hours at the Brakes Does"),
           ("f4", "4. The Capital Options Against the Package"), ("f5", "5. What the Floor Cannot Fix")]
    print(f"wrote {page('options', chr(10).join(b), toc)}: 5 sections, {len(T.order)} appendix tables")
    return T.order


def main():
    build()


if __name__ == "__main__":
    main()
