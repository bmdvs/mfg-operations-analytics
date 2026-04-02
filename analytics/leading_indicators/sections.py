"""Leading indicators: the data, tables and figures of its part of the report, from the marts.

Built by analytics.reports.quoting_and_early_warning.
"""
import numpy as np
import pandas as pd

from analytics.db import q
from analytics.leading_indicators import analysis as A
from analytics.style.style import ACCENT, AMBER, BRAND_BLUE, DOCS, GREEN, GREY, LIGHT_BLUE, RED, fig, pct, save_conformed as save, table

YEAR, REST = A.YEAR, "Q2 to Q4"
D = A.load()
W = D["w"]
CA, CE = A.cross_correlation(D, False).set_index("indicator"), A.cross_correlation(D, True).set_index("indicator")
LA, LE = A.correlation_by_lag(D, False), A.correlation_by_lag(D, True)
DL, DEC, LT = A.decline_leads(D)
DL = DL.set_index("indicator")
BANDS, THR, SHORT, KIT, OT, BYQ = A.backlog_bands(D), A.backlog_threshold(D).set_index("period"), A.short_promises(D).set_index("period"), \
    A.kit_and_material(D).set_index("period"), A.overtime(D), A.by_quarter(D)
OTS, LASER, BACKLOG, BRAKES, OVERTIME = "On-time start rate", "Jobs waiting at the lasers", "Brake backlog at release (days)", "Jobs waiting at the brakes", \
    "Overtime labor hours at the brakes"
RELEASED, PROMISED, KITS = "Brake standard hours released", "Jobs released late", "Kit completeness"
SETUP, ADHERENCE, OUTSIDE = "Setup efficiency at the brakes", "Schedule adherence", "Outside-processing receipts on time"
COL = {l: c for c, l, _, _ in A.INDICATORS}
SIGN = {l: s for _, l, s, _ in A.INDICATORS}
PY, PR, PALL = f"{YEAR}", f"{YEAR} {REST}", "2023 to 2025"
otd = q(f"select avg(on_time::int) as y, avg(on_time::int) filter (where quarter(ship_date) >= 2) as r from marts.mart_job_lead_time where year(ship_date) = {YEAR}").iloc[0]

DEFS = [
    (OTS, "In-house operations planned to start in the week that had started by the planned date; operations planned before the job's release are left out", "lower"),
    (SETUP, "Brake setup standard hours over actual setup hours, setups started in the week", "lower"),
    (ADHERENCE, "Operations started in the week whose planned start is no earlier than that of the operation the machine started before it", "lower"),
    (OVERTIME, "Brake labor hours on Saturday and after 22:00 on days with an extended second shift", "higher"),
    (OUTSIDE, "Outside-processing PO lines received in the week on or before the promised date", "lower"),
    (KITS, "Kit checks in the week with result complete (job-specific material only)", "lower"),
    (BACKLOG, "Mean, over jobs released in the week, of the brake work waiting at release: standard hours at the brakes' actual-over-standard ratio, in days "
              "of crewed brake capacity", "higher"),
    (PROMISED, "Jobs released in the week with fewer working days to the promised date than the standard 10, 15 or 20, rush included", "higher"),
    (RELEASED, "Brake standard hours on jobs released in the week", "higher"),
    (LASER, "Mean daily jobs at the lasers in the week", "higher"),
    (BRAKES, "Mean daily jobs at the brakes in the week", "higher"),
]


def r2(x):
    return "" if pd.isna(x) else f"{x:+.2f}"


def d1(x):
    return f"{x:.1f}"


def n0(x):
    return f"{x:,.0f}"


def share(x):
    return "under 0.001" if x == 0 else f"{x:.3f}"


def above(c, name):
    r = c.loc[name]
    return bool(r["r_best_lead"] > r["shuffled_p95"] and r["r_best_lead"] > r["shifted_p95"])


def join_and(xs):
    xs = list(xs)
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


def word(n):
    return ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven"][int(n)]


