"""Quoting and early warning from load: the report.

Usage: python -m analytics.reports.quoting_and_early_warning
"""
import pandas as pd

from analytics.leading_indicators import analysis as LA
from analytics.leading_indicators import sections as L
from analytics.quoting import sections as Q
from analytics.reports.layout import Tables, link, page, titled
from analytics.style.style import pct, table

YEAR, REST = Q.YEAR, Q.REST
LATE = "released with fewer working days to the promised date than the standard quoted lead time for the routing class"


def build():
    T = Tables()
    T.add("fixed", f"The fixed quote against the lead time of jobs shipped, by routing class, {YEAR} and {REST}", Q.t_fixed())
    T.add("family", "Promised and actual lead time by part family and routing class", Q.t_family())
    T.add("lines", "Rush lines, jobs released late and standard promises", Q.t_promises())
    T.add("qtable", f"The quote table: 80th-percentile lead time by routing class and brake backlog at release, jobs shipped 2023 to {YEAR}", Q.t_quote_table())
    T.add("rules", f"Four quote rules on non-rush jobs shipped in {YEAR}: share meeting the quote, share quoted longer than the fixed quote, mean quote, and share "
                   f"meeting the quote by release quarter", Q.t_rules())
    T.add("release_class", "Quote rules by release quarter and routing class", Q.t_release_class())
    T.add("band", "Win rate by turnaround band", Q.t_band())
    T.add("strata", "Win rate by complexity group and turnaround", Q.t_strata())
    T.add("rush", "Win rate on rush RFQs by quoted lead time", Q.t_rush())
    T.add("customer", "Win rate by customer: the ten customers with the most quotes", Q.t_group(Q.CUST, "Customer"))
    T.add("groups", "Win rate by key account and part family", Q.t_group(Q.KEY, "Customer group", {True: "Key account", False: "Other"})
          + Q.t_group(Q.FAMW.assign(family=Q.FAMW["family"].str.capitalize()), "Part family"))
    T.add("estimators", "Quote volume and turnaround by estimator", Q.t_estimators() + Q.t_group(Q.EST, "Estimator, 2023 to 2025"))
    T.add("lost", "Lost reasons as entered", Q.t_lost())
    T.add("summary", f"Largest correlation with on-time delivery at a lead of 1 to {LA.MAX_LAG} weeks, with the 95th percentile of the same statistic on "
                     f"{LA.SHUFFLES:,} shuffled and shifted series; event weeks are {L.wk(LA.EVENT[0])} to {L.wk(LA.EVENT[1])}", L.t_summary())
    T.add("defs", "Indicators and definitions", table(pd.DataFrame(L.DEFS, columns=["Indicator", "Definition", "Adverse direction"])))
    T.add("quarter", "Weekly means by quarter", L.t_quarter())
    T.add("lags_all", "Correlation by weeks of lead, all weeks", L.t_lags(L.LA))
    T.add("lags_event", "Correlation by weeks of lead, event weeks excluded", L.t_lags(L.LE))
    T.add("declines", "On-time delivery declines", L.t_declines())
    T.add("leads", "Indicators ahead of the declines", L.t_leads())
    T.add("lead_by", "Lead in weeks by decline", L.t_lead_by_decline())
    T.add("bands", "Late rate by brake backlog at release", L.t_bands())
    T.add("threshold", f"Brake backlog above {LA.BACKLOG_THRESHOLD:.0f} days at release", L.t_threshold())
    T.add("late", "Jobs released late", L.t_short())
    T.add("kit", "Kit completeness and material-caused lateness", L.t_kit())
    T.add("review", "The review set: indicator, grain, trigger and record", L.t_review())
    T.add("overtime", "Overtime labor hours by work center and part family", L.t_overtime())

    fx, pr, nth, d1, n0 = Q.fx, Q.pr, Q.nth, Q.d1, Q.n0
    PY, PR, PX, SC = Q.PY, Q.PR, Q.PX, Q.SC
    ti, to, tr, fq = SC[Q.TABLE_IN], SC[Q.TABLE_OUT], SC[Q.TRAIL], SC[Q.FIXED]
    TURN, TBAND, STRATA, RUSH = Q.TURN, Q.TBAND, Q.STRATA, Q.RUSH
    short = "short promise, not rush"
    b = []

    # 1 ── the quote against lead time
    b.append("<h2 id='f1'>1. The Quote Against Lead Time</h2>")
    b.append(f"<p>A quote is met when the working days from release to ship are at or under it. The fixed quote is 10 days for repeat parts, 15 for new parts and 20 "
             f"with outside processing. Standard promises are order lines that are not rush and not released late ({LATE}). The 10-day repeat quote sits at the "
             f"{nth(fx(PY, 'repeat part', 'percentile_of_quote'))} percentile of {YEAR} repeat lead time "
             f"({nth(fx(PR, 'repeat part', 'percentile_of_quote'))} in {REST}), the 15-day new-part quote at the {nth(fx(PY, 'new part', 'percentile_of_quote'))} "
             f"({nth(fx(PR, 'new part', 'percentile_of_quote'))}) and the 20-day outside-processing quote at the "
             f"{nth(fx(PY, 'outside processing', 'percentile_of_quote'))} ({nth(fx(PR, 'outside processing', 'percentile_of_quote'))}). Standard promises shipped "
             f"{pct(fx(PY, 'all', 'standard_promise_on_time'))} on time for the year and {pct(fx(PR, 'all', 'standard_promise_on_time'))} in {REST}. "
             f"{T.see('fixed', 'family')}</p>")
    b.append(titled(Q.fig_distribution(), "Lead Time of Jobs Shipped by Routing Class, with the Fixed Quote and the Quote Table"))

    b.append("<h3 id='f1_1'>Rush lines and jobs released late</h3>")
    b.append(f"<p>Rush lines ship within the standard lead time on {pct(pr(PY, 'rush', 'quote_met'))} of jobs ({pct(pr(PR, 'rush', 'quote_met'))} in {REST}) and on "
             f"time to their promised date on {pct(pr(PY, 'rush', 'on_time'))} ({pct(pr(PR, 'rush', 'on_time'))}); jobs released late and not flagged rush "
             f"{pct(pr(PY, short, 'quote_met'))} ({pct(pr(PR, short, 'quote_met'))}) and "
             f"{pct(pr(PY, short, 'on_time'))} ({pct(pr(PR, short, 'on_time'))}). They are "
             f"{pct(pr(PY, 'rush', 'share_of_jobs'))} and {pct(pr(PY, short, 'share_of_jobs'))} of jobs and together "
             f"{pct(pr(PY, 'rush', 'share_of_late_jobs') + pr(PY, short, 'share_of_late_jobs'))} of late jobs and "
             f"{pct(pr(PY, 'rush', 'share_of_days_late') + pr(PY, short, 'share_of_days_late'))} of days late for the year, "
             f"{pct(pr(PR, 'rush', 'share_of_late_jobs') + pr(PR, short, 'share_of_late_jobs'))} and "
             f"{pct(pr(PR, 'rush', 'share_of_days_late') + pr(PR, short, 'share_of_days_late'))} in {REST}. {link('lead')} attributes "
             f"{n0(pr(PY, 'rush', 'released_late_days') + pr(PY, short, 'released_late_days'))} of their "
             f"{n0(pr(PY, 'rush', 'days_late') + pr(PY, short, 'days_late'))} days late to the late release itself. {T.see('lines')}</p>")

    # 2 ── a quote table from load
    b.append("<h2 id='f2'>2. A Quote Table From Load</h2>")
    q = Q.QTAB.set_index(["routing_class", "band"])["p80"]
    b.append(f"<p>Brake backlog at release is the standard hours of brake work waiting at 10:00 on the release date, at the brakes' actual-over-standard ratio, in "
             f"days of crewed brake capacity. The quote table gives the 80th-percentile lead time of the routing class and backlog band (under 2, 2 to 3, 3 to 5 and "
             f"over 5 days), rounded up and never below the fixed quote; out of sample, each job is quoted from the jobs shipped before its release.</p>")
    b.append(f"<p>A quote from the 80th-percentile lead time by routing class and brake backlog at release, never below the fixed quote, is met on "
             f"{pct(to.loc[PY, 'met'])} of non-rush jobs for the year and {pct(to.loc[PR, 'met'])} in {REST} when each job is quoted from the jobs shipped before "
             f"its release, against {pct(fq.loc[PY, 'met'])} and {pct(fq.loc[PR, 'met'])} for the fixed quote; it is longer than the fixed quote on "
             f"{pct(to.loc[PY, 'longer'])} and {pct(to.loc[PR, 'longer'])} of jobs. The rule quotes the 80th percentile, so 80% is its hit rate by construction on the "
             f"jobs quoted. The table as fitted on 2023 to {YEAR} is met in sample on {pct(ti.loc[PY, 'met'])} and {pct(ti.loc[PR, 'met'])} and is longer "
             f"on {pct(ti.loc[PY, 'longer'])} and {pct(ti.loc[PR, 'longer'])}; the gap for the year is what the table's high-backlog bands learn from the 2024 to "
             f"{YEAR} event. Under 2 days of backlog the table gives {n0(q[('repeat part', 'under 2')])}, {n0(q[('new part', 'under 2')])} and "
             f"{n0(q[('outside processing', 'under 2')])} days; its lowest band for repeat parts is {n0(q[('repeat part', 'under 2')])} days against the fixed 10, so "
             f"every repeat part is quoted at least one day longer, and the median lengthening where longer is {n0(ti.loc[PR, 'median_longer_by'])} day in {REST}. "
             f"The trailing 13-week rule is met on {pct(tr.loc[PY, 'met'])} and {pct(tr.loc[PR, 'met'])} and is longer on {pct(tr.loc[PY, 'longer'])} and "
             f"{pct(tr.loc[PR, 'longer'])}. {T.see('qtable', 'rules')}</p>")

    b.append("<h3 id='f2_1'>By release quarter</h3>")
    FIRST_Q, RQ = Q.FIRST_Q, Q.RQ
    q2 = [g for g in tr.index if g.startswith(f"released {YEAR} Q2,")]
    b.append(f"<p>Jobs released in {Q.qlabel(FIRST_Q)} ({n0(fq.loc[FIRST_Q, 'jobs'])}) met the fixed quote on {pct(fq.loc[FIRST_Q, 'met'])} and the trailing rule on "
             f"{pct(tr.loc[FIRST_Q, 'met'])}; the quote table as fitted, reading the backlog on the day, quoted them {d1(ti.loc[FIRST_Q, 'mean_quote'])} days on "
             f"average and was met on {pct(ti.loc[FIRST_Q, 'met'])} ({pct(to.loc[FIRST_Q, 'met'])} out of sample). From jobs released in {YEAR} Q1 onward the quote "
             f"table is met on {pct(ti.loc[PX, 'met'])} for the year ({pct(to.loc[PX, 'met'])} out of sample), the trailing rule on {pct(tr.loc[PX, 'met'])} and the "
             f"fixed quote on {pct(fq.loc[PX, 'met'])}. The trailing rule quotes {n0(tr.loc[q2, 'mean_quote'].min())} to {n0(tr.loc[q2, 'mean_quote'].max())} days to "
             f"jobs released in {YEAR} Q2 and is met on {pct(tr.loc[q2, 'met'].min(), 0)} to {pct(tr.loc[q2, 'met'].max(), 0)} of them; the quote table carries load "
             f"through the backlog band rather than a window. For jobs released in {YEAR} Q3 and Q4 the out-of-sample quote table and the fixed quote are met at "
             f"the same rate ({pct(to.loc[RQ[3], 'met'])} against {pct(fq.loc[RQ[3], 'met'])}, {pct(to.loc[RQ[4], 'met'])} against {pct(fq.loc[RQ[4], 'met'])}); "
             f"the table's gain is on jobs released from {YEAR} Q1 to Q2, into and out of the event. {T.see('release_class')}</p>")
    b.append(titled(Q.fig_hit(), "Share of Non-rush Jobs Meeting Each Quote, by Release Quarter"))
    b.append(f"<p>Quoting from the table at order entry, by routing class and the brake backlog on the day, is met on {pct(to.loc[PR, 'met'])} of non-rush jobs in "
             f"{REST} out of sample and lengthens {pct(to.loc[PR, 'longer'])} of them. The table is refreshed quarterly from the trailing twelve quarters, all quarters "
             f"included, so the high-backlog bands keep their counts.</p>")

    # 3 ── quote turnaround and win rate
    b.append("<h2 id='f3'>3. Quote Turnaround and Win Rate</h2>")
    b.append(f"<p>Win rate is quotes won over quotes sent, with no decision counted as not won; the adjusted rate holds RFQ complexity (new part, 8 or more bends, "
             f"outside processing) constant. Quotes sent within 3 days win {pct(TURN['fast'])} against {pct(TURN['slow'])} for those taking longer, a gap of "
             f"{d1(TURN['raw_gap'] * 100)} points and {d1(TURN['adjusted_gap'] * 100)} ({d1(TURN['adjusted_low'] * 100)} to {d1(TURN['adjusted_high'] * 100)}) after "
             f"adjusting for RFQ complexity. Within the eight complexity groups the gap is {d1(STRATA['gap'].min() * 100)} to {d1(STRATA['gap'].max() * 100)} points. "
             f"The {n0(TBAND.loc[TBAND['turnaround'] == '0 to 1', 'quotes'].iloc[0])} quotes turned in 0 to 1 day hold no new parts, no parts with 8 or more bends and "
             f"no outside processing. The win rate overall is {pct(TURN['win_rate'])} on {n0(TURN['quotes'])} quotes; {pct(TURN['quotes_fast'] / TURN['quotes'])} are "
             f"sent within 3 days. {T.see('band', 'strata')}</p>")
    b.append(titled(Q.fig_turnaround(), "Win Rate by Quote Turnaround, as Quoted and Adjusted, and the Gap by Complexity Group"))

    b.append("<h3 id='f3_1'>Rush RFQs</h3>")
    b.append(f"<p>On rush RFQs the win rate falls from {pct(RUSH['win_rate'].iloc[0])} at a quoted lead time of 5 days or fewer to {pct(RUSH['win_rate'].iloc[-1])} at "
             f"12 or more, and lead time is the entered lost reason on {pct(RUSH['lost_to_lead_time'].iloc[0])} to {pct(RUSH['lost_to_lead_time'].max())} of them. The "
             f"quote table lengthens {pct(to.loc[PY, 'longer'])} of non-rush promised lead times for the year and {pct(to.loc[PR, 'longer'])} in {REST} out of sample "
             f"({pct(ti.loc[PY, 'longer'])} and {pct(ti.loc[PR, 'longer'])} as fitted). {T.see('rush')}</p>")
    b.append(titled(Q.fig_rush(), "Win Rate on Rush RFQs by Quoted Lead Time"))

    b.append("<h3 id='f3_2'>Customers, key accounts and estimators</h3>")
    CUST, FAMW, EST = Q.CUST, Q.FAMW, Q.EST
    top = CUST.iloc[0]
    hi, lo = CUST.sort_values("adjusted").iloc[-1], CUST.sort_values("adjusted").iloc[0]
    k = Q.KEY.set_index("key_account")
    b.append(f"<p>{top['customer_name']}, the customer with the most quotes ({n0(top['quotes'])}), wins {pct(top['win_rate'])} against {pct(top['expected'])} "
             f"expected from the complexity of its RFQs. Among the ten customers with the most quotes the adjusted win rate runs from {pct(lo['adjusted'])} "
             f"({lo['customer_name']}) to {pct(hi['adjusted'])} ({hi['customer_name']}). Key accounts win {pct(k.loc[True, 'win_rate'])} against "
             f"{pct(k.loc[False, 'win_rate'])} for other customers. By part family the win rate runs from {pct(FAMW['win_rate'].min())} to "
             f"{pct(FAMW['win_rate'].max())} and, adjusted for complexity, from {pct(FAMW['adjusted'].min())} to {pct(FAMW['adjusted'].max())}. "
             f"{T.see('customer', 'groups')}</p>")
    b.append(f"<p>The four estimators do not differ: median turnaround is {n0(EST['turnaround_median'].min())} days for each, {pct(EST['slow'].min())} to "
             f"{pct(EST['slow'].max())} of their quotes take over 3 days, and the adjusted win rate is {pct(EST['adjusted'].min())} to {pct(EST['adjusted'].max())}. "
             f"{T.see('estimators')}</p>")

    b.append("<h3 id='f3_3'>Lost reasons as entered</h3>")
    lost = Q.LOST.set_index("reason")["all"]
    b.append(f"<p>{n0(lost['blank'])} of {n0(lost.sum())} lost quotes carry no reason ({pct(lost['blank'] / lost.sum(), 0)}); price is entered on {n0(lost['price'])} "
             f"and lead time on {n0(lost['lead time'])}. {n0(Q.STATUS.get('no decision', 0))} quotes have no decision recorded. Complex RFQs should turn in three days "
             f"or less, and every lost quote should carry a reason. {T.see('lost')}</p>")

    # 4 ── early warning
    b.append("<h2 id='f4'>4. Early Warning of a Decline in On-time Delivery</h2>")
    W, CA, CE, DL, DEC, LT, THR, SHORT, KIT, BYQ = L.W, L.CA, L.CE, L.DL, L.DEC, L.LT, L.THR, L.SHORT, L.KIT, L.BYQ
    OTS, LASER, BACKLOG, BRAKES, OVERTIME, RELEASED, KITS, SETUP, ADHERENCE, OUTSIDE = (L.OTS, L.LASER, L.BACKLOG, L.BRAKES, L.OVERTIME, L.RELEASED, L.KITS, L.SETUP,
                                                                                    L.ADHERENCE, L.OUTSIDE)
    r2, word, wk, join_and = L.r2, L.word, L.wk, L.join_and
    e, a = CE.loc[OTS], CA.loc[OTS]
    o, la, bk, br = DL.loc[OTS], DL.loc[LASER], DL.loc[BACKLOG], DL.loc[BRAKES]
    ty, tq = THR.loc[L.PY], THR.loc[L.PR]
    sy, sr = SHORT.loc[L.PY], SHORT.loc[L.PR]
    ky, kr = KIT.loc[L.PY], KIT.loc[L.PR]
    bands = L.BANDS.pivot(index="band", columns="period", values="late_rate")
    others_e = [n for n in L.ABOVE_E if n != OTS]
    b.append(f"<p>Weekly series from {wk(W.index.min())} to {wk(W.index.max())}, {len(W)} weeks; on-time delivery by ship week. A series counts as leading when its "
             f"largest correlation at a lead of 1 to {LA.MAX_LAG} weeks exceeds the 95th percentile of the same statistic on {LA.SHUFFLES:,} shuffled and "
             f"{LA.SHUFFLES:,} time-shifted copies of the series. Of eleven weekly series tested against on-time delivery over {len(W)} weeks, "
             f"{word(len(L.ABOVE_E))} leads it in ordinary weeks and {word(len(L.ABOVE_A))} exceed chance with the 2024 year-end build included. Each series is "
             f"compared with two chance levels, and with the {word(len(DEC))} declines in on-time delivery in the period. An indicator counts as above chance only "
             f"when it exceeds both. {T.see('summary', 'defs', 'quarter')}</p>")

    b.append("<h3 id='f4_1'>Ordinary weeks and the 2024 year-end build</h3>")
    b.append(f"<p>The on-time start rate correlates {r2(e['r_best_lead'])} with on-time delivery {e['best_lead_weeks']} week later, against a 95th percentile of "
             f"{r2(e['shuffled_p95'])} on shuffled series and {r2(e['shifted_p95'])} on shifted series. "
             + ("No other series exceeds both comparisons with the event weeks excluded." if not others_e else f"{join_and(others_e)} also exceed both.")
             + f" {T.see('lags_event', 'lags_all')}</p>")
    b.append(titled(L.fig_lags(), "Correlation with On-time Delivery by Weeks of Lead"))
    b.append(f"<p>Jobs waiting at the lasers led on-time delivery by {CA.loc[LASER, 'best_lead_weeks']} weeks ({r2(CA.loc[LASER, 'r_best_lead'])}): "
             f"{n0(L.laser_before.min())} to {n0(L.laser_before.max())} jobs in the {LA.LOOKBACK} weeks before the decline of {wk(L.build['onset'])} against "
             f"{n0(L.quiet.min())} to {n0(L.quiet.max())} as the quarterly mean before it. The on-time start rate ({r2(a['r_best_lead'])} at {a['best_lead_weeks']} week), brake "
             f"backlog at release ({r2(CA.loc[BACKLOG, 'r_peak'])} at lag {CA.loc[BACKLOG, 'peak_lag_weeks']}), jobs waiting at the brakes "
             f"({r2(CA.loc[BRAKES, 'r_lag0'])} at lag 0) and overtime labor hours at the brakes ({r2(CA.loc[OVERTIME, 'r_peak'])} at lag "
             f"{CA.loc[OVERTIME, 'peak_lag_weeks']}) move with on-time delivery and describe the event under way. Brake standard hours released reaches "
             f"{r2(CA.loc[RELEASED, 'r_best_lead'])} at {CA.loc[RELEASED, 'best_lead_weeks']} weeks, the edge of the range tested.</p>")

    b.append("<h3 id='f4_2'>Declines</h3>")
    leads_o = [f"{x:.0f}" for x in LT.loc[OTS]]
    b.append(f"<p>On-time delivery declined {word(len(DEC))} times (a decline starts in the first week the trailing {LA.WINDOW}-week on-time delivery is more than 5 "
             f"points below the {LA.BASE} weeks before, at least {LA.LOOKBACK} weeks after the last) in 36 months, in the weeks of "
             f"{join_and([wk(t) for t in DEC['onset']])}; thresholds of 3, 4 and 5 "
             f"points give the same {word(L.counts[0.05])} and 6 points gives {word(L.counts[0.06])}. The on-time start rate moved before all {word(o['preceded'])}, by "
             f"{join_and(leads_o)} weeks (median {d1(o['median_lead_weeks'])}), against {d1(o['shuffled_expected'])} expected on shuffled series and "
             f"{d1(o['shifted_expected'])} on shifted (share at or above {o['shuffled_p']:.2f} and {o['shifted_p']:.2f}). Brake backlog at release, jobs waiting at "
             f"the lasers and jobs waiting at the brakes each moved before {bk['preceded']} of "
             f"{bk['declines']} against {d1(min(bk['shuffled_expected'], la['shuffled_expected'], br['shuffled_expected']))} to "
             f"{d1(max(bk['shifted_expected'], la['shifted_expected'], br['shifted_expected']))} expected, which is not distinguishable from chance. With four "
             f"declines the count separates the on-time start rate from the rest and nothing else. The on-time start rate gave {o['signal_episodes']} signal "
             f"episodes and {o['episodes_followed_by_decline']} were followed by a decline within {LA.LOOKBACK} weeks; brake backlog at release "
             f"{bk['signal_episodes']} and {bk['episodes_followed_by_decline']}; jobs waiting at the lasers {la['signal_episodes']} and "
             f"{la['episodes_followed_by_decline']}. {T.see('declines', 'leads', 'lead_by')}</p>")
    b.append(titled(L.fig_declines(), "On-time Delivery, the On-time Start Rate and Jobs Waiting at the Lasers by Week"))

    b.append("<h3 id='f4_3'>Job-level flags</h3>")
    b.append(f"<p>Jobs released with more than {LA.BACKLOG_THRESHOLD:.0f} days of brake work waiting are {pct(ty['share_of_late_jobs_above'])} of the late jobs "
             f"released in {YEAR} against {pct(ty['share_of_all_jobs_above'])} of all jobs, and {pct(tq['share_of_late_jobs_above'])} against "
             f"{pct(tq['share_of_all_jobs_above'])} in {REST}. The late rate is {pct(bands[L.PY].iloc[:3].min())} to {pct(bands[L.PY].iloc[:3].max())} below 3 days and "
             f"{pct(bands[L.PY].iloc[3])}, {pct(bands[L.PY].iloc[4])}, {pct(bands[L.PY].iloc[5])} and {pct(bands[L.PY].iloc[6])} in the bands above. Every job released in "
             f"the first quarter was above the threshold; in {REST} it marks {pct(tq['share_of_all_jobs_above'])} of jobs. {T.see('bands', 'threshold')}</p>")
    b.append(titled(L.fig_backlog(), "Late Rate by Brake Backlog at Release"))
    b.append(f"<p>Jobs released late are {pct(sr['share_of_jobs'])} of jobs and {pct(sr['share_of_late_jobs'])} of late jobs released in {REST} (late rate "
             f"{pct(sr['late_rate_inside'])} against {pct(sr['late_rate_other'])}), and {pct(sy['share_of_jobs'])} and {pct(sy['share_of_late_jobs'])} for the year. "
             f"The weekly share is flat at {pct(BYQ['promised_inside_standard_share'].min(), 0)} to {pct(BYQ['promised_inside_standard_share'].max(), 0)} by quarter "
             f"and does not lead as a series; the flag identifies the jobs. {T.see('late')}</p>")
    b.append(f"<p>{pct(ky['share_of_days_short_kit'])} of material-caused lost days in {YEAR} are on jobs with a short kit ({pct(kr['share_of_days_short_kit'])} in "
             f"{REST}) against a short rate of {pct(ky['short_rate_all_kit_checks'])} on all kit checks (a recorded kit shortage is one trigger of the flow report's "
             f"material rule, so part of this share is the rule's own definition). As a weekly series kit completeness does not lead "
             f"on-time delivery in ordinary weeks ({r2(CE.loc[KITS, 'r_best_lead'])}). {T.see('kit')}</p>")

    b.append("<h3 id='f4_4'>The weekly review set</h3>")
    b.append(f"<p>Setup efficiency at the brakes ({r2(CE.loc[SETUP, 'r_best_lead'])} in ordinary weeks, {r2(CA.loc[SETUP, 'r_best_lead'])} in all weeks) and "
             f"outside-processing receipts on time ({r2(CE.loc[OUTSIDE, 'r_best_lead'])}, {r2(CA.loc[OUTSIDE, 'r_best_lead'])}) do not exceed chance. Schedule "
             f"adherence has the opposite sign ({r2(CA.loc[ADHERENCE, 'r_lag0'])} at lag 0 in all weeks): adherence is higher when on-time delivery is lower. "
             f"Overtime labor hours at the brakes move with on-time delivery ({r2(CA.loc[OVERTIME, 'r_lag0'])} at lag 0) and not ahead of it "
             f"({r2(CE.loc[OVERTIME, 'r_best_lead'])} in ordinary weeks). {T.see('overtime')}</p>")
    b.append(f"<p>Two weekly indicators and three job-level flags carry the lead found. {L.PAIR_TEXT} {T.see('review')}</p>")
    b.append(f"<p>Production control reviews the on-time start rate and jobs waiting at the lasers weekly against the triggers in Table {T.number('review')}, and flags "
             f"at release every job with more than {LA.BACKLOG_THRESHOLD:.0f} days of brake backlog and every job released late, and a short kit at the kit check. "
             f"Setup efficiency, schedule adherence, outside-processing receipts and overtime leave the leading set; they remain measures of their own work "
             f"centers.</p>")

    b.append("<h2 id='appendix'>Appendix</h2>")
    b.append(T.appendix())
    toc = [("f1", "1. The Quote Against Lead Time"), ("f2", "2. A Quote Table From Load"), ("f3", "3. Quote Turnaround and Win Rate"),
           ("f4", "4. Early Warning of a Decline in On-time Delivery")]
    print(f"wrote {page('quoting', chr(10).join(b), toc)}: 4 sections, {len(T.order)} appendix tables")
    return T.order


def main():
    build()


if __name__ == "__main__":
    main()
