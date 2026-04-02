"""Capacity, constraints and setups: the report.

Usage: python -m analytics.reports.capacity_constraints_and_setups
"""
import numpy as np
import pandas as pd

from analytics.constraint import analysis as CA
from analytics.constraint import screen as SC
from analytics.constraint import sections as C
from analytics.db import q
from analytics.reports.layout import Tables, block, chart, join_and, link, page, titled
from analytics.setups import analysis as SA
from analytics.setups import sections as S
from analytics.style.style import AMBER, GREY, LIGHT_BLUE, fig, paired_columns, pct, save_conformed as save, table

YEAR, REST, RT = SC.YEAR, "Q2 to Q4", "Q2-Q4"
WC = C.WC
NAME = {"press_brake": "the brakes", "robotic_weld": "the robotic weld cell", "assembly": "assembly", "punch": "the punch", "laser": "the lasers",
        "weld": "the manual weld bays", "grind_deburr": "grind and deburr", "inspection_pack": "inspection and pack", "hardware": "hardware",
        "powder_coat": "the powder line"}
NUMBER = {3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight"}
TIMES = {3: "three", 4: "four", 5: "five", 6: "six"}
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
d1, d2, d3, n0, rng = C.d1, C.d2, C.d3, C.n0, C.rng

X = SC.load()
HOT = SC.hot_weeks(X).set_index(["period", "work_center"])
HY, HR = HOT.loc["year"], HOT.loc[REST]
BY_START, HOURS, BRAKE_HOURS = SC.dispatch(X)
START_Y, START_R = BY_START[BY_START["period"] == "year"].set_index("work_center"), BY_START[BY_START["period"] == REST].set_index("work_center")
NEXT_DAY = SC.next_day_wait(X)
POWDER, POWDER_ALL = SC.powder(X)
ROBOT_BANDS, ROBOT_FAMILIES, ROBOT_STD = SC.bands(X, "robotic_weld"), SC.families(X, "robotic_weld"), SC.against_standard(X, "robotic_weld")
ASM = SC.assembly(X)
LAS = SC.lasers(X)
QSHARE = q("select work_center, share_of_queue from marts.mart_queue_by_work_center where period = 'year'").set_index("work_center")["share_of_queue"]


# ── figures ─────────────────────────────────────────────────────────────────
HOT_ORDER = ["press_brake", "robotic_weld", "assembly", "laser", "punch", "weld"]


def fig_hot():
    f, ax = fig(h=3.7)
    paired_columns(ax, [WC[w] for w in HOT_ORDER], list(HR.loc[HOT_ORDER, "queue_hot"]), list(HR.loc[HOT_ORDER, "queue_other"]),
                   ("Weeks at or above 0.95", "Other weeks"), decimals=2)
    ax.set_ylabel("Queue, working days per operation")
    f.legend(*ax.get_legend_handles_labels(), frameon=False, fontsize=9, ncol=2, loc="lower center")
    f.tight_layout(rect=(0, 0.06, 1, 1))
    return save(f, "capacity_queue_in_hot_weeks", "Queue in Hot Weeks and Other Weeks by Work Center, Q2-Q4 2025")


def fig_assembly():
    w = X["uw"][X["uw"]["work_center"] == "assembly"].sort_values("week_start")
    f, ax = fig(h=3.3)
    ax.bar(w["week_start"], w["utilization"], width=5, color=LIGHT_BLUE, label="Utilization (left)")
    ax.axhline(0.95, color=GREY, linewidth=1, linestyle="--")
    ax.set_ylabel("Utilization")
    ax.set_ylim(0, 1.3)
    ax2 = ax.twinx()
    ax2.plot(w["week_start"], w["queue_mean"], color=AMBER, linewidth=1.4, label="Queue per operation (right)")
    ax2.set_ylabel("Working days")
    ax2.spines["top"].set_visible(False)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, frameon=False, fontsize=9, ncol=2, loc="upper left")
    f.tight_layout()
    return save(f, "capacity_assembly_weekly", "Assembly Weekly Utilization and Queue")


# ── the new appendix tables ─────────────────────────────────────────────────
def blank(v, f=d2):
    return f(v) if v == v else ""


def t_hot():
    out = ""
    for per, H in ((f"{YEAR}", HY), (f"{YEAR} {REST}", HR)):
        rows = [[WC[w], d3(r["utilization"]), f"{int(r['hot_weeks'])} of {int(r['weeks'])}", n0(r["hot_full_weeks"]), blank(r["queue_hot"]), d2(r["queue_other"]),
                 pct(r["hours_share_hot"], 0)] for w, r in H.sort_values("utilization", ascending=False).iterrows()]
        out += block(per, table(pd.DataFrame(rows, columns=["Work center", "Utilization", "Weeks at 0.95 or above", "Of which full five-day weeks",
                                                             "Queue in those weeks", "Queue in the other weeks", "Share of machine hours in those weeks"])))
    return out


def t_dispatch():
    out = ""
    for per, T in ((f"{YEAR}", START_Y), (f"{YEAR} {REST}", START_R)):
        rows = [[WC[w], n0(r["operations"]), pct(r["same_share"], 0), d2(r["same_queue"]), pct(r["next_share"], 0), d2(r["next_queue"]), pct(r["later_share"], 0),
                 d2(r["later_queue"]), pct(r["after_10"], 0), pct(r["after_14"], 0)] for w, r in T.loc[SC.LIST_CENTERS].iterrows()]
        out += block(per, table(pd.DataFrame(rows, columns=["Work center", "Operations", "Start the same working day", "Queue, same day", "Start the next working day", "Queue, next day",
                                                             "Start later", "Queue, later", "Arrive after 10:00", "Arrive after 14:00"])))
    rows = [[k, pct(r["share"], 0), pct(r["same_day"], 0), d2(r["queue"]), pct(BRAKE_HOURS.loc[k, "same_day"], 0)] for k, r in HOURS.iterrows()]
    return out + block(f"The four work centers together by hour of arrival, {YEAR}, with the brakes beside them",
                       table(pd.DataFrame(rows, columns=["Arrival", "Share of arrivals", "Start the same day", "Queue", "Start the same day, press brake"])))