def wk(ts):
    return f"{ts:%B} {ts.day}, {ts.year}"


ABOVE_E = [n for n in CE.index if above(CE, n)]
ABOVE_A = [n for n in CA.index if above(CA, n)]
ONSETS = DEC["position"].tolist()
counts = {}
for p_ in (0.03, 0.04, 0.05, 0.06):
    A.DECLINE_POINTS = p_
    counts[p_] = len(A.declines(D))
A.DECLINE_POINTS = 0.05
n_pre, n_all = int(W["operations_planned_before_release"].sum()), int(W["operations_planned"].sum() + W["operations_planned_before_release"].sum())
build = DEC[DEC["onset"] == DEC.loc[DEC["otd_low"].idxmin(), "onset"]].iloc[0]
laser_before = W["wip_at_laser"].iloc[int(build["position"]) - A.LOOKBACK:int(build["position"])]
quiet = BYQ.loc[BYQ.index < pd.Period("2024Q4"), "wip_at_laser"]
PAIR = A.pair_leads(D, OTS, LASER)
best_weekly = PAIR["lead"]
PAIR_TEXT = (f"One of the two weekly indicators moved {join_and([f'{x:.0f}' for x in best_weekly])} weeks before the four declines, against "
             f"{PAIR['shuffled_expected']:.1f} declines expected on shuffled series and {PAIR['shifted_expected']:.1f} on shifted (share at or above "
             f"{PAIR['shuffled_p']:.2f} and {PAIR['shifted_p']:.2f})"
             + ("; the pair is not distinguishable from chance." if max(PAIR["shuffled_p"], PAIR["shifted_p"]) > 0.05 else "."))


laser_sig = A.signal(W["wip_at_laser"].to_numpy(dtype=float), 1)
LAST_RUN = 0
while LAST_RUN < len(laser_sig) and laser_sig[-1 - LAST_RUN]:
    LAST_RUN += 1


REVIEW = [l for _, l, _, g in A.INDICATORS if g == "review set"]


# ── figures ─────────────────────────────────────────────────────────────────
HIGHLIGHT = [(OTS, BRAND_BLUE), (LASER, AMBER), (BACKLOG, RED), (OVERTIME, GREEN)]


def lag_panel(ax, L, C, title):
    x = list(L.columns)
    for name in L.index:
        if name not in dict(HIGHLIGHT):
            ax.plot(x, L.loc[name], color=GREY, linewidth=0.9, label="Other series" if name == L.index[1] else None)
    for name, color in HIGHLIGHT:
        ax.plot(x, L.loc[name], color=color, linewidth=1.8, marker="o", markersize=3, label=name)
    ax.axhspan(-1, C["shuffled_p95"].max(), color=LIGHT_BLUE, alpha=0.35, linewidth=0)
    ax.axhline(0, color=GREY, linewidth=0.8)
    ax.set_ylim(-0.45, 1.0)
    ax.set_xlabel("Weeks the series leads on-time delivery", fontsize=9.5)
    ax.set_title(title, fontsize=10, loc="left")


def fig_lags(name="leading_indicators_correlation_by_lead", h=3.8, both=True):
    if both:
        f, axes = fig(h=h, ncols=2, sharey=True)
        lag_panel(axes[0], LE, CE, "Event weeks excluded")
        lag_panel(axes[1], LA, CA, "All weeks")
        axes[0].set_ylabel("Correlation, adverse direction")
        hs, ls = axes[1].get_legend_handles_labels()
        f.legend(hs, ls, frameon=False, fontsize=8.5, loc="lower center", ncols=5)
        f.tight_layout(rect=(0, 0.07, 1, 1))
        return save(f, name, "Correlation with on-time delivery by weeks of lead")
    else:
        f, ax = fig(h=h)
        lag_panel(ax, LE, CE, "Event weeks excluded")
        ax.set_ylabel("Correlation, adverse direction")
        ax.legend(frameon=False, fontsize=8, loc="upper right", ncols=3)
    f.tight_layout()
    return save(f, name, "Correlation with on-time delivery by weeks of lead")


