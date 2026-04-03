"""The constraint, utilization and variability: the measures and the fitted queue curves, read from the marts."""
import numpy as np
import pandas as pd

from analytics.db import q

YEAR = 2025
PERIODS = (("year", 1), ("Q2 to Q4", 2))
QUEUE_AT = (0.75, 0.85, 0.90, 0.92)


def vut_factor(u, m):
    """Utilization term of the queue-time approximation for m machines (Sakasegawa form of the VUT equation)."""
    u = np.asarray(u, dtype=float)
    return u ** (np.sqrt(2 * (m + 1)) - 1) / (m * (1 - u))


def fit_curve(weeks, m, window=1):
    """Least-squares scale k of queue = k x factor(u, m), on windows of `window` weeks with utilization between 0.3 and 0.98.

    With window 1 only full five-day weeks are used; longer windows roll week by week and pool hours and operations."""
    w = weeks.sort_values("week_start").reset_index(drop=True)
    if window == 1:
        d = w[(w["weekdays"] == 5) & w["queue_mean"].notna()]
        d = pd.DataFrame({"u": d["utilization"], "q": d["queue_mean"]})
    else:
        r = w[["machine_hours", "scheduled_hours", "downtime_hours"]].rolling(window).sum()
        ops = w["operations"].fillna(0)
        d = pd.DataFrame({"u": r["machine_hours"] / (r["scheduled_hours"] - r["downtime_hours"]),
                          "q": (w["queue_mean"].fillna(0) * ops).rolling(window).sum() / ops.rolling(window).sum()}).dropna()
    d = d[(d["u"] > 0.3) & (d["u"] < 0.98)]
    x, y = vut_factor(d["u"], m), d["q"].to_numpy()
    k = float((x * y).sum() / (x * x).sum())
    sse, sst = float(((y - k * x) ** 2).sum()), float(((y - y.mean()) ** 2).sum())
    rho = float(pd.Series(d["u"].to_numpy()).corr(pd.Series(y), method="spearman"))
    return dict(k=k, windows=len(d), r2=1 - sse / sst, rank_correlation=rho, u_min=float(d["u"].min()), u_max=float(d["u"].max()))


def load():
    return dict(
        uw=q("select * from marts.mart_utilization_weekly"),
        mw=q("select * from marts.mart_machine_weekly"),
        ops=q(f"select * from marts.mart_operations where start_year = {YEAR}"),
        rel=q("select * from marts.mart_releases_daily"),
        att=q("select * from marts.mart_attendance_daily"),
        dt=q("select * from marts.mart_downtime_events"),
        arrivals=q("select work_center, cast(prev_end as date) as d, count(*) as n from intermediate.int_operation_queue "
                   "where not is_first_op group by 1, 2"),
        batch=q("select export_batch_id from marts.mart_utilization_weekly limit 1").iloc[0, 0],
    )


def utilization(D):
    rows = []
    for per, fq in PERIODS:
        w = D["uw"][(D["uw"]["week_year"] == YEAR) & (D["uw"]["week_quarter"] >= fq)]
        g = w.groupby("work_center").agg(machines=("machines", "max"), scheduled=("scheduled_hours", "sum"), machine=("machine_hours", "sum"),
                                         down=("downtime_hours", "sum"))
        o = D["ops"][D["ops"]["start_quarter"] >= fq]
        g["utilization"] = g["machine"] / (g["scheduled"] - g["down"])
        g["uptime"] = 1 - g["down"] / g["scheduled"]
        g["utilization_of_scheduled"] = g["machine"] / g["scheduled"]
        qd = o[~o["is_first_op"].fillna(False)].groupby("work_center")["queue_net_wd"].agg(queue_mean="mean", queue_median="median", queue_p90=lambda x: x.quantile(0.9))
        g = g.join(qd)
        g.insert(0, "period", per)
        rows.append(g.reset_index())
    return pd.concat(rows).sort_values(["period", "utilization"], ascending=[False, False])


