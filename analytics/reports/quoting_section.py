"""Quoting and early warning: the fourth section of the flow report, with its appendix tables."""
import numpy as np
from matplotlib.patches import Patch
import pandas as pd

from analytics.leading_indicators import analysis as LA
from analytics.leading_indicators import sections as L
from analytics.quoting import analysis as A
from analytics.quoting import rules as R
from analytics.quoting import sections as Q
from analytics.reports.layout import RT, Tables, block, chart, join_and, titled
from analytics.style.style import AMBER, BRAND_BLUE, GREY, LIGHT_BLUE, fig, pct, save_conformed as save, table

YEAR = R.YEAR
TITLE = "Quoting and Early Warning"
CURRENT, REC = "Current practice", "Recommended rule"
CLS = {"repeat part": "Repeat part", "new part": "New part", "outside processing": "Outside processing"}
SHOWN = {R.RECOMMENDED: f"{R.RECOMMENDED} (recommended)"}
T0 = R.THRESHOLD
# the recommended rule's columns: the class standard below the switch, then the table's bands from the one the switch falls in
SWITCH_BAND = A.BAND_LABELS[int(np.searchsorted(A.BANDS[1:-1], T0, side="right"))]
RULE_BANDS = A.BAND_LABELS[A.BAND_LABELS.index(SWITCH_BAND):]
n0 = lambda x: f"{x:,.0f}"
d1 = lambda x: f"{x:.1f}"
day = lambda t: f"{t:%B} {t.day}"
quarter = lambda s: f"{s[:4]} Q{s[-1]}"
money = lambda x: f"${x / 1e6:.2f}M"
name = lambda r: CURRENT if r is None else SHOWN.get(r, r)


def band_head(b):
    lo = b.split(" ")[0] if b[0].isdigit() else None
    if b == SWITCH_BAND and lo is not None and float(lo) < T0:
        return f"{T0:g} to {b.split(' to ')[1]}"
    return b.capitalize()


# ── figures ─────────────────────────────────────────────────────────────────
def fig_weekly(g):
    f, axes = fig(h=5.4, nrows=2, sharex=True, gridspec_kw=dict(height_ratios=[1, 1.35]))
    for ax in axes:
        for w in g.index[g["adder"]]:
            ax.axvspan(w - pd.Timedelta(days=3.5), w + pd.Timedelta(days=3.5), color=GREY, alpha=0.18, lw=0)
    ax = axes[0]
    ax.plot(g.index, g["backlog"], color=BRAND_BLUE, lw=1.6)
    ax.axhline(T0, color=AMBER, lw=1, ls="--")
    ax.annotate(f"{T0:g} days", (g.index[2], T0), textcoords="offset points", xytext=(0, 4), fontsize=8, color=AMBER)
    ax.set_ylabel("Brake backlog at release (days)")
    ax.set_ylim(0, float(g["backlog"].max()) * 1.12)
    ax = axes[1]
    ax.plot(g.index, g["current"], color=GREY, lw=1.6, label=CURRENT)
    ax.plot(g.index, g[R.FIRST], color=AMBER, lw=1.6, label=R.FIRST)
    ax.plot(g.index, g[R.RECOMMENDED], color=BRAND_BLUE, lw=1.9, label=REC)
    ax.set_ylabel("Mean quoted lead time,\nnon-rush jobs (days)")
    ax.set_xlabel("Release week")
    hs, ls = ax.get_legend_handles_labels()
    ax.legend(hs + [Patch(color=GREY, alpha=0.18, lw=0)], ls + ["Weeks the shop's adder was on quotes"], frameon=False, fontsize=9, ncol=4)
    f.tight_layout()
    return save(f, "quote_and_backlog_by_week", "")


def fig_quarters(by):
    f, ax = fig(h=3.3)
    x = np.arange(len(R.QUARTERS))
    for off, r, color in ((-0.27, None, GREY), (0, R.FIRST, AMBER), (0.27, R.RECOMMENDED, BRAND_BLUE)):
        h = [by[(qn, r)]["on_time"] * 100 for qn in R.QUARTERS]
        ax.bar(x + off, h, 0.27, color=color, label=REC if r == R.RECOMMENDED else name(r))
        for xi, hi in zip(x + off, h):
            ax.annotate(f"{hi:.0f}", (xi, hi), textcoords="offset points", xytext=(0, 2), ha="center", fontsize=7)
    ax.set_xticks(x)
    ax.set_xticklabels([quarter(qn) for qn in R.QUARTERS], fontsize=9)
    ax.set_ylim(50, 100)
    ax.set_xlabel("Release quarter")
    ax.set_ylabel("On-time delivery, all jobs (%)")
    ax.legend(frameon=False, fontsize=9, ncol=3)
    f.tight_layout()
    return save(f, "quote_rules_on_time_by_release_quarter", "")


