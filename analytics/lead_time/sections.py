"""Lead time decomposition: the sections, tables and figures of its half of the report, read from the marts.

Built by analytics.reports.lead_time_and_late_jobs.
"""
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch, Patch

from analytics.db import q
from analytics.style.style import ACCENT, AMBER, BRAND_BLUE, DARK_GREY as DARK, DOCS, GREEN, GREY, LIGHT_BLUE, RED, TEXT, fig, paired_columns, pct, save, sig, table

YEAR = 2025
REST = "Q2 to Q4"
RT = "Q2-Q4"                                  # the same quarters as written in the report text and its figures
CLASSES = ["repeat part", "new part", "outside processing"]
WC = {"press_brake": "Press brake", "grind_deburr": "Grind and deburr", "inspection_pack": "Inspection and pack", "hardware": "Hardware",
      "weld": "Weld", "robotic_weld": "Robotic weld", "assembly": "Assembly", "powder_coat": "Powder coat", "laser": "Laser", "punch": "Punch",
      "outside_processing": "Outside processing", "complete, not shipped": "Complete, not shipped"}
STAGE = {"release to traveler print": "Release to traveler print", "first-operation queue": "First-operation queue",
         "material wait at first operation": "Material wait at first operation", "queue: press brake": "Queue: press brake",
         "queue: hardware": "Queue: hardware", "queue: weld": "Queue: weld", "queue: robotic weld": "Queue: robotic weld",
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
        ax.axvline(d["quoted_lead_days"].iloc[0], color=RED, linewidth=1.6, linestyle="--", label="Quoted lead time")
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


def fig_stages_diagram():
    """The stages of lead time from release to ship, named as the rows of the stage table."""
    later = [STAGE[s].replace("Queue: ", "").lower() for s in stage.sort_values("stage_order")["stage"].drop_duplicates() if s.startswith("queue:")]
    gap, y, h = 0.25, 2.0, 0.86
    line = [("Release", 0.72, None), ("Release to\ntraveler print", 0.98, WAITING), ("First-operation\nqueue; material wait\nat first operation", 1.3, WAITING),
            ("Setup and run\n(laser or punch)", 1.08, WORKING), ("Move", 0.6, WAITING), ("Queue", 0.62, WAITING), ("Setup\nand run", 0.72, WORKING),
            ("Complete\nto ship", 0.82, WAITING), ("Ship", 0.58, None)]
    branch = 0.5                                   # room after the repeated group for the outside processing branch to rejoin
    f, ax = fig(h=3.5, w=10.0)
    ax.axis("off")
    arrow = dict(arrowstyle="-|>", color=DARK, linewidth=1.1, shrinkA=0, shrinkB=0, mutation_scale=11)
    box = lambda x0, y0, w, hh, **kw: ax.add_patch(FancyBboxPatch((x0, y0), w, hh, boxstyle="round,pad=0.02,rounding_size=0.06", **kw))
    x, edges = 0.1, []
    for k, (name, w, fill) in enumerate(line):
        box(x, y - h / 2, w, h, facecolor=fill or "white", edgecolor=DARK, linewidth=1.6 if fill is None else 0.8)
        ax.text(x + w / 2, y, name, ha="center", va="center", fontsize=8.2, color="white" if fill == WORKING else TEXT, fontweight="bold" if fill is None else None)
        edges.append((x, x + w))
        x += w + (gap + branch if k == 6 else gap)
    for (_, a), (c, _) in zip(edges[:-1], edges[1:]):
        ax.annotate("", (c - 0.03, y), (a + 0.03, y), arrowprops=arrow)
    total = edges[-1][1] + 0.1
    # the repeated group, framed and named
    fa, fb = edges[4][0] - 0.12, edges[6][1] + 0.12
    ax.add_patch(FancyBboxPatch((fa, y - h / 2 - 0.14), fb - fa, h + 0.28, boxstyle="round,pad=0.0,rounding_size=0.08", facecolor="none", edgecolor=ACCENT,
                                linewidth=1.0, linestyle="--"))
    ax.text((fa + fb) / 2, y + h / 2 + 0.24, "each later work center on the routing:\n" + ", ".join(later[:4]) + ",\n" + ", ".join(later[4:]),
            ha="center", va="bottom", fontsize=8, color=TEXT)
    # outside processing, for the routings that need it: it leaves the group and rejoins before complete to ship
    xa, xb, yo, ho = fb - 0.4, (fb + edges[7][0]) / 2, 0.95, 0.62
    oa, ob = xb - 0.22, edges[-1][1]
    box(oa, yo - ho / 2, ob - oa, ho, facecolor=WAITING, edgecolor=DARK, linewidth=0.8)
    ax.text((oa + ob) / 2, yo, "Outside processing\n(PO to receipt)", ha="center", va="center", fontsize=8.2, color=TEXT)
    ax.text((oa + ob) / 2, yo - ho / 2 - 0.1, "routings that need it", ha="center", va="top", fontsize=8, color=TEXT, style="italic")
    ax.plot([xa, xa], [y - h / 2 - 0.14, yo], color=DARK, linewidth=1.1)
    ax.annotate("", (oa - 0.03, yo), (xa, yo), arrowprops=arrow)
    ax.annotate("", (xb, y - 0.02), (xb, yo + ho / 2 + 0.03), arrowprops=arrow)
    # holds sit off the path
    ha_, hb_ = edges[1][0], edges[3][1]
    box(ha_, yo - ho / 2, hb_ - ha_, ho, facecolor=WAITING, edgecolor=DARK, linewidth=0.8, linestyle=":")
    ax.text((ha_ + hb_) / 2, yo, "Holds: anywhere on the routing", ha="center", va="center", fontsize=8.2, color=TEXT)
    # the span that is lead time
    ax.annotate("", (edges[-1][1], 0.12), (edges[0][0], 0.12), arrowprops=dict(arrowstyle="<|-|>", color=DARK, linewidth=0.8, mutation_scale=9, shrinkA=0, shrinkB=0))
    ax.text(total / 2, 0.19, "Lead time, working days", ha="center", va="bottom", fontsize=8.2, color=TEXT)
    ax.set_xlim(0, total)
    ax.set_ylim(-0.05, 3.5)
    f.legend([Patch(facecolor=WAITING, edgecolor=DARK, linewidth=0.6), Patch(facecolor=WORKING)], ["Waiting", "Working"], frameon=False, fontsize=9, ncol=2,
             loc="lower center")
    f.tight_layout(rect=(0, 0.07, 1, 1))
    return save(f, "lead_time_stages_diagram", "Lead time stages, release to shipment")


def fig_queue():
    d = queue.loc["year"].sort_values("share_of_queue", ascending=False)
    r = queue.loc[REST].reindex(d.index)
    f, ax = fig(h=3.7)
    paired_columns(ax, [WC[w] for w in d.index], list(d["share_of_queue"] * 100), list(r["share_of_queue"] * 100), (f"{YEAR}", RT), percent=True)
    ax.set_ylabel("Share of queue time")
    h, lab = ax.get_legend_handles_labels()
    f.legend(h, lab, frameon=False, fontsize=9, ncol=2, loc="lower center")
    f.tight_layout(rect=(0, 0.06, 1, 1))
    return save(f, "lead_time_queue_share", "Queue share by work center")


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
    return save(f, "lead_time_wip_by_quarter", "Average WIP and Days on the Floor by Quarter, 2023 to 2025")


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
laser_three = laser_six.head(3)                                                  # its first three weeks, the three from November 11
assert list(laser_three["week_start"]) == list(laser_weeks["week_start"])
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
    b.append("<h2 id='f1'>1. Lead time stages</h2>")
    b.append("<p>A job's lead time is the number of working days from its release onto the floor to its shipment to the customer. A job moves through the stages "
             "outlined in the diagram below. First, the traveler is printed and the job waits in queue at its first operation, either the laser cutting station or "
             "the punch, and for its material when it is not on hand. It is then cut, and repeats through move, queue, and setup and run at each later work center "
             "on its routing. Where the routing calls for it, the job goes out for outside processing and returns. Holds are counted as their own stage at whatever "
             "point on the routing they occur. Once the job is complete it waits to ship. Queue is defined as arrival at a work center to first start. Setup and run "
             "is measured from first start to completion, and move is measured from the end of one operation to arrival at the next.</p>")
    b.append(chart("Lead time stages, release to shipment", fig_stages_diagram()))

    b.append("<h2 id='f2'>2. Actual vs. quoted lead times</h2>")
    b.append(f"<p>In {YEAR}, the median job shipped in {d1(ya['lead_time_median'])} working days vs. an average quoted lead time of {d1(ya['quoted_lead_days'])}; "
             f"in {RT}, it was {d1(ra['lead_time_median'])} vs. {d1(ra['quoted_lead_days'])}. The quoted lead time was met on {pct(ya['share_within_quoted'], 0)} of jobs in "
             f"{YEAR} and {pct(ra['share_within_quoted'], 0)} in {RT}. The standard quoted lead times are 10 days for repeat parts (met on {hit['repeat part'][0]} of jobs in "
             f"{YEAR} and {hit['repeat part'][1]} in {RT}), 15 days for new parts ({hit['new part'][0]} and {hit['new part'][1]}) and 20 days for outside processing "
             f"({hit['outside processing'][0]} and {hit['outside processing'][1]}). {see('1')}</p>")
    b.append(f"<p>{pct(ya['on_time_delivery'], 0)} of jobs shipped by the promised date in {YEAR} and {pct(ra['on_time_delivery'], 0)} in {RT}, against the "
             f"shop's {pct(required, 0)} target. The 90th-percentile lead time for all jobs is {d1(ya['lead_time_p90'])} days for {YEAR} and "
             f"{d1(ra['lead_time_p90'])} in {RT}. Late jobs have a median lead time of {d1(ya['lead_time_median_late'])} days against "
             f"{d1(ya['lead_time_median_on_time'])} for on-time jobs.</p>")
    b.append(chart("Actual vs. Quoted Lead Times, by Routing Class", fig_distribution()))

    b.append("<h2 id='f3'>3. Lead time decomposition</h2>")
    b.append(f"<p>In {YEAR}, the brake queue was {pct(st(SY, bq, 'share'), 0)} of all jobs' lead time and accounted for the largest share of the extra days on "
             f"late jobs: {d2(st(SY, bq, 'late'))} days against {d2(st(SY, bq, 'on time'))} for on-time jobs. This was due to the first quarter's backlog: the "
             f"2024 year-end build released more work than the brakes could absorb and put {n0(q1['late_jobs'])} of the year's {n0(ya['late_jobs'])} late jobs "
             f"into Q1. In {RT}, with the backlog cleared, late and on-time jobs waited a similar number of days at the brakes "
             f"({d2(st(SR, bq, 'late'))} and {d2(st(SR, bq, 'on time'))}).</p>")
    b.append(f"<p>In {RT}, the extra days on late jobs were due to material wait at the first operation "
             f"({d2(st(SR, 'material wait at first operation', 'late'))} days for late jobs vs. {d2(st(SR, 'material wait at first operation', 'on time'))} for "
             f"on-time jobs), outside processing ({d2(st(SR, 'outside processing', 'late'))} vs. {d2(st(SR, 'outside processing', 'on time'))}), "
             f"the robotic weld queue ({d2(st(SR, 'queue: robotic weld', 'late'))} vs. {d2(st(SR, 'queue: robotic weld', 'on time'))}) and "
             f"setup and run ({d2(st(SR, 'setup and run', 'late'))} vs. {d2(st(SR, 'setup and run', 'on time'))}; the average lot size for late jobs was "
             f"{n0(lot_late)} pieces vs. {n0(lot_on)} for on-time jobs). {see('2a', '2b')}</p>")
    b.append(chart("Lead time by stage, on-time vs. late jobs", fig_stages_report()))
    g, i, pb = "grind_deburr", "inspection_pack", "press_brake"
    b.append(f"<p>Across all work centers, for both on-time and late jobs, the brakes accounted for {pct(qy.loc[pb, 'share_of_queue'], 0)} of queue time in {YEAR} and "
             f"{pct(qr.loc[pb, 'share_of_queue'], 0)} in {RT}. Grind and deburr follows at {pct(qy.loc[g, 'share_of_queue'], 0)} in {YEAR} and "
             f"{pct(qr.loc[g, 'share_of_queue'], 0)} in {RT}, and inspection and pack at {pct(qy.loc[i, 'share_of_queue'], 0)} and "
             f"{pct(qr.loc[i, 'share_of_queue'], 0)}. The brake queue per operation has a median of {d1(qy.loc[pb, 'median_queue_days'])} day in {YEAR} vs. "
             f"{d1(qr.loc[pb, 'median_queue_days'])} in {RT}, and a 90th percentile of {d1(qy.loc[pb, 'p90_queue_days'])} days in {YEAR} vs. "
             f"{d1(qr.loc[pb, 'p90_queue_days'])} in {RT}. {see('3')}</p>")
    b.append(chart("Queue Time by Work Center", fig_queue()))

    b.append("<h2 id='f4'>4. Work in Process</h2>")
    spare = wr["wip_at_quoted_lead_times"] - wr["wip_mean"]
    b.append(f"<p>In {YEAR}, the shop carried an average of {n0(wy['wip_mean'])} WIP jobs against a throughput of about {n0(wy['throughput_per_day'])} shipped a day, "
             f"so a job spent about {n0(wy['wip_over_throughput_days'])} working days on the floor. WIP averaged {n0(wipd['wip'].mean())} jobs over the past three "
             f"years and peaks every December: {n0(peaks[2023]['peak'])} jobs in 2023, {n0(peaks[2024]['peak'])} in 2024 and {n0(peaks[2025]['peak'])} in 2025.</p>")
    b.append(chart("Average WIP and Days on the Floor by Quarter, 2023 to 2025", fig_wip_quarters()))
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
    assert ahead == ["2024 Q4"] and len(behind) >= 1
    b.append(f"<p>WIP was within 10% of its expected value (measured as <i>throughput x working days</i>) in {llq_in} of the last {len(llq)} quarters, "
             f"meaning the floor was in balance. The {NUMBER[len(llq_miss)]} quarters that miss are the 2024 year-end build ({ahead[0]}), when WIP ran "
             f"ahead of shipments, and the quarters in which a build shipped ({join_and(behind)}), when shipments ran ahead of WIP. {see('6')}</p>")
    b.append(f"<p>WIP peaked at {n0(peaks[2024]['peak'])} jobs at the end of 2024 against a Q3 2024 average of {n0(peaks[2024]['q3'])}. In Q4 2024, the shop "
             f"released {pct(brake_up, 0)} more brake standard hours than in Q3. Over six weeks in Q4 2024, this surge pushed the lasers to "
             f"{pct(laser_six['laser_utilization'].mean(), 0)} of scheduled hours on average, vs. {pct(q3_24['laser_utilization'].mean(), 0)} in Q3. During the "
             f"three peak weeks, {n0(laser_three['wip_at_laser'].min())} to {n0(laser_three['wip_at_laser'].max())} jobs were waiting to be cut, "
             f"vs. an average of {n0(q3_24['wip_at_laser'].mean())} jobs in Q3. The work then queued at the brakes, which already run at {pct(brake_rest, 0)} in a "
             f"normal quarter, and it took through Q1 and into Q2 {YEAR} to clear this backlog. The fourth-quarter release is the "
             f"lever: taking the peak on planned Saturday brake shifts from November through February is the option that raised on-time delivery, while a cap on "
             f"release lowered it. <a href='options_tested.html'>Options tested</a> sizes both. {see('7')}</p>")
    b.append(chart("Weekly WIP and Net Inflow, Q3 &rsquo;24 to Q2 &rsquo;25", fig_weekly_year()))

    b.append("<h2 id='rec'>Recommendation</h2>")
    b.append(f"<p>Restate the fixed quote as a percentile of the measured lead-time distribution by routing class ([[R:quoting]]): the 10-day repeat quote is met on "
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
    b.append("<div class='glossary'>WIP: jobs released and not shipped. Quoted lead time: 10 working days for repeat parts, 15 for new parts, "
             "20 with outside processing. On time: shipped on or before the promised date as last revised.</div>")
    toc = [("f1", "Lead time stages"), ("f2", "Actual vs. quoted lead times"), ("f3", "Lead time decomposition"), ("f4", "Work in Process"),
           ("rec", "Recommendation"), ("method", "Method and data"), ("appendix", "Appendix")]
    scope = (f"Jobs shipped in {YEAR}, whole year and {REST}; records from January 2023 to December 2025.<br>"
             f"Sources: ERP, shop-floor data collection, quality, maintenance and attendance exports (batch {batch}).")
    return {"body": "\n".join(b), "toc": toc[:-3], "meta": scope}


# ── target, countermeasures and follow-up ──────────────────────────────────
COUNTERMEASURES = [
    ("Plan the fourth-quarter peak on the shop model: planned Saturday brake shifts and the setup program ([[R:options]]); a WIP cap and due-date dispatch lower on-time "
     "delivery ([[R:options]])", "Plant manager", "April 2026"),
    ("Restate quoted lead times as a percentile of measured lead time by routing class and brake load ([[R:quoting]])", "Estimating and customer service manager", "May 2026"),
]


def control():
    """The target, the countermeasures and the follow-up, for the Recommendation section."""
    target = (f"{pct(required, 0)} of jobs shipped by the promised date in every quarter, the first quarter included.")
    follow = ("Weekly: WIP by location, brake queue per operation, and material wait at the first operation. "
              "[[R:quoting]] evaluates these as leading measures of on-time delivery.")
    return target, COUNTERMEASURES, follow


