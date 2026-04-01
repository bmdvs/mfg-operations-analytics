"""P5 release control and the shop model: report and figures, from the scenario runs and the marts.

Usage: python -m analytics.p5_release_control.build
The scenario runs come from analytics.p5_release_control.scenarios and validate (results/scenario_runs.csv, results/validation_quarters.csv).
"""
from pathlib import Path

import numpy as np
import pandas as pd

from analytics.db import q
from analytics.p5_release_control.scenarios import OUT, QUARTERS, summarize, versus
from analytics.p5_release_control.validate import TOLERANCE, measured
from analytics.style.style import ACCENT, AMBER, BRAND_BLUE, DOCS, GREY, LIGHT_BLUE, RED, fig, pct, save, report_shell, table
from analytics.style.style import recommendation_block

YEAR, REST = 2025, "Q2 to Q4"
RES = Path(__file__).resolve().parent / "results"
S0, S8 = "S0 Current practice", "S8 Setup reduction from P4"
SHORT = {"S1 WIP cap 240": "WIP cap 240", "S1 WIP cap 210": "WIP cap 210", "S1 WIP cap 180": "WIP cap 180",
         "S2 Constraint-paced release (3 days of brake work)": "Constraint-paced release", "S3 Earliest due date": "Earliest due date",
         "S3 Critical ratio": "Critical ratio", "S3 Shortest processing time, brakes only": "Shortest processing time, brakes",
         "S4 Light work first on B1 and B2 when the B3 to B5 queue exceeds 2 days": "Light work ahead of heavy on B1 and B2",
         "S5 Second shift on the robotic weld cell": "Weld cell second shift", "S6 Third weekly color day for black": "Third color day for black",
         "S7 Planned Saturday brake shift, November to February": "Planned Saturdays, November to February", S8: "Setup reduction from P4", S0: "Current practice"}
MEAS = {"lead_time_median": ("Median lead time", "{:.1f}"), "lead_time_p90": ("90th-percentile lead time", "{:.1f}"), "on_time_delivery": ("On time", "{:.1%}"),
        "wip_mean": ("Mean WIP", "{:.0f}"), "brake_utilization": ("Brake utilization", "{:.3f}"), "robotic_weld_utilization": ("Robotic weld utilization", "{:.3f}"),
        "saturday_shifts": ("Saturday shifts", "{:.1f}"), "extended_hours": ("Extended hours", "{:.0f}"), "jobs_shipped": ("Jobs shipped", "{:,.0f}")}

df = pd.read_csv(OUT)
S = summarize(df)
REPS = int(df.groupby("scenario")["replication"].nunique().iloc[0])
PK = [s for s in df["scenario"].unique() if s.startswith("P")]
CHRONIC, NOCAP = PK[0], PK[1]
SINGLE = [s for s in df["scenario"].unique() if s.startswith("S") and not s.startswith(("S0", "S10"))]
CAPCOMBO = [s for s in df["scenario"].unique() if s.startswith("S10")]
VQ = pd.read_csv(QUARTERS)
MQ = q("select * from marts.mart_delivery_by_quarter order by quarter_start")
MQ["quarter"] = pd.to_datetime(MQ["quarter_start"]).dt.to_period("Q").astype(str)
batch = q("select export_batch_id from marts.mart_delivery_by_quarter limit 1").iloc[0, 0]
quote_mean = float(q(f"select avg(quoted_lead_days) from marts.mart_job_lead_time where year(ship_date) = {YEAR} and quarter(ship_date) >= 2").iloc[0, 0])
required = float(q("select max(required_otd_pct) from marts.mart_job_lead_time where key_account").iloc[0, 0]) / 100


def P(period):
    return S[S["period"] == period].set_index(["scenario", "measure"])


PY, PR = P("year"), P(REST)


def hold(sc):
    """Mean working days a job is held before release to the floor, over the whole replay."""
    return float(PY.loc[(sc, "release_hold_days"), "mean"])


def v(p, sc, m, col="mean"):
    return float(p.loc[(sc, m), col])