def t_powder():
    rows = [[k.capitalize(), n0(r["operations"]), d1(r["days_per_week"]), r["weekdays"], d2(r["wait_mean"]), pct(r["day_or_more"], 0), pct(r["share_of_wait"], 0)]
            for k, r in POWDER.iterrows()]
    rows.append(["All", n0(POWDER_ALL["operations"]), "", "", d2(POWDER_ALL["wait_mean"]), pct(POWDER_ALL["day_or_more"], 0), "100%"])
    return table(pd.DataFrame(rows, columns=["Color", "Operations", "Scheduled days a week", "Days", "Wait for the color day, mean", "Waiting a day or more",
                                             "Share of the color-day wait"]))


def t_robot():
    rows = [[k, n0(r["weeks"]), n0(r["full_weeks"]), n0(r["operations"]), blank(r["queue"])] for k, r in ROBOT_BANDS.iterrows()]
    a = table(pd.DataFrame(rows, columns=["Utilization in the week", "Weeks", "Of which full five-day weeks", "Operations", "Queue per operation"]))
    rows = [[k.capitalize(), n0(r["operations"]), n0(r["hours"]), pct(r["share"], 0), d2(r["queue"])] for k, r in ROBOT_FAMILIES.iterrows()]
    b = table(pd.DataFrame(rows, columns=["Part family", "Operations", "Machine hours", "Share of hours", "Queue per operation"]))
    s = ROBOT_STD
    c = table(pd.DataFrame([["Setup", n0(s["setup_hours"]), n0(s["setup_standard"]), d2(s["setup_ratio"])], ["Run", n0(s["run_hours"]), n0(s["run_standard"]), d2(s["run_ratio"])]],
                           columns=["", "Hours", "Standard hours", "Hours over standard"]))
    return block(f"Weeks by utilization band, {YEAR}", a) + block(f"Hours by part family, {YEAR}", b) + block(f"Setup and run against standard, {YEAR}", c)


def t_assembly():
    rows = [[str(y), d3(r["utilization"]), d2(r["queue"]), f"{int(r['hot_weeks'])} of {int(r['weeks'])}", n0(r["operations"])] for y, r in ASM["years"].iterrows()]
    a = table(pd.DataFrame(rows, columns=["Year", "Utilization", "Queue per operation", "Weeks at 0.95 or above", "Operations"]))
    h, o = ASM["compare"]["hot"], ASM["compare"]["other"]
    rows = [["Weeks", n0(h["weeks"]), n0(o["weeks"])], ["Utilization", d2(h["utilization"]), d2(o["utilization"])], ["Queue per operation", d2(h["queue"]), d2(o["queue"])],
            ["Arrivals a week", d1(h["arrivals"]), d1(o["arrivals"])],
            ["Arrivals a week on jobs routed through the robotic weld cell", d1(h["robot_arrivals"]), d1(o["robot_arrivals"])],
            ["Robotic weld cell share of arrivals", pct(h["robot_share"], 0), pct(o["robot_share"], 0)],
            ["Machine hours per operation", d2(h["hours_per_operation"]), d2(o["hours_per_operation"])]]
    b = table(pd.DataFrame(rows, columns=["", "Weeks at 0.95 or above", "Other weeks"]))
    rows = [[k, n0(r["operations"]), pct(r["share_of_hours"], 0), d2(r["queue"]), d1(r["p90"])] for k, r in ASM["origin"].sort_values("operations", ascending=False).iterrows()]
    c = table(pd.DataFrame(rows, columns=["Weld on the job's routing", "Operations", "Share of assembly hours", "Queue per operation", "90th percentile"]))
    rows = [[WC.get(k, "Outside processing" if k == "outside_processing" else k), pct(v, 0)] for k, v in ASM["previous"].items()]
    d = table(pd.DataFrame(rows, columns=["Operation before assembly", "Share of assembly operations"]))
    rows = [[k.capitalize(), n0(r["operations"]), n0(r["hours"]), pct(r["share"], 0)] for k, r in ASM["families"].iterrows()]
    e = table(pd.DataFrame(rows, columns=["Part family", "Operations", "Machine hours", "Share of hours"]))
    g = table(pd.DataFrame([[k, d2(v)] for k, v in ASM["corr"].items()], columns=[f"Across the weeks of {YEAR}", "Correlation"]))
    return (block("By year", a) + block(f"Weeks at 0.95 or above against the other weeks, {YEAR}", b) + block(f"Where assembly's work comes from, {YEAR}", c + d)
            + block(f"Hours by part family, {YEAR}", e) + block("Weekly correlations", g))


def t_lasers():
    rows = [[MONTHS[m - 1], n0(r["first_operations"]), d2(r["queue"]), d1(r["p90"]), d2(r["material_wait"]), pct(r["with_wait"], 0), d2(r["utilization"])]
            for m, r in LAS["month"].iterrows()]
    for per, label in (("year", f"{YEAR}"), (REST, f"{YEAR} {REST}")):
        r = LAS["period"][per]
        rows.append([label, n0(r["first_operations"]), d2(r["queue"]), d1(r["p90"]), d2(r["material_wait"]), pct(r["with_wait"], 0), ""])
    a = table(pd.DataFrame(rows, columns=["Month of the first cut", "First operations", "First-operation queue, mean", "90th percentile", "Material wait, mean",
                                          "First operations with a material wait", "Laser utilization"]))
    rows = [[k, n0(r["scheduled"]), n0(r["machine"]), pct(r["share_of_hours"], 0), d2(r["utilization"]), d2(r["uptime"]), n0(r["run_hours"]), n0(r["standard_hours"]),
             d2(r["run_ratio"]), pct(r["share_of_standard"], 0)] for k, r in LAS["machines"].iterrows()]
    m = LAS["machines"]
    rows.append(["All", n0(m["scheduled"].sum()), n0(m["machine"].sum()), "100%", "", "", n0(m["run_hours"].sum()), n0(m["standard_hours"].sum()),
                 d2(m["run_hours"].sum() / m["standard_hours"].sum()), "100%"])
    b = table(pd.DataFrame(rows, columns=["Laser", "Scheduled hours", "Machine hours", "Share of laser hours", "Utilization", "Uptime", "Run hours",
                                          "Run standard hours", "Run hours over standard", "Share of laser standard hours"]))
    return block(f"By month, {YEAR}", a) + block(f"The three machines, {YEAR}", b)


