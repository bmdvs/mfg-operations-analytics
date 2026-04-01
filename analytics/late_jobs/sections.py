"""Late jobs: the sections, tables and figures of its half of the report, read from the marts.

Built by analytics.reports.lead_time_and_late_jobs.
"""
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

from analytics.db import q
from analytics.style.style import ACCENT, AMBER, BRAND_BLUE, GREEN, GREY, LIGHT_BLUE, fig, paired_columns, pct, save_conformed as save, sig, table

YEAR = 2025
REST = "Q2 to Q4"
RT = "Q2-Q4"                                  # the same quarters as written in the figures
CODES = ["capacity", "material", "outside processing", "customer change", "quality", "other"]
CAUSES = ["released late", "constraint queue", "material", "outside processing", "setup overrun", "quality", "other hold", "not attributable"]
CAUSE_LABEL = {"released late": "Released late", "constraint queue": "Queue constraint", "material": "Material", "outside processing": "Outside processing",
               "setup overrun": "Setup overrun", "quality": "Quality", "other hold": "Hold", "not attributable": "Not attributed"}
CAUSE_COLOR = {"released late": AMBER, "constraint queue": BRAND_BLUE, "material": ACCENT, "outside processing": LIGHT_BLUE, "setup overrun": "#8E6BA8",
               "quality": GREEN, "other hold": "#B9A36B", "not attributable": GREY}
CODED_CAUSES = ["constraint queue", "setup overrun", "material", "outside processing", "quality"]
WC = {"press_brake": "Press brake", "grind_deburr": "Grind and deburr", "inspection_pack": "Inspection and pack", "hardware": "Hardware", "weld": "Weld",
      "robotic_weld": "Robotic weld", "assembly": "Assembly", "powder_coat": "Powder coat", "laser": "Laser", "punch": "Punch",
      "outside_processing": "Outside processing", "shipping": "Shipping", "order entry": "Order entry (promise)", "none": "No stage above normal"}
WC_SHORT = {"press_brake": "Press\nbrake", "grind_deburr": "Grind and\ndeburr", "inspection_pack": "Inspection\nand pack", "robotic_weld": "Robotic\nweld",
            "powder_coat": "Powder\ncoat", "outside_processing": "Outside\nprocessing"}
STAGE = {"queue: press brake": "Queue: press brake", "setup and run": "Setup and run", "move": "Move", "complete to ship": "Complete to ship",
         "queue: assembly": "Queue: assembly", "first-operation queue": "First-operation queue", "queue: grind deburr": "Queue: grind and deburr",
         "material wait at first operation": "Material wait at first operation", "queue: robotic weld": "Queue: robotic weld",
         "release to traveler print": "Release to traveler print", "queue: weld": "Queue: weld", "queue: hardware": "Queue: hardware",
         "outside processing": "Outside processing", "hold: other": "Hold: other", "queue: inspection pack": "Queue: inspection and pack",
         "queue: powder coat": "Queue: powder coat", "no stage above normal": "No stage above normal"}


def d1(x):
    return f"{x:.1f}"


def n0(x):
    return f"{x:,.0f}"


# ── data ────────────────────────────────────────────────────────────────────
batch = q("select export_batch_id from marts.mart_late_jobs limit 1").iloc[0, 0]
L_all = q("select * from marts.mart_late_jobs")
A_all = q("select * from marts.mart_late_job_attribution")
sens = q("select * from marts.mart_attribution_threshold_sensitivity")
ship = q(f"select customer_id, quarter(ship_date) as ship_quarter, count(*) as jobs, sum((not on_time)::int) as late from marts.mart_job_lead_time "
         f"where year(ship_date) = {YEAR} group by 1, 2")
LY = L_all[L_all["ship_year"] == YEAR]
LR = LY[LY["ship_quarter"] >= 2]
AY = A_all[A_all["ship_year"] == YEAR]
AR = AY[AY["ship_quarter"] >= 2]
PER = {"year": (LY, AY), REST: (LR, AR)}


