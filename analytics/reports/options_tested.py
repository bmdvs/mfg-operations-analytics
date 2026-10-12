"""Discrete event simulation of on-time delivery: the report.

Usage: python -m analytics.reports.options_tested
"""
import re

import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from analytics.db import q
from analytics.release_control import analysis as A
from analytics.reports.combine import REPORTS
from analytics.reports.layout import RT, Tables, block, chart, link, page, titled
from analytics.style.style import AMBER, BRAND_BLUE, DOCS, GREEN, GREY, LIGHT_BLUE, RED, fig, save_conformed as save, table

YEAR = A.YEAR
CURRENT, PACKAGE = A.CURRENT, A.PACKAGE
SETUP, SAT_ONE, SAT_BOTH, WELD, CHANGER, TOWER, CELL, EDD = ("Setup program", "Planned Saturdays, as crewed today", "Planned Saturdays, both brakes crewed", "Weld cell second shift",
                                                             "Tool changer on B3", "Laser tower on L2", "Robotic bending cell", "Earliest due date")
P_CHANGER, P_TOWER, P_CELL, P_EDD = A.COMBOS
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


def fig_effects():
    f, axes = fig(h=6.2, ncols=2, grid="x", sharey=True)
    groups = [("Release and dispatch", sorted(A.RELEASE, key=lambda s: -chg(s, "on_time_delivery"))), ("Capacity", sorted(A.CAPACITY, key=lambda s: -chg(s, "on_time_delivery")))]
    rows, y, ticks, heads = [], 0, [], []
    for g, names in groups:
        heads.append((y, g))
        y -= 1
        for s in names:
            rows.append((y, s))
            ticks.append((y, s))
            y -= 1
        y -= 0.5
    for ax, (per, lab) in zip(axes, PERIODS):
        ax.axvline(0, color="#333333", lw=1)
        for yi, s in rows:
            t = [v * 100 for v in A.diff(s, "on_time_delivery", per)]
            ax.barh(yi, t[0], 0.62, color=COLOR[A.VERDICT[s]])
            ax.plot([t[1], t[2]], [yi, yi], color="#222222", lw=1.2)
        ax.set_title(lab, fontsize=10)
        ax.set_xlabel("Change in on-time delivery (points)")
    axes[0].set_yticks([t[0] for t in ticks] + [h[0] for h in heads])
    axes[0].set_yticklabels([t[1] for t in ticks] + [h[1].upper() for h in heads], fontsize=8.5)
    for lab_ in axes[0].get_yticklabels()[len(ticks):]:
        lab_.set_fontweight("bold")
    f.legend([Patch(color=c) for c in COLOR.values()] + [Line2D([], [], color="#222222", lw=1.2)], list(COLOR) + ["95% interval"], frameon=False, fontsize=9, ncol=4, loc="lower center")
    f.tight_layout(rect=(0, 0.04, 1, 1))
    return save(f, "scenario_effects", "")


def fig_build_up():
    f, axes = fig(h=3.4, ncols=2, sharey=True)
    for ax, (per, lab) in zip(axes, PERIODS):
        base = A.mean(CURRENT, "on_time_delivery", per) * 100
        steps = [("Current" + "\n" + "practice", base, GREY), ("Setup" + "\n" + "program", A.mean(SETUP, "on_time_delivery", per) * 100, LIGHT_BLUE),
                 ("Planned Saturdays," + "\n" + "both brakes", A.mean(SAT_BOTH, "on_time_delivery", per) * 100, LIGHT_BLUE),
                 ("Operating" + "\n" + "package", A.mean(PACKAGE, "on_time_delivery", per) * 100, BRAND_BLUE)]
        for k, (_, v, c) in enumerate(steps):
            ax.bar(k, v, 0.62, color=c)
            ax.annotate(f"{v:.1f}%", (k, v), textcoords="offset points", xytext=(0, 2), ha="center", fontsize=8.5)
        ax.axhline(95, color=RED, lw=1, ls="--")
        ax.annotate("95% target", (3.4, 95), textcoords="offset points", xytext=(0, 3), ha="right", fontsize=8, color=RED)
        ax.set_xticks(range(len(steps)))
        ax.set_xticklabels([s[0] for s in steps], fontsize=8.5)
        ax.set_title(lab, fontsize=10)
        ax.set_ylim(70, 100)
    axes[0].set_ylabel("On-time delivery (%)")
    f.tight_layout()
    return save(f, "package_build_up", "")