def pts(p, sc, m="on_time_delivery", interval=False):
    r = p.loc[(sc, m)]
    return f"{abs(r['diff']) * 100:.1f}" + (f" ({r['diff_low'] * 100:+.1f} to {r['diff_high'] * 100:+.1f})" if interval else "")


def sg(x, f="{:+.1f}"):
    """A signed number without a negative zero."""
    t = f.format(x)
    return t.replace("-", "+") if float(t) == 0 else t


def spts(r):
    return f"{sg(r['diff'] * 100)} ({sg(r['diff_low'] * 100)} to {sg(r['diff_high'] * 100)})"


def spp(r):
    """A signed change in points followed by its interval, for running text."""
    return f"{sg(r['diff'] * 100)} points ({sg(r['diff_low'] * 100)} to {sg(r['diff_high'] * 100)})"


def sdd(r):
    return f"{sg(r['diff'])} days ({sg(r['diff_low'])} to {sg(r['diff_high'])})"


def paired(period, sc, m, ref, ref_m):
    """Paired difference in points between a measure of one scenario and a measure of another, by replication, with its 95% interval."""
    a = df[(df["scenario"] == sc) & (df["period"] == period)].set_index("replication")[m]
    d = (a - df[(df["scenario"] == ref) & (df["period"] == period)].set_index("replication")[ref_m].reindex(a.index)) * 100
    h = 1.96 * d.std(ddof=1) / np.sqrt(len(d))
    return f"{sg(d.mean())} ({sg(d.mean() - h)} to {sg(d.mean() + h)})"


def by(r):
    """A positive change in points with its interval, for running text."""
    return f"{r['diff'] * 100:.1f} points ({r['diff_low'] * 100:.1f} to {r['diff_high'] * 100:.1f})"


def sdays(r, f="{:+.1f}"):
    return f"{sg(r['diff'], f)} ({sg(r['diff_low'], f)} to {sg(r['diff_high'], f)})"


def d1(x):
    return f"{x:.1f}"


def n0(x):
    return f"{x:,.0f}"


# ── validation ──────────────────────────────────────────────────────────────
def validation_rows():
    rows, n_in, n_tol = [], 0, 0
    for fq, label, p in ((1, f"{YEAR}", PY), (2, f"{YEAR} {REST}", PR)):
        m = measured(fq)
        for k in ("lead_time_median", "lead_time_p90", "wip_mean", "brake_utilization", "robotic_weld_utilization", "on_time_delivery", "jobs_shipped"):
            name, f = MEAS[k]
            r = p.loc[(S0, k)]
            kind, tol = TOLERANCE.get(k, (None, None))
            if kind == "relative":
                diff, ok, tl = f"{r['mean'] / m[k] - 1:+.1%}", abs(r["mean"] / m[k] - 1) <= tol, "within 10%"
            elif kind == "points":
                diff, ok, tl = f"{(r['mean'] - m[k]) * 100:+.1f} points", abs(r["mean"] - m[k]) <= tol, "within 3 points"
            else:
                diff, ok, tl = f"{r['mean'] / m[k] - 1:+.1%}", None, "reported"
            if ok is not None:
                n_tol += 1
                n_in += int(ok)
            rows.append([label, name, f.format(m[k]), f.format(r["mean"]), f"{f.format(r['low'])} to {f.format(r['high'])}", diff, tl,
                         "" if ok is None else ("within" if ok else "outside")])
    return rows, n_in, n_tol


VROWS, V_IN, V_TOL = validation_rows()


def t_validation():
    return table(pd.DataFrame(VROWS, columns=["Period", "Measure", "Measured", "Model", "95% interval", "Difference", "Tolerance", "Result"]))


def quarter_rows():
    g = VQ.groupby("quarter")[["jobs_shipped", "on_time_delivery", "lead_time_median"]].mean()
    rows = []
    for r in MQ.itertuples():
        if r.quarter in g.index:
            s = g.loc[r.quarter]
            rows.append(dict(quarter=r.quarter, n_m=r.jobs_shipped, n_s=s["jobs_shipped"], otd_m=r.on_time_delivery, otd_s=s["on_time_delivery"],
                             med_m=r.lead_time_median, med_s=s["lead_time_median"]))
    return pd.DataFrame(rows)


