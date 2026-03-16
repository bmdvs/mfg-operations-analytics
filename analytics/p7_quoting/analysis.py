"""P7 lead-time quoting and quote analytics: the measures, read from the marts."""
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from analytics.db import q

YEAR = 2025
PCTL = 0.8
MIN_JOBS = 20
EVENT_QUARTERS = ("2024Q4", "2025Q1")
BANDS = [-1, 2, 3, 5, 99]
BAND_LABELS = ["under 2", "2 to 3", "3 to 5", "over 5"]
CLASSES = ["repeat part", "new part", "outside processing"]


def load():
    j = q("""select l.*, c.brake_backlog_days, c.promised_inside_standard, a.released_late_days
             from marts.mart_job_lead_time l
             join marts.mart_job_release_conditions c using (job_id)
             left join (select job_id, sum(attributed_days) as released_late_days from marts.mart_p2_attribution where cause = 'released late' group by 1) a
                 using (job_id)
             where l.ship_date is not null order by l.job_id""")
    for c in ("release_date", "ship_date", "due_date"):
        j[c] = pd.to_datetime(j[c])
    j["rush_flag"] = j["rush_flag"].fillna(False).astype(bool)
    j["late"] = ~j["on_time"].astype(bool)
    j["band"] = pd.cut(j["brake_backlog_days"], BANDS, labels=BAND_LABELS)
    j["ship_q"] = j["ship_date"].dt.to_period("Q").astype(str)
    j["promise"] = np.where(j["rush_flag"], "rush", np.where(j["promised_lead_wd"] < j["quoted_lead_days"], "short promise, not rush", "standard promise"))
    j["released_late_days"] = j["released_late_days"].fillna(0.0)
    qt = q("select * from marts.mart_quotes where rfq_year between 2023 and 2025 order by quote_id")
    for c in ("won", "slow_turnaround", "new_part", "outside_processing", "rush_rfq", "key_account"):
        qt[c] = qt[c].astype(bool)
    qt["slow"], qt["w"] = qt["slow_turnaround"].astype(int), qt["won"].astype(int)
    qt["f_new"], qt["f_bend"], qt["f_op"], qt["f_rush"] = qt["new_part"].astype(int), (qt["bend_count"] >= 8).astype(int), qt["outside_processing"].astype(int), \
        qt["rush_rfq"].astype(int)
    return dict(j=j, qt=qt, batch=j["export_batch_id"].iloc[0])


def periods(j):
    y = j[j["ship_date"].dt.year == YEAR]
    return ((f"{YEAR}", y), (f"{YEAR} Q2 to Q4", y[y["ship_date"].dt.quarter >= 2]))


# ── the fixed quote ─────────────────────────────────────────────────────────
def fixed_quote(D):
    """By routing class: where the fixed quote sits in the lead-time distribution, and delivery against the promise."""
    rows = []
    for name, d in periods(D["j"]):
        for c in CLASSES + ["all"]:
            g = d if c == "all" else d[d["routing_class"] == c]
            std = g[g["promise"] == "standard promise"]
            rows.append(dict(period=name, routing_class=c, jobs=len(g), quoted=g["quoted_lead_days"].mean(), percentile_of_quote=(g["wip_days"] <= g["quoted_lead_days"]).mean(),
                             median=g["wip_days"].median(), p80=g["wip_days"].quantile(0.8), p90=g["wip_days"].quantile(0.9), on_time=g["on_time"].mean(),
                             standard_promise_jobs=len(std), standard_promise_quote_met=(std["wip_days"] <= std["quoted_lead_days"]).mean(),
                             standard_promise_on_time=std["on_time"].mean()))
    return pd.DataFrame(rows)


def by_family(D):
    rows = []
    for name, d in periods(D["j"]):
        for (f, c), g in d.groupby(["family", "routing_class"]):
            rows.append(dict(period=name, family=f, routing_class=c, jobs=len(g), promised_mean=g["promised_lead_wd"].mean(), actual_median=g["wip_days"].median(),
                             actual_p80=g["wip_days"].quantile(0.8), quote_met=(g["wip_days"] <= g["quoted_lead_days"]).mean(), on_time=g["on_time"].mean()))
    return pd.DataFrame(rows)


