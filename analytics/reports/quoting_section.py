"""The quoting section and the early warning section of the flow report, each with its appendix tables."""
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

from analytics.leading_indicators import analysis as LA
from analytics.leading_indicators import sections as L
from analytics.quoting import accuracy as A
from analytics.reports.layout import RT, Tables, block, chart, join_and, titled
from analytics.style.style import AMBER, BRAND_BLUE, GREY, LIGHT_BLUE, RED, fig, pct, save_conformed as save, table

YEAR = A.YEAR
QUOTING, WARNING = "Quoting", "Early Warning"
CLS = {"repeat part": "Repeat part", "new part": "New part", "outside processing": "Outside processing", "all": "All"}
FITTED = "fitted on 2023 to 2025"
SHORT = {A.CURRENT: "Current quote", A.CLASS: "Class median", A.REC: "Recommended quote, out of sample", A.REC_FIT: f"Recommended quote, {FITTED}"}
d1 = lambda x: f"{x:.1f}"
d2 = lambda x: f"{x:.2f}"
sg = lambda x, d=2: f"{x:+.{d}f}"
n0 = lambda x: f"{x:,.0f}"
month = lambda m: f"{m.to_timestamp():%B %Y}"


def shade(ax):
    for m in A.LOADED:
        t = m.to_timestamp()
        ax.axvspan(t - pd.Timedelta(days=15), t + pd.Timedelta(days=15), color=GREY, alpha=0.18, lw=0)


# ── figures ─────────────────────────────────────────────────────────────────
def fig_quote_and_actual(m):
    f, axes = fig(h=5.2, nrows=2, sharex=True, gridspec_kw=dict(height_ratios=[1.5, 1]))
    x = m.index.to_timestamp()
    for ax in axes:
        shade(ax)
    ax = axes[0]
    ax.plot(x, m["actual"], color=BRAND_BLUE, lw=1.8, label="Actual lead time")
    ax.plot(x, m[f"quoted|{A.CURRENT}"], color=AMBER, lw=1.8, label="Quoted lead time")
    ax.set_ylabel("Mean working days," + "\n" + "non-rush jobs released")
    ax.set_ylim(0, None)
    hs, ls = ax.get_legend_handles_labels()
    ax.legend(hs + [Patch(color=GREY, alpha=0.18, lw=0)], ls + [f"Loaded months ({A.LOADED_AT:g} days of brake backlog or more)"], frameon=False, fontsize=9, ncol=3)
    ax = axes[1]
    ax.plot(x, m["backlog"], color=BRAND_BLUE, lw=1.6)
    ax.axhline(A.LOADED_AT, color=RED, lw=1, ls="--")
    ax.annotate(f"{A.LOADED_AT:g} days", (x[1], A.LOADED_AT), textcoords="offset points", xytext=(0, 4), fontsize=8, color=RED)
    ax.set_ylabel("Mean brake backlog" + "\n" + "at release (days)")
    ax.set_xlabel("Release month")
    ax.set_ylim(0, None)
    f.tight_layout()
    return save(f, "quote_and_actual_by_release_month", "")


def fig_conditions(backlog, outside):
    f, axes = fig(h=3.4, ncols=2, sharey=True, gridspec_kw=dict(width_ratios=[2.2, 1]))
    for ax, t, lab in ((axes[0], backlog, "Brake backlog at release (days)"), (axes[1], outside, "Outside processing on the routing")):
        x = np.arange(len(t))
        ax.bar(x, t["bias"], 0.62, color=[RED if v > 0 else BRAND_BLUE for v in t["bias"]])
        ax.axhline(0, color="#333333", lw=1)
        for xi, v in zip(x, t["bias"]):
            ax.annotate(sg(v, 1), (xi, v), textcoords="offset points", xytext=(0, 3 if v > 0 else -10), ha="center", fontsize=8.5)
        ax.set_xticks(x)
        ax.set_xticklabels([str(i).capitalize() for i in t.index], fontsize=9)
        ax.set_xlabel(lab)
    axes[0].set_ylabel("Actual less quoted lead time," + "\n" + "working days")
    lo, hi = axes[0].get_ylim()
    axes[0].set_ylim(lo - 0.8, hi + 0.8)
    f.legend([Patch(color=RED), Patch(color=BRAND_BLUE)], ["Quote too short", "Quote too long"], frameon=False, fontsize=9, ncol=2, loc="lower center")
    f.tight_layout(rect=(0, 0.07, 1, 1))
    return save(f, "quote_error_by_condition", "")


