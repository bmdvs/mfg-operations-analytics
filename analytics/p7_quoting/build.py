"""P7 lead-time quoting and quote analytics: report, A3 and figures, from the marts.

Usage: python -m analytics.p7_quoting.build
"""
import numpy as np
import pandas as pd

from analytics.p7_quoting import analysis as A
from analytics.style.style import ACCENT, AMBER, BRAND_BLUE, DOCS, GREY, LIGHT_BLUE, RED, a3_shell, fig, pct, save, report_shell, table

YEAR, REST = A.YEAR, "Q2 to Q4"
PY, PR, PX = f"{YEAR}", f"{YEAR} {REST}", f"{YEAR}, released from {YEAR} Q1"
D = A.load()
J, QT = D["j"], D["qt"]
FIX = A.fixed_quote(D).set_index(["period", "routing_class"])
PROM = A.promise_types(D).set_index(["period", "promise"])
SCORES, RULE_QUOTES = A.three_rules(D)
FIXED, TABLE_IN, TRAIL, TABLE_OUT = "Fixed quote", "Quote table, never below the fixed quote", "Routing class, trailing 13 weeks", \
    "Routing class and brake backlog, all earlier jobs, never below the fixed quote"
NAMES = {FIXED: "Fixed quote", TABLE_IN: "Quote table, as fitted on 2023 to 2025 (in sample)", TABLE_OUT: "Quote table, from jobs shipped before each release (out of sample)",
         TRAIL: "Routing class, trailing 13 weeks"}
ORDER = [FIXED, TABLE_IN, TABLE_OUT, TRAIL]
SC = {k: v.set_index("group") for k, v in SCORES.items()}
QTAB = A.quote_table(D)
FAM = A.by_family(D)
TURN, TBAND, STRATA = A.turnaround(D)
RUSH = A.rush_rfq(D)
CUST, KEY, FAMW, EST = A.adjusted_groups(D, "customer_name", 10), A.adjusted_groups(D, "key_account"), A.adjusted_groups(D, "family"), A.adjusted_groups(D, "estimator")
ESTY = A.estimators(D)
LOST, STATUS = A.lost_reasons(D)
CLS = {"repeat part": "Repeat part", "new part": "New part", "outside processing": "Outside processing", "all": "All"}
QUARTERS = [g for g in SC[FIXED].index if g.startswith("released") and "," not in g]
RQ = {int(g[-1]): g for g in QUARTERS if g.startswith(f"released {YEAR}")}
FIRST_Q = QUARTERS[0]


def d1(x):
    return "" if pd.isna(x) else f"{x:.1f}"


def n0(x):
    return "" if pd.isna(x) else f"{x:,.0f}"


def nth(x):
    n = int(round(x * 100))
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def qlabel(g):
    return g.replace("released ", "")


def join_and(xs):
    xs = list(xs)
    if not xs:
        return ""
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


# ── figures ─────────────────────────────────────────────────────────────────
def fig_distribution():
    f, axes = fig(h=3.9, ncols=3)
    y = J[J["ship_date"].dt.year == YEAR]
    for ax, c in zip(axes, A.CLASSES):
        d = y[y["routing_class"] == c]
        fixed = float(d["quoted_lead_days"].iloc[0])
        ax.hist(d["wip_days"].clip(upper=45), bins=np.arange(0, 47, 1), color=LIGHT_BLUE, edgecolor="white", linewidth=0.3)
        ax.axvline(fixed, color=RED, linewidth=1.6, linestyle="--", label="Fixed quote")
        t = QTAB[QTAB["routing_class"] == c]
        quotes = [(b_, max(v_, fixed) if v_ == v_ else fixed) for b_, v_ in zip(t["band"], t["p80"])]
        at_fixed = [b_ for b_, v_ in quotes if v_ == fixed]
        labels = [f"Fixed quote{' and ' + ', '.join(at_fixed) if at_fixed else ''}: {fixed:.0f}"]
        rest = [(b_, v_) for b_, v_ in quotes if v_ != fixed]
        k = 0
        while k < len(rest):
            group = [rest[k]]
            while k + 1 < len(rest) and rest[k + 1][1] - group[-1][1] <= 1:
                k += 1
                group.append(rest[k])
            for n_, (_, v_) in enumerate(group):
                ax.axvline(v_, color=AMBER, linewidth=1.2, label="Quote table by brake backlog band (days), never below the fixed quote" if not n_ and len(labels) == 1 else None)
            labels.append(", ".join(f"{b_}: {v_:.0f}" for b_, v_ in group))
            k += 1
        top = ax.get_ylim()[1]
        ax.set_ylim(0, top * 1.38)
        ax.text(0.98, 0.98, chr(10).join(labels), transform=ax.transAxes, ha="right", va="top", fontsize=7.5, linespacing=1.35)
        ax.set_title(CLS[c], fontsize=10, loc="left")
        ax.set_xlabel("Lead time (working days)", fontsize=9.5)
    axes[0].set_ylabel("Jobs")
    hs, ls = axes[0].get_legend_handles_labels()
    f.legend(hs, ls, frameon=False, fontsize=8.5, loc="lower center", ncols=2)
    f.tight_layout(rect=(0, 0.07, 1, 1))
    return save(f, "p7_lead_time_distribution", f"Lead time of jobs shipped in {YEAR} by routing class with the fixed quote and the quote table")


