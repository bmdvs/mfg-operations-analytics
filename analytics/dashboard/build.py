"""Operations dashboard: one static page from the marts, weekly grain, a 13-week view and the trend for each panel.

Usage: python -m analytics.dashboard.build
"""
import numpy as np
import pandas as pd

from analytics.db import q
from analytics.constraint import analysis as CONSTRAINT
from analytics.leading_indicators import analysis as INDICATORS
from analytics.style.style import ACCENT, AMBER, BRAND_BLUE, CSS, DOCS, GREEN, GREY, LIGHT_BLUE, RED, fig, pct, table
from analytics.style import style

TARGET = 0.95
VIEW = 13
SHIPPED_SHARE = 0.95
WC = {"laser": "Laser", "punch": "Punch", "press_brake": "Press brake", "hardware": "Hardware", "weld": "Weld", "robotic_weld": "Robotic weld",
      "grind_deburr": "Grind and deburr", "powder_coat": "Powder coat", "assembly": "Assembly", "inspection_pack": "Inspection and pack",
      "outside_processing": "Outside processing", "complete, not shipped": "Complete, not shipped"}
CAUSES = [("constraint_queue", "Constraint queue"), ("released_late", "Released late"), ("material", "Material"), ("outside_processing", "Outside processing"),
          ("setup_overrun", "Setup overrun"), ("quality", "Quality hold or rework"), ("other_hold", "Other hold"), ("not_attributable", "Not attributable")]
PALETTE = [BRAND_BLUE, AMBER, GREEN, ACCENT, RED, LIGHT_BLUE, "#7A5C99", GREY, "#B8A04A", "#4F8F8B", "#C97B63", "#555555"]

# ── data ────────────────────────────────────────────────────────────────────
D6 = INDICATORS.load()
I = D6["w"]                                                    # weekly indicators, from the first week kept
W = q("select * from marts.mart_dashboard_weekly order by week_start")
W["week_start"] = pd.to_datetime(W["week_start"])
W = W.set_index("week_start").loc[I.index.min():]
QW = q("select * from marts.mart_dashboard_quotes_weekly order by week_start")
QW["week_start"] = pd.to_datetime(QW["week_start"])
QW = QW.set_index("week_start").loc[I.index.min():]
U = q("select * from marts.mart_utilization_weekly where work_center = 'press_brake' order by week_start")
U["week_start"] = pd.to_datetime(U["week_start"])
U = U.set_index("week_start").loc[I.index.min():]
MW = q("select * from marts.mart_machine_weekly where work_center = 'press_brake' order by week_start, machine_id")
MW["week_start"] = pd.to_datetime(MW["week_start"])
WIP = q("""select cast(date_trunc('week', calendar_date) as date) as week_start, location, avg(jobs) as jobs
           from (select calendar_date, location, sum(jobs) as jobs from marts.mart_wip_daily group by 1, 2) group by 1, 2""")
WIP["week_start"] = pd.to_datetime(WIP["week_start"])
WIP = WIP.pivot(index="week_start", columns="location", values="jobs").fillna(0.0).loc[I.index.min():]
OT = q("select * from marts.mart_overtime_hours where work_center = 'press_brake'")
OT["week_start"] = pd.to_datetime(OT["week_start"])
OT["rush_flag"] = OT["rush_flag"].fillna(False).astype(bool)
batch = W["export_batch_id"].iloc[0]

CW = W.index[W["weekdays"] == 5].max()                         # the current week: the last five-day week
PARTIAL = [t for t in W.index if t > CW]
V = list(W.index[(W.index <= CW)][-VIEW:])
VP = V + PARTIAL
DEC = INDICATORS.declines(D6)


def wk(ts):
    return f"{ts:%B} {ts.day}, {ts.year}"


def short(ts):
    return f"{ts:%b} {ts.day}"


def n0(x):
    return f"{x:,.0f}"


def d1(x):
    return f"{x:.1f}"


def tiles(items):
    return "<div class='kpis'>" + "".join(f"<div class='kpi'><div class='v'>{v_}</div><div class='l'>{l}</div></div>" for v_, l in items) + "</div>"


def save(f, name, alt):
    out = DOCS / "figures"
    out.mkdir(parents=True, exist_ok=True)
    f.savefig(out / f"{name}.png", format="png", bbox_inches="tight", dpi=style.CHART_DPI)
    style.plt.close(f)
    return f'<img alt="{alt}" src="../figures/{name}.png">'


def wrap(t):
    return f"<div style='overflow-x:auto'>{t}</div>"


def cap(text):
    note = "" if not PARTIAL else f" The week of {wk(PARTIAL[0])} has {int(W.loc[PARTIAL[0], 'weekdays'])} working days and is drawn lighter."
    return f"<div class='caption'>{text}{note}</div>"


def definition(text):
    DEFINITIONS.append(text)
    return f"<div class='glossary' style='margin-top:6px'>{text}</div>"