def fig_error_by_month(m):
    f, ax = fig(h=3.5)
    x = m.index.to_timestamp()
    shade(ax)
    ax.plot(x, m[f"mae|{A.CURRENT}"], color=AMBER, lw=1.8, label=SHORT[A.CURRENT])
    ax.plot(x, m[f"mae|{A.CLASS}"], color=LIGHT_BLUE, lw=1.5, label=SHORT[A.CLASS])
    ax.plot(x, m[f"mae|{A.REC}"], color=BRAND_BLUE, lw=1.8, label=SHORT[A.REC])
    ax.set_ylabel("Mean absolute error (working days)")
    ax.set_xlabel("Release month")
    ax.set_ylim(0, None)
    hs, ls = ax.get_legend_handles_labels()
    f.legend(hs + [Patch(color=GREY, alpha=0.18, lw=0)], ls + ["The four months of the build"], frameon=False, fontsize=9, ncol=2, loc="lower center")
    f.tight_layout(rect=(0, 0.13, 1, 1))
    return save(f, "quote_error_by_release_month", "")


def fig_ordinary_and_loaded(scores):
    f, axes = fig(h=3.6, ncols=2)
    quotes = [(A.CURRENT, AMBER, None), (A.CLASS, LIGHT_BLUE, None), (A.REC, BRAND_BLUE, None), (A.REC_FIT, BRAND_BLUE, "///")]
    for ax, key, lab in ((axes[0], "bias", "Mean error (working days)"), (axes[1], "mae", "Mean absolute error (working days)")):
        for g, per in enumerate(("Ordinary months", "Loaded months")):
            for k, (qn, color, hatch) in enumerate(quotes):
                v = scores[(qn, per)][key]
                ax.bar(g + (k - 1.5) * 0.2, v, 0.19, color="white" if hatch else color, edgecolor=color, hatch=hatch, linewidth=0.8, label=SHORT[qn] if g == 0 else None)
                ax.annotate(sg(v, 1) if key == "bias" else d1(v), (g + (k - 1.5) * 0.2, v), textcoords="offset points", xytext=(0, 3 if v >= 0 else -10), ha="center", fontsize=7.5)
        ax.axhline(0, color="#333333", lw=1)
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["Ordinary months", "Loaded months"], fontsize=9)
        ax.set_ylabel(lab)
        lo, hi = ax.get_ylim()
        ax.set_ylim(lo - (0.9 if lo < 0 else 0), hi + 0.9)
    f.legend(*axes[0].get_legend_handles_labels(), frameon=False, fontsize=9, ncol=2, loc="lower center")
    f.tight_layout(rect=(0, 0.13, 1, 1))
    return save(f, "quote_error_ordinary_and_loaded", "")


# ── tables ──────────────────────────────────────────────────────────────────
def t_grid(g):
    rows = [[CLS[c], n0(r["standard"]), n0(r["median"])] + [n0(r[b]) for b in A.BANDS] for c, r in g.iterrows()]
    return table(pd.DataFrame(rows, columns=["Routing class", "Class standard", "Class median"] + [f"{b.capitalize()} day{'' if b == A.BANDS[0] else 's'}" for b in A.BANDS]))


