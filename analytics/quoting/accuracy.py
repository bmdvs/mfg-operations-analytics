"""How accurately the quote predicts the lead time a job takes, and a quote from the routing class and the brake backlog at release.

The population is non-rush jobs released from January 2023 and shipped by the end of the record, less the lines customer service accepted inside the
quote. Error is the actual lead time less the quoted lead time in whole working days: positive, the quote was too short. The floor is as recorded.
"""
import numpy as np
import pandas as pd

from analytics.db import q

YEAR = 2025
FIRST_RELEASE = "2023-01-01"           # jobs released earlier are in the record only when they shipped late in it
CLASSES = ["repeat part", "new part", "outside processing"]
EDGES, BANDS = [-np.inf, 1, 2, 3, 5, np.inf], ["under 1", "1 to 2", "2 to 3", "3 to 5", "over 5"]
LOADED_AT = 2.5                        # a loaded month: mean brake backlog at release of this many days or more
MIN_JOBS = 30                          # a cell with fewer earlier jobs takes the nearest brake backlog band that has them, the deeper band first
WITHIN = 2                             # working days either side of the quote
ORDER = {b: k for k, b in enumerate(BANDS)}


def load():
    j = q("""select l.job_id, l.routing_class, l.qty, l.standard_lead_days, l.quoted_lead_days, l.rush_flag, l.release_date, l.ship_date, l.wip_days, c.brake_backlog_days,
                    ol.order_date, ol.original_promised_date, o.operations, o.brake_std, o.outside
             from marts.mart_job_lead_time l join marts.mart_job_release_conditions c using (job_id)
             join staging.stg_erp__jobs sj using (job_id) join staging.stg_erp__order_lines ol on ol.order_line_id = sj.order_line_id
             join (select job_id, count(*) as operations, sum(case when work_center = 'press_brake' then setup_std + run_std * qty else 0 end) as brake_std,
                          max((work_center = 'outside_processing')::int) as outside from staging.stg_erp__job_operations group by 1) o using (job_id)
             where l.ship_date is not null and not coalesce(l.rush_flag, false) order by l.job_id""")
    for c in ("release_date", "ship_date", "order_date", "original_promised_date"):
        j[c] = pd.to_datetime(j[c])
    # weekday working days, as due dates are set; a line accepted inside the quote was not quoted by the shop
    cal = pd.to_datetime(q("select distinct calendar_date from staging.stg_erp__work_center_calendar where not saturday order by 1")["calendar_date"])
    before = pd.bdate_range("2022-06-01", cal.min() - pd.Timedelta(days=1))
    before = before[~((before.month == 12) & (before.day >= 24)) & ~before.isin(pd.to_datetime(["2022-07-04", "2022-09-05", "2022-11-24", "2022-11-25", "2023-01-02"]))]
    days = before.append(pd.DatetimeIndex(cal))
    every = pd.date_range(days.min(), days.max())
    index = pd.Series(np.searchsorted(days.values, every.values), index=every)
    j["inside"] = (j["original_promised_date"].map(index) - j["order_date"].map(index)) < j["quoted_lead_days"]
    j["lead"], j["quote"] = j["wip_days"].astype(float), j["quoted_lead_days"].astype(float)
    j["band"] = pd.cut(j["brake_backlog_days"], EDGES, labels=BANDS, right=False).astype(str)
    j["month"] = j["release_date"].dt.to_period("M")
    return j


ALL = load()
EARLIER = ALL[ALL["release_date"] < FIRST_RELEASE]
HISTORY = ALL[ALL["release_date"] >= FIRST_RELEASE].copy()             # what a quote is fitted on
D = HISTORY[~HISTORY["inside"]].copy()                                 # the jobs whose quotes are scored
D["error"] = D["lead"] - D["quote"]
_backlog = D.groupby("month")["brake_backlog_days"].mean()
LOADED = sorted(_backlog[_backlog >= LOADED_AT].index)
D["loaded"] = D["month"].isin(LOADED)
# release months whose jobs had not all shipped when the record closes: only their faster jobs are in it
_open = q(f"select date_trunc('month', release_date) as m, avg((ship_date is null)::int) as open from staging.stg_erp__jobs where release_date >= '{FIRST_RELEASE}' group by 1")
INCOMPLETE = sorted(pd.Period(m, "M") for m, s in zip(_open["m"], _open["open"]) if s > 0.5)