CHARTED = [R.FIRST, R.switch(1.5), R.switch(2.0), R.switch(2.5), R.FILLED, R.RECOMMENDED]


def fig_cost(costs):
    f, ax = fig(h=3.4, grid="x")
    y = np.arange(len(CHARTED))[::-1]
    removed, forgone = [costs[r]["removed"] for r in CHARTED], [costs[r]["forgone"] for r in CHARTED]
    ax.barh(y + 0.19, removed, 0.38, color=BRAND_BLUE, label="Late jobs removed")
    ax.barh(y - 0.19, forgone, 0.38, color=LIGHT_BLUE, label="Orders forgone")
    for yi, a, b in zip(y, removed, forgone):
        ax.annotate(n0(a), (a, yi + 0.19), textcoords="offset points", xytext=(3, 0), va="center", fontsize=8)
        ax.annotate(n0(b), (b, yi - 0.19), textcoords="offset points", xytext=(3, 0), va="center", fontsize=8)
    ax.set_yticks(y)
    ax.set_yticklabels([REC if r == R.RECOMMENDED else r for r in CHARTED], fontsize=9)
    ax.set_xlim(0, max(forgone) * 1.1)
    ax.set_xlabel(f"Jobs shipped in {YEAR}")
    ax.legend(frameon=False, fontsize=9, ncol=2)
    f.tight_layout()
    return save(f, "quote_rules_late_jobs_and_orders", "")


# ── tables ──────────────────────────────────────────────────────────────────
def t_grid(g):
    rows = [[CLS[r["routing_class"]], r["standard"]] + [r[b] for b in RULE_BANDS] for _, r in g.iterrows()]
    return table(pd.DataFrame(rows, columns=["Routing class", f"Under {T0:g} days (the class standard)"] + [f"{band_head(b)} days" for b in RULE_BANDS]))


def t_grid_full(g):
    rows = []
    for _, r in g.iterrows():
        j = R.J[R.J["routing_class"] == r["routing_class"]]
        for b in A.BAND_LABELS:
            x = j[j["band"] == b]["wip_days"]
            rows.append([CLS[r["routing_class"]], b, r["standard"], n0(len(x)), n0(np.ceil(x.quantile(A.PCTL))) if len(x) else "", r[b]])
    return table(pd.DataFrame(rows, columns=["Routing class", "Brake backlog at release (days)", "Class standard", "Jobs", "80th-percentile lead time", "Quote"]))


def t_history(months):
    h = R.history(months)
    rows = [[f"{r['month']:%B} {r['month'].day}, {r['month'].year}", CLS[r["routing_class"]]] + [n0(r[b]) for b in A.BAND_LABELS] for _, r in h.iterrows()]
    return table(pd.DataFrame(rows, columns=["Jobs shipped before", "Routing class"] + [f"{b.capitalize()} days" for b in A.BAND_LABELS]))


def t_outcomes(where):
    rows = []
    for label, sel in where:
        for r in [None] + R.EVERY:
            o = R.outcome(r, sel)
            share = lambda k: "" if o[k] != o[k] else pct(o[k], 0)
            rows.append([label, name(r), n0(o["non_rush"]), pct(o["met"]), share("longer"), "" if o["added"] != o["added"] else d1(o["added"]), share("shorter"),
                         pct(o["on_time"]), n0(o["late"]), n0(o["days_late"])])
    return table(pd.DataFrame(rows, columns=["Jobs", "Quote rule", "Non-rush jobs", "Quote met", "Quoted longer than current practice", "Mean days added where longer",
                                             "Quoted shorter", "On time, all jobs", "Late jobs", "Days late"]))


BY_QUARTER = [None, R.FIRST, R.switch(T0), R.FILLED, R.RECOMMENDED]


