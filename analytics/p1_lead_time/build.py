"""P1 lead time decomposition: report and figures, read from the marts.

Usage: python -m analytics.p1_lead_time.build
"""
import numpy as np
import pandas as pd

from analytics.db import q
from analytics.style.style import ACCENT, AMBER, BRAND_BLUE, DOCS, GREEN, GREY, LIGHT_BLUE, RED, fig, pct, save, report_shell, table
from analytics.style.style import recommendation_block

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
batch = q("select export_batch_id from marts.mart_p1_lead_time_summary limit 1").iloc[0, 0]
summ = q("select * from marts.mart_p1_lead_time_summary").set_index(["period", "routing_class"])
stage = q("select * from marts.mart_p1_lead_time_by_stage")
queue = q("select * from marts.mart_p1_queue_by_work_center").set_index(["period", "work_center"])
wipi = q("select * from marts.mart_p1_wip_implied").set_index("period")
wloc = q("select location, wip_mean from marts.mart_p1_wip_by_location where period_type = 'report year' order by wip_mean desc")
ll = q("select * from marts.mart_p1_littles_law")
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
    return save(f, "p1_lead_time_distribution", "Lead time distribution by routing class")


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
        ax.barh(yy + 0.2, g["on time"], height=0.38, color=ACCENT, label="On-time")
        ax.barh(yy - 0.2, g["late"], height=0.38, color=AMBER, label="Late")
        ax.set_yticks(yy)
        ax.set_yticklabels(["Setup and run, all work centers" if s == "setup and run" else STAGE.get(s, s.capitalize()) for s in g.index], fontsize=9)
        ax.set_title(label, fontsize=11)
        ax.set_xlabel("Mean working days per job")
    axes[0].legend(frameon=False, loc="lower right")
    f.tight_layout()
    return save(f, "p1_stage_decomposition", "Lead time by stage, on-time and late jobs")


def _paired_columns(ax, labels, a, b, fmt):
    """Two columns per label, the year and the ordinary quarters, each with its value above it."""
    x = np.arange(len(labels))
    for dx, v, color, lab in ((-0.2, a, LIGHT_BLUE, f"{YEAR}"), (0.2, b, BRAND_BLUE, RT)):
        ax.bar(x + dx, v, width=0.38, color=color, label=lab)
        for xi, vi in zip(x, v):
            ax.text(xi + dx, vi, fmt(vi), ha="center", va="bottom", fontsize=7.5)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_ylim(0, max(max(a), max(b)) * 1.1)


def fig_queue():
    d = queue.loc["year"].sort_values("share_of_queue", ascending=False)
    r = queue.loc[REST].reindex(d.index)
    f, ax = fig(h=3.7)
    _paired_columns(ax, [WC[w] for w in d.index], list(d["share_of_queue"] * 100), list(r["share_of_queue"] * 100), lambda v: f"{v:.0f}")
    ax.set_ylabel("Share of queue time (%)")
    h, lab = ax.get_legend_handles_labels()
    f.legend(h, lab, frameon=False, fontsize=9, ncol=2, loc="lower center")
    f.tight_layout(rect=(0, 0.06, 1, 1))
    return save(f, "p1_queue_share", "Queue share by work center")


def fig_wip():
    order = list(wl_year.sort_values(ascending=False).index)
    f, ax = fig(h=3.7)
    _paired_columns(ax, [WC.get(x, x) for x in order], list(wl_year.reindex(order)), list(wl_rest.reindex(order)), lambda v: f"{v:.0f}")
    ax.set_ylabel("Jobs")
    h, lab = ax.get_legend_handles_labels()
    f.legend(h, lab, frameon=False, fontsize=9, ncol=2, loc="lower center")
    f.tight_layout(rect=(0, 0.06, 1, 1))
    return save(f, "p1_wip_by_location", "WIP by location")