def code_stats(L):
    ent = L.dropna(subset=["late_reason_code"])
    return dict(n=len(L), blank=L["late_reason_code"].isna().mean(), entered=len(ent),
                share={k: (ent["late_reason_code"] == k).mean() for k in CODES})


def cause_stats(L, A):
    tot = A["attributed_days"].sum()
    days = A.groupby("cause")["attributed_days"].sum().reindex(CAUSES).fillna(0.0)
    return dict(total=tot, days=days, share=days / tot, jobs=A.groupby("cause")["job_id"].nunique().reindex(CAUSES).fillna(0).astype(int),
                dominant=L["dominant_cause"].value_counts().reindex(CAUSES).fillna(0).astype(int))


def agreement(L, coded_only=False):
    d = L.dropna(subset=["late_reason_code"])
    if coded_only:
        d = d[d["dominant_cause"].isin(CODED_CAUSES)]
    pc, pa = d["late_reason_code"].value_counts(normalize=True), d["dominant_cause_code"].value_counts(normalize=True)
    return dict(n=len(d), agree=(d["late_reason_code"] == d["dominant_cause_code"]).mean(), chance=sum(pc.get(k, 0) * pa.get(k, 0) for k in CODES))


CS = {k: code_stats(v[0]) for k, v in PER.items()}
CA = {k: cause_stats(*v) for k, v in PER.items()}
AG = {k: agreement(v[0]) for k, v in PER.items()}
AGC = {k: agreement(v[0], True) for k, v in PER.items()}
by_year = L_all.groupby("ship_year").agg(late=("job_id", "size"), blank=("late_reason_code", lambda x: x.isna().mean()),
                                         capacity=("late_reason_code", lambda x: (x.dropna() == "capacity").mean()))
cross = pd.crosstab(LY.dropna(subset=["late_reason_code"])["late_reason_code"], LY.dropna(subset=["late_reason_code"])["dominant_cause"])
cross = cross.reindex(index=CODES, columns=CAUSES).fillna(0).astype(int)
cross_all = pd.crosstab(LY["late_reason_code"].fillna("blank"), LY["dominant_cause"]).reindex(index=["blank"] + CODES, columns=CAUSES).fillna(0).astype(int)
mat_jobs = set(AY.loc[AY["cause"] == "material", "job_id"])
mat_coded = int((LY[LY["job_id"].isin(mat_jobs)]["late_reason_code"] == "material").sum())


def wc_table(A):
    w = A.pivot_table(index="work_center", columns="cause", values="attributed_days", aggfunc="sum", fill_value=0.0).reindex(columns=CAUSES).fillna(0.0)
    w["lost"] = w.sum(axis=1)
    w["share"] = w["lost"] / w["lost"].sum()
    return w.sort_values("lost", ascending=False)


WY, WR = wc_table(AY), wc_table(AR)


def customers(L, A, first_quarter):
    s = ship[ship["ship_quarter"] >= first_quarter].groupby("customer_id")[["jobs", "late"]].sum()
    g = A.groupby("customer_id")["attributed_days"].sum().rename("lost").to_frame().join(s)
    g["share"] = g["lost"] / g["lost"].sum()
    g["on_time"] = 1 - g["late"] / g["jobs"]
    top = A.groupby(["customer_id", "cause"])["attributed_days"].sum().reset_index().sort_values("attributed_days", ascending=False).drop_duplicates("customer_id")
    g = g.join(top.set_index("customer_id")["cause"].rename("largest")).join(L.drop_duplicates("customer_id").set_index("customer_id")[["customer_name", "key_account"]])
    g = g.sort_values("lost", ascending=False).head(10)
    g["cum"] = g["share"].cumsum()
    return g


CY, CR = customers(LY, AY, 1), customers(LR, AR, 2)


def na_stages(A):
    na = A[A["cause"] == "not attributable"].groupby("stage")["attributed_days"].sum().sort_values(ascending=False)
    return na, na / na.sum()


NAY, NAYs = na_stages(AY)
NAR, NARs = na_stages(AR)
no_cause = {k: (int((~v[0]["has_assigned_cause"]).sum()), len(v[0])) for k, v in PER.items()}


