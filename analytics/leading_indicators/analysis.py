"""Leading indicators: the measures, read from the marts."""
import numpy as np
import pandas as pd

from analytics.db import q

YEAR = 2025
MAX_LAG = 12
SHUFFLES = 1000
SEED = 20250101
EVENT = (pd.Timestamp("2024-11-11"), pd.Timestamp("2025-03-31"))     # the 2024 year-end build, by week start
START = pd.Timestamp("2023-01-30")                                    # the first four weeks carry the jobs in process when the records begin
MIN_JOBS = 30                                                        # weeks shipping fewer jobs carry no on-time delivery figure
DECLINE_POINTS = 0.05
WINDOW, BASE, LOOKBACK = 4, 13, 8
BACKLOG_THRESHOLD = 3.0

# column, label, direction (+1: a higher value is adverse), group
INDICATORS = [
    ("on_time_start_rate", "On-time start rate", -1, "review set"),
    ("brake_setup_efficiency", "Setup efficiency at the brakes", -1, "review set"),
    ("schedule_adherence", "Schedule adherence", -1, "review set"),
    ("brake_overtime_labor_hours", "Overtime labor hours at the brakes", 1, "review set"),
    ("outside_receipt_on_time", "Outside-processing receipts on time", -1, "review set"),
    ("kit_complete_rate", "Kit completeness", -1, "review set"),
    ("brake_backlog_days_at_release", "Brake backlog at release (days)", 1, "added"),
    ("promised_inside_standard_share", "Jobs released late", 1, "added"),
    ("brake_std_hours_released", "Brake standard hours released", 1, "floor"),
    ("wip_at_laser", "Jobs waiting at the lasers", 1, "floor"),
    ("wip_at_brakes", "Jobs waiting at the brakes", 1, "floor"),
]
LABEL = {c: l for c, l, _, _ in INDICATORS}


def load():
    w = q("select * from marts.mart_weekly_indicators order by week_start")
    w["week_start"] = pd.to_datetime(w["week_start"])
    w = w.set_index("week_start")
    w = w[w.index >= START]
    w["otd"] = w["on_time_delivery"].where(w["jobs_shipped"] >= MIN_JOBS)
    w["event"] = (w.index >= EVENT[0]) & (w.index <= EVENT[1])
    j = q("select * from marts.mart_job_release_conditions")
    for c in ("release_date", "ship_date"):
        j[c] = pd.to_datetime(j[c])
    j["late"] = j["on_time"].notna() & ~j["on_time"].fillna(True).astype(bool)
    return dict(w=w, j=j, batch=w["export_batch_id"].iloc[0])


# ── cross-correlation ───────────────────────────────────────────────────────
def lagged(x, y, k):
    """Correlation of the indicator k weeks earlier with on-time delivery (k < 0: the indicator k weeks later)."""
    n = len(x)
    a, b = (x[:n - k], y[k:]) if k >= 0 else (x[-k:], y[:n + k])
    ok = ~(np.isnan(a) | np.isnan(b))
    if ok.sum() < 20 or a[ok].std() == 0 or b[ok].std() == 0:
        return np.nan
    return float(np.corrcoef(a[ok], b[ok])[0, 1])


def best_lead(x, y, sign):
    """The largest correlation in the adverse direction at leads of 1 to MAX_LAG weeks, and the lead it occurs at."""
    r = np.array([-sign * lagged(x, y, k) for k in range(1, MAX_LAG + 1)])
    k = int(np.nanargmax(r))
    return r[k], k + 1


