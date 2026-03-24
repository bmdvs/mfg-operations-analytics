"""P4 setups and standards: report, A3 and figures.

Usage: python -m analytics.p4_setups.build
"""
import numpy as np
import pandas as pd

from analytics.p4_setups import analysis as A
from analytics.style.style import ACCENT, AMBER, BRAND_BLUE, DOCS, GREY, LIGHT_BLUE, RED, a3_shell, fig, pct, save, shell, table

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


def fig_conditions(name="p4_overrun_by_condition", h=4.6):
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


def fig_tenure(name="p4_tenure_decomposition", h=3.0):
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
    return save(f, "p4_grouping_by_machine", "Same-tooling grouping by brake")


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
    return save(f, "p4_run_ratio", "Run actual over standard by work center")


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
             d2(r.median_ratio), d1(r.overrun_hours), d2(r.weight), d1(r.score), d2(r.hours_per_week_at_standard)] for r in TOP.itertuples()]
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


# ── report ──────────────────────────────────────────────────────────────────
HEADER_META = (f"Custom sheet-metal fabrication job shop, about 120 employees, one plant. Setups and operations started in {YEAR}; "
               f"records from January 2023 to December 2025.<br>"
               f"Sources: ERP routings and job operations, shop-floor data collection and attendance exports (batch {D['batch']}). "
               f"Hours are machine hours.")


