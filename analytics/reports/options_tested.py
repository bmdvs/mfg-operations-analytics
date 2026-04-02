"""Options tested: the report.

Usage: python -m analytics.reports.options_tested
"""
from analytics.release_control import sections as R
from analytics.reports.layout import Tables, link, page, titled
from analytics.technology_roi import analysis as KA
from analytics.technology_roi import sections as K
from analytics.style.style import pct

YEAR, REST = R.YEAR, R.REST
WORD = {5: "five", 7: "seven", 10: "ten"}
LATE = "released with fewer working days to the promised date than the standard quoted lead time for the routing class"


def build():
    T = Tables()
    S0, S8, CHRONIC, NOCAP, SINGLE, PY, PR = R.S0, R.S8, R.CHRONIC, R.NOCAP, R.SINGLE, R.PY, R.PR
    v, pts, by, spp, d1, n0 = R.v, R.pts, R.by, R.spp, R.d1, R.n0
    allsc = [S0] + SINGLE + [CHRONIC, NOCAP] + R.CAPCOMBO
    T.add("validation", f"The model under current practice against measured {YEAR}, with tolerances", R.t_validation())
    T.add("quarters", "The model against measured, by quarter shipped", R.t_quarters())
    T.add("hold", "Release hold under the WIP cap and constraint-paced release", R.t_hold())
    T.add("full_y", f"Scenario results, {YEAR}", R.t_full(PY, allsc))
    T.add("diff_y", f"Difference from current practice, {YEAR}", R.t_diff(PY, allsc[1:]))
    T.add("full_r", f"Scenario results, {YEAR} {REST}", R.t_full(PR, allsc))
    T.add("diff_r", f"Difference from current practice, {YEAR} {REST}", R.t_diff(PR, allsc[1:]))
    T.add("rules", "On-time delivery at the two promise rules", R.t_promise())
    T.add("packages", f"The packages against current practice and against setup reduction alone, {YEAR} and {REST}", R.t_packages())
    E, EP, S, SP, M, F, RH, O = K.E, K.EP, K.S, K.SP, K.M, K.F, K.R, K.O
    ATC, TOWER, CELL, PACKAGE, ATC_ALL, N_ATC, N_TOWER, N_CELL, N_ALL = K.ATC, K.TOWER, K.CELL, K.PACKAGE, K.ATC_ALL, K.N_ATC, K.N_TOWER, K.N_CELL, K.N_ALL
    kv, kpts, byp, usd, k, kn0, kd1, breakeven, sg = K.v, K.pts, K.byp, K.usd, K.k, K.n0, K.d1, K.breakeven, K.sg
    options = [n for n in K.NAMES if n != K.S0]
    T.add("measured", f"Measured inputs for {YEAR}, from the marts", K.t_measured())
    T.add("assumptions", "Assumptions", K.t_assumptions())
    T.add("effects", f"Each option against current practice, {YEAR} and {REST}, with 95% intervals", K.t_effects_body())
    for period, pl, tag in (("year", f"{YEAR}", "y"), (REST, f"{YEAR} {REST}", "r")):
        T.add(f"k_levels_{tag}", f"Capital options: scenario results, {pl}", K.t_levels(period))
        T.add(f"k_diff_{tag}", f"Capital options: difference from current practice, {pl}", K.t_effects(options, period))
        T.add(f"k_pkg_{tag}", f"On top of the no-capital package: difference from the package, {pl}", K.t_effects(K.ON_PKG + [N_ALL], period, SP))
    T.add("november", "The laser tower in the weeks of November 11 to December 1, 2024", K.t_november())
    T.add("money", f"Payback and NPV against current practice at {F['discount_rate']:.0%} over {K.HORIZON} years, before tax: overtime and labor alone, and with the "
                   f"throughput value of released constraint hours", K.t_money([(n, E[n]) for n in K.BASE + [PACKAGE]]))
    T.add("money_pkg", "Each option added to the no-capital package: its own cost against what it adds beyond the package",
          K.t_money([(n, EP[n]) for n in K.ON_PKG], summary=SP))
    T.add("hours", "Hours behind the money lines, per year, against current practice", K.t_hours(options))
    T.add("money_all", "Payback and NPV against current practice, every scenario", K.t_money([(n, E[n]) for n in options], body=False))
    T.add("money_pkg_all", "Each option added to the no-capital package, with the sensitivity", K.t_money([(n, EP[n]) for n in K.ON_PKG + [N_ALL]], body=False, summary=SP))

    cap = ["S1 WIP cap 240", "S1 WIP cap 210", "S1 WIP cap 180"]
    paced, edd, cr, spt = SINGLE[3], SINGLE[4], SINGLE[5], SINGLE[6]
    s4, s5, s6, s7 = SINGLE[7], SINGLE[8], SINGLE[9], SINGLE[10]
    Q1 = R.Q1
    b = []

    # 1 ── the shop model
    b.append("<h2 id='f1'>1. The Shop Model</h2>")
    b.append(f"<p>The options in this report are run on a model of the shop that replays the jobs released from January 2024 to December {YEAR} with their routings, "
             f"standards, promised dates, rush flags, shift calendars, recorded downtime and the powder color schedule; setup, run, material, move, hold, outside "
             f"processing and ship times are drawn from their {YEAR} distributions. Each scenario runs {R.REPS} replications; differences from current practice are "
             f"paired by replication and reported with 95% intervals. Lead time is in working days, scheduled Saturdays counted.</p>")
    b.append(f"<p>The model of current practice is within tolerance on {R.V_IN} of {R.V_TOL} measures. It replays the 2024 year-end build and clears it sooner than the "
             f"shop did: first-quarter on-time delivery is {pct(Q1['otd_s'])} in the model against {pct(Q1['otd_m'])} measured, and every other quarter is within "
             f"{R.OTHER_GAP * 100:.1f} points. Effects on the first-quarter event are therefore lower bounds. The model's brakes run "
             f"{(v(PY, S0, 'brake_utilization') - R.measured(1)['brake_utilization']) * 100:.0f} points hotter than measured ({v(PY, S0, 'brake_utilization'):.3f} against "
             f"{R.measured(1)['brake_utilization']:.3f}), so the effects of capacity levers in the ordinary quarters are slightly overstated. "
             f"{T.see('validation', 'quarters')}</p>")

    # 2 ── levers one at a time
    b.append("<h2 id='f2'>2. Levers Tested One at a Time</h2>")
    b.append("<h3 id='f2_1'>Release control and dispatch rules</h3>")
    b.append(f"<p>A WIP cap (non-rush jobs held in release order until the floor is below the cap; lead time still runs from the release date) at 240, 210 and 180 "
             f"jobs lowers on-time delivery by {pts(PR, cap[0])}, {pts(PR, cap[1])} and {pts(PR, cap[2])} points in {REST} "
             f"({pts(PY, cap[0])}, {pts(PY, cap[1])} and {pts(PY, cap[2])} for the year) and lengthens the 90th-percentile lead time by "
             f"{d1(v(PR, cap[0], 'lead_time_p90', 'diff'))} to {d1(v(PR, cap[2], 'lead_time_p90', 'diff'))} days; jobs wait {d1(R.hold(cap[0]))} to "
             f"{d1(R.hold(cap[2]))} days at the gate. Constraint-paced release (jobs with brake work held while the work waiting at the brakes exceeds 3 days of crewed "
             f"brake capacity) is {pts(PR, paced)} points worse in {REST}. In an ordinary quarter the floor already carries less WIP than the quoted lead times allow "
             f"({link('lead')}); a cap delays work the floor could have started. {T.see('hold')}</p>")
    b.append(titled(R.fig_cap(), "On-time Delivery Against Release Hold Under a WIP Cap"))
    b.append(f"<p>Earliest due date makes no difference for the year, {spp(PY.loc[(edd, 'on_time_delivery')])}, is {pts(PR, edd)} points worse in {REST} and "
             f"ships {n0(-v(PY, edd, 'jobs_shipped', 'diff'))} fewer jobs. Critical ratio is {pts(PR, cr)} to {pts(PY, cr)} points worse. Shortest processing time at "
             f"the brakes shortens the median and is {pts(PY, spt)} to {pts(PR, spt)} points worse on time, with {n0(-v(PY, spt, 'jobs_shipped', 'diff'))} fewer jobs "
             f"shipped in the year. The dispatch list with rush and hot-list precedence is as good as any rule tested. Release should not be capped, and the dispatch "
             f"list stays. {T.see('full_y', 'diff_y', 'full_r', 'diff_r')}</p>")

    b.append("<h3 id='f2_2'>Capacity at the constraint</h3>")
    b.append(f"<p>The setup reduction (the top 12 part-operations at standard and the assignment and handover hours of {link('capacity', 'the capacity report')} taken "
             f"off the other brake setups in proportion) raises on-time delivery by {by(PY.loc[(S8, 'on_time_delivery')])} for the year, shortens the 90th percentile "
             f"by {d1(-v(PY, S8, 'lead_time_p90', 'diff'))} days, lowers WIP by {n0(-v(PY, S8, 'wip_mean', 'diff'))} jobs and cuts Saturday shifts from "
             f"{n0(v(PY, S0, 'saturday_shifts'))} to {n0(v(PY, S8, 'saturday_shifts'))} and extended hours from {n0(v(PY, S0, 'extended_hours'))} to "
             f"{n0(v(PY, S8, 'extended_hours'))}. In {REST} it shortens the 90th percentile by {d1(-v(PR, S8, 'lead_time_p90', 'diff'))} days and leaves on-time delivery "
             f"unchanged, {spp(PR.loc[(S8, 'on_time_delivery')])}: lateness in those quarters is set by jobs released late ({LATE}; the flow report).</p>")
    b.append(titled(R.fig_effects(), "Change in On-time Delivery and 90th-percentile Lead Time by Scenario"))
    y5 = PY.loc[(s5, "on_time_delivery")]
    b.append(f"<p>A second shift on the robotic weld cell raises on-time delivery by {by(PR.loc[(s5, 'on_time_delivery')])} in {REST} and shortens the 90th "
             f"percentile there by {d1(-v(PR, s5, 'lead_time_p90', 'diff'))} days; for the year the effect is {spp(y5)}"
             + (", not distinguishable from zero." if y5["diff_low"] <= 0 <= y5["diff_high"] else ".") + "</p>")
    b.append(f"<p>A planned Saturday brake shift every week from November through February raises on-time delivery by {by(PY.loc[(s7, 'on_time_delivery')])} "
             f"for the year and shortens the 90th percentile by {d1(-v(PY, s7, 'lead_time_p90', 'diff'))} days, for "
             f"{d1(v(PY, s7, 'saturday_shifts') - v(PY, S0, 'saturday_shifts'))} more Saturday shifts in {YEAR} than the queue-triggered practice produced. "
             f"This is a lower bound.</p>")
    b.append(f"<p>Light work ahead of heavy on B1 and B2 (after precision, when the B3 to B5 queue exceeds 2 days), {spp(PY.loc[(s4, 'on_time_delivery')])} for the "
             f"year, and a third weekly color day for black, {spp(PY.loc[(s6, 'on_time_delivery')])}, do not move on-time delivery or the 90th percentile beyond their "
             f"intervals.</p>")

    b.append("<h3 id='f2_3'>The promise rules</h3>")
    b.append(f"<p>At the quote table of {link('quoting')} (routing class and brake backlog at release, never below the fixed quote) the current floor delivers "
             f"{pct(v(PY, S0, 'on_time_delivery_quote_table'))} on time for the year and {pct(v(PR, S0, 'on_time_delivery_quote_table'))} in {REST}, with "
             f"{pct(v(PY, S0, 'promises_longer_quote_table'), 0)} and {pct(v(PR, S0, 'promises_longer_quote_table'), 0)} of non-rush promised lead times longer than "
             f"the fixed quote; at the 80th percentile of the routing class over the trailing 13 weeks, {pct(v(PY, S0, 'on_time_delivery_load_aware'))} and "
             f"{pct(v(PR, S0, 'on_time_delivery_load_aware'))}, with {pct(v(PY, S0, 'promises_longer_than_fixed_quote'), 0)} and "
             f"{pct(v(PR, S0, 'promises_longer_than_fixed_quote'), 0)} longer. The promise rules do not change the floor; the quote table is the rule of the quoting "
             f"report and the trailing rule the one first modeled. {T.see('rules')}</p>")

    # 3 ── the operating package
    b.append("<h2 id='f3'>3. The Operating Package</h2>")
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
             f"first-quarter backlog ships earlier. At the quote table the same floor delivers "
             f"{pct(v(PY, NOCAP, 'on_time_delivery_quote_table'))} on time for the year and {pct(v(PR, NOCAP, 'on_time_delivery_quote_table'))} in {REST} "
             f"({pct(v(PY, NOCAP, 'on_time_delivery_load_aware'))} and {pct(v(PR, NOCAP, 'on_time_delivery_load_aware'))} at the trailing 13-week rule). "
             f"{T.see('packages')}</p>")
    epk = E[PACKAGE]
    b.append(f"<p>The setup program, a second shift on the robotic weld cell and a planned Saturday brake shift every week from November through February are the "
             f"operating package: on-time delivery rises by {by(PY.loc[(NOCAP, 'on_time_delivery')])} for the year and {by(PR.loc[(NOCAP, 'on_time_delivery')])} in "
             f"{REST}, with the 90th-percentile lead time {d1(-v(PY, NOCAP, 'lead_time_p90', 'diff'))} and {d1(-v(PR, NOCAP, 'lead_time_p90', 'diff'))} days shorter, "
             f"for {usd(epk['one_time'])}. It goes in first; the quoted lead times are restated from {link('quoting')}.</p>")

    # 4 ── capital options
    b.append("<h2 id='f4'>4. Capital Options</h2>")
    b.append("<h3 id='f4_1'>Inputs and assumptions</h3>")
    ea, et, ec = E[ATC], E[TOWER], E[CELL]
    b.append(f"<p>The brakes ran at {M['brake_utilization']:.3f} in {YEAR} with {kd1(M['brake_setup_hours_per_week'])} setup hours a week, {pct(M['b3_share_of_setup_hours'])} "
             f"of them on B3; the lasers ran at {M['laser_utilization']:.3f} and the robotic weld cell at {M['robotic_weld_utilization']:.3f}. Jobs shipped in {YEAR} "
             f"carried {usd(M['revenue'])} of revenue over {kn0(M['brake_hours'])} crewed brake hours, {usd(M['revenue_per_brake_hour'])} a brake hour. The tool "
             f"changer multiplies the setups on B3 by "
             f"{1 - O['press_brake_atc']['tool_change_share_of_setup'] * O['press_brake_atc']['tool_change_reduction']:.4f}; the laser tower adds 6 unattended hours "
             f"after second shift on L2; the robotic bending cell is a sixth brake on two shifts at "
             f"{O['robotic_bending_cell']['added_crewed_hours_per_week'] / 80:.3f} availability that runs light, repeat parts in lots of 25 or more. "
             f"{T.see('measured', 'assumptions')}</p>")

    b.append("<h3 id='f4_2'>What each option does on the floor</h3>")
    b.append(f"<p>For the year the robotic bending cell raises on-time delivery by {kpts(CELL)} points, the tool changer on B3 by {kpts(ATC)}, the laser tower by "
             f"{kpts(TOWER)} and the no-capital package by {kpts(PACKAGE)}. In {REST} every capital option adds under a point ({kpts(ATC, REST)}, {kpts(TOWER, REST)} and "
             f"{kpts(CELL, REST)}) against {kpts(PACKAGE, REST)} for the package. {T.see('effects', 'k_levels_y', 'k_diff_y', 'k_levels_r', 'k_diff_r')}</p>")
    b.append(titled(K.fig_effects(), "Change in On-time Delivery and 90th-percentile Lead Time by Option"))
    b.append(f"<p>A press brake with automatic tool changing in place of B3 raises on-time delivery by {byp(S.loc[(ATC, 'year', 'on_time_delivery')])} for "
             f"the year and shortens the 90th percentile by {kd1(-kv(ATC, 'lead_time_p90', col='diff'))} days; it saves {kd1(ea['setup_hours_saved'] / KA.WEEKS)} setup "
             f"hours a week, against {kd1(epk['setup_hours_saved'] / KA.WEEKS)} for the no-capital package. Covering every brake setup at the same price would match "
             f"the robotic cell ({sg(kv(ATC_ALL, 'on_time_delivery', col='diff') * 100)} points, {kd1(E[ATC_ALL]['setup_hours_saved'] / KA.WEEKS)} setup hours a week); "
             f"one machine covers B3's {pct(kv(K.S0, 'b3_setup_hours') / kv(K.S0, 'brake_setup_hours'), 0)} of setup hours.</p>")
    b.append(f"<p>The cell raises on-time delivery by {byp(S.loc[(CELL, 'year', 'on_time_delivery')])} for the year, shortens the 90th percentile by "
             f"{kd1(-kv(CELL, 'lead_time_p90', col='diff'))} days and removes {kd1(-kv(CELL, 'saturday_shifts', col='diff'))} of {kd1(kv(K.S0, 'saturday_shifts'))} Saturday "
             f"shifts. The parts it can run are {pct(M['cell_share_of_brake_standard_hours'])} of brake standard hours; it works {kn0(ec['cell_hours'] / KA.WEEKS)} hours "
             f"a week and takes {kn0(ec['manual_brake_hours_displaced'] / KA.WEEKS)} hours a week off the manual brakes, whose setup hours rise by "
             f"{kn0(-ec['setup_hours_saved'])} a year. On top of the package it reaches {pct(kv(N_CELL, 'on_time_delivery'))} on time for the year and "
             f"{pct(kv(N_CELL, 'on_time_delivery', REST))} in {REST}, with brake utilization at {kv(N_CELL, 'brake_utilization'):.2f}.</p>")
    b.append(f"<p>The tower clears the laser queue and changes nothing downstream: in the three weeks from November 11, 2024 the jobs waiting at the lasers fall from "
             f"{kn0(kv(K.S0, 'laser_queue_nov_2024'))} to {kn0(kv(TOWER, 'laser_queue_nov_2024'))} a day and the jobs released in those weeks ship "
             f"{pct(kv(TOWER, 'on_time_released_nov_2024'))} on time against {pct(kv(K.S0, 'on_time_released_nov_2024'))}; the package alone lifts those jobs to "
             f"{pct(kv(PACKAGE, 'on_time_released_nov_2024'))}. For the year the tower's effect is {byp(S.loc[(TOWER, 'year', 'on_time_delivery')])} and in "
             f"{REST} {byp(S.loc[(TOWER, REST, 'on_time_delivery')])}. {T.see('november')}</p>")
    b.append(titled(K.fig_laser(), "Jobs Waiting at the Lasers by Day, November and December 2024"))

    b.append("<h3 id='f4_3'>Payback and NPV</h3>")
    b.append(f"<p>Payback is the one-time cost over the net annual benefit; NPV discounts {WORD[K.HORIZON]} years of that benefit at {F['discount_rate']:.0%}, before "
             f"tax and with no residual value. Overtime and labor are valued at the loaded rate and premium the shop supplied; the throughput line assumes "
             f"{'half' if RH['utilization_of_released_hours'] == 0.5 else format(RH['utilization_of_released_hours'], '.0%') + ' of'} the released brake hours are "
             f"sold at a {RH['contribution_margin_share']:.0%} margin, and only brake hours carry throughput value. On overtime and labor alone no option pays back "
             f"within the {K.HORIZON}-year horizon, and the no-capital package is net negative ({k(-epk['net_without_throughput'])} a year, the weld cell's second "
             f"shift). If half the released brake hours are sold at the stated margin the robotic "
             f"cell pays back in {kd1(ec['payback_with_throughput'])} years, the tool changer on B3 in {kd1(ea['payback_with_throughput'])}, the tower not at all, and "
             f"the package in {kd1(epk['payback_with_throughput'])}. NPV reaches zero when {breakeven(ec, False)} of the cell's released brake hours are sold "
             f"({kn0(ec['breakeven_hours'])} hours a year), {breakeven(ea, False)} of the tool changer's ({kn0(ea['breakeven_hours'])}) and {breakeven(epk, False)} of the "
             f"package's ({kn0(epk['breakeven_hours'])}); the tower releases no constraint hours. {T.see('money', 'hours', 'money_all')}</p>")
    b.append(titled(K.fig_npv(), "NPV Against the Share of Released Brake Hours Sold"))
    b.append(f"<p>On top of the no-capital package the robotic cell adds {kpts(N_CELL, s=SP)} points for the year, the tool changer on B3 {kpts(N_ATC, s=SP)} and the "
             f"laser tower {kpts(N_TOWER, s=SP)}. At its own cost against what it adds, the cell reaches an NPV of zero at {breakeven(EP[N_CELL])} of released brake "
             f"hours sold and the tool changer at {breakeven(EP[N_ATC])}. {T.see('money_pkg', 'k_pkg_y', 'k_pkg_r', 'money_pkg_all')}</p>")
    b.append(f"<p>The no-capital package delivers more on-time improvement than the tool changer on B3 ({kpts(PACKAGE)} against {kpts(ATC)} points) and "
             f"{pct(kv(PACKAGE, 'on_time_delivery', col='diff') / kv(CELL, 'on_time_delivery', col='diff'), 0)} of the robotic cell's ({kpts(CELL)}), for "
             f"{usd(epk['one_time'])} against {usd(ea['one_time'])} and {usd(ec['one_time'])}.</p>")
    b.append(f"<p>The robotic bending cell is the capital option with the largest effect and the lowest break-even; it is taken up when the shop can show that "
             f"{kn0(EP[N_CELL]['breakeven_hours'])} of the released brake hours a year will be sold ({kn0(ec['breakeven_hours'])} without the package). The tool "
             f"changer on B3 is justified only if {breakeven(ea, False)} of its released hours ({kn0(ea['breakeven_hours'])} a year) will be sold. The laser tower "
             f"clears a queue that is not the constraint and is not bought.</p>")

    b.append("<h2 id='appendix'>Appendix</h2>")
    b.append(T.appendix())
    toc = [("f1", "1. The Shop Model"), ("f2", "2. Levers Tested One at a Time"), ("f3", "3. The Operating Package"), ("f4", "4. Capital Options")]
    print(f"wrote {page('options', chr(10).join(b), toc)}: 4 sections, {len(T.order)} appendix tables")
    return T.order


def main():
    build()


if __name__ == "__main__":
    main()