def sv(period, pctl, cause):
    r = sens[(sens["period"] == period) & (sens["queue_percentile"] == pctl) & (sens["cause"] == cause)]
    return float(r["share_of_lost_days"].iloc[0]), float(r["lost_days"].iloc[0])


# ── figures ─────────────────────────────────────────────────────────────────
def bottom_legend(f, handles, labels, ncol, space):
    f.legend(handles, labels, frameon=False, fontsize=9, ncol=ncol, loc="lower center")
    f.tight_layout(rect=(0, space, 1, 1))


def fig_causes():
    f, ax = fig(h=3.7)
    paired_columns(ax, [CAUSE_LABEL[k] for k in CAUSES], list(CA["year"]["share"] * 100), list(CA[REST]["share"] * 100), (f"{YEAR}", RT), percent=True)
    ax.set_ylabel("Share of lost days")
    bottom_legend(f, *ax.get_legend_handles_labels(), ncol=2, space=0.06)
    return save(f, "late_jobs_lost_days_by_cause", "Lost days by attributed cause")


def fig_work_center():
    """Lost days at each work center by cause: one stacked column for the year and one for the ordinary quarters."""
    centers = [w for w in WY.index if w not in ("order entry", "none")]
    causes = [k for k in CAUSES if k != "released late"]
    f, ax = fig(h=4.5)
    x = np.arange(len(centers))
    ticks, names = [], []
    for dx, W, name in ((-0.2, WY, f"{YEAR}"), (0.2, WR, RT)):
        bottom = np.zeros(len(centers))
        for k in causes:
            v = sig(W[k].reindex(centers).fillna(0.0).values)
            ax.bar(x + dx, v, width=0.36, bottom=bottom, color=CAUSE_COLOR[k])
            bottom += v
        ticks += list(x + dx)
        names += [name] * len(centers)
    for xi in x[:-1]:
        ax.axvline(xi + 0.5, color="#D5D5D5", linewidth=0.9)
    ax.set_xticks(ticks)
    ax.set_xticklabels(names, rotation=90, fontsize=7.5)
    ax.tick_params(axis="x", length=0)
    for xi, w in zip(x, centers):
        ax.annotate(WC_SHORT.get(w, WC.get(w, w)), (xi, 0), xycoords=("data", "axes fraction"), xytext=(0, -36), textcoords="offset points",
                    ha="center", va="top", fontsize=8)
    ax.set_xlim(-0.5, len(centers) - 0.5)
    ax.set_ylabel("Lost days")
    bottom_legend(f, [Patch(color=CAUSE_COLOR[k]) for k in causes], [CAUSE_LABEL[k] for k in causes], ncol=4, space=0.1)
    return save(f, "late_jobs_lost_days_by_work_center", "Lost days by work center and cause")


def fig_codes():
    keys = CODES + ["blank"]
    share = lambda L: [float((L["late_reason_code"].fillna("blank") == k).mean()) * 100 for k in keys]
    f, ax = fig(h=3.7)
    paired_columns(ax, [k.capitalize() for k in keys], share(LY), share(LR), (f"{YEAR}", RT), percent=True)
    ax.set_ylabel("Share of late jobs")
    bottom_legend(f, *ax.get_legend_handles_labels(), ncol=2, space=0.06)
    return save(f, "late_jobs_codes_entered", "Late-reason codes as entered on late jobs")