def fig_declines():
    f, axes = fig(h=6.2, nrows=3, sharex=True)
    o4 = A.rolling_otd(W) * 100
    axes[0].plot(W.index, o4, color=BRAND_BLUE, linewidth=1.5)
    axes[0].set_ylabel("On time, trailing\n4 weeks (%)", fontsize=9)
    for name, ax, scale, lab in ((OTS, axes[1], 100, "On-time start\nrate (%)"), (LASER, axes[2], 1, "Jobs waiting at\nthe lasers")):
        x = W[COL[name]].to_numpy(dtype=float)
        sig = A.signal(x, SIGN[name])
        ax.plot(W.index, x * scale, color=ACCENT, linewidth=1.2)
        for i in np.where(sig)[0]:
            ax.axvspan(W.index[i] - pd.Timedelta(days=3.5), W.index[i] + pd.Timedelta(days=3.5), color=AMBER, alpha=0.3, linewidth=0)
        ax.set_ylabel(lab, fontsize=9)
    for ax in axes:
        for t in DEC["onset"]:
            ax.axvline(t, color=RED, linewidth=1.1, linestyle="--")
    f.tight_layout()
    return save(f, "leading_indicators_declines", "On-time delivery, the on-time start rate and jobs waiting at the lasers by week")


def fig_backlog():
    f, ax = fig(h=3.2, w=7.6)
    b = BANDS.pivot(index="band", columns="period", values="late_rate")
    x = np.arange(len(b))
    n = BANDS.pivot(index="band", columns="period", values="jobs")
    for off, per, color, lab in ((-0.2, PY, BRAND_BLUE, PY), (0.2, PR, AMBER, REST)):
        h = (b[per] * 100).fillna(0)
        ax.bar(x + off, h, 0.4, color=color, label=lab)
        for xi, hi, ni in zip(x + off, h, n[per]):
            ax.annotate(f"{ni:,.0f}", (xi, hi), textcoords="offset points", xytext=(0, 2), ha="center", fontsize=6.5)
    ax.set_ylim(0, float(np.nanmax(b[[PY, PR]].to_numpy())) * 100 * 1.15)
    ax.set_xticks(x)
    ax.set_xticklabels(b.index, fontsize=9)
    ax.set_xlabel("Brake backlog at release (days)")
    ax.set_ylabel("Late jobs (%)")
    ax.legend(frameon=False, fontsize=9)
    f.tight_layout()
    return save(f, "leading_indicators_late_rate_by_backlog", "Late rate by brake backlog at release")


# ── tables ──────────────────────────────────────────────────────────────────
def t_summary(short=False):
    if short:
        rows = [[name, f"{r2(CE.loc[name, 'r_best_lead'])} at {CE.loc[name, 'best_lead_weeks']}", "yes" if above(CE, name) else "no",
                 f"{r2(CA.loc[name, 'r_best_lead'])} at {CA.loc[name, 'best_lead_weeks']}", "yes" if above(CA, name) else "no"] for name in CA.index]
        return table(pd.DataFrame(rows, columns=["Indicator", "Event excluded: r at best lead (weeks)", "Above both", "All weeks: r at best lead (weeks)",
                                                 "Above both, all weeks"]))
    sub = ["Lead (weeks)", "r", "Shuffled 95th", "Shifted 95th", "Above both", "Peak lag (weeks)"]
    head = ("<tr><th rowspan='2'>Indicator</th><th colspan='6' style='text-align:center'>Event excluded</th>"
            "<th colspan='6' style='text-align:center'>All weeks</th></tr><tr>" + "".join(f"<th>{c}</th>" for c in sub * 2) + "</tr>")
    body = ""
    for name in CA.index:
        cells = f"<td>{name}</td>"
        for c in (CE, CA):
            r = c.loc[name]
            for v_ in (r["best_lead_weeks"], r2(r["r_best_lead"]), r2(r["shuffled_p95"]), r2(r["shifted_p95"]), "yes" if above(c, name) else "no",
                       r["peak_lag_weeks"]):
                cells += f"<td class='num'>{v_}</td>"
        body += f"<tr>{cells}</tr>"
    return f"<table class='data'><thead>{head}</thead><tbody>{body}</tbody></table>"


