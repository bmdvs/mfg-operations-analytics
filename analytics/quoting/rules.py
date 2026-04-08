"""Quote rules from the brake backlog at release, against current practice, on non-rush jobs.

Every rule is out of sample: a job's quote is the 80th-percentile lead time of jobs of its routing class and backlog band shipped before its release,
never below the class standard. Lines customer service accepted inside the quote keep their recorded quote and due date; every other non-rush line is
restated, its due date the later of the requested date and the order date plus the rule's quote, with any later customer change kept. The floor is unchanged.
"""
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from analytics.db import q
from analytics.quoting import analysis as A

YEAR = 2025
FILL_MIN = 30                          # a band with fewer earlier jobs than this takes the quote of the deepest band below it that has them
THRESHOLDS = (1.5, 2.0, 2.5, 3.0)      # days of brake backlog at release at which a switch rule leaves the class standard for the table
KEEP = 0.9                             # the release flag's 3 days is the switch when it keeps this share of the late jobs the best lower switch removes
FIRST, FILLED = "Table as first fitted", "Table, thin bands filled"
LOT, WEEK = "Table with a lot-size band", "Standard plus the large-lot week"
CLASSES = ["repeat part", "new part", "outside processing"]
ORDER = {b: k for k, b in enumerate(A.BAND_LABELS)}


def switch(t, filled=False):
    return f"{'Filled table' if filled else 'Table as first fitted'}, switch at {t:.1f} days"


def load():
    j = q("""select l.job_id, l.routing_class, l.family, l.qty, l.standard_lead_days, l.quoted_lead_days, l.rush_flag, l.release_date, l.due_date, l.ship_date, l.on_time,
                    l.days_late, l.wip_days, c.brake_backlog_days, ol.order_date, ol.requested_date, ol.promised_date, ol.original_promised_date
             from marts.mart_job_lead_time l join marts.mart_job_release_conditions c using (job_id)
             join staging.stg_erp__jobs sj using (job_id) join staging.stg_erp__order_lines ol on ol.order_line_id = sj.order_line_id
             where l.ship_date is not null order by l.job_id""")
    for c in ("release_date", "due_date", "ship_date", "order_date", "requested_date", "promised_date", "original_promised_date"):
        j[c] = pd.to_datetime(j[c])
    j["rush_flag"] = j["rush_flag"].fillna(False).astype(bool)
    j["on_time"] = j["on_time"].astype(bool)
    j["band"] = pd.cut(j["brake_backlog_days"], A.BANDS, labels=A.BAND_LABELS).astype(str)
    # a large lot: at or above the 90th percentile of non-rush quote quantity in its part family
    large = q("select family, quantile_cont(qty, 0.9) as threshold from staging.stg_erp__quote_lines where not rush_rfq group by 1").set_index("family")["threshold"]
    j["large"] = j["qty"] >= j["family"].map(large)
    return j


class Clock:
    """Due dates are set in weekday working days; scheduled Saturdays are not counted. Outside the exported calendar, weekdays less the plant holidays."""

    def __init__(self):
        cal = pd.to_datetime(q("select distinct calendar_date from staging.stg_erp__work_center_calendar where not saturday order by 1")["calendar_date"])
        after = pd.bdate_range(cal.max() + pd.Timedelta(days=1), f"{YEAR + 1}-06-30")
        after = after[~((after.month == 12) & (after.day >= 24)) & ~((after.month == 1) & (after.day == 1))]
        before = pd.bdate_range("2022-06-01", cal.min() - pd.Timedelta(days=1))
        before = before[~((before.month == 12) & (before.day >= 24)) & ~before.isin(pd.to_datetime(["2022-07-04", "2022-09-05", "2022-11-24", "2022-11-25", "2023-01-02"]))]
        self.days = before.append(pd.DatetimeIndex(cal)).append(after)
        every = pd.date_range(self.days.min(), self.days.max())
        self.index = pd.Series(np.searchsorted(self.days.values, every.values), index=every).to_dict()      # a day off counts from the next working day

    def at(self, d):
        return d.map(self.index)

    def add(self, d, n):
        return pd.Series(self.days.values[np.minimum((self.at(d) + n).astype(int).to_numpy(), len(self.days) - 1)], index=d.index)