def t_periods():
    rows = []
    for per, f in A.PERIODS.items():
        for c in ["all"] + A.CLASSES:
            d = f(A.D)
            s = A.score(d if c == "all" else d[d["routing_class"] == c])
            rows.append([per, CLS[c], n0(s["jobs"]), d2(s["actual"]), d2(s["quoted"]), sg(s["bias"]), d2(s["mae"]), pct(s["within"]), d2(s["backlog"])])
    return table(pd.DataFrame(rows, columns=["Period, by release date", "Routing class", "Jobs", "Mean actual lead time", "Mean quoted lead time", "Mean error", "Mean absolute error",
                                             f"Within {A.WITHIN} days", "Mean brake backlog at release"]))


def t_months(m):
    rows = []
    for i, r in m.iterrows():
        note = "loaded" if r["loaded"] else "incomplete" if r["incomplete"] else ""
        rows.append([f"{i}", n0(r["jobs"]), d2(r["actual"]), d2(r[f"quoted|{A.CURRENT}"]), sg(r[f"bias|{A.CURRENT}"]), d2(r[f"mae|{A.CURRENT}"]), pct(r[f"within|{A.CURRENT}"]), d2(r["backlog"])]
                    + [f"{d2(r[f'mae|{k}'])} ({sg(r[f'bias|{k}'])})" for k in (A.CLASS, A.REC, A.REC_FIT)] + [note])
    return table(pd.DataFrame(rows, columns=["Release month", "Jobs", "Mean actual lead time", "Mean quoted lead time", "Mean error", "Mean absolute error", f"Within {A.WITHIN} days",
                                             "Mean brake backlog at release", "Class median: mean absolute error (mean error)", "Recommended quote, out of sample",
                                             f"Recommended quote, {FITTED}", "Note"]))


def t_conditions():
    summary, parts = [], ""
    for name, col in A.CONDITIONS.items():
        t, r2 = A.condition(col)
        summary.append([name, pct(r2), f"{sg(t['bias'].iloc[0])} ({t.index[0]})", f"{sg(t['bias'].iloc[-1])} ({t.index[-1]})"])
        rows = [[str(i), n0(r["jobs"]), d2(r["actual"]), d2(r["quoted"]), sg(r["bias"]), d2(r["mae"])] for i, r in t.iterrows()]
        parts += block(name, table(pd.DataFrame(rows, columns=["Band", "Jobs", "Mean actual lead time", "Mean quoted lead time", "Mean error", "Mean absolute error"])))
    head = table(pd.DataFrame(summary, columns=["Condition at release", "Variance in quote error explained alone", "Mean error, lowest band", "Mean error, highest band"]))
    return block("Each condition alone", head) + parts


def t_candidates():
    rows = []
    for k in (A.CURRENT, A.CLASS, A.REC, A.REC_FIT, A.SIZE, A.LOT):
        for per, f in A.PERIODS.items():
            s = A.score(f(A.D), k)
            rows.append([k, per, n0(s["jobs"]), sg(s["bias"]), d2(s["mae"]), pct(s["within"]), d2(s["quoted"])])
    a = table(pd.DataFrame(rows, columns=["Quote", "Period, by release date", "Jobs", "Mean error", "Mean absolute error", f"Within {A.WITHIN} days", "Mean quote"]))
    rows = []
    for k in (A.CLASS, A.REC, A.REC_FIT, A.SIZE, A.LOT):
        c = A.against_current(k)
        rows.append([k, pct(c["shorter"]), d2(c["shorter_by"]), pct(c["longer"]), "" if c["longer_by"] != c["longer_by"] else d2(c["longer_by"]), pct(c["same"])])
    b = table(pd.DataFrame(rows, columns=["Quote", "Shorter than the current quote", "Shorter by, days (mean)", "Longer", "Longer by, days (mean)", "Same"]))
    rows = []
    for lab, how, fl, key in ((A.CLASS, A.HOW, A.FLOORED, "class"), (A.REC, A.HOW, A.FLOORED, "backlog"), (A.SIZE, A.HOW, A.FLOORED, "size"), (A.LOT, A.HOW_LOT, A.FLOORED_LOT, "size")):
        vc = how[key].value_counts()
        rows.append([lab, "; ".join(f"{i}: {n0(v)} ({pct(v / len(A.D))})" for i, v in vc.items()), f"{n0(fl[key])} ({pct(fl[key] / len(A.D))})"])
    c = table(pd.DataFrame(rows, columns=["Quote", "Cell the quote was read from", "Quotes at the floor"]))
    return (block("Error by period", a) + block("Against the current quote, 2023 to 2025", b) + block("How the out-of-sample quotes were reached", c)
            + f"<p>Out of sample, each job is quoted the median lead time of non-rush jobs shipped before the first day of its release month, in its cell, rounded to whole days and never "
              f"below the 10th percentile of lead time for the routing class. A cell with fewer than {A.MIN_JOBS} earlier jobs takes the nearest brake backlog band that has them, the "
              f"deeper band first. Job size is in thirds within the routing class.</p>")


