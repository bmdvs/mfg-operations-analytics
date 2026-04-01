"""P2 why jobs are late: report and figures, read from the marts.

Usage: python -m analytics.p2_late_jobs.build
"""
import numpy as np
import pandas as pd

from analytics.db import q
from analytics.style.style import ACCENT, AMBER, BRAND_BLUE, DOCS, GREEN, GREY, LIGHT_BLUE, RED, fig, pct, save, report_shell, table
from analytics.style.style import recommendation_block

YEAR = 2025
REST = "Q2 to Q4"
CODES = ["capacity", "material", "outside processing", "customer change", "quality", "other"]
CAUSES = ["released late", "constraint queue", "material", "outside processing", "setup overrun", "quality", "other hold", "not attributable"]
CAUSE_LABEL = {"released late": "Released late", "constraint queue": "Constraint queue", "material": "Material", "outside processing": "Outside processing",
               "setup overrun": "Setup overrun", "quality": "Quality", "other hold": "Other hold", "not attributable": "Unexplained"}
CAUSE_COLOR = {"released late": AMBER, "constraint queue": BRAND_BLUE, "material": ACCENT, "outside processing": LIGHT_BLUE, "setup overrun": "#8E6BA8",
               "quality": GREEN, "other hold": "#B9A36B", "not attributable": GREY}
CODED_CAUSES = ["constraint queue", "setup overrun", "material", "outside processing", "quality"]
WC = {"press_brake": "Press brake", "grind_deburr": "Grind and deburr", "inspection_pack": "Inspection and pack", "hardware": "Hardware", "weld": "Weld",
      "robotic_weld": "Robotic weld", "assembly": "Assembly", "powder_coat": "Powder coat", "laser": "Laser", "punch": "Punch",
      "outside_processing": "Outside processing", "shipping": "Shipping", "order entry": "Order entry (promise)", "none": "No stage above normal"}
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
batch = q("select export_batch_id from marts.mart_p2_late_jobs limit 1").iloc[0, 0]
L_all = q("select * from marts.mart_p2_late_jobs")
A_all = q("select * from marts.mart_p2_attribution")
sens = q("select * from marts.mart_p2_threshold_sensitivity")
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
def fig_pareto(name="p2_paired_pareto", h=5.4):
    f, axes = fig(h=h, ncols=2, nrows=2, grid="x")
    for row, (per, label) in enumerate((("year", f"{YEAR}"), (REST, f"{YEAR} {REST}"))):
        cs, ca = CS[per], CA[per]
        L = PER[per][0]
        codes = pd.Series({"blank": cs["blank"], **{k: (L["late_reason_code"] == k).mean() for k in CODES}}).sort_values()
        ax = axes[row, 0]
        ax.barh([k.capitalize() for k in codes.index], codes.values * 100, color=[GREY if k == "blank" else ACCENT for k in codes.index])
        ax.set_title(f"Late-reason code as entered, {label}", fontsize=10.5)
        ax.set_xlabel("Share of late jobs (%)")
        sh = ca["share"].sort_values()
        ax = axes[row, 1]
        ax.barh([CAUSE_LABEL[k] for k in sh.index], sh.values * 100, color=[CAUSE_COLOR[k] for k in sh.index])
        ax.set_title(f"Attributed lost days, {label}", fontsize=10.5)
        ax.set_xlabel("Share of lost days (%)")
    f.tight_layout()
    return save(f, name, "Late-reason codes as entered against attributed lost days")


def fig_work_center():
    w = WR.iloc[::-1]
    f, ax = fig(h=3.8, grid="x")
    left = np.zeros(len(w))
    for k in CAUSES:
        ax.barh([WC.get(x, x) for x in w.index], w[k].values, left=left, color=CAUSE_COLOR[k], label=CAUSE_LABEL[k])
        left += w[k].values
    ax.set_xlabel("Lost days")
    ax.legend(frameon=False, fontsize=8.5, ncol=2, loc="lower right")
    f.tight_layout()
    return save(f, "p2_lost_days_by_work_center", "Lost days by work center and cause")