def report():
    y = OV.loc["year"]
    ho, nho = HO.loc["Handed over at a shift boundary"], HO.loc["Not handed over"]
    small = LOT.loc["under 25"]
    cf_naive, cf_start = HCF.iloc[0], HCF.iloc[1]
    late = HST.iloc[0]
    early_med = HST.iloc[2:]["median_ratio"]
    others = BYWC.drop("press_brake")
    b12, b345 = GRP.loc[["B1", "B2"], "share_grouped"], GRP.loc[["B3", "B4", "B5"], "share_grouped"]
    gap = SRAT["run_gap"]
    sall, lall = SRC.set_index("routing_class").loc["all"], LRC.set_index("routing_class").loc["all"]
    other_run = RWC[RWC["work_center"] != "laser"]["run_ratio"]
    bump = small["median_ratio"] / LOT.drop("under 25")["median_ratio"].mean() - 1
    b = []
    b.append("<h2 id='f1'>1. Brake setups against standard</h2>")
    b.append(f"<p>Brake setups ran {n0(y['setup_hours'])} hours against {n0(y['standard_hours'])} standard in {YEAR}: {n0(y['overrun_hours'])} hours over, "
             f"{n0(ST['brake_overrun_per_week'])} a week, {pct(ST['brake_overrun_per_week'] / MH_WEEK, 0)} of brake machine time. The median setup runs at "
             f"{d2(y['median_ratio'])} of standard and the 90th percentile at {d2(y['p90_ratio'])}; no other work center exceeds "
             f"{n0(others['overrun_hours'].max())} overrun hours in the year. Setup ratios do not move with the 2024 year-end build: the median is "
             f"{d2(OV.loc['Q1', 'median_ratio'])} in the first quarter and {d2(OV.loc[REST, 'median_ratio'])} in {REST}.</p>")

    b.append("<h2 id='f2'>2. Where the overrun sits</h2>")
    b.append(f"<p>Setups handed over at a shift boundary are {pct(ho['share_of_setups'], 0)} of setups and {pct(ho['share_of_overrun'], 0)} of the overrun hours, "
             f"median {d2(ho['median_ratio'])} against {d2(nho['median_ratio'])}; most of those hours are long setups that reached the boundary rather than "
             f"the handover itself (section 5). Lots under 25 are {pct(small['setups'] / y['setups'], 0)} of setups and "
             f"{pct(ST['small_lot_overrun_share'], 0)} of the overrun, median {d2(small['median_ratio'])} against "
             f"{d2(LOT.loc['100 and over', 'median_ratio'])} to {d2(LOT.loc['25 to 99', 'median_ratio'])} on larger lots: the setup standards under-plan small lots. "
             f"First setups of a part by the operator run at {d2(FML.loc['none', 'median_ratio'])} against {d2(FML.loc['1 or 2', 'median_ratio'])}. Enclosures and "
             f"chassis run at {d2(FAM.loc['enclosure', 'median_ratio'])} and {d2(FAM.loc['chassis', 'median_ratio'])}; panels and brackets at "
             f"{d2(FAM.loc['panel', 'median_ratio'])} and {d2(FAM.loc['bracket', 'median_ratio'])}.</p>")
    b.append(fig_conditions())
    b.append(f"<div class='caption'>Figure 1. Brake setup hours over standard by condition, {YEAR}, with setup counts and median ratios; the conditions overlap.</div>")

    b.append("<h2 id='f3'>3. Operator tenure</h2>")
    b.append(f"<p>Operators with under 12 months run {pct(TM['tenure_effect_pct'].iloc[0], 0)} above tenured operators before controls and "
             f"{pct(TM['tenure_effect_pct'].iloc[-1], 0)} after familiarity, grouping, machine, lot size, bend count and shift handover. Their "
             f"{n0(MIX.loc[1, 'setups'])} setups of {n0(y['setups'])} were made by {len(WHO)} operators, {n0(WHO.iloc[0])} by one, and "
             f"{pct(PLACE.loc['B4', 1], 0)} were on B4. The tenure effect is mostly what new operators are given, not who they are.</p>")
    b.append(fig_tenure())
    b.append(f"<div class='caption'>Figure 2. Brake setup ratio of operators with under 12 months over tenured operators as controls are added, {YEAR}.</div>")

    b.append("<h2 id='f4'>4. Grouping</h2>")
    ga = GRP.loc["all brakes"]
    b.append(f"<p>{pct(ga['share_grouped'], 0)} of brake setups follow a job on the same tooling set and run at {d2(ga['ratio_grouped'])} of standard against "
             f"{d2(ga['ratio_not_grouped'])}, saving {d1(ga['hours_saved_per_week'])} hours a week. B1 and B2 group {pct(b12.min(), 0)} to {pct(b12.max(), 0)} of their "
             f"setups against {pct(b345.min(), 0)} to {pct(b345.max(), 0)} on B3 to B5: precision work and the hot list come first there.</p>")
    b.append(fig_grouping())
    b.append(f"<div class='caption'>Figure 3. Share of setups grouped on the same tooling set and setup ratio grouped and not grouped, by brake, {YEAR}.</div>")

    b.append("<h2 id='f5'>5. The setup reduction list and the handover</h2>")
    b.append(f"<p>The top {A.TOP_N} part-operations release {d1(ST['top_hours_per_week'])} brake hours a week at standard: {pct(ST['top_share_of_brake_overrun'], 0)} of "
             f"the overrun and {pct(ST['top_hours_per_week'] / MH_WEEK)} of brake machine time. The overrun is spread across {n0(ST['brake_part_operations'])} "
             f"part-operations, so no short list captures most of it.</p>")
    b.append(f"<p>Handed-over setups carry {d1(cf_naive['hours_per_week'])} hours a week above the ratio of setups finished by the operator who started them, but most "
             f"of that is length, not handover: a long setup is the one that reaches the end of the shift. Setups started in the last 30 minutes of a shift are handed "
             f"over {pct(late['share_handed_over'], 0)} of the time and run at a median {d2(late['median_ratio'])} against {d2(early_med.min())} to "
             f"{d2(early_med.max())} for setups started with more than an hour left. On that comparison the handover itself costs "
             f"{d1(cf_start['hours_per_week'])} brake hours a week.</p>")
    b.append(f"<p>{n0(ASG_ANY['count'])} first setups of a repeat part were made while another current brake operator had set the part up in the "
             f"previous 24 months. They ran at {d2(ASG_ANY['hours_weighted_ratio'])} of standard against {d2(ASG_ANY['ratio_with_familiarity'])} for setups with prior "
             f"familiarity in the same lot band and family: {d1(ASG_ANY['hours_released_per_week'])} brake hours a week ({d1(ASG_SAME['hours_released_per_week'])} "
             f"where that operator was on the same shift). This is a matched comparison, not a start-time test, so part of it may be selection.</p>")
    b.append(t_top())
    b.append(f"<div class='caption'>Table 1. The top {A.TOP_N} setup reduction candidates by overrun hours times work center utilization, {YEAR}.</div>")

    b.append("<h2 id='f6'>6. Run standards</h2>")
    b.append(f"<p>{' and '.join(NEWER)} run at {d2(LF[NEWER].mean())} of the run standard and L1 at {d2(LF['L1'])}; every other work center runs at "
             f"{d2(other_run.min())} to {d2(other_run.max())}. {n0(POP['stale_parts'])} of {n0(POP['active_parts_with_routing'])} active parts "
             f"({pct(POP['stale_share'], 0)}) carry a standard dated at first quote and run {pct(gap.min(), 0)} to {pct(gap.max(), 0)} further above standard than "
             f"refreshed parts at the same work center.</p>")
    b.append(fig_run())
    b.append(f"<div class='caption'>Figure 4. Run hours over standard by work center, with the three lasers shown separately, {YEAR}.</div>")

    b.append("<h2 id='f7'>7. Refreshing standards</h2>")
    swc = SWC.set_index("work_center")
    b.append(f"<p>With the stale standards refreshed, planned hours rise {pct(swc.loc['press_brake', 'change'])} at the brakes and "
             f"{pct(swc['change'].min())} to {pct(swc['change'].max())} elsewhere; standard hours per job rise {pct(sall['change_stale_jobs'], 0)} on jobs for those parts "
             f"({pct(sall['jobs_on_stale_parts'] / sall['jobs'], 0)} of jobs) and {pct(sall['change_all_jobs'])} overall. With the {' and '.join(NEWER)} run standards set "
             f"to measured, planned laser hours fall {pct(-LWC['change'].iloc[1])} and standard hours per job fall {pct(-lall['change_laser'])}. Both together move "
             f"standard hours per job by {sp(lall['change_both'])}.</p>")

    b.append("<h2 id='rec'>Recommendation</h2>")
    b.append(f"<p>By measured brake capacity: run the top {A.TOP_N} part-operations at standard as the first targets of the setup reduction program "
             f"({d1(ST['top_hours_per_week'])} hours a week); assign repeat setups to an operator who has set the part up before "
             f"({d1(ASG_ANY['hours_released_per_week'])} hours a week); adopt a shift-handover standard at the brakes, the operator who starts a setup finishing it or "
             f"leaving a written handover at the machine ({d1(cf_start['hours_per_week'])} hours a week). Together these are {d1(LEVERS)} brake hours a week, "
             f"{pct(LEVERS / MH_WEEK)} of brake machine time, and go to P8 as the no-capital alternative.</p>")
    b.append(f"<p>For planning accuracy: raise the setup standard on lots under 25 pieces by {pct(bump, 0)} so the schedule and the quote stop under-planning them; "
             f"refresh the {n0(POP['stale_parts'])} stale standards (up) and set the {' and '.join(NEWER)} run standards to measured (down), with the effect on "
             f"standard hours per job going to estimating (P7).</p>")

    b.append("<h2 id='method'>Method and data</h2>")
    b.append(f"<p>Coverage: {n0(y['setups'])} brake setups and {n0(len(D['s']))} setups at all work centers in {YEAR}; {n0(len(D['r']))} operations for run standards. "
             f"Setup ratio is setup machine hours (the union of setup transactions on the operation) over the setup standard on the job operation; the hours over "
             f"standard ratio is total setup hours over total standard hours.<br>"
             f"A handed-over setup has setup transactions by different operators one after the other (first shift 06:00 to 14:00, second 14:30 to 22:30); transactions "
             f"by two operators at the same time are a two-person setup and are not handovers. Familiarity counts the operator's prior setups of the part in the "
             f"trailing 24 months. A grouped setup follows a job on the same tooling set on the same machine; the tooling set is on the routing for "
             f"{pct(B['tooling_set'].notna().mean())} of brake setups. Hours saved by grouping compare each grouped setup with the median ratio of ungrouped setups on "
             f"the same machine.<br>"
             f"The tenure effect is the coefficient on tenure under 12 months in a regression of log setup ratio, with the controls named. The candidate score is "
             f"overrun hours of the part-operation times the utilization of its work center. The assignment comparison takes first setups of repeat parts where "
             f"another brake operator, still employed, had set the part up in the trailing 24 months, at the hours over standard ratio of setups with prior familiarity "
             f"in the same lot band and family; machine capability and shift are not constrained except where stated. The three capacity figures overlap where a "
             f"setup falls under more than one.<br>"
             f"A stale standard has a standard date equal to the part's first quote date. Refreshing scales the standards of stale parts to the actual-over-standard "
             f"ratio of refreshed parts at the same work center; the laser refresh scales run standards on {' and '.join(NEWER)} to measured run hours.</p>")

    b.append("<h2 id='appendix'>Appendix</h2>")
    b.append("<h3>Table 2. Brake setup against standard by period</h3>" + t_by(OV, "Period", {"year": f"{YEAR}", REST: f"{YEAR} {REST}", "Q1": f"{YEAR} Q1"}, rest=False))
    b.append("<h3>Table 3. Brake setups by part family</h3>" + t_by(FAM, "Family"))
    b.append("<h3>Table 4. Brake setups by lot-size band</h3>" + t_by(LOT, "Lot size"))
    b.append("<h3>Table 5. Brake setups by the operator's prior setups of the part</h3>" + t_by(FML, "Prior setups"))
    b.append("<h3>Table 6. Brake setups by operator tenure, and the tenure effect as controls are added</h3>" + t_by(TEN, "Tenure") + t_tenure())
    b.append("<h3>Table 7. Brake setups handed over at a shift boundary, and by time left in the shift at the start</h3>" + t_handover() + t_start())
    b.append("<h3>Table 8. Brake hours released: the handover and the candidate list</h3>" + t_cf())
    b.append("<h3>Table 8a. First setups of repeat parts where another operator had set the part up</h3>" + t_assign())
    b.append("<h3>Table 9. Same-tooling grouping by brake</h3>" + t_grouping())
    b.append("<h3>Table 10. Setup against standard by work center</h3>" + t_by(BYWC.rename(index=WC), "Work center", rest=False))
    b.append("<h3>Table 11. Setup reduction candidates, top 20</h3>" + t_top20())
    b.append("<h3>Table 12. Run actual against standard by work center and laser</h3>" + t_run())
    b.append("<h3>Table 13. Stale-standard parts against refreshed parts</h3>" + t_stale())
    b.append("<h3>Table 14. Planned operation hours with standards refreshed</h3>" + t_planned())
    b.append("<h3>Table 15. Standard hours per job with standards refreshed, by routing class</h3>" + t_quoted())
    b.append("<div class='glossary'>Setup ratio: setup hours over the setup standard. Overrun hours: setup hours less standard hours. "
             "Stale standard: a standard dated at the part's first quote.</div>")
    toc = [("f1", "Setups against standard"), ("f2", "Where the overrun sits"), ("f3", "Tenure"), ("f4", "Grouping"), ("f5", "Reduction list and handover"),
           ("f6", "Run standards"), ("f7", "Refreshing standards"), ("rec", "Recommendation"), ("method", "Method and data"), ("appendix", "Appendix")]
    (DOCS / "reports").mkdir(parents=True, exist_ok=True)
    (DOCS / "reports" / "p4_setups.html").write_text(shell("Setups and standards", "Project 4 report", HEADER_META, "\n".join(b), toc), encoding="utf8")