def machines(D, work_centers=("press_brake", "robotic_weld")):
    rows = []
    for per, fq in PERIODS:
        w = D["mw"][(D["mw"]["week_year"] == YEAR) & (D["mw"]["week_quarter"] >= fq) & D["mw"]["work_center"].isin(work_centers)]
        g = w.groupby(["work_center", "machine_id"]).agg(crewed_shifts=("crewed_shifts", "max"), scheduled=("scheduled_hours", "sum"), machine=("machine_hours", "sum"),
                                                          saturday_hours=("saturday_hours", "sum"), down=("downtime_hours", "sum"))
        g["utilization_weekday_basis"] = g["machine"] / (g["scheduled"] - g["down"])
        # Saturday and extended hours worked at the work center, shared by the machines that ran on Saturdays
        u = D["uw"][(D["uw"]["week_year"] == YEAR) & (D["uw"]["week_quarter"] >= fq)].groupby("work_center")["scheduled_hours"].sum()
        g["overtime_scheduled"] = 0.0
        for wc in g.index.get_level_values("work_center").unique():
            extra = float(u.get(wc, 0.0)) - float(g.loc[wc, "scheduled"].sum())
            sat = g.loc[wc, "saturday_hours"] > 0
            if extra > 0 and sat.any():
                g.loc[[(wc, mid) for mid in sat[sat].index], "overtime_scheduled"] = extra / int(sat.sum())
        g["utilization"] = g["machine"] / (g["scheduled"] + g["overtime_scheduled"] - g["down"])
        g["uptime"] = 1 - g["down"] / (g["scheduled"] + g["overtime_scheduled"])
        o = D["ops"][(D["ops"]["start_quarter"] >= fq) & ~D["ops"]["is_first_op"].fillna(False)]
        qd = o.groupby("machine_id")["queue_net_wd"].agg(operations="size", queue_mean="mean", queue_median="median", queue_p90=lambda x: x.quantile(0.9))
        g = g.reset_index().merge(qd, on="machine_id", how="left")
        g.insert(0, "period", per)
        rows.append(g)
    return pd.concat(rows)


def curves(D, window=13):
    fits, pos = [], []
    for wc, w in D["uw"].groupby("work_center"):
        m = int(w["machines"].max())
        f = fit_curve(w, m, window)
        fits.append(dict(work_center=wc, machines=m, **f, **{f"queue_at_{u:.2f}": f["k"] * float(vut_factor(u, m)) for u in QUEUE_AT}))
        for per, fq in PERIODS:
            x = w[(w["week_year"] == YEAR) & (w["week_quarter"] >= fq)]
            u = x["machine_hours"].sum() / (x["scheduled_hours"].sum() - x["downtime_hours"].sum())
            qm = (x["queue_mean"] * x["operations"]).sum() / x["operations"].sum()
            pos.append(dict(period=per, work_center=wc, utilization=u, queue_measured=qm, queue_on_curve=f["k"] * float(vut_factor(u, m)),
                            weeks=len(x), weeks_at_0_95=int((x["utilization"] >= 0.95).sum())))
    return pd.DataFrame(fits).sort_values("k", ascending=False), pd.DataFrame(pos)


def cv(x):
    x = pd.Series(x).dropna()
    return float(x.std() / x.mean())