DEFINITIONS = []


def line13(ax, s, color, label=None, marker="o", scale=1.0):
    """A weekly series over the 13-week view, the partial week after it drawn lighter."""
    ax.plot(range(len(V)), s.reindex(V).to_numpy() * scale, color=color, marker=marker, markersize=3.5, linewidth=1.6, label=label)
    if PARTIAL:
        x = [len(V) - 1] + [len(V) + k for k in range(len(PARTIAL))]
        y = s.reindex([V[-1]] + PARTIAL).to_numpy() * scale
        ax.plot(x, y, color=color, marker=marker, markersize=3.5, linewidth=1.2, linestyle=":", alpha=0.45, markerfacecolor="white")


def axis13(ax):
    ax.set_xticks(range(len(VP)))
    ax.set_xticklabels([short(t) for t in VP], fontsize=7.5, rotation=45, ha="right")
    ax.axvline(len(V) - 1, color=GREY, linewidth=0.8, linestyle=":")


def mark_declines(ax):
    for t in DEC["onset"]:
        if t in W.index:
            ax.axvline(t, color=RED, linewidth=1.0, linestyle="--")


# ── 1 on-time delivery and lead time ────────────────────────────────────────
def panel_delivery():
    c = W.loc[CW]
    f, axes = fig(h=3.0, ncols=2)
    line13(axes[0], W["on_time_delivery"], BRAND_BLUE, scale=100)
    axes[0].axhline(TARGET * 100, color=RED, linewidth=1, linestyle="--")
    axes[0].set_ylabel("On-time delivery (%)")
    line13(axes[1], W["lead_time_median"], BRAND_BLUE, "Median")
    line13(axes[1], W["lead_time_p90"], AMBER, "90th percentile")
    axes[1].set_ylabel("Lead time (working days)")
    axes[1].legend(frameon=False, fontsize=8)
    for ax in axes:
        axis13(ax)
    f.tight_layout()
    a = save(f, "dashboard_delivery_13_weeks", "On-time delivery and lead time by ship week, 13 weeks")
    f, axes = fig(h=4.2, nrows=2, sharex=True)
    axes[0].plot(W.index, W["on_time_delivery"] * 100, color=BRAND_BLUE, linewidth=1.2)
    axes[0].axhline(TARGET * 100, color=RED, linewidth=1, linestyle="--")
    axes[0].set_ylabel("On-time delivery (%)", fontsize=9)
    axes[1].plot(W.index, W["lead_time_median"], color=BRAND_BLUE, linewidth=1.2, label="Median")
    axes[1].plot(W.index, W["lead_time_p90"], color=AMBER, linewidth=1.2, label="90th percentile")
    axes[1].set_ylabel("Lead time (working days)", fontsize=9)
    axes[1].legend(frameon=False, fontsize=8)
    for ax in axes:
        mark_declines(ax)
    f.tight_layout()
    b = save(f, "dashboard_delivery_trend", "On-time delivery and lead time by ship week, trend")
    return ("<h2 id='panel1'>1. On-time delivery and lead time</h2>" +
            tiles([(pct(c["on_time_delivery"]), "On-time delivery"), (n0(c["jobs_shipped"]), "Jobs shipped"), (d1(c["lead_time_median"]), "Median lead time (days)"),
                   (d1(c["lead_time_p90"]), "90th-percentile lead time (days)")]) +
            a + cap(f"On-time delivery with the {pct(TARGET, 0)} target line, and median and 90th-percentile lead time, by ship week.") +
            b + f"<div class='caption'>The same series from {wk(W.index.min())}, with the start of each of the {len(DEC)} declines in on-time delivery marked.</div>" +
            definition("On-time delivery: jobs shipped on or before the promised date, by ship week. Lead time runs from the release date at 10:00 to the ship date at "
                       "15:00, in working days; a scheduled Saturday counts as one. A decline starts in the first week the on-time delivery of the trailing 4 weeks is "
                       "more than 5 points below that of the 13 weeks before them, at least 8 weeks after the last."))


# ── 2 leading set ───────────────────────────────────────────────────────────
def trigger(col, sign):
    """Per week: the 4-week mean, the mean and standard deviation of the 13 weeks before that window, the trigger level, and whether the mean is beyond it."""
    s = I[col]
    m4 = s.rolling(INDICATORS.WINDOW).mean()
    b = s.shift(INDICATORS.WINDOW).rolling(INDICATORS.BASE)
    mean, sd = b.mean(), b.std(ddof=1)
    return pd.DataFrame(dict(value=s, m4=m4, mean=mean, sd=sd, level=mean + sign * sd, beyond=sign * (m4 - mean) > sd))


LEAD = [("on_time_start_rate", "On-time start rate", -1, 100, "{:.1f}%"), ("wip_at_laser", "Jobs waiting at the lasers", 1, 1, "{:.0f}")]


