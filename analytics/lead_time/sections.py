"""Lead time decomposition: the sections, tables and figures of its half of the report, read from the marts.

Built by analytics.reports.lead_time_and_late_jobs.
"""
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch, Patch, Rectangle

from analytics.db import q
from analytics.style.style import ACCENT, AMBER, BRAND_BLUE, DARK_GREY as DARK, DOCS, GREEN, GREY, LIGHT_BLUE, RED, TEXT, fig, paired_columns, pct, save, sig, table

YEAR = 2025
REST = "Q2 to Q4"
RT = "Q2-Q4"                                  # the same quarters as written in the report text and its figures
CLASSES = ["repeat part", "new part", "outside processing"]
WC = {"press_brake": "Press brake", "grind_deburr": "Grind and deburr", "inspection_pack": "Inspection and pack", "hardware": "Hardware",
      "weld": "Manual weld", "robotic_weld": "Robotic weld", "assembly": "Assembly", "powder_coat": "Powder coat", "laser": "Laser", "punch": "Punch",
      "outside_processing": "Outside processing", "complete, not shipped": "Complete, not shipped"}
STAGE = {"release to traveler print": "Release to traveler print", "first-operation queue": "First-operation queue",
         "material wait at first operation": "Material wait at first operation", "queue: press brake": "Queue: press brake",
         "queue: hardware": "Queue: hardware", "queue: weld": "Queue: manual weld", "queue: robotic weld": "Queue: robotic weld",
         "queue: grind deburr": "Queue: grind and deburr", "powder scheduling wait": "Powder scheduling wait", "queue: powder coat": "Queue: powder coat",
         "queue: assembly": "Queue: assembly", "queue: inspection pack": "Queue: inspection and pack", "setup and run": "Setup and run", "move": "Move",
         "hold: customer": "Hold: customer", "hold: engineering": "Hold: engineering", "hold: material": "Hold: material", "hold: other": "Hold: other",
         "hold: quality": "Hold: quality", "hold: tooling": "Hold: tooling", "outside processing": "Outside processing",
         "complete to ship": "Complete to ship"}


def d1(x):
    return f"{x:.1f}"


def d2(x):
    return f"{x:.2f}"


def n0(x):
    return f"{x:,.0f}"


def qlabel(ts):
    ts = pd.Timestamp(ts)
    return f"{ts.year} Q{ts.quarter}"