def fig_capital():
    f, ax = fig(h=3.2, grid="x")
    rows = [(CHANGER, P_CHANGER, "Tool changer on B3"), (TOWER, P_TOWER, "Laser tower on L2"), (CELL, P_CELL, "Robotic bending cell")]
    y = np.arange(len(rows))[::-1] * 1.0
    ax.axvline(0, color="#333333", lw=1)
    for yi, (alone, top, _) in zip(y, rows):
        for off, t, c in ((0.17, A.diff(alone, "on_time_delivery"), LIGHT_BLUE), (-0.17, A.diff(top, "on_time_delivery", "year", PACKAGE), BRAND_BLUE)):
            t = [v * 100 for v in t]
            ax.plot([t[1], t[2]], [yi + off, yi + off], color=c, lw=2.2)
            ax.scatter([t[0]], [yi + off], color=c, s=40, zorder=3)
            ax.annotate(f"{t[0]:+.1f}", (t[2], yi + off), textcoords="offset points", xytext=(5, 0), va="center", fontsize=8.5)
    ax.set_yticks(y)
    ax.set_yticklabels([r[2] for r in rows], fontsize=9)
    ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.set_xlabel(f"Change in on-time delivery, {YEAR} (points, with 95% interval)")
    ax.legend([Line2D([], [], color=LIGHT_BLUE, lw=2.2, marker="o"), Line2D([], [], color=BRAND_BLUE, lw=2.2, marker="o")],
              ["Alone, against current practice", "On top of the operating package, against the package"], frameon=False, fontsize=9, ncol=2)
    f.tight_layout()
    return save(f, "capital_options_alone_and_on_package", "")


def fig_npv(money):
    f, ax = fig(h=3.6, grid="x")
    y = np.arange(len(RETURN))[::-1]
    for yi, (sc, ref) in zip(y, RETURN):
        m = money[sc]
        left = 0.0
        for v, c in ((m["one_time"], RED), (m["added"] * A.ANNUITY, AMBER)):
            ax.barh(yi, -v / 1e6, 0.55, left=left, color=c)
            left -= v / 1e6
        right = 0.0
        for v, c in ((m["avoided"] * A.ANNUITY, LIGHT_BLUE), (m["throughput"] * A.ANNUITY, BRAND_BLUE)):
            ax.barh(yi, v / 1e6, 0.55, left=right, color=c)
            right += v / 1e6
        t = [v / 1e6 for v in m["npv"]]
        ax.plot([t[1], t[2]], [yi, yi], color="#111111", lw=1.4, zorder=4)
        ax.scatter([t[0]], [yi], marker="D", color="#111111", s=34, zorder=5)
        ax.annotate(musd(m["npv"][0]), (max(right, t[2]), yi), textcoords="offset points", xytext=(6, 0), va="center", fontsize=8.5)
    ax.axvline(0, color="#333333", lw=1)
    ax.set_yticks(y)
    ax.set_yticklabels([name(sc) for sc, _ in RETURN], fontsize=9)
    ax.set_xlabel(f"Present value over {A.F['horizon_years']} years at {A.F['discount_rate']:.0%} ($ million)")
    lo, hi = ax.get_xlim()
    ax.set_xlim(lo, hi + (hi - lo) * 0.08)
    ax.legend([Patch(color=RED), Patch(color=AMBER), Patch(color=LIGHT_BLUE), Patch(color=BRAND_BLUE), Line2D([], [], color="#111111", marker="D", lw=1.4)],
              ["One-time cost", "Added cost", "Overtime avoided", "Throughput value (50% sold)", "NPV, with 95% interval"], frameon=False, fontsize=8.5, ncol=5)
    f.tight_layout()
    return save(f, "return_npv_parts", "")