def fit(pctl=0.5, size=None):
    """Each job's quote from the non-rush jobs shipped before the first day of its release month: the class median, and the routing class by brake backlog
    band (and by thirds of a job-size measure when one is given), never below the 10th percentile of the class. Returns the quotes and how each was reached."""
    res = {k: pd.Series(np.nan, index=D.index) for k in ("class", "backlog", "size")}
    how = {k: pd.Series("", index=D.index) for k in res}
    floored = {k: 0 for k in res}
    for m, d in D.groupby("month"):
        h = HISTORY[HISTORY["ship_date"] < m.to_timestamp()]
        for cls in CLASSES:
            hc, dc = h[h["routing_class"] == cls], d[d["routing_class"] == cls]
            if dc.empty:
                continue
            if len(hc) < MIN_JOBS:
                for k in res:
                    res[k][dc.index], how[k][dc.index] = float(dc["standard_lead_days"].iloc[0]), "class standard (no history)"
                continue
            floor, base = float(np.floor(hc["lead"].quantile(0.10))), float(np.round(hc["lead"].quantile(pctl)))
            res["class"][dc.index], how["class"][dc.index] = max(base, floor), "class"
            by = {b: hc[hc["band"] == b]["lead"] for b in BANDS}
            if size:
                cuts = hc[size].quantile([1 / 3, 2 / 3]).to_numpy()
                hs = np.searchsorted(cuts, hc[size].to_numpy(), side="right")
            for b, db in dc.groupby("band"):
                k0 = ORDER[b]
                near = [k0] + [x for step in range(1, len(BANDS)) for x in (k0 + step, k0 - step) if 0 <= x < len(BANDS)]
                use = next((x for x in near if len(by[BANDS[x]]) >= MIN_JOBS), None)
                v, tag = (base, "class (no band with enough jobs)") if use is None else (float(np.round(by[BANDS[use]].quantile(pctl))), "own band" if use == k0 else "nearest band")
                res["backlog"][db.index], how["backlog"][db.index] = max(v, floor), tag
                if size:
                    ds = np.searchsorted(cuts, db[size].to_numpy(), side="right")
                    for s_ in range(3):
                        idx = db.index[ds == s_]
                        cell = hc[(hc["band"] == b).to_numpy() & (hs == s_)]["lead"]
                        if len(idx) and len(cell) >= MIN_JOBS:
                            res["size"][idx], how["size"][idx] = max(float(np.round(cell.quantile(pctl))), floor), "own cell"
                        elif len(idx):
                            res["size"][idx], how["size"][idx] = max(v, floor), "backlog band only"
            for k in res:
                floored[k] += int((res[k][dc.index] == floor).sum())
    return res, how, floored


def grid(pctl=0.5):
    """The quote by routing class and brake backlog band fitted on every job of the history, with the class standard, median and floor."""
    rows = []
    for cls in CLASSES:
        hc = HISTORY[HISTORY["routing_class"] == cls]
        floor = float(np.floor(hc["lead"].quantile(0.10)))
        row = dict(routing_class=cls, standard=float(hc["standard_lead_days"].iloc[0]), median=float(np.round(hc["lead"].median())), floor=floor)
        for b in BANDS:
            x = hc[hc["band"] == b]["lead"]
            row[b], row[f"jobs {b}"] = max(float(np.round(x.quantile(pctl))), floor), len(x)
        rows.append(row)
    return pd.DataFrame(rows).set_index("routing_class")


def fitted(pctl=0.5):
    """The grid's quote for each scored job: fitted on 2023 to 2025, so each job is in its own history."""
    g = grid(pctl)
    return pd.Series([g.loc[c, b] for c, b in zip(D["routing_class"], D["band"])], index=D.index)


_res, HOW, FLOORED = fit(size="brake_std")
_lot, HOW_LOT, FLOORED_LOT = fit(size="qty")
_p80, _, _ = fit(0.8)
CURRENT, CLASS, REC, REC_FIT, SIZE, LOT = ("Current quote", "Class median", "Class and brake backlog, out of sample", "Class and brake backlog, fitted on 2023 to 2025",
                                           "Class, brake backlog and brake standard hours, out of sample", "Class, brake backlog and lot size, out of sample")
REC_80, REC_FIT_80 = "Class and brake backlog at the 80th percentile, out of sample", "Class and brake backlog at the 80th percentile, fitted on 2023 to 2025"
QUOTES = {CURRENT: D["quote"], CLASS: _res["class"], REC: _res["backlog"], REC_FIT: fitted(), SIZE: _res["size"], LOT: _lot["size"], REC_80: _p80["backlog"], REC_FIT_80: fitted(0.8)}
for _k, _v in QUOTES.items():
    D[_k] = _v