def join_and(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


# ── data ────────────────────────────────────────────────────────────────────
batch = q("select export_batch_id from marts.mart_lead_time_summary limit 1").iloc[0, 0]
summ = q("select * from marts.mart_lead_time_summary").set_index(["period", "routing_class"])
stage = q("select * from marts.mart_lead_time_by_stage")
queue = q("select * from marts.mart_queue_by_work_center").set_index(["period", "work_center"])
wipi = q("select * from marts.mart_wip_implied").set_index("period")
wloc = q("select location, wip_mean from marts.mart_wip_by_location where period_type = 'report year' order by wip_mean desc")
ll = q("select * from marts.mart_littles_law")
dq = q("select * from marts.mart_delivery_by_quarter order by quarter_start")
wk = q("select * from marts.mart_weekly_floor order by week_start")
rq = q("select * from marts.mart_releases_by_quarter order by quarter_start").set_index("quarter_start")
jobs = q(f"select routing_class, quoted_lead_days, lead_time_wd, on_time, qty, quarter(ship_date) as ship_quarter, key_account, required_otd_pct "
         f"from marts.mart_job_lead_time where year(ship_date) = {YEAR}")
wipd = q("select calendar_date, sum(jobs) as wip from marts.mart_wip_daily group by 1 order by 1")
wloc_days = q(f"select calendar_date, location, jobs from marts.mart_wip_daily where year(calendar_date) = {YEAR}")
brake_weeks = q(f"select machine_hours, scheduled_hours, downtime_hours from marts.mart_utilization_weekly "
                f"where work_center = 'press_brake' and week_year = {YEAR} and week_quarter >= 2")

Y, R = summ.loc["year"], summ.loc[REST]
required = jobs.loc[jobs["key_account"] == True, "required_otd_pct"].max() / 100.0  # noqa: E712


# ── the job flow ────────────────────────────────────────────────────────────
# the share of jobs shipped 2023 to 2025 that pass through each step, and where their recorded holds fall
CUT, JOIN, FINISH = ["laser", "punch"], ["hardware", "weld", "robotic_weld"], ["powder_coat", "outside_processing"]
_ops = q("""select jo.job_id, jo.op_seq, jo.work_center from staging.stg_erp__job_operations jo join intermediate.int_job_lead_time l using (job_id)
            where l.ship_date is not null order by 1, 2""")
_ops["previous"] = _ops.groupby("job_id")["work_center"].shift(1)
_flow_jobs = _ops["job_id"].nunique()


def _through(mask):
    return float(_ops[mask]["job_id"].nunique() / _flow_jobs)


_brake = _ops[_ops["work_center"] == "press_brake"]
_second = _brake[_brake.groupby("job_id").cumcount() == 1]
_wc = _ops["work_center"]
FLOW = dict(
    cut=_through(_wc.isin(CUT)), deburr=_through((_wc == "grind_deburr") & _ops["previous"].isin(CUT)),
    laser_deburr=float(((_wc == "grind_deburr") & (_ops["previous"] == "laser")).sum() / (_wc == "laser").sum()), form=_through(_wc == "press_brake"),
    second_form=float(len(_second) / _flow_jobs), second_form_after_hardware=float((_second["previous"] == "hardware").mean()), hardware=_through(_wc == "hardware"),
    weld=_through(_wc.isin(["weld", "robotic_weld"])), join=_through(_wc.isin(JOIN)), grind_welds=_through((_wc == "grind_deburr") & _ops["previous"].isin(["weld", "robotic_weld"])),
    powder=_through(_wc == "powder_coat"), outside=_through(_wc == "outside_processing"), finish=_through(_wc.isin(FINISH)), assembly=_through(_wc == "assembly"),
    inspect=_through(_wc == "inspection_pack"))
assert FLOW["cut"] == FLOW["form"] == FLOW["inspect"] == 1.0 and abs(FLOW["grind_welds"] - FLOW["weld"]) < 1e-9 and FLOW["laser_deburr"] > 0.5
_holds = q("""select h.op_seq = f.first_seq as at_first, h.hold_reason from staging.stg_mes__holds h join intermediate.int_job_lead_time l using (job_id)
              join (select job_id, min(op_seq) as first_seq from staging.stg_erp__job_operations group by 1) f using (job_id) where l.ship_date is not null""")
HOLDS_AT_FIRST = float(_holds["at_first"].mean())
assert float((_holds[_holds["at_first"]]["hold_reason"] == "material").mean()) > 0.5

# mean working days per job by step in the job flow: waiting, working and at the vendor, with a job that skips a step counted as zero
FLOW_ROWS = ["Release to traveler print", "Cut (laser or punch)", "Grind and deburr, edges", "Press brake", "Hardware", "Manual weld", "Robotic weld", "Grind and deburr, welds",
             "Powder coat", "Outside processing", "Assembly", "Inspection and pack", "Holds", "Complete to ship"]
_ROW = {"press_brake": "Press brake", "hardware": "Hardware", "weld": "Manual weld", "robotic_weld": "Robotic weld", "powder_coat": "Powder coat", "assembly": "Assembly",
        "inspection_pack": "Inspection and pack"}
_sd = q(f"""select s.job_id, s.op_seq, s.work_center, s.stage, s.days, quarter(l.ship_date) as ship_quarter from intermediate.int_job_stage_days s
            join intermediate.int_job_lead_time l using (job_id) where year(l.ship_date) = {YEAR}""").merge(_ops[["job_id", "op_seq", "previous"]], on=["job_id", "op_seq"], how="left")


def _step(stage_, wc_, previous):
    if stage_.startswith("hold"):
        return "Holds", "waiting"
    if stage_ == "release to traveler print":
        return FLOW_ROWS[0], "waiting"
    if stage_ == "complete to ship":
        return FLOW_ROWS[-1], "waiting"
    if stage_ == "outside processing":
        return "Outside processing", "vendor"
    kind = "working" if stage_ == "setup and run" else "waiting"
    if wc_ in CUT:
        return FLOW_ROWS[1], kind
    if wc_ == "grind_deburr":
        return ("Grind and deburr, edges" if previous in CUT else "Grind and deburr, welds"), kind
    return _ROW[wc_], kind


_sd["step"], _sd["kind"] = zip(*[_step(a, b, c) for a, b, c in zip(_sd["stage"], _sd["work_center"], _sd["previous"])])


def flow_days(d, n):
    g = (d.groupby(["step", "kind"])["days"].sum() / n).unstack(fill_value=0.0).reindex(FLOW_ROWS).fillna(0.0)
    for k in ("waiting", "working", "vendor"):
        if k not in g:
            g[k] = 0.0
    g["total"] = g[["waiting", "working", "vendor"]].sum(axis=1)
    return g


FY, FR = flow_days(_sd, len(jobs)), flow_days(_sd[_sd["ship_quarter"] >= 2], int((jobs["ship_quarter"] >= 2).sum()))
BRAKE_QUEUE = {"year": float(_sd[(_sd["stage"] == "queue") & (_sd["work_center"] == "press_brake")]["days"].sum() / len(jobs)),
               "rest": float(_sd[(_sd["stage"] == "queue") & (_sd["work_center"] == "press_brake") & (_sd["ship_quarter"] >= 2)]["days"].sum() / (jobs["ship_quarter"] >= 2).sum())}

# working days from the due date to the ship date for every job shipped in the year: negative is early
AFTER = q(f"""select cs.wd_index - cd.wd_index as days_after, quarter(j.ship_date) as ship_quarter from marts.mart_job_lead_time j
              join intermediate.int_working_days cs on cs.calendar_date = j.ship_date join intermediate.int_working_days cd on cd.calendar_date = j.due_date
              where year(j.ship_date) = {YEAR}""")
assert len(AFTER) == len(jobs) and int((AFTER["days_after"] > 0).sum()) == int((~jobs["on_time"]).sum())
EARLY, LATE_CAP = -6, 30
AFTER_BINS = list(range(EARLY, LATE_CAP + 1))
AFTER_LABEL = {EARLY: "6 or more early", LATE_CAP: "30 or more"}


def after_counts(d):
    return d["days_after"].clip(lower=EARLY, upper=LATE_CAP).value_counts().reindex(AFTER_BINS).fillna(0).astype(int)


AY, AR = after_counts(AFTER), after_counts(AFTER[AFTER["ship_quarter"] >= 2])


def stage_pivot(period):
    d = stage[stage["period"] == period]
    p = d.pivot(index="stage", columns="job_class", values="mean_days").fillna(0.0)
    p["share"] = d[d["job_class"] == "all"].set_index("stage")["share_of_lead_time"]
    p["order"] = d.groupby("stage")["stage_order"].first()
    p = p.sort_values(["order", "stage"])
    tot = d.groupby("job_class")[["jobs", "lead_time_mean", "lead_time_median"]].first()
    return p, tot


SY, TY = stage_pivot("year")
SR, TR = stage_pivot(REST)


def st(p, name, col):
    return float(p.loc[name, col]) if name in p.index else 0.0


# ── figures ─────────────────────────────────────────────────────────────────
def fig_distribution():
    f, axes = fig(h=3.6, ncols=3, sharey=False)
    bins = np.arange(0, 46, 1)
    for ax, cls in zip(axes, CLASSES):
        d = jobs[jobs["routing_class"] == cls]
        ax.hist(d["lead_time_wd"].clip(upper=45), bins=bins, color=LIGHT_BLUE, label=f"{YEAR}")
        ax.hist(d.loc[d["ship_quarter"] >= 2, "lead_time_wd"].clip(upper=45), bins=bins, color=BRAND_BLUE, label=RT)
        ax.axvline(float(d["quoted_lead_days"].mean()), color=RED, linewidth=1.6, linestyle="--", label="Average quoted lead time")
        ax.set_title(cls.capitalize(), fontsize=11)
        ax.set_xlabel("Lead time (working days)")
    axes[0].set_ylabel("Jobs")
    h, lab = axes[0].get_legend_handles_labels()
    f.legend(h, lab, frameon=False, fontsize=9, ncol=3, loc="lower center")
    f.tight_layout(rect=(0, 0.07, 1, 1))
    return save(f, "lead_time_distribution", "Lead time distribution by routing class")


def fig_stages_report():
    f, axes = fig(h=5.6, ncols=2, grid="x", sharey=True, sharex=True)
    for ax, (p, label) in zip(axes, ((SY, f"{YEAR}"), (SR, f"{YEAR} {RT}"))):
        g = p.copy()
        holds = g[g.index.str.startswith("hold:")][["on time", "late"]].sum()
        g = g[~g.index.str.startswith("hold:")]
        g.loc["hold (recorded)", ["on time", "late"]] = holds.values
        g.loc["hold (recorded)", "order"] = 16
        g = g.sort_values("order", ascending=False)
        yy = np.arange(len(g))
        ax.barh(yy + 0.2, g["on time"], height=0.38, color=ACCENT, label="On-time jobs")
        ax.barh(yy - 0.2, g["late"], height=0.38, color=AMBER, label="Late jobs")
        ax.set_yticks(yy)
        ax.set_yticklabels(["Setup and run, all work centers" if s == "setup and run" else STAGE.get(s, s.capitalize()) for s in g.index], fontsize=9)
        ax.set_title(label, fontsize=11)
        ax.set_xlabel("Mean working days per job")
    h, lab = axes[0].get_legend_handles_labels()
    f.tight_layout(rect=(0, 0.05, 1, 1))
    between = (axes[0].get_position().x1 + axes[1].get_position().x0) / 2
    f.legend(h, lab, frameon=False, fontsize=9, ncol=2, loc="lower center", bbox_to_anchor=(float(sig(between, 4)), 0.0))
    return save(f, "lead_time_stage_decomposition", "Lead time by stage, on-time and late jobs")


WAITING, WORKING = "#DCE6EE", BRAND_BLUE


def fig_job_flow():
    """The job flow from release to shipment: the steps in sequence, the share of jobs through each, the cycle inside a work center and where holds fall."""
    P = lambda x: f"{x * 100:.0f}%"
    # name, width, kind (edge: a point in time; wait: waiting only; step: a work-center step), share, every job
    steps = [("Release", 0.62, "edge", None, True), ("Release to" + chr(10) + "traveler" + chr(10) + "print", 0.72, "wait", None, True),
             ("Cut" + chr(10) + "laser or punch," + chr(10) + "after queue and" + chr(10) + "material wait", 1.0, "step", FLOW["cut"], True),
             ("Deburr" + chr(10) + "edges" + chr(10) + "grind and" + chr(10) + "deburr", 0.78, "step", FLOW["deburr"], False),
             ("Form" + chr(10) + "press brake", 0.82, "step", FLOW["form"], True),
             ("Insert" + chr(10) + "and join" + chr(10) + "hardware," + chr(10) + "weld", 0.82, "step", FLOW["join"], False),
             ("Grind" + chr(10) + "welds" + chr(10) + "grind and" + chr(10) + "deburr", 0.78, "step", FLOW["grind_welds"], False),
             ("Finish" + chr(10) + "powder coat;" + chr(10) + "outside" + chr(10) + "processing", 0.92, "step", FLOW["finish"], False),
             ("Assemble", 0.76, "step", FLOW["assembly"], False), ("Inspect" + chr(10) + "and pack", 0.76, "step", FLOW["inspect"], True),
             ("Complete" + chr(10) + "to ship", 0.72, "wait", None, True), ("Ship", 0.54, "edge", None, True)]
    gap, y, h = 0.16, 2.35, 1.12
    f, ax = fig(h=4.1, w=10.0)
    ax.axis("off")
    arrow = dict(arrowstyle="-|>", color=DARK, linewidth=1.0, shrinkA=0, shrinkB=0, mutation_scale=9)
    box = lambda x0, y0, w, hh, **kw: ax.add_patch(FancyBboxPatch((x0, y0), w, hh, boxstyle="round,pad=0.02,rounding_size=0.06", **kw))
    x, edges = 0.1, []
    for name, w, kind, share, every in steps:
        fill = WAITING if kind == "wait" else "white"
        box(x, y - h / 2, w, h, facecolor=fill, edgecolor=DARK, linewidth=1.6 if kind == "edge" else 0.9, linestyle="-" if every else "--")
        if kind == "step":
            lines = name.split(chr(10))
            head = 2 if lines[0] in ("Deburr", "Insert", "Grind") else 1
            ax.text(x + w / 2, y + h / 2 - 0.09, chr(10).join(lines[:head]), ha="center", va="top", fontsize=8.2, color=TEXT, fontweight="bold")
            ax.text(x + w / 2, y + h / 2 - 0.09 - 0.2 * head - 0.03, chr(10).join(lines[head:]), ha="center", va="top", fontsize=6.8, color=TEXT)
            # the cycle inside the step: waiting, then working
            ax.add_patch(Rectangle((x + 0.06, y - h / 2 + 0.06), (w - 0.12) * 0.62, 0.1, facecolor=WAITING, edgecolor=DARK, linewidth=0.4))
            ax.add_patch(Rectangle((x + 0.06 + (w - 0.12) * 0.62, y - h / 2 + 0.06), (w - 0.12) * 0.38, 0.1, facecolor=WORKING, edgecolor=DARK, linewidth=0.4))
            ax.text(x + w / 2, y - h / 2 - 0.1, P(share) + " of jobs", ha="center", va="top", fontsize=7.6, color=TEXT)
        else:
            ax.text(x + w / 2, y, name, ha="center", va="center", fontsize=8.0, color=TEXT, fontweight="bold" if kind == "edge" else None)
        edges.append((x, x + w))
        x += w + gap
    for (_, a), (c, _) in zip(edges[:-1], edges[1:]):
        ax.annotate("", (c - 0.02, y), (a + 0.02, y), arrowprops=arrow)
    total = edges[-1][1] + 0.1
    # inside every work-center step
    ix, iy, ih = edges[2][0], 3.62, 0.36
    ax.text(ix, iy + ih / 2 + 0.1, "Inside each work-center step:", ha="left", va="bottom", fontsize=7.8, color=TEXT)
    for name, w, fill in (("Move", 0.62, WAITING), ("Queue", 0.66, WAITING), ("Setup and run", 1.05, WORKING)):
        box(ix, iy - ih / 2, w, ih, facecolor=fill, edgecolor=DARK, linewidth=0.7)
        ax.text(ix + w / 2, iy, name, ha="center", va="center", fontsize=7.8, color="white" if fill == WORKING else TEXT)
        if name != "Setup and run":
            ax.annotate("", (ix + w + 0.14, iy), (ix + w + 0.03, iy), arrowprops=arrow)
        ix += w + 0.17
    ax.text(ix + 0.1, iy, "Dashed border: a step not every job takes", ha="left", va="center", fontsize=7.8, color=TEXT)
    # holds, under every work-center step
    ha_, hb_, yo, ho = edges[2][0], edges[9][1], 1.02, 0.36
    box(ha_, yo - ho / 2, hb_ - ha_, ho, facecolor=WAITING, edgecolor=DARK, linewidth=0.8, linestyle=":")
    ax.text((ha_ + hb_) / 2, yo, f"Holds: at any operation on the routing ({P(HOLDS_AT_FIRST)} at the first operation, most of them for material)", ha="center", va="center",
            fontsize=8.0, color=TEXT)
    # the span that is lead time
    ax.annotate("", (edges[-1][1], 0.3), (edges[0][0], 0.3), arrowprops=dict(arrowstyle="<|-|>", color=DARK, linewidth=0.8, mutation_scale=9, shrinkA=0, shrinkB=0))
    ax.text(total / 2, 0.37, "In WIP from release to shipment: lead time, working days", ha="center", va="bottom", fontsize=8.2, color=TEXT)
    ax.set_xlim(0, total)
    ax.set_ylim(0.1, 4.15)
    f.legend([Patch(facecolor=WAITING, edgecolor=DARK, linewidth=0.6), Patch(facecolor=WORKING)], ["Waiting", "Working"], frameon=False, fontsize=9, ncol=2,
             loc="lower center")
    f.tight_layout(rect=(0, 0.06, 1, 1))
    return save(f, "job_flow_diagram", "Job Flow Through the Shop, Release to Shipment")


VENDOR = AMBER


def flow_shares(g):
    t = g["total"].sum()
    return dict(total=float(t), waiting=float(g["waiting"].sum() / t), working=float(g["working"].sum() / t), vendor=float(g["vendor"].sum() / t))


def fig_flow_days():
    f, axes = fig(h=5.4, ncols=2, grid="x", sharey=True, sharex=True)
    yy = np.arange(len(FLOW_ROWS))[::-1]
    for ax, (g, label) in zip(axes, ((FY, f"{YEAR}"), (FR, RT))):
        s = flow_shares(g)
        ax.barh(yy, g["waiting"], height=0.66, color=WAITING, edgecolor=DARK, linewidth=0.4, label="Waiting (move and queue)")
        ax.barh(yy, g["working"], height=0.66, left=g["waiting"], color=WORKING, label="Working (setup and run)")
        ax.barh(yy, g["vendor"], height=0.66, left=g["waiting"] + g["working"], color=VENDOR, label="At the vendor")
        for yi, v in zip(yy, g["total"]):
            ax.annotate(f"{v:.2f}", (v, yi), textcoords="offset points", xytext=(3, 0), va="center", fontsize=7.8)
        ax.set_yticks(yy)
        ax.set_yticklabels(FLOW_ROWS, fontsize=9)
        ax.set_title(f"{label}" + chr(10) + f"mean lead time {s['total']:.1f} working days" + chr(10) + f"{s['waiting'] * 100:.0f}% waiting", fontsize=10)
        ax.set_xlabel("Working days per job")
    axes[0].set_xlim(0, float(FY["total"].max()) * 1.12)
    h, lab = axes[0].get_legend_handles_labels()
    f.legend(h, lab, frameon=False, fontsize=9, ncol=3, loc="lower center")
    f.tight_layout(rect=(0, 0.05, 1, 1))
    return save(f, "lead_time_by_flow_step", f"Where Lead Time Goes: Mean Working Days per Job by Step in the Job Flow, {YEAR} and {RT}")


def late_stats(d):
    late = d[d["days_after"] > 0]["days_after"]
    return dict(late=int(len(late)), share=float(len(late) / len(d)), median=float(late.median()), p90=float(late.quantile(0.9)))


def fig_after_due():
    f, ax = fig(h=3.8)
    x = np.array(AFTER_BINS, dtype=float)
    ax.axvspan(0.5, LATE_CAP + 0.6, color=RED, alpha=0.06, lw=0)
    ax.bar(x, AY.to_numpy(), 0.86, color=LIGHT_BLUE, label=f"{YEAR}")
    ax.bar(x, AR.to_numpy(), 0.86, color=BRAND_BLUE, label=RT)
    ax.axvline(0, color=RED, linewidth=1.6, linestyle="--", label="Due date")
    # the bin of jobs six or more days early is several times any other: the axis stops above the rest and that bar carries its counts
    top = float(AY.iloc[1:].max()) * 1.35
    ax.set_ylim(0, top)
    ax.text(EARLY + 0.6, top * 0.97, f"{AY.iloc[0]:,} in {YEAR}," + chr(10) + f"{AR.iloc[0]:,} in {RT}", ha="left", va="top", fontsize=8, color=TEXT)
    for k, (lab, d) in enumerate(((f"{YEAR}", AFTER), (RT, AFTER[AFTER["ship_quarter"] >= 2]))):
        s = late_stats(d)
        ax.text(LATE_CAP, top * (0.92 - 0.1 * k), f"{lab}: {s['late']:,} late jobs, {s['share'] * 100:.0f}% of jobs; median {s['median']:.0f} days late, 90th percentile {s['p90']:.0f}",
                ha="right", va="top", fontsize=8.5, color=TEXT)
    ticks = [EARLY, -4, -2, 0, 2, 4, 6, 8, 10, 15, 20, 25, LATE_CAP]
    ax.set_xticks(ticks)
    ax.set_xticklabels(["6 or more" + chr(10) + "early" if t == EARLY else "30 or" + chr(10) + "more" if t == LATE_CAP else str(t) for t in ticks], fontsize=8.5)
    ax.set_xlim(EARLY - 0.8, LATE_CAP + 0.8)
    ax.set_xlabel("Working days shipped after the due date")
    ax.set_ylabel("Jobs")
    h, lab = ax.get_legend_handles_labels()
    f.legend(h, lab, frameon=False, fontsize=9, ncol=3, loc="lower center")
    f.tight_layout(rect=(0, 0.07, 1, 1))
    return save(f, "days_after_due_date", f"Working Days Shipped After the Due Date, {YEAR} and {RT}")


def t8():
    rows = [[AFTER_LABEL.get(k, ("on the due date" if k == 0 else f"{-k} early" if k < 0 else f"{k} late")), n0(AY[k]), n0(AR[k])] for k in AFTER_BINS]
    rows.append(["All jobs", n0(AY.sum()), n0(AR.sum())])
    return table(pd.DataFrame(rows, columns=["Working days from the due date to the ship date", f"Jobs shipped, {YEAR}", f"Jobs shipped, {YEAR} {REST}"]))


def fig_wip():
    order = list(ws_year.sort_values(ascending=False).index)
    f, ax = fig(h=3.7)
    paired_columns(ax, [WC.get(x, x) for x in order], list(ws_year.reindex(order) * 100), list(ws_rest.reindex(order) * 100), (f"{YEAR}", RT), percent=True)
    ax.set_ylabel("Share of WIP Jobs")
    h, lab = ax.get_legend_handles_labels()
    f.legend(h, lab, frameon=False, fontsize=9, ncol=2, loc="lower center")
    f.tight_layout(rect=(0, 0.06, 1, 1))
    return save(f, "lead_time_wip_by_location", "WIP by location")


def fig_wip_quarters():
    """Mean floor WIP by calendar quarter, with the days on the floor it implies at the quarter's throughput."""
    d = llq.sort_values("period_start")
    x = np.arange(len(d))
    wip = sig(d["wip_mean"].to_numpy(dtype=float))
    days = sig((d["wip_mean"] / d["throughput_per_day"]).to_numpy(dtype=float))
    f, ax = fig(h=3.9)
    ax.bar(x, wip, width=0.7, color=LIGHT_BLUE, label="Average WIP (left)")
    for xi, v in zip(x, wip):
        ax.text(xi, float(wip.max()) * 0.02, f"{v:.0f}", ha="center", va="bottom", fontsize=8.5)          # at the foot of the column, clear of the line
    ax.set_xticks(x)
    ax.set_xticklabels([qlabel(t) for t in d["period_start"]], rotation=30, ha="right")
    ax.set_ylabel("Jobs in WIP")
    ax.set_ylim(0, float(wip.max()) * 1.12)
    ax2 = ax.twinx()
    ax2.plot(x, days, color=BRAND_BLUE, linewidth=2.0, marker="o", markersize=5, label="Days on the floor (right)")
    ax2.set_ylabel("Working days on the floor")
    ax2.set_ylim(0, float(days.max()) * 1.12)
    ax2.grid(False)
    ax2.spines["top"].set_visible(False)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    f.legend(h1 + h2, l1 + l2, frameon=False, fontsize=9, ncol=2, loc="lower center")
    f.tight_layout(rect=(0, 0.06, 1, 1))
    return save(f, "lead_time_wip_by_quarter", "Average WIP and Working Days on the Floor, 2023 to 2025")


def fig_weekly_year():
    """Weekly WIP and the net inflow to it, from the third quarter of 2024 through the second quarter of 2025."""
    d = wk[(wk["week_start"] >= "2024-07-01") & (wk["week_start"] <= "2025-06-29")].copy()
    net = d["releases"] - d["jobs_shipped"]
    f, ax = fig(h=4.2)
    x = pd.to_datetime(d["week_start"])
    ax.plot(x, d["wip_mean"], color=BRAND_BLUE, linewidth=2.4, label="Total WIP (left)")
    ax.plot(x, d["wip_at_laser"], color=GREEN, linewidth=1.9, linestyle="--", label="WIP at the laser (left)")
    ax.plot(x, d["wip_at_brakes"], color=AMBER, linewidth=1.9, linestyle="--", label="WIP at the brakes (left)")
    ax.set_ylabel("Jobs in WIP")
    ax2 = ax.twinx()
    ax2.bar(x, net, width=4.6, color=LIGHT_BLUE, label="Net inflow to WIP (releases less shipments, right)", zorder=2)
    ax2.axhline(0, color=RED, linewidth=1.3, linestyle="--", zorder=3)
    lim = float(np.ceil(net.abs().max() / 25) * 25)
    ax2.set_ylabel("Jobs per week")
    ax2.set_ylim(-lim, lim)
    ax2.grid(False)
    for s in ("top",):
        ax2.spines[s].set_visible(False)
    ax.set_zorder(ax2.get_zorder() + 1)
    ax.patch.set_visible(False)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.set_ylim(0, d["wip_mean"].max() * 1.08)
    ax.set_xlim(x.min() - pd.Timedelta(days=6), x.max() + pd.Timedelta(days=6))
    right = x.max() + pd.Timedelta(days=4)
    ax2.text(right, lim * 0.06, "build", color=RED, fontsize=8.5, ha="right", va="bottom", zorder=4)
    ax2.text(right, -lim * 0.06, "drain", color=RED, fontsize=8.5, ha="right", va="top", zorder=4)
    ax.legend(h1 + h2, l1 + l2, frameon=False, fontsize=8.5, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.11))
    f.tight_layout()
    return save(f, "lead_time_year_end_build", "Weekly WIP and net inflow, July 2024 to June 2025")