def cross_correlation(D, exclude_event=False):
    """Per indicator: correlation at lag 0, the best lead and its correlation, the best lag on either side, and the same statistic on shuffled series.

    Correlations are signed so that positive means the indicator's adverse movement goes with lower on-time delivery.
    Shuffled: the indicator's weeks in random order. Shifted: the indicator moved in time by a random offset of 13 weeks or more, its own pattern kept."""
    w = D["w"]
    rng = np.random.default_rng(SEED)
    y = w["otd"].to_numpy(dtype=float).copy()
    if exclude_event:
        y[w["event"].to_numpy()] = np.nan
    rows = []
    for col, label, sign, group in INDICATORS:
        x = w[col].to_numpy(dtype=float).copy()
        if exclude_event:
            x[w["event"].to_numpy()] = np.nan
        r0 = -sign * lagged(x, y, 0)
        rb, kb = best_lead(x, y, sign)
        both = {k: -sign * lagged(x, y, k) for k in range(-MAX_LAG, MAX_LAG + 1)}
        kpeak = max(both, key=lambda k: -np.inf if np.isnan(both[k]) else both[k])
        obs = np.where(~np.isnan(x))[0]
        shuf, shift = [], []
        for _ in range(SHUFFLES):
            xs = x.copy()
            xs[obs] = rng.permutation(x[obs])
            shuf.append(best_lead(xs, y, sign)[0])
            shift.append(best_lead(np.roll(x, int(rng.integers(BASE, len(x) - BASE))), y, sign)[0])
        shuf, shift = np.array(shuf), np.array(shift)
        rows.append(dict(indicator=label, group=group, weeks=int((~np.isnan(x) & ~np.isnan(y)).sum()), r_lag0=r0, best_lead_weeks=kb, r_best_lead=rb,
                         peak_lag_weeks=kpeak, r_peak=both[kpeak],
                         shuffled_mean=shuf.mean(), shuffled_p95=np.quantile(shuf, 0.95), shuffled_p=(shuf >= rb).mean(),
                         shifted_mean=np.nanmean(shift), shifted_p95=np.nanquantile(shift, 0.95), shifted_p=(shift >= rb).mean()))
    return pd.DataFrame(rows)


def correlation_by_lag(D, exclude_event=False):
    w = D["w"]
    y = w["otd"].to_numpy(dtype=float).copy()
    out = {}
    for col, label, sign, _ in INDICATORS:
        x = w[col].to_numpy(dtype=float).copy()
        if exclude_event:
            x[w["event"].to_numpy()] = np.nan
            y[w["event"].to_numpy()] = np.nan
        out[label] = [-sign * lagged(x, y, k) for k in range(0, MAX_LAG + 1)]
    return pd.DataFrame(out, index=range(0, MAX_LAG + 1)).T


# ── declines ────────────────────────────────────────────────────────────────
def rolling_otd(w):
    """On-time delivery of the jobs shipped in the trailing four weeks."""
    on = (w["on_time_delivery"] * w["jobs_shipped"]).rolling(WINDOW).sum()
    return on / w["jobs_shipped"].rolling(WINDOW).sum()


def declines(D):
    """Decline onsets: the first week the trailing four-week on-time delivery is more than 5 points below the 13 weeks before that window,
    after at least eight weeks without the condition."""
    w = D["w"]
    o4 = rolling_otd(w)
    on = (w["on_time_delivery"] * w["jobs_shipped"]).shift(WINDOW).rolling(BASE).sum()
    base = on / w["jobs_shipped"].shift(WINDOW).rolling(BASE).sum()
    cond = ((base - o4) > DECLINE_POINTS).to_numpy()
    onsets, last = [], -10 ** 6
    for i, c in enumerate(cond):
        if c:
            if i - last > LOOKBACK:
                onsets.append(i)
            last = i
    return pd.DataFrame(dict(onset=w.index[onsets], position=onsets, otd_before=base.iloc[onsets].to_numpy(), otd_at_onset=o4.iloc[onsets].to_numpy(),
                             otd_low=[o4.iloc[i:i + BASE].min() for i in onsets]))


def signal(x, sign):
    """Weeks in which the indicator's four-week mean is adverse to the 13 weeks before that window by more than one standard deviation of those weeks."""
    s = pd.Series(x)
    m4 = s.rolling(WINDOW).mean()
    b = s.shift(WINDOW).rolling(BASE)
    return (sign * (m4 - b.mean()) > b.std(ddof=1)).to_numpy()


def leads(sig, onsets):
    """For each decline onset, the weeks between the earliest signal in the eight weeks before it and the onset (nan: no signal)."""
    out = []
    for i in onsets:
        win = np.where(sig[max(i - LOOKBACK, 0):i])[0]
        out.append(float(min(i, LOOKBACK) - win[0]) if len(win) else np.nan)
    return np.array(out)