def trigger_record(name):
    r = DL.loc[name]
    return (f"Moved before {r['preceded']} of {r['declines']} declines; {r['signal_episodes']} episodes, {r['episodes_followed_by_decline']} followed by a decline "
            f"within {A.LOOKBACK} weeks")


def review_rows():
    ta, tr, sr, ky, kr = THR.loc[PALL], THR.loc[PR], SHORT.loc[PR], KIT.loc[PY], KIT.loc[PR]
    move = "4-week mean {} the 13 weeks before by more than one standard deviation of those weeks"
    return [
        [OTS, "Weekly", move.format("below"), trigger_record(OTS)],
        [LASER, "Weekly", move.format("above"), f"{trigger_record(LASER)}; {n0(laser_before.min())} to {n0(laser_before.max())} jobs in the {A.LOOKBACK} weeks before the "
                                f"{wk(build['onset'])} decline against {n0(quiet.min())} to {n0(quiet.max())} as the quarterly mean before it"],
        ["Brake backlog at release", "Job, at release", f"Above {A.BACKLOG_THRESHOLD:.0f} days",
         f"Late rate {pct(ta['late_rate_above'])} above and {pct(ta['late_rate_below'])} at or below, 2023 to 2025; marks {pct(tr['share_of_all_jobs_above'])} of jobs "
         f"in {REST}"],
        ["Released late", "Job, at release", "Fewer working days to the promised date than the standard 10, 15 or 20",
         f"{pct(sr['share_of_jobs'])} of jobs and {pct(sr['share_of_late_jobs'])} of late jobs in {REST}; flat as a weekly series"],
        ["Kit shortage", "Job, at the kit check", "Kit check result short",
         f"{pct(ky['share_of_days_short_kit'])} of material lost days ({pct(kr['share_of_days_short_kit'])} in {REST}) against a short rate of "
         f"{pct(ky['short_rate_all_kit_checks'])}"],
    ]


def t_review():
    return table(pd.DataFrame(review_rows(), columns=["Indicator", "Grain", "Trigger", "Record"]))


def t_quarter():
    fmt = {"on_time_delivery": "{:.1%}", "on_time_start_rate": "{:.1%}", "brake_setup_efficiency": "{:.2f}", "schedule_adherence": "{:.1%}",
           "brake_overtime_labor_hours": "{:.1f}", "outside_receipt_on_time": "{:.1%}", "kit_complete_rate": "{:.1%}", "brake_backlog_days_at_release": "{:.2f}",
           "promised_inside_standard_share": "{:.1%}", "brake_std_hours_released": "{:.0f}", "wip_at_laser": "{:.0f}", "wip_at_brakes": "{:.0f}"}
    t = pd.DataFrame({f"{i.year} Q{i.quarter}": [fmt[c].format(v) for c, v in r.items()] for i, r in BYQ.iterrows()})
    t.insert(0, "Weekly mean", ["On-time delivery"] + [A.LABEL[c] for c in BYQ.columns[1:]])
    return table(t)


def t_lags(L):
    t = L.map(r2)
    t.columns = [f"{k} wk" for k in t.columns]
    t.insert(0, "Indicator", t.index)
    return table(t)


def t_declines():
    rows = [[wk(r.onset), pct(r.otd_before), pct(r.otd_at_onset), pct(r.otd_low)] for r in DEC.itertuples()]
    return table(pd.DataFrame(rows, columns=["Decline starts, week of", f"On time, {A.BASE} weeks before", f"On time, {A.WINDOW} weeks at the start",
                                             f"Lowest {A.WINDOW}-week figure in the next {A.BASE} weeks"]))