def fig_weekly_year():
    """Weekly WIP and the net inflow to it, from the third quarter of 2024 through the second quarter of 2025."""
    d = wk[(wk["week_start"] >= "2024-07-01") & (wk["week_start"] <= "2025-06-29")].copy()
    net = d["releases"] - d["jobs_shipped"]
    f, ax = fig(h=4.2)
    x = pd.to_datetime(d["week_start"])
    ax.plot(x, d["wip_mean"], color=BRAND_BLUE, linewidth=2.4, label="Total WIP (left)")
    ax.plot(x, d["wip_at_laser"], color=GREEN, linewidth=1.9, label="WIP at the laser (left)")
    ax.plot(x, d["wip_at_brakes"], color=AMBER, linewidth=1.9, label="WIP at the brakes (left)")
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
    return save(f, "p1_year_end_build", "Weekly WIP and net inflow, July 2024 to June 2025")


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


NUMBER = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}


def report():
    ya, ra = Y.loc["all"], R.loc["all"]
    bq = "queue: press brake"
    b = []
    b.append("<h2 id='f1'>1. Lead time against the quote</h2>")
    b.append(f"<p>Throughout the report below, data for full-year {YEAR} is compared to data in {RT} {YEAR} because the 2024 year-end build put "
             f"{n0(q1['late_jobs'])} of the year's {n0(ya['late_jobs'])} late jobs into the first quarter. {see('5a')}</p>")
    b.append(f"<p>In {YEAR} the median job shipped in {d1(ya['lead_time_median'])} working days against an average quoted lead time of {d1(ya['quoted_lead_days'])}; "
             f"{d1(ra['lead_time_median'])} in {RT}. The quoted lead time was met on {pct(ya['share_within_quoted'], 0)} of jobs for the year and "
             f"{pct(ra['share_within_quoted'], 0)} in {RT}. The standard quoted lead times are 10 days for repeat parts (met on {hit['repeat part'][0]} of jobs in "
             f"{YEAR} and {hit['repeat part'][1]} in {RT}), 15 days for new parts ({hit['new part'][0]} and {hit['new part'][1]}) and 20 days for outside processing "
             f"({hit['outside processing'][0]} and {hit['outside processing'][1]}). {see('1')}</p>")
    b.append(f"<p>{pct(ya['on_time_delivery'], 0)} of jobs shipped by the promised date in {YEAR} and {pct(ra['on_time_delivery'], 0)} in {RT}, against the "
             f"{pct(required, 0)} target that the key accounts require. The 90th-percentile lead time is {d1(ya['lead_time_p90'])} days for {YEAR} and "
             f"{d1(ra['lead_time_p90'])} in {RT}. Late jobs have a median lead time of {d1(ya['lead_time_median_late'])} days against "
             f"{d1(ya['lead_time_median_on_time'])} for on-time jobs.</p>")
    b.append(chart("Lead Times, Actual vs. Quoted, by Routing Class", fig_distribution()))

    b.append("<h2 id='f2'>2. Lead time decomposition</h2>")
    b.append(f"<p>Throughout {YEAR} the brake queue was {pct(st(SY, bq, 'share'), 0)} of lead time and accounted for the largest share of the extra days on "
             f"late jobs: {d2(st(SY, bq, 'late'))} days against {d2(st(SY, bq, 'on time'))} for on-time jobs. This was due to the first quarter's backlog: the "
             f"2024 year-end build released more work than the brakes could absorb and put {n0(q1['late_jobs'])} of the year's {n0(ya['late_jobs'])} late jobs "
             f"into Q1 (Section 3). In {RT}, with the backlog cleared, late and on-time jobs waited a similar number of days at the brakes "
             f"({d2(st(SR, bq, 'late'))} and {d2(st(SR, bq, 'on time'))}).</p>")
    b.append(f"<p>The extra days on late jobs in {RT} were instead due to material wait at the first operation "
             f"({d2(st(SR, 'material wait at first operation', 'late'))} days for late jobs vs. {d2(st(SR, 'material wait at first operation', 'on time'))} for "
             f"on-time jobs), outside processing ({d2(st(SR, 'outside processing', 'late'))} vs. {d2(st(SR, 'outside processing', 'on time'))}), "
             f"the robotic weld queue ({d2(st(SR, 'queue: robotic weld', 'late'))} vs. {d2(st(SR, 'queue: robotic weld', 'on time'))}) and "
             f"setup and run ({d2(st(SR, 'setup and run', 'late'))} vs. {d2(st(SR, 'setup and run', 'on time'))}; the average lot size for late jobs was "
             f"{n0(lot_late)} pieces vs. {n0(lot_on)} for on-time jobs). The second report, <a href='p2_late_jobs.html'>Why jobs are late</a>, provides more "
             f"detail on these drivers. {see('2a', '2b')}</p>")
    b.append(chart("Lead time by stage, on-time vs. late jobs", fig_stages_report()))
    g, i, pb = "grind_deburr", "inspection_pack", "press_brake"
    b.append(f"<p>Across all work centers, the brakes accounted for {pct(qy.loc[pb, 'share_of_queue'], 0)} of queue time in {YEAR} and "
             f"{pct(qr.loc[pb, 'share_of_queue'], 0)} in {RT}. Grind and deburr follows at {pct(qy.loc[g, 'share_of_queue'], 0)} in {YEAR} and "
             f"{pct(qr.loc[g, 'share_of_queue'], 0)} in {RT}, and inspection and pack at {pct(qy.loc[i, 'share_of_queue'], 0)} and "
             f"{pct(qr.loc[i, 'share_of_queue'], 0)}. The brake queue per operation has a median of {d1(qy.loc[pb, 'median_queue_days'])} day in {YEAR} vs. "
             f"{d1(qr.loc[pb, 'median_queue_days'])} in {RT}, and a 90th percentile of {d1(qy.loc[pb, 'p90_queue_days'])} days in {YEAR} vs. "
             f"{d1(qr.loc[pb, 'p90_queue_days'])} in {RT}. {see('3')}</p>")
    b.append(chart("Queue Time by Work Center", fig_queue(), f"Figure 3. Share of queue time by work center, {YEAR} and {REST}, operations after the first."))

    b.append("<h2 id='f3'>3. Work in Process</h2>")
    spare = wr["wip_at_quoted_lead_times"] - wr["wip_mean"]
    b.append(f"<p>In {YEAR} floor WIP was {n0(wy['wip_mean'])} jobs against the {n0(wy['wip_at_quoted_lead_times'])} the quoted lead times imply at measured "
             f"throughput (ratio {d2(wy['wip_ratio'])}); in {RT} it was {n0(wr['wip_mean'])} against {n0(wr['wip_at_quoted_lead_times'])} "
             f"({d2(wr['wip_ratio'])}). The excess for the year is the first-quarter backlog. In {RT} the floor carried "
             f"{n0(round(wr['wip_at_quoted_lead_times']) - round(wr['wip_mean']))} fewer jobs than its quoted lead times allow at the throughput it achieved, so it "
             f"could have taken on about {pct(spare / wr['wip_mean'], 0)} more work, or quoted shorter lead times, and still shipped the average job inside its "
             f"quote. {see('5')}</p>")
    b.append(f"<p>By location, queue and run together, the brakes hold {pct(wl_share['press_brake'], 0)} of WIP, the lasers {pct(wl_share['laser'], 0)} and "
             f"outside processing {pct(wl_share['outside_processing'], 0)}.</p>")
    b.append(chart("Jobs in WIP by Location", fig_wip()))
    ahead = [qlabel(x) for x in llq_miss.loc[llq_miss["wip_over_throughput_x_lead_time"] > 1, "period_start"]]
    behind = [qlabel(x) for x in llq_miss.loc[llq_miss["wip_over_throughput_x_lead_time"] < 1, "period_start"]]
    assert ahead == ["2024 Q4"] and len(behind) >= 1
    b.append(f"<p>WIP was within 10% of its expected value (jobs shipped per day times the days each job spent in WIP) in {llq_in} of {len(llq)} quarters, so "
             f"in those quarters the floor was in balance. The {NUMBER[len(llq_miss)]} quarters that miss are the 2024 year-end build ({ahead[0]}), when WIP ran "
             f"ahead of shipments, and the quarters in which a build shipped ({join_and(behind)}), when shipments ran ahead of WIP. {see('6')}</p>")
    b.append(f"<p>WIP peaked at {n0(peaks[2024]['peak'])} jobs at the end of 2024 against a Q3 2024 average of {n0(peaks[2024]['q3'])}. In Q4 2024, the shop "
             f"released {pct(brake_up, 0)} more brake standard hours than in Q3. Over six weeks in Q4 2024, this surge pushed the lasers to "
             f"{pct(laser_six['laser_utilization'].mean(), 0)} of scheduled hours on average, vs. {pct(q3_24['laser_utilization'].mean(), 0)} in Q3. During the "
             f"first three of those weeks, {n0(laser_three['wip_at_laser'].min())} to {n0(laser_three['wip_at_laser'].max())} jobs were waiting to be cut, "
             f"vs. an average of {n0(q3_24['wip_at_laser'].mean())} jobs in Q3. The work then queued at the brakes, which already run at {pct(brake_rest, 0)} in a "
             f"normal quarter, and the backlog was worked through in Q1 and into Q2 {YEAR}. {see('7')}</p>")
    b.append(chart("Weekly WIP, Releases and Shipments, Q3 &rsquo;24 to Q2 &rsquo;25", fig_weekly_year()))

    b.append("<h2 id='rec'>Recommendation</h2>")
    b.append(f"<p>Restate the fixed quote as a percentile of the measured lead-time distribution by routing class (P7): the 10-day repeat quote is met on "
             f"{hit['repeat part'][1]} of jobs in an ordinary quarter. Plan the fourth-quarter peak with planned Saturday brake shifts from November through February and the setup program, sized on the shop model (P5); "
             f"the 2024 build put {n0(q1['late_jobs'])} jobs late in the first quarter of {YEAR}. Take ordinary-quarter lateness to P2, where material, vendor and "
             f"robotic weld causes are attributed job by job.</p>")

    b.append(control())

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
    toc = [("f1", "Lead time against the quote"), ("f2", "Lead time decomposition"), ("f3", "Work in Process"),
           ("rec", "Recommendation"), ("method", "Method and data"), ("appendix", "Appendix")]
    html = report_shell("Lead time decomposition", "", "", "\n".join(b), toc)
    (DOCS / "reports").mkdir(parents=True, exist_ok=True)
    (DOCS / "reports" / "p1_lead_time.html").write_text(html, encoding="utf8")


# ── target, countermeasures and follow-up ──────────────────────────────────
COUNTERMEASURES = [
    ("Attribute each late job to a cause and replace the late-reason code with a buffer status record (P2)", "Production control manager", "February 2026"),
    ("Plan the fourth-quarter peak on the shop model: planned Saturday brake shifts and the setup program (P5); a WIP cap and due-date dispatch lower on-time "
     "delivery (P5)", "Plant manager", "April 2026"),
    ("Restate quoted lead times as a percentile of measured lead time by routing class and brake load (P7)", "Estimating and customer service manager", "May 2026"),
]


def control():
    """The target, the countermeasures and the follow-up, for the Recommendation section."""
    target = (f"{pct(required, 0)} of jobs shipped by the promised date in every quarter, the first quarter included.")
    follow = ("Weekly: WIP by location, brake queue per operation, and material wait at the first operation. "
              "P6 evaluates these as leading measures of on-time delivery.")
    return recommendation_block(target, COUNTERMEASURES, follow)


def main():
    report()
    print("wrote docs/reports/p1_lead_time.html")


if __name__ == "__main__":
    main()
