"""P4 setups and standards: the measures, read from the marts."""
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from analytics.db import q

YEAR = 2025
WEEKS = 52
TOP_N = 12


def load():
    s = q(f"select * from marts.mart_setups where setup_year = {YEAR}")
    for c in ("same_tooling_as_previous", "spans_shift_change", "two_person_setup", "stale_standard"):
        s[c] = s[c].fillna(False).astype(bool)
    s["familiarity"] = pd.cut(s["prior_setups"], [-1, 0, 2, 10 ** 6], labels=["none", "1 or 2", "3 or more"])
    s["tenure"] = np.where(s["tenure_days"] < 365, "under 12 months", "12 months or more")
    s["lot_band"] = pd.Categorical(s["lot_band"], ["under 25", "25 to 99", "100 and over"])
    r = q(f"select * from marts.mart_run_standards where start_year = {YEAR}")
    for c in ("stale_standard", "has_routing"):
        r[c] = r[c].fillna(False).astype(bool)
    util = q(f"select work_center, sum(machine_hours) / sum(scheduled_hours - downtime_hours) as utilization, sum(machine_hours) as machine_hours "
             f"from marts.mart_utilization_weekly where week_year = {YEAR} group by 1").set_index("work_center")
    parts = q("select p.part_id, p.active, p.first_quoted_date, r.standard_set_date from staging.stg_erp__parts p "
              "left join (select part_id, min(standard_set_date) as standard_set_date from staging.stg_erp__routings group by 1) r using (part_id)")
    return dict(s=s, r=r, util=util, parts=parts, batch=s["export_batch_id"].iloc[0])


def summary(d):
    return pd.Series(dict(setups=len(d), median_ratio=d["setup_ratio"].median(), mean_ratio=d["setup_hours"].sum() / d["setup_std"].sum(),
                          p90_ratio=d["setup_ratio"].quantile(0.9), setup_hours=d["setup_hours"].sum(), standard_hours=d["setup_std"].sum(),
                          overrun_hours=(d["setup_hours"] - d["setup_std"]).sum()))


def brake(D):
    return D["s"][D["s"]["work_center"] == "press_brake"]


def overall(D):
    b = brake(D)
    return pd.DataFrame({"year": summary(b), "Q2 to Q4": summary(b[b["setup_quarter"] >= 2]),
                         "Q1": summary(b[b["setup_quarter"] == 1])}).T.reset_index(names="period")


def by(D, col):
    b = brake(D)
    g = b.groupby(col, observed=True).apply(summary, include_groups=False).reset_index()
    g["ratio_q2_q4"] = g[col].map(b[b["setup_quarter"] >= 2].groupby(col, observed=True)["setup_ratio"].median())
    return g


def tenure_model(D):
    b = brake(D).copy()
    b["lr"] = np.log(b["setup_ratio"])
    b["new"] = (b["tenure_days"] < 365).astype(int)
    b["fam0"] = (b["prior_setups"] == 0).astype(int)
    b["grouped"] = b["same_tooling_as_previous"].astype(int)
    rows = []
    for name, f in (("Tenure only", "lr ~ new"), ("+ familiarity", "lr ~ new + fam0"), ("+ grouping", "lr ~ new + fam0 + grouped"),
                    ("+ machine", "lr ~ new + fam0 + grouped + C(machine_id)"),
                    ("+ lot under 25, bends 6 or more, shift change", "lr ~ new + fam0 + grouped + C(machine_id) + I(qty < 25) + I(bend_count >= 6) + spans_shift_change")):
        m = smf.ols(f, b).fit()
        rows.append(dict(model=name, tenure_effect_log=m.params["new"], tenure_effect_pct=np.exp(m.params["new"]) - 1, std_error=m.bse["new"],
                         share_of_raw_remaining=None))
    t = pd.DataFrame(rows)
    t["share_of_raw_remaining"] = t["tenure_effect_log"] / t["tenure_effect_log"].iloc[0]
    who = b[b["new"] == 1].groupby("setup_employee_id").size().sort_values(ascending=False)
    mix = b.groupby("new").agg(setups=("lr", "size"), fam0=("fam0", "mean"), grouped=("grouped", "mean"), median_ratio=("setup_ratio", "median"))
    place = pd.crosstab(b["machine_id"], b["new"], normalize="columns")
    return t, mix, place, who