PERIODS = {"2023 to 2025": lambda d: d, "2023": lambda d: d[d["release_date"].dt.year == 2023], "2024": lambda d: d[d["release_date"].dt.year == 2024],
           f"{YEAR}": lambda d: d[d["release_date"].dt.year == YEAR], f"{YEAR} Q2-Q4": lambda d: d[(d["release_date"].dt.year == YEAR) & (d["release_date"].dt.quarter >= 2)],
           "Loaded months": lambda d: d[d["loaded"]], "Ordinary months": lambda d: d[~d["loaded"]]}


def score(d, quote=CURRENT):
    """Mean error, mean absolute error, the share within two days and the share shipped within the quote."""
    e = d["lead"] - d[quote]
    return dict(jobs=len(d), actual=float(d["lead"].mean()), quoted=float(d[quote].mean()), bias=float(e.mean()), mae=float(e.abs().mean()),
                within=float((e.abs() <= WITHIN).mean()), met=float((e <= 0).mean()), backlog=float(d["brake_backlog_days"].mean()))


def by_month(quotes=(CURRENT, CLASS, REC, REC_FIT)):
    rows = []
    for m, d in D.groupby("month"):
        row = dict(month=m, jobs=len(d), actual=float(d["lead"].mean()), backlog=float(d["brake_backlog_days"].mean()), loaded=m in LOADED, incomplete=m in INCOMPLETE)
        for k in quotes:
            s = score(d, k)
            row.update({f"quoted|{k}": s["quoted"], f"bias|{k}": s["bias"], f"mae|{k}": s["mae"], f"within|{k}": s["within"]})
        rows.append(row)
    return pd.DataFrame(rows).set_index("month")


# the conditions at release the error is read against
D["c_backlog"] = pd.Categorical(D["band"], BANDS, ordered=True)
D["c_brake"] = pd.qcut(D["brake_std"], 4, duplicates="drop")
D["c_lot"] = pd.qcut(D["qty"], 4, duplicates="drop")
D["c_operations"] = D["operations"].clip(upper=8).astype(int)
D["c_outside"] = np.where(D["outside"] == 1, "yes", "no")
D["c_month"] = D["release_date"].dt.month
CONDITIONS = {"Brake backlog at release (days)": "c_backlog", "Brake standard hours on the job (quartiles)": "c_brake", "Lot size (quartiles)": "c_lot",
              "Operations on the routing": "c_operations", "Outside processing on the routing": "c_outside", "Release month of the year": "c_month"}


def condition(col):
    """Jobs, mean lead time, mean quote, mean error and mean absolute error by band of a condition, and the share of the error's variance the bands explain."""
    g = D.groupby(col, observed=True)
    t = pd.DataFrame({"jobs": g.size(), "actual": g["lead"].mean(), "quoted": g["quote"].mean(), "bias": g["error"].mean(), "mae": g["error"].apply(lambda e: e.abs().mean())})
    total = float(((D["error"] - D["error"].mean()) ** 2).sum())
    return t, float((t["jobs"] * (t["bias"] - D["error"].mean()) ** 2).sum() / total)


def against_current(quote):
    """How a quote compares with the current one: the share shorter and by how much, the share longer and by how much."""
    d = D[quote] - D["quote"]
    return dict(shorter=float((d < 0).mean()), shorter_by=float(-d[d < 0].mean()), longer=float((d > 0).mean()), longer_by=float(d[d > 0].mean()), same=float((d == 0).mean()))


def size_grid():
    """The grid with brake standard hours in thirds, fitted on the history, for reference."""
    rows = []
    for cls in CLASSES:
        hc = HISTORY[HISTORY["routing_class"] == cls]
        cuts = hc["brake_std"].quantile([1 / 3, 2 / 3]).to_numpy()
        hs = np.searchsorted(cuts, hc["brake_std"].to_numpy(), side="right")
        for s_, lab in enumerate((f"under {cuts[0]:.2f}", f"{cuts[0]:.2f} to {cuts[1]:.2f}", f"over {cuts[1]:.2f}")):
            row = dict(routing_class=cls, hours=lab)
            for b in BANDS:
                x = hc[(hc["band"] == b).to_numpy() & (hs == s_)]["lead"]
                row[b] = (float(np.round(x.median())) if len(x) >= MIN_JOBS else np.nan, len(x))
            rows.append(row)
    return pd.DataFrame(rows)