QT = quarter_rows()
Q1 = QT[QT["quarter"] == f"{YEAR}Q1"].iloc[0]
OTHER_GAP = float((QT[QT["quarter"] != f"{YEAR}Q1"]["otd_s"] - QT[QT["quarter"] != f"{YEAR}Q1"]["otd_m"]).abs().max())


def t_quarters():
    rows = [[r.quarter[:4] + " " + r.quarter[4:], n0(r.n_m), n0(r.n_s), pct(r.otd_m), pct(r.otd_s), d1(r.med_m), d1(r.med_s)] for r in QT.itertuples()]
    return table(pd.DataFrame(rows, columns=["Quarter shipped", "Jobs shipped, measured", "Jobs shipped, model", "On time, measured", "On time, model", "Median lead time, measured", "Median lead time, model"]))


# ── figures ─────────────────────────────────────────────────────────────────
def fig_effects(name="p5_scenario_effects", h=5.0, scen=None):
    scen = scen or SINGLE
    f, axes = fig(h=h, ncols=2, grid="x", sharey=True)
    y = np.arange(len(scen))[::-1]
    for ax, m, scale, xl in ((axes[0], "on_time_delivery", 100, "On-time delivery (points)"),
                             (axes[1], "lead_time_p90", 1, "90th-percentile lead time (days)")):
        for p, off, color, lab in ((PY, 0.17, BRAND_BLUE, f"{YEAR}"), (PR, -0.17, AMBER, REST)):
            d = [p.loc[(s, m)] for s in scen]
            x = np.array([r["diff"] for r in d]) * scale
            lo, hi = np.array([r["diff_low"] for r in d]) * scale, np.array([r["diff_high"] for r in d]) * scale
            ax.errorbar(x, y + off, xerr=[x - lo, hi - x], fmt="o", color=color, markersize=4, capsize=2, linewidth=1.2, label=lab)
        ax.axvline(0, color=GREY, linewidth=1)
        ax.set_xlabel(xl, fontsize=9.5)
        ax.set_yticks(y)
        ax.set_yticklabels([SHORT.get(s, s) for s in scen], fontsize=9)
    axes[0].legend(frameon=False, fontsize=9, loc="lower left")
    f.tight_layout()
    return save(f, name, "Change in on-time delivery and 90th-percentile lead time by scenario")


def fig_cap():
    caps = ["S1 WIP cap 240", "S1 WIP cap 210", "S1 WIP cap 180"]
    f, ax = fig(h=3.0, w=6.2)
    for p, color, lab in ((PY, BRAND_BLUE, f"{YEAR}"), (PR, AMBER, REST)):
        x = [0.0] + [hold(c) for c in caps]
        y = [v(p, S0, "on_time_delivery") * 100] + [v(p, c, "on_time_delivery") * 100 for c in caps]
        ax.plot(x, y, marker="o", color=color, label=lab)
        for xi, yi, t in zip(x, y, ["No cap", "240", "210", "180"]):
            ax.annotate(t, (xi, yi), textcoords="offset points", xytext=(5, 5), fontsize=8.5)
    ax.set_xlabel("Days a job waits before release to the floor")
    ax.set_ylabel("On-time delivery (%)")
    ax.legend(frameon=False, fontsize=9)
    f.tight_layout()
    return save(f, "p5_wip_cap", "On-time delivery against release hold under a WIP cap")


# ── tables ──────────────────────────────────────────────────────────────────
PKG_NAMES = {S8: "Setup reduction alone", CHRONIC: "Chronic package: setup reduction + weld cell second shift",
             NOCAP: "No-capital package: + planned Saturdays, November to February"}