def grouping(D):
    b = brake(D)
    rows = []
    for mid, g in list(b.groupby("machine_id")) + [("all brakes", b)]:
        yes, no = g[g["same_tooling_as_previous"]], g[~g["same_tooling_as_previous"]]
        ref = no.groupby("machine_id")["setup_ratio"].median()
        saved = (yes["setup_std"] * yes["machine_id"].map(ref) - yes["setup_hours"]).sum()
        rows.append(dict(machine=mid, setups=len(g), share_grouped=len(yes) / len(g), ratio_grouped=yes["setup_ratio"].median(), ratio_not_grouped=no["setup_ratio"].median(),
                         hours_saved=saved, hours_saved_per_week=saved / WEEKS))
    return pd.DataFrame(rows)


def by_work_center(D):
    g = D["s"].groupby("work_center").apply(summary, include_groups=False).reset_index()
    return g.sort_values("overrun_hours", ascending=False)


def smed(D):
    s = D["s"].copy()
    s["weight"] = s["work_center"].map(D["util"]["utilization"])
    g = s.groupby(["work_center", "part_id", "op_seq"]).agg(family=("family", "first"), setups=("setup_hours", "size"), mean_lot=("qty", "mean"),
                                                            setup_hours=("setup_hours", "sum"), standard_hours=("setup_std", "sum"),
                                                            median_ratio=("setup_ratio", "median"), weight=("weight", "first")).reset_index()
    g["overrun_hours"] = g["setup_hours"] - g["standard_hours"]
    g["score"] = g["overrun_hours"] * g["weight"]
    g["hours_per_week_at_standard"] = g["overrun_hours"] / WEEKS
    g = g.sort_values("score", ascending=False).reset_index(drop=True)
    b = brake(D)
    tot_over = (b["setup_hours"] - b["setup_std"]).sum()
    top = g.head(TOP_N)
    topb = top[top["work_center"] == "press_brake"]
    freq = g[g["work_center"] == "press_brake"].sort_values("setups", ascending=False).head(TOP_N)
    stats = dict(brake_setup_hours=b["setup_hours"].sum(), brake_overrun_hours=tot_over, brake_overrun_per_week=tot_over / WEEKS,
                 top_n=TOP_N, top_overrun_hours=topb["overrun_hours"].sum(), top_hours_per_week=topb["overrun_hours"].sum() / WEEKS,
                 top_share_of_brake_overrun=topb["overrun_hours"].sum() / tot_over, top_setups=int(topb["setups"].sum()),
                 brake_part_operations=int((g["work_center"] == "press_brake").sum()),
                 most_frequent_overrun_hours=freq["overrun_hours"].sum(), most_frequent_share_of_overrun=freq["overrun_hours"].sum() / tot_over,
                 most_frequent_setups=int(freq["setups"].sum()), brake_machine_hours_per_week=float(D["util"].loc["press_brake", "machine_hours"]) / WEEKS,
                 small_lot_overrun_share=(b[b["qty"] < 25]["setup_hours"] - b[b["qty"] < 25]["setup_std"]).sum() / tot_over)
    return g.head(20), stats


def run_standards(D):
    r = D["r"][D["r"]["run_std_hours"] > 0]
    wc = r.groupby("work_center").agg(operations=("run_hours", "size"), run_hours=("run_hours", "sum"), standard_hours=("run_std_hours", "sum")).reset_index()
    wc["run_ratio"] = wc["run_hours"] / wc["standard_hours"]
    wc["ratio_q2_q4"] = wc["work_center"].map(r[r["start_quarter"] >= 2].groupby("work_center").apply(lambda x: x["run_hours"].sum() / x["run_std_hours"].sum(),
                                                                                                    include_groups=False))
    fam = r.groupby(["work_center", "family"]).apply(lambda x: x["run_hours"].sum() / x["run_std_hours"].sum(), include_groups=False).unstack("family")
    las = r[r["work_center"] == "laser"].groupby("machine_id").agg(operations=("run_hours", "size"), run_hours=("run_hours", "sum"),
                                                                  standard_hours=("run_std_hours", "sum")).reset_index()
    las["run_ratio"] = las["run_hours"] / las["standard_hours"]
    return wc.sort_values("run_ratio"), fam.reset_index(), las


