"""Scenarios on the validated shop model: 30 replications each on the 2024 to 2025 release stream, with paired differences from current practice.
Each run draws from one generator seeded by its scenario and replication number, so a run repeats exactly.

Usage: python -m analytics.release_control.scenarios [replications] [workers]
"""
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from analytics.release_control.model import Inputs, Shop, generator_seed, measures, quarter_measures

OUT = Path(__file__).resolve().parent / "results" / "scenario_runs.csv"
QUARTERS = Path(__file__).resolve().parent / "results" / "validation_quarters.csv"
PEAK_MONTHS = (11, 12, 1, 2)
MEASURES = ["lead_time_median", "lead_time_p90", "on_time_delivery", "wip_mean", "brake_utilization", "robotic_weld_utilization", "saturday_shifts",
            "extended_hours", "jobs_shipped", "on_time_delivery_load_aware", "promises_longer_than_fixed_quote", "release_hold_days",
            "on_time_delivery_quote_table", "promises_longer_quote_table"]

SCENARIOS = {
    "S0 Current practice": {},
    "S1 WIP cap 240": {"wip_cap": 240},
    "S1 WIP cap 210": {"wip_cap": 210},
    "S1 WIP cap 180": {"wip_cap": 180},
    "S2 Constraint-paced release (3 days of brake work)": {"paced_days": 3.0},
    "S3 Earliest due date": {"dispatch": "edd"},
    "S3 Critical ratio": {"dispatch": "cr"},
    "S3 Shortest processing time, brakes only": {"dispatch": "spt", "dispatch_brakes_only": True},
    "S4 Light work first on B1 and B2 when the B3 to B5 queue exceeds 2 days": {"light_relief_days": 2.0},
    "S5 Second shift on the robotic weld cell": {"second_shift": "R1"},
    "S6 Third weekly color day for black": {"extra_color_day": ("black", 4)},
    "S7 Planned Saturday brake shift, November to February": {"planned_saturday_months": PEAK_MONTHS},
    "S8 Setup reduction": {"setup_reduction": True},
}


def combos(best_cap):
    cap = {"wip_cap": best_cap}
    return {
        f"S10 WIP cap {best_cap} + earliest due date": {**cap, "dispatch": "edd"},
        f"S10 WIP cap {best_cap} + earliest due date + weld second shift": {**cap, "dispatch": "edd", "second_shift": "R1"},
        "S10 Planned Saturdays + light work on B1 and B2": {"planned_saturday_months": PEAK_MONTHS, "light_relief_days": 2.0},
        f"S10 WIP cap {best_cap} + earliest due date + weld second shift + setup reduction": {**cap, "dispatch": "edd", "second_shift": "R1",
                                                                                         "setup_reduction": True},
    }


PACKAGES = {
    "Package 1 Setup reduction + weld second shift": {"setup_reduction": True, "second_shift": "R1"},
    "Package 2 Setup reduction + weld second shift + planned Saturdays": {"setup_reduction": True, "second_shift": "R1", "planned_saturday_months": PEAK_MONTHS},
}


def versus(df, scenario, reference):
    """Paired difference of one scenario from another, by period and measure."""
    out = []
    for period in df["period"].unique():
        a = df[(df["scenario"] == scenario) & (df["period"] == period)].set_index("replication")
        b = df[(df["scenario"] == reference) & (df["period"] == period)].set_index("replication").reindex(a.index)
        for m in MEASURES:
            if m in a and not a[m].isna().all():
                d = a[m] - b[m]
                h = 1.96 * d.std(ddof=1) / np.sqrt(len(d))
                out.append(dict(scenario=scenario, reference=reference, period=period, measure=m, diff=d.mean(), diff_low=d.mean() - h, diff_high=d.mean() + h))
    return pd.DataFrame(out)


_INP = None
_RED = None