def panel_leading():
    T = {c: trigger(c, s) for c, _, s, _, _ in LEAD}
    items = []
    for c, name, sign, scale, f_ in LEAD:
        r = T[c].loc[CW]
        items.append((f_.format(r["value"] * scale), f"{name}, week"))
        items.append((f_.format(r["m4"] * scale), f"{name}, 4-week mean; trigger {'below' if sign < 0 else 'above'} {f_.format(r['level'] * scale)}: "
                                                  f"<b>{'beyond the trigger' if r['beyond'] else 'inside'}</b>"))
    c = W.loc[CW]
    items += [(n0(c["released_above_3_days_backlog"]), f"Jobs released above 3 days of brake backlog, of {n0(c['jobs_released'])} released"),
              (n0(c["promised_inside_standard"]), f"Lines promised inside the standard lead time, of {n0(c['jobs_released'])} released"),
              (n0(c["short_kits"]), f"Short kits, of {n0(c['kit_checks'])} kit checks")]

    def draw(axes, idx, pos, full=None):
        """The weekly value, the 4-week mean and the band of the prior 13 weeks; weeks after `full` positions are drawn lighter."""
        for ax, (col, name, sign, scale, _) in zip(axes, LEAD):
            t = T[col].reindex(idx)
            x = np.array(pos) if pos is not None else idx
            n = full or len(t)
            ax.fill_between(x[:n], ((t["mean"] - t["sd"]) * scale)[:n], ((t["mean"] + t["sd"]) * scale)[:n], color=LIGHT_BLUE, alpha=0.45, linewidth=0,
                            label="Prior 13 weeks, one standard deviation")
            ax.plot(x[:n], (t["value"] * scale)[:n], color=GREY, linewidth=1.0, label="Week")
            ax.plot(x[:n], (t["m4"] * scale)[:n], color=BRAND_BLUE, linewidth=1.8, label="4-week mean")
            if n < len(t):
                ax.fill_between(x[n - 1:], ((t["mean"] - t["sd"]) * scale)[n - 1:], ((t["mean"] + t["sd"]) * scale)[n - 1:], color=LIGHT_BLUE, alpha=0.2, linewidth=0)
                ax.plot(x[n - 1:], (t["value"] * scale)[n - 1:], color=GREY, linewidth=1.0, linestyle=":", alpha=0.6)
                ax.plot(x[n - 1:], (t["m4"] * scale)[n - 1:], color=BRAND_BLUE, linewidth=1.4, linestyle=":", alpha=0.5)
            for k_, (xi, bz) in enumerate(zip(x, t["beyond"])):
                if bz:
                    half = 0.5 if pos is not None else pd.Timedelta(days=3.5)
                    ax.axvspan(xi - half, xi + half, color=AMBER, alpha=0.3 if k_ < n else 0.12, linewidth=0)
            ax.set_ylabel(name + (" (%)" if scale == 100 else ""), fontsize=9)
    f, axes = fig(h=3.0, ncols=2)
    draw(axes, VP, list(range(len(VP))), len(V))
    for ax in axes:
        axis13(ax)
    hs, ls = axes[0].get_legend_handles_labels()
    f.legend(hs, ls, frameon=False, fontsize=8, loc="lower center", ncols=3)
    f.tight_layout(rect=(0, 0.07, 1, 1))
    a = save(f, "dashboard_leading_13_weeks", "The on-time start rate and jobs waiting at the lasers with their trigger bands, 13 weeks")
    f, axes = fig(h=4.2, nrows=2, sharex=True)
    draw(axes, I.index, None)
    for ax in axes:
        mark_declines(ax)
    f.tight_layout()
    b = save(f, "dashboard_leading_trend", "The on-time start rate and jobs waiting at the lasers with their trigger bands, trend")
    f, ax = fig(h=2.6)
    ax.plot(W.index, W["released_above_3_days_backlog"], color=RED, linewidth=1.1, label="Released above 3 days of brake backlog")
    ax.plot(W.index, W["promised_inside_standard"], color=BRAND_BLUE, linewidth=1.1, label="Promised inside the standard lead time")
    ax.plot(W.index, W["short_kits"], color=AMBER, linewidth=1.1, label="Short kits")
    ax.set_ylabel("Jobs in the week", fontsize=9)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    f.tight_layout()
    c3 = save(f, "dashboard_flags_trend", "The three job-level flags as weekly counts")
    thr, sp = INDICATORS.backlog_threshold(D6).set_index("period"), INDICATORS.short_promises(D6).set_index("period")
    j = D6["j"][D6["j"]["on_time"].notna() & D6["j"]["kit_result"].notna()]
    rows = []
    for per in ("2023 to 2025", f"{INDICATORS.YEAR} Q2 to Q4"):
        jj = dict(INDICATORS.periods(j))[per]
        rows += [[per, "Released above 3 days of brake backlog", pct(thr.loc[per, "share_of_all_jobs_above"]), pct(thr.loc[per, "late_rate_above"]),
                  pct(thr.loc[per, "late_rate_below"])],
                 [per, "Promised inside the standard lead time", pct(sp.loc[per, "share_of_jobs"]), pct(sp.loc[per, "late_rate_inside"]), pct(sp.loc[per, "late_rate_other"])],
                 [per, "Short kit at the kit check", pct((jj["kit_result"] == "short").mean()), pct(jj.loc[jj["kit_result"] == "short", "late"].mean()),
                  pct(jj.loc[jj["kit_result"] != "short", "late"].mean())]]
    t = wrap(table(pd.DataFrame(rows, columns=["Jobs released in", "Flag", "Share of jobs flagged", "Late rate, flagged", "Late rate, not flagged"])))
    return ("<h2 id='panel2'>2. Leading set</h2>" + tiles(items) + a +
            cap("The on-time start rate and jobs waiting at the lasers by week, with the 4-week mean, the band of the prior 13 weeks and the weeks beyond the trigger "
                "shaded.") + b + f"<div class='caption'>The same from {wk(I.index.min())}, with the declines in on-time delivery marked.</div>" + c3 +
            "<div class='caption'>Jobs released above 3 days of brake backlog, lines promised inside the standard lead time, and short kits, by week.</div>" + t +
            "<div class='caption'>Late rate of flagged and unflagged jobs; short kits among jobs with a kit check, late rate of short kits computed for this page.</div>" +
            definition("On-time start rate: in-house operations planned to start in the week that had started by the planned date; operations planned before the "
                       "job's release are left out. Jobs waiting at the lasers: mean daily jobs at the lasers in the week. Trigger: the 4-week mean adverse to the 13 "
                       "weeks before by more than one standard deviation of those weeks. Brake backlog at release: the standard hours of brake operations waiting at "
                       "10:00 on the release date, at the brakes' actual-over-standard ratio, in days of crewed brake capacity. Promised inside the standard: a promise "
                       "shorter than the standard 10, 15 or 20 days, rush included. Short kit: kit check result short (job-specific material only)."))