def promise_types(D):
    """Rush lines, non-rush lines promised inside the standard lead time, and standard promises: delivery and the lateness they carry."""
    rows = []
    for name, d in periods(D["j"]):
        for t in ("rush", "short promise, not rush", "standard promise"):
            g = d[d["promise"] == t]
            rows.append(dict(period=name, promise=t, jobs=len(g), share_of_jobs=len(g) / len(d), promised_mean=g["promised_lead_wd"].mean(),
                             actual_median=g["wip_days"].median(), on_time=g["on_time"].mean(), late_jobs=int(g["late"].sum()),
                             share_of_late_jobs=g["late"].sum() / d["late"].sum(), days_late=g["days_late"].sum(),
                             share_of_days_late=g["days_late"].sum() / d["days_late"].sum(), released_late_days=g["released_late_days"].sum(),
                             quote_met=(g["wip_days"] <= g["quoted_lead_days"]).mean()))
    return pd.DataFrame(rows)


# ── the load-aware quote ────────────────────────────────────────────────────
RULES = [
    ("Routing class, trailing 13 weeks", dict(window=91, band=False)),
    ("Routing class, trailing 8 weeks", dict(window=56, band=False)),
    ("Routing class, ordinary quarters", dict(window="ordinary", band=False)),
    ("Routing class and brake backlog, trailing 13 weeks", dict(window=91, band=True)),
    ("Routing class and brake backlog, trailing 8 weeks", dict(window=56, band=True)),
    ("Routing class and brake backlog, ordinary quarters", dict(window="ordinary", band=True)),
    ("Routing class and brake backlog, all earlier jobs", dict(window="all", band=True)),
]


def quote_rule(D, window, band):
    """For each non-rush job shipped in the report year, the 80th-percentile lead time of earlier jobs of its routing class (and brake backlog band at
    release), rounded up: jobs shipped in the window before its release date. With fewer than MIN_JOBS in the band the routing class is used."""
    j = D["j"]
    out = pd.Series(np.nan, index=j.index)
    fallback = pd.Series(False, index=j.index)
    target = j[(j["ship_date"].dt.year == YEAR) & ~j["rush_flag"]]
    for cls, g in j.groupby("routing_class"):
        g = g.sort_values("ship_date")
        ship, lead, bnd = g["ship_date"].to_numpy(), g["wip_days"].to_numpy(dtype=float), g["band"].astype(str).to_numpy()
        ordinary = ~g["ship_q"].isin(EVENT_QUARTERS).to_numpy()
        qstart = g["ship_date"].dt.to_period("Q").dt.start_time.to_numpy()
        for idx, r in target[target["routing_class"] == cls].iterrows():
            rel = np.datetime64(r["release_date"])
            before = ship < rel
            if window == "ordinary":
                pool = before & ordinary & (ship < np.datetime64(pd.Timestamp(rel).to_period("Q").start_time))
            elif window == "all":
                pool = before
            else:
                pool = before & (ship >= rel - np.timedelta64(window, "D"))
            use = pool & (bnd == str(r["band"])) if band else pool
            if band and use.sum() < MIN_JOBS:
                use, fallback[idx] = pool, True
            if use.sum() >= MIN_JOBS:
                out[idx] = np.ceil(np.quantile(lead[use], PCTL))
    return out, fallback


def quote_rules(D):
    j = D["j"]
    rows, quotes = [], {}
    for name, kw in RULES:
        qv, fb = quote_rule(D, **kw)
        quotes[name] = qv
        for pname, d in periods(j):
            t = d[~d["rush_flag"]]
            x = qv.reindex(t.index)
            ok = x.notna()
            t, x = t[ok], x[ok]
            rows.append(dict(rule=name, period=pname, jobs=len(t), not_quoted=int((~ok).sum()), met=(t["wip_days"] <= x).mean(),
                             fixed_met=(t["wip_days"] <= t["quoted_lead_days"]).mean(), longer=(x > t["quoted_lead_days"]).mean(),
                             shorter=(x < t["quoted_lead_days"]).mean(), mean_quote=x.mean(), mean_fixed=t["quoted_lead_days"].mean(),
                             median_longer_by=(x - t["quoted_lead_days"])[x > t["quoted_lead_days"]].median(), band_fallback=fb.reindex(t.index).mean()))
    return pd.DataFrame(rows), quotes


