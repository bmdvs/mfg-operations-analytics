"""P1 lead time decomposition: report, A3 and figures, read from the marts.

Usage: python -m analytics.p1_lead_time.build
"""
import numpy as np
import pandas as pd

from analytics.db import q
from analytics.style.style import ACCENT, AMBER, BRAND_BLUE, DOCS, GREY, LIGHT_BLUE, RED, a3_shell, fig, pct, save, report_shell, table

YEAR = 2025
REST = "Q2 to Q4"
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
    f, axes = fig(h=3.3, ncols=3, sharey=False)
    bins = np.arange(0, 46, 1)
    for ax, cls in zip(axes, CLASSES):
        d = jobs[jobs["routing_class"] == cls]
        ax.hist(d["lead_time_wd"].clip(upper=45), bins=bins, color=LIGHT_BLUE, label=f"{YEAR}")
        ax.hist(d.loc[d["ship_quarter"] >= 2, "lead_time_wd"].clip(upper=45), bins=bins, color=BRAND_BLUE, label=REST)
        ax.axvline(d["quoted_lead_days"].iloc[0], color=RED, linewidth=1.6, linestyle="--", label="Quoted lead time")
        ax.set_title(cls.capitalize(), fontsize=11)
        ax.set_xlabel("Lead time (working days)")
    axes[0].set_ylabel("Jobs")
    axes[0].legend(frameon=False, fontsize=8.5)
    f.tight_layout()
    return save(f, "p1_lead_time_distribution", "Lead time distribution by routing class")


def fig_stages(name="p1_stage_decomposition", up=1, h=5.6):
    f, axes = fig(h=h, ncols=2, grid="x", sharey=True)
    for ax, (p, label) in zip(axes, ((SY, f"{YEAR}"), (SR, f"{YEAR} {REST}"))):
        g = p.copy()
        holds = g[g.index.str.startswith("hold:")][["on time", "late"]].sum()
        g = g[~g.index.str.startswith("hold:")]
        g.loc["hold (recorded)", ["on time", "late"]] = holds.values
        g.loc["hold (recorded)", "order"] = 16
        g = g.sort_values("order", ascending=False)
        yy = np.arange(len(g))
        ax.barh(yy + 0.2, g["on time"], height=0.38, color=ACCENT, label="On time")
        ax.barh(yy - 0.2, g["late"], height=0.38, color=AMBER, label="Late")
        ax.set_yticks(yy)
        ax.set_yticklabels([STAGE.get(s, s.capitalize()) for s in g.index], fontsize=9)
        ax.set_title(label, fontsize=11)
        ax.set_xlabel("Mean working days per job")
    axes[0].legend(frameon=False, loc="lower right")
    f.tight_layout()
    return save(f, name, "Lead time by stage, on-time and late jobs", up)


def fig_queue():
    d = queue.loc["year"].sort_values("share_of_queue", ascending=False)
    r = queue.loc[REST].reindex(d.index)
    f, ax = fig(h=3.3)
    x = np.arange(len(d))
    ax.bar(x - 0.2, d["share_of_queue"] * 100, width=0.38, color=LIGHT_BLUE, label=f"{YEAR}")
    ax.bar(x + 0.2, r["share_of_queue"] * 100, width=0.38, color=BRAND_BLUE, label=REST)
    ax.set_xticks(x)
    ax.set_xticklabels([WC[w] for w in d.index], rotation=20, ha="right")
    ax.set_ylabel("Share of queue time (%)")
    ax.legend(frameon=False)
    f.tight_layout()
    return save(f, "p1_queue_share", "Queue share by work center")


def fig_wip():
    d = wloc.iloc[::-1]
    f, ax = fig(h=3.4, grid="x")
    ax.barh([WC.get(x, x) for x in d["location"]], d["wip_mean"], color=[BRAND_BLUE if x == "press_brake" else ACCENT if x == "laser" else LIGHT_BLUE for x in d["location"]])
    ax.set_xlabel("Mean jobs in WIP")
    f.tight_layout()
    return save(f, "p1_wip_by_location", "WIP by location")


def build_weeks():
    return wk[(wk["week_start"] >= "2024-09-30") & (wk["week_start"] <= "2025-03-30")].copy()


