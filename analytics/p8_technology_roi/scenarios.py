"""The capital options on the shop model: each alone and on top of the no-capital package, 30 replications, beside current practice and the package.

Usage: python -m analytics.p8_technology_roi.scenarios [replications] [workers]
"""
import sys
from pathlib import Path

import yaml

from analytics.p5_release_control.scenarios import PACKAGES, run

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "results" / "scenario_runs.csv"
ASSUME = yaml.safe_load((ROOT / "p8_assumptions.yaml").read_text(encoding="utf8"))
S0, PACKAGE = "S0 Current practice", "P2 Setup reduction + weld second shift + planned Saturdays"
O = ASSUME["options"]
_factor = 1 - O["press_brake_atc"]["tool_change_share_of_setup"] * O["press_brake_atc"]["tool_change_reduction"]
OPTIONS = {
    "Tool changer on B3": {"tool_changer": {"machines": (O["press_brake_atc"]["replaces"],), "setup_factor": _factor}},
    "Laser tower on L2": {"laser_tower": O["laser_tower"]["laser_fitted"]},
    "Robotic bending cell": {"bending_cell": {"availability": O["robotic_bending_cell"]["added_crewed_hours_per_week"] / 80.0}},
    "Tool changing at every brake setup (upper bound)": {"tool_changer": {"machines": "all", "setup_factor": _factor}},
}
SCENARIOS = {S0: {}, PACKAGE: PACKAGES[PACKAGE]}
SCENARIOS.update({f"T {k}": v for k, v in OPTIONS.items()})
SCENARIOS.update({f"N No-capital package + {k[0].lower() + k[1:]}": {**PACKAGES[PACKAGE], **v} for k, v in OPTIONS.items()})

QUEUE = Path(__file__).resolve().parent / "results" / "laser_queue_november_2024.csv"
_INP = None


def _laser_queue(args):
    """Jobs waiting at the lasers at the end of each day from November 4 to December 13, 2024, from one run stopped at the end of 2024."""
    import pandas as pd
    from analytics.p5_release_control.model import T0, Inputs, Shop, generator_seed
    global _INP
    name, sc, rep = args
    if _INP is None:
        _INP = Inputs()
    shop = Shop(_INP, generator_seed(name, rep), scenario=dict(sc)).run(until="2025-01-01")
    rows = []
    for x in shop.daily:
        day = (T0 + pd.Timedelta(hours=x["t"] - 1)).normalize()
        if pd.Timestamp("2024-11-04") <= day <= pd.Timestamp("2024-12-13"):
            rows.append(dict(scenario=name, replication=rep, day=day.date().isoformat(), jobs_waiting_at_lasers=x.get("laser", 0)))
    return rows


def laser_queue(reps=30, workers=7):
    from concurrent.futures import ProcessPoolExecutor
    import pandas as pd
    names = [S0, "T Laser tower on L2"]
    tasks = [(n, SCENARIOS[n], k + 1) for n in names for k in range(reps)]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        rows = [r for part in ex.map(_laser_queue, tasks, chunksize=2) for r in part]
    pd.DataFrame(rows).to_csv(QUEUE, index=False)


if __name__ == "__main__":
    reps = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    if len(sys.argv) > 3 and sys.argv[3] == "laser_queue":
        laser_queue(reps, workers)
        print("wrote", QUEUE)
        sys.exit(0)
    only = sys.argv[3].split("|") if len(sys.argv) > 3 else None
    out = Path(sys.argv[4]) if len(sys.argv) > 4 else OUT
    df = run({k: v for k, v in SCENARIOS.items() if not only or k in only}, reps, workers)
    df.to_csv(out, index=False)
    print("wrote", out)