def build_weeks():
    return wk[(wk["week_start"] >= "2024-09-30") & (wk["week_start"] <= "2025-03-30")].copy()


def cls_pair(col, fmt=pct, d=0):
    return {c: (fmt(Y.loc[c, col], d) if fmt is pct else fmt(Y.loc[c, col]), fmt(R.loc[c, col], d) if fmt is pct else fmt(R.loc[c, col])) for c in CLASSES}


hit = cls_pair("share_within_quoted")
qy, qr = queue.loc["year"], queue.loc[REST]
wy, wr = wipi.loc["year"], wipi.loc[REST]
wl = wloc.set_index("location")["wip_mean"]
wl_share = wl / wl.sum()
llq = ll[ll["period_type"] == "quarter"].sort_values("period_start")
llq_in = int((abs(llq["wip_over_throughput_x_lead_time"] - 1) <= 0.10).sum())
llq_miss = llq[abs(llq["wip_over_throughput_x_lead_time"] - 1) > 0.10]
llm = ll[ll["period_type"] == "month"]["wip_over_throughput_x_lead_time"]
llr = ll[ll["period_type"] == "rolling 13 weeks"]["wip_over_throughput_x_lead_time"]
b24 = build_weeks()
b24["week_start"] = pd.to_datetime(b24["week_start"])
laser_weeks = b24[(b24["week_start"] >= "2024-11-11") & (b24["week_start"] <= "2024-11-25")]
wipd["calendar_date"] = pd.to_datetime(wipd["calendar_date"])
peaks = {}
for y in (2023, 2024, 2025):
    dec = wipd[(wipd["calendar_date"].dt.year == y) & (wipd["calendar_date"].dt.month == 12)]
    q3 = wipd[(wipd["calendar_date"].dt.year == y) & (wipd["calendar_date"].dt.month.isin([7, 8, 9]))]["wip"].mean()
    top = dec.loc[dec["wip"].idxmax()]
    peaks[y] = dict(peak=top["wip"], date=top["calendar_date"], q3=q3, ratio=top["wip"] / q3)
