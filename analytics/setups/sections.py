"""Setups and standards: the data, tables and figures of its part of the report.

Built by analytics.reports.capacity_constraints_and_setups.
"""
import numpy as np
import pandas as pd

from analytics.setups import analysis as A
from analytics.style.style import ACCENT, AMBER, BRAND_BLUE, DOCS, GREY, LIGHT_BLUE, RED, fig, pct, save_conformed as save, table

YEAR, REST = A.YEAR, "Q2 to Q4"
WC = {"press_brake": "Press brake", "grind_deburr": "Grind and deburr", "inspection_pack": "Inspection and pack", "hardware": "Hardware", "weld": "Weld",
      "robotic_weld": "Robotic weld", "assembly": "Assembly", "powder_coat": "Powder coat", "laser": "Laser", "punch": "Punch"}


def d1(x):
    return f"{x:.1f}"


def d2(x):
    return f"{x:.2f}"


def n0(x):
    return f"{x:,.0f}"


def sp(x, d=1):
    return f"{x * 100:+.{d}f}%"


D = A.load()
B = A.brake(D)
OV = A.overall(D).set_index("period")
FAM, LOT, FML, TEN = (A.by(D, c).set_index(c) for c in ("family", "lot_band", "familiarity", "tenure"))
TM, MIX, PLACE, WHO = A.tenure_model(D)
HO = A.handover(D).set_index("setup")
HST = A.handover_start_time(D)
HCF = A.handover_counterfactual(D)
GRP = A.grouping(D).set_index("machine")
BYWC = A.by_work_center(D).set_index("work_center")
TOP, ST = A.smed(D)
RWC, RFAM, RLAS = A.run_standards(D)
POP, SRAT, SWC, SRC = A.stale(D)
LWC, LRC, LF, NEWER = A.laser_refresh(D)
ASG = A.assignment(D)
ASG_ANY, ASG_SAME = ASG.iloc[2], ASG.iloc[3]
TOTAL_OVER = float(OV.loc["year", "overrun_hours"])
MH_WEEK = ST["brake_machine_hours_per_week"]
LEVERS = float(ST["top_hours_per_week"] + ASG_ANY["hours_released_per_week"] + HCF.iloc[1]["hours_per_week"])


# ── figures ─────────────────────────────────────────────────────────────────
def conditions():
    rows = [("Handed over at a shift boundary", B[B["spans_shift_change"]]), ("Finished by the operator who started", B[~B["spans_shift_change"]]),
            ("Lot under 25", B[B["qty"] < 25]), ("Lot 25 and over", B[B["qty"] >= 25]),
            ("No prior setup of the part by the operator", B[B["prior_setups"] == 0]), ("One or more prior setups", B[B["prior_setups"] > 0])]
    for f in FAM.sort_values("overrun_hours", ascending=False).index:
        rows.append((f"Family: {f}", B[B["family"] == f]))
    return [(n, len(g), float((g["setup_hours"] - g["setup_std"]).sum()), float(g["setup_ratio"].median())) for n, g in rows]


def fig_conditions(name="setups_overrun_by_condition", h=4.6):
    c = conditions()[::-1]
    f, ax = fig(h=h, grid="x")
    colors = []
    for n, *_ in c:
        colors.append(AMBER if n.startswith("Handed") else BRAND_BLUE if n.startswith("Lot under") else ACCENT if n.startswith("No prior") else
                      LIGHT_BLUE if n.startswith("Family") else GREY)
    ax.barh([x[0] for x in c], [x[2] for x in c], color=colors)
    for i, (n, cnt, hrs, med) in enumerate(c):
        ax.text(hrs + 15, i, f"{cnt:,} setups, median {med:.2f}", va="center", fontsize=8.5, color="#444444")
    ax.set_xlim(0, max(x[2] for x in c) * 1.38)
    ax.set_xlabel(f"Setup hours over standard, {YEAR}")
    f.tight_layout()
    return save(f, name, "Brake setup overrun hours by condition")


def fig_tenure(name="setups_tenure_decomposition", h=3.0):
    f, ax = fig(h=h)
    lab = ["Tenure only", "+ familiarity", "+ grouping", "+ machine", "+ lot size, bends,\nshift handover"]
    v = TM["tenure_effect_pct"].to_numpy() * 100
    ax.bar(lab, v, color=[BRAND_BLUE] + [ACCENT] * 3 + [LIGHT_BLUE])
    for i, x in enumerate(v):
        ax.text(i, x + 0.3, f"+{x:.1f}%", ha="center", fontsize=9.5)
    ax.set_ylabel("New operators over tenured (%)")
    ax.set_ylim(0, v.max() * 1.2)
    f.tight_layout()
    return save(f, name, "Tenure effect on brake setup ratio as controls are added")