def quote(j, target, fill, lot=False):
    """Each target job's quote from the jobs shipped before its release. Without fill, a band with fewer than MIN_JOBS earlier jobs takes every earlier
    job of the class; with it, a band with fewer than FILL_MIN takes the deepest band below it that has them, and with none the class standard."""
    out = pd.Series(np.nan, index=target.index)
    used = pd.Series("", index=target.index)
    for cls, g in j.groupby("routing_class"):
        g = g.sort_values(["ship_date", "job_id"])
        ship, lead, band, large = g["ship_date"].to_numpy(), g["wip_days"].to_numpy(dtype=float), g["band"].to_numpy(), g["large"].to_numpy()
        for i, r in target[target["routing_class"] == cls].iterrows():
            earlier = ship < np.datetime64(r["release_date"])
            if lot:
                cells = [("lot", earlier & (band == r["band"]) & (large == r["large"]), A.MIN_JOBS), (r["band"], earlier & (band == r["band"]), A.MIN_JOBS),
                         ("class", earlier, A.MIN_JOBS)]
            elif fill:
                cells = [(b, earlier & (band == b), FILL_MIN) for b in A.BAND_LABELS[ORDER[r["band"]]::-1]]
            else:
                cells = [(r["band"], earlier & (band == r["band"]), A.MIN_JOBS), ("class", earlier, A.MIN_JOBS)]
            for name, use, least in cells:
                if use.sum() >= least:
                    out[i], used[i] = np.ceil(np.quantile(lead[use], A.PCTL)), name
                    break
    return np.maximum(out.fillna(target["standard_lead_days"]), target["standard_lead_days"]), used


J = load()
CLOCK = Clock()
N = J[~J["rush_flag"]].copy()
N[FIRST], _ = quote(J, N, False)
N[FILLED], N["band_used"] = quote(J, N, True)
N[LOT], _ = quote(J, N, False, lot=True)
N[WEEK] = N["standard_lead_days"] + 5 * N["large"]
for _t in THRESHOLDS:
    N[switch(_t)] = np.where(N["brake_backlog_days"] < _t, N["standard_lead_days"], N[FIRST])
    N[switch(_t, True)] = np.where(N["brake_backlog_days"] < _t, N["standard_lead_days"], N[FILLED])
N["release_quarter"] = N["release_date"].dt.to_period("Q").astype(str)
# accepted by customer service inside the quote: the due date was not set by the quote, and stays as recorded
N["inside"] = (CLOCK.at(N["original_promised_date"]) - CLOCK.at(N["order_date"])) < N["quoted_lead_days"]
_revision = (CLOCK.at(N["promised_date"]) - CLOCK.at(N["original_promised_date"])).fillna(0).astype(int)
EVERY = [FIRST] + [switch(t) for t in THRESHOLDS] + [LOT, WEEK, FILLED] + [switch(t, True) for t in THRESHOLDS]
for _r in EVERY:
    _due = CLOCK.add(N["order_date"], N[_r].astype(int))
    _due = _due.where(_due > N["requested_date"], N["requested_date"])
    _due = CLOCK.add(_due, _revision).where(~N["inside"], N["due_date"])
    N[f"on_time|{_r}"] = N["ship_date"] <= _due
    N[f"days_late|{_r}"] = (CLOCK.at(N["ship_date"]) - CLOCK.at(_due)).clip(lower=0)
    N[f"quote|{_r}"] = np.where(N["inside"], N["quoted_lead_days"], N[_r])

# what a longer quote costs: the fall in the non-rush win rate per day quoted above the standard
QN = q("select * from marts.mart_quotes where rfq_year between 2023 and 2025 and not rush_rfq order by quote_id")
QN["above"] = QN["quoted_lead_time_days"] - QN["standard_lead_days"]
QN["won"] = (QN["status"] == "won").astype(int)
_fit = smf.ols("won ~ above", QN).fit()
FALL, FALL_LOW, FALL_HIGH = float(-_fit.params["above"]), float(-_fit.conf_int().loc["above", 1]), float(-_fit.conf_int().loc["above", 0])
WIN_AT_STANDARD = float(QN[QN["above"] == 0]["won"].mean())
WIN_ABOVE = QN[QN["above"] > 0].groupby("above")["won"].agg(["mean", "size"])
QUOTE_VALUE = float((QN["quoted_price"] * QN["qty"]).mean())
ADDER_WEEKS = sorted(set((pd.to_datetime(QN[QN["above"] > 0]["quote_sent_date"]) - pd.to_timedelta(pd.to_datetime(QN[QN["above"] > 0]["quote_sent_date"]).dt.weekday, unit="D"))))
# the orders the shop's own adder forgoes: its quotes, times the win rate at the standard less their own
ADDER_QUOTES = int((QN["above"] > 0).sum())
ADDER_FORGONE = float(ADDER_QUOTES * (WIN_AT_STANDARD - QN[QN["above"] > 0]["won"].mean()))

SHIPPED = lambda d: d["ship_date"].dt.year == YEAR
SHIPPED_REST = lambda d: (d["ship_date"].dt.year == YEAR) & (d["ship_date"].dt.quarter >= 2)
RELEASED = lambda d: d["release_date"].dt.year == YEAR
ORDINARY = lambda d: (d["release_date"].dt.year == YEAR) & (d["release_date"].dt.quarter >= 3)      # the two quarters clear of the build, counted twice


def released_in(quarter):
    return lambda d: d["release_date"].dt.to_period("Q").astype(str) == quarter


