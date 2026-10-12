"""Scenarios on the validated shop model: 30 replications each on the 2024 to 2025 release stream, with paired differences from current practice.
Each run draws from one generator seeded by its scenario and replication number, so a run repeats exactly.

Usage: python -m analytics.release_control.scenarios [replications] [workers]
"""
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from analytics.release_control.model import Inputs, Shop, customer_measures, generator_seed, measures, quarter_measures

OUT = Path(__file__).resolve().parent / "results" / "scenario_runs.csv"
QUARTERS = Path(__file__).resolve().parent / "results" / "validation_quarters.csv"
CUSTOMERS = Path(__file__).resolve().parent / "results" / "customer_delivery.csv"
PEAK_MONTHS = (11, 12, 1, 2)
MEASURES = ["on_time_delivery", "late_jobs", "days_late", "brake_queue_mean", "wip_mean", "brake_utilization", "lead_time_median", "lead_time_p90", "queue_mean_all",
            "robotic_weld_utilization", "laser_utilization", "jobs_shipped", "saturday_shifts", "extended_hours", "release_hold_days"]

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
    "S7 Planned Saturday brake shift on both brakes, November to February": {"planned_saturday_months": PEAK_MONTHS, "planned_saturday_crew": "both"},
    "S8 Setup reduction": {"setup_reduction": True},
}


PACKAGE = "Package Setup reduction + planned Saturdays on both brakes"
PACKAGES = {
    PACKAGE: {"setup_reduction": True, "planned_saturday_months": PEAK_MONTHS, "planned_saturday_crew": "both"},
    "Package + earliest due date": {"setup_reduction": True, "planned_saturday_months": PEAK_MONTHS, "planned_saturday_crew": "both", "dispatch": "edd"},
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
    for fq, label in ((1, "year"), (2, "Q2 to Q4"), (3, "Q3 to Q4")):
        m = measures(shop, fq)
        rows.append(dict(scenario=name, replication=rep, period=label, **m))
    quarters = quarter_measures(shop).assign(replication=rep).to_dict("records") if name.startswith("S0") else []
    customers = [dict(scenario=name, replication=rep, **c) for c in customer_measures(shop)]
    return rows, quarters, customers


def run(scenarios, reps, workers, quarters_to=QUARTERS, customers_to=CUSTOMERS):
    tasks = [(n, sc, k + 1) for n, sc in scenarios.items() for k in range(reps)]
    rows, quarters, customers = [], [], []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for i, r in enumerate(ex.map(run_one, tasks, chunksize=2)):
            rows.extend(r[0])
            quarters.extend(r[1])
            customers.extend(r[2])
            if (i + 1) % 30 == 0:
                print(f"{i + 1} of {len(tasks)} runs", flush=True)
    if quarters and quarters_to is not None:
        pd.DataFrame(quarters).to_csv(quarters_to, index=False)
    pd.DataFrame(customers).to_csv(customers_to, index=False)
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


if __name__ == "__main__":
    reps = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    out = Path(sys.argv[3]) if len(sys.argv) > 3 else OUT
    only = sys.argv[4].split("|") if len(sys.argv) > 4 else None
    every = {**SCENARIOS, **PACKAGES}
    side = out.parent if out != OUT else None                # a second run writes all of its files beside its runs
    run({n: sc for n, sc in every.items() if not only or n in only}, reps, workers, quarters_to=side / QUARTERS.name if side else QUARTERS,
        customers_to=side / CUSTOMERS.name if side else CUSTOMERS).to_csv(out, index=False)
    print("wrote", out)