def fig_grouping():
    g = GRP.drop("all brakes")
    f, ax = fig(h=3.0)
    x = np.arange(len(g))
    ax.bar(x, g["share_grouped"] * 100, color=LIGHT_BLUE, width=0.55, label="Share of setups grouped (left)")
    ax.set_xticks(x)
    ax.set_xticklabels(g.index)
    ax.set_ylabel("Setups grouped (%)")
    ax2 = ax.twinx()
    ax2.plot(x, g["ratio_grouped"], color=BRAND_BLUE, marker="o", linewidth=0, markersize=7, label="Ratio, grouped (right)")
    ax2.plot(x, g["ratio_not_grouped"], color=AMBER, marker="s", linewidth=0, markersize=7, label="Ratio, not grouped (right)")
    ax2.axhline(1.0, color=GREY, linewidth=1, linestyle="--")
    ax2.set_ylim(0.6, 1.6)
    ax2.set_ylabel("Setup actual over standard")
    ax2.spines["top"].set_visible(False)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, frameon=False, fontsize=8.5, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    f.tight_layout()
    return save(f, "setups_grouping_by_machine", "Same-tooling grouping by brake")


def fig_run():
    w = RWC.set_index("work_center")["run_ratio"].drop("laser")
    rows = [(f"Laser {m}", float(r)) for m, r in zip(RLAS["machine_id"], RLAS["run_ratio"])] + [(WC[k], float(v)) for k, v in w.sort_values().items()]
    f, ax = fig(h=3.2)
    ax.bar([r[0] for r in rows], [r[1] for r in rows], color=[AMBER if r[0] in [f"Laser {m}" for m in NEWER] else ACCENT if r[0].startswith("Laser") else LIGHT_BLUE for r in rows])
    ax.axhline(1.0, color=GREY, linewidth=1, linestyle="--")
    ax.set_ylim(0.6, 1.15)
    ax.set_ylabel("Run actual over standard")
    for lab in ax.get_xticklabels():
        lab.set_rotation(25)
        lab.set_ha("right")
    f.tight_layout()
    return save(f, "setups_run_ratio", "Run actual over standard by work center")


# ── tables ──────────────────────────────────────────────────────────────────
COLS = ["Setups", "Median ratio", "Hours over standard ratio", "90th percentile", "Setup hours", "Standard hours", "Overrun hours"]


def srow(r):
    return [n0(r["setups"]), d2(r["median_ratio"]), d2(r["mean_ratio"]), d2(r["p90_ratio"]), n0(r["setup_hours"]), n0(r["standard_hours"]), n0(r["overrun_hours"])]


def t_by(df, first, labels=None, rest=True):
    rows = []
    for k, r in df.iterrows():
        lab = (labels or {}).get(k, str(k).capitalize() if isinstance(k, str) else str(k))
        rows.append([lab] + srow(r) + ([d2(r["ratio_q2_q4"])] if rest else []))
    return table(pd.DataFrame(rows, columns=[first] + COLS + ([f"Median ratio, {REST}"] if rest else [])))


def t_top():
    rows = [[r.part_id, n0(r.op_seq), r.family.capitalize(), n0(r.setups), n0(r.mean_lot), d1(r.setup_hours), d1(r.standard_hours), d2(r.median_ratio),
             d1(r.overrun_hours), d2(r.hours_per_week_at_standard)] for r in TOP.head(A.TOP_N).itertuples()]
    return table(pd.DataFrame(rows, columns=["Part", "Operation", "Family", "Setups", "Mean lot", "Setup hours", "Standard hours", "Median ratio",
                                             "Overrun hours", "Brake hours a week at standard"]))


def t_top20():
    rows = [[WC[r.work_center], r.part_id, n0(r.op_seq), r.family.capitalize(), n0(r.setups), n0(r.mean_lot), d1(r.setup_hours), d1(r.standard_hours),
             d2(r.median_ratio), d1(r.overrun_hours), f"{r.weight * 100:.0f}%", d1(r.score), d2(r.hours_per_week_at_standard)] for r in TOP.itertuples()]
    return table(pd.DataFrame(rows, columns=["Work center", "Part", "Operation", "Family", "Setups", "Mean lot", "Setup hours", "Standard hours", "Median ratio",
                                             "Overrun hours", "Utilization", "Score", "Hours a week at standard"]))


def t_tenure():
    rows = [[r.model, f"{r.tenure_effect_log:.3f}", sp(r.tenure_effect_pct), f"{r.std_error:.3f}", pct(r.share_of_raw_remaining, 0)] for r in TM.itertuples()]
    return table(pd.DataFrame(rows, columns=["Model", "Tenure effect (log ratio)", "New operators over tenured", "Standard error", "Share of the raw effect remaining"]))


def t_handover():
    rows = [[k.strip().capitalize() if k.startswith("  ") else k] + srow(r) + [pct(r["share_of_setups"]), pct(r["share_of_overrun"])] for k, r in HO.iterrows()]
    return table(pd.DataFrame(rows, columns=["Setup"] + COLS + ["Share of setups", "Share of overrun"]))