def t_packages():
    out = ""
    for period, label, p in (("year", f"{YEAR}", PY), (REST, f"{YEAR} {REST}", PR)):
        rows = [["Current practice", pct(v(p, S0, "on_time_delivery")), "", "", d1(v(p, S0, "lead_time_p90")), "", "", n0(v(p, S0, "wip_mean")),
                 d1(v(p, S0, "saturday_shifts")), n0(v(p, S0, "extended_hours"))]]
        for sc in (S8, CHRONIC, NOCAP):
            vs = versus(df, sc, S8)
            vs = vs[vs["period"] == period].set_index("measure")
            rows.append([PKG_NAMES[sc], pct(v(p, sc, "on_time_delivery")), spts(p.loc[(sc, "on_time_delivery")]),
                         "" if sc == S8 else spts(vs.loc["on_time_delivery"]), d1(v(p, sc, "lead_time_p90")), sdays(p.loc[(sc, "lead_time_p90")]),
                         "" if sc == S8 else sdays(vs.loc["lead_time_p90"]), n0(v(p, sc, "wip_mean")), d1(v(p, sc, "saturday_shifts")), n0(v(p, sc, "extended_hours"))])
        for name, m in (("No-capital package at the P7 quote table", "on_time_delivery_quote_table"),
                        ("No-capital package at the trailing 13-week promise", "on_time_delivery_load_aware")):
            rows.append([name, pct(v(p, NOCAP, m)), paired(period, NOCAP, m, S0, "on_time_delivery"), "", "", "", "", "", "", ""])
        out += f"<h3>{label}</h3>" + table(pd.DataFrame(rows, columns=["Package", "On time", "Against current practice (points)", "Against setup reduction (points)",
                                                                       "90th-percentile lead time", "Against current practice (days)",
                                                                       "Against setup reduction (days)", "Mean WIP", "Saturday shifts", "Extended hours"]))
    return out


def t_full(p, scen):
    rows = []
    for sc in scen:
        rows.append([SHORT.get(sc, sc[4:] if sc.startswith("S10") else PKG_NAMES.get(sc, sc))] +
                    [f"{f.format(v(p, sc, m))} ({f.format(v(p, sc, m, 'low'))} to {f.format(v(p, sc, m, 'high'))})" for m, (_, f) in MEAS.items()])
    return table(pd.DataFrame(rows, columns=["Scenario"] + [n for n, _ in MEAS.values()]))


def t_diff(p, scen):
    rows = []
    for sc in scen:
        js = p.loc[(sc, "jobs_shipped")]
        rows.append([SHORT.get(sc, sc[4:] if sc.startswith("S10") else PKG_NAMES.get(sc, sc)), sdays(p.loc[(sc, "lead_time_median")]), sdays(p.loc[(sc, "lead_time_p90")]),
                     spts(p.loc[(sc, "on_time_delivery")]), sdays(p.loc[(sc, "wip_mean")], "{:+.0f}"), sdays(js, "{:+.0f}"),
                     "fewer" if js["diff_high"] < 0 else "holds"])
    return table(pd.DataFrame(rows, columns=["Scenario", "Median lead time (days)", "90th-percentile lead time (days)", "On time (points)", "Mean WIP (jobs)",
                                             "Jobs shipped", "Throughput"]))


def t_hold():
    rows = [[SHORT.get(sc, sc[4:]), f"{v(PY, sc, 'release_hold_days'):.2f} ({v(PY, sc, 'release_hold_days', 'low'):.2f} to {v(PY, sc, 'release_hold_days', 'high'):.2f})"]
            for sc in df["scenario"].unique() if (sc, "release_hold_days") in PY.index]
    return table(pd.DataFrame(rows, columns=["Scenario", "Working days held before release to the floor, mean per job"]))


def t_promise():
    rows = []
    for period, label, p in (("year", f"{YEAR}", PY), (REST, f"{YEAR} {REST}", PR)):
        for name, sc in (("Current practice", S0), ("No-capital package", NOCAP)):
            a = p.loc[(sc, "on_time_delivery")]
            for rule, m, lm in (("P7 quote table", "on_time_delivery_quote_table", "promises_longer_quote_table"),
                                ("Routing class, trailing 13 weeks", "on_time_delivery_load_aware", "promises_longer_than_fixed_quote")):
                rows.append([label, name, rule, pct(a["mean"]), pct(v(p, sc, m)), paired(period, sc, m, sc, "on_time_delivery"), pct(v(p, sc, lm), 0)])
    return table(pd.DataFrame(rows, columns=["Period", "Floor", "Promise rule", "On time at the promises as made", "On time at the rule", "Difference (points)",
                                             "Non-rush promises longer than the fixed quote"]))