def t_release(by):
    rows = [[quarter(qn), n0(by[(qn, None)]["non_rush"])] + [x for r in BY_QUARTER for x in (pct(by[(qn, r)]["on_time"]), n0(by[(qn, r)]["late"]))] for qn in R.QUARTERS]
    head = ("<tr><th rowspan='2'>Released</th><th rowspan='2'>Non-rush jobs</th>" + "".join(f"<th colspan='2' style='text-align:center'>{name(r)}</th>" for r in BY_QUARTER)
            + "</tr><tr>" + "<th>On time</th><th>Late jobs</th>" * len(BY_QUARTER) + "</tr>")
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table class="data"><thead>{head}</thead><tbody>{body}</tbody></table>'


def t_cost():
    rows = []
    for label, sel, times in ((f"Jobs shipped in {YEAR}", R.SHIPPED, 1.0), (f"An ordinary year (jobs released in {YEAR} Q3 and Q4, twice)", R.ORDINARY, 2.0)):
        for r in R.EVERY:
            c = R.cost(r, sel, times)
            rows.append([label, name(r), f"{c['net']:+.2f}", f"{c['forgone']:,.0f} ({c['forgone_low']:,.0f} to {c['forgone_high']:,.0f})", f"${c['revenue']:,.0f}",
                         n0(c["removed"]), "" if c["forgone"] <= 0.5 else f"{c['removed'] / c['forgone']:.2f}"])
    return table(pd.DataFrame(rows, columns=["Jobs", "Quote rule", "Mean days added to the quote, net", "Orders forgone (95% interval of the fall)", "Revenue forgone",
                                             "Late jobs removed", "Late jobs removed per order forgone"]))


def t_above():
    g = R.QN.groupby("above")["won"].agg(["size", "sum", "mean"])
    rows = [[n0(k), n0(r["size"]), n0(r["sum"]), pct(r["mean"])] for k, r in g.iterrows()]
    return table(pd.DataFrame(rows, columns=["Days quoted above the class standard", "Non-rush quotes", "Won", "Win rate"]))