def t_start():
    rows = [[str(r.started).capitalize(), n0(r.setups), pct(r.share_handed_over), d2(r.median_ratio), d2(r.hours_weighted_ratio)] for r in HST.itertuples()]
    return table(pd.DataFrame(rows, columns=["Time left in the shift at setup start", "Setups", "Handed over", "Median ratio", "Hours over standard ratio"]))


def t_cf():
    rows = [[r.estimate, r.basis, n0(r.hours_per_year), d1(r.hours_per_week), pct(r.share_of_brake_machine_hours)] for r in HCF.itertuples()]
    rows.append([f"Top {A.TOP_N} setup reduction candidates at standard", f"{ST['top_setups']:,} setups", n0(ST["top_overrun_hours"]), d1(ST["top_hours_per_week"]),
                 pct(ST["top_hours_per_week"] / MH_WEEK)])
    return table(pd.DataFrame(rows, columns=["Estimate", "Basis", "Brake hours a year", "Brake hours a week", "Share of brake machine hours"]))


def t_assign():
    rows = [[r.setups.strip().capitalize() if r.setups.startswith("  ") else r.setups, n0(r["count"]), n0(r.setup_hours), n0(r.standard_hours), d2(r.hours_weighted_ratio),
             d2(r.ratio_with_familiarity) if r.ratio_with_familiarity == r.ratio_with_familiarity else "",
             d1(r.hours_released_per_week) if r.hours_released_per_week == r.hours_released_per_week else "",
             pct(r.share_of_brake_machine_hours) if r.share_of_brake_machine_hours == r.share_of_brake_machine_hours else ""] for _, r in ASG.iterrows()]
    return table(pd.DataFrame(rows, columns=["Setups", "Count", "Setup hours", "Standard hours", "Hours over standard ratio",
                                             "Ratio of setups with prior familiarity, same lot band and family", "Brake hours a week released",
                                             "Share of brake machine hours"]))


def t_grouping():
    rows = [[k if k != "all brakes" else "All brakes", n0(r["setups"]), pct(r["share_grouped"]), d2(r["ratio_grouped"]), d2(r["ratio_not_grouped"]),
             n0(r["hours_saved"]), d1(r["hours_saved_per_week"])] for k, r in GRP.iterrows()]
    return table(pd.DataFrame(rows, columns=["Machine", "Setups", "Grouped", "Median ratio, grouped", "Median ratio, not grouped", "Hours saved", "Hours saved a week"]))


def t_run():
    rows = [[WC[r.work_center], n0(r.operations), n0(r.run_hours), n0(r.standard_hours), f"{r.run_ratio:.3f}", f"{r.ratio_q2_q4:.3f}"] for r in RWC.itertuples()]
    t = table(pd.DataFrame(rows, columns=["Work center", "Operations", "Run hours", "Standard run hours", "Actual over standard", f"Actual over standard, {REST}"]))
    rows = [[f"Laser {r.machine_id}", n0(r.operations), n0(r.run_hours), n0(r.standard_hours), f"{r.run_ratio:.3f}"] for r in RLAS.itertuples()]
    return t + table(pd.DataFrame(rows, columns=["Machine", "Operations", "Run hours", "Standard run hours", "Actual over standard"]))


def t_stale():
    rows = [[WC[r.work_center], n0(r.operations_stale), f"{r.run_ratio_stale:.3f}", f"{r.run_ratio_refreshed:.3f}", sp(r.run_gap), f"{r.setup_ratio_stale:.3f}",
             f"{r.setup_ratio_refreshed:.3f}"] for r in SRAT.itertuples()]
    return table(pd.DataFrame(rows, columns=["Work center", "Operations on stale-standard parts", "Run ratio, stale", "Run ratio, refreshed", "Gap",
                                             "Setup ratio, stale", "Setup ratio, refreshed"]))


def t_planned():
    rows = [[WC[r.work_center], n0(r.planned), n0(r.refreshed), sp(r.change)] for r in SWC.itertuples()]
    t = table(pd.DataFrame(rows, columns=["Work center", "Planned hours", "With stale standards refreshed", "Change"]))
    rows = [[r.measure, n0(r.hours), sp(r.change)] for r in LWC.itertuples()]
    return t + table(pd.DataFrame(rows, columns=["Laser", "Hours", "Change"]))


def t_quoted():
    a, b = SRC.set_index("routing_class"), LRC.set_index("routing_class")
    rows = []
    for c in ["all", "repeat part", "new part", "outside processing"]:
        x, y = a.loc[c], b.loc[c]
        rows.append([c.capitalize(), n0(x["jobs"]), n0(x["jobs_on_stale_parts"]), d2(x["hours_per_job"]), sp(x["change_all_jobs"]), sp(x["change_stale_jobs"]),
                     sp(y["change_laser"]), sp(y["change_both"])])
    return table(pd.DataFrame(rows, columns=["Routing class", "Jobs", "Jobs for stale-standard parts", "Standard hours per job", "Stale parts refreshed, all jobs",
                                             "Stale parts refreshed, their jobs", "L2 and L3 set to measured", "Both"]))