def t_leads():
    rows = []
    for name, r in DL.iterrows():
        rows.append([name, f"{r['preceded']} of {r['declines']}", "" if pd.isna(r["median_lead_weeks"]) else d1(r["median_lead_weeks"]),
                     f"{r['shuffled_expected']:.2f}", share(r["shuffled_p"]), f"{r['shifted_expected']:.2f}", share(r["shifted_p"]), r["signal_weeks"],
                     r["signal_episodes"], r["episodes_followed_by_decline"]])
    return table(pd.DataFrame(rows, columns=["Indicator", "Declines preceded", "Median lead (weeks)", "Shuffled: expected", "Shuffled: share at or above",
                                             "Shifted: expected", "Shifted: share at or above", "Weeks moved", "Signal episodes",
                                             f"Episodes followed by a decline within {A.LOOKBACK} weeks"]))


def t_lead_by_decline():
    t = LT.map(lambda x: "" if pd.isna(x) else f"{x:.0f}")
    t.columns = [wk(pd.Timestamp(c)) for c in t.columns]
    t.insert(0, "Indicator", t.index)
    return table(t)


def t_bands():
    r = BANDS.pivot(index="band", columns="period", values="late_rate")
    n = BANDS.pivot(index="band", columns="period", values="jobs")
    rows = [[b] + [x for p in (PALL, PY, PR) for x in (n0(n.loc[b, p]), "" if pd.isna(r.loc[b, p]) else pct(r.loc[b, p]))] for b in r.index]
    return table(pd.DataFrame(rows, columns=["Brake backlog at release (days)"] + [f"{p}: {x}" for p in (PALL, PY, PR) for x in ("jobs", "late rate")]))


def t_threshold():
    rows = [[p, n0(r["jobs"]), n0(r["late_jobs"]), n0(r["late_jobs_above"]), pct(r["share_of_late_jobs_above"]), pct(r["share_of_all_jobs_above"]),
             pct(r["late_rate_above"]), pct(r["late_rate_below"])] for p, r in THR.iterrows()]
    return table(pd.DataFrame(rows, columns=["Jobs released in", "Jobs", "Late jobs", "Late jobs released above the threshold", "Share of late jobs",
                                             "Share of all jobs (chance)", "Late rate above", "Late rate at or below"]))


def t_short():
    rows = [[p, n0(r["jobs"]), n0(r["promised_inside"]), pct(r["share_of_jobs"]), pct(r["late_rate_inside"]), pct(r["late_rate_other"]),
             pct(r["share_of_late_jobs"])] for p, r in SHORT.iterrows()]
    return table(pd.DataFrame(rows, columns=["Jobs released in", "Jobs", "Released late", "Share of jobs (chance)", "Late rate, released late",
                                             "Late rate, other jobs", "Share of late jobs"]))


def t_kit():
    rows = [[p, n0(r["late_jobs_with_material_days"]), n0(r["material_days"]), n0(r["jobs_with_kit_check"]), n0(r["jobs_with_short_kit"]),
             n0(r["days_on_jobs_with_short_kit"]), pct(r["share_of_days_short_kit"]), pct(r["short_rate_all_kit_checks"])] for p, r in KIT.iterrows()]
    return table(pd.DataFrame(rows, columns=["Jobs shipped in", "Late jobs with material days", "Material lost days", "With a kit check", "With a short kit",
                                             "Lost days on short kits", "Share of material lost days on short kits", "Short rate, all kit checks (chance)"]))


def t_overtime():
    w = OT["by_work_center"]
    names = {"press_brake": "Press brake", "laser": "Laser"}
    a = pd.DataFrame([[names.get(i, i)] + [n0(v) for v in r] for i, r in w.iterrows()], columns=["Work center"] + [str(c) for c in w.columns])
    fam = OT["by_family"]
    b = pd.DataFrame([[f.capitalize(), n0(h), pct(h / fam.sum())] for f, h in fam.items()], columns=["Part family", f"Brake overtime labor hours, {YEAR}", "Share"])
    return table(a) + table(b)