def t_commitment():
    rows = []
    for k in (A.CURRENT, A.REC, A.REC_80, A.REC_FIT, A.REC_FIT_80):
        for per in ("2023 to 2025", "Loaded months", "Ordinary months"):
            s = A.score(A.PERIODS[per](A.D), k)
            rows.append([k, per, pct(s["met"]), sg(s["bias"]), d2(s["mae"]), pct(s["within"]), d2(s["quoted"])])
    return table(pd.DataFrame(rows, columns=["Quote", "Period", "Jobs shipped within the quote", "Mean error", "Mean absolute error", f"Within {A.WITHIN} days", "Mean quote"]))


def t_size_grid():
    g = A.size_grid()
    rows = [[CLS[r["routing_class"]], r["hours"]] + [f"{n0(r[b][0])} ({n0(r[b][1])})" if r[b][0] == r[b][0] else f"({n0(r[b][1])})" for b in A.BANDS] for _, r in g.iterrows()]
    return table(pd.DataFrame(rows, columns=["Routing class", "Brake standard hours on the job"] + [f"{b.capitalize()} days" for b in A.BANDS]))


# ── quoting ─────────────────────────────────────────────────────────────────
def quoting(n, start=100):
    """The quoting section's text and appendix tables, its tables numbered from `start` until the report orders every table by first reference."""
    T = Tables(start)
    D, S = A.D, {(k, per): A.score(f(A.D), k) for k in (A.CURRENT, A.CLASS, A.REC, A.REC_FIT, A.REC_80, A.REC_FIT_80) for per, f in A.PERIODS.items()}
    every, ordinary, loaded = "2023 to 2025", "Ordinary months", "Loaded months"
    months = A.by_month()
    shown = months[~months["incomplete"]]
    grid = A.grid()
    backlog, r2_backlog = A.condition("c_backlog")
    outside, _ = A.condition("c_outside")
    r2_small = max(A.condition("c_brake")[1], A.condition("c_lot")[1])
    out_class = A.score(D[D["routing_class"] == "outside processing"])
    assert len(A.LOADED) == 4 and A.LOADED[0] == pd.Period(f"{YEAR - 1}-12") and A.LOADED[-1] == pd.Period(f"{YEAR}-03") and r2_small < 0.01
    cur, cls, rec, fit = (lambda per, k=k: S[(k, per)] for k in (A.CURRENT, A.CLASS, A.REC, A.REC_FIT))
    assert rec(loaded)["mae"] > cur(loaded)["mae"] > fit(loaded)["mae"] and cls(ordinary)["mae"] < cur(ordinary)["mae"]

    T.add("periods", "The current quote against actual lead time by period and routing class, non-rush jobs released 2023 to 2025", t_periods()
          + f"<p>{n0(len(D))} non-rush jobs released from January 2023 and shipped by December {YEAR}. Left out: {n0(len(A.EARLIER))} released before January 2023, which the record holds "
            f"only where they shipped late, and {n0(int(A.HISTORY['inside'].sum()))} lines customer service accepted inside the quote. Error is the actual lead time less the quoted lead "
            f"time in whole working days; a loaded month has a mean brake backlog at release of {A.LOADED_AT:g} days or more.</p>")
    T.add("months", "Quote error by release month: the current quote, the class median and the recommended quote", t_months(months)
          + f"<p>{join_and([month(m) for m in A.INCOMPLETE])} is incomplete: most of the jobs released in it had not shipped when the record closes, so it holds only its faster jobs.</p>")
    T.add("conditions", "Quote error by condition at release, non-rush jobs released 2023 to 2025", t_conditions())
    T.add("candidates", "Every quote tested: error by period, change from the current quote, and how each quote was reached", t_candidates())
    T.add("commitment", "The recommended quote at the median and at the 80th percentile: jobs shipped within the quote and error", t_commitment())
    T.add("size", "The quote grid with brake standard hours in thirds, fitted on 2023 to 2025: median lead time (jobs in the cell)", t_size_grid())

    repeat = grid.loc["repeat part"]
    b = [f"<p>The shop's quote misses the lead time a job actually takes by {d1(cur(every)['mae'])} working days on average, and in opposite directions: in ordinary months it is "
         f"{d1(-cur(ordinary)['bias'])} days too long, with the median repeat part shipping in {n0(repeat['median'])} days against a {n0(repeat['standard'])}-day standard, and in the "
         f"four months of the {YEAR - 1} year-end build it was {d1(cur(loaded)['bias'])} days too short. A quote set from what jobs of the same routing class actually take cuts the miss "
         f"in ordinary months from {d1(cur(ordinary)['mae'])} to {d1(cls(ordinary)['mae'])} days. Adding the brake backlog at release lets the quote lengthen when the brakes load up. "
         f"The record could teach that only once it held a build, so out of sample it would not have helped in {YEAR - 1}; {FITTED}, it misses by {d1(fit(loaded)['mae'])} days in the "
         f"build against {d1(cur(loaded)['mae'])} for the current quote. {T.see('periods')}</p>"]

    b.append(f"<h3 id='f{n}_1'>How accurate the quote is</h3>")
    short = shown[shown[f"bias|{A.CURRENT}"] > 0.5]
    assert len(short) == 4 and short.index[0] == pd.Period(f"{YEAR - 1}-11") and short.index[-1] == pd.Period(f"{YEAR}-02")
    b.append(f"<p>The quote barely moves while lead time swings with the brake backlog. The mean quote stays between {d1(shown[f'quoted|{A.CURRENT}'].min())} and "
             f"{d1(shown[f'quoted|{A.CURRENT}'].max())} days while the mean lead time runs from {d1(shown['actual'].min())} to {d1(shown['actual'].max())}; the quote is too long in "
             f"{len(shown[shown[f'bias|{A.CURRENT}'] < -0.5])} of the {len(shown)} months and too short from {month(short.index[0])} to {month(short.index[-1])}. {T.see('months')}</p>")
    b.append(titled(fig_quote_and_actual(shown), "Quoted and Actual Lead Time by Release Month, Non-rush Jobs, 2023 to 2025"))

    b.append(f"<h3 id='f{n}_2'>When the quote misses</h3>")
    nov = months.loc[pd.Period(f"{YEAR - 1}-11")]
    deep = backlog["bias"].iloc[3:]
    b.append(f"<p>Brake backlog at release explains {pct(r2_backlog, 0)} of the error. The quote runs {d1(-backlog['bias'].iloc[0])} days long below 1 day of backlog and "
             f"{d1(deep.min())} to {d1(deep.max())} days short above 3, across all three years, not only in the build. Outside processing quotes run {d1(-out_class['bias'])} days long: "
             f"the median job takes {n0(grid.loc['outside processing', 'median'])} days against the {n0(grid.loc['outside processing', 'standard'])}-day standard. Job size and lot size "
             f"explain under 1%. The backlog at release sees a build late: jobs released in {month(nov.name)} ran {d1(nov[f'bias|{A.CURRENT}'])} days over their quotes at "
             f"{d1(nov['backlog'])} days of backlog. {T.see('conditions')}</p>")
    b.append(titled(fig_conditions(backlog, outside), "Quote Error by Condition at Release, Non-rush Jobs, 2023 to 2025"))

    b.append(f"<h3 id='f{n}_3'>A more accurate quote</h3>")
    co, cf = A.against_current(A.REC), A.against_current(A.REC_FIT)
    assert int((A.HISTORY[A.HISTORY["ship_date"] < f"{YEAR - 1}-12-01"]["brake_backlog_days"] >= 3).sum()) == 0
    b.append(f"<p>The recommended quote is the median lead time of jobs of the same routing class at the same brake backlog at release, refitted monthly from the jobs shipped; "
             f"the table below gives it as {FITTED}. Fitted that way, it misses by {d1(fit(ordinary)['mae'])} days in ordinary months and {d1(fit(loaded)['mae'])} in the build, "
             f"against {d1(cur(ordinary)['mae'])} and {d1(cur(loaded)['mae'])} for today's quote, and quotes shorter than today on {pct(cf['shorter'], 0)} of jobs, by "
             f"{d1(cf['shorter_by'])} days on average, and longer on {pct(cf['longer'], 0)}, by {d1(cf['longer_by'])}. Applied month by month as the shop would have had it at the "
             f"time, it does as well in ordinary months ({d1(rec(ordinary)['mae'])} days) but not in the {YEAR - 1} build ({d1(rec(loaded)['mae'])}), because no earlier job had "
             f"shipped from a backlog above 3 days. A median quote is met by about half of jobs; at the 80th percentile of the same cell the commitment is met on "
             f"{pct(S[(A.REC_FIT_80, every)]['met'], 0)} of jobs, against {pct(cur(every)['met'], 0)} for today's quote. {T.see('candidates', 'commitment', 'size')}</p>")
    b.append(chart("Quoted Lead Time by Routing Class and Brake Backlog at Release, Working Days, Fitted on 2023 to 2025", t_grid(grid)))
    b.append(titled(fig_error_by_month(shown), "Mean Absolute Error of the Quote by Release Month, Current Quote Against the Recommended Quote, 2023 to 2025"))
    b.append(titled(fig_ordinary_and_loaded(S), "Quote Error in Ordinary and Loaded Months, Current Quote Against Each Candidate"))
    b.append("<p>Quote from the routing class and the brake backlog at release, from the jobs shipped and refitted monthly, and commit to the customer at the 80th percentile of the "
             "same quote.</p>")
    return "\n".join(b), T.appendix()