COUNTERMEASURES = [
    ("Setup reduction on the top 12 part-operations", "Brake supervisor, manufacturing engineering", "May 2026"),
    ("Assign repeat setups to an operator who has set the part up before", "Brake supervisor", "February 2026"),
    ("Shift-handover standard at the brakes: the starting operator finishes the setup, or a written handover at the machine", "Brake supervisor", "February 2026"),
    ("Correct the setup standard on lots under 25 pieces", "Manufacturing engineering", "March 2026"),
    ("Refresh the stale standards and set the newer lasers' run standards to measured", "Manufacturing engineering, estimating", "April 2026"),
]


def a3():
    y = OV.loc["year"]
    ho, nho = HO.loc["Handed over at a shift boundary"], HO.loc["Not handed over"]
    small = LOT.loc["under 25"]
    ga = GRP.loc["all brakes"]
    cf_naive, cf_start = HCF.iloc[0], HCF.iloc[1]
    left, right = [], []
    left.append(f"<section><h2>Background and problem</h2><p>Brake setups ran {n0(y['overrun_hours'])} hours over standard in {YEAR}: {n0(ST['brake_overrun_per_week'])} "
                f"hours a week and {pct(ST['brake_overrun_per_week'] / MH_WEEK, 0)} of brake machine time.<br>The median setup runs at {d2(y['median_ratio'])} of standard "
                f"and the 90th percentile at {d2(y['p90_ratio'])}; the ratios are the same in the first quarter and in {REST}.</p></section>")
    left.append(f"<section><h2>Current condition</h2>{fig_conditions('p4_a3_overrun_by_condition', 4.0)}"
                f"<div class='caption'>Brake setup hours over standard by condition, {YEAR}, with setup counts and median ratios; the conditions overlap.</div></section>")
    wk = y["setup_hours"] / A.WEEKS
    left.append(f"<section><h2>Target</h2><p>Brake setup hours under {n0(wk - LEVERS)} a week, from {n0(wk)} in {YEAR}. Measured levers: top {A.TOP_N} "
                f"part-operations at standard {d1(ST['top_hours_per_week'])} hours a week; repeat setups assigned to an operator who has set the part up "
                f"{d1(ASG_ANY['hours_released_per_week'])}; shift-handover standard {d1(cf_start['hours_per_week'])}; {d1(LEVERS)} in all.</p></section>")
    right.append(
        f"<section><h2>Analysis</h2>{fig_tenure('p4_a3_tenure_decomposition', 2.3)}<div class='caption'>Brake setup ratio of operators with under 12 months over tenured operators as controls are "
        f"added.</div><ul>"
        f"<li>Handed-over setups are {pct(ho['share_of_setups'], 0)} of setups and {pct(ho['share_of_overrun'], 0)} of the overrun (median {d2(ho['median_ratio'])} "
        f"against {d2(nho['median_ratio'])}); the handover itself costs {d1(cf_start['hours_per_week'])} hours a week, the rest is long setups reaching the shift end.</li>"
        f"<li>Lots under 25 are {pct(small['setups'] / y['setups'], 0)} of setups and {pct(ST['small_lot_overrun_share'], 0)} of the overrun "
        f"(median {d2(small['median_ratio'])}).</li>"
        f"<li>New operators run {pct(TM['tenure_effect_pct'].iloc[0], 0)} above tenured before controls and {pct(TM['tenure_effect_pct'].iloc[-1], 0)} after.</li>"
        f"<li>{pct(ga['share_grouped'], 0)} of setups are grouped on the same tooling set and run at {d2(ga['ratio_grouped'])} against {d2(ga['ratio_not_grouped'])}.</li>"
        f"<li>The top {A.TOP_N} part-operations release {d1(ST['top_hours_per_week'])} hours a week at standard; the overrun is spread across "
        f"{n0(ST['brake_part_operations'])} part-operations.</li></ul></section>")
    right.append(f"<section><h2>Countermeasures</h2>{table(pd.DataFrame(COUNTERMEASURES, columns=['Action', 'Owner', 'When']))}</section>")
    right.append(f"<section><h2>Results</h2><p>Measured baseline for {YEAR}: {n0(y['setup_hours'])} brake setup hours against {n0(y['standard_hours'])} standard. "
                 f"Measured potential: {d1(LEVERS)} brake hours a week from the three capacity levers, {pct(LEVERS / MH_WEEK)} of brake machine time. "
                 f"P8 carries the hours released.</p></section>")
    right.append("<section><h2>Follow-up</h2><p>Weekly brake setup hours, and setup overrun hours by condition once the standards are corrected, "
                 "on the operations dashboard.</p></section>")
    (DOCS / "a3").mkdir(parents=True, exist_ok=True)
    (DOCS / "a3" / "p4_setups.html").write_text(a3_shell("Setups and standards", "Project 4 A3", HEADER_META, "\n".join(left), "\n".join(right)), encoding="utf8")


def main():
    report()
    a3()
    print("wrote docs/reports/p4_setups.html and docs/a3/p4_setups.html")


if __name__ == "__main__":
    main()