sat = b24[b24["week_start"] >= "2024-12-01"]
sat_run = sat[sat["brake_saturday_shifts"] > 0]
sat_all = bool((sat[sat["week_start"] >= sat_run["week_start"].min()]["brake_saturday_shifts"] > 0).all())
dq["quarter_start"] = pd.to_datetime(dq["quarter_start"])
q1 = dq[dq["quarter_start"] == f"{YEAR}-01-01"].iloc[0]
q1_2024 = dq[dq["quarter_start"] == "2024-01-01"].iloc[0]
rq.index = pd.to_datetime(rq.index)
brake_up = rq.loc["2024-10-01", "brake_std_hours"] / rq.loc["2024-07-01", "brake_std_hours"] - 1
rest_jobs = jobs[jobs["ship_quarter"] >= 2]
lot_late, lot_on = rest_jobs.loc[~rest_jobs["on_time"], "qty"].mean(), rest_jobs.loc[rest_jobs["on_time"], "qty"].mean()
short_weeks = b24[b24["weekdays"] < 5]
wloc_days["calendar_date"] = pd.to_datetime(wloc_days["calendar_date"])
wl_year = wloc_days.groupby("location")["jobs"].sum() / wloc_days["calendar_date"].nunique()
_rest_days = wloc_days[wloc_days["calendar_date"].dt.quarter >= 2]
wl_rest = _rest_days.groupby("location")["jobs"].sum() / _rest_days["calendar_date"].nunique()
ws_year, ws_rest = wl_year / wl_year.sum(), wl_rest / wl_rest.sum()
_named = ["press_brake", "laser", "outside_processing"]
ws_other = ws_year.drop(_named)
other_centers = [x for x in ws_other.index if x != "complete, not shipped"]
wk["week_start"] = pd.to_datetime(wk["week_start"])
q3_24 = wk[(wk["week_start"] >= "2024-07-01") & (wk["week_start"] <= "2024-09-29")]
q4_24 = wk[(wk["week_start"] >= "2024-09-30") & (wk["week_start"] <= "2024-12-29")].reset_index(drop=True)
_roll = q4_24["laser_utilization"].rolling(6).mean()
laser_six = q4_24.iloc[int(_roll.idxmax()) - 5:int(_roll.idxmax()) + 1]          # the six consecutive weeks of the fourth quarter with the highest laser load
assert laser_six["week_start"].min() >= pd.Timestamp("2024-11-04")
brake_rest = brake_weeks["machine_hours"].sum() / (brake_weeks["scheduled_hours"].sum() - brake_weeks["downtime_hours"].sum())
_gap = (SY["late"] - SY["on time"]).sort_values(ascending=False)
assert _gap.index[0] == "queue: press brake"