def fig_hit(name="p7_hit_rate_by_release_quarter", h=3.3):
    f, ax = fig(h=h)
    x = np.arange(len(QUARTERS))
    for k, (rule, color, lab) in enumerate(((FIXED, GREY, "Fixed quote"), (TABLE_OUT, BRAND_BLUE, "Quote table, out of sample"), (TRAIL, AMBER, "Trailing 13 weeks"))):
        h_ = [SC[rule].loc[g, "met"] * 100 for g in QUARTERS]
        ax.bar(x + (k - 1) * 0.27, h_, 0.27, color=color, label=lab)
        for xi, hi in zip(x + (k - 1) * 0.27, h_):
            ax.annotate(f"{hi:.0f}", (xi, hi), textcoords="offset points", xytext=(0, 2), ha="center", fontsize=7.5, annotation_clip=False)
    ax.axhline(80, color=RED, linewidth=1, linestyle="--")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{qlabel(g)}\n{n0(SC[FIXED].loc[g, 'jobs'])} jobs" for g in QUARTERS], fontsize=9)
    ax.set_ylabel("Quote met (%)")
    ax.set_ylim(0, 100)
    ax.legend(frameon=False, fontsize=8.5, loc="upper center", bbox_to_anchor=(0.5, -0.27), ncols=3)
    f.tight_layout()
    return save(f, name, "Share of non-rush jobs meeting each quote, by release quarter")


def fig_turnaround():
    f, axes = fig(h=3.4, ncols=2, gridspec_kw=dict(width_ratios=[1, 1.5]))
    ax = axes[0]
    x = np.arange(2)
    ax.bar(x - 0.2, [TURN["fast"] * 100, TURN["slow"] * 100], 0.4, color=BRAND_BLUE, label="As quoted")
    ax.bar(x + 0.2, [TURN["adjusted_fast"] * 100, TURN["adjusted_slow"] * 100], 0.4, color=AMBER, label="Adjusted for complexity")
    for xi, hi in zip(list(x - 0.2) + list(x + 0.2), [TURN["fast"], TURN["slow"], TURN["adjusted_fast"], TURN["adjusted_slow"]]):
        ax.annotate(f"{hi * 100:.1f}", (xi, hi * 100), textcoords="offset points", xytext=(0, 2), ha="center", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(["3 days" + chr(10) + "or less", "Over" + chr(10) + "3 days"], fontsize=9)
    ax.set_ylabel("Win rate (%)")
    ax.set_ylim(0, 70)
    ax.legend(frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.2))
    ax = axes[1]
    lab = [join_and([n for n, f_ in (("new part", r.f_new), ("8 or more bends", r.f_bend), ("outside processing", r.f_op)) if f_]) or "none of the three"
           for r in STRATA.itertuples()]
    y = np.arange(len(STRATA))[::-1]
    ax.barh(y, STRATA["gap"] * 100, color=ACCENT)
    for yi, g in zip(y, STRATA["gap"] * 100):
        ax.annotate(f"{g:.1f}", (g, yi), textcoords="offset points", xytext=(3, -3), fontsize=8)
    ax.set_yticks(y)
    ax.set_yticklabels([s.capitalize() for s in lab], fontsize=8)
    ax.set_xlabel("Win rate gap, 3 days or less against over 3 days (points)", fontsize=9)
    ax.grid(axis="y", visible=False)
    f.tight_layout()
    return save(f, "p7_win_rate_by_turnaround", "Win rate by quote turnaround, as quoted and adjusted, and the gap by complexity group")