def fig_sold(money):
    f, ax = fig(h=3.8)
    x = np.linspace(0, 1, 41)
    colors = {SETUP: LIGHT_BLUE, PACKAGE: BRAND_BLUE, P_CELL: GREEN, P_CHANGER: AMBER, WELD: GREY, SAT_BOTH: RED}
    for sc, ref in RETURN:
        m = money[sc]
        v = np.array([A.npv_at(m, s) for s in x]) / 1e6
        even = m["share"] == m["share"] and 0 < m["share"] < 1
        ax.plot(x * 100, v[:, 0], color=colors[sc], lw=1.8, label=name(sc) + (f": breaks even at {n0(m['hours'])} hours a year" if even else ""))
        ax.fill_between(x * 100, v[:, 1], v[:, 2], color=colors[sc], alpha=0.15, lw=0)
        if even:
            ax.scatter([m["share"] * 100], [0], color=colors[sc], s=30, zorder=5)
    ax.axhline(0, color="#333333", lw=1)
    ax.axvline(A.SOLD * 100, color=GREY, lw=1, ls="--")
    ax.annotate("50% assumed", (A.SOLD * 100, ax.get_ylim()[1]), textcoords="offset points", xytext=(4, -10), fontsize=8, color="#555555")
    ax.set_xlabel("Share of freed brake hours sold (%)")
    ax.set_ylabel("NPV ($ million)")
    f.legend(*ax.get_legend_handles_labels(), frameon=False, fontsize=8.5, ncol=2, loc="lower center")
    f.tight_layout(rect=(0, 0.14, 1, 1))
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
    return table(pd.DataFrame(rows, columns=["Scenario", "The change", "Cost", "Why it could help", "How it is modelled"]))


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
    b = [["Setup program", usd(NC["setup_program_one_time"]), usd(NC["setup_program_annual"]), "Tooling carts, setup sheets and engineering time for the top 12 part-operations"],
         ["Tool changer on B3", usd(A.COSTS["changer"][0]), usd(A.COSTS["changer"][1]), f"Removes {O['press_brake_atc']['tool_change_reduction']:.0%} of tool changing, "
          f"{O['press_brake_atc']['tool_change_share_of_setup']:.0%} of a setup's hours, on B3"],
         ["Laser tower on L2", usd(A.COSTS["tower"][0]), usd(A.COSTS["tower"][1]), f"{O['laser_tower']['added_laser_hours_per_week']} unattended laser hours a week after second shift"],
         ["Robotic bending cell", usd(A.COSTS["cell"][0]), usd(A.COSTS["cell"][1]), f"{O['robotic_bending_cell']['added_crewed_hours_per_week']} brake hours a week; an operator for "
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
    T.add("hold", "Release hold under the WIP caps and constraint-paced release", t_hold())
    T.add("year", f"Scenario results, {YEAR}: current practice, and each scenario's further outcomes as a difference from it with 95% intervals",
          block("Current practice", t_levels("year")) + block("Further outcomes, difference from current practice", t_results("year", A.FURTHER, A.EVERY, False)))
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

    b = []
    # 1 ── the shop model
    b.append("<h2 id='f1'>1. The Shop Model</h2>")
    b.append(f"<p>On-time delivery was {pc(measured_otd['year'], 0)} in {YEAR} against a 95% target because jobs wait at the brakes and because jobs are released late ({flow}; "
             f"{capacity}). The record shows what happened under the shop's practice; it cannot show what would have happened under another. This report answers that question with a "
             f"discrete event simulation of the shop that replays the jobs the shop actually released in {YEAR - 1} and {YEAR} through a floor whose rules can be changed, one at a time, "
             f"while the demand stays the same.</p>")
    b.append("<h3 id='f1_1'>How the model works</h3>")
    b.append(f"<p>The model takes each job as the shop released it and moves it through its routing, machine by machine, under the shop's shift calendars and dispatch rules. What the "
             f"record fixes, the model keeps: release dates, routings, standards, due dates and rush flags are those of the actual jobs, and machine downtime is the recorded downtime. "
             f"What varies from job to job, how long each setup and run takes and how long a job waits for material, a move or outside processing, is drawn from the shop's {YEAR} "
             f"distributions. The behaviours the record does not state as rules are estimated from it: how fully the brakes are crewed when work is waiting, and when and how the shop "
             f"works a Saturday or an extended brake shift. Each scenario runs 30 times with different draws, and its effect is the difference from current practice, run for run, with "
             f"a 95% interval.</p>")
    ps = M["p_saturday"]
    rows = [
        ["Jobs", "Every job released from January 2024: release date, routing, setup and run standards, quantity, due date, rush flag and planned operation dates.", "", ""],
        ["Machines and calendars", "Shift calendars by work center and day, the shifts each machine is crewed, every recorded downtime event and the powder color schedule.", "", ""],
        ["Setup and run time", "", f"Actual over standard by work center and size of operation; at the brakes by whether the setup is grouped and by lot size. On {pc(M['no_setup_share'])} "
         f"of brake operations the setup is inside the run, as the record clocks it, so the setup program and the tool changer have no setup to shorten there and are understated by "
         f"about that share.", ""],
        ["Waits between operations", "", "Material wait at the first operation by routing class; move and hold time by work center; outside processing time; complete to ship.", ""],
        ["Dispatch", "Rush first, then jobs due within 2 working days, then planned start. Brake classes by machine, setups grouped on the same tooling up to three in a row, and the "
         "10:00 daily list at the single-shift work centers.", "", "A job of two or more sheets is cut on arrival; a single-sheet job waits for a second job on its sheet or for 2 working days before its planned start."],
        ["Brake hours worked", "", "", f"{M['brake_yield']:.3f} of crewed hours on an ordinary weekday, {M['holiday_yield']:.3f} in a holiday week, fitted on weeks with work waiting."],
        ["Saturday and extended brake shifts", "", "", f"A Saturday is called on {pc(ps[0], 0)} to {pc(ps[4], 0)} of Fridays by the jobs at the brakes, and worked on {pc(M['saturday_worked'], 0)} of those, "
         f"on one brake at {M['saturday_yield']:.3f} of its hours. An extended shift yields {M['extended_yield']:.3f} of its hours. All fitted on the record's shifts."],
        ["Laser hours worked", "", "", f"{M['laser_yield']:.3f} of crewed hours, fitted on weeks with over 90 jobs at the lasers."],
        ["Not modelled", "Scrap and rework as events, operator absence and assignment by name, holds as events, nests and sheets, quoting, and the customer's response to delivery: "
         "orders and due dates are those of the record under every scenario.", "", ""]]
    b.append(chart("What the Model Takes, Draws and Assumes", table(pd.DataFrame(rows, columns=["", "Taken from the record", f"Drawn from the shop's {YEAR} distributions", "Estimated or assumed"]))))
    b.append(f"<p>Operator familiarity enters as a reduction in brake setup time in proportion to the hours measured in {link('capacity', 'the capacity report')}.</p>")

    b.append(f"<h3 id='f1_2'>How well it reproduces {YEAR}</h3>")
    du = (wcs["utilization_model"] - wcs["utilization_measured"]).abs().max() * 100
    dq = (wcs["queue_model"] / wcs["queue_measured"] - 1)
    out_q = wcs[dq.abs() > 0.25]
    later = wcs.dropna(subset=["queue_days_model"])
    share_model = later.loc[later["work_center"] == "Press brake", "queue_days_model"].iloc[0] / later["queue_days_model"].sum()
    share_meas = M["brake_share_of_queue"]
    assert abs(share_model - share_meas) < 0.02
    dp = (pct["model"] / pct["measured"] - 1)
    out_p = pct[dp.abs() > 0.10]
    assert len(out_q) == 1 and len(out_p) == 1 and ten["within"].all()
    op, oq_ = out_p.iloc[0], out_q.iloc[0]
    b.append(f"<p>The model reproduces {YEAR} within tolerance on {WORD[int(ten['within'].sum())]} of the ten measures set before the model was run. Utilization is within "
             f"{d1(du)} points of measured at every work center, and queue time per operation is within 25% at every work center but the punch ({d2(oq_['queue_model'])} days against "
             f"{d2(oq_['queue_measured'])}), which takes {n0(punch_ops)} first operations a year. Lead-time percentiles from the 10th to the 95th are within 10% of measured except the 10th "
             f"for {YEAR} ({d1(op['model'])} days against {d1(op['measured'])}). On-time delivery is {pc(model_otd['year'])} against {pc(measured_otd['year'])} for {YEAR} and "
             f"{pc(model_otd['rest'])} against {pc(measured_otd['rest'])} in {RT}, and the brakes hold {pc(share_model, 0)} of queue time in the model against {pc(share_meas, 0)} in "
             f"the record, with the wait for the powder color day left out of both, the capacity report's basis. {T.see('tolerance', 'shop')}</p>")
    b.append(titled(fig_work_centers(wcs), f"Utilization and Queue Time by Work Center, Measured Against Model, {YEAR}"))
    b.append(f"<p>The brakes and the robotic weld cell, the two work centers that hold a queue, sit within {d1((wcs['utilization_model'] - wcs['utilization_measured']).iloc[:2].abs().max() * 100)} "
             f"points of measured utilization and {abs(dq.iloc[:2]).max() * 100:.0f}% of measured queue time.</p>")
    b.append(titled(fig_lead(pct, curve), "Lead Time of Jobs Shipped, Measured Against Model"))
    p50, p90 = pct[(pct["period"] == "year") & (pct["percentile"] == 50)].iloc[0], pct[(pct["period"] == "year") & (pct["percentile"] == 90)].iloc[0]
    b.append(f"<p>The model's curve lies on the shop's in both periods: the {YEAR} median is {d1(p50['model'])} days against {d1(p50['measured'])} and the 90th percentile "
             f"{d1(p90['model'])} against {d1(p90['measured'])}.</p>")

    b.append("<h3 id='f1_3'>The year-end build</h3>")
    q1 = qt.loc[f"{YEAR}Q1"]
    q4 = qt.loc[f"{YEAR - 1}Q4"]
    lo300, lo250, lo220 = bd["below"][300], bd["below"][250], bd["below"][220]
    assert lo300[0] == lo300[1] and lo250[0] == lo250[1] and bd["peak_week"] == bd["peak_week_model"]
    oct_ = wk[(wk.index >= f"{YEAR - 1}-10-07") & (wk.index <= f"{YEAR - 1}-10-28")]
    b.append(f"<p>The model builds and clears the year-end backlog as the shop did. Floor WIP peaks at {n0(bd['peak_model'])} jobs against {n0(bd['peak_measured'])}, both in the week of "
             f"{week(bd['peak_week'])}, falls below 300 in the week of {week(lo300[0])} and below 250 in the week of {week(lo250[0])} in both, and below 220 in the week of "
             f"{week(lo220[1])} against {week(lo220[0])}. The brakes worked {n0(bd['brake_hours_model'])} hours from December through March against {n0(bd['brake_hours_measured'])}, "
             f"{n0(bd['saturday_hours_model'])} of them on Saturdays against {n0(bd['saturday_hours_measured'])}, and jobs shipped in the first quarter were "
             f"{pc(q1['on_time_delivery_model'])} on time against {pc(q1['on_time_delivery'])}. The model enters the autumn heavier than the shop, with {n0(oct_['wip_model'].min())} to "
             f"{n0(oct_['wip_model'].max())} jobs on the floor in October against {n0(oct_['wip_measured'].min())} to {n0(oct_['wip_measured'].max())}, and ships {YEAR - 1} Q4 at "
             f"{pc(q4['on_time_delivery_model'])} on time against {pc(q4['on_time_delivery'])}; it has converged by the week of November 18.</p>")
    b.append(f"<p>Three effects in this report are not exact, and the direction of each is known. The setup program and the tool changer are understated by about 6%, because "
             f"{pc(M['no_setup_share'])} of brake operations carry their setup inside the run and leave nothing for either to shorten. Planned Saturdays with both brakes crewed are "
             f"likely overstated: both brakes are worked at the weekday yield of {M['brake_yield']:.3f}, the record has {WORD[both_saturdays]} Saturdays with both brakes crewed, and its one-brake "
             f"Saturdays yield {M['saturday_yield']:.3f}. Effects in {RT} are slightly generous throughout, because the model ships those quarters at {pc(model_otd['rest'])} against "
             f"{pc(measured_otd['rest'])} and so has about {n0(A.mean(CURRENT, 'late_jobs', 'rest') - late_rest)} more late jobs there to remove.</p>")
    b.append(titled(fig_build(wk), f"Weekly WIP and Brake Queue Time Through the Year-End Build, Measured Against Model, October {YEAR - 1} to June {YEAR}"))

    # 2 ── the scenarios
    b.append("<h2 id='f2'>2. The Scenarios Simulated</h2>")
    b.append(f"<p>{link('capacity', 'The capacity report')} finds the brakes are the constraint: they hold {pc(M['brake_share_of_queue'], 0)} of queue time and lose "
             f"{n0(M['setups_over_per_week'])} hours a week to setups over standard. That allows two ways to raise on-time delivery. The first changes how work enters and moves through "
             f"the floor, through release and dispatch rules, and costs nothing but the rule. If late jobs come from too much work on the floor, or from the wrong job going next at the "
             f"brakes, these should move delivery. The second adds hours at the brakes or around them, through operating changes or new equipment, and costs labor or capital. If late "
             f"jobs come from too few brake hours, only these should move it. Each scenario changes one thing in the model and keeps the {YEAR - 1} to {YEAR} releases. "
             f"{T.see('assume')}</p>")
    wip_now = float(tol[(tol["period"] == "year") & (tol["measure"] == "wip_mean")]["measured"].iloc[0])
    cap_r, flow_r = "the capacity report", "the flow report"
    release = [
        ["WIP cap at 240, 210 and 180", "A job is released only when fewer jobs than the cap are on the floor.", "None", f"The floor carried {n0(wip_now)} jobs on average in {YEAR} ({flow_r}); fewer "
         f"jobs on the floor should mean shorter waits.", "Non-rush jobs wait at a release gate, in release order, until a job ships; rush jobs pass."],
        ["Constraint-paced release", "A job with brake work is released only when the brakes have 3 days of work or less waiting.", "None", f"The brakes hold {pc(M['brake_share_of_queue'], 0)} of "
         f"queue time ({cap_r}); pacing release to them should keep work from piling up there.", "Jobs with brake work wait at the gate while the brake backlog is over 3 days."],
        [EDD, "Every work center takes the job with the earliest due date next.", "None", f"Late jobs wait longest at the brakes ({flow_r}); taking the most urgent job first should "
         f"ship more of them on time.", "Rush first, then earliest due date, at every work center."],
        ["Critical ratio", "Every work center takes the job with the least time left for the work still to do.", "None", "It ranks jobs by urgency and remaining work together.",
         "Rush first, then the lowest ratio of time to the due date over standard hours remaining."],
        ["Shortest processing time at the brakes", "The brakes take the shortest job next.", "None", "Short jobs clear the queue fastest, which lowers the average wait.",
         "Rush first, then the least standard hours, at the brakes only."],
        ["Light work ahead of heavy on B1 and B2", "B1 and B2 take light parts ahead of heavy ones when the other brakes are backed up.", "None",
         f"Precision and expedited work goes to B1 and B2, which have the shortest brake queues ({cap_r}); light work could use that room.", "When over 2 days of light and heavy work waits, B1 and B2 take light parts before heavy."],
        ["Third color day for black", "The powder line runs black on a third day each week.", "None", f"Powder coat operations wait {d1(M['powder_wait'])} days on average for their color day "
         f"({flow_r}).", "Black is added to the color schedule on Fridays."]]
    b.append(chart("Release and Dispatch Scenarios", t_scenarios(release)))
    cp = A.O["press_brake_atc"]
    capacity_rows = [
        [SETUP, "Setup standards, carts and sheets for the 12 part-operations with the most setup hours over standard; repeat setups assigned to the operators who know the part; a "
         "handover standard at shift change.", f"{usd(A.COSTS['setup'][0])} once and {usd(A.COSTS['setup'][1])} a year", f"Brake setups run {n0(M['setups_over_per_week'])} hours a week over "
         f"standard ({cap_r}).", "The 12 part-operations set up at standard; the other brake setups shorter by the assignment and handover hours measured."],
        ["Planned Saturdays, November to February", "A Saturday brake shift every week of the build, in two variants: as crewed today (one brake) and both B1 and B2 crewed.",
         f"Overtime of the added shifts: {usd(round(sat_cost[SAT_ONE], -2))} a year as crewed today, {usd(round(sat_cost[SAT_BOTH], -2))} with both brakes",
         f"A Saturday shift as worked today supplies {sat_one} brake machine hours, {sat_share}% of the weekly gap in the build; with both brakes crewed about {sat_two}, "
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

    # 3 ── results
    b.append("<h2 id='f3'>3. Simulation Results</h2>")
    works_cap = [s for s in (SETUP, SAT_BOTH, CHANGER, CELL) if A.VERDICT[s] == "Works"]
    worse = [s for s in A.RELEASE if A.VERDICT[s] == "Makes it worse"]
    none = [s for s in A.RELEASE + A.CAPACITY if A.VERDICT[s] == "No effect"]
    assert len(works_cap) == 4 and A.VERDICT[EDD] == "Works" and A.VERDICT[WELD] == "Works" and A.VERDICT[SAT_ONE] == "Works" and A.VERDICT[TOWER] == "No effect"
    edd_late, edd_days = A.diff(EDD, "late_jobs"), A.diff(EDD, "days_late")
    assert edd_late[2] < 0 and edd_days[1] < 0 < edd_days[2]
    cap180 = A.RELEASE[2]
    b.append(f"<p>Adding brake hours raises on-time delivery; changing the order or the release of work does not, with one exception. A scenario works when the 95% interval of its change "
             f"in on-time delivery lies entirely above zero for {YEAR} or for {RT}. Four capacity changes work in the year of the build: the setup program ({ptsb(SETUP)}), planned "
             f"Saturdays with both brakes crewed ({ptsb(SAT_BOTH)}), the tool changer on B3 ({ptsb(CHANGER)}) and the robotic bending cell ({ptsb(CELL)}). Planned Saturdays as crewed today "
             f"add {pts(SAT_ONE)}, and the weld cell second shift works in {RT} only ({ptsb(WELD, 'rest')}). Among the release and dispatch rules only earliest due date works "
             f"({ptsb(EDD)}), and it trades days for jobs: {n0(-edd_late[0])} fewer late jobs in {YEAR} with no fewer days late. The three WIP caps, critical ratio and shortest processing time at the brakes "
             f"make delivery worse, the cap at 180 by {d1(-chg(cap180, 'on_time_delivery') * 100)} points, because a cap moves the wait from the brakes to the release gate "
             f"({d1(A.mean(cap180, 'release_hold_days'))} days held) without adding an hour of brake time. {T.see('hold')}</p>")
    b.append(titled(fig_effects(), "Change in On-time Delivery by Scenario, With 95% Intervals"))

    b.append("<h3 id='f3_1'>What each scenario changes</h3>")
    b.append(f"<p>On-time delivery decides whether a scenario works; five other outcomes show how. The capacity changes that work shorten the wait at the brakes and take jobs off the "
             f"floor: the setup program cuts queue time per brake operation by {d2(-chg(SETUP, 'brake_queue_mean'))} days and floor WIP by {n0(-chg(SETUP, 'wip_mean'))} jobs, removes "
             f"{n0(-chg(SETUP, 'late_jobs'))} late jobs and {n0(-chg(SETUP, 'days_late'))} days late, and lowers brake utilization by {d1(-chg(SETUP, 'brake_utilization') * 100)} points. "
             f"The tool changer does the same through B3's setups ({n0(-chg(CHANGER, 'late_jobs'))} late jobs and {n0(-chg(CHANGER, 'days_late'))} days late removed), and the robotic "
             f"cell does about twice as much ({n0(-chg(CELL, 'late_jobs'))} late jobs, {n0(-chg(CELL, 'days_late'))} days late, {d2(-chg(CELL, 'brake_queue_mean'))} days of brake queue "
             f"and {d1(-chg(CELL, 'brake_utilization') * 100)} points of utilization on the manual brakes). Planned Saturdays with both brakes remove {n0(-chg(SAT_BOTH, 'late_jobs'))} late "
             f"jobs and {n0(-chg(SAT_BOTH, 'days_late'))} days late by adding hours in the build, with brake utilization unchanged.</p>")
    b.append(f"<p>The rules that fail show the opposite pattern. The WIP caps shorten the brake queue ({d2(-chg(cap180, 'brake_queue_mean'))} days at 180) and raise floor WIP "
             f"({sg(chg(cap180, 'wip_mean'), 0)} jobs) and days late ({sg(chg(cap180, 'days_late'), 0)}), because the jobs held at the gate are still jobs released and not shipped. Critical "
             f"ratio adds {n0(chg('Critical ratio', 'late_jobs'))} late jobs. Earliest due date removes {n0(-edd_late[0])} late jobs in {YEAR} and leaves days late where they were "
             f"({sg(edd_days[0], 0)}, {sg(edd_days[1], 0)} to {sg(edd_days[2], 0)}); in {RT} it adds {n0(chg(EDD, 'days_late', 'rest'))} days late. The laser tower clears the laser queue in the build and does not move delivery "
             f"({ptsb(TOWER)}), since the work it cuts sooner waits at the brakes. {T.see('year', 'rest', 'tower')}</p>")
    rows = []
    for grp, names_ in (("Release and dispatch", A.RELEASE), ("Capacity", A.CAPACITY), ("Package and combinations", [PACKAGE] + A.COMBOS)):
        for sc in names_:
            rows.append([grp, sc, A.VERDICT[sc]] + [band(A.diff(sc, m_), d, 100 if p_ else 1) for m_, _, d, p_ in A.OUTCOMES])
    b.append(chart(f"Scenario Results Against Current Practice, {YEAR}", table(pd.DataFrame(rows, columns=["Group", "Scenario", "Verdict"] + [x[1] for x in A.OUTCOMES]))))

    b.append("<h3 id='f3_2'>Combining the levers that work</h3>")
    pk, pkr = A.diff(PACKAGE, "on_time_delivery"), A.diff(PACKAGE, "on_time_delivery", "rest")
    singles = chg(SETUP, "on_time_delivery") + chg(SAT_BOTH, "on_time_delivery")
    e_on = A.diff(P_EDD, "on_time_delivery", "year", PACKAGE)
    assert e_on[1] < 0 < e_on[2] and A.diff(P_TOWER, "on_time_delivery", "year", PACKAGE)[1] < 0
    b.append(f"<p>The levers that work combine, though not fully additively. The setup program and planned Saturdays with both brakes crewed add {sg(chg(SETUP, 'on_time_delivery') * 100)} "
             f"and {sg(chg(SAT_BOTH, 'on_time_delivery') * 100)} points singly and {pts(PACKAGE)} together, {d1((singles - pk[0]) * 100)} points less than their sum, since both work on "
             f"the same queue. With the operating package the shop ships {pc(A.mean(PACKAGE, 'on_time_delivery'))} on time for {YEAR} and {pc(A.mean(PACKAGE, 'on_time_delivery', 'rest'))} "
             f"in {RT}, with {n0(-chg(PACKAGE, 'late_jobs'))} fewer late jobs and {n0(-chg(PACKAGE, 'days_late'))} fewer days late in the year. On top of the package the robotic cell "
             f"adds {pts(P_CELL, 'year', PACKAGE)} and the tool changer {pts(P_CHANGER, 'year', PACKAGE)}; the laser tower adds nothing ({ptsb(P_TOWER, 'year', PACKAGE)}). Earliest due "
             f"date on top of the package brings no gain ({ptsb(P_EDD, 'year', PACKAGE)}) and {n0(chg(P_EDD, 'days_late', 'year', PACKAGE))} more days late.</p>")
    b.append(titled(fig_build_up(), f"From Current Practice to the Operating Package, {YEAR} and {RT}"))
    b.append(titled(fig_capital(), f"What Each Capital Option Adds, Alone and on Top of the Operating Package, {YEAR}"))

    # 4 ── return
    b.append("<h2 id='f4'>4. Return on the Changes That Work</h2>")
    mp, mc, mt, mw = money[PACKAGE], money[P_CELL], money[P_CHANGER], money[WELD]
    assert all(money[sc]["net_without"] < 0 for sc, _ in RETURN) and mt["npv"][2] < 0 and mc["npv"][1] > 0
    b.append(f"<p>Two decisions follow from the results, and they are separate. The operating package addresses the year-end build: it costs {usd(mp['one_time'])} once and "
             f"{usd(round(mp['added'], -2))} a year, and returns that in {d1(mp['payback'])} years if half the {n0(mp['freed'])} brake hours it frees are sold, for an NPV of "
             f"{musd(mp['npv'][0])}. On top of it the robotic cell returns {musd(mc['npv'][0])} with a payback of {d1(mc['payback'])} years and breaks even when {pc(mc['share'], 0)} of its "
             f"freed hours are sold; the tool changer does not reach zero at half sold ({musd(mt['npv'][0])}) and needs {pc(mt['share'], 0)}. The weld cell second shift is the one lever "
             f"that moves an ordinary quarter, at about {usd(round(mw['weld'], -3))} a year with no return in money. Nothing that costs money pays on cost savings alone.</p>")
    b.append("<h3 id='f4_1'>What the changes cost and return</h3>")
    b.append(f"<p>The return on each change is the brake hours it frees, if those hours are sold, plus overtime avoided, less what it costs to run. The operating package frees "
             f"{n0(mp['freed'])} brake hours a year, worth {usd(round(mp['throughput'], -3))} at half sold, and adds {usd(round(mp['added_overtime'], -2))} of Saturday overtime; the robotic "
             f"cell frees a further {n0(mc['freed'])} hours ({usd(round(mc['throughput'], -3))}) and costs {usd(round(mc['added'], -3))} a year to run, {usd(round(mc['cell'], -3))} of it "
             f"its operator; the tool changer frees {n0(mt['freed'])} ({usd(round(mt['throughput'], -3))}). Overtime avoided is under {usd(np.ceil(max(money[sc]['avoided'] for sc, _ in RETURN) / 1000) * 1000)} a year for every change. The simulation "
             f"replays the {YEAR} orders, so it ships within {n0(max(abs(chg(sc, 'jobs_shipped')) for sc, _ in RETURN))} jobs of current practice under every option; the throughput value "
             f"is an assumption about sales, not a simulated result, and only brake hours carry it. Operator hours freed without a change in hours paid are not counted as money. Planned "
             f"Saturdays add hours rather than free them; their return is in on-time delivery, not in this table. Payback is the one-time cost over the net a year, and NPV is the net a "
             f"year over {A.F['horizon_years']} years at {A.F['discount_rate']:.0%} less the one-time cost, before tax; rates and prices are the shop's. "
             f"{T.see('measures', 'cost')}</p>")
    b.append(chart(f"Cost and Return, {YEAR}", t_cost(RETURN)))
    b.append(titled(fig_npv(money), f"What Makes Up Each Option's NPV, {YEAR}"))

    b.append("<h3 id='f4_2'>When the freed hours are sold</h3>")
    oc, ot_ = ordinary[P_CELL], ordinary[P_CHANGER]
    b.append(f"<p>Whether the capital options pay depends on one figure the simulation cannot supply: how many of the freed brake hours the shop sells. The package breaks even at "
             f"{n0(mp['hours'])} hours sold a year and the robotic cell at {n0(mc['hours'])}, against the {n0(M['brake_hours'])} brake hours the shop ran in {YEAR}; the tool changer needs "
             f"{n0(mt['hours'])} of the {n0(mt['freed'])} it frees. In an ordinary year, without a build, the package frees {n0(ordinary[PACKAGE]['freed'])} hours and its NPV falls to "
             f"{musd(ordinary[PACKAGE]['npv'][0])}; the cell's is {musd(oc['npv'][0])} and the tool changer's {musd(ot_['npv'][0])}.</p>")
    b.append(titled(fig_sold(money), "NPV Against the Share of Freed Brake Hours Sold"))

    b.append("<h3 id='f4_3'>What the money does not capture</h3>")
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
        return f" Operator hours freed: {n0(h)}."

    def unpriced(sc, ref):
        c90, c95 = A.lifted(sc, 0.90), A.lifted(sc, 0.95)
        per = "rest" if sc == WELD else "year"
        lab = RT if sc == WELD else f"{YEAR}"
        return (f"{lab}: {n0(-chg(sc, 'late_jobs', per, ref))} late jobs and {n0(-chg(sc, 'days_late', per, ref))} days late removed ({sg(chg(sc, 'on_time_delivery', per, ref) * 100)} points); "
                f"90th-percentile lead time {sg(chg(sc, 'lead_time_p90', per, ref), 1)} days; floor WIP {sg(chg(sc, 'wip_mean', per, ref), 0)} jobs. Top customers at or above 90% on time: "
                f"{c90[0]} of {len(A.REVENUE)} ({musd(c90[1])} of revenue) against {base90[0]} today; at or above 95%: {c95[0]}.{freed_hours(sc, ref)} Weekend hours per brake operator, "
                f"November to February: {d1(A.mean(sc, 'saturday_hours_winter') / M['operators'])}.")

    sats = A.mean(SAT_BOTH, "saturday_hours_winter") / 8 / M["operators"]
    sats_now = A.mean(CURRENT, "saturday_hours_winter") / 8 / M["operators"]
    added_setup = chg(P_CELL, "brake_setup_hours", "year", PACKAGE)
    consider = {
        SETUP: "Depends on repeat setups going to the operators who know the part, and on a handover standard being kept. It narrows cross-training. It can be stopped at no cost.",
        SAT_BOTH: f"About {d1(sats)} Saturdays per brake operator from November to February, against {d1(sats_now)} today. Sustained weekend work raises fatigue, absence and turnover risk, "
                  f"while a planned shift is easier to staff than one called at short notice. The record has only {WORD[both_saturdays]} Saturdays with both brakes crewed.",
        PACKAGE: "Both of the above.",
        WELD: "One operator alone on the shift, with no programming or quality support on hand. The shop must hire for it and keep the post filled.",
        P_CELL: f"Runs only light, repeat parts in lots of 25 or more, so its value depends on that work staying {pc(M['cell_share'], 0)} of brake hours. Adds {n0(added_setup)} setup hours a "
                f"year to the manual brakes. Needs in-house programming skills. Gives headroom to quote more work. It is the largest sum at risk and cannot be reversed.",
        P_CHANGER: "B3 is out of service while it is replaced. The effect is limited to B3's setups. One vendor maintains it."}
    assert added_setup > 0
    b.append(chart("Measured but Not Priced, and Other Considerations",
                   table(pd.DataFrame([[name(sc), unpriced(sc, ref), consider[sc]] for sc, ref in RETURN], columns=["Change", "Measured, not priced", "Considerations"]))))
    b.append(f"<p>The package comes first: {usd(mp['one_time'])} and Saturday overtime for {sg(pk[0] * 100)} points in a year with a build, and {n0(mp['hours'])} freed hours sold a year "
             f"covers it. The robotic cell follows if the shop can sell {n0(mc['hours'])} of the {n0(mc['freed'])} brake hours it frees; the tool changer only if it can sell "
             f"{n0(mt['hours'])} of {n0(mt['freed'])}. The weld cell second shift is a separate decision: {usd(round(mw['weld'], -3))} a year for {sg(chg(WELD, 'on_time_delivery', 'rest') * 100)} "
             f"point in an ordinary quarter, {n0(-chg(WELD, 'late_jobs', 'rest'))} late jobs and {n0(-chg(WELD, 'days_late', 'rest'))} days late.</p>")

    b.append("<h2 id='appendix'>Appendix</h2>")
    b.append(T.appendix())
    toc = [("f1", "1. The Shop Model"), ("f2", "2. The Scenarios Simulated"), ("f3", "3. Simulation Results"), ("f4", "4. Return on the Changes That Work")]
    print(f"wrote {page('options', chr(10).join(b), toc, heading=REPORTS['options'][1])}: 4 sections, {len(T.order)} appendix tables")


def main():
    build()


if __name__ == "__main__":
    main()