def fig_mosaic():
    """One column per entered code, as wide as its share of the year's late jobs, stacked by the largest attributed cause of its jobs."""
    width = cross_all.sum(axis=1) / cross_all.values.sum()
    gap = 0.008
    f, ax = fig(h=4.6)
    ax.grid(False)
    left, centers = 0.0, []
    for code in cross_all.index:
        share = cross_all.loc[code] / cross_all.loc[code].sum()
        bottom = 0.0
        for k in CAUSES:
            v = float(sig(share[k] * 100))
            if v == 0:
                continue
            ax.bar(left, v, width=width[code], bottom=bottom, align="edge", color=CAUSE_COLOR[k], edgecolor="white", linewidth=0.5)
            if width[code] >= 0.06 and v >= 6:
                ax.text(left + width[code] / 2, bottom + v / 2, f"{v:.0f}%", ha="center", va="center", fontsize=8,
                        color="white" if k in ("constraint queue", "material", "setup overrun", "quality") else "#222222")
            bottom += v
        centers.append(left + width[code] / 2)
        left += width[code] + gap
    ax.set_xlim(0, left - gap)
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.set_ylabel("Share of the code's late jobs")
    ax.set_xticks(centers)
    ax.set_xticklabels([f"{k.capitalize()}, {pct(width[k], 0)}" for k in cross_all.index], rotation=40, ha="right", fontsize=9)
    labels = [CAUSE_LABEL[k] if k != "not attributable" else "Not attributed by rule" for k in CAUSES]
    bottom_legend(f, [Patch(color=CAUSE_COLOR[k]) for k in CAUSES], labels, ncol=4, space=0.1)
    return save(f, "late_jobs_code_against_cause", "What the shop coded against what the data shows")


# ── tables ──────────────────────────────────────────────────────────────────
def t_codes():
    rows = []
    for y, r in by_year.iterrows():
        rows.append([str(y), n0(r["late"]), pct(r["blank"]), pct(r["capacity"])])
    rows.append([f"{YEAR} {REST}", n0(CS[REST]["n"]), pct(CS[REST]["blank"]), pct(CS[REST]["share"]["capacity"])])
    return table(pd.DataFrame(rows, columns=["Period shipped", "Late jobs", "Blank", "Capacity share of entered codes"]))


def t_causes():
    rows = []
    for k in CAUSES:
        y, r = CA["year"], CA[REST]
        rows.append([CAUSE_LABEL[k], n0(y["days"][k]), pct(y["share"][k]), n0(y["jobs"][k]), n0(y["dominant"][k]),
                     n0(r["days"][k]), pct(r["share"][k]), n0(r["jobs"][k]), n0(r["dominant"][k])])
    rows.append(["Total", n0(CA["year"]["total"]), "100.0%", n0(len(LY)), n0(len(LY)), n0(CA[REST]["total"]), "100.0%", n0(len(LR)), n0(len(LR))])
    return table(pd.DataFrame(rows, columns=["Cause", f"Lost days, {YEAR}", "Share", "Late jobs with the cause", "Jobs where largest",
                                             f"Lost days, {REST}", f"Share, {REST}", f"Late jobs with the cause, {REST}", f"Jobs where largest, {REST}"]))


def t_agree():
    rows = []
    for name, src in (("All coded late jobs", AG), ("Jobs whose largest cause has a code", AGC)):
        for per, label in (("year", f"{YEAR}"), (REST, f"{YEAR} {REST}")):
            a = src[per]
            rows.append([name, label, n0(a["n"]), pct(a["agree"]), pct(a["chance"]), f"{(a['agree'] - a['chance']) * 100:+.1f} points"])
    return table(pd.DataFrame(rows, columns=["Comparison", "Period", "Late jobs", "Code agrees with largest attributed cause", "Chance level", "Over chance"]))


def t_wc(w):
    rows = [[WC.get(k, k), n0(r["lost"]), pct(r["share"])] + [n0(r[c]) for c in CAUSES] for k, r in w.iterrows()]
    return table(pd.DataFrame(rows, columns=["Work center", "Lost days", "Share"] + [CAUSE_LABEL[c] for c in CAUSES]))


def t_cust(g):
    rows = [[r["customer_name"], "yes" if r["key_account"] else "no", n0(r["jobs"]), n0(r["late"]), pct(r["on_time"]), n0(r["lost"]), pct(r["share"]), pct(r["cum"]),
             CAUSE_LABEL[r["largest"]]] for _, r in g.iterrows()]
    return table(pd.DataFrame(rows, columns=["Customer", "Key account", "Jobs shipped", "Late jobs", "On time", "Lost days", "Share of lost days",
                                             "Cumulative share", "Largest cause"]))