def fig_build(name="p1_year_end_build", up=1, h=3.8):
    d = build_weeks()
    f, ax = fig(h=h)
    x = pd.to_datetime(d["week_start"])
    for xs, wd in zip(x, d["weekdays"]):
        if wd < 5:
            ax.axvspan(xs - pd.Timedelta(days=3.5), xs + pd.Timedelta(days=3.5), color="#F1E3CF", zorder=0)
    ax.plot(x, d["wip_mean"], color=BRAND_BLUE, linewidth=2.2, label="WIP (jobs, left)")
    ax.plot(x, d["wip_at_laser"], color=ACCENT, linewidth=1.4, linestyle="--", label="WIP at the laser (left)")
    ax.plot(x, d["wip_at_brakes"], color=AMBER, linewidth=1.4, linestyle="--", label="WIP at the brakes (left)")
    ax.set_ylabel("Jobs in WIP")
    ax2 = ax.twinx()
    ax2.bar(x - pd.Timedelta(days=1.3), d["releases"], width=2.4, color=LIGHT_BLUE, label="Releases (right)")
    ax2.bar(x + pd.Timedelta(days=1.3), d["jobs_shipped"], width=2.4, color=GREY, label="Shipments (right)")
    ax2.set_ylabel("Jobs per week")
    ax2.set_ylim(0, d["releases"].max() * 3.2)
    for s in ("top",):
        ax2.spines[s].set_visible(False)
    ax.set_zorder(ax2.get_zorder() + 1)
    ax.patch.set_visible(False)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.set_ylim(0, d["wip_mean"].max() * 1.08)
    ax.legend(h1 + h2, l1 + l2, frameon=False, fontsize=8.5, ncol=5, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    f.tight_layout()
    return save(f, name, "Weekly WIP, releases and shipments, October 2024 to March 2025", up)


# ── measured values used in the text ────────────────────────────────────────
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
HEADER_META = (f"Custom sheet-metal fabrication job shop, about 120 employees, one plant. Jobs shipped in {YEAR}, whole year and {REST}; "
               f"records from January 2023 to December 2025.<br>"
               f"Sources: ERP, shop-floor data collection, quality, maintenance and attendance exports (batch {batch}). "
               f"All durations in working days, scheduled Saturdays counted.")


def report():
    ya, ra = Y.loc["all"], R.loc["all"]
    miss = join_and([qlabel(x) for x in llq_miss["period_start"]])
    lw = laser_weeks
    b = []
    b.append("<h2 id='f1'>1. Lead time against the quote</h2>")
    b.append(f"<p>The median job ships in {d1(ya['lead_time_median'])} working days against an average quoted lead time of {d1(ya['quoted_lead_days'])}; "
             f"{d1(ra['lead_time_median'])} in {REST}. The fixed quote is met on {pct(ya['share_within_quoted'], 0)} of jobs for the year and "
             f"{pct(ra['share_within_quoted'], 0)} in {REST}: repeat parts {hit['repeat part'][0]} and {hit['repeat part'][1]} at 10 days, new parts "
             f"{hit['new part'][0]} and {hit['new part'][1]} at 15, outside processing {hit['outside processing'][0]} and {hit['outside processing'][1]} at 20.</p>")
    b.append(f"<p>{pct(ya['on_time_delivery'])} of jobs shipped by the promised date for the year and {pct(ra['on_time_delivery'])} in {REST}, against the "
             f"{pct(required, 0)} the key accounts require. The 90th-percentile lead time is {d1(ya['lead_time_p90'])} days for the year and "
             f"{d1(ra['lead_time_p90'])} in {REST}. Late jobs have a median of {d1(ya['lead_time_median_late'])} days against "
             f"{d1(ya['lead_time_median_on_time'])} for on-time jobs.</p>")
    b.append(fig_distribution())
    b.append(f"<div class='caption'>Figure 1. Lead time of jobs shipped in {YEAR} by routing class, with {REST} overlaid and the quoted lead time marked.</div>")

    b.append("<h2 id='f2'>2. Where the days go</h2>")
    b.append(f"<p>For the year, the brake queue is {pct(st(SY, 'queue: press brake', 'share'), 0)} of lead time and the stage that separates late jobs from "
             f"on-time jobs: {d2(st(SY, 'queue: press brake', 'late'))} days against {d2(st(SY, 'queue: press brake', 'on time'))}.</p>")
    b.append(f"<p>In {REST} the brake queue is the same for both: {d2(st(SR, 'queue: press brake', 'late'))} days for late jobs against "
             f"{d2(st(SR, 'queue: press brake', 'on time'))} for on-time jobs. Late jobs in those quarters differ in material wait at the first operation "
             f"({d2(st(SR, 'material wait at first operation', 'late'))} against {d2(st(SR, 'material wait at first operation', 'on time'))}), "
             f"outside processing ({d2(st(SR, 'outside processing', 'late'))} against {d2(st(SR, 'outside processing', 'on time'))}), "
             f"the robotic weld queue ({d2(st(SR, 'queue: robotic weld', 'late'))} against {d2(st(SR, 'queue: robotic weld', 'on time'))}) and "
             f"setup and run ({d2(st(SR, 'setup and run', 'late'))} against {d2(st(SR, 'setup and run', 'on time'))}; their mean lot is "
             f"{n0(lot_late)} pieces against {n0(lot_on)}).</p>")
    b.append(fig_stages())
    b.append(f"<div class='caption'>Figure 2. Mean working days per job at each stage, on-time against late jobs, {YEAR} and {REST}.</div>")

    b.append("<h2 id='f3'>3. Queue time by work center</h2>")
    g, i = "grind_deburr", "inspection_pack"
    b.append(f"<p>The brakes hold {pct(qy.loc['press_brake', 'share_of_queue'], 0)} of queue time for the year and {pct(qr.loc['press_brake', 'share_of_queue'], 0)} "
             f"in {REST}. Grind and deburr follows at {pct(qy.loc[g, 'share_of_queue'], 0)} and {pct(qr.loc[g, 'share_of_queue'], 0)}, inspection and pack at "
             f"{pct(qy.loc[i, 'share_of_queue'], 0)} and {pct(qr.loc[i, 'share_of_queue'], 0)}. The brake queue per operation has a median of "
             f"{d1(qy.loc['press_brake', 'median_queue_days'])} day and a 90th percentile of {d1(qy.loc['press_brake', 'p90_queue_days'])} days for the year, "
             f"{d1(qr.loc['press_brake', 'p90_queue_days'])} in {REST}.</p>")
    b.append(fig_queue())
    b.append(f"<div class='caption'>Figure 3. Share of queue time by work center, {YEAR} and {REST}, operations after the first.</div>")

    b.append("<h2 id='f4'>4. WIP against the quoted lead times</h2>")
    b.append(f"<p>Floor WIP is {n0(wy['wip_mean'])} jobs against the {n0(wy['wip_at_quoted_lead_times'])} the quoted lead times imply at measured throughput "
             f"for the year (ratio {d2(wy['wip_ratio'])}), and {n0(wr['wip_mean'])} against {n0(wr['wip_at_quoted_lead_times'])} in {REST} "
             f"({d2(wr['wip_ratio'])}). In {REST} the floor carries less WIP than its quotes allow; the gap between quote and delivery is dispersion, not level.</p>")
    b.append(f"<p>The brakes hold {pct(wl_share['press_brake'], 0)} of WIP, released work not yet cut at the laser {pct(wl_share['laser'], 0)} and "
             f"outside processing {pct(wl_share['outside_processing'], 0)}.</p>")
    b.append(fig_wip())
    b.append(f"<div class='caption'>Figure 4. Mean jobs in WIP by location, {YEAR}.</div>")

    b.append("<h2 id='f5'>5. Quarterly balance and the 2024 year-end build</h2>")
    b.append(f"<p>WIP equals throughput times days in WIP within 10% in {llq_in} of {len(llq)} quarters. The misses are {miss}, the quarter of the 2024 "
             f"year-end build and the quarters after a build in which it shipped.</p>")
    b.append(f"<p>The fourth quarter of 2024 released {pct(brake_up, 0)} more brake standard hours than the third, with the Thanksgiving and Christmas "
             f"short weeks inside the peak. The lasers ran at {join_and([d2(x) for x in lw['laser_utilization']])} of scheduled hours in the three weeks "
             f"from November 11, with {n0(lw['wip_at_laser'].min())} to {n0(lw['wip_at_laser'].max())} jobs waiting; in those weeks the lasers, not the "
             f"brakes, limited output. WIP peaked at {n0(peaks[2024]['peak'])} jobs on {peaks[2024]['date'].strftime('%B %d').replace(' 0', ' ')} "
             f"against a third-quarter mean of {n0(peaks[2024]['q3'])}. "
             + (f"The brakes ran a Saturday shift in each of the {len(sat_run)} weeks from {pd.Timestamp(sat_run['week_start'].min()).strftime('%B %d').replace(' 0', ' ')} "
                f"through March. " if sat_all else f"The brakes ran a Saturday shift in {len(sat_run)} of {len(sat)} weeks from December through March. ")
             + f"The first quarter of {YEAR} shipped {pct(q1['on_time_delivery'])} on time with a {d1(q1['lead_time_median'])}-day median and holds "
             f"{n0(q1['late_jobs'])} of the year's {n0(ya['late_jobs'])} late jobs.</p>")
    b.append(f"<p>The 2023 build peaked at {d1(peaks[2023]['ratio'])} times the third-quarter mean and the following quarter shipped "
             f"{pct(q1_2024['on_time_delivery'])} on time. The 2025 build stood at {d1(peaks[2025]['ratio'])} times the third-quarter mean on "
             f"{peaks[2025]['date'].strftime('%B %d').replace(' 0', ' ')}, the last working day of the period.</p>")
    b.append(fig_build())
    b.append("<div class='caption'>Figure 5. Weekly WIP, releases and shipments, October 2024 to March 2025; shaded weeks have fewer than five working days.</div>")

    b.append("<h2 id='rec'>Recommendation</h2>")
    b.append(f"<p>Restate the fixed quote as a percentile of the measured lead-time distribution by routing class (P7): the 10-day repeat quote is met on "
             f"{hit['repeat part'][1]} of jobs in an ordinary quarter. Plan the fourth-quarter peak with planned Saturday brake shifts from November through February and the setup program, sized on the shop model (P5); "
             f"the 2024 build put {n0(q1['late_jobs'])} jobs late in the first quarter of {YEAR}. Take ordinary-quarter lateness to P2, where material, vendor and "
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
    b.append("<h3>Table 1. Lead time against the quoted lead time by routing class</h3>" + t1())
    b.append(f"<h3>Table 2a. Lead time by stage, {YEAR}: mean working days per job, stages in routing order</h3>" + stage_table(SY, TY))
    b.append(f"<h3>Table 2b. Lead time by stage, {YEAR} {REST}: mean working days per job, stages in routing order</h3>" + stage_table(SR, TR))
    b.append("<h3>Table 3. Queue time by work center</h3>" + t3())
    b.append("<h3>Table 5. Floor WIP against the WIP the quoted lead times imply</h3>" + t5())
    b.append("<h3>Table 5a. On-time delivery and lead time by quarter shipped</h3>" + t5a())
    b.append("<h3>Table 6. WIP, throughput and days in WIP by calendar quarter</h3>" + t6())
    b.append("<h3>Table 7. Year-end WIP build by year</h3>" + t7())
    b.append("<div class='glossary'>WIP: jobs released and not shipped. Quoted lead time: 10 working days for repeat parts, 15 for new parts, "
             "20 with outside processing. On time: shipped on or before the promised date as last revised.</div>")
    toc = [("f1", "Lead time against the quote"), ("f2", "Where the days go"), ("f3", "Queue by work center"), ("f4", "WIP"), ("f5", "Year-end build"),
           ("rec", "Recommendation"), ("method", "Method and data"), ("appendix", "Appendix")]
    html = report_shell("Lead time decomposition", "Project 1 report", HEADER_META, "\n".join(b), toc)
    (DOCS / "reports").mkdir(parents=True, exist_ok=True)
    (DOCS / "reports" / "p1_lead_time.html").write_text(html, encoding="utf8")


# ── A3 ──────────────────────────────────────────────────────────────────────
COUNTERMEASURES = [
    ("Attribute each late job to a cause and replace the late-reason code with a buffer status record (P2)", "Production control manager", "February 2026"),
    ("Plan the fourth-quarter peak on the shop model: planned Saturday brake shifts and the setup program (P5); a WIP cap and due-date dispatch lower on-time "
     "delivery (P5)", "Plant manager", "April 2026"),
    ("Restate quoted lead times as a percentile of measured lead time by routing class and brake load (P7)", "Estimating and customer service manager", "May 2026"),
]


def a3():
    ya, ra = Y.loc["all"], R.loc["all"]
    lw = laser_weeks
    left = []
    left.append(f"<section><h2>Background and problem</h2><p>The fixed quote of 10, 15 or 20 working days is met on {pct(ya['share_within_quoted'], 0)} of jobs "
                f"({pct(ra['share_within_quoted'], 0)} in {REST}); {pct(ya['on_time_delivery'])} ship by the promised date ({pct(ra['on_time_delivery'])} in {REST}) "
                f"against the {pct(required, 0)} key accounts require.<br>The 90th-percentile lead time is {d1(ya['lead_time_p90'])} days ({d1(ra['lead_time_p90'])} in "
                f"{REST}) against a median of {d1(ya['lead_time_median'])} ({d1(ra['lead_time_median'])}).</p></section>")
    left.append(f"<section><h2>Current condition</h2>{fig_stages('p1_a3_stage_decomposition', 1, 4.3)}"
                f"<div class='caption'>Mean working days per job at each stage, on-time against late jobs, {YEAR} and {REST}.</div></section>")
    left.append(f"<section><h2>Target</h2><p>{pct(required, 0)} of jobs shipped by the promised date in every quarter, the first quarter included.</p></section>")
    right = []
    right.append(
        f"<section><h2>Analysis</h2>{fig_build('p1_a3_year_end_build', 1, 2.7)}"
        f"<div class='caption'>Weekly WIP, releases and shipments, October 2024 to March 2025; shaded weeks have fewer than five working days.</div><ul>"
        f"<li>For the year the brake queue separates late from on-time jobs ({d2(st(SY, 'queue: press brake', 'late'))} against "
        f"{d2(st(SY, 'queue: press brake', 'on time'))} days). In {REST} it does not ({d2(st(SR, 'queue: press brake', 'late'))} against "
        f"{d2(st(SR, 'queue: press brake', 'on time'))}); late jobs there differ in material wait at the first operation, outside processing, "
        f"the robotic weld queue and setup and run.</li>"
        f"<li>The brakes hold {pct(qy.loc['press_brake', 'share_of_queue'], 0)} of queue time for the year and {pct(qr.loc['press_brake', 'share_of_queue'], 0)} in "
        f"{REST}; the 90th-percentile brake queue is {d1(qy.loc['press_brake', 'p90_queue_days'])} days and {d1(qr.loc['press_brake', 'p90_queue_days'])}.</li>"
        f"<li>Floor WIP is {n0(wy['wip_mean'])} jobs against {n0(wy['wip_at_quoted_lead_times'])} at the quoted lead times for the year and "
        f"{n0(wr['wip_mean'])} against {n0(wr['wip_at_quoted_lead_times'])} in {REST}: the gap between quote and delivery is dispersion, not level.</li>"
        f"<li>The 2024 year-end build: {pct(brake_up, 0)} more brake standard hours released than in the third quarter, the lasers at "
        f"{join_and([d2(x) for x in lw['laser_utilization']])} for three weeks from November 11, WIP at {n0(peaks[2024]['peak'])} on "
        f"{peaks[2024]['date'].strftime('%B %d').replace(' 0', ' ')}, and a first quarter of {YEAR} at {pct(q1['on_time_delivery'])} on time with "
        f"{n0(q1['late_jobs'])} of the year's {n0(ya['late_jobs'])} late jobs.</li></ul></section>")
    cm = table(pd.DataFrame(COUNTERMEASURES, columns=["Action", "Owner", "When"]))
    right.append(f"<section><h2>Countermeasures</h2>{cm}</section>")
    right.append(f"<section><h2>Results</h2><p>Measured baseline for {YEAR}: on-time delivery {pct(ya['on_time_delivery'])} ({pct(ra['on_time_delivery'])} in {REST}); "
                 f"quote met on {pct(ya['share_within_quoted'], 0)} ({pct(ra['share_within_quoted'], 0)}); 90th-percentile lead time {d1(ya['lead_time_p90'])} days "
                 f"({d1(ra['lead_time_p90'])}). Results of the countermeasures are reported in P2, P5 and P7.</p></section>")
    right.append("<section><h2>Follow-up</h2><p>Weekly: WIP by location, brake queue per operation, and material wait at the first operation. "
                 "P6 evaluates these as leading measures of on-time delivery.</p></section>")
    html = a3_shell("Lead time decomposition", "Project 1 A3", HEADER_META, "\n".join(left), "\n".join(right))
    (DOCS / "a3").mkdir(parents=True, exist_ok=True)
    (DOCS / "a3" / "p1_lead_time.html").write_text(html, encoding="utf8")


def main():
    report()
    a3()
    print("wrote docs/reports/p1_lead_time.html and docs/a3/p1_lead_time.html")


if __name__ == "__main__":
    main()