def episodes(sig):
    """Signal onsets: a signal week after at least four weeks without one."""
    out, last = [], -10 ** 6
    for i, c in enumerate(sig):
        if c:
            if i - last > WINDOW:
                out.append(i)
            last = i
    return out


def decline_leads(D):
    w, dec = D["w"], declines(D)
    onsets = dec["position"].tolist()
    rng = np.random.default_rng(SEED + 1)
    rows, detail = [], {}
    for col, label, sign, group in INDICATORS:
        x = w[col].to_numpy(dtype=float)
        sig = signal(x, sign)
        ld = leads(sig, onsets)
        detail[label] = ld
        ep = episodes(sig)
        followed = sum(any(0 < o - e <= LOOKBACK for o in onsets) for e in ep)
        shuf, shift = [], []
        for _ in range(SHUFFLES):
            shuf.append(np.isfinite(leads(signal(rng.permutation(x), sign), onsets)).sum())
            shift.append(np.isfinite(leads(np.roll(sig, int(rng.integers(BASE, len(x) - BASE))), onsets)).sum())
        k = int(np.isfinite(ld).sum())
        rows.append(dict(indicator=label, group=group, declines=len(onsets), preceded=k, median_lead_weeks=np.nanmedian(ld) if k else np.nan,
                         shuffled_expected=np.mean(shuf), shuffled_p=(np.array(shuf) >= k).mean(),
                         shifted_expected=np.mean(shift), shifted_p=(np.array(shift) >= k).mean(),
                         signal_weeks=int(sig.sum()), signal_episodes=len(ep), episodes_followed_by_decline=followed))
    lead_table = pd.DataFrame(detail, index=dec["onset"].dt.strftime("%Y-%m-%d")).T
    return pd.DataFrame(rows), dec, lead_table


def pair_leads(D, first, second):
    """Declines preceded by either of two indicators, the longer lead of the two, and the same count on shuffled and shifted series."""
    w, onsets = D["w"], declines(D)["position"].tolist()
    col = {l: (c, s) for c, l, s, _ in INDICATORS}
    xs = [(w[col[n][0]].to_numpy(dtype=float), col[n][1]) for n in (first, second)]
    sigs = [signal(x, s) for x, s in xs]
    lead = np.fmax(*[leads(sig, onsets) for sig in sigs])
    k = int(np.isfinite(lead).sum())
    rng = np.random.default_rng(SEED + 2)
    shuf, shift = [], []
    for _ in range(SHUFFLES):
        a = [leads(signal(rng.permutation(x), s), onsets) for x, s in xs]
        b = [leads(np.roll(sig, int(rng.integers(BASE, len(sig) - BASE))), onsets) for sig in sigs]
        shuf.append(np.isfinite(np.fmax(*a)).sum())
        shift.append(np.isfinite(np.fmax(*b)).sum())
    shuf, shift = np.array(shuf), np.array(shift)
    return dict(lead=lead, preceded=k, declines=len(onsets), shuffled_expected=shuf.mean(), shuffled_p=(shuf >= k).mean(),
                shifted_expected=shift.mean(), shifted_p=(shift >= k).mean())


# ── the two largest causes ──────────────────────────────────────────────────
def periods(j, col="release_date"):
    return (("2023 to 2025", j), (f"{YEAR}", j[j[col].dt.year == YEAR]), (f"{YEAR} Q2 to Q4", j[(j[col].dt.year == YEAR) & (j[col].dt.quarter >= 2)]))


def backlog_bands(D):
    j = D["j"][D["j"]["on_time"].notna()].copy()
    j["band"] = pd.cut(j["brake_backlog_days"], [-1, 1, 2, 3, 4, 5, 6, 99], labels=["under 1", "1 to 2", "2 to 3", "3 to 4", "4 to 5", "5 to 6", "over 6"])
    rows = []
    for name, d in periods(j):
        g = d.groupby("band", observed=False).agg(jobs=("late", "size"), late_jobs=("late", "sum"))
        g["late_rate"] = g["late_jobs"] / g["jobs"]
        rows.append(g.assign(period=name).reset_index())
    return pd.concat(rows)