# ── 3 WIP and queue ─────────────────────────────────────────────────────────
def panel_wip():
    total = WIP.sum(axis=1)
    order = list(WIP.loc[V].mean().sort_values(ascending=False).index)
    f, axes = fig(h=3.4, ncols=2, gridspec_kw=dict(width_ratios=[1.5, 1]))
    ax = axes[0]
    bottom = np.zeros(len(VP))
    for k, loc in enumerate(order):
        y = WIP[loc].reindex(VP).to_numpy()
        bars = ax.bar(range(len(VP)), y, bottom=bottom, color=PALETTE[k % len(PALETTE)], label=WC.get(loc, loc), width=0.8)
        for b_ in bars[len(V):]:
            b_.set_alpha(0.4)
            b_.set_hatch("//")
        bottom += y
    axis13(ax)
    ax.set_ylabel("Jobs, weekly mean")
    ax.legend(frameon=False, fontsize=6.8, ncols=3, loc="upper left")
    ax.set_ylim(0, bottom.max() * 1.45)
    ops = q(f"""select work_center, avg(queue_net_wd) as queue_days from marts.mart_operations
                where not is_first_op and week_start between '{V[0]:%Y-%m-%d}' and '{V[-1]:%Y-%m-%d}' group by 1 order by 2""")
    ax = axes[1]
    ax.barh([WC.get(x, x) for x in ops["work_center"]], ops["queue_days"], color=ACCENT)
    for yi, v_ in enumerate(ops["queue_days"]):
        ax.annotate(f"{v_:.2f}", (v_, yi), textcoords="offset points", xytext=(3, -3), fontsize=7.5)
    ax.set_xlabel("Mean queue (working days), 13 weeks", fontsize=9)
    ax.tick_params(axis="y", labelsize=8)
    ax.grid(axis="y", visible=False)
    f.tight_layout()
    a = save(f, "dashboard_wip_13_weeks", "WIP by work center by week and queue days by work center, 13 weeks")
    f, axes = fig(h=4.2, nrows=2, sharex=True)
    axes[0].plot(total.index, total, color=BRAND_BLUE, linewidth=1.3, label="Jobs released and not shipped")
    axes[0].plot(WIP.index, WIP["press_brake"], color=RED, linewidth=1.1, label="At the brakes")
    axes[0].plot(WIP.index, WIP["laser"], color=AMBER, linewidth=1.1, label="At the lasers")
    axes[0].set_ylabel("Jobs, weekly mean", fontsize=9)
    axes[0].legend(frameon=False, fontsize=8, loc="upper left")
    axes[1].plot(I.index, I["brake_backlog_days_at_release"], color=BRAND_BLUE, linewidth=1.2)
    axes[1].axhline(INDICATORS.BACKLOG_THRESHOLD, color=RED, linewidth=1, linestyle="--")
    axes[1].set_ylabel("Brake backlog at release (days)", fontsize=9)
    f.tight_layout()
    b = save(f, "dashboard_wip_trend", "WIP and brake backlog at release, trend")
    return ("<h2 id='panel3'>3. WIP and queue by work center</h2>" +
            tiles([(n0(total[CW]), "Jobs released and not shipped"), (n0(WIP.loc[CW, "press_brake"]), "Jobs at the brakes"), (n0(WIP.loc[CW, "laser"]), "Jobs at the lasers"),
                   (d1(I.loc[CW, "brake_backlog_days_at_release"]), "Brake backlog at release (days)")]) +
            a + cap("WIP by work center, weekly mean, and mean queue by work center for operations started in the 13 weeks.") +
            b + f"<div class='caption'>Jobs released and not shipped, jobs at the brakes and at the lasers, and brake backlog at release with the 3-day threshold, from "
                f"{wk(W.index.min())}.</div>" +
            definition("WIP is jobs released and not shipped, sampled every working day; a job is at the work center of the operation it is waiting for or running. "
                       "Queue is the previous operation's end to this operation's first start, operations after the first, less the powder color-day wait, in working "
                       "days. Brake backlog at release is the mean over the jobs released in the week."))


