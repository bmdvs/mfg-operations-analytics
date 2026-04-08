"""Lead time decomposition: the sections, tables and figures of its half of the report, read from the marts.

Built by analytics.reports.lead_time_and_late_jobs.
"""
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch, Patch, Rectangle

from analytics.db import q
from analytics.style.style import ACCENT, AMBER, BRAND_BLUE, CHART_W, DARK_GREY as DARK, DOCS, GREEN, GREY, LIGHT_BLUE, RED, TEXT, fig, paired_columns, pct, save, sig, table

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
         "complete to ship": "Packed, waiting to ship"}


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
    second_form=float(len(_second) / _flow_jobs), second_form_after_hardware=float((_second["previous"] == "hardware").mean()), hardware=_through(_wc == "hardware"), laser=_through(_wc == "laser"), punch=_through(_wc == "punch"),
    manual_weld=_through(_wc == "weld"), robotic_weld=_through(_wc == "robotic_weld"),
    weld=_through(_wc.isin(["weld", "robotic_weld"])), join=_through(_wc.isin(JOIN)), grind_welds=_through((_wc == "grind_deburr") & _ops["previous"].isin(["weld", "robotic_weld"])),
    powder=_through(_wc == "powder_coat"), outside=_through(_wc == "outside_processing"), finish=_through(_wc.isin(FINISH)), assembly=_through(_wc == "assembly"),
    inspect=_through(_wc == "inspection_pack"))
assert FLOW["cut"] == FLOW["form"] == FLOW["inspect"] == 1.0 and abs(FLOW["grind_welds"] - FLOW["weld"]) < 1e-9 and FLOW["laser_deburr"] > 0.5
_holds = q("""select h.op_seq = f.first_seq as at_first, h.hold_reason from staging.stg_mes__holds h join intermediate.int_job_lead_time l using (job_id)
              join (select job_id, min(op_seq) as first_seq from staging.stg_erp__job_operations group by 1) f using (job_id) where l.ship_date is not null""")
HOLDS_AT_FIRST = float(_holds["at_first"].mean())
assert float((_holds[_holds["at_first"]]["hold_reason"] == "material").mean()) > 0.5

# mean working days per job by step in the job flow: waiting, working and at the vendor, with a job that skips a step counted as zero
FLOW_ROWS = ["Release to traveler print", "Laser", "Punch", "Grind and deburr, edges", "Press brake", "Hardware", "Manual weld", "Robotic weld", "Grind and deburr, welds",
             "Powder coat", "Outside processing", "Assembly", "Inspection and pack", "Holds", "Packed, waiting to ship"]
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
        return wc_.capitalize(), kind
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
AFTER = q(f"""select cs.wd_index - cd.wd_index as days_after, quarter(j.ship_date) as ship_quarter, cr.wd_index - co.wd_index > j.quoted_lead_days as requested_past_quote,
                     j.due_date = ol.requested_date as due_is_requested, cr.wd_index - co.wd_index as requested_lead
              from marts.mart_job_lead_time j join staging.stg_erp__jobs sj using (job_id) join staging.stg_erp__order_lines ol on ol.order_line_id = sj.order_line_id
              join intermediate.int_working_days cs on cs.calendar_date = j.ship_date join intermediate.int_working_days cd on cd.calendar_date = j.due_date
              left join intermediate.int_working_days cr on cr.calendar_date = ol.requested_date left join intermediate.int_working_days co on co.calendar_date = ol.order_date
              where year(j.ship_date) = {YEAR}""")
assert len(AFTER) == len(jobs) and int((AFTER["days_after"] > 0).sum()) == int((~jobs["on_time"]).sum())
EARLY, LATE_CAP = -8, 15
AFTER_BINS = list(range(EARLY, LATE_CAP + 1))
AFTER_LABEL = {EARLY: "8 or more early", LATE_CAP: "15 or more late"}


def after_counts(d):
    return d["days_after"].clip(lower=EARLY, upper=LATE_CAP).value_counts().reindex(AFTER_BINS).fillna(0).astype(int)