def stale(D):
    p = D["parts"][D["parts"]["active"] & D["parts"]["standard_set_date"].notna()]
    pop = dict(active_parts_with_routing=len(p), stale_parts=int((p["standard_set_date"] == p["first_quoted_date"]).sum()),
               stale_share=float((p["standard_set_date"] == p["first_quoted_date"]).mean()))
    r = D["r"][D["r"]["has_routing"]]
    rows = []
    for wc, g in r.groupby("work_center"):
        a, b = g[g["stale_standard"]], g[~g["stale_standard"]]
        rows.append(dict(work_center=wc, operations_stale=len(a), run_ratio_stale=a["run_hours"].sum() / a["run_std_hours"].sum(),
                         run_ratio_refreshed=b["run_hours"].sum() / b["run_std_hours"].sum(),
                         setup_ratio_stale=a["setup_hours"].sum() / a["setup_std"].sum(), setup_ratio_refreshed=b["setup_hours"].sum() / b["setup_std"].sum()))
    ratios = pd.DataFrame(rows)
    ratios["run_gap"] = ratios["run_ratio_stale"] / ratios["run_ratio_refreshed"] - 1
    # refreshing: stale standards scaled so stale parts run at the ratio of refreshed parts at the same work center
    k = ratios.set_index("work_center")
    x = r.copy()
    x["planned"] = x["setup_std"] + x["run_std_hours"]
    f_run = x["work_center"].map(k["run_ratio_stale"] / k["run_ratio_refreshed"])
    f_set = x["work_center"].map(k["setup_ratio_stale"] / k["setup_ratio_refreshed"])
    x["planned_refreshed"] = np.where(x["stale_standard"], x["setup_std"] * f_set + x["run_std_hours"] * f_run, x["planned"])
    by_wc = x.groupby("work_center").agg(planned=("planned", "sum"), refreshed=("planned_refreshed", "sum")).reset_index()
    by_wc["change"] = by_wc["refreshed"] / by_wc["planned"] - 1
    job = x.groupby(["job_id", "routing_class"]).agg(planned=("planned", "sum"), refreshed=("planned_refreshed", "sum"), stale=("stale_standard", "max")).reset_index()
    rc = []
    for c, g in list(job.groupby("routing_class")) + [("all", job)]:
        st = g[g["stale"]]
        rc.append(dict(routing_class=c, jobs=len(g), jobs_on_stale_parts=len(st), hours_per_job=g["planned"].mean(), hours_per_job_refreshed=g["refreshed"].mean(),
                       change_all_jobs=g["refreshed"].sum() / g["planned"].sum() - 1,
                       hours_per_stale_job=st["planned"].mean(), hours_per_stale_job_refreshed=st["refreshed"].mean(),
                       change_stale_jobs=st["refreshed"].sum() / st["planned"].sum() - 1))
    return pop, ratios, by_wc, pd.DataFrame(rc)


def handover(D):
    """Brake setups handed over at a shift boundary, against setups finished by the operator who started them."""
    b = brake(D)
    rows = []
    for name, g in (("Not handed over", b[~b["spans_shift_change"]]), ("Handed over at a shift boundary", b[b["spans_shift_change"]]),
                    ("  afternoon (14:00 to 14:30)", b[b["handover_boundary"] == "afternoon"]), ("  overnight (22:30 to 06:00)", b[b["handover_boundary"] == "overnight"]),
                    ("  other", b[b["handover_boundary"] == "other"]),
                    ("Two-person setup, not handed over", b[b["two_person_setup"] & ~b["spans_shift_change"]])):
        x = summary(g)
        rows.append(dict(setup=name, **x.to_dict(), share_of_setups=len(g) / len(b), share_of_overrun=x["overrun_hours"] / (b["setup_hours"] - b["setup_std"]).sum()))
    return pd.DataFrame(rows)