# ── early warning ───────────────────────────────────────────────────────────
def early_warning(n, start=200):
    T = Tables(start)
    T.add("bands", "Late rate by brake backlog at release", L.t_bands())
    T.add("threshold", f"Jobs released above {LA.BACKLOG_THRESHOLD:.0f} days of brake backlog", L.t_threshold())
    T.add("late", "Jobs released late", L.t_short())
    T.add("defs", "Weekly indicators and definitions", table(pd.DataFrame(L.DEFS, columns=["Indicator", "Definition", "Adverse direction"])))
    T.add("lags_event", "Correlation with on-time delivery by weeks of lead, ordinary weeks", L.t_lags(L.LE))
    T.add("lags_all", "Correlation with on-time delivery by weeks of lead, all weeks", L.t_lags(L.LA))
    T.add("declines", "Declines in on-time delivery", L.t_declines())
    T.add("lead_by", "Weeks each indicator moved before each decline", L.t_lead_by_decline())

    b = ["<p>Two flags at release mark the jobs most likely to ship late, and one weekly measure warns of a decline in on-time delivery a week ahead.</p>"]
    b.append(f"<h3 id='f{n}_1'>Flags at release</h3>")
    ty, tq, sr = L.THR.loc[L.PY], L.THR.loc[L.PR], L.SHORT.loc[L.PR]
    assert tq["late_jobs_above"] == 0 and tq["share_of_all_jobs_above"] == 0
    b.append(f"<p>Brake backlog flags jobs in a build, and a short due date flags them in an ordinary quarter. Jobs released above "
             f"{LA.BACKLOG_THRESHOLD:.0f} days of brake backlog are {pct(ty['share_of_all_jobs_above'], 0)} of jobs released in {YEAR} and "
             f"{pct(ty['share_of_late_jobs_above'], 0)} of late jobs, a late rate of {pct(ty['late_rate_above'], 0)} against {pct(ty['late_rate_below'], 0)}; no job "
             f"released in {RT} crossed it. Jobs released late are {pct(sr['share_of_jobs'], 0)} of jobs released in {RT} and {pct(sr['share_of_late_jobs'], 0)} of "
             f"late jobs, a late rate of {pct(sr['late_rate_inside'])} against {pct(sr['late_rate_other'])}. Each late release should be a decision: flag the job as a "
             f"rush, with a named approver, and count these releases weekly. {T.see('bands', 'threshold', 'late')}</p>")
    b.append(titled(L.fig_backlog(), "Late Rate by Brake Backlog at Release"))

    b.append(f"<h3 id='f{n}_2'>Weekly indicators</h3>")
    e, o, lt = L.CE.loc[L.OTS], L.DL.loc[L.OTS], L.LT
    others = [x for x in L.ABOVE_E if x != L.OTS]
    assert e["best_lead_weeks"] == 1 and L.OTS in L.ABOVE_E and o["preceded"] == len(L.DEC) and min(o["shuffled_p"], o["shifted_p"]) > 0.05
    assert others == [L.OUTSIDE], others
    laser = lt.loc[L.LASER].dropna()
    la = L.DL.loc[L.LASER]
    assert min(la["shuffled_p"], la["shifted_p"]) > 0.05
    when = lambda t: f"{t:%B %Y}"
    b.append(f"<p>The on-time start rate leads on-time delivery by one week in ordinary weeks (correlation {e['r_best_lead']:.2f}, against chance levels of "
             f"{e['shuffled_p95']:.2f} and {e['shifted_p95']:.2f}). It moved {join_and([f'{x:.0f}' for x in lt.loc[L.OTS]])} weeks before the "
             f"{L.word(len(L.DEC))} declines in on-time delivery, which cannot be told apart from chance ({d1(o['shuffled_expected'])} and {d1(o['shifted_expected'])} "
             f"expected). Jobs waiting at the lasers moved "
             f"{join_and([f'{v:.0f} weeks before the {when(pd.Timestamp(k))} decline' for k, v in laser.items()])}, {len(laser)} of {len(L.DEC)} and no better than "
             f"chance. Outside-processing receipts on time clear both chance levels only at a {L.CE.loc[L.OUTSIDE, 'best_lead_weeks']}-week lead (correlation "
             f"{L.CE.loc[L.OUTSIDE, 'r_best_lead']:.2f}); no other measure leads in ordinary weeks. "
             f"{T.see('defs', 'lags_event', 'lags_all', 'declines', 'lead_by')}</p>")
    b.append(f"<p>Flag at release every job above {LA.BACKLOG_THRESHOLD:.0f} days of brake backlog and every job released late, and review the on-time start rate weekly.</p>")
    return "\n".join(b).replace(L.REST, RT), T.appendix().replace(L.REST, RT)