def t_na():
    idx = list(NAY.index)
    rows = [[STAGE.get(k, k), n0(NAY[k]), pct(NAYs[k]), n0(NAR.get(k, 0.0)), pct(NARs.get(k, 0.0))] for k in idx]
    rows.append(["Total", n0(NAY.sum()), "100.0%", n0(NAR.sum()), "100.0%"])
    return table(pd.DataFrame(rows, columns=["Stage", f"Days not attributed, {YEAR}", "Share", f"Days not attributed, {REST}", f"Share, {REST}"]))


def t_sens():
    rows = []
    for p in (70, 80, 90):
        rows.append([f"{p}th percentile" + (" (the rule)" if p == 80 else ""), pct(sv("year", p, "constraint queue")[0]), pct(sv("year", p, "not attributable")[0]),
                     pct(sv(REST, p, "constraint queue")[0]), pct(sv(REST, p, "not attributable")[0])])
    return table(pd.DataFrame(rows, columns=["Queue threshold of the constraint rule", f"Queue constraint, {YEAR}", f"Not attributed, {YEAR}",
                                             f"Queue constraint, {REST}", f"Not attributed, {REST}"]))


def t_cross():
    d = cross_all.copy()
    d.columns = [CAUSE_LABEL[c] for c in d.columns]
    d.insert(0, "Code entered", [k.capitalize() for k in d.index])
    return table(d.reset_index(drop=True))


# ── report ──────────────────────────────────────────────────────────────────
HEADER_META = (f"Custom sheet-metal fabrication job shop, about 120 employees, one plant. Late jobs shipped in {YEAR}, whole year and {REST}; "
               f"records from January 2023 to December 2025.<br>"
               f"Sources: ERP, shop-floor data collection, quality, maintenance and attendance exports (batch {batch}). "
               f"Lost days in working days, scheduled Saturdays counted.")


def see(*tables):
    """One sentence pointing to appendix tables; the report links each."""
    t = [str(x) for x in tables]
    return f"See Appendix Table{'s' if len(t) > 1 else ''} {t[0] if len(t) == 1 else ', '.join(t[:-1]) + ' and ' + t[-1]} for additional detail."


def chart(title, img):
    return f"<div class='chart-title'>{title}</div>{img}"