def variability(D):
    rel = D["rel"][pd.to_datetime(D["rel"]["calendar_date"]).dt.year == YEAR]
    rows = [dict(source="Arrivals: jobs released per working day", measure="coefficient of variation", value=cv(rel["releases"])),
            dict(source="Arrivals: Monday releases over the daily mean", measure="ratio", value=rel[rel["weekday_no"] == 1]["releases"].mean() / rel["releases"].mean()),
            dict(source="Arrivals: top customer, last three working days of the month over its daily mean", measure="ratio",
                 value=rel[rel["month_end"]]["top_customer_releases"].mean() / rel["top_customer_releases"].mean()),
            dict(source="Arrivals: releases per week", measure="coefficient of variation",
                 value=cv(rel.groupby(pd.to_datetime(rel["calendar_date"]).dt.to_period("W"))["releases"].sum()))]
    b = D["ops"][(D["ops"]["work_center"] == "press_brake") & (D["ops"]["setup_hours"] > 0)]
    rows += [dict(source="Brake setup time per operation (hours)", measure="coefficient of variation", value=cv(b["setup_hours"])),
             dict(source="Brake setup actual over standard", measure="coefficient of variation", value=cv(b["setup_hours"] / b["setup_std"])),
             dict(source="Brake run time per operation (hours)", measure="coefficient of variation", value=cv(b["run_hours"])),
             dict(source="Brake setup and run per operation (hours)", measure="coefficient of variation", value=cv(b["setup_hours"] + b["run_hours"]))]
    dt = D["dt"][(D["dt"]["work_center"] == "press_brake") & (pd.to_datetime(D["dt"]["start_ts"]).dt.year == YEAR)]
    weeks = D["uw"][(D["uw"]["work_center"] == "press_brake") & (D["uw"]["week_year"] == YEAR)]
    rows += [dict(source="Brake downtime hours per week", measure="coefficient of variation", value=cv(weeks["downtime_hours"])),
             dict(source="Brake downtime hours per event", measure="coefficient of variation", value=cv(dt["hours"])),
             dict(source="Brake downtime share of scheduled hours", measure="share", value=weeks["downtime_hours"].sum() / weeks["scheduled_hours"].sum())]
    att = D["att"][pd.to_datetime(D["att"]["work_date"]).dt.year == YEAR].copy()
    att["rate"] = att["absent"] / att["scheduled"]
    for s, g in att.groupby("shift"):
        rows += [dict(source=f"Absence, {s} shift: share of scheduled employee-days", measure="share", value=g["absent"].sum() / g["scheduled"].sum()),
                 dict(source=f"Absence, {s} shift: daily rate", measure="coefficient of variation", value=cv(g["rate"]))]
    return pd.DataFrame(rows)


def powder(D):
    rows = []
    for per, fq in PERIODS:
        o = D["ops"][(D["ops"]["work_center"] == "powder_coat") & (D["ops"]["start_quarter"] >= fq)]
        w = D["uw"][(D["uw"]["work_center"] == "powder_coat") & (D["uw"]["week_year"] == YEAR) & (D["uw"]["week_quarter"] >= fq)]
        rows.append(dict(period=per, operations=len(o), utilization=w["machine_hours"].sum() / (w["scheduled_hours"].sum() - w["downtime_hours"].sum()),
                         color_day_wait_mean=o["scheduling_wait_wd"].mean(), color_day_wait_median=o["scheduling_wait_wd"].median(),
                         color_day_wait_p90=o["scheduling_wait_wd"].quantile(0.9), share_waiting_a_day_or_more=(o["scheduling_wait_wd"] >= 1).mean(),
                         queue_after_color_day_mean=o["queue_net_wd"].mean()))
    return pd.DataFrame(rows)


def laser(D):
    w = D["uw"][D["uw"]["work_center"] == "laser"].copy()
    w["week_start"] = pd.to_datetime(w["week_start"])
    ann = w.groupby("week_year").apply(lambda x: x["machine_hours"].sum() / (x["scheduled_hours"].sum() - x["downtime_hours"].sum()), include_groups=False)
    nov = w[(w["week_start"] >= "2024-11-04") & (w["week_start"] <= "2024-12-16")].sort_values("week_start")[["week_start", "weekdays", "utilization", "operations", "queue_mean", "queue_p90"]]
    return ann.rename("utilization").reset_index(), nov


def robot(D):
    rows = []
    for per, fq in PERIODS:
        o = D["ops"][(D["ops"]["work_center"] == "robotic_weld") & (D["ops"]["start_quarter"] >= fq)]
        w = D["uw"][(D["uw"]["work_center"] == "robotic_weld") & (D["uw"]["week_year"] == YEAR) & (D["uw"]["week_quarter"] >= fq)]
        rows.append(dict(period=per, operations=len(o), utilization=w["machine_hours"].sum() / (w["scheduled_hours"].sum() - w["downtime_hours"].sum()),
                         queue_mean=o["queue_net_wd"].mean(), queue_median=o["queue_net_wd"].median(), queue_p90=o["queue_net_wd"].quantile(0.9),
                         enclosure_share_of_hours=(o.loc[o["family"] == "enclosure", ["setup_hours", "run_hours"]].sum().sum()) / o[["setup_hours", "run_hours"]].sum().sum(),
                         weeks_at_0_95=int((w["utilization"] >= 0.95).sum()), weeks=len(w)))
    return pd.DataFrame(rows)


