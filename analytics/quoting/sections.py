"""Lead-time quoting and quote analytics: the data, tables and figures of its part of the report, from the marts.

Built by analytics.reports.quoting_and_early_warning.
"""
import numpy as np
import pandas as pd

from analytics.quoting import analysis as A
from analytics.style.style import ACCENT, AMBER, BRAND_BLUE, DOCS, GREY, LIGHT_BLUE, RED, fig, pct, save_conformed as save, table

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
    return save(f, "quoting_lead_time_distribution", f"Lead time of jobs shipped in {YEAR} by routing class with the fixed quote and the quote table")


def fig_hit(name="quoting_hit_rate_by_release_quarter", h=3.3):
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
    return save(f, "quoting_win_rate_by_turnaround", "Win rate by quote turnaround, as quoted and adjusted, and the gap by complexity group")


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
    return save(f, "quoting_rush_rfq_win_rate", "Win rate on rush RFQs by quoted lead time")


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
    kind = {"rush": "Rush", "short promise, not rush": "Released late, not rush", "standard promise": "Standard promise"}
    rows = [[per, kind[t], n0(r["jobs"]), pct(r["share_of_jobs"]), d1(r["promised_mean"]), n0(r["actual_median"]), pct(r["on_time"]), pct(r["quote_met"]),
             n0(r["late_jobs"]), pct(r["share_of_late_jobs"]), n0(r["days_late"]), pct(r["share_of_days_late"]), n0(r["released_late_days"])] for (per, t), r in PROM.iterrows()]
    return table(pd.DataFrame(rows, columns=["Period", "Order line", "Jobs", "Share of jobs", "Mean promised lead time", "Median lead time", "On time to the promised date",
                                             "Within the standard lead time", "Late jobs", "Share of late jobs", "Days late", "Share of days late",
                                             "Released-late days (the flow report)"]))


def t_family():
    rows = [[x.period, x.family.capitalize(), CLS[x.routing_class], n0(x.jobs), d1(x.promised_mean), n0(x.actual_median), n0(x.actual_p80), pct(x.quote_met),
             pct(x.on_time)] for x in FAM.itertuples()]
    return table(pd.DataFrame(rows, columns=["Period", "Part family", "Routing class", "Jobs", "Mean promised lead time", "Median lead time", "80th percentile",
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


def fx(per, c, col):
    return FIX.loc[(per, c), col]


def pr(per, t, col):
    return PROM.loc[(per, t), col]