def handover_start_time(D):
    """Setups by time left in the shift when they started: start time does not depend on how long the setup turns out to be."""
    b = brake(D).dropna(subset=["hours_to_shift_end"]).copy()
    b["started"] = pd.cut(b["hours_to_shift_end"], [0, 0.5, 1, 2, 4, 9], labels=["last 30 minutes", "30 to 60 minutes", "1 to 2 hours", "2 to 4 hours", "over 4 hours"])
    g = b.groupby("started", observed=True).agg(setups=("setup_hours", "size"), share_handed_over=("spans_shift_change", "mean"), median_ratio=("setup_ratio", "median"),
                                                setup_hours=("setup_hours", "sum"), standard_hours=("setup_std", "sum")).reset_index()
    g["hours_weighted_ratio"] = g["setup_hours"] / g["standard_hours"]
    return g


def handover_counterfactual(D):
    b = brake(D)
    mh_week = float(D["util"].loc["press_brake", "machine_hours"]) / WEEKS
    ho, rest = b[b["spans_shift_change"]], b[~b["spans_shift_change"]]
    base = rest["setup_ratio"].median()
    naive = (ho["setup_hours"] - ho["setup_std"] * base).sum()
    # by start time: setups started in the last hour of a shift against those started with more than an hour left
    x = b.dropna(subset=["hours_to_shift_end"])
    late, early = x[x["hours_to_shift_end"] <= 1], x[x["hours_to_shift_end"] > 1]
    r_late, r_early = late["setup_hours"].sum() / late["setup_std"].sum(), early["setup_hours"].sum() / early["setup_std"].sum()
    by_start = (r_late - r_early) * late["setup_std"].sum()
    return pd.DataFrame([
        dict(estimate="Handed-over setups at the median ratio of setups not handed over", basis=f"ratio {base:.2f} on {len(ho):,} setups",
             hours_per_year=naive, hours_per_week=naive / WEEKS, share_of_brake_machine_hours=naive / WEEKS / mh_week),
        dict(estimate="Setups started in the last hour of a shift at the ratio of setups started earlier",
             basis=f"hours-weighted ratio {r_late:.2f} against {r_early:.2f} on {len(late):,} setups, {late['spans_shift_change'].mean():.0%} handed over",
             hours_per_year=by_start, hours_per_week=by_start / WEEKS, share_of_brake_machine_hours=by_start / WEEKS / mh_week)])


def laser_refresh(D):
    """Laser run standards on the two newer lasers set to measured, beside the stale-part refresh, by work center and routing class."""
    r = D["r"][D["r"]["has_routing"]].copy()
    r["planned"] = r["setup_std"] + r["run_std_hours"]
    las = r[r["work_center"] == "laser"]
    f = las.groupby("machine_id").apply(lambda x: x["run_hours"].sum() / x["run_std_hours"].sum(), include_groups=False)
    newer = [m for m in f.index if f[m] < 0.95]
    factor = r["machine_id"].map(f).where(r["machine_id"].isin(newer) & (r["work_center"] == "laser"), 1.0)
    r["laser_refreshed"] = r["setup_std"] + r["run_std_hours"] * factor
    _, ratios, _, _ = stale(D)
    k = ratios.set_index("work_center")
    f_run = r["work_center"].map(k["run_ratio_stale"] / k["run_ratio_refreshed"])
    f_set = r["work_center"].map(k["setup_ratio_stale"] / k["setup_ratio_refreshed"])
    r["stale_refreshed"] = np.where(r["stale_standard"], r["setup_std"] * f_set + r["run_std_hours"] * f_run, r["planned"])
    r["both"] = r["stale_refreshed"] + (r["laser_refreshed"] - r["planned"])
    lz = r["work_center"] == "laser"
    wc = pd.DataFrame([dict(measure="Planned laser hours, current standards", hours=r.loc[lz, "planned"].sum()),
                       dict(measure="With L2 and L3 run standards set to measured", hours=r.loc[lz, "laser_refreshed"].sum()),
                       dict(measure="With stale parts refreshed", hours=r.loc[lz, "stale_refreshed"].sum()),
                       dict(measure="With both", hours=r.loc[lz, "both"].sum())])
    wc["change"] = wc["hours"] / wc["hours"].iloc[0] - 1
    job = r.groupby(["job_id", "routing_class"])[["planned", "laser_refreshed", "stale_refreshed", "both"]].sum().reset_index()
    rc = []
    for c, g in list(job.groupby("routing_class")) + [("all", job)]:
        rc.append(dict(routing_class=c, jobs=len(g), hours_per_job=g["planned"].mean(), laser_refreshed=g["laser_refreshed"].mean(),
                       change_laser=g["laser_refreshed"].sum() / g["planned"].sum() - 1, stale_refreshed=g["stale_refreshed"].mean(),
                       change_stale=g["stale_refreshed"].sum() / g["planned"].sum() - 1, both=g["both"].mean(), change_both=g["both"].sum() / g["planned"].sum() - 1))
    return wc, pd.DataFrame(rc), f, newer