# ── tables ──────────────────────────────────────────────────────────────────
def stage_table(p, tot):
    rows = []
    for s, r in p.iterrows():
        rows.append([STAGE.get(s, s), d2(r["all"]), pct(r["share"]), d2(r["on time"]), d2(r["late"])])
    rows.append(["Lead time, mean", d2(tot.loc["all", "lead_time_mean"]), "", d2(tot.loc["on time", "lead_time_mean"]), d2(tot.loc["late", "lead_time_mean"])])
    rows.append(["Lead time, median", d1(tot.loc["all", "lead_time_median"]), "", d1(tot.loc["on time", "lead_time_median"]), d1(tot.loc["late", "lead_time_median"])])
    rows.append(["Jobs", n0(tot.loc["all", "jobs"]), "", n0(tot.loc["on time", "jobs"]), n0(tot.loc["late", "jobs"])])
    return table(pd.DataFrame(rows, columns=["Stage", "All jobs", "Share of lead time", "On time", "Late"]))


def t1():
    rows = []
    for per, S in (("2025", Y), (f"2025 {REST}", R)):
        for c in ["all"] + CLASSES:
            r = S.loc[c]
            rows.append([per, c.capitalize(), n0(r["jobs"]), d1(r["quoted_lead_days"]), d1(r["lead_time_median"]), d1(r["lead_time_mean"]), d1(r["lead_time_p90"]),
                         pct(r["share_within_quoted"]), pct(r["on_time_delivery"]), n0(r["late_jobs"]), d1(r["lead_time_median_on_time"]), d1(r["lead_time_median_late"])])
    return table(pd.DataFrame(rows, columns=["Period", "Routing class", "Jobs", "Quoted", "Median", "Mean", "90th percentile", "Within quoted", "On time",
                                             "Late jobs", "Median, on time", "Median, late"]))