def quote_by_quarter(D, quotes, rule):
    j = D["j"]
    t = j[(j["ship_date"].dt.year == YEAR) & ~j["rush_flag"]].copy()
    t["quote"] = quotes[rule].reindex(t.index)
    t = t[t["quote"].notna()]
    t["rq"] = t["release_date"].dt.to_period("Q").astype(str)
    g = t.groupby(["rq", "routing_class"])
    return g.apply(lambda d: pd.Series(dict(jobs=len(d), mean_quote=d["quote"].mean(), met=(d["wip_days"] <= d["quote"]).mean(),
                                            fixed_met=(d["wip_days"] <= d["quoted_lead_days"]).mean(), longer=(d["quote"] > d["quoted_lead_days"]).mean()))).reset_index()


def quote_table(D):
    """The 80th-percentile lead time by routing class and brake backlog band at release: ordinary quarters, and all jobs shipped through the report year."""
    j = D["j"]
    rows = []
    for c in CLASSES:
        for b in BAND_LABELS:
            g = j[(j["routing_class"] == c) & (j["band"] == b)]
            o = g[~g["ship_q"].isin(EVENT_QUARTERS)]
            rows.append(dict(routing_class=c, band=b, jobs=len(g), p80=np.ceil(g["wip_days"].quantile(PCTL)) if len(g) >= MIN_JOBS else np.nan,
                             jobs_ordinary=len(o), p80_ordinary=np.ceil(o["wip_days"].quantile(PCTL)) if len(o) >= MIN_JOBS else np.nan,
                             fixed=g["quoted_lead_days"].iloc[0] if len(g) else np.nan))
    return pd.DataFrame(rows)


def table_quote(D):
    """The quote table applied to every non-rush job shipped in the report year: the later of the table value for its routing class and brake backlog
    band at release and the fixed quote."""
    j = D["j"]
    t = quote_table(D).set_index(["routing_class", "band"])["p80"]
    target = j[(j["ship_date"].dt.year == YEAR) & ~j["rush_flag"]]
    v = pd.Series([t.get((c, str(b_)), np.nan) for c, b_ in zip(target["routing_class"], target["band"])], index=target.index, dtype=float)
    return np.maximum(v.fillna(target["quoted_lead_days"]), target["quoted_lead_days"]).reindex(j.index)


def floored(D, quote):
    j = D["j"]
    return np.maximum(quote, j["quoted_lead_days"]).where(quote.notna())


def score(D, quote):
    """Hit rate of a quote on non-rush jobs shipped in the report year: whole year, Q2 to Q4, and by release quarter."""
    j = D["j"]
    t = j[(j["ship_date"].dt.year == YEAR) & ~j["rush_flag"]].copy()
    t["quote"] = quote.reindex(t.index)
    t = t[t["quote"].notna()]
    t["rq"] = t["release_date"].dt.to_period("Q").astype(str)

    def m(d):
        return dict(jobs=len(d), met=(d["wip_days"] <= d["quote"]).mean(), longer=(d["quote"] > d["quoted_lead_days"]).mean(), mean_quote=d["quote"].mean(),
                    median_longer_by=(d["quote"] - d["quoted_lead_days"])[d["quote"] > d["quoted_lead_days"]].median())
    first = t["rq"].min()
    out = [dict(group=f"{YEAR}", **m(t)), dict(group=f"{YEAR} Q2 to Q4", **m(t[t["ship_date"].dt.quarter >= 2])),
           dict(group=f"{YEAR}, released from {YEAR} Q1", **m(t[t["rq"] != first]))]
    out += [dict(group=f"released {k[:4]} {k[4:]}", **m(g)) for k, g in t.groupby("rq")]
    out += [dict(group=f"released {k[:4]} {k[4:]}, {c}", **m(g)) for (k, c), g in t.groupby(["rq", "routing_class"])]
    return pd.DataFrame(out)


def three_rules(D):
    j = D["j"]
    trailing, _ = quote_rule(D, 91, False)
    earlier, _ = quote_rule(D, "all", True)
    rules = {"Fixed quote": j["quoted_lead_days"].astype(float).where((j["ship_date"].dt.year == YEAR) & ~j["rush_flag"]),
             "Quote table, never below the fixed quote": table_quote(D),
             "Routing class, trailing 13 weeks": trailing,
             "Routing class and brake backlog, all earlier jobs, never below the fixed quote": floored(D, earlier)}
    return {k: score(D, v) for k, v in rules.items()}, rules