# ── 4 late jobs by cause ────────────────────────────────────────────────────
def panel_causes():
    c = W.loc[CW]
    cols = [f"lost_days_{k}" for k, _ in CAUSES]
    s = W.loc[V, cols].sum().sort_values()
    names = dict((f"lost_days_{k}", n) for k, n in CAUSES)
    f, ax = fig(h=2.9, w=6.6)
    ax.barh([names[x] for x in s.index], s.to_numpy(), color=BRAND_BLUE)
    for yi, v_ in enumerate(s.to_numpy()):
        ax.annotate(f"{v_:.0f} ({v_ / s.sum():.0%})", (v_, yi), textcoords="offset points", xytext=(3, -3), fontsize=8)
    ax.set_xlabel(f"Lost days, {VIEW} weeks", fontsize=9)
    ax.set_xlim(0, s.max() * 1.22)
    ax.grid(axis="y", visible=False)
    f.tight_layout()
    a = save(f, "dashboard_causes_13_weeks", "Lost days by attributed cause, 13 weeks")
    g = W.groupby(W.index.to_period("Q"))
    qs = g[cols].sum()
    share = qs.div(qs.sum(axis=1), axis=0) * 100
    nocode = g["late_jobs_without_reason_code"].sum() / g["late_jobs"].sum() * 100
    f, axes = fig(h=4.4, nrows=2, sharex=True, gridspec_kw=dict(height_ratios=[2, 1]))
    x = np.arange(len(share))
    bottom = np.zeros(len(share))
    for k, (key, name) in enumerate(CAUSES):
        axes[0].bar(x, share[f"lost_days_{key}"], bottom=bottom, color=PALETTE[k], label=name, width=0.8)
        bottom += share[f"lost_days_{key}"].to_numpy()
    axes[0].set_ylabel("Share of lost days (%)", fontsize=9)
    axes[0].legend(frameon=False, fontsize=7.5, ncols=4, loc="upper center", bbox_to_anchor=(0.5, 1.28))
    axes[1].bar(x, nocode, color=ACCENT, width=0.8)
    axes[1].set_ylabel("Late jobs with no\nreason code (%)", fontsize=9)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels([f"{p_.year} Q{p_.quarter}" for p_ in share.index], fontsize=8, rotation=45, ha="right")
    f.tight_layout()
    b = save(f, "dashboard_causes_trend", "Cause shares of lost days and late jobs with no reason code, by quarter")
    v13 = W.loc[V]
    return ("<h2 id='panel4'>4. Late jobs by attributed cause</h2>" +
            tiles([(n0(c["late_jobs"]), "Late jobs shipped"), (n0(c["lost_days"]), "Lost days"),
                   (f"{n0(c['late_jobs_without_reason_code'])} of {n0(c['late_jobs'])}", "Late jobs with no reason code"),
                   (pct(v13["late_jobs_without_reason_code"].sum() / v13["late_jobs"].sum()), f"No reason code, {VIEW} weeks ({n0(v13['late_jobs'].sum())} late jobs)")]) +
            a + f"<div class='caption'>Lost days by attributed cause for jobs shipped in the {VIEW} weeks to the week of {wk(CW)}.</div>" +
            b + "<div class='caption'>Cause shares of lost days and the share of late jobs with no reason code, by quarter shipped.</div>" +
            definition("A job's lost days are its working days late. Lost days at a stage are the stage days above the median of on-time jobs of the same routing class "
                       "shipped in the same quarter. Released late is allocated first, capped at days late; the days late remaining are split across the stages' lost "
                       "days in proportion; days at stages with no matching rule are not attributable. The reason code is the late-reason code entered on the "
                       "shipment."))