# ── report ──────────────────────────────────────────────────────────────────
HEADER_META = (f"Custom sheet-metal fabrication job shop, about 120 employees, one plant. Shop model of the jobs released from January 2024 to December {YEAR}; "
               f"results for jobs shipped in {YEAR}, whole year and {REST}.<br>"
               f"Sources: ERP, shop-floor data collection, maintenance exports (batch {batch}); {REPS} replications per scenario, 95% intervals. "
               f"Lead time in working days, scheduled Saturdays counted.")


def report():
    cap = ["S1 WIP cap 240", "S1 WIP cap 210", "S1 WIP cap 180"]
    paced, edd, cr, spt = SINGLE[3], SINGLE[4], SINGLE[5], SINGLE[6]
    s4, s5, s6, s7 = SINGLE[7], SINGLE[8], SINGLE[9], SINGLE[10]
    b = []
    b.append("<h2 id='f1'>1. Validation</h2>")
    b.append(f"<p>The model of current practice is within tolerance on {V_IN} of {V_TOL} measures. It replays the 2024 year-end build and clears it sooner than the "
             f"shop did: first-quarter on-time delivery is {pct(Q1['otd_s'])} in the model against {pct(Q1['otd_m'])} measured, and every other quarter is within "
             f"{OTHER_GAP * 100:.1f} points. Effects on the first-quarter event are therefore lower bounds. The model's brakes run "
             f"{(v(PY, S0, 'brake_utilization') - measured(1)['brake_utilization']) * 100:.0f} points hotter than measured ({v(PY, S0, 'brake_utilization'):.3f} against "
             f"{measured(1)['brake_utilization']:.3f}), so the effects of capacity levers in the ordinary quarters are slightly overstated.</p>")
    b.append(t_validation())
    b.append(f"<div class='caption'>Table 1. The model under current practice against measured {YEAR}, with tolerances.</div>")

    b.append("<h2 id='f2'>2. Release control does not help this shop</h2>")
    b.append(f"<p>A WIP cap at 240, 210 and 180 jobs lowers on-time delivery by {pts(PR, cap[0])}, {pts(PR, cap[1])} and {pts(PR, cap[2])} points in {REST} "
             f"({pts(PY, cap[0])}, {pts(PY, cap[1])} and {pts(PY, cap[2])} for the year) and lengthens the 90th-percentile lead time by "
             f"{d1(v(PR, cap[0], 'lead_time_p90', 'diff'))} to {d1(v(PR, cap[2], 'lead_time_p90', 'diff'))} days; jobs wait {d1(hold(cap[0]))} to "
             f"{d1(hold(cap[2]))} days at the gate. Constraint-paced release is {pts(PR, paced)} points worse in {REST}. In an ordinary quarter the "
             f"floor already carries less WIP than the quoted lead times allow (P1); a cap delays work the floor could have started.</p>")
    b.append(fig_cap())
    b.append(f"<div class='caption'>Figure 1. On-time delivery against the days a job waits for release under a WIP cap of 240, 210 and 180 jobs.</div>")

    b.append("<h2 id='f3'>3. Dispatch rules do not help either</h2>")
    b.append(f"<p>Earliest due date makes no difference for the year, {spp(PY.loc[(edd, 'on_time_delivery')])}, is {pts(PR, edd)} points worse in {REST} and "
             f"ships {n0(-v(PY, edd, 'jobs_shipped', 'diff'))} fewer jobs. Critical ratio is {pts(PR, cr)} to {pts(PY, cr)} points worse. Shortest processing time at "
             f"the brakes shortens the median and is {pts(PY, spt)} to {pts(PR, spt)} points worse on time, with {n0(-v(PY, spt, 'jobs_shipped', 'diff'))} fewer jobs "
             f"shipped in the year. The dispatch list with rush and hot-list precedence is as good as any rule tested.</p>")

    b.append("<h2 id='f4'>4. Capacity at the constraint is the lever</h2>")
    b.append(f"<p>The setup reduction from P4 raises on-time delivery by {by(PY.loc[(S8, 'on_time_delivery')])} for the year, shortens the 90th percentile by "
             f"{d1(-v(PY, S8, 'lead_time_p90', 'diff'))} days, lowers WIP by {n0(-v(PY, S8, 'wip_mean', 'diff'))} jobs and cuts Saturday shifts from "
             f"{n0(v(PY, S0, 'saturday_shifts'))} to {n0(v(PY, S8, 'saturday_shifts'))} and extended hours from {n0(v(PY, S0, 'extended_hours'))} to "
             f"{n0(v(PY, S8, 'extended_hours'))}. In {REST} it shortens the 90th percentile by {d1(-v(PR, S8, 'lead_time_p90', 'diff'))} days and leaves on-time delivery "
             f"unchanged, {spp(PR.loc[(S8, 'on_time_delivery')])}: lateness in those quarters is set by the promise (P2).</p>")
    b.append(fig_effects())
    b.append(f"<div class='caption'>Figure 2. Change in on-time delivery and in 90th-percentile lead time against current practice, by scenario, {YEAR} and {REST}, "
             f"with 95% intervals.</div>")

    b.append("<h2 id='f5'>5. The secondary constraint</h2>")
    y5 = PY.loc[(s5, "on_time_delivery")]
    b.append(f"<p>A second shift on the robotic weld cell raises on-time delivery by {by(PR.loc[(s5, 'on_time_delivery')])} in {REST} and shortens the 90th "
             f"percentile there by {d1(-v(PR, s5, 'lead_time_p90', 'diff'))} days; for the year the effect is {spp(y5)}"
             + (", not distinguishable from zero." if y5["diff_low"] <= 0 <= y5["diff_high"] else ".") + "</p>")

    b.append("<h2 id='f6'>6. The peak</h2>")
    b.append(f"<p>A planned Saturday brake shift every week from November through February raises on-time delivery by {by(PY.loc[(s7, 'on_time_delivery')])} "
             f"for the year and shortens the 90th percentile by {d1(-v(PY, s7, 'lead_time_p90', 'diff'))} days, for "
             f"{d1(v(PY, s7, 'saturday_shifts') - v(PY, S0, 'saturday_shifts'))} more Saturday shifts in {YEAR} than the queue-triggered practice produced. "
             f"This is a lower bound.</p>")

    b.append("<h2 id='f7'>7. Two changes that make no difference</h2>")
    b.append(f"<p>Light work ahead of heavy on B1 and B2, {spp(PY.loc[(s4, 'on_time_delivery')])} for the year, and a third weekly color day for black, "
             f"{spp(PY.loc[(s6, 'on_time_delivery')])}, do not move on-time delivery or the 90th percentile beyond their intervals.</p>")

    b.append("<h2 id='f8'>8. The promise rules</h2>")
    b.append(f"<p>At the P7 quote table (routing class and brake backlog at release, never below the fixed quote) the current floor delivers "
             f"{pct(v(PY, S0, 'on_time_delivery_quote_table'))} on time for the year and {pct(v(PR, S0, 'on_time_delivery_quote_table'))} in {REST}, with "
             f"{pct(v(PY, S0, 'promises_longer_quote_table'), 0)} and {pct(v(PR, S0, 'promises_longer_quote_table'), 0)} of non-rush promises longer than the fixed "
             f"quote; at the 80th percentile of the routing class over the trailing 13 weeks, {pct(v(PY, S0, 'on_time_delivery_load_aware'))} and "
             f"{pct(v(PR, S0, 'on_time_delivery_load_aware'))}, with {pct(v(PY, S0, 'promises_longer_than_fixed_quote'), 0)} and "
             f"{pct(v(PR, S0, 'promises_longer_than_fixed_quote'), 0)} longer. Neither touches the floor; the quote table is the P7 rule and the trailing rule the "
             f"one first modeled.</p>")

    b.append("<h2 id='f9'>9. Packages</h2>")
    alone = sum(v(PY, sc, "on_time_delivery", "diff") for sc in (S8, s5, s7)) * 100
    sat_rest = (v(PR, NOCAP, "on_time_delivery", "diff") - v(PR, CHRONIC, "on_time_delivery", "diff")) * 100
    fewer = sorted(-v(PR, sc, "jobs_shipped", "diff") for sc in (S8, CHRONIC, NOCAP))
    assert all(PY.loc[(sc, "jobs_shipped"), "diff_low"] <= 0 <= PY.loc[(sc, "jobs_shipped"), "diff_high"] for sc in (CHRONIC, NOCAP))
    b.append(f"<p>Setup reduction with the weld cell's second shift raises on-time delivery by {by(PR.loc[(CHRONIC, 'on_time_delivery')])} in {REST} and "
             f"{by(PY.loc[(CHRONIC, 'on_time_delivery')])} for the year. Adding planned Saturdays from November through February takes the year to "
             f"{pct(v(PY, NOCAP, 'on_time_delivery'))} on time, up {by(PY.loc[(NOCAP, 'on_time_delivery')])}, with a 90th percentile of "
             f"{d1(v(PY, NOCAP, 'lead_time_p90'))} days against {d1(v(PY, S0, 'lead_time_p90'))}; {REST} reaches {pct(v(PR, NOCAP, 'on_time_delivery'))} and "
             f"{d1(v(PR, NOCAP, 'lead_time_p90'))} days. The three effects are close to additive: the levers alone sum to {alone:+.1f} points for the year against "
             f"{v(PY, NOCAP, 'on_time_delivery', 'diff') * 100:+.1f} for the package. In {REST} the gain is the weld cell's second shift; planned Saturdays add "
             f"{sat_rest:.1f} points there. Setup reduction and the packages ship {n0(fewer[0])} to {n0(fewer[-1])} fewer jobs in {REST} and the same number for the year; the "
             f"first-quarter backlog ships earlier. At the P7 quote table the same floor delivers "
             f"{pct(v(PY, NOCAP, 'on_time_delivery_quote_table'))} on time for the year and {pct(v(PR, NOCAP, 'on_time_delivery_quote_table'))} in {REST} "
             f"({pct(v(PY, NOCAP, 'on_time_delivery_load_aware'))} and {pct(v(PR, NOCAP, 'on_time_delivery_load_aware'))} at the trailing 13-week promise).</p>")
    b.append(t_packages())
    b.append(f"<div class='caption'>Table 2. The packages against current practice and against setup reduction alone, {YEAR} and {REST}.</div>")

    b.append("<h2 id='rec'>Recommendation</h2>")
    b.append(f"<p>Do not cap release, and keep the dispatch list. Take the P4 setup program, a second shift on the robotic weld cell and planned Saturday brake "
             f"shifts from November through February as the operating package: on-time delivery is expected to rise by {by(PY.loc[(NOCAP, 'on_time_delivery')])} for the "
             f"year and {by(PR.loc[(NOCAP, 'on_time_delivery')])} in {REST}, with the 90th-percentile lead time {d1(-v(PY, NOCAP, 'lead_time_p90', 'diff'))} and "
             f"{d1(-v(PR, NOCAP, 'lead_time_p90', 'diff'))} days shorter. Restate quoted lead times (P7). P8 compares this package with the capital options on the same "
             f"measures.</p>")

    b.append(control())

    b.append("<h2 id='method'>Method and data</h2>")
    b.append(f"<p>The model replays the jobs released from January 2024 with their routings, standards, promised dates, rush flags and planned operation dates, each "
             f"machine's shift calendar and recorded downtime, and the powder color schedule. Setup and run times are drawn from {YEAR} actual-over-standard ratios of "
             f"operations of similar standard hours at the same work center (brake setups by grouping and lot size, laser run time by machine); material wait, move and "
             f"recorded hold, outside processing and complete-to-ship times from their {YEAR} distributions.<br>"
             f"Practice modeled: traveler print the next working morning; dispatch by rush, hot list, planned operation start, arrival; the daily dispatch list at the "
             f"five single-shift work centers; precision first on B1 and B2, the list on B3 and B4, light work on B5, rush and hot-list jobs on any capable brake; "
             f"same-tooling grouping up to three in a row; a second operator on heavy setups; Saturday and extended brake shifts on B1 and B2 for enclosure and rush "
             f"work.<br>"
             f"Three parameters are estimated from the records: the share of crewed brake hours worked when the queue never empties (0.967), and the frequency of "
             f"Saturday and of extended brake shifts by the number of jobs at the brakes. Nest-fill is approximated: a laser job issued one sheet waits for a second job "
             f"on the sheet item or for two working days before its planned start; blank area is not in the records.<br>"
             f"Scenarios: the WIP cap holds non-rush jobs in release order until the jobs on the floor are below the cap, and lead time still runs from the release "
             f"date; constraint-paced release holds jobs with brake work while the work waiting at the brakes exceeds 3 days of crewed brake capacity; light work goes "
             f"ahead of heavy on B1 and B2, after precision, when the B3 to B5 queue exceeds 2 days; the setup reduction runs the top 12 part-operations at standard and "
             f"takes the assignment and handover hours off the other brake setups in proportion, the model having no individual operators. The promise rules do not change the floor: the model reads its own brake backlog at "
             f"each job's release to select the band of the quote table, which is the table fitted on 2023 to {YEAR} (P7). Each run draws from one generator seeded by its scenario and "
             f"replication number. Differences are paired by replication; throughput is flagged where a scenario ships fewer jobs in the period with the interval excluding zero.</p>")

    b.append("<h2 id='appendix'>Appendix</h2>")
    b.append("<h3>Table 3. The model against measured, by quarter shipped</h3>" + t_quarters())
    allsc = [S0] + SINGLE + [CHRONIC, NOCAP] + CAPCOMBO
    b.append(f"<h3>Table 4. Scenario results, {YEAR}</h3>" + t_full(PY, allsc))
    b.append(f"<h3>Table 5. Difference from current practice, {YEAR}</h3>" + t_diff(PY, allsc[1:]))
    b.append(f"<h3>Table 6. Scenario results, {YEAR} {REST}</h3>" + t_full(PR, allsc))
    b.append(f"<h3>Table 7. Difference from current practice, {YEAR} {REST}</h3>" + t_diff(PR, allsc[1:]))
    b.append("<h3>Table 8. Release hold under the WIP cap and constraint-paced release</h3>" + t_hold())
    b.append("<h3>Table 9. On-time delivery at the two promise rules</h3>" + t_promise())
    b.append("<div class='glossary'>WIP cap: a limit on jobs released to the floor and not shipped. Promise rule: the later of the requested date and the order "
             "date plus the rule's lead time; rush lines keep their promise.</div>")
    toc = [("f1", "Validation"), ("f2", "Release control"), ("f3", "Dispatch"), ("f4", "Capacity at the constraint"), ("f5", "Weld cell"), ("f6", "The peak"),
           ("f8", "Promise rules"), ("f9", "Packages"), ("rec", "Recommendation"), ("method", "Method and data"), ("appendix", "Appendix")]
    (DOCS / "reports").mkdir(parents=True, exist_ok=True)
    (DOCS / "reports" / "p5_release_control.html").write_text(report_shell("Release control and the shop model", "Project 5 report", HEADER_META, "\n".join(b), toc),
                                                              encoding="utf8")


COUNTERMEASURES = [
    ("Setup program at the brakes: top 12 part-operations, operator assignment, shift handover (P4)", "Brake supervisor, manufacturing engineering", "May 2026"),
    ("Second shift on the robotic weld cell", "Production manager", "April 2026"),
    ("Planned Saturday brake shift every week, November through February", "Plant manager", "November 2026"),
]


def control():
    """The target, the countermeasures and the follow-up, for the Recommendation section."""
    target = (f"{pct(required, 0)} of jobs shipped by the promised date in every quarter.")
    follow = ("Quarterly re-validation of the model against the actual lead time, WIP, utilization and on-time delivery. Saturday shifts and extended hours at the brakes reported "
              "monthly against the model's expected values.")
    return recommendation_block(target, COUNTERMEASURES, follow)


def main():
    report()
    print("wrote docs/reports/p5_release_control.html")


if __name__ == "__main__":
    main()