# ── win rate ────────────────────────────────────────────────────────────────
def turnaround(D):
    qt = D["qt"]
    band = pd.cut(qt["turnaround_days"], [-1, 1, 3, 5, 999], labels=["0 to 1", "2 to 3", "4 to 5", "6 and over"])
    by_band = qt.groupby(band, observed=True).agg(quotes=("w", "size"), win_rate=("w", "mean"), new_part=("f_new", "mean"), bends_8=("f_bend", "mean"),
                                                  outside=("f_op", "mean")).reset_index(names="turnaround")
    fast, slow = qt.loc[qt["slow"] == 0, "w"].mean(), qt.loc[qt["slow"] == 1, "w"].mean()
    m = smf.logit("w ~ slow + f_new + f_bend + f_op", qt).fit(disp=0)
    p0, p1 = m.predict(qt.assign(slow=0)), m.predict(qt.assign(slow=1))
    rng = np.random.default_rng(7)
    boot = []
    for _ in range(200):
        s = qt.iloc[rng.integers(0, len(qt), len(qt))]
        mb = smf.logit("w ~ slow + f_new + f_bend + f_op", s).fit(disp=0)
        boot.append((mb.predict(s.assign(slow=0)) - mb.predict(s.assign(slow=1))).mean())
    strata = qt.groupby(["f_new", "f_bend", "f_op", "slow"])["w"].agg(["mean", "size"]).unstack("slow")
    strata.columns = ["win_fast", "win_slow", "quotes_fast", "quotes_slow"]
    strata["gap"] = strata["win_fast"] - strata["win_slow"]
    wgt = strata["quotes_fast"] + strata["quotes_slow"]
    summary = dict(quotes=len(qt), win_rate=qt["w"].mean(), fast=fast, slow=slow, quotes_fast=int((qt["slow"] == 0).sum()), quotes_slow=int(qt["slow"].sum()),
                   raw_gap=fast - slow, adjusted_gap=float((p0 - p1).mean()), adjusted_low=float(np.quantile(boot, 0.025)), adjusted_high=float(np.quantile(boot, 0.975)),
                   stratified_gap=float((strata["gap"] * wgt).sum() / wgt.sum()), adjusted_fast=float(p0.mean()), adjusted_slow=float(p1.mean()),
                   coefficients=m.params.to_dict())
    return summary, by_band, strata.reset_index()


def adjusted_groups(D, col, top=None):
    """Win rate by group, and adjusted for RFQ complexity: the overall rate plus the group's rate less the rate expected from its mix of new parts,
    parts with 8 or more bends, outside processing and rush RFQs."""
    qt = D["qt"].copy()
    m = smf.logit("w ~ f_new + f_bend + f_op + f_rush", qt).fit(disp=0)
    qt["expected"] = m.predict(qt)
    g = qt.groupby(col).agg(quotes=("w", "size"), win_rate=("w", "mean"), expected=("expected", "mean"), turnaround_median=("turnaround_days", "median"),
                            slow=("slow", "mean"), new_part=("f_new", "mean")).reset_index()
    g["adjusted"] = qt["w"].mean() + g["win_rate"] - g["expected"]
    g = g.sort_values("quotes", ascending=False)
    return g.head(top) if top else g


def rush_rfq(D):
    qt = D["qt"]
    r = qt[qt["rush_rfq"]].copy()
    r["band"] = pd.cut(r["quoted_lead_time_days"], [0, 5, 8, 11, 40], labels=["5 or fewer", "6 to 8", "9 to 11", "12 or more"])
    return r.groupby("band", observed=True).agg(quotes=("w", "size"), win_rate=("w", "mean"), lost_to_lead_time=("lost_reason", lambda s: (s == "lead time").mean())).reset_index()


def estimators(D):
    qt = D["qt"]
    g = qt.groupby(["estimator", "rfq_year"]).agg(quotes=("w", "size"), turnaround_median=("turnaround_days", "median"), turnaround_mean=("turnaround_days", "mean"),
                                                 slow=("slow", "mean"), win_rate=("w", "mean"), new_part=("f_new", "mean")).reset_index()
    return g


def lost_reasons(D):
    qt = D["qt"]
    lost = qt[qt["status"] == "lost"]
    g = lost.assign(reason=lost["lost_reason"].fillna("blank")).groupby(["reason", "slow"]).size().unstack("slow").fillna(0)
    g.columns = ["turnaround 3 days or less", "turnaround over 3 days"]
    g["all"] = g.sum(axis=1)
    return g.sort_values("all", ascending=False).reset_index(), qt["status"].value_counts()