AY, AR = after_counts(AFTER), after_counts(AFTER[AFTER["ship_quarter"] >= 2])
EARLY_SHARE = float((AFTER["days_after"] <= -6).mean())                                  # shipped six or more working days before the due date
DUE_IS_REQUESTED = float(AFTER["due_is_requested"].fillna(False).mean())
REQUESTED_LEAD = float(AFTER[AFTER["due_is_requested"].fillna(False)]["requested_lead"].median())


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
    f, axes = fig(h=7.2, ncols=2, grid="x", sharey=True, sharex=True)
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
        for off, col in ((0.2, "on time"), (-0.2, "late")):
            for yi, v in zip(yy, g[col]):
                ax.annotate(f"{v:.1f}", (v, yi + off), textcoords="offset points", xytext=(2, 0), va="center", fontsize=6.5)
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
    """The job flow from release to shipment in one row, the work centers of a stage stacked where it has more than one, each with the share of jobs through it.
    Drawn at the width of the report's text column, one unit to a pixel as the page shows it."""
    P = lambda x: f"{x * 100:.0f}%"
    NL = chr(10)
    WIDE, TALL = 832.0, 286.0
    NAME, SHARE = 8.6, 8.2                                 # points: 12 pixels on the page, against 15 for the body text
    f, ax = fig(h=CHART_W * TALL / WIDE, w=CHART_W)
    ax.set_position([0, 0, 1, 1])
    ax.axis("off")
    arrow = dict(arrowstyle="-|>", color=DARK, linewidth=0.9, shrinkA=0, shrinkB=0, mutation_scale=8)
    go = lambda a, b, **kw: ax.annotate("", b, a, arrowprops=dict(arrow, **kw))
    at = {}

    def box(key, name, x0, w, yc, hh, share=None, edge=0.9, bold=True):
        ax.add_patch(FancyBboxPatch((x0, yc - hh / 2), w, hh, boxstyle="round,pad=0,rounding_size=5", facecolor="white", edgecolor=DARK, linewidth=edge))
        n = name.count(NL) + 1
        if share is None:
            ax.text(x0 + w / 2, yc, name, ha="center", va="center", fontsize=NAME, color=TEXT, fontweight="bold" if bold else None, linespacing=1.12)
        else:
            ax.text(x0 + w / 2, yc + 8, name, ha="center", va="center", fontsize=NAME, color=TEXT, fontweight="bold", linespacing=1.12)
            ax.text(x0 + w / 2, yc - 8 * n - 6, P(share), ha="center", va="center", fontsize=SHARE, color=TEXT)
        at[key] = (x0, x0 + w, yc, hh)

    def stage(label, x0, w, top):
        ax.text(x0 + w / 2, top + 6, label, ha="center", va="bottom", fontsize=NAME, color=TEXT, fontweight="bold")

    y, x, gap = 142.0, 2.0, 18.0
    box("print", "Release to" + NL + "traveler" + NL + "print", x, 68, y, 90, bold=False)
    box("release", "Release", x, 68, 262, 32, edge=1.6)
    x += 68 + gap
    box("laser", "Laser", x, 48, y + 32, 54, FLOW["laser"])
    box("punch", "Punch", x, 48, y - 32, 54, FLOW["punch"])
    stage("Cut", x, 48, y + 59)
    x += 48 + gap
    box("deburr", "Grind and" + NL + "deburr", x, 74, y, 90, FLOW["deburr"])
    x += 74 + gap
    box("brake", "Press" + NL + "brake", x, 50, y, 90, FLOW["form"])
    x += 50 + gap
    box("hardware", "Hardware", x, 72, y + 68, 52, FLOW["hardware"])
    box("weld", "Manual" + NL + "weld", x, 72, y, 64, FLOW["manual_weld"])
    box("robot", "Robotic" + NL + "weld", x, 72, y - 72, 64, FLOW["robotic_weld"])
    stage("Insert and join", x, 72, y + 94)
    x += 72 + gap
    box("grind", "Grind and" + NL + "deburr", x, 74, y - 36, 112, FLOW["grind_welds"])
    x += 74 + gap
    box("powder", "Powder" + NL + "coat", x, 82, y + 44, 64, FLOW["powder"])
    box("outside", "Outside" + NL + "processing", x, 82, y - 36, 64, FLOW["outside"])
    stage("Finish", x, 82, y + 76)
    x += 82 + gap
    box("assembly", "Assemble", x, 72, y, 90, FLOW["assembly"])
    x += 72 + gap
    box("inspect", "Inspect" + NL + "and pack", x, 68, y, 90, FLOW["inspect"])
    x += 68 + gap
    box("packed", "Packed," + NL + "waiting" + NL + "to ship", x, 58, y, 90, bold=False)
    box("ship", "Shipment", x + 58 - 70, 70, 262, 32, edge=1.6)
    L, R, Y = (lambda n: at[n][0] - 2), (lambda n: at[n][1] + 2), (lambda n: at[n][2])
    link = lambda a, b, dy=0.0, dz=0.0: go((R(a), Y(a) + dy), (L(b), Y(b) + dz))
    mid = lambda n: (at[n][0] + at[n][1]) / 2
    go((mid("release"), at["release"][2] - 18), (mid("print"), at["print"][2] + 47))
    go((mid("packed"), at["packed"][2] + 47), (mid("packed"), at["ship"][2] - 18))
    link("print", "laser", 12)
    link("print", "punch", -12)
    link("laser", "deburr", 0, 14)
    link("punch", "deburr", 0, -14)
    link("deburr", "brake")
    link("brake", "hardware", 18)
    link("brake", "weld")
    link("brake", "robot", -18)
    link("weld", "grind", 0, 30)
    link("robot", "grind", 0, -30)
    link("hardware", "powder", 8, 16)
    link("grind", "powder", 40, -14)
    link("grind", "outside", -4)
    link("powder", "assembly", 0, 18)
    link("outside", "assembly", 0, -18)
    link("assembly", "inspect")
    link("inspect", "packed")
    # inside a stage: hardware on to a weld, powder coat on to outside processing
    hx = at["hardware"][0] + 12
    go((hx, at["hardware"][2] - 27), (hx, at["weld"][2] + 33))
    ax.annotate("", (R("robot") - 1, Y("robot") + 12), (R("hardware") - 1, Y("hardware") - 12), arrowprops=dict(arrow, connectionstyle="arc3,rad=-0.22"))
    px = at["powder"][0] + 16
    go((px, at["powder"][2] - 33), (px, at["outside"][2] + 33))
    ax.text(WIDE / 2, 20, "Percentages are the share of jobs that pass through each work center", ha="center", va="center", fontsize=SHARE, color=TEXT)
    ax.set_xlim(0, WIDE)
    ax.set_ylim(8, 8 + TALL)
    return save(f, "job_flow_diagram", "Job Flow, Release to Shipment")