# ── the report ──────────────────────────────────────────────────────────────
def build():
    T = Tables()
    T.add("util", "Utilization and machine uptime by work center", C.t_util())
    T.add("pos", "Position of each work center on its curve", C.t_pos())
    T.add("hot", "Weekly utilization at or above 0.95 by work center: weeks, queue and share of hours", t_hot())
    T.add("bins", "Weekly brake queue by utilization band, full weeks 2023 to 2025", C.t_bins())
    T.add("fits", "Fitted queue curve by work center", C.t_fits())
    T.add("dispatch", "The dispatch-list work centers: start day, queue and hour of arrival", t_dispatch())
    T.add("powder", "The powder line by color", t_powder())
    T.add("var", f"Variability sources, {YEAR}", C.t_var())
    T.add("spread", "Brake queue with the spread of setup time halved, and the inputs", C.t_setup())
    T.add("machines", f"Utilization and queue per operation for the five brakes and the robotic weld cell, {YEAR} and {REST}", C.t_machines())
    T.add("basis", "The brakes and the robotic weld cell: hours and utilization on both bases", C.t_machine_basis())
    T.add("robot", "The robotic weld cell: weeks by utilization band, hours by part family, setup and run against standard", t_robot())
    T.add("assembly", "Assembly: hot weeks, where its work comes from, and the weekly correlations", t_assembly())
    T.add("laser_weeks", "Laser weeks, November and December 2024", C.t_laser())
    T.add("lasers", "The lasers: first-operation queue and material wait by month, and the three machines", t_lasers())
    T.add("bywc", "Setup against standard by work center", S.t_by(S.BYWC.rename(index=S.WC), "Work center", rest=False))
    T.add("period", "Brake setup against standard by period", S.t_by(S.OV, "Period", {"year": f"{YEAR}", REST: f"{YEAR} {REST}", "Q1": f"{YEAR} Q1"}, rest=False))
    T.add("handover", "Brake setups handed over at a shift boundary, and by time left in the shift at the start", S.t_handover() + S.t_start())
    T.add("lot", "Brake setups by lot-size band", S.t_by(S.LOT, "Lot size"))
    T.add("familiarity", "Brake setups by the operator's prior setups of the part", S.t_by(S.FML, "Prior setups"))
    T.add("family", "Brake setups by part family", S.t_by(S.FAM, "Family"))
    T.add("tenure", "Brake setups by operator tenure, and the tenure effect as controls are added", S.t_by(S.TEN, "Tenure") + S.t_tenure())
    T.add("assign", "First setups of repeat parts where another operator had set the part up", S.t_assign())
    T.add("grouping", "Same-tooling grouping by brake", S.t_grouping())
    T.add("top12", f"The top {SA.TOP_N} setup reduction candidates by overrun hours times work center utilization, {YEAR}", S.t_top())
    T.add("top20", "Setup reduction candidates, top 20", S.t_top20())
    T.add("released", "Brake hours released: the handover and the candidate list", S.t_cf())
    T.add("run", "Run actual against standard by work center and laser", S.t_run())
    T.add("stale", "Stale-standard parts against refreshed parts", S.t_stale())
    T.add("planned", "Planned operation hours with standards refreshed", S.t_planned())
    T.add("quoted", "Standard hours per job with standards refreshed, by routing class", S.t_quoted())

    UY, UR, MY, MR, PY, PR, FB = C.UY, C.UR, C.MY, C.MR, C.PY, C.PR, C.FB
    ops = C.D["ops"]
    y = S.OV.loc["year"]
    others_setup = S.BYWC.drop("press_brake")
    other_run = S.RWC[S.RWC["work_center"] != "laser"]["run_ratio"]
    newer = " and ".join(S.NEWER)
    b = []

    # 1 ── the screen
    b.append("<h2 id='f1'>1. The Screen</h2>")
    mid = UY.drop(["press_brake", "robotic_weld", "laser", "powder_coat"])
    b.append(f"<p>{n0(len(ops))} operations started in {YEAR} at ten work centers, {n0((ops['start_quarter'] >= 2).sum())} of them in {REST}. Utilization is machine "
             f"hours over scheduled hours net of downtime, Saturday and extended shifts included; uptime is one less downtime over scheduled hours. Queue is the end "
             f"of the previous operation to the first start of this one, less the powder color-day wait; for the lasers it is traveler print to first cut, less "
             f"material wait. The brakes run at {d2(UY.loc['press_brake', 'utilization'])} of scheduled hours net of downtime, the robotic weld cell at "
             f"{d2(UY.loc['robotic_weld', 'utilization'])}, the lasers at {d2(UY.loc['laser', 'utilization'])}, assembly through hardware at "
             f"{rng(mid['utilization'].min(), mid['utilization'].max())} and the powder line at {d2(UY.loc['powder_coat', 'utilization'])}. "
             f"Machine uptime is {rng(UY['uptime'].min(), UY['uptime'].max())} at every work center and does not distinguish the constraint. {T.see('util')}</p>")
    b.append(titled(C.fig_util(), "Utilization and Machine Uptime by Work Center"))

    hot_y = HY[HY["hot_weeks"] > 0].sort_values("hot_weeks", ascending=False)
    never = [w for w in ("inspection_pack", "hardware", "powder_coat") if HY.loc[w, "hot_weeks"] == 0]
    assert len(never) == 3 and len(hot_y) == 7 and set(HR[HR["hot_weeks"] > 0].index) == set(HOT_ORDER), (list(hot_y.index), never)
    weeks = int(HY["weeks"].iloc[0])
    counted = [f"{NAME[w]} in {int(r['hot_weeks'])}" + (f" weeks of {weeks}" if k == 0 else "") for k, (w, r) in enumerate(hot_y.iterrows())]
    pair = lambda w: f"{d2(HR.loc[w, 'queue_hot'])} against {d2(HR.loc[w, 'queue_other'])}"
    assert all(HR.loc[w, "queue_hot"] > HR.loc[w, "queue_other"] for w in HOT_ORDER) and HY.loc["press_brake", "queue_hot"] < HY.loc["press_brake", "queue_other"]
    b.append(f"<p>{NUMBER[len(hot_y)]} work centers reached 0.95 utilization in at least one week of {YEAR}: {join_and(counted)}; {join_and(NAME[w] for w in never)} "
             f"never did. In {REST} a hot week shows as a queue at each of the six that had one: {d2(HR.loc['press_brake', 'queue_hot'])} days per operation at the "
             f"brakes against {d2(HR.loc['press_brake', 'queue_other'])} in the other weeks, {pair('robotic_weld')} at the robotic weld cell, {pair('assembly')} at "
             f"assembly, {pair('punch')} at the punch, {pair('laser')} at the lasers and {pair('weld')} at the manual weld bays. For the full year the brakes read "
             f"the other way ({d2(HY.loc['press_brake', 'queue_hot'])} against {d2(HY.loc['press_brake', 'queue_other'])}) because the first-quarter backlog kept "
             f"the queue long whatever the week's utilization. Hot weeks carry {pct(HR.loc['press_brake', 'hours_share_hot'], 0)} of brake hours and "
             f"{pct(HR.loc['robotic_weld', 'hours_share_hot'], 0)} of the weld cell's in {REST}, {pct(HR.loc['punch', 'hours_share_hot'], 0)} of the punch's and "
             f"{pct(HR.loc['assembly', 'hours_share_hot'], 0)} of assembly's. {T.see('pos', 'hot')}</p>")
    b.append(chart("Queue in Hot Weeks and Other Weeks by Work Center, Q2-Q4 2025", fig_hot()))

    ah, ao = ASM["compare"]["hot"], ASM["compare"]["other"]
    assert PR["queue_measured"].idxmax() == "robotic_weld"
    listed = UY.loc[SC.LIST_CENTERS, "utilization"]
    b.append(f"<p>Three work centers are followed in <a href='#f3'>Section 3</a>. The brakes run at {d2(UY.loc['press_brake', 'utilization'])} and carry "
             f"{pct(QSHARE['press_brake'], 0)} of all queue time. The robotic weld cell runs at {d2(UY.loc['robotic_weld', 'utilization'])} on one shift and has the "
             f"longest queue in the shop in {REST}. Assembly runs at {d2(UY.loc['assembly', 'utilization'])} for the year but at {d2(ah['utilization'])} in its "
             f"{int(ah['weeks'])} hot weeks, when its queue is {TIMES[round(ah['queue'] / ao['queue'])]} times the other weeks'. The lasers matter at the year-end peak and are "
             f"followed there. The punch is one machine at {d2(UY.loc['punch', 'utilization'])} whose hot weeks raise a short queue "
             f"{TIMES[round(HR.loc['punch', 'queue_hot'] / HR.loc['punch', 'queue_other'])]}fold; it is left at that. Grind and deburr, inspection and pack, hardware "
             f"and the manual weld bays carry {join_and(pct(QSHARE[w], 0) for w in SC.LIST_CENTERS)} of queue time at {rng(listed.min(), listed.max())} utilization, "
             f"and their queues are set by the daily dispatch list rather than by load (<a href='#f2'>Section 2</a>); the powder line runs at "
             f"{d2(UY.loc['powder_coat', 'utilization'])} and holds jobs for the color day.</p>")
    b.append(f"<p>Brake setups ran {n0(y['overrun_hours'])} hours over standard in {YEAR}; no other work center exceeds {n0(others_setup['overrun_hours'].max())}. "
             f"Run standards are within {pct(other_run.min() - 1, 0)} to {pct(other_run.max() - 1, 0)} of actual at every work center except the lasers, where "
             f"{newer} run at {d2(S.LF[S.NEWER].mean())} (<a href='#f4'>Sections 4</a> and <a href='#f5'>5</a>).</p>")

    # 2 ── queue against load
    b.append("<h2 id='f2'>2. Queue Against Load</h2>")
    lo = C.BINS.iloc[:2]
    below = float((lo["queue_mean"] * lo["weeks"]).sum() / lo["weeks"].sum())
    step = float(C.BINS.iloc[2]["queue_mean"])
    b.append(f"<p>The curve gives the queue expected at a utilization for the number of machines at the work center, with its scale fitted on rolling 13-week "
             f"windows of 2023 to 2025. On the fitted curve the brake queue is {d2(FB['queue_at_0.75'])} days per operation at 0.75 utilization, "
             f"{d2(FB['queue_at_0.85'])} at 0.85, {d2(FB['queue_at_0.90'])} at 0.90 and {d2(FB['queue_at_0.92'])} at 0.92; the measured queue is "
             f"{d2(PY.loc['press_brake', 'queue_measured'])} at {d3(PY.loc['press_brake', 'utilization'])} for the year and "
             f"{d2(PR.loc['press_brake', 'queue_measured'])} at {d3(PR.loc['press_brake', 'utilization'])} in {REST}. Week by week, the brake queue steps from about "
             f"{d1(below)} days below 0.85 utilization to {d1(step)} above it and does not settle back. {T.see('bins', 'fits')}</p>")
    b.append(titled(C.fig_curve(), "Brake Queue Against Utilization"))
    b.append("<p>The curve does not describe hardware, grind and deburr, inspection and pack, or the powder line: their queues follow the daily dispatch list and "
             "the color schedule, not load.</p>")
    BQ = C.BQ
    b.append(f"<p>The brake queue's 90th percentile was {d1(BQ.loc[1, 'queue_p90'])} and {d1(BQ.loc[2, 'queue_p90'])} days in Q1 and Q2 {YEAR} and "
             f"{d1(BQ.loc[3, 'queue_p90'])} and {d1(BQ.loc[4, 'queue_p90'])} in Q3 and Q4; under 5 days in every quarter is the mark the levers in this report are "
             f"measured against.</p>")

    b.append("<h3 id='f2_1'>Queues made by the list, not by load</h3>")
    share = lambda Tb, c: f"{pct(Tb[c].min(), 0)} to {pct(Tb[c].max(), 0)}"
    early, mid_day, late = HOURS.iloc[:3], HOURS.iloc[3:5], HOURS.iloc[5:]
    same = lambda g: float((g["same_day"] * g["arrivals"]).sum() / g["arrivals"].sum())
    assert 0.85 <= same(early) < 0.95 and 0.25 <= same(mid_day) < 0.35, (same(early), same(mid_day))
    assert set(X["shifts"].set_index("work_center").loc[SC.LIST_CENTERS, "shifts"]) == {1}          # one shift at each, so no crew for a list at 14:00
    brake_day = BRAKE_HOURS.iloc[1:5]["same_day"]
    next_queue = float((START_Y["next_queue"] * START_Y["next_share"] * START_Y["operations"]).sum() / (START_Y["next_share"] * START_Y["operations"]).sum())
    b.append(f"<p>At grind and deburr, inspection and pack, hardware and the manual weld bays, {share(START_Y, 'next_share')} of operations start on the working day "
             f"after they arrive and wait about {d1(next_queue)} days to do so; {share(START_Y, 'same_share')} start the same day, within half a day; "
             f"{share(START_Y, 'later_share')} wait longer. The split is the same in {REST} ({share(START_R, 'next_share')} next day). What decides it is the hour of "
             f"arrival, not the load: work arriving before 10:00 starts the same day nine times in ten, work arriving between 10:00 and 14:00 "
             f"({pct(mid_day['share'].sum(), 0)} of arrivals) starts the same day about three times in ten, and the {pct(late['share'].sum(), 0)} arriving after the "
             f"shift ends starts the next morning. The brakes show no such break; {pct(brake_day.min(), 0)} to {pct(brake_day.max(), 0)} of their arrivals start the "
             f"same day in every band from 06:00 to 14:00. Across a shipped job, these next-day waits add {d1(NEXT_DAY['year'])} working days of lead time "
             f"({d1(NEXT_DAY[REST])} in {REST}). {T.see('dispatch')}</p>")
    b.append(f"<p>The lever is the list, not capacity. A midday refresh of the day's list at these four work centers lets the arrivals between 10:00 and 12:00, "
             f"{pct(HOURS.iloc[3]['share'], 0)} of the total, start the same afternoon; what arrives after the shift ends can only start the next morning.</p>")
    two, one = POWDER[POWDER["days_per_week"] > 1.5], POWDER[POWDER["days_per_week"] <= 1.5]
    assert list(two.index) == ["black", "white", "gray"] and sorted(one.index) == ["beige", "blue", "red"]
    b.append(f"<p>The powder line's color-day wait is {d2(POWDER_ALL['wait_mean'])} days per operation and {pct(POWDER_ALL['day_or_more'], 0)} of operations wait a day "
             f"or more. Black, white and gray run two days a week and wait {rng(two['wait_mean'].min(), two['wait_mean'].max())} days; beige, blue and red run once a "
             f"week, wait {rng(one['wait_mean'].min(), one['wait_mean'].max(), d1)} days, and {share(one, 'day_or_more')} of their operations wait a day or more. The "
             f"three once-a-week colors are {pct(one['share_of_operations'].sum(), 0)} of operations and {pct(one['share_of_wait'].sum(), 0)} of the wait; black is "
             f"{pct(POWDER.loc['black', 'share_of_wait'], 0)} of the wait on volume alone. A third day for black was tested in {link('options')} and does not move "
             f"on-time delivery. {T.see('powder')}</p>")

    b.append("<h3 id='f2_2'>Variability</h3>")
    SV, var = C.SV, C.var
    b.append(f"<p>Halving the spread of brake setup time (each setup time moved halfway to the mean) releases {d1(SV.loc['year', 'hours_per_week_released'])} brake "
             f"hours a week and cuts the queue on the curve from {d2(SV.loc['year', 'queue_on_curve'])} to {d2(SV.loc['year', 'queue_with_half_setup_spread'])} days. "
             f"The variability at the brakes is in arrivals (daily coefficient of variation {d2(var('Arrivals: jobs released per working day'))}, Mondays "
             f"{d2(var('Arrivals: Monday'))} times the daily mean, the top customer's month-end {d2(var('Arrivals: top customer'))} times) and in run time "
             f"(coefficient of variation {d2(var('Brake run time'))} against {d2(var('Brake setup time'))} for setup). This is the spread of setup time, not its mean; "
             f"the mean is the subject of <a href='#f4'>Section 4</a>. Second-shift absence is {pct(var('Absence, second shift: share'), 0)} against "
             f"{pct(var('Absence, first shift: share'), 0)} on first shift. {T.see('var', 'spread')}</p>")
    b.append("<p>The brake queue is set by arrival variability and by load above 0.85, so capacity at the constraint is the lever: the setup program of "
             "<a href='#f4'>Section 4</a> and planned Saturday brake shifts for the peak, both tested in Options Tested. Release leveling and dispatch rules do not "
             "help this shop, and reducing the spread of setup time is not a lever.</p>")

    # 3 ── the constraints
    b.append("<h2 id='f3'>3. The Constraints</h2>")
    b.append("<h3 id='f3_1'>The five brakes</h3>")
    tail = MY.loc[["B3", "B4", "B5"]]
    top_y = MY.loc[C.BRAKES, "utilization"].sort_values(ascending=False).index.tolist()
    b.append(f"<p>B1 and B2 run at {d3(MY.loc['B1', 'utilization'])} and {d3(MY.loc['B2', 'utilization'])} for the year and "
             f"{d3(MR.loc['B1', 'utilization'])} and {d3(MR.loc['B2', 'utilization'])} in {REST}, with the shortest queues of the five "
             f"(mean {d1(MY.loc['B1', 'queue_mean'])} and {d1(MY.loc['B2', 'queue_mean'])} days): precision work goes to them first and the hot list sends "
             f"expedited work to them. B3 to B5 carry the tail: mean {rng(tail['queue_mean'].min(), tail['queue_mean'].max(), d1)} days and 90th percentile "
             f"{rng(tail['queue_p90'].min(), tail['queue_p90'].max(), d1)}. "
             + (f"Over all hours worked, {top_y[0]} carries the highest load of the five for the year; in {REST} B1 and B2 do. " if top_y[0] not in ("B1", "B2") else "")
             + f"On crewed weekday shifts only, B1 and B2 run at {d3(MY.loc['B1', 'utilization_weekday_basis'])} and {d3(MY.loc['B2', 'utilization_weekday_basis'])} "
             f"for the year. {T.see('machines', 'basis')}</p>")

    b.append("<h3 id='f3_2'>The robotic weld cell</h3>")
    ROB = C.ROB
    b.append(f"<p>In {REST} the robotic weld cell has the longest queue in the shop: {d1(ROB.loc[REST, 'queue_mean'])} days per operation against "
             f"{d1(UR.loc['press_brake', 'queue_mean'])} at the brakes, on one shift at {d2(ROB.loc[REST, 'utilization'])} utilization. It ran at or above 0.95 in "
             f"{int(ROB.loc[REST, 'weeks_at_0_95'])} of {int(ROB.loc[REST, 'weeks'])} weeks, and enclosures are {pct(ROB.loc[REST, 'enclosure_share_of_hours'], 0)} "
             f"of its hours.</p>")
    b.append(titled(C.fig_robot(), "Robotic Weld Cell Weekly Utilization and Queue"))
    rf = ROBOT_FAMILIES
    assert list(rf.index[:3]) == ["enclosure", "weldment", "chassis"]
    b.append(f"<p>The cell runs at or above 0.95 in {n0(ROBOT_BANDS.loc['0.95 and above', 'weeks'])} weeks of {n0(ROBOT_BANDS['weeks'].sum())} and below 0.80 in "
             f"{n0(ROBOT_BANDS.loc['below 0.80', 'weeks'])}; its queue is {d2(ROBOT_BANDS.loc['below 0.80', 'queue'])} days per operation in the weeks below 0.80 and "
             f"{d2(ROBOT_BANDS.loc['0.95 and above', 'queue'])} in the weeks at 0.95 and above. Enclosures are {pct(rf.loc['enclosure', 'share'], 0)} of its hours, "
             f"weldments {pct(rf.loc['weldment', 'share'], 0)} and chassis {pct(rf.loc['chassis', 'share'], 0)}. Its setups run at {d2(ROBOT_STD['setup_ratio'])} of "
             f"standard and its run time at {d2(ROBOT_STD['run_ratio'])}, so the cell's queue is load, not standards. {T.see('robot')}</p>")
    b.append(f"<p>A second shift on the robotic weld cell is the open shift on the secondary constraint; {link('options', 'the options report')} tests and prices "
             f"it.</p>")

    b.append("<h3 id='f3_3'>Assembly</h3>")
    yr, og, pv = ASM["years"], ASM["origin"], ASM["previous"]
    assert list(pv.index[:2]) == ["powder_coat", "outside_processing"] and og["p90"].idxmax() == "No weld"
    quiet = max(abs(v) for k, v in ASM["corr"].items() if "robotic weld cell hours" in k or "earlier" in k)
    assert quiet < 0.2, quiet
    b.append(f"<p>Assembly's two benches ran at {d2(yr.loc[YEAR, 'utilization'])} in {YEAR}, up from {d2(yr.loc[YEAR - 2, 'utilization'])} in {YEAR - 2} and "
             f"{d2(yr.loc[YEAR - 1, 'utilization'])} in {YEAR - 1}, with {int(yr.loc[YEAR, 'hot_weeks'])} hot weeks against "
             f"{'none' if yr.loc[YEAR - 2, 'hot_weeks'] == 0 else int(yr.loc[YEAR - 2, 'hot_weeks'])} in {YEAR - 2} and {int(yr.loc[YEAR - 1, 'hot_weeks'])} in "
             f"{YEAR - 1}. In the hot weeks utilization is {d2(ah['utilization'])} and the queue {d2(ah['queue'])} days per operation against {d2(ao['utilization'])} "
             f"and {d2(ao['queue'])} in the other {int(ao['weeks'])}; {ASM['backlog_weeks']} of the {int(ah['weeks'])} are the first-quarter backlog. The hot weeks "
             f"are assembly's own: arrivals run {d1(ah['arrivals'])} a week against {d1(ao['arrivals'])} and operations are "
             f"{pct(ah['hours_per_operation'] / ao['hours_per_operation'] - 1, 0)} larger ({d2(ah['hours_per_operation'])} machine hours against "
             f"{d2(ao['hours_per_operation'])}), while the robotic weld cell's share of arrivals barely moves ({pct(ah['robot_share'], 0)} against "
             f"{pct(ao['robot_share'], 0)}) and assembly utilization does not follow the cell's output in the same week or the two before it. Assembly receives "
             f"{pct(pv['powder_coat'], 0)} of its work from the powder line and {pct(pv['outside_processing'], 0)} from outside processing, the two stages that "
             f"release work on their own schedules, and the longest assembly queues are on jobs with no weld operation at all (90th percentile "
             f"{d1(og.loc['No weld', 'p90'])} days against {d1(og.loc['Manual weld bays', 'p90'])} and {d1(og.loc['Robotic weld cell', 'p90'])}). "
             f"{T.see('assembly')}</p>")
    b.append(chart("Assembly Weekly Utilization and Queue", fig_assembly()))

    b.append("<h3 id='f3_4'>The lasers</h3>")
    nov = C.LAS_NOV
    six = nov[nov["week_start"] >= "2024-11-11"]
    three = six.iloc[:3]
    assert len(six) == 6
    b.append(f"<p>The lasers ran at {d2(UY.loc['laser', 'utilization'])} for the year. Over the six weeks from November 11, 2024 they ran at "
             f"{rng(six['utilization'].min(), six['utilization'].max())}, and at {rng(three['utilization'].min(), three['utilization'].max())} in the first three, "
             f"with the first-operation queue rising from {d1(nov.iloc[0]['queue_mean'])} to {d1(nov.iloc[-1]['queue_mean'])} days by mid-December. They reached 0.95 "
             f"in {C.LW_N} of {C.LW_ALL} full weeks in three years. {T.see('laser_weeks')}</p>")
    mo, lm, lp = LAS["month"], LAS["machines"], LAS["period"]
    builds = mo.loc[[1, 12]]
    ordinary = mo.drop([1, 12])
    assert builds["queue"].min() > ordinary["queue"].max()
    over = float((lm.loc[S.NEWER, "standard_hours"] - lm.loc[S.NEWER, "run_hours"]).sum())
    b.append(f"<p>In an ordinary month the first-operation queue is under a day and a half ({rng(ordinary['queue'].min(), ordinary['queue'].max())} on the monthly "
             f"mean) and its 90th percentile no more than {d1(ordinary['p90'].max())} days; January ({d2(mo.loc[1, 'queue'])}) and December ({d2(mo.loc[12, 'queue'])}) "
             f"are the two builds. Material wait is steady through the year: {pct(lp['year']['with_wait'], 0)} of first operations wait for material, "
             f"{rng(mo['material_wait'].min(), mo['material_wait'].max(), d1)} days on the monthly mean across all jobs and "
             f"{rng(min(lp[REST]['wait_where_any'], lp['year']['wait_where_any']), max(lp[REST]['wait_where_any'], lp['year']['wait_where_any']), d1)} days where "
             f"there is a wait. The work center's {d2(UY.loc['laser', 'utilization'])} hides a split by machine: L1 runs one shift at "
             f"{d2(lm.loc['L1', 'utilization'])}, {newer} run two shifts at {d2(lm.loc[S.NEWER[0], 'utilization'])} and {d2(lm.loc[S.NEWER[1], 'utilization'])}. "
             f"{newer} carry {pct(lm.loc[S.NEWER, 'share_of_standard'].sum(), 0)} of laser standard hours and run them in "
             f"{d2(lm.loc[S.NEWER, 'run_hours'].sum() / lm.loc[S.NEWER, 'standard_hours'].sum())} of the standard time, so planned laser hours on the two are "
             f"overstated by {n0(over)} for the year ({n0(lm['standard_hours'].sum())} standard against {n0(lm['run_hours'].sum())} actual across the three "
             f"machines); <a href='#f5'>Section 5</a> takes this up. {T.see('lasers')}</p>")

    # 4 ── setups against standard
    b.append("<h2 id='f4'>4. Setups Against Standard</h2>")
    ST, MH_WEEK = S.ST, S.MH_WEEK
    b.append(f"<p>{n0(len(S.D['s']))} setups at all work centers in {YEAR}, {n0(y['setups'])} of them at the brakes. A setup's ratio is its setup machine hours over "
             f"the setup standard on the job operation; hours over standard is total setup hours over total standard hours. Every work center except the brakes runs "
             f"its setups at a median of {rng(others_setup['median_ratio'].min(), others_setup['median_ratio'].max())} of standard and within "
             f"{n0(others_setup['overrun_hours'].max())} overrun hours for the year; the brakes ran {n0(y['setup_hours'])} hours against {n0(y['standard_hours'])} "
             f"standard, {n0(y['overrun_hours'])} over, {n0(ST['brake_overrun_per_week'])} a week, {pct(ST['brake_overrun_per_week'] / MH_WEEK, 0)} of brake machine "
             f"time. The median brake setup runs at {d2(y['median_ratio'])} of standard and the 90th percentile at {d2(y['p90_ratio'])}. Setup ratios do not move "
             f"with the 2024 year-end build: the median is {d2(S.OV.loc['Q1', 'median_ratio'])} in the first quarter and {d2(S.OV.loc[REST, 'median_ratio'])} in "
             f"{REST}. {T.see('bywc', 'period')}</p>")

    b.append("<h3 id='f4_1'>Where the overrun sits</h3>")
    ho, nho, small, LOT, FML, FAM = S.HO.loc["Handed over at a shift boundary"], S.HO.loc["Not handed over"], S.LOT.loc["under 25"], S.LOT, S.FML, S.FAM
    bump = small["median_ratio"] / LOT.drop("under 25")["median_ratio"].mean() - 1
    b.append(f"<p>Setups handed over at a shift boundary (setup transactions by different operators one after the other) are {pct(ho['share_of_setups'], 0)} of setups "
             f"and {pct(ho['share_of_overrun'], 0)} of the overrun hours, median {d2(ho['median_ratio'])} against {d2(nho['median_ratio'])}; most of those hours are "
             f"long setups that reached the boundary rather than the handover itself (<a href='#f4_4'>The setup reduction list and the handover</a>). Lots under 25 "
             f"are {pct(small['setups'] / y['setups'], 0)} of setups and {pct(ST['small_lot_overrun_share'], 0)} of the overrun, median {d2(small['median_ratio'])} "
             f"against {d2(LOT.loc['100 and over', 'median_ratio'])} to {d2(LOT.loc['25 to 99', 'median_ratio'])} on larger lots: the setup standards under-plan "
             f"small lots. First setups of a part by the operator run at {d2(FML.loc['none', 'median_ratio'])} against {d2(FML.loc['1 or 2', 'median_ratio'])}. "
             f"Enclosures and chassis run at {d2(FAM.loc['enclosure', 'median_ratio'])} and {d2(FAM.loc['chassis', 'median_ratio'])}; panels and brackets at "
             f"{d2(FAM.loc['panel', 'median_ratio'])} and {d2(FAM.loc['bracket', 'median_ratio'])}. {T.see('handover', 'lot', 'familiarity', 'family')}</p>")
    b.append(titled(S.fig_conditions(), "Brake Setup Overrun Hours by Condition"))
    b.append(f"<p>The setup standard on lots under 25 pieces should be raised by {pct(bump, 0)}, so the schedule and the quote stop under-planning them.</p>")

    b.append("<h3 id='f4_2'>Operator tenure and familiarity</h3>")
    TM, MIX, PLACE, WHO, ANY, SAME = S.TM, S.MIX, S.PLACE, S.WHO, S.ASG_ANY, S.ASG_SAME
    b.append(f"<p>Operators with under 12 months run {pct(TM['tenure_effect_pct'].iloc[0], 0)} above tenured operators before controls and "
             f"{pct(TM['tenure_effect_pct'].iloc[-1], 0)} after familiarity, grouping, machine, lot size, bend count and shift handover. Their "
             f"{n0(MIX.loc[1, 'setups'])} setups of {n0(y['setups'])} were made by {len(WHO)} operators, {n0(WHO.iloc[0])} by one, and "
             f"{pct(PLACE.loc['B4', 1], 0)} were on B4. The tenure effect is mostly what new operators are given, not who they are. {T.see('tenure')}</p>")
    b.append(titled(S.fig_tenure(), "Tenure Effect on Brake Setup Ratio as Controls Are Added"))
    b.append(f"<p>{n0(ANY['count'])} first setups of a repeat part were made while another current brake operator had set the part up in the "
             f"previous 24 months. They ran at {d2(ANY['hours_weighted_ratio'])} of standard against {d2(ANY['ratio_with_familiarity'])} for setups with prior "
             f"familiarity in the same lot band and family: {d1(ANY['hours_released_per_week'])} brake hours a week ({d1(SAME['hours_released_per_week'])} "
             f"where that operator was on the same shift). This is a matched comparison, not a start-time test, so part of it may be selection. Repeat setups should "
             f"go to an operator who has set the part up before. {T.see('assign')}</p>")

    b.append("<h3 id='f4_3'>Grouping</h3>")
    GRP = S.GRP
    ga, b12, b345 = GRP.loc["all brakes"], GRP.loc[["B1", "B2"], "share_grouped"], GRP.loc[["B3", "B4", "B5"], "share_grouped"]
    b.append(f"<p>{pct(ga['share_grouped'], 0)} of brake setups follow a job on the same tooling set and run at {d2(ga['ratio_grouped'])} of standard against "
             f"{d2(ga['ratio_not_grouped'])}, saving {d1(ga['hours_saved_per_week'])} hours a week. B1 and B2 group {pct(b12.min(), 0)} to {pct(b12.max(), 0)} of their "
             f"setups against {pct(b345.min(), 0)} to {pct(b345.max(), 0)} on B3 to B5: precision work and the hot list come first there. {T.see('grouping')}</p>")
    b.append(titled(S.fig_grouping(), "Same-tooling Grouping by Brake"))

    b.append("<h3 id='f4_4'>The setup reduction list and the handover</h3>")
    cf_naive, cf_start, late, early_med = S.HCF.iloc[0], S.HCF.iloc[1], S.HST.iloc[0], S.HST.iloc[2:]["median_ratio"]
    b.append(f"<p>The top {SA.TOP_N} part-operations release {d1(ST['top_hours_per_week'])} brake hours a week at standard: {pct(ST['top_share_of_brake_overrun'], 0)} of "
             f"the overrun and {pct(ST['top_hours_per_week'] / MH_WEEK)} of brake machine time. The overrun is spread across {n0(ST['brake_part_operations'])} "
             f"part-operations, so no short list captures most of it. {T.see('top12', 'top20')}</p>")
    b.append(f"<p>Handed-over setups carry {d1(cf_naive['hours_per_week'])} hours a week above the ratio of setups finished by the operator who started them, but most "
             f"of that is length, not handover: a long setup is the one that reaches the end of the shift. Setups started in the last 30 minutes of a shift are handed "
             f"over {pct(late['share_handed_over'], 0)} of the time and run at a median {d2(late['median_ratio'])} against {d2(early_med.min())} to "
             f"{d2(early_med.max())} for setups started with more than an hour left. On that comparison the handover itself costs "
             f"{d1(cf_start['hours_per_week'])} brake hours a week. {T.see('released')}</p>")
    b.append(f"<p>Three levers release {d1(S.LEVERS)} brake hours a week, {pct(S.LEVERS / MH_WEEK)} of brake machine time: the top {SA.TOP_N} part-operations run at "
             f"standard ({d1(ST['top_hours_per_week'])} hours a week), repeat setups assigned to an operator who has set the part up before "
             f"({d1(ANY['hours_released_per_week'])}), and a shift-handover standard at the brakes, the operator who starts a setup finishing it or leaving a written "
             f"handover at the machine ({d1(cf_start['hours_per_week'])}). {link('options')} carries these hours as the setup program.</p>")

    # 5 ── run standards
    b.append("<h2 id='f5'>5. Run Standards</h2>")
    POP, gap = S.POP, S.SRAT["run_gap"]
    b.append(f"<p>{newer} run at {d2(S.LF[S.NEWER].mean())} of the run standard and L1 at {d2(S.LF['L1'])}; every other work center runs at "
             f"{d2(other_run.min())} to {d2(other_run.max())}. {n0(POP['stale_parts'])} of {n0(POP['active_parts_with_routing'])} active parts "
             f"({pct(POP['stale_share'], 0)}) carry a stale standard (one dated at the part's first quote) and run {pct(gap.min(), 0)} to {pct(gap.max(), 0)} further "
             f"above standard than refreshed parts at the same work center. {T.see('run', 'stale')}</p>")
    b.append(titled(S.fig_run(), "Run Actual Over Standard by Work Center"))
    swc = S.SWC.set_index("work_center")
    sall, lall = S.SRC.set_index("routing_class").loc["all"], S.LRC.set_index("routing_class").loc["all"]
    b.append(f"<p>With the stale standards refreshed, planned hours rise {pct(swc.loc['press_brake', 'change'])} at the brakes and "
             f"{pct(swc['change'].min())} to {pct(swc['change'].max())} elsewhere; standard hours per job rise {pct(sall['change_stale_jobs'], 0)} on jobs for those parts "
             f"({pct(sall['jobs_on_stale_parts'] / sall['jobs'], 0)} of jobs) and {pct(sall['change_all_jobs'])} overall. With the {newer} run standards set "
             f"to measured, planned laser hours fall {pct(-S.LWC['change'].iloc[1])} and standard hours per job fall {pct(-lall['change_laser'])}. Both together move "
             f"standard hours per job by {S.sp(lall['change_both'])}. The {n0(POP['stale_parts'])} stale standards should be refreshed and the {newer} run standards "
             f"set to measured, with the effect on standard hours per job going to estimating ({link('quoting')}). {T.see('planned', 'quoted')}</p>")

    b.append("<h2 id='appendix'>Appendix</h2>")
    b.append(T.appendix())
    toc = [("f1", "1. The Screen"), ("f2", "2. Queue Against Load"), ("f3", "3. The Constraints"), ("f4", "4. Setups Against Standard"), ("f5", "5. Run Standards")]
    print(f"wrote {page('capacity', chr(10).join(b), toc)}: 5 sections, {len(T.order)} appendix tables")
    return T.order


def main():
    build()


if __name__ == "__main__":
    main()