# ── 5 brake utilization and the queue curve ─────────────────────────────────
def panel_brakes():
    fits, _ = CONSTRAINT.curves(CONSTRAINT.load(), 13)
    fb = fits[fits["work_center"] == "press_brake"].iloc[0]
    k, m = float(fb["k"]), int(fb["machines"])
    c = U.loc[CW]
    f, axes = fig(h=3.2, ncols=2)
    ax = axes[0]
    u = np.linspace(0.55, 0.985, 200)
    ax.plot(u, style.sig(k * CONSTRAINT.vut_factor(u, m)), color=GREY, linewidth=1.5, label="Curve fitted on 2023 to 2025")
    ax.scatter(style.sig(U.loc[V, "utilization"]), style.sig(U.loc[V, "queue_mean"]), color=BRAND_BLUE, s=22, zorder=3, label=f"{VIEW} weeks")
    ax.scatter(style.sig([c["utilization"]]), style.sig([c["queue_mean"]]), color=RED, s=46, zorder=4, label="Current week")
    for t in PARTIAL:
        ax.scatter(style.sig([U.loc[t, "utilization"]]), style.sig([U.loc[t, "queue_mean"]]), facecolors="white", edgecolors=BRAND_BLUE, s=22, zorder=3)
    ax.set_xlabel("Brake utilization", fontsize=9)
    ax.set_ylabel("Mean brake queue (working days)", fontsize=9)
    ax.set_ylim(0, max(float(U.loc[VP, "queue_mean"].max()) * 1.4, float(k * CONSTRAINT.vut_factor(0.95, m))))
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax = axes[1]
    line13(ax, U["utilization"], BRAND_BLUE)
    ax.set_ylabel("Brake utilization", fontsize=9)
    axis13(ax)
    f.tight_layout()
    a = save(f, "dashboard_brakes_13_weeks", "Brake queue against utilization on the fitted curve, and brake utilization by week")
    f, axes = fig(h=4.0, nrows=2, sharex=True)
    axes[0].plot(U.index, U["utilization"], color=BRAND_BLUE, linewidth=1.2)
    axes[0].set_ylabel("Brake utilization", fontsize=9)
    axes[1].plot(U.index, U["queue_mean"], color=AMBER, linewidth=1.2)
    axes[1].set_ylabel("Mean brake queue (days)", fontsize=9)
    f.tight_layout()
    b = save(f, "dashboard_brakes_trend", "Brake utilization and mean brake queue by week, trend")
    rows = []
    for mid, g in MW.groupby("machine_id"):
        g = g.set_index("week_start")
        v13, cur = g.loc[V], g.loc[CW]
        g["available"] = g["scheduled_hours"] - g["downtime_hours"]
        g["worked"] = np.minimum(g["machine_hours"] - g["saturday_hours"], g["available"])      # extended-shift hours can exceed the weekday shifts
        v13, cur = g.loc[V], g.loc[CW]
        util = lambda d: d["worked"].sum() / d["available"].sum()
        qm = (v13["queue_mean"] * v13["operations"]).sum() / v13["operations"].sum()
        rows.append([mid, f"{cur['worked'] / cur['available']:.3f}", f"{util(v13):.3f}",
                     n0(v13["operations"].sum()), f"{qm:.2f}", d1(v13["downtime_hours"].sum())])
    t = wrap(table(pd.DataFrame(rows, columns=["Brake", "Utilization, current week", f"Utilization, {VIEW} weeks", f"Operations, {VIEW} weeks",
                                               f"Mean queue (days), {VIEW} weeks", f"Downtime hours, {VIEW} weeks"])))
    return ("<h2 id='panel5'>5. Brake utilization against the queue curve</h2>" +
            tiles([(f"{c['utilization']:.3f}", "Brake utilization"), (f"{c['queue_mean']:.2f}", "Mean brake queue (days)"),
                   (n0(c["operations"]), "Brake operations started"), (f"{k * float(CONSTRAINT.vut_factor(c['utilization'], m)):.2f}", "Queue on the curve at this utilization (days)")]) +
            a + cap("Mean brake queue against brake utilization for the 13 weeks on the curve fitted on 2023 to 2025, the current week marked; and brake utilization by "
                    "week.") + t + "<div class='caption'>The five brakes: utilization on crewed weekday shifts, operations, queue and downtime.</div>" +
            b + f"<div class='caption'>Brake utilization and mean brake queue by week from {wk(U.index.min())}.</div>" +
            definition("Utilization is machine time (the union of labor transaction intervals on a machine) over scheduled hours net of downtime, Saturday and extended "
                       "shifts included; for the individual brakes, on crewed weekday shifts only, capped at the scheduled hours net of "
                       "downtime. Queue is the previous operation's end to this operation's first "
                       "start, in working days. Curve: queue = k x u^(sqrt(2(m+1)) - 1) / (m(1 - u)), m the number of machines, k fitted by least squares on rolling "
                       "13-week windows of 2023 to 2025."))