VENDOR = AMBER


def flow_shares(g):
    t = g["total"].sum()
    return dict(total=float(t), waiting=float(g["waiting"].sum() / t), working=float(g["working"].sum() / t), vendor=float(g["vendor"].sum() / t))


def fig_flow_days():
    f, axes = fig(h=5.4, ncols=2, grid="x", sharey=True, sharex=True)
    yy = np.arange(len(FLOW_ROWS))[::-1]
    for ax, (g, label) in zip(axes, ((FY, f"{YEAR}"), (FR, RT))):
        s = flow_shares(g)
        edge = dict(edgecolor=DARK, linewidth=0.4)
        ax.barh(yy, g["waiting"], height=0.66, color=WAITING, label="Waiting (move and queue)", **edge)
        ax.barh(yy, g["working"], height=0.66, left=g["waiting"], color=WORKING, label="Working (setup and run)", **edge)
        ax.barh(yy, g["vendor"], height=0.66, left=g["waiting"] + g["working"], color=VENDOR, label="At the vendor", **edge)
        for yi, v in zip(yy, g["total"]):
            ax.annotate(f"{v:.2f}", (v, yi), textcoords="offset points", xytext=(3, 0), va="center", fontsize=7.8)
        ax.set_yticks(yy)
        ax.set_yticklabels(FLOW_ROWS, fontsize=9)
        ax.set_title(label, fontsize=10)
        ax.set_xlabel("Working days per job")
    axes[0].set_xlim(0, float(FY["total"].max()) * 1.12)
    h, lab = axes[0].get_legend_handles_labels()
    f.legend(h, lab, frameon=False, fontsize=9, ncol=3, loc="lower center")
    f.tight_layout(rect=(0, 0.05, 1, 1))
    return save(f, "lead_time_by_flow_step", f"Lead Time Decomposition by Stage, {YEAR} and {RT}")


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
    ax.set_xticks(AFTER_BINS)
    ax.set_xticklabels(["8 or" + chr(10) + "more" + chr(10) + "early" if t == EARLY else "15 or" + chr(10) + "more" + chr(10) + "late" if t == LATE_CAP else str(t) for t in AFTER_BINS],
                       fontsize=8)
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
    b.append("<h2 id='f1'>1. </h2>")
    b.append("<p>Every job follows the same general flow through the shop between its release onto the floor and its shipment to the customer. At any moment every job in "
             "WIP sits somewhere in this flow, and its lead time, the working days from release to shipment, is the time it takes to pass through it.</p>")
    b.append(chart("Job Flow, Release to Shipment", fig_job_flow()))

    b.append("<h2 id='f2'>2. Actual vs. quoted lead times</h2>")
    b.append(f"<p>In {YEAR}, the median job shipped in {d1(ya['lead_time_median'])} working days vs. an average quoted lead time of {d1(ya['quoted_lead_days'])}; "
             f"in {RT}, it was {d1(ra['lead_time_median'])} vs. {d1(ra['quoted_lead_days'])}. The quoted lead time was met on {pct(ya['share_within_quoted'], 0)} of jobs in "
             f"{YEAR} and {pct(ra['share_within_quoted'], 0)} in {RT}. The quote was met on {hit['repeat part'][0]} of repeat-part jobs in {YEAR} ({hit['repeat part'][1]} in {RT}), "
             f"{hit['new part'][0]} of new-part jobs ({hit['new part'][1]}) and {hit['outside processing'][0]} of outside-processing jobs "
             f"({hit['outside processing'][1]}). {see('1')}</p>")
    b.append("<p>The shop quotes lead times by starting with a routing class standard (10 working days for repeat parts, 15 for new parts and 20 with outside processing) "
             "which is then adjusted slightly based on current shop capacity and WIP levels. <a href='#f4'>Section 4</a> analyzes the quote against the brake backlog.</p>")
    b.append(chart("Actual vs. Quoted Lead Times, by Routing Class", fig_distribution()))

    b.append("<h2 id='f3'>3. Lead time decomposition</h2>")
    fy, fr = flow_shares(FY), flow_shares(FR)
    pb = "press_brake"
    b.append(f"<p>In {YEAR}, the average lead time of all jobs was {d1(fy['total'])} days, and in {RT} it was {d1(fr['total'])} days. {P0(fy['waiting'])} of lead time in {YEAR} was "
             f"spent waiting (movement between and queueing at work centers), against {P0(fy['working'])} spent working at machines (both setup and run), and "
             f"{P0(fy['vendor'])} with outside vendors. The time spent waiting was concentrated: in {YEAR}, the brake queue alone was {d1(BRAKE_QUEUE['year'])} days of the average "
             f"job's lead time ({P0(BRAKE_QUEUE['year'] / fy['total'])} of total), and the brakes held {pct(qy.loc[pb, 'share_of_queue'], 0)} of all queue time. The brake queue time "
             f"in {YEAR} was highly skewed: the median queue time was {d1(qy.loc[pb, 'median_queue_days'])} day, with a 90th percentile of {d1(qy.loc[pb, 'p90_queue_days'])} days. "
             f"We've presented {RT} data alongside {YEAR}, as this largely removes the impact of the Q4 build and presents a more normalized view. {see('3')}</p>")
    b.append(chart(f"Lead Time Decomposition by Stage, {YEAR} and {RT}", fig_flow_days()))

    b.append("<h2 id='f4'>4. </h2>")
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
    b.append(chart("Average Share of Jobs in WIP by Location", fig_wip()))
    b.append(f"<p>The {YEAR} average floor WIP of {n0(wy['wip_mean'])} jobs was {d2(wy['wip_ratio'])}x the WIP the quoted lead times imply at measured "
             f"throughput; in {RT} it was {n0(wr['wip_mean'])} WIP jobs against {n0(wr['wip_at_quoted_lead_times'])} implied ({d2(wr['wip_ratio'])}x). The excess for the year is a "
             f"result of the first-quarter backlog. In {RT} the floor carried "
             f"{n0(round(wr['wip_at_quoted_lead_times']) - round(wr['wip_mean']))} fewer jobs than its quoted lead times allow at the throughput it achieved, so it "
             f"could have taken on about {pct(spare / wr['wip_mean'], 0)} more work, or quoted shorter lead times, and still shipped the average job inside its "
             f"quote. {see('5')}</p>")

    b.append("<h2 id='f5'>5. </h2>")
    ly, lr = late_stats(AFTER), late_stats(AFTER[AFTER["ship_quarter"] >= 2])
    b.append(f"<p>A job's due date is set as the later of the quote and the customer's requested date. Requested dates were {P0(DUE_IS_REQUESTED)} of job due dates in {YEAR}, "
             f"with a median of {n0(REQUESTED_LEAD)} working days. On-time delivery was {pct(ya['on_time_delivery'], 0)} in {YEAR}, and in {RT} once the backlog was worked "
             f"through, on-time delivery was {pct(ra['on_time_delivery'], 0)}.</p>")
    b.append(f"<p>There were {n0(ly['late'])} late jobs in {YEAR}, with a median days late of {n0(ly['median'])} and a 90th percentile of {n0(ly['p90'])}. That dropped to "
             f"{n0(lr['late'])} late jobs in {RT}, with a median days late of {n0(lr['median'])} and a 90th percentile of {n0(lr['p90'])}. In {YEAR}, {P0(EARLY_SHARE)} of jobs "
             f"shipped 6 days or more before the due date. {see('5a', '8')}</p>")
    b.append(chart(f"Working Days Shipped After the Due Date, {YEAR} and {RT}", fig_after_due()))

    b.append("<h2 id='f6'>6. Where late jobs spend their time</h2>")
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
    b.append("<h3 id='t7'>Table 7. Year-end WIP build by year</h3>" + t7())
    b.append(f"<h3 id='t8'>Table 8. Jobs shipped by working days from the due date to the ship date, {YEAR} and {REST}</h3>" + t8())
    b.append("<div class='glossary'>WIP: jobs released and not shipped. Quoted lead time: 10 working days for repeat parts, 15 for new parts, "
             "20 with outside processing. On time: shipped on or before the promised date as last revised.</div>")
    toc = [("f1", ""), ("f2", "Actual vs. quoted lead times"), ("f3", "Lead time decomposition"), ("f4", ""), ("f5", ""),
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