def report():
    y, r = CA["year"], CA[REST]
    ys, rs = y["share"], r["share"]
    b = []
    b.append("<h2 id='f1'>1. Drivers behind late jobs</h2>")
    b.append(f"<p>In {YEAR}, the shop had {n0(len(LY))} late jobs that shipped a total of {n0(y['total'])} days late (average of {d1(y['total'] / len(LY))} days late "
             f"for each job), with {n0(len(LR))} of these late jobs ({pct(len(LR) / len(LY), 0)}) in {REST} which shipped a total of {n0(r['total'])} days late "
             f"(average of {d1(r['total'] / len(LR))} days late for each).</p>")
    b.append("<p>We analyzed the ERP and shop-floor records to arrive at an attribution of lost days (i.e., how many days late the jobs shipped) by driver. "
             "For each late job, we counted the days above the on-time median at each stage as lost, and assigned to a driver by the rules in "
             "<a href='#method'>Method and data</a>.</p>")
    b.append(f"<p>In {YEAR}, jobs waiting at work centers (i.e., queue constraints) accounted for {pct(ys['constraint queue'], 0)} of the {n0(y['total'])} lost days, "
             f"while jobs that were released late accounted for {pct(ys['released late'], 0)}, and jobs that waited on material and outside processing accounted for "
             f"{pct(ys['material'], 0)} and {pct(ys['outside processing'], 0)}, respectively. In {REST}, jobs that were released late accounted for "
             f"{pct(rs['released late'], 0)} of the {n0(r['total'])} lost days, with queue constraint ({pct(rs['constraint queue'], 0)}), material "
             f"({pct(rs['material'], 0)}) and outside processing ({pct(rs['outside processing'], 0)}) the other main drivers. {see(1, 5, 6)}</p>")
    queues = [k for k in NAYs.index if k.startswith("queue:") or k == "first-operation queue"]
    b.append(f"<p>{pct(ys['not attributable'], 0)} of lost days in {YEAR} and {pct(rs['not attributable'], 0)} in {REST} have no attribution. Of the "
             f"{n0(NAY.sum())} non-attributed lost days in {YEAR}, {pct(NAYs[queues].sum(), 0)} was from work center queue time above on-time median but below "
             f"the attribution threshold, {pct(NAYs['setup and run'], 0)} from setup and run time above normal with no overrun or rework recorded, and "
             f"{pct(NAYs['move'], 0)} from movement between stages. The remainder have no discernible cause. {see(9, 10)}</p>")
    b.append(chart("Lost days by attributed cause", fig_causes()))
    b.append(chart("Lost days by work center and cause", fig_work_center()))

    b.append("<h2 id='f2'>2. The shop's records</h2>")
    b.append(f"<p>Late-reason codes are inputted retroactively on late jobs by the customer service team during the weekly delivery review. These codes are pulled "
             f"from a dropdown list with six choices: capacity, material, outside processing, customer change, quality and other. As seen below, a significant "
             f"portion of late jobs had no late-reason code entered. {see(2)}</p>")
    b.append(chart("Late-reason codes as entered on late jobs", fig_codes()))
    late = cross.loc[:, "released late"]
    b.append(f"<p>To validate the accuracy of these codes, we compared them against the lost days attribution calculations under "
             f"<a href='#f3_1'>Drivers behind late jobs</a>. We first mapped the late-reason codes to the corresponding attribution drivers: queue constraint and setup "
             f"overrun count as capacity; material, outside processing and quality as their own codes; a hold and days not attributed as other. The notable "
             f"exception is that the \"released late\" attribution driver is not a listed option for late-reason codes; those jobs are mostly coded as capacity "
             f"or other ({n0(late['capacity'] + late['other'])} of the {n0(late.sum())} with a code), and count as other in the comparison.</p>")
    cq = cross_all["constraint queue"] / cross_all.sum(axis=1)
    rel = cross_all["released late"]
    b.append(f"<p>The entered code agrees with the largest attributed cause on {pct(AG['year']['agree'])} of coded late jobs against {pct(AG['year']['chance'])} "
             f"expected by chance ({pct(AG[REST]['agree'])} against {pct(AG[REST]['chance'])} in {REST}). Queue constraint is the largest attributed cause on "
             f"{pct(cq['capacity'], 0)} of the jobs coded capacity, and on {pct(cq['blank'], 0)} of the jobs with no code and {pct(cq['material'], 0)} of those coded "
             f"material. Material is the largest cause on {n0(cross_all.loc['material', 'material'])} of the {n0(cross_all.loc['material'].sum())} jobs coded "
             f"material, outside processing on {n0(cross_all.loc['outside processing', 'outside processing'])} of the "
             f"{n0(cross_all.loc['outside processing'].sum())} coded outside processing and quality on {n0(cross_all.loc['quality', 'quality'])} of the "
             f"{n0(cross_all.loc['quality'].sum())} coded quality. Of the {n0(rel.sum())} jobs where released late is the largest cause, {n0(rel['capacity'])} are "
             f"coded capacity, {n0(rel['blank'])} carry no code and {n0(rel['other'])} are coded other. {see(3, 4)} From this analysis, we conclude that the "
             f"late-reason codes carry almost no relevant information. In the <a href='#rec'>Recommendation</a> section, we lay out our proposed solution for the "
             f"shop going forward.</p>")
    b.append(chart("What the shop coded against what the data shows", fig_mosaic()))

    b.append("<h2 id='rec'>Recommendation and control</h2>")
    b.append("<p>Replace the late-reason code on the shipment with a buffer status record kept by production control: each job's time buffer in thirds, and a reason "
             "captured when the job turns red, from this list: promise inside the standard lead time; queue at a named work center; material short at the first cut; "
             "outside processing late; quality; hold by reason; not attributed. Review the record weekly in place of the late-reason Pareto.</p>")
    b.append("<p>Require the rush flag and a named approver on every promise inside the standard lead time ([[R:quoting]] sizes the quote). Extend the kit check to stock sheet "
             "items ([[R:quoting]] measures kit completeness).</p>")

    b.append("<h2 id='method'>Method and data</h2>")
    b.append(f"<p>Coverage: {n0(len(LY))} late jobs and {n0(y['total'])} lost days in {YEAR}; {n0(len(LR))} and {n0(r['total'])} in {REST}. A job's lost days are its "
             f"working days late. Lost days at a stage are the stage days above the median of on-time jobs of the same routing class shipped in the same quarter; "
             f"the powder scheduling wait is not lost time.<br>"
             f"Rules. Released late: the standard lead time of 10, 15 or 20 working days less the promised lead time, capped at days late, allocated first. Queue constraint: an operation with queue above "
             f"its work center's 80th percentile for the quarter, or first-operation queue above its 80th percentile. Material: material wait at the first operation "
             f"with a kit shortage or material hold recorded; a material hold at a later operation; or first-operation queue where the sheet issue came after planned "
             f"start and followed a stock receipt of the same item, with the first work center's queue that week below its median. Outside processing: a line received "
             f"after its promised date. Setup overrun: setup above standard by more than 2 hours and by more than twice standard. Quality: a recorded quality hold, "
             f"or setup and run above normal on a job with a rework operation. Hold: a recorded engineering, customer or tooling hold. Not attributed: the rest.<br>"
             f"The days late remaining after released late are split across the stages' lost days in proportion; days at stages with no matching rule are not attributed.<br>"
             f"Agreement compares the entered code with the cause holding the most lost days on the job: queue constraint and setup overrun count as capacity; material, "
             f"outside processing and quality as their own codes; released late, hold and days not attributed as other. The chance level is the agreement expected if codes "
             f"were assigned at the shop's code frequencies independently of the cause.</p>")

    b.append("<h2 id='appendix'>Appendix</h2>")
    b.append(f"<h3>Table 1. Lost days of late jobs by attributed cause, {YEAR} and {REST}</h3>" + t_causes())
    b.append("<h3>Table 2. Late-reason codes by period shipped</h3>" + t_codes())
    b.append("<h3>Table 3. Agreement of the entered code with the largest attributed cause</h3>" + t_agree())
    b.append(f"<h3>Table 4. Entered code against largest attributed cause, {YEAR}</h3>" + t_cross())
    b.append(f"<h3>Table 5. Lost days by work center and cause, {YEAR}</h3>" + t_wc(WY))
    b.append(f"<h3>Table 6. Lost days by work center and cause, {YEAR} {REST}</h3>" + t_wc(WR))
    b.append(f"<h3>Table 7. Lost days by customer, top ten, {YEAR}</h3>" + t_cust(CY))
    b.append(f"<h3>Table 8. Lost days by customer, top ten, {YEAR} {REST}</h3>" + t_cust(CR))
    b.append("<h3>Table 9. Stage composition of the lost days not attributed</h3>" + t_na())
    b.append("<h3>Table 10. Queue constraint and not attributed shares by queue threshold</h3>" + t_sens())
    b.append("<div class='glossary'>Lost days: working days a job shipped after its promised date. Released late: promised inside the standard lead time of 10, 15 or "
             "20 working days. Not attributed: lost days that match no rule.</div>")
    toc = [("f1", "Drivers behind late jobs"), ("f2", "The shop's records"), ("rec", "Recommendation"), ("method", "Method and data"), ("appendix", "Appendix")]
    return {"body": "\n".join(b), "toc": toc[:-3], "meta": HEADER_META}


# ── target, countermeasures and follow-up ──────────────────────────────────
COUNTERMEASURES = [
    ("Replace the late-reason code with a buffer status record: time buffer in thirds, reason captured when a job turns red, weekly review", "Production control manager",
     "March 2026"),
    ("Require the rush flag and a named approver on every promise inside the standard lead time ([[R:quoting]] sizes the quote)", "Customer service manager", "February 2026"),
    ("Extend the kit check to stock sheet items ([[R:quoting]] measures kit completeness)", "Purchasing manager", "March 2026"),
]


def control():
    """The target, the countermeasures and the follow-up, for the Recommendation section."""
    target = ("A reason recorded on every late job at the moment it turns red.")
    return target, COUNTERMEASURES, None