# ── 6 overtime ──────────────────────────────────────────────────────────────
def panel_overtime():
    fam = OT.pivot_table(index="week_start", columns="family", values="labor_hours", aggfunc="sum", fill_value=0.0).reindex(W.index, fill_value=0.0)
    typ = OT.pivot_table(index="week_start", columns="overtime_type", values="labor_hours", aggfunc="sum", fill_value=0.0).reindex(W.index, fill_value=0.0)
    for col in ("Saturday shift", "extended shift"):
        if col not in typ:
            typ[col] = 0.0
    rush = OT[OT["rush_flag"]].groupby("week_start")["labor_hours"].sum().reindex(W.index, fill_value=0.0)
    v = OT[OT["week_start"].isin(V)]
    tot = v["labor_hours"].sum()
    er = v.loc[(v["family"] == "enclosure") | v["rush_flag"], "labor_hours"].sum() / tot if tot else np.nan
    f, ax = fig(h=2.8)
    bottom = np.zeros(len(VP))
    for k_, fm in enumerate(sorted(fam.columns, key=lambda x: -fam.loc[V, x].sum())):
        y = fam[fm].reindex(VP).to_numpy()
        if y.sum() > 0:
            ax.bar(range(len(VP)), y, bottom=bottom, color=PALETTE[k_ % len(PALETTE)], label=fm.capitalize(), width=0.75)
            bottom += y
    ax.plot(range(len(VP)), rush.reindex(VP).to_numpy(), color=RED, marker="D", markersize=4, linewidth=0, label="Of which rush jobs")
    axis13(ax)
    ax.set_ylabel("Overtime labor hours", fontsize=9)
    ax.set_ylim(0, max(bottom.max() * 1.25, 1))
    ax.legend(frameon=False, fontsize=8, loc="upper left", ncols=3)
    f.tight_layout()
    a = save(f, "dashboard_overtime_13_weeks", "Overtime labor hours at the brakes by part family, 13 weeks")
    f, ax = fig(h=2.8)
    ax.bar(W.index, typ["Saturday shift"], width=6, color=BRAND_BLUE, label="Saturday shift")
    ax.bar(W.index, typ["extended shift"], width=6, bottom=typ["Saturday shift"], color=AMBER, label="Extended shift")
    ax.set_ylabel("Overtime labor hours", fontsize=9)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    f.tight_layout()
    b = save(f, "dashboard_overtime_trend", "Overtime labor hours at the brakes, Saturday and extended, trend")
    return ("<h2 id='panel6'>6. Overtime by attributed cause</h2>" +
            tiles([(d1(typ.loc[CW, "Saturday shift"]), "Saturday labor hours at the brakes"), (d1(typ.loc[CW, "extended shift"]), "Extended-shift labor hours at the brakes"),
                   (d1(tot), f"Overtime labor hours, {VIEW} weeks"), ("none" if not tot else pct(er), f"Enclosure and rush share, {VIEW} weeks")]) +
            a + cap("Overtime labor hours at the brakes by part family, with the hours on rush jobs marked.") +
            b + f"<div class='caption'>Overtime labor hours at the brakes by week from {wk(W.index.min())}, Saturday and extended shifts.</div>" +
            definition("Overtime is labor hours at the brakes on Saturdays and after 22:00 on days with an extended second shift, attributed to the part family and the "
                       "rush flag of the job worked."))