def t3():
    rows = []
    for w in qy.sort_values("queue_days", ascending=False).index:
        a, b = qy.loc[w], qr.loc[w]
        rows.append([WC[w], n0(a["operations"]), n0(a["queue_days"]), pct(a["share_of_queue"]), d2(a["mean_queue_days"]), d2(a["median_queue_days"]),
                     d2(a["p90_queue_days"]), pct(b["share_of_queue"]), d2(b["mean_queue_days"]), d2(b["median_queue_days"]), d2(b["p90_queue_days"])])
    return table(pd.DataFrame(rows, columns=["Work center", "Operations", "Queue days", "Share", "Mean", "Median", "90th percentile",
                                             f"Share, {REST}", f"Mean, {REST}", f"Median, {REST}", f"90th percentile, {REST}"]))


def t5():
    rows = []
    for per, r in (("2025", wy), (f"2025 {REST}", wr)):
        rows.append([per, n0(r["working_days"]), n0(r["jobs_shipped"]), n0(r["wip_mean"]), d2(r["throughput_per_day"]), d2(r["quoted_lead_mean"]),
                     n0(r["wip_at_quoted_lead_times"]), d2(r["wip_ratio"]), d2(r["wip_over_throughput_days"]), d2(r["days_in_wip_mean"]), d2(r["lead_time_mean"])])
    return table(pd.DataFrame(rows, columns=["Period", "Working days", "Jobs shipped", "Mean WIP", "Jobs shipped per day", "Mean quoted lead time",
                                             "WIP at quoted lead times", "Ratio", "WIP over throughput (days)", "Mean days in WIP", "Mean lead time"]))


def t5a():
    rows = [[qlabel(r.quarter_start), n0(r.jobs_shipped), n0(r.late_jobs), pct(r.on_time_delivery), d1(r.lead_time_median), d1(r.lead_time_p90)] for r in dq.itertuples()]
    return table(pd.DataFrame(rows, columns=["Quarter shipped", "Jobs shipped", "Late jobs", "On time", "Median lead time", "90th percentile"]))


def t6():
    rows = [[qlabel(r.period_start), n0(r.working_days), n0(r.jobs_shipped), d1(r.throughput_per_day), d1(r.lead_time_days), n0(r.wip_mean),
             d2(r.wip_over_throughput_x_lead_time), "yes" if abs(r.wip_over_throughput_x_lead_time - 1) <= 0.10 else "no"] for r in llq.itertuples()]
    return table(pd.DataFrame(rows, columns=["Quarter", "Working days", "Jobs shipped", "Jobs shipped per day", "Days in WIP", "Mean WIP",
                                             "WIP over (throughput x days in WIP)", "Within 10%"]))


def t7():
    rows = []
    for y, p in peaks.items():
        nxt = dq[dq["quarter_start"] == f"{y + 1}-01-01"]
        rows.append([str(y), n0(p["q3"]), n0(p["peak"]), p["date"].strftime("%b %d"), d1(p["ratio"]),
                     pct(nxt.iloc[0]["on_time_delivery"]) if len(nxt) else "", d1(nxt.iloc[0]["lead_time_median"]) if len(nxt) else ""])
    return table(pd.DataFrame(rows, columns=["Year", "Third-quarter mean WIP", "December peak WIP", "Peak date", "Peak over third-quarter mean",
                                             "On time, following first quarter", "Median lead time, following first quarter"]))


# ── report ──────────────────────────────────────────────────────────────────
def see(*tables):
    """One sentence pointing to appendix tables, each linked once in the report."""
    links = [f"<a href='#t{t.lower()}'>{t}</a>" for t in tables]
    return f"See Appendix Table{'s' if len(links) > 1 else ''} {join_and(links)} for additional detail."


def chart(title, img, note=""):
    return f"<div class='chart-title'>{title}</div>{img}" + (f"<div class='caption'>{note}</div>" if note else "")


NUMBER = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine"}