def setup_reduction():
    """Top 12 part-operations at standard; the assignment and handover hours taken off the other brake setups in proportion."""
    from analytics.setups import analysis as A
    D = A.load()
    top, st = A.smed(D)
    asg = A.assignment(D).iloc[2]["hours_released_per_year"]
    ho = A.handover_counterfactual(D).iloc[1]["hours_per_year"]
    keys = {(r.part_id, int(r.op_seq)) for r in top.head(A.TOP_N).itertuples() if r.work_center == "press_brake"}
    b = A.brake(D)
    other = b[[(p, int(o)) not in keys for p, o in zip(b["part_id"], b["op_seq"])]]["setup_hours"].sum()
    return dict(at_standard=keys, other_factor=round(1 - (asg + ho) / other, 9))


def run_one(args):
    global _INP, _RED
    name, sc, rep = args
    if _INP is None:
        _INP = Inputs()
    sc = dict(sc)
    if sc.get("setup_reduction") is True:
        if _RED is None:
            _RED = setup_reduction()
        sc["setup_reduction"] = _RED
    shop = Shop(_INP, generator_seed(name, rep), scenario=sc).run()
    rows = []
    for fq, label in ((1, "year"), (2, "Q2 to Q4")):
        m = measures(shop, fq)
        rows.append(dict(scenario=name, replication=rep, period=label, **m))
    quarters = quarter_measures(shop).assign(replication=rep).to_dict("records") if name.startswith("S0") else []
    return rows, quarters


def run(scenarios, reps, workers):
    tasks = [(n, sc, k + 1) for n, sc in scenarios.items() for k in range(reps)]
    rows, quarters = [], []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for i, r in enumerate(ex.map(run_one, tasks, chunksize=2)):
            rows.extend(r[0])
            quarters.extend(r[1])
            if (i + 1) % 30 == 0:
                print(f"{i + 1} of {len(tasks)} runs", flush=True)
    if quarters:
        pd.DataFrame(quarters).to_csv(QUARTERS, index=False)
    return pd.DataFrame(rows)


def summarize(df):
    """Mean and 95% interval per scenario and period, and the paired difference from current practice."""
    base = df[df["scenario"].str.startswith("S0")].set_index(["period", "replication"])
    out = []
    for (name, period), g in df.groupby(["scenario", "period"], sort=False):
        g = g.set_index("replication")
        b = base.loc[period].reindex(g.index)
        n = len(g)
        for m in MEASURES:
            if m not in g or g[m].isna().all():
                continue
            mean, half = g[m].mean(), 1.96 * g[m].std(ddof=1) / np.sqrt(n)
            d = g[m] - b[m] if m in b else g[m] * np.nan
            out.append(dict(scenario=name, period=period, measure=m, mean=mean, low=mean - half, high=mean + half,
                            diff=d.mean(), diff_low=d.mean() - 1.96 * d.std(ddof=1) / np.sqrt(n), diff_high=d.mean() + 1.96 * d.std(ddof=1) / np.sqrt(n)))
    return pd.DataFrame(out)


def best_cap(summary):
    """The cap with the highest Q2 to Q4 on-time delivery among those that ship no fewer jobs than current practice."""
    s = summary[(summary["scenario"].str.startswith("S1 ")) & (summary["period"] == "Q2 to Q4")]
    ok = s[(s["measure"] == "jobs_shipped") & (s["diff_high"] >= 0)]["scenario"]
    otd = s[(s["measure"] == "on_time_delivery") & s["scenario"].isin(ok)].sort_values("mean", ascending=False)
    pick = otd.iloc[0]["scenario"] if len(otd) else s[s["measure"] == "on_time_delivery"].sort_values("mean", ascending=False).iloc[0]["scenario"]
    return int(pick.split()[-1])


if __name__ == "__main__":
    reps = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    out = Path(sys.argv[3]) if len(sys.argv) > 3 else OUT
    only = sys.argv[4].split("|") if len(sys.argv) > 4 else None
    if only:
        every = {**SCENARIOS, **combos(240), **PACKAGES}
        run({n: every[n] for n in only}, reps, workers).to_csv(out, index=False)
        sys.exit(0)
    df = run({**SCENARIOS, **PACKAGES}, reps, workers)
    df.to_csv(out, index=False)
    cap = best_cap(summarize(df))
    print("best cap", cap, flush=True)
    df = pd.concat([df, run(combos(cap), reps, workers)], ignore_index=True)
    df.to_csv(out, index=False)
    print("wrote", out)