def assignment(D):
    """Brake setups made by an operator with no prior setup of the part, where another current brake operator had set the part up before.

    A matched comparison: the setups are costed at the hours-weighted ratio of setups with prior familiarity in the same lot band and family."""
    allb = q("select job_id, op_seq, part_id, setup_employee_id, setup_start from marts.mart_setups where work_center = 'press_brake'")
    emp = q("select employee_id, shift, termination_date from staging.stg_hr__employees")
    allb = allb.merge(emp, left_on="setup_employee_id", right_on="employee_id", how="left")
    b = brake(D).merge(emp[["employee_id", "shift"]], left_on="setup_employee_id", right_on="employee_id", how="left")
    first = b[(b["prior_setups"] == 0) & (b["routing_class"] == "repeat part")]
    # another operator still employed at the time, with a setup of the part in the trailing 24 months
    m = first[["job_id", "op_seq", "part_id", "setup_employee_id", "setup_start", "shift"]].merge(allb, on="part_id", suffixes=("", "_other"))
    m = m[(m["setup_employee_id_other"] != m["setup_employee_id"]) & (m["setup_start_other"] < m["setup_start"])
          & (m["setup_start_other"] > m["setup_start"] - pd.Timedelta(days=730))
          & (m["termination_date"].isna() | (pd.to_datetime(m["termination_date"]) > m["setup_start"]))]
    any_shift = m[["job_id", "op_seq"]].drop_duplicates().assign(other_any=True)
    same_shift = m[m["shift_other"] == m["shift"]][["job_id", "op_seq"]].drop_duplicates().assign(other_same=True)
    first = first.merge(any_shift, on=["job_id", "op_seq"], how="left").merge(same_shift, on=["job_id", "op_seq"], how="left")
    fam = b[b["prior_setups"] > 0].groupby(["lot_band", "family"], observed=True).apply(lambda x: x["setup_hours"].sum() / x["setup_std"].sum(), include_groups=False)
    first["ref_ratio"] = [fam.get((lb, f), np.nan) for lb, f in zip(first["lot_band"], first["family"])]
    mh_week = float(D["util"].loc["press_brake", "machine_hours"]) / WEEKS
    rows = []
    for name, g in (("First setups of a part by the operator, all brake setups", b[b["prior_setups"] == 0].assign(ref_ratio=np.nan)),
                    ("  of which repeat parts", first),
                    ("  another current brake operator had set the part up, any shift", first[first["other_any"].fillna(False).astype(bool)]),
                    ("  another current brake operator on the same shift had set the part up", first[first["other_same"].fillna(False).astype(bool)])):
        rel = (g["setup_hours"] - g["setup_std"] * g["ref_ratio"]).sum() if g["ref_ratio"].notna().any() else np.nan
        rows.append(dict(setups=name, count=len(g), setup_hours=g["setup_hours"].sum(), standard_hours=g["setup_std"].sum(),
                         hours_weighted_ratio=g["setup_hours"].sum() / g["setup_std"].sum(),
                         ratio_with_familiarity=(g["setup_std"] * g["ref_ratio"]).sum() / g["setup_std"].sum() if g["ref_ratio"].notna().any() else np.nan,
                         hours_released_per_year=rel, hours_released_per_week=rel / WEEKS if rel == rel else np.nan,
                         share_of_brake_machine_hours=rel / WEEKS / mh_week if rel == rel else np.nan))
    return pd.DataFrame(rows)