def setup_variability(D, fits, pos):
    """Brake queue and capacity with the spread of setup time around its mean halved, read off the fitted curve."""
    b = D["ops"][D["ops"]["work_center"] == "press_brake"]
    s, r = b["setup_hours"].fillna(0), b["run_hours"].fillna(0)
    t = s + r
    ce2 = float(t.var() / t.mean() ** 2)
    t_half = (s.mean() + (s - s.mean()) / 2) + r
    ce2_half = float(t_half.var() / t_half.mean() ** 2)
    arr = D["arrivals"][(D["arrivals"]["work_center"] == "press_brake") & (pd.to_datetime(D["arrivals"]["d"]).dt.year == YEAR)]
    days = pd.to_datetime(D["rel"][pd.to_datetime(D["rel"]["calendar_date"]).dt.year == YEAR]["calendar_date"])
    n = arr.assign(d=pd.to_datetime(arr["d"])).set_index("d")["n"].reindex(days).fillna(0)
    ca2 = float(n.var() / n.mean())
    f = fits[fits["work_center"] == "press_brake"].iloc[0]
    m, k = int(f["machines"]), float(f["k"])
    k_half = k * (ca2 + ce2_half) / (ca2 + ce2)
    out = []
    w = D["uw"][(D["uw"]["work_center"] == "press_brake") & (D["uw"]["week_year"] == YEAR)]
    net_week = float((w["scheduled_hours"] - w["downtime_hours"]).sum() / len(w))
    grid = np.linspace(0.5, 0.995, 2000)
    for per, _ in PERIODS:
        u = float(pos[(pos["work_center"] == "press_brake") & (pos["period"] == per)]["utilization"].iloc[0])
        q_now, q_half = k * float(vut_factor(u, m)), k_half * float(vut_factor(u, m))
        u_same = float(grid[np.argmin(abs(k_half * vut_factor(grid, m) - q_now))])
        out.append(dict(period=per, utilization=u, queue_on_curve=q_now, queue_with_half_setup_spread=q_half, utilization_at_same_queue=u_same,
                        hours_per_week_released=(u_same - u) * net_week))
    par = dict(setup_cv=cv(s), setup_run_cv2=ce2, setup_run_cv2_half=ce2_half, arrival_dispersion=ca2, curve_scale=k, curve_scale_half=k_half,
               setup_share_of_brake_hours=float(s.sum() / t.sum()), net_hours_per_week=net_week)
    return pd.DataFrame(out), par


def brake_bins(D):
    """Weekly brake queue by utilization band, full weeks of the whole period."""
    b = D["uw"][(D["uw"]["work_center"] == "press_brake") & (D["uw"]["weekdays"] == 5)]
    b = b.assign(band=pd.cut(b["utilization"], [0, 0.8, 0.85, 0.9, 0.95, 2], labels=["below 80%", "80% to 85%", "85% to 90%", "90% to 95%", "at or above 95%"]))
    return b.groupby("band", observed=True).agg(weeks=("queue_mean", "size"), queue_mean=("queue_mean", "mean"), queue_median=("queue_mean", "median")).reset_index()


def brake_quarters(D):
    """Brake queue per operation by quarter of the report year."""
    o = D["ops"][(D["ops"]["work_center"] == "press_brake") & ~D["ops"]["is_first_op"].fillna(False)]
    return o.groupby("start_quarter")["queue_net_wd"].agg(operations="size", queue_mean="mean", queue_median="median", queue_p90=lambda x: x.quantile(0.9)).reset_index()


def laser_weeks_at(D, level=0.95):
    w = D["uw"][(D["uw"]["work_center"] == "laser") & (D["uw"]["weekdays"] == 5)]
    hot = w[w["utilization"] >= level]
    return len(hot), len(w), sorted(pd.to_datetime(hot["week_start"]).dt.strftime("%Y-%m-%d"))