QUARTERS = [f"{YEAR - 1}Q3", f"{YEAR - 1}Q4", f"{YEAR}Q1", f"{YEAR}Q2", f"{YEAR}Q3", f"{YEAR}Q4"]


def outcome(rule, where):
    """A rule on the jobs chosen: quote met and quotes moved on the non-rush jobs, delivery on all jobs."""
    d, a = N[where(N)], J[where(J)]
    if rule is None:
        return dict(non_rush=len(d), met=float((d["wip_days"] <= d["quoted_lead_days"]).mean()), longer=np.nan, added=np.nan, shorter=np.nan,
                    on_time=float(a["on_time"].mean()), late=int((~a["on_time"]).sum()), days_late=float(a["days_late"].sum()), net=0.0)
    m = a.merge(d[["job_id", f"on_time|{rule}", f"days_late|{rule}"]], on="job_id", how="left")
    ot, dl, qv = m[f"on_time|{rule}"].fillna(m["on_time"]).astype(bool), m[f"days_late|{rule}"].fillna(m["days_late"]), d[f"quote|{rule}"]
    longer = qv > d["quoted_lead_days"]
    return dict(non_rush=len(d), met=float((d["wip_days"] <= qv).mean()), longer=float(longer.mean()),
                added=float((qv - d["quoted_lead_days"])[longer].mean()) if longer.any() else np.nan, shorter=float((qv < d["quoted_lead_days"]).mean()),
                on_time=float(ot.mean()), late=int((~ot).sum()), days_late=float(dl.sum()), net=float((qv - d["quoted_lead_days"]).mean()))


def cost(rule, where, times=1.0):
    """Orders forgone and late jobs removed: the quotes behind the non-rush jobs, times the mean days the rule adds, times the fall per day."""
    base, o = outcome(None, where), outcome(rule, where)
    quotes = o["non_rush"] / WIN_AT_STANDARD
    forgone = [quotes * o["net"] * f * times for f in (FALL, FALL_LOW, FALL_HIGH)]
    return dict(net=o["net"], forgone=forgone[0], forgone_low=forgone[1], forgone_high=forgone[2], revenue=forgone[0] * QUOTE_VALUE,
                removed=(base["late"] - o["late"]) * times)


# the switch: the lower threshold that removes the most late jobs per order forgone, unless the release flag's 3 days keeps nearly all of them
_per = {t: cost(switch(t, True), SHIPPED)["removed"] / cost(switch(t, True), SHIPPED)["forgone"] for t in THRESHOLDS[:-1]}
BEST_LOWER = max(_per, key=_per.get)
THRESHOLD = 3.0 if cost(switch(3.0, True), SHIPPED)["removed"] >= KEEP * cost(switch(BEST_LOWER, True), SHIPPED)["removed"] else BEST_LOWER
RECOMMENDED = switch(THRESHOLD, True)


def weekly(start, end, rules):
    """By release week: brake backlog at release on all jobs, and the mean non-rush quote under current practice and each rule."""
    week = lambda d: d["release_date"] - pd.to_timedelta(d["release_date"].dt.weekday, unit="D")
    a = J[(J["release_date"] >= start) & (J["release_date"] <= end)]
    d = N[(N["release_date"] >= start) & (N["release_date"] <= end)]
    g = pd.DataFrame({"jobs": d.groupby(week(d)).size(), "backlog": a.groupby(week(a))["brake_backlog_days"].mean(), "current": d.groupby(week(d))["quoted_lead_days"].mean()})
    for r in rules:
        g[r] = d.groupby(week(d))[f"quote|{r}"].mean()
    g["adder"] = [w in set(ADDER_WEEKS) for w in g.index]
    return g


def history(months):
    """Jobs shipped before the first day of each month, by routing class and backlog band: what the table had to quote from."""
    rows = []
    for m in months:
        h = J[J["ship_date"] < m]
        for cls in CLASSES:
            c = h[h["routing_class"] == cls]["band"].value_counts()
            rows.append(dict(month=m, routing_class=cls, **{b: int(c.get(b, 0)) for b in A.BAND_LABELS}))
    return pd.DataFrame(rows)


def grid():
    """The quote table fitted on every job shipped: 80th-percentile lead time by routing class and backlog band, never below the standard, thin bands filled."""
    rows = []
    for cls in CLASSES:
        g = J[J["routing_class"] == cls]
        std = int(g["standard_lead_days"].max())
        row, last = dict(routing_class=cls, standard=std), std
        for b in A.BAND_LABELS:
            x = g[g["band"] == b]["wip_days"]
            if len(x) >= FILL_MIN:
                last = max(int(np.ceil(x.quantile(A.PCTL))), std)
            row[b], row[f"jobs {b}"] = last, len(x)
        rows.append(row)
    return pd.DataFrame(rows)


FILL = N[N["band_used"] != N["band"]]