def report():
    ya, ra = Y.loc["all"], R.loc["all"]
    bq = "queue: press brake"
    b = []
    P0 = lambda x: pct(x, 0)
    b.append("<h2 id='f1'>1. Job Flow</h2>")
    b.append(f"<p>Every job follows the same flow through the shop between its release onto the floor and its shipment to the customer, shown below. It is cut on the laser "
             f"or the punch, waiting first for its traveler to print and, when it is not on hand, for its material. Most laser-cut parts then have their edges deburred. Every "
             f"job is formed on the press brakes ({P0(FLOW['second_form'])} return to them for a second forming operation, {P0(FLOW['second_form_after_hardware'])} of those after "
             f"hardware is inserted between bends). {P0(FLOW['hardware'])} then have hardware inserted and {P0(FLOW['weld'])} are welded, by hand or on the robotic cell, and every "
             f"welded part is ground. {P0(FLOW['powder'])} are powder coated and {P0(FLOW['outside'])} go out for plating or other outside processing; {P0(FLOW['assembly'])} are "
             f"then assembled. Every job ends at inspection and pack, then waits to ship. At each work center the job moves, queues, and is set up and run, and holds can stop it "
             f"at any point. At any moment every job in WIP sits somewhere in this flow, and its lead time, the working days from release to shipment, is the time it takes to pass "
             f"through it. Queue is measured from arrival at a work center to first start, setup and run from first start to completion, and move from the end of one operation "
             f"to arrival at the next.</p>")
    b.append(chart("Job Flow Through the Shop, Release to Shipment", fig_job_flow()))

    b.append("<h2 id='f2'>2. Actual vs. quoted lead times</h2>")
    b.append(f"<p>In {YEAR}, the median job shipped in {d1(ya['lead_time_median'])} working days vs. an average quoted lead time of {d1(ya['quoted_lead_days'])}; "
             f"in {RT}, it was {d1(ra['lead_time_median'])} vs. {d1(ra['quoted_lead_days'])}. The quoted lead time was met on {pct(ya['share_within_quoted'], 0)} of jobs in "
             f"{YEAR} and {pct(ra['share_within_quoted'], 0)} in {RT}. The quote was met on {hit['repeat part'][0]} of repeat-part jobs in {YEAR} ({hit['repeat part'][1]} in {RT}), "
             f"{hit['new part'][0]} of new-part jobs ({hit['new part'][1]}) and {hit['outside processing'][0]} of outside-processing jobs "
             f"({hit['outside processing'][1]}). {see('1')}</p>")
    b.append("<p>The shop quotes lead times by starting with a routing class standard (10 working days for repeat parts, 15 for new parts and 20 with outside processing) "
             "which is then adjusted slightly based on current shop capacity and WIP levels. <a href='#f5'>Section 5</a> analyzes the quote against the brake backlog.</p>")
    b.append(chart("Actual vs. Quoted Lead Times, by Routing Class", fig_distribution()))

    b.append("<h2 id='f3'>3. Lead time decomposition</h2>")
    b.append(chart(f"Where Lead Time Goes: Mean Working Days per Job by Step in the Job Flow, {YEAR} and {RT}", fig_flow_days()))
    fy, fr = flow_shares(FY), flow_shares(FR)
    b.append(f"<p>Of the {d1(fy['total'])} working days the average job spent from release to shipment in {YEAR}, {P0(fy['waiting'])} was waiting and {P0(fy['working'])} was "
             f"setup and run, with the rest at outside vendors; the brake queue alone was {d1(BRAKE_QUEUE['year'])} days, {P0(BRAKE_QUEUE['year'] / fy['total'])} of the total. In "
             f"{RT} the average job took {d1(fr['total'])} days, {P0(fr['waiting'])} of them waiting, and the brake queue's share fell to {P0(BRAKE_QUEUE['rest'] / fr['total'])}.</p>")
    g, i, pb = "grind_deburr", "inspection_pack", "press_brake"
    b.append(f"<p>The waiting is concentrated: the brakes held {pct(qy.loc[pb, 'share_of_queue'], 0)} of all queue time in {YEAR} and {pct(qr.loc[pb, 'share_of_queue'], 0)} in "
             f"{RT}, grind and deburr {pct(qy.loc[g, 'share_of_queue'], 0)} and {pct(qr.loc[g, 'share_of_queue'], 0)}, and inspection and pack "
             f"{pct(qy.loc[i, 'share_of_queue'], 0)} and {pct(qr.loc[i, 'share_of_queue'], 0)}. The brake queue per operation has a median of "
             f"{d1(qy.loc[pb, 'median_queue_days'])} day in {YEAR} vs. "
             f"{d1(qr.loc[pb, 'median_queue_days'])} in {RT}, and a 90th percentile of {d1(qy.loc[pb, 'p90_queue_days'])} days in {YEAR} vs. "
             f"{d1(qr.loc[pb, 'p90_queue_days'])} in {RT}. {see('3')}</p>")

    b.append("<h2 id='f4'>4. Work in Process</h2>")
    spare = wr["wip_at_quoted_lead_times"] - wr["wip_mean"]
    b.append(f"<p>In {YEAR}, the shop carried an average of {n0(wy['wip_mean'])} WIP jobs against a throughput of about {n0(wy['throughput_per_day'])} shipped a day, "
             f"so a job spent about {n0(wy['wip_over_throughput_days'])} working days on the floor. {YEAR} WIP was skewed by the large Q1 backlog detailed below. WIP averaged {n0(wipd['wip'].mean())} jobs over the past three "
             f"years and peaks every December: {n0(peaks[2023]['peak'])} jobs in 2023, {n0(peaks[2024]['peak'])} in 2024 and {n0(peaks[2025]['peak'])} in 2025.</p>")
    b.append(chart("Average WIP and Working Days on the Floor, 2023 to 2025", fig_wip_quarters()))
    b.append(f"<p>WIP peaked at {n0(peaks[2024]['peak'])} jobs at the end of 2024 against a Q3 2024 average of {n0(peaks[2024]['q3'])}. In Q4 2024, the shop "
             f"released {pct(brake_up, 0)} more brake standard hours than in Q3. This surge pushed the lasers to "
             f"{pct(laser_six['laser_utilization'].mean(), 0)} of scheduled hours on average over the six weeks from "
             f"{laser_six['week_start'].min():%B} {laser_six['week_start'].min().day}, vs. {pct(q3_24['laser_utilization'].mean(), 0)} in Q3. Over those weeks, "
             f"{n0(laser_six['wip_at_laser'].min())} to {n0(laser_six['wip_at_laser'].max())} jobs were waiting to be cut, "
             f"vs. an average of {n0(q3_24['wip_at_laser'].mean())} jobs in Q3. The work then queued at the brakes, which already run at {pct(brake_rest, 0)} in a "
             f"normal quarter, and it took through Q1 and into Q2 {YEAR} to clear this backlog. {see('7')}</p>")
    b.append(chart("Weekly WIP and Net Inflow, Q3 2024 to Q2 2025", fig_weekly_year()))
    turn = lambda a, c: "falls" if c < a else "rises"
    b.append(f"<p>By location, the brakes (queue and run together) hold {pct(ws_year['press_brake'], 0)} of WIP in {YEAR}, while the laser cutting stations hold "
             f"{pct(ws_year['laser'], 0)} and outside processing {pct(ws_year['outside_processing'], 0)}. The other {NUMBER[len(other_centers)]} work centers and jobs "
             f"complete but not yet shipped hold the remaining {pct(ws_other.sum(), 0)} between them, none above {pct(ws_other.max(), 0)}. In {RT} the brakes' share "
             f"{turn(ws_year['press_brake'], ws_rest['press_brake'])} to {pct(ws_rest['press_brake'], 0)} and the lasers' "
             f"{turn(ws_year['laser'], ws_rest['laser'])} to {pct(ws_rest['laser'], 0)}, as a result of the Q1 backlog having been worked through.</p>")
    b.append(f"<p>The {YEAR} average floor WIP of {n0(wy['wip_mean'])} jobs was {d2(wy['wip_ratio'])}x the WIP the quoted lead times imply at measured "
             f"throughput; in {RT} it was {n0(wr['wip_mean'])} WIP jobs against {n0(wr['wip_at_quoted_lead_times'])} implied ({d2(wr['wip_ratio'])}x). The excess for the year is a "
             f"result of the first-quarter backlog. In {RT} the floor carried "
             f"{n0(round(wr['wip_at_quoted_lead_times']) - round(wr['wip_mean']))} fewer jobs than its quoted lead times allow at the throughput it achieved, so it "
             f"could have taken on about {pct(spare / wr['wip_mean'], 0)} more work, or quoted shorter lead times, and still shipped the average job inside its "
             f"quote. {see('5')}</p>")
    b.append(chart("Average Share of Jobs in WIP by Location", fig_wip()))
    ahead = [qlabel(x) for x in llq_miss.loc[llq_miss["wip_over_throughput_x_lead_time"] > 1, "period_start"]]
    behind = [qlabel(x) for x in llq_miss.loc[llq_miss["wip_over_throughput_x_lead_time"] < 1, "period_start"]]
    assert "2024 Q4" in ahead and len(behind) >= 1 and all(x.endswith(("Q4", "Q1", "Q2")) for x in ahead + behind)
    b.append(f"<p>WIP was within 10% of its expected value (measured as <i>throughput x working days</i>) in {llq_in} of the last {len(llq)} quarters, "
             f"meaning the floor was in balance. The {NUMBER[len(llq_miss)]} quarters that miss are all year-end quarters: the builds ({join_and(ahead)}), when WIP "
             f"ran ahead of shipments, and the quarters in which a build shipped ({join_and(behind)}), when shipments ran ahead of WIP. {see('6')}</p>")

    b.append("<h2 id='f5'>5. </h2>")
    b.append(f"<p>A job's due date is the later of the quote and the customer's requested date. {pct(ya['on_time_delivery'], 0)} of jobs shipped by the due date in {YEAR} and {pct(ra['on_time_delivery'], 0)} in {RT}, against the "
             f"shop's {pct(required, 0)} target. The 90th-percentile lead time for all jobs is {d1(ya['lead_time_p90'])} days for {YEAR} and "
             f"{d1(ra['lead_time_p90'])} in {RT}. Late jobs have a median lead time of {d1(ya['lead_time_median_late'])} days against "
             f"{d1(ya['lead_time_median_on_time'])} for on-time jobs. {see('5a', '8')}</p>")
    b.append(chart(f"Working Days Shipped After the Due Date, {YEAR} and {RT}", fig_after_due()))

    b.append("<h2 id='f6'>6. Where late jobs spend their time</h2>")
    b.append("<p>Late jobs spend their extra days in different stages in the year-end build and in ordinary quarters.</p>")
    b.append(f"<p>In {YEAR}, the brake queue was {pct(st(SY, bq, 'share'), 0)} of all jobs' lead time and accounted for the largest share of the extra days on "
             f"late jobs: {d2(st(SY, bq, 'late'))} days against {d2(st(SY, bq, 'on time'))} for on-time jobs. This was due to the first quarter's backlog: the "
             f"2024 year-end build released more work than the brakes could absorb and put {n0(q1['late_jobs'])} of the year's {n0(ya['late_jobs'])} late jobs "
             f"into Q1. In {RT}, with the backlog cleared, late jobs waited less at the brakes than on-time jobs "
             f"({d2(st(SR, bq, 'late'))} days against {d2(st(SR, bq, 'on time'))}).</p>")
    b.append(f"<p>In {RT}, the extra days on late jobs were due to material wait at the first operation "
             f"({d2(st(SR, 'material wait at first operation', 'late'))} days for late jobs vs. {d2(st(SR, 'material wait at first operation', 'on time'))} for "
             f"on-time jobs), outside processing ({d2(st(SR, 'outside processing', 'late'))} vs. {d2(st(SR, 'outside processing', 'on time'))}), "
             f"the robotic weld queue ({d2(st(SR, 'queue: robotic weld', 'late'))} vs. {d2(st(SR, 'queue: robotic weld', 'on time'))}) and "
             f"setup and run ({d2(st(SR, 'setup and run', 'late'))} vs. {d2(st(SR, 'setup and run', 'on time'))}; the average lot size for late jobs was "
             f"{n0(lot_late)} pieces vs. {n0(lot_on)} for on-time jobs). {see('2a', '2b')}</p>")
    b.append(chart("Lead time by stage, on-time vs. late jobs", fig_stages_report()))

    b.append("<h2 id='rec'>Recommendation</h2>")
    b.append(f"<p>Restate the fixed quote as a percentile of the measured lead-time distribution by routing class (Section 5): the 10-day repeat quote is met on "
             f"{hit['repeat part'][1]} of jobs in an ordinary quarter. Plan the fourth-quarter peak with planned Saturday brake shifts from November through February and the setup program, sized on the shop model ([[R:options]]); "
             f"the 2024 build put {n0(q1['late_jobs'])} jobs late in the first quarter of {YEAR}. Ordinary-quarter lateness is taken up in <a href='#f3'>Section 3</a>, where material, vendor and "
             f"robotic weld causes are attributed job by job.</p>")

    b.append("<h2 id='method'>Method and data</h2>")
    b.append(f"<p>Coverage: {n0(ya['jobs'])} jobs shipped in {YEAR}, {n0(ra['jobs'])} in {REST}. Durations are in working days; a scheduled Saturday counts as one. "
             f"Lead time runs from the release date at 10:00 to the ship date at 15:00; days in WIP counts whole days from the release day to the day before "
             f"shipment and is 0.21 days shorter on every job.<br>"
             f"Stages: release to traveler print; first-operation queue (print to first cut, less material wait); material wait at the first operation "
             f"(a recorded material hold, or a job-specific receipt after the print); queue (arrival at the work center to first start, operations after the first, "
             f"less the powder scheduling wait to the next day of the color); setup and run (first start to last end of the operation); move (end of one operation "
             f"to arrival at the next, less recorded holds, so holds not entered remain in it); holds (recorded holds only); outside processing (purchase order "
             f"to receipt, with the wait before it); complete to ship.<br>"
             f"Clock-offs closed automatically at shift end take the median hours of operator-closed transactions of the same work center and type. "
             f"A new-part job is the first order against a new-part quote line within 60 days of the quote decision.<br>"
             f"WIP is jobs released and not shipped, sampled every working day; throughput is jobs shipped per working day; the quarterly balance uses "
             f"days in WIP of the jobs shipped in the quarter, including days before the quarter. Monthly, {int((abs(llm - 1) <= 0.10).sum())} of {len(llm)} "
             f"periods are within 10%; rolling 13 weeks, {int((abs(llr - 1) <= 0.10).sum())} of {len(llr)}.</p>")

    b.append("<h2 id='appendix'>Appendix</h2>")
    b.append("<h3 id='t1'>Table 1. Lead time against the quoted lead time by routing class</h3>" + t1())
    b.append(f"<h3 id='t2a'>Table 2a. Lead time by stage, {YEAR}: mean working days per job, stages in routing order</h3>" + stage_table(SY, TY))
    b.append(f"<h3 id='t2b'>Table 2b. Lead time by stage, {YEAR} {REST}: mean working days per job, stages in routing order</h3>" + stage_table(SR, TR))
    b.append("<h3 id='t3'>Table 3. Queue time by work center</h3>" + t3())
    b.append("<h3 id='t5'>Table 5. Floor WIP against the WIP the quoted lead times imply</h3>" + t5())
    b.append("<h3 id='t5a'>Table 5a. On-time delivery and lead time by quarter shipped</h3>" + t5a())
    b.append("<h3 id='t6'>Table 6. WIP, throughput and days in WIP by calendar quarter</h3>" + t6())
    b.append("<h3 id='t7'>Table 7. Year-end WIP build by year</h3>" + t7())
    b.append(f"<h3 id='t8'>Table 8. Jobs shipped by working days from the due date to the ship date, {YEAR} and {REST}</h3>" + t8())
    b.append("<div class='glossary'>WIP: jobs released and not shipped. Quoted lead time: 10 working days for repeat parts, 15 for new parts, "
             "20 with outside processing. On time: shipped on or before the promised date as last revised.</div>")
    toc = [("f1", "Job Flow"), ("f2", "Actual vs. quoted lead times"), ("f3", "Lead time decomposition"), ("f4", "Work in Process"), ("f5", ""),
           ("f6", "Where late jobs spend their time"),
           ("rec", "Recommendation"), ("method", "Method and data"), ("appendix", "Appendix")]
    scope = (f"Jobs shipped in {YEAR}, whole year and {REST}; records from January 2023 to December 2025.<br>"
             f"Sources: ERP, shop-floor data collection, quality, maintenance and attendance exports (batch {batch}).")
    return {"body": "\n".join(b), "toc": toc[:-3], "meta": scope}


# ── target, countermeasures and follow-up ──────────────────────────────────
COUNTERMEASURES = [
    ("Plan the fourth-quarter peak on the shop model: planned Saturday brake shifts and the setup program ([[R:options]]); a WIP cap and due-date dispatch lower on-time "
     "delivery ([[R:options]])", "Plant manager", "April 2026"),
    ("Restate quoted lead times as a percentile of measured lead time by routing class and brake load (Section 4)", "Estimating and customer service manager", "May 2026"),
]


def control():
    """The target, the countermeasures and the follow-up, for the Recommendation section."""
    target = (f"{pct(required, 0)} of jobs shipped by the promised date in every quarter, the first quarter included.")
    follow = ("Weekly: WIP by location, brake queue per operation, and material wait at the first operation. "
              "Section 4 evaluates these as leading measures of on-time delivery.")
    return target, COUNTERMEASURES, follow