def fig_rush():
    f, ax = fig(h=2.8, w=6.0)
    x = np.arange(len(RUSH))
    ax.bar(x, RUSH["win_rate"] * 100, 0.55, color=BRAND_BLUE)
    for xi, r in zip(x, RUSH.itertuples()):
        ax.annotate(f"{r.win_rate * 100:.1f}%\n{r.quotes:,} quotes", (xi, r.win_rate * 100), textcoords="offset points", xytext=(0, 2), ha="center", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(RUSH["band"])
    ax.set_xlabel("Quoted lead time on rush RFQs (days)")
    ax.set_ylabel("Win rate (%)")
    ax.set_ylim(0, 70)
    f.tight_layout()
    return save(f, "p7_rush_rfq_win_rate", "Win rate on rush RFQs by quoted lead time")


# ── tables ──────────────────────────────────────────────────────────────────
def t_fixed(short=False):
    rows = []
    for (per, c), r in FIX.iterrows():
        row = [per, CLS[c], n0(r["jobs"]), d1(r["quoted"]) if c == "all" else n0(r["quoted"]), pct(r["percentile_of_quote"]), n0(r["median"]), n0(r["p80"]), n0(r["p90"])]
        row += [pct(r["standard_promise_on_time"])] if short else [pct(r["on_time"]), n0(r["standard_promise_jobs"]), pct(r["standard_promise_quote_met"]),
                                                                   pct(r["standard_promise_on_time"])]
        rows.append(row)
    cols = ["Period", "Routing class", "Jobs", "Fixed quote", "Percentile of the quote", "Median lead time", "80th percentile", "90th percentile"]
    cols += ["On time, standard promises"] if short else ["On time, all jobs", "Standard promises", "Lead time within the quote, standard promises",
                                                         "On time, standard promises"]
    return table(pd.DataFrame(rows, columns=cols))


def t_quote_table():
    rows = [[CLS[r.routing_class], r.band, n0(r.fixed), n0(r.jobs), n0(r.p80), n0(max(r.p80, r.fixed)) if r.p80 == r.p80 else n0(r.fixed), n0(r.jobs_ordinary),
             n0(r.p80_ordinary)] for r in QTAB.itertuples()]
    return table(pd.DataFrame(rows, columns=["Routing class", "Brake backlog at release (days)", "Fixed quote", "Jobs", "80th-percentile lead time",
                                             "Quote (never below the fixed quote)", "Jobs, ordinary quarters", "80th percentile, ordinary quarters"]))


def t_rules():
    rows = []
    for k in ORDER:
        y, r = SC[k].loc[PY], SC[k].loc[PR]
        rows.append([NAMES[k], pct(y["met"]), pct(r["met"]), "" if k == FIXED else pct(y["longer"]), "" if k == FIXED else pct(r["longer"]), d1(y["mean_quote"]),
                     d1(r["mean_quote"])] + [pct(SC[k].loc[g, "met"]) for g in QUARTERS])
    return table(pd.DataFrame(rows, columns=["Rule", f"Met, {YEAR}", f"Met, {REST}", f"Longer than the fixed quote, {YEAR}", f"Longer, {REST}",
                                             f"Mean quote, {YEAR}", f"Mean quote, {REST}"] + [f"Met, released {qlabel(g)}" for g in QUARTERS]))


def t_release_class():
    groups = [g for g in SC[FIXED].index if g.startswith("released") and "," in g]
    rows = []
    for g in groups:
        q_, c = qlabel(g).split(", ")
        row = [q_, CLS[c], n0(SC[FIXED].loc[g, "jobs"])]
        for k in ORDER:
            r = SC[k].loc[g]
            row += [pct(r["met"])] + ([] if k == FIXED else [d1(r["mean_quote"]), pct(r["longer"], 0)])
        rows.append(row)
    short = {FIXED: "Fixed", TABLE_IN: "Table, in sample", TABLE_OUT: "Table, out of sample", TRAIL: "Trailing 13 weeks"}
    cols = ["Released", "Routing class", "Jobs"]
    for k in ORDER:
        cols += [f"{short[k]}: met"] + ([] if k == FIXED else [f"{short[k]}: mean quote", f"{short[k]}: longer"])
    return table(pd.DataFrame(rows, columns=cols))


def t_promises():
    rows = [[per, t.capitalize(), n0(r["jobs"]), pct(r["share_of_jobs"]), d1(r["promised_mean"]), n0(r["actual_median"]), pct(r["on_time"]), pct(r["quote_met"]),
             n0(r["late_jobs"]), pct(r["share_of_late_jobs"]), n0(r["days_late"]), pct(r["share_of_days_late"]), n0(r["released_late_days"])] for (per, t), r in PROM.iterrows()]
    return table(pd.DataFrame(rows, columns=["Period", "Promise", "Jobs", "Share of jobs", "Mean promised lead", "Median lead time", "On time to the promise",
                                             "Within the standard lead time", "Late jobs", "Share of late jobs", "Days late", "Share of days late",
                                             "Released-late days (P2)"]))


def t_family():
    rows = [[x.period, x.family.capitalize(), CLS[x.routing_class], n0(x.jobs), d1(x.promised_mean), n0(x.actual_median), n0(x.actual_p80), pct(x.quote_met),
             pct(x.on_time)] for x in FAM.itertuples()]
    return table(pd.DataFrame(rows, columns=["Period", "Part family", "Routing class", "Jobs", "Mean promised lead", "Median lead time", "80th percentile",
                                             "Within the standard lead time", "On time"]))


def t_band():
    rows = [[x.turnaround, n0(x.quotes), pct(x.win_rate), pct(x.new_part), pct(x.bends_8), pct(x.outside)] for x in TBAND.itertuples()]
    return table(pd.DataFrame(rows, columns=["Turnaround (weekdays)", "Quotes", "Win rate", "New part", "8 or more bends", "Outside processing"]))


def t_strata():
    yn = {1: "yes", 0: "no"}
    rows = [[yn[x.f_new], yn[x.f_bend], yn[x.f_op], n0(x.quotes_fast), pct(x.win_fast), n0(x.quotes_slow), pct(x.win_slow), d1(x.gap * 100)] for x in STRATA.itertuples()]
    return table(pd.DataFrame(rows, columns=["New part", "8 or more bends", "Outside processing", "Quotes, 3 days or less", "Win rate, 3 days or less",
                                             "Quotes, over 3 days", "Win rate, over 3 days", "Gap (points)"]))


def t_group(g, label, names=None):
    rows = [[(names or {}).get(getattr(x, g.columns[0]), str(getattr(x, g.columns[0]))), n0(x.quotes), pct(x.win_rate), pct(x.expected), pct(x.adjusted),
             n0(x.turnaround_median), pct(x.slow), pct(x.new_part)] for x in g.itertuples()]
    return table(pd.DataFrame(rows, columns=[label, "Quotes", "Win rate", "Expected from complexity", "Adjusted win rate", "Median turnaround", "Over 3 days",
                                             "New part"]))


def t_estimators():
    rows = [[x.estimator, x.rfq_year, n0(x.quotes), n0(x.turnaround_median), f"{x.turnaround_mean:.2f}", pct(x.slow), pct(x.win_rate), pct(x.new_part)]
            for x in ESTY.itertuples()]
    return table(pd.DataFrame(rows, columns=["Estimator", "Year", "Quotes", "Median turnaround", "Mean turnaround", "Over 3 days", "Win rate", "New part"]))


def t_lost():
    rows = [[str(x[0]).capitalize()] + [n0(v_) for v_ in x[1:]] for x in LOST.itertuples(index=False)]
    return table(pd.DataFrame(rows, columns=["Lost reason", "Turnaround 3 days or less", "Turnaround over 3 days", "All"]))


def t_rush():
    rows = [[x.band, n0(x.quotes), pct(x.win_rate), pct(x.lost_to_lead_time)] for x in RUSH.itertuples()]
    return table(pd.DataFrame(rows, columns=["Quoted lead time (days)", "Quotes", "Win rate", "Lost with reason lead time, share of quotes"]))


# ── report ──────────────────────────────────────────────────────────────────
HEADER_META = (f"Custom sheet-metal fabrication job shop, about 120 employees, one plant. Jobs shipped in {YEAR}, whole year and {REST}; quotes with the RFQ received "
               f"from 2023 to {YEAR}.<br>Sources: ERP quotes, orders, jobs and shipments, shop-floor data collection (batch {D['batch']}). Lead time in working days "
               f"from the release day to the ship day; turnaround in weekdays.")


def fx(per, c, col):
    return FIX.loc[(per, c), col]


def pr(per, t, col):
    return PROM.loc[(per, t), col]


def report():
    ti, to, tr, fq = SC[TABLE_IN], SC[TABLE_OUT], SC[TRAIL], SC[FIXED]
    b = []
    b.append("<h2 id='f1'>1. The fixed quote in the lead-time distribution</h2>")
    b.append(f"<p>The 10-day repeat quote sits at the {nth(fx(PY, 'repeat part', 'percentile_of_quote'))} percentile of {YEAR} repeat lead time "
             f"({nth(fx(PR, 'repeat part', 'percentile_of_quote'))} in {REST}), the 15-day new-part quote at the {nth(fx(PY, 'new part', 'percentile_of_quote'))} "
             f"({nth(fx(PR, 'new part', 'percentile_of_quote'))}) and the 20-day outside-processing quote at the "
             f"{nth(fx(PY, 'outside processing', 'percentile_of_quote'))} ({nth(fx(PR, 'outside processing', 'percentile_of_quote'))}). Standard promises shipped "
             f"{pct(fx(PY, 'all', 'standard_promise_on_time'))} on time for the year and {pct(fx(PR, 'all', 'standard_promise_on_time'))} in {REST}.</p>")
    b.append(t_fixed())
    b.append(f"<div class='caption'>Table 1. The fixed quote against the lead time of jobs shipped, by routing class, {YEAR} and {REST}.</div>")
    b.append(fig_distribution())
    b.append(f"<div class='caption'>Figure 1. Lead time of jobs shipped in {YEAR} by routing class, with the fixed quote and the quote-table values by brake backlog "
             f"band marked.</div>")

    b.append("<h2 id='f2'>2. Rush lines and short promises</h2>")
    b.append(f"<p>Rush lines ship within the standard lead time on {pct(pr(PY, 'rush', 'quote_met'))} of jobs ({pct(pr(PR, 'rush', 'quote_met'))} in {REST}) and on "
             f"time to their promise on {pct(pr(PY, 'rush', 'on_time'))} ({pct(pr(PR, 'rush', 'on_time'))}); short promises not flagged rush "
             f"{pct(pr(PY, 'short promise, not rush', 'quote_met'))} ({pct(pr(PR, 'short promise, not rush', 'quote_met'))}) and "
             f"{pct(pr(PY, 'short promise, not rush', 'on_time'))} ({pct(pr(PR, 'short promise, not rush', 'on_time'))}). They are "
             f"{pct(pr(PY, 'rush', 'share_of_jobs'))} and {pct(pr(PY, 'short promise, not rush', 'share_of_jobs'))} of jobs and together "
             f"{pct(pr(PY, 'rush', 'share_of_late_jobs') + pr(PY, 'short promise, not rush', 'share_of_late_jobs'))} of late jobs and "
             f"{pct(pr(PY, 'rush', 'share_of_days_late') + pr(PY, 'short promise, not rush', 'share_of_days_late'))} of days late for the year, "
             f"{pct(pr(PR, 'rush', 'share_of_late_jobs') + pr(PR, 'short promise, not rush', 'share_of_late_jobs'))} and "
             f"{pct(pr(PR, 'rush', 'share_of_days_late') + pr(PR, 'short promise, not rush', 'share_of_days_late'))} in {REST}. P2 attributes "
             f"{n0(pr(PY, 'rush', 'released_late_days') + pr(PY, 'short promise, not rush', 'released_late_days'))} of their "
             f"{n0(pr(PY, 'rush', 'days_late') + pr(PY, 'short promise, not rush', 'days_late'))} days late to the promise itself.</p>")

    b.append("<h2 id='f3'>3. The quote table</h2>")
    q = QTAB.set_index(["routing_class", "band"])["p80"]
    b.append(f"<p>A quote from the 80th-percentile lead time by routing class and brake backlog at release, never below the fixed quote, is met on "
             f"{pct(to.loc[PY, 'met'])} of non-rush jobs for the year and {pct(to.loc[PR, 'met'])} in {REST} when each job is quoted from the jobs shipped before "
             f"its release, against {pct(fq.loc[PY, 'met'])} and {pct(fq.loc[PR, 'met'])} for the fixed quote; it is longer than the fixed quote on "
             f"{pct(to.loc[PY, 'longer'])} and {pct(to.loc[PR, 'longer'])} of jobs. The rule quotes the 80th percentile, so 80% is its hit rate by construction on the "
             f"jobs quoted. The table as fitted on 2023 to {YEAR} (Table 2) is met in sample on {pct(ti.loc[PY, 'met'])} and {pct(ti.loc[PR, 'met'])} and is longer "
             f"on {pct(ti.loc[PY, 'longer'])} and {pct(ti.loc[PR, 'longer'])}; the gap for the year is what the table's high-backlog bands learn from the 2024 to "
             f"{YEAR} event. Under 2 days of backlog the table gives {n0(q[('repeat part', 'under 2')])}, {n0(q[('new part', 'under 2')])} and "
             f"{n0(q[('outside processing', 'under 2')])} days; its lowest band for repeat parts is {n0(q[('repeat part', 'under 2')])} days against the fixed 10, so "
             f"every repeat part is quoted at least one day longer, and the median lengthening where longer is {n0(ti.loc[PR, 'median_longer_by'])} day in {REST}. "
             f"The trailing 13-week rule is met on {pct(tr.loc[PY, 'met'])} and {pct(tr.loc[PR, 'met'])} and is longer on {pct(tr.loc[PY, 'longer'])} and "
             f"{pct(tr.loc[PR, 'longer'])}.</p>")
    b.append(t_quote_table())
    b.append(f"<div class='caption'>Table 2. The quote table: 80th-percentile lead time by routing class and brake backlog at release, jobs shipped 2023 to {YEAR}."
             f"</div>")
    b.append(t_rules())
    b.append(f"<div class='caption'>Table 3. Four quote rules on non-rush jobs shipped in {YEAR}: share meeting the quote, share quoted longer than the fixed quote, "
             f"mean quote, and share meeting the quote by release quarter.</div>")

    b.append("<h2 id='f4'>4. By release quarter</h2>")
    q2 = [g for g in SC[TRAIL].index if g.startswith(f"released {YEAR} Q2,")]
    b.append(f"<p>Jobs released in {qlabel(FIRST_Q)} ({n0(fq.loc[FIRST_Q, 'jobs'])}) met the fixed quote on {pct(fq.loc[FIRST_Q, 'met'])} and the trailing rule on "
             f"{pct(tr.loc[FIRST_Q, 'met'])}; the quote table as fitted, reading the backlog on the day, quoted them {d1(ti.loc[FIRST_Q, 'mean_quote'])} days on "
             f"average and was met on {pct(ti.loc[FIRST_Q, 'met'])} ({pct(to.loc[FIRST_Q, 'met'])} out of sample). From jobs released in {YEAR} Q1 onward the quote "
             f"table is met on {pct(ti.loc[PX, 'met'])} for the year ({pct(to.loc[PX, 'met'])} out of sample), the trailing rule on {pct(tr.loc[PX, 'met'])} and the "
             f"fixed quote on {pct(fq.loc[PX, 'met'])}. The trailing rule quotes {n0(tr.loc[q2, 'mean_quote'].min())} to {n0(tr.loc[q2, 'mean_quote'].max())} days to "
             f"jobs released in {YEAR} Q2 and is met on {pct(tr.loc[q2, 'met'].min(), 0)} to {pct(tr.loc[q2, 'met'].max(), 0)} of them; the quote table carries load "
             f"through the backlog band rather than a window. For jobs released in {YEAR} Q3 and Q4 the out-of-sample quote table and the fixed quote are met at "
             f"the same rate ({pct(to.loc[RQ[3], 'met'])} against {pct(fq.loc[RQ[3], 'met'])}, {pct(to.loc[RQ[4], 'met'])} against {pct(fq.loc[RQ[4], 'met'])}); "
             f"the table's gain is on jobs released from {YEAR} Q1 to Q2, into and out of the event.</p>")
    b.append(fig_hit())
    b.append(f"<div class='caption'>Figure 2. Share of non-rush jobs meeting the fixed quote, the out-of-sample quote table and the trailing 13-week rule, by release "
             f"quarter; the line is 80%.</div>")

    b.append("<h2 id='f5'>5. Win rate and turnaround</h2>")
    b.append(f"<p>Quotes sent within 3 days win {pct(TURN['fast'])} against {pct(TURN['slow'])} for those taking longer, a gap of {d1(TURN['raw_gap'] * 100)} points "
             f"and {d1(TURN['adjusted_gap'] * 100)} ({d1(TURN['adjusted_low'] * 100)} to {d1(TURN['adjusted_high'] * 100)}) after adjusting for RFQ complexity. Within "
             f"the eight complexity groups the gap is {d1(STRATA['gap'].min() * 100)} to {d1(STRATA['gap'].max() * 100)} points. The "
             f"{n0(TBAND.loc[TBAND['turnaround'] == '0 to 1', 'quotes'].iloc[0])} quotes turned in 0 to 1 day hold no new parts, no parts with 8 or more bends and no "
             f"outside processing. The win rate overall is {pct(TURN['win_rate'])} on {n0(TURN['quotes'])} quotes; {pct(TURN['quotes_fast'] / TURN['quotes'])} are "
             f"sent within 3 days.</p>")
    b.append(fig_turnaround())
    b.append("<div class='caption'>Figure 3. Win rate by quote turnaround, as quoted and adjusted for RFQ complexity, and the gap within each complexity group.</div>")

    b.append("<h2 id='f6'>6. Rush RFQs</h2>")
    b.append(f"<p>On rush RFQs the win rate falls from {pct(RUSH['win_rate'].iloc[0])} at a quoted lead time of 5 days or fewer to {pct(RUSH['win_rate'].iloc[-1])} at "
             f"12 or more, and lead time is the entered lost reason on {pct(RUSH['lost_to_lead_time'].iloc[0])} to {pct(RUSH['lost_to_lead_time'].max())} of them. The "
             f"quote table lengthens {pct(to.loc[PY, 'longer'])} of non-rush promises for the year and {pct(to.loc[PR, 'longer'])} in {REST} out of sample "
             f"({pct(ti.loc[PY, 'longer'])} and {pct(ti.loc[PR, 'longer'])} as fitted).</p>")
    b.append(fig_rush())
    b.append("<div class='caption'>Figure 4. Win rate on rush RFQs by quoted lead time.</div>")

    b.append("<h2 id='f7'>7. Customers, key accounts and part families</h2>")
    top = CUST.iloc[0]
    hi, lo = CUST.sort_values("adjusted").iloc[-1], CUST.sort_values("adjusted").iloc[0]
    k = KEY.set_index("key_account")
    b.append(f"<p>{top['customer_name']}, the customer with the most quotes ({n0(top['quotes'])}), wins {pct(top['win_rate'])} against {pct(top['expected'])} "
             f"expected from the complexity of its RFQs. Among the ten customers with the most quotes the adjusted win rate runs from {pct(lo['adjusted'])} "
             f"({lo['customer_name']}) to {pct(hi['adjusted'])} ({hi['customer_name']}). Key accounts win {pct(k.loc[True, 'win_rate'])} against "
             f"{pct(k.loc[False, 'win_rate'])} for other customers. By part family the win rate runs from {pct(FAMW['win_rate'].min())} to "
             f"{pct(FAMW['win_rate'].max())} and, adjusted for complexity, from {pct(FAMW['adjusted'].min())} to {pct(FAMW['adjusted'].max())}.</p>")

    b.append("<h2 id='f8'>8. Estimators</h2>")
    b.append(f"<p>The four estimators do not differ: median turnaround is {n0(EST['turnaround_median'].min())} days for each, {pct(EST['slow'].min())} to "
             f"{pct(EST['slow'].max())} of their quotes take over 3 days, and the adjusted win rate is {pct(EST['adjusted'].min())} to {pct(EST['adjusted'].max())}.</p>")

    b.append("<h2 id='f9'>9. Lost reasons as entered</h2>")
    lost = LOST.set_index("reason")["all"]
    b.append(f"<p>{n0(lost['blank'])} of {n0(lost.sum())} lost quotes carry no reason ({pct(lost['blank'] / lost.sum(), 0)}); price is entered on {n0(lost['price'])} "
             f"and lead time on {n0(lost['lead time'])}. {n0(STATUS.get('no decision', 0))} quotes have no decision recorded.</p>")

    b.append("<h2 id='rec'>Recommendation</h2>")
    b.append(f"<p>Quote from the table at order entry by routing class and the brake backlog on the day of the quote, never below the fixed quote: out of sample it is "
             f"met on {pct(to.loc[PR, 'met'])} of non-rush jobs in {REST} and lengthens {pct(to.loc[PR, 'longer'])} of them. Refresh the table quarterly from the "
             f"trailing twelve quarters, all quarters included, so the high-backlog bands keep their counts. Require the rush flag and a named approver on every "
             f"promise inside the standard lead time (P2). Turn complex RFQs in three days or less. Require a lost reason on every lost quote.</p>")

    b.append("<h2 id='method'>Method and data</h2>")
    oq = QTAB.set_index(["routing_class", "band"])["jobs_ordinary"]
    b.append(f"<p>A quote is met when the working days from the release day to the ship day are at or under it. The fixed quote is 10 days for repeat parts, 15 for "
             f"new parts and 20 with outside processing; a new-part job is the first order against a new-part quote line within 60 days of the quote decision. "
             f"Standard promises are lines that are not rush and not promised inside the standard lead time.<br>"
             f"Brake backlog at release is the standard hours of brake operations waiting at 10:00 on the release date, at the brakes' actual-over-standard ratio, "
             f"in days of crewed brake capacity; bands are under 2, 2 to 3, 3 to 5 and over 5 days. The quote is the 80th-percentile lead time of the routing class "
             f"and band, rounded up; with fewer than {A.MIN_JOBS} jobs in a band the routing class is used. Out of sample, each job is quoted from jobs shipped "
             f"before its release date. The ordinary quarters alone hold {n0(oq[('repeat part', 'over 5')])} repeat-part jobs and {n0(oq[('new part', 'over 5')])} "
             f"new-part jobs over 5 days of backlog. Rush lines are not requoted.<br>"
             f"Win rate is won over quotes sent, with no decision counted as not won. The adjustment is a logistic model of the win on turnaround over 3 days, new "
             f"part, 8 or more bends and outside processing; the adjusted rates are the model's mean predicted win rate with every quote set to 3 days or less and "
             f"to over 3 days, with the interval from 200 resamples of the quotes. Group win rates are adjusted as the overall rate plus the group's rate less the "
             f"rate expected from its mix of new parts, 8 or more bends, outside processing and rush RFQs.</p>")

    b.append("<h2 id='appendix'>Appendix</h2>")
    b.append("<h3>Table 4. Rush lines, short promises and standard promises</h3>" + t_promises())
    b.append("<h3>Table 5. Quote rules by release quarter and routing class</h3>" + t_release_class())
    b.append("<h3>Table 6. Promised and actual lead time by part family and routing class</h3>" + t_family())
    b.append("<h3>Table 7. Win rate by turnaround band</h3>" + t_band())
    b.append("<h3>Table 8. Win rate by complexity group and turnaround</h3>" + t_strata())
    b.append("<h3>Table 9. Win rate on rush RFQs by quoted lead time</h3>" + t_rush())
    b.append("<h3>Table 10. Win rate by customer: the ten customers with the most quotes</h3>" + t_group(CUST, "Customer"))
    b.append("<h3>Table 11. Win rate by key account and part family</h3>" + t_group(KEY, "Customer group", {True: "Key account", False: "Other"}) +
             t_group(FAMW.assign(family=FAMW["family"].str.capitalize()), "Part family"))
    b.append("<h3>Table 12. Quote volume and turnaround by estimator</h3>" + t_estimators() + t_group(EST, "Estimator, 2023 to 2025"))
    b.append("<h3>Table 13. Lost reasons as entered</h3>" + t_lost())
    toc = [("f1", "The fixed quote"), ("f2", "Rush and short promises"), ("f3", "The quote table"), ("f4", "By release quarter"), ("f5", "Win rate and turnaround"),
           ("f6", "Rush RFQs"), ("f7", "Customers and families"), ("f8", "Estimators"), ("f9", "Lost reasons"), ("rec", "Recommendation"),
           ("method", "Method and data"), ("appendix", "Appendix")]
    (DOCS / "reports").mkdir(parents=True, exist_ok=True)
    (DOCS / "reports" / "p7_quoting.html").write_text(report_shell("Lead-time quoting and quote analytics", "Project 7 report", HEADER_META, "\n".join(b), toc),
                                                     encoding="utf8")


COUNTERMEASURES = [
    ("Quote table in the order-entry screen: routing class and the brake backlog on the day, never below the fixed quote", "Customer service manager, IT", "April 2026"),
    ("Rush flag and a named approver on every promise inside the standard lead time (P2)", "Customer service manager", "February 2026"),
    ("Quote turnaround of three days or less on complex RFQs", "Estimating lead", "March 2026"),
    ("Lost reason required on every lost quote", "Customer service manager", "February 2026"),
]


def a3():
    ti, to, tr, fq = SC[TABLE_IN], SC[TABLE_OUT], SC[TRAIL], SC[FIXED]
    left, right = [], []
    left.append(f"<section><h2>Background and problem</h2><p>The 10-day repeat quote sits at the {nth(fx(PY, 'repeat part', 'percentile_of_quote'))} percentile of "
                f"{YEAR} repeat lead time ({nth(fx(PR, 'repeat part', 'percentile_of_quote'))} in {REST}); standard promises shipped "
                f"{pct(fx(PY, 'all', 'standard_promise_on_time'))} on time ({pct(fx(PR, 'all', 'standard_promise_on_time'))}).<br>Rush lines and short promises are "
                f"{pct(pr(PR, 'rush', 'share_of_jobs') + pr(PR, 'short promise, not rush', 'share_of_jobs'))} of jobs and "
                f"{pct(pr(PR, 'rush', 'share_of_late_jobs') + pr(PR, 'short promise, not rush', 'share_of_late_jobs'))} of late jobs in {REST}; "
                f"{pct(TURN['quotes_fast'] / TURN['quotes'])} of quotes are sent within 3 days.</p></section>")
    left.append(f"<section><h2>Current condition</h2>{t_fixed(short=True)}<div class='caption'>The fixed quote against the lead time of jobs shipped, by routing "
                f"class.</div></section>")
    left.append("<section><h2>Target</h2><p>Promised lead times met on 80% of standard promises in every quarter, and quote turnaround of three days or less on 80% "
                "of RFQs.</p></section>")
    q2 = [g for g in SC[TRAIL].index if g.startswith(f"released {YEAR} Q2,")]
    right.append(
        f"<section><h2>Analysis</h2>{fig_hit('p7_a3_hit_rate_by_release_quarter', 2.7)}<div class='caption'>Share of non-rush jobs meeting each quote by release "
        f"quarter; the line is 80%.</div><ul>"
        f"<li>The fixed quote is met on {pct(fq.loc[PY, 'met'])} of non-rush jobs for the year and {pct(fq.loc[PR, 'met'])} in {REST}.</li>"
        f"<li>A quote by routing class and brake backlog at release, never below the fixed quote, is met out of sample on {pct(to.loc[PY, 'met'])} and "
        f"{pct(to.loc[PR, 'met'])} and lengthens {pct(to.loc[PY, 'longer'])} and {pct(to.loc[PR, 'longer'])} of promises.</li>"
        f"<li>For jobs released in {YEAR} Q3 and Q4 the out-of-sample table and the fixed quote are met at the same rate ({pct(to.loc[RQ[3], 'met'])} against "
        f"{pct(fq.loc[RQ[3], 'met'])}, {pct(to.loc[RQ[4], 'met'])} against {pct(fq.loc[RQ[4], 'met'])}); the gain is on jobs released from Q1 to Q2.</li>"
        f"<li>Quotes sent within 3 days win {pct(TURN['fast'])} against {pct(TURN['slow'])}; {d1(TURN['adjusted_gap'] * 100)} points "
        f"({d1(TURN['adjusted_low'] * 100)} to {d1(TURN['adjusted_high'] * 100)}) after adjusting for RFQ complexity.</li></ul></section>")
    right.append(f"<section><h2>Countermeasures</h2>{table(pd.DataFrame(COUNTERMEASURES, columns=['Action', 'Owner', 'When']))}</section>")
    right.append(f"<section><h2>Expected results</h2><p>On the record of {YEAR}: the quote table met on {pct(to.loc[PR, 'met'])} of non-rush jobs in {REST} out of "
                 f"sample ({pct(ti.loc[PR, 'met'])} as fitted) against {pct(fq.loc[PR, 'met'])} for the fixed quote, and {pct(to.loc[RQ[2], 'met'])}, {pct(to.loc[RQ[3], 'met'])} and "
                 f"{pct(to.loc[RQ[4], 'met'])} for jobs released in Q2, Q3 and Q4, with {pct(to.loc[PR, 'longer'])} of promises "
                 f"longer. The adjusted win-rate gap between quotes sent within 3 days and later is {d1(TURN['adjusted_gap'] * 100)} points.</p></section>")
    right.append("<section><h2>Follow-up</h2><p>The quote table refreshed quarterly from the trailing twelve quarters, all quarters included. Hit rate and share of "
                 "quotes longer than the fixed quote reported monthly.</p></section>")
    (DOCS / "a3").mkdir(parents=True, exist_ok=True)
    (DOCS / "a3" / "p7_quoting.html").write_text(a3_shell("Lead-time quoting and quote analytics", "Project 7 A3", HEADER_META, "\n".join(left), "\n".join(right)),
                                                encoding="utf8")


def main():
    report()
    a3()
    print("wrote docs/reports/p7_quoting.html and docs/a3/p7_quoting.html")


if __name__ == "__main__":
    main()