# ── 7 quoting ───────────────────────────────────────────────────────────────
def panel_quoting():
    done = QW.index[(QW["shipped_share"] >= SHIPPED_SHARE) & (QW.index <= CW)]
    last = done.max()
    r = QW.loc[last]
    c = QW.loc[CW]
    v = QW.loc[V]
    win_fast, win_slow = v["won_within_3_days"].sum() / v["quotes_within_3_days"].sum(), v["won_over_3_days"].sum() / v["quotes_over_3_days"].sum()
    undecided = v["quotes_undecided"].sum() / v["quotes_sent"].sum()
    f, axes = fig(h=3.0, ncols=2, gridspec_kw=dict(width_ratios=[1.7, 1]))
    ax = axes[0]
    ok = QW["shipped_share"] >= SHIPPED_SHARE
    line13(ax, QW["fixed_quote_met"].where(ok), GREY, "Fixed quote", scale=100)
    line13(ax, QW["quote_table_met"].where(ok), BRAND_BLUE, "Quote table", scale=100)
    ax.axhline(80, color=RED, linewidth=1, linestyle="--")
    ax.set_ylabel("Quote met (%)", fontsize=9)
    ax.legend(frameon=False, fontsize=8, loc="lower left")
    axis13(ax)
    ax = axes[1]
    ax.bar([0, 1], [win_fast * 100, win_slow * 100], color=[BRAND_BLUE, AMBER], width=0.55)
    for xi, y, n_ in ((0, win_fast, v["quotes_within_3_days"].sum()), (1, win_slow, v["quotes_over_3_days"].sum())):
        ax.annotate(f"{y:.1%}\n{n_:,.0f} quotes", (xi, y * 100), textcoords="offset points", xytext=(0, 2), ha="center", fontsize=8)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["3 days or less", "Over 3 days"], fontsize=9)
    ax.set_ylabel(f"Win rate, {VIEW} weeks (%)", fontsize=9)
    ax.set_ylim(0, 75)
    f.tight_layout()
    a = save(f, "dashboard_quoting_13_weeks", "Quote hit rates by release week and win rate by turnaround, 13 weeks")
    f, axes = fig(h=4.2, nrows=2, sharex=True)
    t = QW[ok]
    axes[0].plot(t.index, t["fixed_quote_met"] * 100, color=GREY, linewidth=1.2, label="Fixed quote")
    axes[0].plot(t.index, t["quote_table_met"] * 100, color=BRAND_BLUE, linewidth=1.2, label="Quote table")
    axes[0].axhline(80, color=RED, linewidth=1, linestyle="--")
    axes[0].set_ylabel("Quote met (%)", fontsize=9)
    axes[0].legend(frameon=False, fontsize=8, loc="lower left")
    axes[1].plot(QW.index, QW["sent_within_3_days"] * 100, color=BRAND_BLUE, linewidth=1.2)
    axes[1].set_ylabel("Quotes sent within 3 days (%)", fontsize=9)
    f.tight_layout()
    b = save(f, "dashboard_quoting_trend", "Quote hit rates by release week and share of quotes sent within 3 days, trend")
    return ("<h2 id='panel7'>7. Quoting</h2>" +
            tiles([(pct(r["fixed_quote_met"]), f"Fixed quote met, jobs released in the week of {wk(last)}"),
                   (pct(r["quote_table_met"]), f"Quote table met, jobs released in the week of {wk(last)}"),
                   (pct(c["sent_within_3_days"]), f"Quotes sent within 3 days, of {n0(c['quotes_sent'])} sent"),
                   (pct(v["won_within_3_days"].sum() / v["quotes_sent"].sum() + v["won_over_3_days"].sum() / v["quotes_sent"].sum()),
                    f"Win rate, {VIEW} weeks; {pct(undecided)} of quotes undecided")]) +
            a + cap(f"Share of non-rush jobs meeting the fixed quote and the quote table by release week, through the week of {wk(last)}, the latest with at least "
                    f"{pct(SHIPPED_SHARE, 0)} of its jobs shipped; and win rate by turnaround for quotes sent in the {VIEW} weeks.") +
            b + f"<div class='caption'>Quote hit rates by release week and the share of quotes sent within 3 days by week from {wk(QW.index.min())}; the line is 80%.</div>" +
            definition("A quote is met when the working days from the release day to the ship day are at or under it; rush lines are left out. The fixed quote is 10 days "
                       "for repeat parts, 15 for new parts and 20 with outside processing. The quote table is the table fitted on 2023 to 2025 (Quoting and early warning from load, Table 2): the "
                       "80th-percentile lead time of the routing class and brake backlog band at release, rounded up, never below the fixed quote. Turnaround is weekdays "
                       "from RFQ received to quote sent. Win rate is won over quotes sent, with no decision counted as not won."))


# ── page ────────────────────────────────────────────────────────────────────
def main():
    partial = f"; the week of {PARTIAL[0]:%B} {PARTIAL[0].day} is partial" if PARTIAL else ""
    meta = (f"Custom sheet-metal fabrication job shop, about 120 employees, one plant. Week of {wk(CW)} (current week{partial}); {VIEW}-week view from {wk(V[0])}; "
            f"trend from {wk(W.index.min())}.<br>Sources: ERP, shop-floor data collection, QMS, maintenance and HR exports (batch {batch}). Weeks start on Monday; "
            f"durations in working days.")
    body = "\n".join([panel_delivery(), panel_leading(), panel_wip(), panel_causes(), panel_brakes(), panel_overtime(), panel_quoting()])
    toc = [("panel1", "Delivery"), ("panel2", "Leading set"), ("panel3", "WIP and queue"), ("panel4", "Late jobs by cause"), ("panel5", "Brakes"), ("panel6", "Overtime"), ("panel7", "Quoting")]
    out = DOCS / "dashboard"
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(style.shell("Operations dashboard", "Dashboard", meta, body, toc), encoding="utf8")
    print("wrote docs/dashboard/index.html")


if __name__ == "__main__":
    main()