def fig_cross():
    f, ax = fig(h=3.4, grid="x")
    ax.grid(False)
    m = cross.values
    ax.imshow(m, cmap="Blues", aspect="auto", vmin=0, vmax=m.max() * 1.15)
    ax.set_xticks(range(len(CAUSES)))
    ax.set_xticklabels([CAUSE_LABEL[k] for k in CAUSES], rotation=25, ha="right")
    ax.set_yticks(range(len(CODES)))
    ax.set_yticklabels([k.capitalize() for k in CODES])
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            ax.text(j, i, str(m[i, j]), ha="center", va="center", fontsize=9.5, color="white" if m[i, j] > m.max() * 0.55 else "#222222")
    ax.set_xlabel("Largest attributed cause")
    ax.set_ylabel("Code entered")
    for s in ("left", "bottom"):
        ax.spines[s].set_visible(False)
    f.tight_layout()
    return save(f, "p2_code_against_cause", "Entered code against largest attributed cause")


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
    return table(pd.DataFrame(rows, columns=["Stage", f"Unexplained days, {YEAR}", "Share", f"Unexplained days, {REST}", f"Share, {REST}"]))


def t_sens():
    rows = []
    for p in (70, 80, 90):
        rows.append([f"{p}th percentile" + (" (the rule)" if p == 80 else ""), pct(sv("year", p, "constraint queue")[0]), pct(sv("year", p, "not attributable")[0]),
                     pct(sv(REST, p, "constraint queue")[0]), pct(sv(REST, p, "not attributable")[0])])
    return table(pd.DataFrame(rows, columns=["Queue threshold of the constraint rule", f"Constraint queue, {YEAR}", f"Unexplained, {YEAR}",
                                             f"Constraint queue, {REST}", f"Unexplained, {REST}"]))


def t_cross():
    d = cross.copy()
    d.columns = [CAUSE_LABEL[c] for c in d.columns]
    d.insert(0, "Code entered", [k.capitalize() for k in d.index])
    return table(d.reset_index(drop=True))


# ── report ──────────────────────────────────────────────────────────────────
HEADER_META = (f"Custom sheet-metal fabrication job shop, about 120 employees, one plant. Late jobs shipped in {YEAR}, whole year and {REST}; "
               f"records from January 2023 to December 2025.<br>"
               f"Sources: ERP, shop-floor data collection, quality, maintenance and attendance exports (batch {batch}). "
               f"Lost days in working days, scheduled Saturdays counted.")


