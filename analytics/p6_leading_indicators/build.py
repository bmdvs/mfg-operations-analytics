"""P6 leading indicators: report and figures, from the marts.

Usage: python -m analytics.p6_leading_indicators.build
"""
import numpy as np
import pandas as pd

from analytics.db import q
from analytics.p6_leading_indicators import analysis as A
from analytics.style.style import ACCENT, AMBER, BRAND_BLUE, DOCS, GREEN, GREY, LIGHT_BLUE, RED, fig, pct, save, report_shell, table
from analytics.style.style import recommendation_block

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
RELEASED, PROMISED, KITS = "Brake standard hours released", "Lines promised inside the standard lead time", "Kit completeness"
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
    (PROMISED, "Jobs released in the week whose promise is shorter than the standard 10, 15 or 20 days, rush included", "higher"),
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


def fig_lags(name="p6_correlation_by_lead", h=3.8, both=True):
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
    return save(f, "p6_declines", "On-time delivery, the on-time start rate and jobs waiting at the lasers by week")


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
    return save(f, "p6_late_rate_by_backlog", "Late rate by brake backlog at release")


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
        ["Promise inside the standard lead time", "Job, at release", "Promise shorter than 10, 15 or 20 days",
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
    return table(pd.DataFrame(rows, columns=["Jobs released in", "Jobs", "Promised inside the standard", "Share of jobs (chance)", "Late rate, promised inside",
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


# ── report ──────────────────────────────────────────────────────────────────
HEADER_META = (f"Custom sheet-metal fabrication job shop, about 120 employees, one plant. Weekly series from {wk(W.index.min())} to {wk(W.index.max())} "
               f"({len(W)} weeks); job-level figures for {YEAR}, whole year and {REST}.<br>"
               f"Sources: ERP, shop-floor data collection, purchasing and kit-check exports (batch {D['batch']}). On-time delivery by ship week; "
               f"brake backlog in working days of crewed brake capacity.")


def report():
    e, a = CE.loc[OTS], CA.loc[OTS]
    o, la, bk, br, ov = DL.loc[OTS], DL.loc[LASER], DL.loc[BACKLOG], DL.loc[BRAKES], DL.loc[OVERTIME]
    ty, tr, tall = THR.loc[PY], THR.loc[PR], THR.loc[PALL]
    sy, sr = SHORT.loc[PY], SHORT.loc[PR]
    ky, kr = KIT.loc[PY], KIT.loc[PR]
    bands = BANDS.pivot(index="band", columns="period", values="late_rate")
    others_e = [n for n in ABOVE_E if n != OTS]
    b = []
    b.append("<h2 id='f1'>1. What was tested</h2>")
    b.append(f"<p>Of eleven weekly series tested against on-time delivery over {len(W)} weeks, {word(len(ABOVE_E))} leads it in ordinary weeks and {word(len(ABOVE_A))} exceed "
             f"chance with the 2024 year-end build included. Each series is compared with two chance levels, and with the {word(len(DEC))} declines in on-time delivery "
             f"in the period. An indicator counts as above chance only when it exceeds both.</p>")
    b.append(t_summary())
    b.append(f"<div class='caption'>Table 1. Largest correlation with on-time delivery at a lead of 1 to {A.MAX_LAG} weeks, with the 95th percentile of the same "
             f"statistic on {A.SHUFFLES:,} shuffled and shifted series; event weeks are {wk(A.EVENT[0])} to {wk(A.EVENT[1])}.</div>")

    b.append("<h2 id='f2'>2. Ordinary weeks</h2>")
    b.append(f"<p>The on-time start rate correlates {r2(e['r_best_lead'])} with on-time delivery {e['best_lead_weeks']} week later, against a 95th percentile of "
             f"{r2(e['shuffled_p95'])} on shuffled series and {r2(e['shifted_p95'])} on shifted series. "
             + ("No other series exceeds both comparisons with the event weeks excluded." if not others_e else
                f"{join_and(others_e)} also exceed both.") + "</p>")
    b.append(fig_lags())
    b.append(f"<div class='caption'>Figure 1. Correlation of each series with on-time delivery by weeks of lead, event weeks excluded and all weeks; the band is the "
             f"shuffled 95th percentile.</div>")

    b.append("<h2 id='f3'>3. The 2024 year-end build</h2>")
    b.append(f"<p>Jobs waiting at the lasers led on-time delivery by {CA.loc[LASER, 'best_lead_weeks']} weeks ({r2(CA.loc[LASER, 'r_best_lead'])}): "
             f"{n0(laser_before.min())} to {n0(laser_before.max())} jobs in the {A.LOOKBACK} weeks before the decline of {wk(build['onset'])} against "
             f"{n0(quiet.min())} to {n0(quiet.max())} as the quarterly mean before it. The on-time start rate ({r2(a['r_best_lead'])} at {a['best_lead_weeks']} week), brake "
             f"backlog at release ({r2(CA.loc[BACKLOG, 'r_peak'])} at lag {CA.loc[BACKLOG, 'peak_lag_weeks']}), jobs waiting at the brakes "
             f"({r2(CA.loc[BRAKES, 'r_lag0'])} at lag 0) and overtime labor hours at the brakes ({r2(CA.loc[OVERTIME, 'r_peak'])} at lag "
             f"{CA.loc[OVERTIME, 'peak_lag_weeks']}) move with on-time delivery and describe the event under way. Brake standard hours released reaches "
             f"{r2(CA.loc[RELEASED, 'r_best_lead'])} at {CA.loc[RELEASED, 'best_lead_weeks']} weeks, the edge of the range tested."
             + (f" In the week of {wk(W.index[-1])}, jobs waiting at the lasers stood at {n0(W['wip_at_laser'].iloc[-1])}, above the trigger in Table 2."
                if LAST_RUN else "") + "</p>")

    b.append("<h2 id='f4'>4. Declines</h2>")
    leads_o = [f"{x:.0f}" for x in LT.loc[OTS]]
    b.append(f"<p>On-time delivery declined {word(len(DEC))} times in 36 months, in the weeks of {join_and([wk(t) for t in DEC['onset']])}; thresholds of 3, 4 and 5 "
             f"points give the same {word(counts[0.05])} and 6 points gives {word(counts[0.06])}. The on-time start rate moved before all {word(o['preceded'])}, by "
             f"{join_and(leads_o)} weeks (median {d1(o['median_lead_weeks'])}), against {d1(o['shuffled_expected'])} expected on shuffled series and "
             f"{d1(o['shifted_expected'])} on shifted (share at or above {o['shuffled_p']:.2f} and {o['shifted_p']:.2f}). Brake backlog at release, jobs waiting at the lasers and jobs waiting at the brakes each moved before {bk['preceded']} of "
             f"{bk['declines']} against {d1(min(bk['shuffled_expected'], la['shuffled_expected'], br['shuffled_expected']))} to "
             f"{d1(max(bk['shifted_expected'], la['shifted_expected'], br['shifted_expected']))} expected, which is not distinguishable from chance. With four "
             f"declines the count separates the on-time start rate from the rest and nothing else. The on-time start rate gave {o['signal_episodes']} signal "
             f"episodes and {o['episodes_followed_by_decline']} were followed by a decline within {A.LOOKBACK} weeks; brake backlog at release "
             f"{bk['signal_episodes']} and {bk['episodes_followed_by_decline']}; jobs waiting at the lasers {la['signal_episodes']} and "
             f"{la['episodes_followed_by_decline']}.</p>")
    b.append(fig_declines())
    b.append("<div class='caption'>Figure 2. On-time delivery with the four declines marked, and the on-time start rate and jobs waiting at the lasers with the "
             "weeks each had moved shaded.</div>")

    b.append("<h2 id='f5'>5. Brake backlog at release</h2>")
    b.append(f"<p>Jobs released with more than {A.BACKLOG_THRESHOLD:.0f} days of brake work waiting are {pct(ty['share_of_late_jobs_above'])} of the late jobs "
             f"released in {YEAR} against {pct(ty['share_of_all_jobs_above'])} of all jobs, and {pct(tr['share_of_late_jobs_above'])} against "
             f"{pct(tr['share_of_all_jobs_above'])} in {REST}. The late rate is {pct(bands[PY].iloc[:3].min())} to {pct(bands[PY].iloc[:3].max())} below 3 days and "
             f"{pct(bands[PY].iloc[3])}, {pct(bands[PY].iloc[4])}, {pct(bands[PY].iloc[5])} and {pct(bands[PY].iloc[6])} in the bands above. Every job released in "
             f"the first quarter was above the threshold; in {REST} it marks {pct(tr['share_of_all_jobs_above'])} of jobs.</p>")
    b.append(fig_backlog())
    b.append(f"<div class='caption'>Figure 3. Late rate by brake backlog at release, jobs released in {YEAR} and in {REST}, with the number of jobs on each bar.</div>")

    b.append("<h2 id='f6'>6. Lines promised inside the standard lead time</h2>")
    b.append(f"<p>They are {pct(sr['share_of_jobs'])} of jobs and {pct(sr['share_of_late_jobs'])} of late jobs released in {REST} (late rate "
             f"{pct(sr['late_rate_inside'])} against {pct(sr['late_rate_other'])}), and {pct(sy['share_of_jobs'])} and {pct(sy['share_of_late_jobs'])} for the year. "
             f"The weekly share is flat at {pct(BYQ['promised_inside_standard_share'].min(), 0)} to {pct(BYQ['promised_inside_standard_share'].max(), 0)} by quarter "
             f"and does not lead as a series; the flag identifies the jobs.</p>")

    b.append("<h2 id='f7'>7. Kit completeness and material lateness</h2>")
    b.append(f"<p>{pct(ky['share_of_days_short_kit'])} of material-caused lost days in {YEAR} are on jobs with a short kit ({pct(kr['share_of_days_short_kit'])} in "
             f"{REST}) against a short rate of {pct(ky['short_rate_all_kit_checks'])} on all kit checks. As a weekly series kit completeness does not lead "
             f"on-time delivery in ordinary weeks ({r2(CE.loc[KITS, 'r_best_lead'])}).</p>")

    b.append("<h2 id='f8'>8. Not leading</h2>")
    b.append(f"<p>Setup efficiency at the brakes ({r2(CE.loc[SETUP, 'r_best_lead'])} in ordinary weeks, {r2(CA.loc[SETUP, 'r_best_lead'])} in all weeks) and "
             f"outside-processing receipts on time ({r2(CE.loc[OUTSIDE, 'r_best_lead'])}, {r2(CA.loc[OUTSIDE, 'r_best_lead'])}) do not exceed chance. Schedule "
             f"adherence has the opposite sign ({r2(CA.loc[ADHERENCE, 'r_lag0'])} at lag 0 in all weeks): adherence is higher when on-time delivery is lower. "
             f"Overtime labor hours at the brakes move with on-time delivery ({r2(CA.loc[OVERTIME, 'r_lag0'])} at lag 0) and not ahead of it "
             f"({r2(CE.loc[OVERTIME, 'r_best_lead'])} in ordinary weeks).</p>")

    b.append("<h2 id='f9'>9. The weekly review set</h2>")
    b.append(f"<p>Two weekly indicators and three job-level flags carry the lead found. {PAIR_TEXT}</p>")
    b.append(t_review())
    b.append("<div class='caption'>Table 2. The review set: indicator, grain, trigger and record.</div>")

    b.append("<h2 id='rec'>Recommendation</h2>")
    b.append("<p>Production control reviews the on-time start rate and jobs waiting at the lasers weekly against the trigger in Table 2, on the dashboard's leading "
             "panel. Flag at release every job released with more than 3 days of brake backlog and every line promised inside the standard lead time, and flag a "
             "short kit at the kit check. Drop setup efficiency, schedule adherence, outside-processing receipts and overtime from the leading set; they remain "
             "measures of their own work centers.</p>")

    b.append(control())

    b.append("<h2 id='method'>Method and data</h2>")
    b.append(f"<p>Correlations are signed so that positive means the indicator's adverse movement goes with lower on-time delivery; the statistic is the largest "
             f"correlation at a lead of 1 to {A.MAX_LAG} weeks. Shuffled, the specified comparison, puts the indicator's weeks in random order; shifted moves the "
             f"indicator in time by a random 13 weeks or more and keeps each series' week-to-week pattern. Both use {A.SHUFFLES:,} series.<br>"
             f"A decline starts in the first week the on-time delivery of the trailing {A.WINDOW} weeks is more than 5 points below that of the {A.BASE} weeks "
             f"before them, at least {A.LOOKBACK} weeks after the last. An indicator has moved when its {A.WINDOW}-week mean is adverse to the {A.BASE} weeks before "
             f"by more than one standard deviation of those weeks; a decline is preceded when the indicator moved in the {A.LOOKBACK} weeks before it.<br>"
             f"The on-time start rate leaves out the {n0(n_pre)} of {n0(n_all)} in-house operations ({pct(n_pre / n_all)}) planned to start before the job's "
             f"release; they belong to lines promised inside the standard lead time (P7). {int(W['otd'].isna().sum())} week shipping fewer than {A.MIN_JOBS} jobs "
             f"carries no on-time delivery figure. The first four weeks of 2023 are left out of every weekly series: the "
             f"jobs in process when the records begin have no labor transactions for their earlier operations.<br>"
             f"A recorded kit shortage is one trigger of the P2 material rule, so the share of material lost days on short kits is in part the rule's own "
             f"definition; {n0(ky['late_jobs_with_material_days'] - ky['jobs_with_kit_check'])} of {n0(ky['late_jobs_with_material_days'])} jobs with material "
             f"days have no kit check. Overtime is labor hours on Saturdays and after 22:00 on days with an extended second shift, not the shift counts of "
             f"P5.</p>")

    b.append("<h2 id='appendix'>Appendix</h2>")
    b.append("<h3>Table 3. Indicators and definitions</h3>" + table(pd.DataFrame(DEFS, columns=["Indicator", "Definition", "Adverse direction"])))
    b.append("<h3>Table 4. Weekly means by quarter</h3>" + t_quarter())
    b.append("<h3>Table 5. Correlation by weeks of lead, all weeks</h3>" + t_lags(LA))
    b.append("<h3>Table 6. Correlation by weeks of lead, event weeks excluded</h3>" + t_lags(LE))
    b.append("<h3>Table 7. On-time delivery declines</h3>" + t_declines())
    b.append("<h3>Table 8. Indicators ahead of the declines</h3>" + t_leads())
    b.append("<h3>Table 9. Lead in weeks by decline</h3>" + t_lead_by_decline())
    b.append("<h3>Table 10. Late rate by brake backlog at release</h3>" + t_bands())
    b.append(f"<h3>Table 11. Brake backlog above {A.BACKLOG_THRESHOLD:.0f} days at release</h3>" + t_threshold())
    b.append("<h3>Table 12. Lines promised inside the standard lead time</h3>" + t_short())
    b.append("<h3>Table 13. Kit completeness and material-caused lateness</h3>" + t_kit())
    b.append("<h3>Table 14. Overtime labor hours by work center and part family</h3>" + t_overtime())
    toc = [("f1", "What was tested"), ("f2", "Ordinary weeks"), ("f3", "Year-end build"), ("f4", "Declines"), ("f5", "Brake backlog"), ("f6", "Short promises"),
           ("f7", "Kit completeness"), ("f8", "Not leading"), ("f9", "Review set"), ("rec", "Recommendation"), ("method", "Method and data"),
           ("appendix", "Appendix")]
    (DOCS / "reports").mkdir(parents=True, exist_ok=True)
    (DOCS / "reports" / "p6_leading_indicators.html").write_text(report_shell("Leading indicators", "Project 6 report", HEADER_META, "\n".join(b), toc), encoding="utf8")


COUNTERMEASURES = [
    ("Weekly review of the on-time start rate and jobs waiting at the lasers against their triggers", "Production control manager", "February 2026"),
    ("Flags in the ERP release screen: brake backlog above 3 days, promise inside the standard lead time", "Production control, IT", "April 2026"),
    ("Flag on a short kit at the kit check", "Purchasing manager", "March 2026"),
]


def control():
    """The target, the countermeasures and the follow-up, for the Recommendation section."""
    target = ("Every decline in on-time delivery preceded by a flagged indicator at least four weeks earlier.")
    follow = ("The signal and decline record reviewed quarterly: episodes, declines preceded, and the lead in weeks.")
    return recommendation_block(target, COUNTERMEASURES, follow)


def main():
    report()
    print("wrote docs/reports/p6_leading_indicators.html")


if __name__ == "__main__":
    main()
