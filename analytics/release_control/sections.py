"""Release control and the shop model: the data, tables and figures of its part of the report, from the scenario runs and the marts.

Built by analytics.reports.options_tested.
The scenario runs come from analytics.release_control.scenarios and validate (results/scenario_runs.csv, results/validation_quarters.csv).
"""
from pathlib import Path

import numpy as np
import pandas as pd

from analytics.db import q
from analytics.release_control.scenarios import OUT, QUARTERS, summarize, versus
from analytics.release_control.validate import TOLERANCE, measured
from analytics.style.style import ACCENT, AMBER, BRAND_BLUE, DOCS, GREY, LIGHT_BLUE, RED, fig, pct, save_conformed as save, table

YEAR, REST = 2025, "Q2 to Q4"
RES = Path(__file__).resolve().parent / "results"
S0, S8 = "S0 Current practice", "S8 Setup reduction"
SHORT = {"S1 WIP cap 240": "WIP cap 240", "S1 WIP cap 210": "WIP cap 210", "S1 WIP cap 180": "WIP cap 180",
         "S2 Constraint-paced release (3 days of brake work)": "Constraint-paced release", "S3 Earliest due date": "Earliest due date",
         "S3 Critical ratio": "Critical ratio", "S3 Shortest processing time, brakes only": "Shortest processing time, brakes",
         "S4 Light work first on B1 and B2 when the B3 to B5 queue exceeds 2 days": "Light work ahead of heavy on B1 and B2",
         "S5 Second shift on the robotic weld cell": "Weld cell second shift", "S6 Third weekly color day for black": "Third color day for black",
         "S7 Planned Saturday brake shift, November to February": "Planned Saturdays, November to February", S8: "Setup reduction", S0: "Current practice"}
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
def fig_effects(name="release_control_scenario_effects", h=5.0, scen=None):
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
    return save(f, "release_control_wip_cap", "On-time delivery against release hold under a WIP cap")


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
        for name, m in (("No-capital package at the load-based quote table", "on_time_delivery_quote_table"),
                        ("No-capital package at the trailing 13-week rule", "on_time_delivery_load_aware")):
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
            for rule, m, lm in (("Load-based quote table", "on_time_delivery_quote_table", "promises_longer_quote_table"),
                                ("Routing class, trailing 13 weeks", "on_time_delivery_load_aware", "promises_longer_than_fixed_quote")):
                rows.append([label, name, rule, pct(a["mean"]), pct(v(p, sc, m)), paired(period, sc, m, sc, "on_time_delivery"), pct(v(p, sc, lm), 0)])
    return table(pd.DataFrame(rows, columns=["Period", "Floor", "Rule", "On time at the promised dates as made", "On time at the rule", "Difference (points)",
                                             "Non-rush promised lead times longer than the fixed quote"]))