def report():
    y, r = CA["year"], CA[REST]
    ys, rs = y["share"], r["share"]
    first_year = int(by_year.index.min())
    rel_dom_top10 = int((CR["largest"] == "released late").sum())
    two_y, two_r = CY["share"].iloc[:2].sum(), CR["share"].iloc[:2].sum()
    b = []
    b.append("<h2 id='f1'>1. The shop's record</h2>")
    b.append(f"<p>{pct(CS['year']['blank'], 0)} of late jobs carry no reason code. \"Capacity\" is {pct(CS['year']['share']['capacity'], 0)} of entered codes for the year "
             f"and {pct(CS[REST]['share']['capacity'], 0)} in {REST}, up from {pct(by_year.loc[first_year, 'capacity'])} in {first_year}. The entered code agrees with "
             f"the largest attributed cause on {pct(AG['year']['agree'])} of coded late jobs against {pct(AG['year']['chance'])} expected by chance "
             f"({pct(AG[REST]['agree'])} against {pct(AG[REST]['chance'])} in {REST}): the codes carry almost no information beyond their own frequencies. "
             f"On the {n0(AGC['year']['n'])} coded jobs whose largest cause has a code of its own, agreement is {pct(AGC['year']['agree'])} against "
             f"{pct(AGC['year']['chance'])} by chance.</p>")
    b.append(fig_pareto())
    b.append(f"<div class='caption'>Figure 1. Late-reason codes as entered and lost days by attributed cause, {YEAR} and {REST}.</div>")

    b.append("<h2 id='f2'>2. Lost days by cause</h2>")
    b.append(f"<p>For the year, constraint queue is {pct(ys['constraint queue'], 0)} of the {n0(y['total'])} lost days, unexplained {pct(ys['not attributable'], 0)}, "
             f"released late {pct(ys['released late'], 0)}, material {pct(ys['material'])} and outside processing {pct(ys['outside processing'], 0)}; "
             f"the year is the 2024 year-end build shipping in the first quarter.</p>")
    b.append(f"<p>In {REST}, released late is {pct(rs['released late'], 0)} of the {n0(r['total'])} lost days and the largest cause on "
             f"{n0(r['dominant']['released late'])} of {n0(len(LR))} late jobs; constraint queue is {pct(rs['constraint queue'], 0)}, unexplained "
             f"{pct(rs['not attributable'], 0)}, material {pct(rs['material'], 0)} and outside processing {pct(rs['outside processing'], 0)}. "
             f"In an ordinary quarter, close to half the days lost are on jobs promised inside the standard lead time before any work started.</p>")
    b.append(t_causes())
    b.append(f"<div class='caption'>Table 1. Lost days of late jobs by attributed cause, {YEAR} and {REST}.</div>")

    b.append("<h2 id='f3'>3. Where the days are lost</h2>")
    b.append(f"<p>In {REST}, order entry holds {pct(WR.loc['order entry', 'share'], 0)} of lost days (promises inside the standard lead time), the laser "
             f"{pct(WR.loc['laser', 'share'], 0)} ({n0(WR.loc['laser', 'material'])} of its {n0(WR.loc['laser', 'lost'])} days are material waits at the first cut), "
             f"robotic weld {pct(WR.loc['robotic_weld', 'share'])} and the brakes {pct(WR.loc['press_brake', 'share'], 0)}. For the year the brakes hold "
             f"{pct(WY.loc['press_brake', 'share'], 0)}, the laser {pct(WY.loc['laser', 'share'], 0)} (the first-operation queue of November and December 2024) "
             f"and order entry {pct(WY.loc['order entry', 'share'], 0)}.</p>")
    b.append(fig_work_center())
    b.append(f"<div class='caption'>Figure 2. Lost days by work center and attributed cause, {REST}.</div>")

    b.append("<h2 id='f4'>4. Whose jobs</h2>")
    b.append(f"<p>The top ten customers hold {pct(CY['cum'].iloc[-1], 0)} of lost days for the year and "
             f"{'all are' if CY['key_account'].all() else str(int(CY['key_account'].sum())) + ' are'} key accounts. In {REST} released late is the largest cause for "
             f"{rel_dom_top10} of the ten. {CY['customer_name'].iloc[0]} and {CY['customer_name'].iloc[1]} hold {pct(two_y, 0)} of lost days for the year and "
             f"{pct(two_r, 0)} in {REST}.</p>")

    b.append("<h2 id='f5'>5. Where the codes and the data disagree</h2>")
    b.append(f"<p>{n0(cross.loc['capacity', 'released late'])} jobs coded \"capacity\" were released late and {n0(cross.loc['capacity', 'not attributable'])} coded "
             f"\"capacity\" have no attributable cause as their largest. Of the {n0(cross.loc['other'].sum())} jobs coded \"other\", "
             f"{n0(cross.loc['other', 'released late'])} were released late; of the {n0(cross.loc['capacity'].sum())} coded \"capacity\", "
             f"{n0(cross.loc['capacity', 'constraint queue'])} had constraint queue as their largest cause. Material was coded on {mat_coded} of the {len(mat_jobs)} late jobs with a material wait, and on "
             f"{n0(cross.loc['material', 'material'])} of the {n0(y['dominant']['material'])} where material is the largest cause.</p>")
    b.append(fig_cross())
    b.append(f"<div class='caption'>Figure 3. Late jobs of {YEAR} with a code entered, by code and largest attributed cause.</div>")

    b.append("<h2 id='f6'>6. The unexplained share</h2>")
    top3 = list(NAYs.index[:3])
    assert top3 == ["queue: press brake", "setup and run", "move"], top3
    b.append(f"<p>{pct(ys['not attributable'], 0)} of lost days for the year and {pct(rs['not attributable'], 0)} in {REST} match no rule. Of the {n0(NAY.sum())} "
             f"unexplained days for the year, {pct(NAYs[top3[0]], 0)} are brake queue above the on-time normal but below the threshold of the constraint rule, "
             f"{pct(NAYs[top3[1]], 0)} are setup and run above normal with no overrun or rework recorded, and {pct(NAYs[top3[2]], 0)} are move. "
             f"With the queue threshold at the 70th percentile the unexplained share is {pct(sv('year', 70, 'not attributable')[0], 0)}; at the 90th, "
             f"{pct(sv('year', 90, 'not attributable')[0], 0)}. {no_cause['year'][0]} of {n0(no_cause['year'][1])} late jobs "
             f"({pct(no_cause['year'][0] / no_cause['year'][1])}) have no cause assigned at all; {no_cause[REST][0]} of {n0(no_cause[REST][1])} in {REST}.</p>")

    b.append("<h2 id='rec'>Recommendation and control</h2>")
    b.append("<p>Replace the late-reason code on the shipment with a buffer status record kept by production control: each job's time buffer in thirds, and a reason "
             "captured when the job turns red, from this list: promise inside the standard lead time; queue at a named work center; material short at the first cut; "
             "outside processing late; quality; hold by reason; unexplained. Review the record weekly in place of the late-reason Pareto.</p>")
    b.append("<p>Require the rush flag and a named approver on every promise inside the standard lead time (P7 sizes the quote). Extend the kit check to stock sheet "
             "items (P6 measures kit completeness).</p>")

    b.append(control())

    b.append("<h2 id='method'>Method and data</h2>")
    b.append(f"<p>Coverage: {n0(len(LY))} late jobs and {n0(y['total'])} lost days in {YEAR}; {n0(len(LR))} and {n0(r['total'])} in {REST}. A job's lost days are its "
             f"working days late. Lost days at a stage are the stage days above the median of on-time jobs of the same routing class shipped in the same quarter; "
             f"the powder scheduling wait is not lost time.<br>"
             f"Rules. Released late: the standard lead time of 10, 15 or 20 working days less the promised lead time, capped at days late, allocated first. Constraint queue: an operation with queue above "
             f"its work center's 80th percentile for the quarter, or first-operation queue above its 80th percentile. Material: material wait at the first operation "
             f"with a kit shortage or material hold recorded; a material hold at a later operation; or first-operation queue where the sheet issue came after planned "
             f"start and followed a stock receipt of the same item, with the first work center's queue that week below its median. Outside processing: a line received "
             f"after its promised date. Setup overrun: setup above standard by more than 2 hours and by more than twice standard. Quality: a recorded quality hold, "
             f"or setup and run above normal on a job with a rework operation. Other hold: a recorded engineering, customer or tooling hold. Not attributable: the rest.<br>"
             f"The days late remaining after released late are split across the stages' lost days in proportion; days at stages with no matching rule are unexplained.<br>"
             f"Agreement compares the entered code with the cause holding the most lost days on the job: constraint queue and setup overrun count as capacity; material, "
             f"outside processing and quality as their own codes; released late, other hold and unexplained as other. The chance level is the agreement expected if codes "
             f"were assigned at the shop's code frequencies independently of the cause.</p>")

    b.append("<h2 id='appendix'>Appendix</h2>")
    b.append("<h3>Table 2. Late-reason codes by period shipped</h3>" + t_codes())
    b.append("<h3>Table 3. Agreement of the entered code with the largest attributed cause</h3>" + t_agree())
    b.append(f"<h3>Table 4. Entered code against largest attributed cause, {YEAR}</h3>" + t_cross())
    b.append(f"<h3>Table 5. Lost days by work center and cause, {YEAR}</h3>" + t_wc(WY))
    b.append(f"<h3>Table 6. Lost days by work center and cause, {YEAR} {REST}</h3>" + t_wc(WR))
    b.append(f"<h3>Table 7. Lost days by customer, top ten, {YEAR}</h3>" + t_cust(CY))
    b.append(f"<h3>Table 8. Lost days by customer, top ten, {YEAR} {REST}</h3>" + t_cust(CR))
    b.append("<h3>Table 9. Stage composition of the unexplained lost days</h3>" + t_na())
    b.append("<h3>Table 10. Constraint queue and unexplained shares by queue threshold</h3>" + t_sens())
    b.append("<div class='glossary'>Lost days: working days a job shipped after its promised date. Released late: promised inside the standard lead time of 10, 15 or "
             "20 working days. Unexplained: lost days that match no rule.</div>")
    toc = [("f1", "The shop's record"), ("f2", "Lost days by cause"), ("f3", "By work center"), ("f4", "By customer"), ("f5", "Codes against data"),
           ("f6", "Unexplained share"), ("rec", "Recommendation"), ("method", "Method and data"), ("appendix", "Appendix")]
    (DOCS / "reports").mkdir(parents=True, exist_ok=True)
    (DOCS / "reports" / "p2_late_jobs.html").write_text(report_shell("Why jobs are late", "Project 2 report", HEADER_META, "\n".join(b), toc), encoding="utf8")


# ── target, countermeasures and follow-up ──────────────────────────────────
COUNTERMEASURES = [
    ("Replace the late-reason code with a buffer status record: time buffer in thirds, reason captured when a job turns red, weekly review", "Production control manager",
     "March 2026"),
    ("Require the rush flag and a named approver on every promise inside the standard lead time (P7 sizes the quote)", "Customer service manager", "February 2026"),
    ("Extend the kit check to stock sheet items (P6 measures kit completeness)", "Purchasing manager", "March 2026"),
]


def control():
    """The target, the countermeasures and the follow-up, for the Recommendation section."""
    target = ("A reason recorded on every late job at the moment it turns red.")
    return recommendation_block(target, COUNTERMEASURES)


def main():
    report()
    print("wrote docs/reports/p2_late_jobs.html")


if __name__ == "__main__":
    main()