def backlog_threshold(D, t=BACKLOG_THRESHOLD):
    """Late jobs released with the brake backlog above the threshold, against the share of all jobs released above it."""
    j = D["j"][D["j"]["on_time"].notna()]
    rows = []
    for name, d in periods(j):
        above = d["brake_backlog_days"] > t
        rows.append(dict(period=name, jobs=len(d), late_jobs=int(d["late"].sum()), late_jobs_above=int((d["late"] & above).sum()),
                         share_of_late_jobs_above=(d["late"] & above).sum() / d["late"].sum(), share_of_all_jobs_above=above.mean(),
                         late_rate_above=d.loc[above, "late"].mean(), late_rate_below=d.loc[~above, "late"].mean()))
    return pd.DataFrame(rows)


def short_promises(D):
    j = D["j"][D["j"]["on_time"].notna()]
    rows = []
    for name, d in periods(j):
        s = d["promised_inside_standard"].fillna(False).astype(bool)
        rows.append(dict(period=name, jobs=len(d), promised_inside=int(s.sum()), share_of_jobs=s.mean(), late_rate_inside=d.loc[s, "late"].mean(),
                         late_rate_other=d.loc[~s, "late"].mean(), share_of_late_jobs=(d["late"] & s).sum() / d["late"].sum()))
    return pd.DataFrame(rows)


def kit_and_material(D):
    """Material-caused lost days (the late-job attribution) on jobs with a kit check and with a short kit, against the short rate of all kit checks."""
    a = q(f"""select a.job_id, a.ship_quarter, sum(a.attributed_days) as days from marts.mart_late_job_attribution a
              where a.cause = 'material' and a.ship_year = {YEAR} group by 1, 2 having sum(a.attributed_days) > 0""")
    k = D["j"][["job_id", "kit_result", "ship_date"]]
    a = a.merge(k, on="job_id", how="left")
    allk = k[k["kit_result"].notna() & (k["ship_date"].dt.year == YEAR)]
    rows = []
    for name, d, kk in ((f"{YEAR}", a, allk), (f"{YEAR} Q2 to Q4", a[a["ship_quarter"] >= 2], allk[allk["ship_date"].dt.quarter >= 2])):
        short, checked = d["kit_result"] == "short", d["kit_result"].notna()
        rows.append(dict(period=name, late_jobs_with_material_days=len(d), material_days=d["days"].sum(), jobs_with_kit_check=int(checked.sum()),
                         days_on_jobs_with_kit_check=d.loc[checked, "days"].sum(), jobs_with_short_kit=int(short.sum()),
                         days_on_jobs_with_short_kit=d.loc[short, "days"].sum(), share_of_days_short_kit=d.loc[short, "days"].sum() / d["days"].sum(),
                         share_of_days_no_kit_check=d.loc[~checked, "days"].sum() / d["days"].sum(),
                         short_rate_all_kit_checks=(kk["kit_result"] == "short").mean()))
    return pd.DataFrame(rows)


def overtime(D):
    o = q("select * from marts.mart_overtime_hours")
    o["year"] = pd.to_datetime(o["week_start"]).dt.year
    o["rush_flag"] = o["rush_flag"].fillna(False).astype(bool)
    by_wc = o.pivot_table(index="work_center", columns="year", values="labor_hours", aggfunc="sum", fill_value=0.0)
    b = o[(o["work_center"] == "press_brake") & (o["year"] == YEAR)]
    by_family = b.groupby("family")["labor_hours"].sum().sort_values(ascending=False)
    by_type = b.groupby("overtime_type")["labor_hours"].sum()
    encl_rush = b.loc[(b["family"] == "enclosure") | b["rush_flag"], "labor_hours"].sum() / b["labor_hours"].sum()
    return dict(by_work_center=by_wc, by_family=by_family, by_type=by_type, rush=b.groupby("rush_flag")["labor_hours"].sum(), enclosure_or_rush=encl_rush)


def by_quarter(D):
    w = D["w"]
    cols = [c for c, *_ in INDICATORS]
    g = w.groupby(w.index.to_period("Q"))
    out = g[cols].mean()
    out.insert(0, "on_time_delivery", g.apply(lambda d: (d["on_time_delivery"] * d["jobs_shipped"]).sum() / d["jobs_shipped"].sum()))
    return out