# ── the section ─────────────────────────────────────────────────────────────
def build(start=100):
    """The section's text and its appendix tables, numbered from `start` until the report orders every table by first reference."""
    T = Tables(start)
    g = R.weekly(f"{YEAR - 1}-07-01", f"{YEAR}-06-30", [R.FIRST, R.RECOMMENDED])
    grid = R.grid()
    base, rec, first = R.outcome(None, R.SHIPPED), R.outcome(R.RECOMMENDED, R.SHIPPED), R.outcome(R.FIRST, R.SHIPPED)
    costs = {r: R.cost(r, R.SHIPPED) for r in R.EVERY}
    c, ordinary = costs[R.RECOMMENDED], R.cost(R.RECOMMENDED, R.ORDINARY, 2.0)
    by = {(qn, r): R.outcome(r, R.released_in(qn)) for qn in R.QUARTERS for r in BY_QUARTER}
    months = pd.to_datetime([f"{YEAR - 1}-11-01", f"{YEAR - 1}-12-01", f"{YEAR}-01-01", f"{YEAR}-02-01", f"{YEAR}-03-01", f"{YEAR}-04-01"])

    T.add("qtable", f"The quote table as fitted on jobs shipped 2023 to {YEAR}: 80th-percentile lead time by routing class and brake backlog at release, never below the "
                    f"class standard, a band with fewer than {R.FILL_MIN} jobs taking the band below", t_grid_full(grid))
    T.add("history", "Jobs shipped before the first of each month, by routing class and brake backlog at release: what a quote on that day is fitted on",
          t_history(months))
    T.add("rules", f"Every quote rule on jobs shipped in {YEAR} and in {RT}",
          t_outcomes(((f"Shipped {YEAR}", R.SHIPPED), (f"Shipped {YEAR} {RT}", R.SHIPPED_REST)))
          + f"<p>Each job is quoted from the jobs shipped before its release. Lines accepted inside the quote keep their recorded due date; every other non-rush line "
            f"takes the later of the requested date and the order date plus the rule's quote. The floor is as recorded. The switch of {T0:g} days was chosen on the "
            f"{YEAR} record, among {join_and([f'{t:g}' for t in R.THRESHOLDS])} days.</p>")
    T.add("release", "On-time delivery and late jobs by release quarter under current practice and four quote rules", t_release(by))
    T.add("cost", f"Orders forgone and late jobs removed by quote rule", t_cost()
          + f"<p>Orders forgone are the quotes behind the non-rush jobs, times the mean days the rule adds to the quote, times the fall in win rate per day. The fall is "
            f"measured at one point, quotes 5 days above the class standard, and is applied in proportion to the days added.</p>")
    T.add("above", "Non-rush win rate by days quoted above the class standard, 2023 to 2025", t_above())
    T.add("band", "Win rate by turnaround band", Q.t_band())
    T.add("strata", "Win rate by complexity group and turnaround", Q.t_strata())
    T.add("rush", "Win rate on rush RFQs by quoted lead time", Q.t_rush())
    T.add("groups", "Win rate by customer, key account and estimator",
          block("The ten customers with the most quotes", Q.t_group(Q.CUST, "Customer"))
          + block("Key accounts", Q.t_group(Q.KEY, "Customer group", {True: "Key account", False: "Other"}))
          + block("Estimators", Q.t_group(Q.EST, "Estimator")))
    T.add("lost", "Lost reasons as entered", Q.t_lost())
    T.add("bands", "Late rate by brake backlog at release", L.t_bands())
    T.add("threshold", f"Jobs released above {LA.BACKLOG_THRESHOLD:.0f} days of brake backlog", L.t_threshold())
    T.add("late", "Jobs released late", L.t_short())
    T.add("defs", "Weekly indicators and definitions", table(pd.DataFrame(L.DEFS, columns=["Indicator", "Definition", "Adverse direction"])))
    T.add("lags_event", "Correlation with on-time delivery by weeks of lead, ordinary weeks", L.t_lags(L.LE))
    T.add("lags_all", "Correlation with on-time delivery by weeks of lead, all weeks", L.t_lags(L.LA))
    T.add("declines", "Declines in on-time delivery", L.t_declines())
    T.add("lead_by", "Weeks each indicator moved before each decline", L.t_lead_by_decline())

    b = [f"<p>Quoting from the brake backlog at release, at or above {T0:g} days, would have raised on-time delivery for {YEAR} from {pct(base['on_time'])} to "
         f"{pct(rec['on_time'])} and removed {n0(c['removed'])} late jobs, nearly all among jobs released into the year-end build, while leaving ordinary quarters "
         f"unchanged. At the win rate the shop loses on longer quotes, it would also have cost about {n0(round(c['forgone'], -1))} orders, {money(c['revenue'])} of "
         f"revenue. The same backlog flags the jobs most likely to ship late at release, and the on-time start rate warns of a decline a week ahead.</p>"]

    # a quote from the brake backlog
    b.append("<h3 id='f4_1'>A quote from the brake backlog</h3>")
    adder = R.ADDER_WEEKS[0]
    rose = g[(g.index >= f"{YEAR - 1}-09-30") & (g[R.FIRST] - g["current"] >= 1)].index.min()
    deep = g[(g.index.year == YEAR) & (g.index.month == 1) & (g[R.FIRST] < g["current"])]
    assert len(deep) >= 3 and (R.J[(R.J["ship_date"] < deep.index.min()) & (R.J["brake_backlog_days"] > 5)]).empty
    b.append(f"<p>The shop's adder raised quotes from {day(adder)}, {(adder - rose).days // 7} weeks after the quote table's quotes first rose in the week of "
             f"{day(rose)}. The table quotes each non-rush job the 80th-percentile lead time of earlier jobs of its routing class released at the same brake backlog, "
             f"never below the class standard; the recommended rule quotes from it at or above {T0:g} days of backlog and quotes the class standard below. The table as "
             f"first fitted quoted {d1(deep[R.FIRST].mean())} days in the {L.word(len(deep))} weeks from {day(deep.index.min())} against backlogs of "
             f"{n0(deep['backlog'].min())} to {n0(deep['backlog'].max())} days because no earlier job had shipped from a backlog above 5 days; a band with fewer than "
             f"{R.FILL_MIN} earlier jobs now takes the quote of the band below it, which raises those quotes to {n0(deep[R.RECOMMENDED].min())} to "
             f"{n0(deep[R.RECOMMENDED].max())} days. {T.see('qtable', 'history')}</p>")
    b.append(chart(f"Quoted Lead Time by Routing Class and Brake Backlog at Release, Working Days", t_grid(grid)))
    b.append(titled(fig_weekly(g), f"Brake Backlog and Quoted Lead Time by Week, Current Practice Against the Recommended Rule, Q3 {YEAR - 1} to Q2 {YEAR}"))

    build_q = [f"{YEAR - 1}Q4", f"{YEAR}Q1"]
    rest_q = [qn for qn in R.QUARTERS if qn not in build_q]
    three = lambda qn: f"{pct(by[(qn, None)]['on_time'])} on time under current practice, {pct(by[(qn, R.FIRST)]['on_time'])} under the table as first fitted and " \
                       f"{pct(by[(qn, R.RECOMMENDED)]['on_time'])} under the recommended rule"
    gap = max(abs(by[(qn, R.RECOMMENDED)]["on_time"] - by[(qn, None)]["on_time"]) for qn in rest_q)
    assert gap < 0.002, gap
    low = R.switch(R.THRESHOLDS[0], True)
    lo_c, lo_rest, rec_rest = costs[low], R.outcome(low, R.SHIPPED_REST), R.outcome(R.RECOMMENDED, R.SHIPPED_REST)
    assert costs[R.LOT]["removed"] <= costs[R.FIRST]["removed"]
    b.append(f"<p>The gain is in the two quarters of the build. Jobs released in {quarter(build_q[0])} shipped {three(build_q[0])}; jobs released in "
             f"{quarter(build_q[1])}, {pct(by[(build_q[1], None)]['on_time'])}, {pct(by[(build_q[1], R.FIRST)]['on_time'])} and "
             f"{pct(by[(build_q[1], R.RECOMMENDED)]['on_time'])}. In the other {L.word(len(rest_q))} quarters the recommended rule is within 0.1 point of current "
             f"practice. Switching at {R.THRESHOLDS[0]:g} days lengthens {pct(lo_rest['longer'], 0)} of non-rush quotes on jobs shipped in {RT} against "
             f"{pct(rec_rest['longer'], 0)} and removes {n0(lo_c['removed'] - c['removed'])} more late jobs for {n0(round(lo_c['forgone'] - c['forgone'], -1))} more "
             f"orders forgone. A lot-size band in the table adds nothing: {n0(costs[R.LOT]['removed'])} late jobs removed against {n0(costs[R.FIRST]['removed'])} "
             f"without it. {T.see('rules', 'release')}</p>")
    b.append(titled(fig_quarters(by), "On-time Delivery by Release Quarter, Current Practice Against the Two Quote Rules"))

    # what a longer quote costs
    b.append("<h3 id='f4_2'>What a longer quote costs</h3>")
    above = R.WIN_ABOVE.iloc[0]
    assert len(R.WIN_ABOVE) == 1 and R.WIN_ABOVE.index[0] == 5
    TURN, lost = Q.TURN, Q.LOST.set_index("reason")["all"]
    slow_value = float((Q.QT[Q.QT["slow"] == 1]["quoted_price"] * Q.QT[Q.QT["slow"] == 1]["qty"]).mean())
    slow_orders = TURN["quotes_slow"] * TURN["adjusted_gap"] / 3
    assert slow_orders > c["forgone"] and ordinary["forgone"] < 0.5 and ordinary["removed"] == 0
    b.append(f"<p>Every day added to a quote costs orders, and the recommended rule spends them only in a build. Non-rush quotes 5 days above the class standard won "
             f"{pct(above['mean'])} against {pct(R.WIN_AT_STANDARD)} at the standard, {R.FALL * 100:.2f} points a day; the fall is measured only at 5 days, on the "
             f"{n0(above['size'])} quotes that carried the shop's adder, and is charged in proportion to the days added. At that rate the recommended rule forgoes about "
             f"{n0(round(c['forgone'], -1))} orders to remove {n0(c['removed'])} late jobs in {YEAR} and none in an ordinary year, and the shop's own adder forgoes "
             f"about {n0(round(R.ADDER_FORGONE, -1))}. Quote turnaround costs more than the rule: quotes sent after more than 3 working days win "
             f"{d1(TURN['adjusted_gap'] * 100)} points less after adjusting for RFQ complexity, about {n0(slow_orders)} orders and "
             f"${slow_orders * slow_value / 1e6:.1f}M a year. On rush RFQs the win rate falls from {pct(Q.RUSH['win_rate'].iloc[0])} at a quoted lead time of 5 days or "
             f"fewer to {pct(Q.RUSH['win_rate'].iloc[-1])} at 12 or more. {pct(lost['blank'] / lost.sum(), 0)} of lost quotes carry no reason; every lost quote should "
             f"carry one. {T.see('cost', 'above', 'band', 'strata', 'rush', 'lost')} Win rates by customer, key account and estimator are in "
             f"{T.cite('groups')}.</p>")
    b.append(titled(fig_cost(costs), f"Late Jobs Removed and Orders Forgone by Quote Rule, {YEAR}"))

    # flags at release
    b.append("<h3 id='f4_3'>Flags at release</h3>")
    ty, tq, sr = L.THR.loc[L.PY], L.THR.loc[L.PR], L.SHORT.loc[L.PR]
    assert tq["late_jobs_above"] == 0 and tq["share_of_all_jobs_above"] == 0
    b.append(f"<p>Two flags at release mark the jobs most likely to ship late: brake backlog in a build, a short due date in an ordinary quarter. Jobs released above "
             f"{LA.BACKLOG_THRESHOLD:.0f} days of brake backlog are {pct(ty['share_of_all_jobs_above'], 0)} of jobs released in {YEAR} and "
             f"{pct(ty['share_of_late_jobs_above'], 0)} of late jobs, a late rate of {pct(ty['late_rate_above'], 0)} against {pct(ty['late_rate_below'], 0)}; no job "
             f"released in {RT} crossed it. Jobs released late are {pct(sr['share_of_jobs'], 0)} of jobs released in {RT} and {pct(sr['share_of_late_jobs'], 0)} of "
             f"late jobs, a late rate of {pct(sr['late_rate_inside'])} against {pct(sr['late_rate_other'])}. Each late release should be a decision: flag the job as a "
             f"rush, with a named approver, and count these releases weekly. {T.see('bands', 'threshold', 'late')}</p>")
    b.append(titled(L.fig_backlog(), "Late Rate by Brake Backlog at Release"))

    # weekly indicators
    b.append("<h3 id='f4_4'>Weekly indicators</h3>")
    e, o, lt = L.CE.loc[L.OTS], L.DL.loc[L.OTS], L.LT
    others = [x for x in L.ABOVE_E if x != L.OTS]
    assert e["best_lead_weeks"] == 1 and L.OTS in L.ABOVE_E and o["preceded"] == len(L.DEC) and min(o["shuffled_p"], o["shifted_p"]) > 0.05
    assert others == [L.OUTSIDE], others
    laser = lt.loc[L.LASER].dropna()
    la = L.DL.loc[L.LASER]
    assert min(la["shuffled_p"], la["shifted_p"]) > 0.05
    month = lambda t: f"{t:%B %Y}"
    b.append(f"<p>The on-time start rate leads on-time delivery by one week in ordinary weeks (correlation {e['r_best_lead']:.2f}, against chance levels of "
             f"{e['shuffled_p95']:.2f} and {e['shifted_p95']:.2f}). It moved {join_and([f'{x:.0f}' for x in lt.loc[L.OTS]])} weeks before the "
             f"{L.word(len(L.DEC))} declines in on-time delivery, which cannot be told apart from chance ({d1(o['shuffled_expected'])} and {d1(o['shifted_expected'])} "
             f"expected). Jobs waiting at the lasers moved "
             f"{join_and([f'{v:.0f} weeks before the {month(pd.Timestamp(k))} decline' for k, v in laser.items()])}, {len(laser)} of {len(L.DEC)} and no better than "
             f"chance. Outside-processing receipts on time clear both chance levels only at a {L.CE.loc[L.OUTSIDE, 'best_lead_weeks']}-week lead (correlation "
             f"{L.CE.loc[L.OUTSIDE, 'r_best_lead']:.2f}); no other measure leads in ordinary weeks. "
             f"{T.see('defs', 'lags_event', 'lags_all', 'declines', 'lead_by')}</p>")

    b.append(f"<p>Quote from the recommended rule at order entry. Flag at release every job above {LA.BACKLOG_THRESHOLD:.0f} days of brake backlog and every job "
             f"released late. Review the on-time start rate weekly.</p>")
    return "\n".join(b).replace(L.REST, RT), T.appendix().replace(L.REST, RT)
