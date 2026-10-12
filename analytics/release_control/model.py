"""Discrete-event model of the shop under current practice, built from the measured release stream and processing distributions.

The model replays the jobs actually released (routing, standards, promised date, rush flag, planned operation dates) and draws processing,
move, material and outside-processing times from the measured distributions. Dispatch, nest-fill cutting, brake assignment, setup grouping,
the daily dispatch list, the powder color schedule and the overtime rule follow the shop's practice.
"""
import bisect
import zlib
from collections import defaultdict

import numpy as np
import pandas as pd
import simpy

from analytics.db import q

T0 = pd.Timestamp("2024-01-01")
REPORT_YEAR = 2025
FIRST, SECOND = (6.0, 14.0), (14.5, 22.5)
EXTENDED = (22.5, 24.5)
DAILY_LIST = {"hardware", "weld", "grind_deburr", "assembly", "inspection_pack"}
LIST_CUTOFF_HOUR = 10.0
HOT_DAYS = 2
GROUP_MAX = 3
HEAVY_GAUGES = {"12ga", "11ga", "0.125in", "0.250in"}
SAT_MACHINES = ("B1", "B2")
CELL = "RB1"                                   # the robotic bending cell, when a scenario adds it
CELL_MIN_LOT = 25
TOWER_HOURS = (22.5, 28.5)                     # unattended cutting after second shift on the laser with the sheet tower
BRAKE_PRIORITY = {"B1": [{"precision"}, {"heavy", "light"}], "B2": [{"precision"}, {"heavy", "light"}], "B3": [{"heavy", "light"}], "B4": [{"heavy", "light"}],
                  "B5": [{"light"}]}


# the keys of the scenarios renamed since their runs were made, so that each still repeats its runs
SEED_KEY = {"S8 Setup reduction": 4044333780, "Package 2 Setup reduction + weld second shift + planned Saturdays": 1174389978, "Package 1 Setup reduction + weld second shift": 3645362548}


def generator_seed(scenario, replication):
    """The seed of the one generator a run draws from: its scenario and its replication number."""
    return np.random.SeedSequence([SEED_KEY.get(scenario, zlib.crc32(scenario.encode("utf8"))), int(replication)])


def hours(ts):
    return (pd.Timestamp(ts) - T0) / pd.Timedelta(hours=1)


# ── measured inputs ─────────────────────────────────────────────────────────
class Sampler:
    """Actual-over-standard ratios drawn from operations of similar standard hours (bands by quantile), so the tails stay with the small operations."""

    def __init__(self, std, ratio, bands=8):
        std, ratio = np.asarray(std, dtype=float), np.asarray(ratio, dtype=float)
        ok = np.isfinite(ratio) & (std > 0)
        order = np.lexsort((ratio[ok], std[ok]))                       # one order whatever order the rows were read in
        std, ratio = std[ok][order], ratio[ok][order]
        self.edges = np.unique(np.quantile(std, np.linspace(0, 1, bands + 1)[1:-1])) if len(std) >= bands * 5 else np.array([])
        idx = np.searchsorted(self.edges, std, side="right")
        self.arrays = [ratio[idx == k] for k in range(len(self.edges) + 1)]
        self.all = ratio

    def draw(self, rng, std):
        if len(self.all) == 0:
            return 1.0
        a = self.arrays[int(np.searchsorted(self.edges, std, side="right"))]
        return float(rng.choice(a if len(a) else self.all))


class Inputs:
    """Everything the model reads from the marts, loaded once."""

    def __init__(self, start="2024-01-01"):
        self.batch = q("select export_batch_id from marts.mart_job_lead_time limit 1").iloc[0, 0]
        jobs = q(f"""
            select j.job_id, j.part_id, j.customer_id, j.release_date, j.due_date, j.qty, l.rush_flag, l.routing_class, l.quoted_lead_days, ol.order_date,
                ol.requested_date, round(coalesce(ol.unit_price * ol.qty, 0), 2) as revenue, p.family, p.bend_count, p.thickness, p.tolerance_critical, p.powder_color, p.repeat_part
            from staging.stg_erp__jobs j
            join intermediate.int_job_lead_time l using (job_id)
            join staging.stg_erp__parts p on p.part_id = j.part_id
            left join staging.stg_erp__order_lines ol on ol.order_line_id = j.order_line_id
            where j.release_date >= '{start}' order by j.job_id""")
        ops = q(f"""
            select jo.job_id, jo.op_seq, jo.work_center, jo.planned_start, jo.setup_std, jo.run_std * jo.qty as run_std_hours, r.tooling_set
            from staging.stg_erp__job_operations jo
            join staging.stg_erp__jobs j using (job_id)
            left join staging.stg_erp__routings r on r.part_id = j.part_id and r.op_seq = jo.op_seq and r.work_center = jo.work_center
            where j.release_date >= '{start}' order by jo.job_id, jo.op_seq""")
        sheets = q("""select t.job_id, min(t.item_id) as sheet_item, sum(t.qty) as sheets from staging.stg_erp__inventory_transactions t
                      join staging.stg_erp__inventory_items i using (item_id) where i.item_type = 'sheet' and t.transaction_type = 'issue' group by 1 order by 1""")
        jobs = jobs.merge(sheets, on="job_id", how="left")
        jobs["rush_flag"] = jobs["rush_flag"].fillna(False).astype(bool)
        jobs["cls"] = np.where((jobs["bend_count"] >= 10) | jobs["tolerance_critical"].fillna(False), "precision",
                               np.where(jobs["thickness"].isin(HEAVY_GAUGES), "heavy", "light"))
        # parts a robotic bending cell can run: light parts, repeat parts, lots of CELL_MIN_LOT pieces or more
        jobs["cell_ok"] = (jobs["cls"] == "light") & jobs["repeat_part"].fillna(False).astype(bool) & (jobs["qty"] >= CELL_MIN_LOT)
        self.jobs = jobs.sort_values(["release_date", "job_id"]).reset_index(drop=True)
        self.ops = {k: g.to_dict("records") for k, g in ops.groupby("job_id")}
        # the customers that make up 80% of the revenue shipped in the report year, largest first
        rev = q(f"""select j.customer_id, sum(ol.unit_price * ol.qty) as revenue from staging.stg_erp__jobs j join staging.stg_erp__order_lines ol using (order_line_id)
                    where year(j.ship_date) = {REPORT_YEAR} group by 1 order by 2 desc, 1""")
        share = (rev["revenue"].cumsum() - rev["revenue"]) / rev["revenue"].sum()
        self.top_customers = {c: round(float(v), 2) for c, v in zip(rev["customer_id"][share < 0.8], rev["revenue"][share < 0.8])}

        cal = q("select work_center, calendar_date, scheduled_hours, saturday from staging.stg_erp__work_center_calendar order by all")
        cal["calendar_date"] = pd.to_datetime(cal["calendar_date"])
        self.cal = cal[cal["calendar_date"] >= T0].sort_values(["work_center", "calendar_date"]).reset_index(drop=True)
        self.shifts = q("select machine_id, work_center, crewed_shifts from intermediate.int_machine_shifts order by all").set_index("machine_id")
        dt = q("select machine_id, start_ts, end_ts from marts.mart_downtime_events order by all")
        self.downtime = {k: [(hours(a), hours(b)) for a, b in zip(g["start_ts"], g["end_ts"])] for k, g in dt.groupby("machine_id")}
        colors = q("select schedule_date, color from staging.stg_mes__powder_color_schedule order by all")
        self.color_days = defaultdict(set)
        for d, c in zip(pd.to_datetime(colors["schedule_date"]), colors["color"]):
            self.color_days[d.date()].add(c)

        # working-day clock
        days = pd.date_range(T0, pd.Timestamp("2026-06-30"))
        wd = set(self.cal["calendar_date"].dt.date)
        last = max(wd)
        self.flag = np.array([(d.date() in wd) if d.date() <= last else d.weekday() < 5 for d in days], dtype=float)
        self.weekday_flag = np.array([f and d.weekday() < 5 for f, d in zip(self.flag, days)], dtype=float)
        self.cum = np.concatenate([[0.0], np.cumsum(self.flag)])
        self.days = days

        # measured distributions (report year)
        s = q(f"select work_center, setup_std, setup_ratio, same_tooling_as_previous as grouped, qty from marts.mart_setups "
              f"where setup_year = {REPORT_YEAR} and setup_std > 0 order by all")
        s["grouped"] = s["grouped"].fillna(False).astype(bool)
        self.setup_ratio = {wc: Sampler(g["setup_std"], g["setup_ratio"]) for wc, g in s[s["work_center"] != "press_brake"].groupby("work_center")}
        b = s[s["work_center"] == "press_brake"]
        self.brake_setup_ratio = {}
        for g_ in (True, False):
            for sm in (True, False):
                x = b[(b["grouped"] == g_) & ((b["qty"] < 25) == sm)]
                self.brake_setup_ratio[(g_, sm)] = Sampler(x["setup_std"], x["setup_ratio"], bands=4)
        # Setup and run are drawn together. At every work center 5% to 7% of operations have no setup clocked (press brake 317 of 5,566 in the
        # report year): the setup was clocked under run, so their run hours hold it. Until this change a setup was drawn for every operation and the
        # run ratio from all operations, which counted those setups twice (about 357 brake hours a year).
        #   no_setup_share  the share of operations of the work center with a setup standard and no setup clocked
        #   run_ratio       run hours over run standard, from operations with a setup clocked
        #   whole_ratio     run hours over setup plus run standard, from operations with no setup clocked, banded on the whole standard. Pooled:
        #                   press brake 0.98, robotic weld 1.00, manual weld 0.97, punch 0.97, hardware 0.96, inspection and pack 0.94,
        #                   powder coat 0.91, grind and deburr 0.90, laser 0.85, assembly 1.02.
        # The whole-time ratio replaces the form first used for these operations, run standard times their run hours over run standard: that
        # ratio is large wherever the run is short beside the setup inside it (mean 4.1 by operation at the robotic weld cell, highest 162 at the
        # brakes), and drawn onto other operations it put the robotic weld cell at 0.913 of crewed hours against 0.818 in the record.
        r = q(f"select work_center, machine_id, setup_std, run_std_hours, run_hours, coalesce(setup_hours, 0) = 0 and setup_std > 0 as no_setup "
              f"from marts.mart_run_standards where start_year = {REPORT_YEAR} and run_std_hours > 0 order by all")
        r["no_setup"] = r["no_setup"].astype(bool)
        r["ratio"], r["whole_std"] = r["run_hours"] / r["run_std_hours"], r["setup_std"] + r["run_std_hours"]
        r["whole"] = r["run_hours"] / r["whole_std"]
        both, none = r[~r["no_setup"]], r[r["no_setup"]]
        self.no_setup_share = {wc: round(float(g["no_setup"].mean()), 9) for wc, g in r.groupby("work_center")}
        self.run_ratio = {wc: Sampler(g["run_std_hours"], g["ratio"]) for wc, g in both.groupby("work_center")}
        self.laser_run_ratio = {m: Sampler(g["run_std_hours"], g["ratio"]) for m, g in both[both["work_center"] == "laser"].groupby("machine_id")}
        self.whole_ratio = {wc: Sampler(g["whole_std"], g["whole"]) for wc, g in none.groupby("work_center")}
        self.laser_whole_ratio = {m: Sampler(g["whole_std"], g["whole"]) for m, g in none[none["work_center"] == "laser"].groupby("machine_id")}
        st = q(f"""select s.job_id, s.op_seq, s.work_center, s.stage, s.days, l.routing_class from intermediate.int_job_stage_days s
                   join intermediate.int_job_lead_time l using (job_id) where year(l.ship_date) = {REPORT_YEAR} order by all""")
        mat = st[st["stage"] == "material wait at first operation"].groupby("job_id")["days"].sum()
        jl = st.drop_duplicates("job_id").set_index("job_id")["routing_class"]
        self.material = {c: np.sort(mat.reindex(jl[jl == c].index).fillna(0.0).to_numpy()) for c in sorted(jl.unique())}
        mv = st[(st["stage"] == "move") | st["stage"].str.startswith("hold")].groupby(["job_id", "op_seq", "work_center"])["days"].sum().reset_index()
        self.move = {wc: np.sort(g["days"].to_numpy()) for wc, g in mv.groupby("work_center")}
        self.outside = np.sort(st[st["stage"] == "outside processing"].groupby(["job_id", "op_seq"])["days"].sum().to_numpy())
        self.ship = np.sort(st[st["stage"] == "complete to ship"]["days"].to_numpy())
        # ratios summed by the database are rounded: the order of a sum is not fixed and its last digits must not reach the model
        self.brake_actual_over_standard = round(float(q(f"""select sum(setup_hours + run_hours) / sum(setup_std + run_std_hours) from marts.mart_operations
                                                           where work_center = 'press_brake' and start_year = {REPORT_YEAR}""").iloc[0, 0]), 9)
        # overtime as worked: share of weeks with a Saturday brake shift and share of days with an extended shift, by jobs at the brakes that week
        wkl = q("select round(wip_at_brakes, 6) as wip_at_brakes, brake_saturday_shifts, brake_extended_hours from marts.mart_weekly_floor "
                "where weekdays = 5 order by week_start")
        self.ot_edges = np.array([30.0, 60.0, 90.0, 120.0])
        band = np.searchsorted(self.ot_edges, wkl["wip_at_brakes"].to_numpy(), side="right")
        self.p_saturday = np.array([float((wkl["brake_saturday_shifts"][band == k] > 0).mean()) if (band == k).any() else 0.0 for k in range(5)])
        self.p_extended = np.array([float((wkl["brake_extended_hours"][band == k] / 4.0 / 5.0).clip(upper=1).mean()) if (band == k).any() else 0.0 for k in range(5)])
        # share of crewed brake hours net of downtime worked when the queue never empties (brakes without overtime, weeks with over 120 jobs waiting)
        av = q("""select sum(m.machine_hours) / sum(m.scheduled_hours - m.downtime_hours) from marts.mart_machine_weekly m
                  join marts.mart_weekly_floor w using (week_start)
                  where m.work_center = 'press_brake' and m.saturday_hours = 0 and m.machine_id not in ('B1', 'B2') and w.wip_at_brakes > 120 and w.weekdays = 5""")
        self.brake_availability = round(min(float(av.iloc[0, 0]), 1.0), 9)
        # Share of crewed laser hours net of downtime worked when work is waiting, measured as the brake share is: full weeks with over 90 jobs at
        # the lasers (10 weeks). Until this change the lasers worked every crewed hour, 1.000; the record gives 0.909, and 0.917 over the nine weeks
        # from November 11, 2024. The unattended hours of a sheet tower are not crewed hours and stay at 1.
        lv = q("""select sum(u.machine_hours) / sum(u.scheduled_hours - u.downtime_hours) from marts.mart_utilization_weekly u
                  join marts.mart_weekly_floor w using (week_start) where u.work_center = 'laser' and w.wip_at_laser > 90 and w.weekdays = 5""")
        self.laser_availability = round(min(float(lv.iloc[0, 0]), 1.0), 9)
        # Brake hours outside the ordinary weekday shift, as the whole record shows them worked. Until this export's rerun every crewed brake hour,
        # Saturday, extended and holiday-week hours included, was worked at brake_availability (0.967), and a Saturday shift was 8 hours on both B1 and B2.
        #   saturday_with_time  was 1.000 (every Saturday called was worked), now 0.679: scheduled brake Saturdays in the calendar that have brake machine time
        #   saturday_yield      was 0.967 on two brakes, now 1.000 on one brake: brake machine hours on those Saturdays over 8 hours each, at most 1
        #   extended_yield      was 0.967, now 0.239: weekday and extended machine hours in full weeks with extended hours, less weekday crewed hours at
        #                       brake_availability, over the extended hours scheduled
        #   holiday_yield       was 0.967, now 0.885: machine hours over crewed hours net of downtime in weeks with fewer than five working weekdays
        #   brake_availability  0.967, unchanged, on ordinary weekday hours
        sat = q("""select c.calendar_date, coalesce(t.hours, 0) as hours from staging.stg_erp__work_center_calendar c
                   left join (select cast(start_ts as date) as d, sum(hours) as hours from intermediate.int_machine_time where work_center = 'press_brake' group by 1) t
                     on t.d = c.calendar_date
                   where c.work_center = 'press_brake' and c.saturday order by 1""")
        worked = sat[sat["hours"] > 0]
        self.saturday_with_time = round(float(len(worked) / len(sat)), 9)
        self.saturday_yield = round(min(float(worked["hours"].sum() / (8.0 * len(worked))), 1.0), 9)
        bw = q("""select m.week_start, w.weekdays, max(u.extended_hours) as extended_hours, sum(m.machine_hours - m.saturday_hours) as worked,
                      sum(m.scheduled_hours - m.downtime_hours) as crewed
                  from marts.mart_machine_weekly m join marts.mart_weekly_floor w using (week_start)
                  join marts.mart_utilization_weekly u on u.week_start = m.week_start and u.work_center = 'press_brake'
                  where m.work_center = 'press_brake' group by 1, 2 order by 1""")
        ext = bw[(bw["weekdays"] == 5) & (bw["extended_hours"] > 0)]
        fitted = (ext["worked"].sum() - self.brake_availability * ext["crewed"].sum()) / ext["extended_hours"].sum()
        self.extended_yield = round(float(min(max(fitted, 0.0), 1.0)), 9)
        short = bw[bw["weekdays"] < 5]
        self.holiday_yield = round(float(short["worked"].sum() / short["crewed"].sum()), 9)
        bc = self.cal[(self.cal["work_center"] == "press_brake") & ~self.cal["saturday"]]
        per_week = bc.groupby(bc["calendar_date"] - pd.to_timedelta(bc["calendar_date"].dt.weekday, unit="D")).size()
        self.holiday_days = {(wk - T0).days + k for wk in per_week[per_week < 5].index for k in range(7)}

    # working-day clock
    def W(self, t):
        d = int(t // 24)
        return self.cum[d] + self.flag[d] * (t - 24 * d) / 24.0

    def wd_add(self, t, days):
        """The time `days` working days after t."""
        if days <= 0:
            return t
        target = self.W(t) + days
        d = int(np.searchsorted(self.cum, target, side="right") - 1)
        d = min(d, len(self.flag) - 1)
        while self.flag[d] == 0:
            d += 1
        return 24 * d + (target - self.cum[d]) * 24.0

    def next_working_morning(self, t):
        d = int(t // 24) + 1
        while self.weekday_flag[d] == 0:
            d += 1
        return 24 * d + FIRST[0]

    def working_days_ahead(self, t, n):
        """Start of the day n working weekdays after the day of t."""
        d = int(t // 24)
        k = 0
        while k < n:
            d += 1
            if self.weekday_flag[d]:
                k += 1
        return 24 * d


# ── the floor ───────────────────────────────────────────────────────────────
class Gate:
    """Release control ahead of the first operation. Rush jobs are released at once; the others in release order.

    cap: a job is released when the jobs on the floor are below the cap (a job leaves the floor when it ships).
    paced: a job with brake work is released when the work waiting at the brakes, in days of crewed brake capacity, is at or below the limit."""

    def __init__(self, shop, mode, limit):
        self.shop, self.mode, self.limit = shop, mode, limit
        self.pending = []
        self.on_floor = 0
        self.brake_load = 0.0
        self.held_days = []

    def backlog_days(self):
        waiting = sum(e["std"] for e in self.shop.queue["press_brake"])
        return waiting * self.shop.inp.brake_actual_over_standard / 72.0

    def open_for(self, brake_std):
        if self.mode == "cap":
            return self.on_floor < self.limit
        return brake_std <= 0 or self.backlog_days() <= self.limit

    def admit(self, ev, brake_std, t_in):
        self.on_floor += 1
        self.brake_load += brake_std
        self.held_days.append(self.shop.inp.W(self.shop.env.now) - self.shop.inp.W(t_in))
        ev.succeed()

    def request(self, rush, brake_std):
        ev = self.shop.env.event()
        if rush:
            self.admit(ev, brake_std, self.shop.env.now)
        else:
            self.pending.append((ev, brake_std, self.shop.env.now))
            self.release()
        return ev

    def release(self):
        i = 0
        while i < len(self.pending):
            ev, std, t_in = self.pending[i]
            if self.open_for(std):
                self.pending.pop(i)
                self.admit(ev, std, t_in)
            elif self.mode == "cap":
                break
            else:
                i += 1

    def brake_done(self, std):
        self.brake_load -= std
        self.release()

    def shipped(self):
        self.on_floor -= 1
        self.release()


class Machine:
    def __init__(self, mid, wc, windows):
        self.id, self.wc = mid, wc
        self.windows = windows                 # sorted (start, end, overtime)
        self.i = 0
        self.extra = []                        # overtime windows added by the rule
        self.busy = False
        self.blocked_until = 0.0
        self.last_tool, self.group_n = None, 0
        self.busy_hours = defaultdict(float)   # by (year, quarter)
        self.setup_hours = defaultdict(float)  # by (year, quarter) of the setup's start
        self.sched_added = defaultdict(float)

    def next_window(self, t):
        while self.i < len(self.windows) and self.windows[self.i][1] <= t + 1e-9:
            self.i += 1
        while self.extra and self.extra[0][1] <= t + 1e-9:
            self.extra.pop(0)
        a = self.windows[self.i] if self.i < len(self.windows) else None
        b = self.extra[0] if self.extra else None
        if a is None:
            return b
        if b is None:
            return a
        return a if a[0] <= b[0] else b


class Shop:
    def __init__(self, inp, seed, scenario=None):
        self.inp, self.rng, self.sc = inp, np.random.default_rng(seed), scenario or {}
        self.env = simpy.Environment()
        self.queue = defaultdict(list)
        self.signal = {}
        self.machines = defaultdict(list)
        self.pool = defaultdict(list)          # nest pools by sheet item
        self.results = []
        self.op_log = []                           # every finished operation: work center, job, operation, arrival, start, end, standard hours,
                                                   # and the end of the job's previous operation (its arrival for a first operation)
        self.overtime = dict(saturdays=0, extended_days=0, hours=0.0)
        self.ot_log = []
        self.saturday_scheduled = defaultdict(float)   # by (year, quarter): the calendar's 16 scheduled brake hours for each Saturday called
        self.gate = None
        if self.sc.get("wip_cap"):
            self.gate = Gate(self, "cap", self.sc["wip_cap"])
        elif self.sc.get("paced_days"):
            self.gate = Gate(self, "paced", self.sc["paced_days"])
        self.color_days = inp.color_days
        if self.sc.get("extra_color_day"):
            color, weekday = self.sc["extra_color_day"]
            self.color_days = defaultdict(set, {d: set(c) for d, c in inp.color_days.items()})
            for d in list(self.color_days) + [x.date() for x in inp.days if inp.weekday_flag[(x - T0).days]]:
                if d.weekday() == weekday:
                    self.color_days[d].add(color)
        self._build_machines()

    # calendar ---------------------------------------------------------------
    def _build_machines(self):
        inp = self.inp
        for wc, cal in inp.cal.groupby("work_center"):
            mids = inp.shifts[inp.shifts["work_center"] == wc].index.tolist()
            for mid in sorted(mids):
                shifts = int(inp.shifts.loc[mid, "crewed_shifts"]) + (1 if self.sc.get("second_shift") == mid else 0)
                win = []
                for d, sat in zip(cal["calendar_date"], cal["saturday"]):
                    base = hours(d)
                    if sat:
                        if wc == "laser":
                            win.append((base + FIRST[0], base + FIRST[1], False))
                        continue                                         # brake Saturdays come from the overtime rule
                    win.append((base + FIRST[0], base + FIRST[1], False))
                    if shifts >= 2:
                        win.append((base + SECOND[0], base + SECOND[1], False))
                    if self.sc.get("laser_tower") == mid:
                        win.append((base + TOWER_HOURS[0], base + TOWER_HOURS[1], False))
                win = self._subtract(sorted(win), sorted(inp.downtime.get(mid, [])))
                self.machines[wc].append(Machine(mid, wc, win))
            if wc == "press_brake" and self.sc.get("bending_cell"):
                win = []
                for d, sat in zip(cal["calendar_date"], cal["saturday"]):
                    if not sat:
                        win += [(hours(d) + FIRST[0], hours(d) + FIRST[1], False), (hours(d) + SECOND[0], hours(d) + SECOND[1], False)]
                self.machines[wc].append(Machine(CELL, wc, sorted(win)))
            self.signal[wc] = self.env.event()

    @staticmethod
    def _subtract(windows, downs):
        out = []
        for a, b, ot in windows:
            cur = a
            for x, y in downs:
                if y <= cur or x >= b:
                    continue
                if x > cur:
                    out.append((cur, x, ot))
                cur = max(cur, y)
                if cur >= b:
                    break
            if cur < b:
                out.append((cur, b, ot))
        return out

    def wake(self, wc):
        old, self.signal[wc] = self.signal[wc], self.env.event()
        old.succeed()

    # dispatch ---------------------------------------------------------------
    def priority(self, e, t):
        if e["rush"]:
            return 0
        return 1 if e["due_h"] <= self.inp.working_days_ahead(t, HOT_DAYS) + 24 else 2

    def key(self, e, t):
        return (self.priority(e, t), e["planned"], e["arrival"])

    def pick(self, m, t, overtime):
        wc = m.wc
        cand = self.queue[wc]
        if not cand:
            return None, False
        if wc == "laser":
            cand = [e for e in cand if e["eligible"]]
        elif wc == "powder_coat":
            colors = self.color_days.get((T0 + pd.Timedelta(hours=t)).date(), set())
            cand = [e for e in cand if e["color"] in colors or e["color"] is None]
        elif wc in DAILY_LIST and not self.sc.get("continuous_dispatch"):
            cutoff = 24 * int(t // 24) + LIST_CUTOFF_HOUR
            cand = [e for e in cand if e["arrival"] < cutoff or self.priority(e, t) < 2]
        grouped = False
        if wc == "press_brake" and m.id == CELL:
            cand = [e for e in cand if e["cell_ok"]]
        elif wc == "press_brake":
            if overtime:
                cand = [e for e in cand if e["family"] == "enclosure" or e["rush"]]
            else:
                hot = [e for e in cand if self.capable(m, e) and self.priority(e, t) < 2]
                if hot:
                    cand = hot
                else:
                    own = []
                    groups = BRAKE_PRIORITY[m.id]
                    limit = self.sc.get("light_relief_days")
                    if limit and m.id in SAT_MACHINES:
                        waiting = sum(e["std"] for e in self.queue[wc] if e["cls"] != "precision") * self.inp.brake_actual_over_standard / 40.0
                        if waiting > limit:
                            groups = [{"precision"}, {"light"}, {"heavy"}]
                    for group in groups:
                        own = [e for e in cand if e["cls"] in group]
                        if own:
                            break
                    cand = own
                same = [e for e in cand if e["tool"] is not None and e["tool"] == m.last_tool]
                if same and m.group_n < GROUP_MAX:
                    cand, grouped = same, True
        if not cand:
            return None, False
        rule = self.sc.get("dispatch")
        if self.sc.get("dispatch_brakes_only") and wc != "press_brake":
            rule = None
        if rule == "edd":
            e = min(cand, key=lambda x: (0 if x["rush"] else 1, x["due_h"], x["arrival"]))
        elif rule == "spt":
            e = min(cand, key=lambda x: (0 if x["rush"] else 1, x["std"], x["arrival"]))
        elif rule == "cr":
            e = min(cand, key=lambda x: (0 if x["rush"] else 1, (x["due_h"] - t) / max(x["remaining_std"], 0.1), x["arrival"]))
        else:
            e = min(cand, key=lambda x: self.key(x, t))
        self.queue[wc].remove(e)
        return e, grouped

    @staticmethod
    def capable(m, e):
        return any(e["cls"] in g for g in BRAKE_PRIORITY[m.id])

    # processing -------------------------------------------------------------
    def durations(self, m, e, grouped):
        inp, r = self.inp, self.rng
        wc = m.wc
        if r.random() < inp.no_setup_share.get(wc, 0.0):                 # the setup is inside the run hours, as on the operations with none clocked
            sm = inp.laser_whole_ratio.get(m.id) if wc == "laser" else inp.whole_ratio.get(wc)
            return 0.0, e["std"] * (sm.draw(r, e["std"]) if sm is not None else 1.0)
        if wc == "press_brake":
            red = self.sc.get("setup_reduction")
            if red and (e["part_id"], e["op_seq"]) in red["at_standard"]:
                su = e["setup_std"]
            else:
                su = e["setup_std"] * inp.brake_setup_ratio[(grouped, e["qty"] < 25)].draw(r, e["setup_std"]) * (red["other_factor"] if red else 1.0)
            atc = self.sc.get("tool_changer")
            if atc and (atc["machines"] == "all" or m.id in atc["machines"]):
                su *= atc["setup_factor"]
            ts = T0 + pd.Timedelta(hours=self.env.now)
            m.setup_hours[(ts.year, ts.quarter)] += su
        else:
            sm = inp.setup_ratio.get(wc)
            su = e["setup_std"] * (sm.draw(r, e["setup_std"]) if sm is not None else 1.0)
        sm = inp.laser_run_ratio.get(m.id) if wc == "laser" else inp.run_ratio.get(wc)
        run = e["run_std"] * (sm.draw(r, e["run_std"]) if sm is not None and e["run_std"] > 0 else 1.0)
        return su, run

    def rate(self, m, w):
        """Machine hours worked per crewed hour in a window: at the brakes the measured share for an ordinary weekday shift, a Saturday shift, an
        extended shift or a holiday week; at the lasers the measured share of crewed hours; 1 elsewhere."""
        if m.id == CELL:
            return self.sc["bending_cell"]["availability"]
        inp = self.inp
        if m.wc == "laser":
            return 1.0 if w[0] % 24 >= TOWER_HOURS[0] - 1e-9 else inp.laser_availability
        if m.wc != "press_brake":
            return 1.0
        day = int(w[0] // 24)
        if inp.days[day].weekday() == 5:
            both = self.sc.get("planned_saturday_crew") == "both" and inp.days[day].month in self.sc.get("planned_saturday_months", ())
            return inp.brake_availability if both else inp.saturday_yield
        if w[0] % 24 >= EXTENDED[0] - 1e-9:
            return inp.extended_yield
        return inp.holiday_yield if day in inp.holiday_days else inp.brake_availability

    def note_work(self, m, start, machine_hours):
        """Called for every stretch of machine time; the model itself keeps none of them."""

    def work(self, m, hours_needed):
        """Hold the machine for `hours_needed` of machine time across its windows; at the brakes the crewed time needed is longer by the measured yield."""
        env = self.env
        left = hours_needed
        while left > 1e-9:
            w = m.next_window(env.now)
            if w is None:
                return
            if w[0] > env.now:
                yield env.timeout(w[0] - env.now)
            phi = self.rate(m, w)
            dt = min(left / phi, w[1] - env.now)
            yield env.timeout(dt)
            ts = T0 + pd.Timedelta(hours=env.now - dt / 2)
            m.busy_hours[(ts.year, ts.quarter)] += dt * phi
            self.note_work(m, env.now - dt, dt * phi)
            left -= dt * phi

    def machine_loop(self, m):
        env = self.env
        while True:
            w = m.next_window(env.now)
            if w is None:
                return
            if w[0] > env.now:
                yield env.timeout(w[0] - env.now)
                continue
            if m.blocked_until > env.now + 1e-9:
                yield env.timeout(min(m.blocked_until, w[1]) - env.now)
                continue
            e, grouped = self.pick(m, env.now, w[2])
            if e is None:
                yield self.signal[m.wc] | env.timeout(w[1] - env.now)
                continue
            m.busy = True
            su, run = self.durations(m, e, grouped)
            if m.wc == "press_brake":
                m.group_n = m.group_n + 1 if grouped else 0
                m.last_tool = e["tool"]
                if e["cls"] == "heavy":                                  # a heavy setup takes a second operator from an idle brake
                    for other in self.machines["press_brake"]:
                        ow = other.next_window(env.now)
                        if other is not m and other.id != CELL and not other.busy and other.blocked_until <= env.now and ow is not None and ow[0] <= env.now:
                            other.blocked_until = env.now + su
                            break
            e["start"] = env.now
            yield from self.work(m, su + run)
            m.busy = False
            self.op_log.append((m.wc, e["job_id"], e["op_seq"], e["arrival"], e["start"], env.now, e["std"], e["previous_end"]))
            e["done"].succeed()

    # jobs -------------------------------------------------------------------
    def job_flow(self, j, ops):
        env, inp, r = self.env, self.inp, self.rng
        brake_std = sum(o["setup_std"] + o["run_std_hours"] for o in ops if o["work_center"] == "press_brake")
        if self.gate is not None:
            yield self.gate.request(bool(j.rush_flag), brake_std)
        yield env.timeout(max(inp.next_working_morning(hours(j.release_date)) - env.now, 0))
        mat = float(r.choice(inp.material[j.routing_class])) if j.routing_class in inp.material else 0.0
        if mat > 0:
            yield env.timeout(inp.wd_add(env.now, mat) - env.now)
        due_h = hours(j.due_date) + 24.0
        remaining = sum(o["setup_std"] + o["run_std_hours"] for o in ops)
        for k, o in enumerate(ops):
            wc = o["work_center"]
            if wc == "outside_processing":
                yield env.timeout(inp.wd_add(env.now, float(r.choice(inp.outside))) - env.now)
                continue
            left = env.now if k > 0 else None
            if k > 0 and wc in inp.move:
                yield env.timeout(inp.wd_add(env.now, float(r.choice(inp.move[wc]))) - env.now)
            e = dict(job_id=j.job_id, part_id=j.part_id, op_seq=o["op_seq"], rush=bool(j.rush_flag), due_h=due_h, planned=hours(o["planned_start"]), arrival=env.now, family=j.family, cls=j.cls,
                     qty=j.qty, tool=o["tooling_set"], setup_std=o["setup_std"], run_std=o["run_std_hours"], std=o["setup_std"] + o["run_std_hours"],
                     remaining_std=remaining, color=j.powder_color if wc == "powder_coat" else None, eligible=True, cell_ok=bool(j.cell_ok), done=env.event(),
                     previous_end=env.now if left is None else left)
            if wc == "laser":
                self.nest(e, j)
            self.queue[wc].append(e)
            self.wake(wc)
            yield e["done"]
            remaining -= e["std"]
            if wc == "press_brake" and self.gate is not None:
                self.gate.brake_done(e["std"])
        yield env.timeout(inp.wd_add(env.now, float(r.choice(inp.ship))) - env.now)
        self.results.append(dict(job_id=j.job_id, customer_id=j.customer_id, revenue=j.revenue, release_date=j.release_date, due_date=j.due_date, ship_ts=T0 + pd.Timedelta(hours=env.now),
                                 routing_class=j.routing_class, rush=bool(j.rush_flag), order_date=j.order_date, requested_date=j.requested_date,
                                 quoted_lead_days=j.quoted_lead_days))
        if self.gate is not None:
            self.gate.shipped()

    def nest(self, e, j):
        """A job needing more than one sheet is cut on its own; single-sheet jobs wait for a second job on the sheet item or for their planned start."""
        if not (j.sheets == j.sheets) or j.sheets >= 2 or j.sheet_item is None:
            return
        pool = self.pool[j.sheet_item]
        pool.append(e)
        if len(pool) >= 2:
            for x in pool:
                x["eligible"] = True
            pool.clear()
        else:
            e["eligible"] = False

    def nest_check(self):
        env, inp = self.env, self.inp
        while True:
            yield env.timeout(inp.next_working_morning(env.now) - 0.25 - env.now)
            limit = inp.working_days_ahead(env.now, HOT_DAYS) + 24
            for item, pool in self.pool.items():
                if any(x["planned"] <= limit for x in pool):
                    for x in pool:
                        x["eligible"] = True
                    pool.clear()
            self.wake("laser")
            if self.gate is not None:
                self.gate.release()
            yield env.timeout(1.0)

    # overtime rule ------------------------------------------------------------
    def jobs_at_brakes(self):
        return len(self.queue["press_brake"]) + sum(1 for m in self.machines["press_brake"] if m.busy)

    def overtime_rule(self):
        """Saturday and extended brake shifts as the shop has worked them: by the number of jobs at the brakes."""
        env, inp, r = self.env, self.inp, self.rng
        mach = {m.id: m for m in self.machines["press_brake"]}
        while True:
            d = int(env.now // 24) + 1
            while d < len(inp.weekday_flag) and inp.weekday_flag[d] == 0:
                d += 1
            if d >= len(inp.weekday_flag) - 3:
                return
            yield env.timeout(24 * d + 12.0 - env.now)
            k = int(np.searchsorted(inp.ot_edges, self.jobs_at_brakes(), side="right"))
            planned = inp.days[d].month in self.sc.get("planned_saturday_months", ())
            if inp.days[d].weekday() == 4 and (planned or r.random() < inp.p_saturday[k]):
                # a planned shift is crewed; a queue-triggered one is worked as often as the record's scheduled Saturdays were, on one brake
                if planned and self.sc.get("planned_saturday_crew") == "both":
                    crew = SAT_MACHINES
                elif planned or r.random() < inp.saturday_with_time:
                    crew = (SAT_MACHINES[int(inp.days[d].isocalendar()[1]) % 2],)
                else:
                    crew = ()
                a = 24 * (d + 1) + FIRST[0]
                for mid in crew:
                    bisect.insort(mach[mid].extra, (a, a + 8.0, not planned))
                # Brake utilization counts a Saturday as the shop's calendar does: 16 scheduled hours for each Saturday called, whichever brakes
                # are crewed. Until this change it counted 8 hours for each brake crewed, which read about 1 point above the record's figure.
                self.saturday_scheduled[(inp.days[d + 1].year, inp.days[d + 1].quarter)] += 16.0
                self.overtime["saturdays"] += 1
                self.overtime["hours"] += 8.0 * len(crew)
                self.ot_log.append((inp.days[d + 1], "saturday", 8.0 * len(crew)))
            yield env.timeout(2.0)
            if r.random() < inp.p_extended[k] and inp.extended_yield >= 0.01:
                a = 24 * d + EXTENDED[0]
                for mid in SAT_MACHINES:
                    bisect.insort(mach[mid].extra, (a, a + 2.0, True))
                    mach[mid].sched_added[(inp.days[d].year, inp.days[d].quarter)] += 2.0
                self.overtime["extended_days"] += 1
                self.overtime["hours"] += 4.0
                self.ot_log.append((inp.days[d], "extended", 4.0))
            self.wake("press_brake")

    def monitor(self):
        """Jobs waiting at each work center at the end of every day."""
        env = self.env
        self.daily = []
        while True:
            yield env.timeout(24 * (int(env.now // 24) + 1) - env.now)
            row = {wc: len(v) for wc, v in self.queue.items()}
            row["t"] = env.now
            self.daily.append(row)

    # run --------------------------------------------------------------------
    def release_stream(self):
        env = self.env
        for j in self.inp.jobs.itertuples():
            t = hours(j.release_date) + 10.0
            if t > env.now:
                yield env.timeout(t - env.now)
            ops = self.inp.ops.get(j.job_id)
            if ops:
                env.process(self.job_flow(j, ops))

    def run(self, until="2026-01-31"):
        env = self.env
        for ms in self.machines.values():
            for m in ms:
                env.process(self.machine_loop(m))
        env.process(self.release_stream())
        env.process(self.nest_check())
        env.process(self.overtime_rule())
        env.process(self.monitor())
        env.run(until=hours(until))
        return self


def quarter_measures(shop):
    """Jobs shipped, on-time delivery and median lead time by quarter shipped, from one run."""
    inp = shop.inp
    r = pd.DataFrame(shop.results)
    r["ship_date"] = r["ship_ts"].dt.normalize()
    r["lead"] = [inp.W(hours(s) + 15) - inp.W(hours(a) + 10) for s, a in zip(r["ship_date"], r["release_date"])]
    r["on_time"] = r["ship_date"] <= pd.to_datetime(r["due_date"])
    g = r[r["ship_date"] >= "2024-07-01"].groupby(r["ship_date"].dt.to_period("Q")).agg(jobs_shipped=("lead", "size"), on_time_delivery=("on_time", "mean"),
                                                                                       lead_time_median=("lead", "median")).reset_index()
    g["quarter"] = g.pop("ship_date").astype(str)
    g["peak_brake_queue"] = pd.DataFrame(shop.daily)["press_brake"].max()
    return g


def customer_measures(shop):
    """Jobs shipped and jobs on time in the report year for each of the customers that make up 80% of its revenue, from one run."""
    r = pd.DataFrame(shop.results)
    r["ship_date"] = r["ship_ts"].dt.normalize()
    r["on_time"] = r["ship_date"] <= pd.to_datetime(r["due_date"])
    rows = []
    for fq, label in ((1, "year"), (2, "Q2 to Q4")):
        y = r[(r["ship_date"].dt.year == REPORT_YEAR) & (r["ship_date"].dt.quarter >= fq) & r["customer_id"].isin(shop.inp.top_customers)]
        g = y.groupby("customer_id")["on_time"].agg(jobs="size", on_time="sum").reset_index()
        rows += [dict(period=label, customer_id=c, jobs=int(n), on_time=int(k)) for c, n, k in zip(g["customer_id"], g["jobs"], g["on_time"])]
    return rows


# ── measures ────────────────────────────────────────────────────────────────
def measures(shop, first_quarter=1):
    """Lead time, WIP, utilization and on-time delivery of the report year from one run, on the same definitions as the marts."""
    inp = shop.inp
    r = pd.DataFrame(shop.results)
    r["ship_date"] = r["ship_ts"].dt.normalize()
    lt = np.array([inp.W(hours(s) + 15.0) - inp.W(hours(a) + 10.0) for s, a in zip(r["ship_date"], r["release_date"])])
    r["lead"] = lt
    r["on_time"] = r["ship_date"] <= pd.to_datetime(r["due_date"])
    y = r[(r["ship_date"].dt.year == REPORT_YEAR) & (r["ship_date"].dt.quarter >= first_quarter)]
    rel = np.sort(pd.to_datetime(inp.jobs["release_date"]).values)
    shp = np.sort(r["ship_date"].values)
    days = [d for d, f in zip(inp.days, inp.flag) if f and d.year == REPORT_YEAR and d.quarter >= first_quarter and d <= inp.cal["calendar_date"].max()]
    wip = np.mean([np.searchsorted(rel, np.datetime64(d), side="right") - np.searchsorted(shp, np.datetime64(d), side="right") for d in days])
    out = dict(jobs_shipped=len(y), lead_time_median=float(y["lead"].median()), lead_time_p90=float(y["lead"].quantile(0.9)), wip_mean=float(wip),
               on_time_delivery=float(y["on_time"].mean()))
    # late jobs, and the working days from the due date to the ship date summed over them
    late = y[~y["on_time"]]
    out["late_jobs"] = float(len(late))
    out["days_late"] = float(sum(inp.W(hours(s)) - inp.W(hours(d)) for s, d in zip(late["ship_date"], late["due_date"])))
    out["revenue_shipped"] = float(y["revenue"].sum())
    # Queue time per operation, operations started in the period: working days from the end of the job's previous operation to the start, the
    # basis of the record's queue figures (the move is inside it). Until this change it ran from arrival at the work center.
    start, end = hours(f"{REPORT_YEAR}-{3 * first_quarter - 2:02d}-01"), hours(f"{REPORT_YEAR + 1}-01-01")
    ops = [(o[0], inp.W(o[4]) - inp.W(o[7])) for o in shop.op_log if start <= o[4] < end]
    brake = [w for wc, w in ops if wc == "press_brake"]
    out["brake_queue_mean"] = float(np.mean(brake)) if brake else np.nan
    out["queue_mean_all"] = float(np.mean([w for _, w in ops])) if ops else np.nan
    # standard hours already worked on the jobs on the floor, mean over the days of the period
    day_no = np.array([(d - T0).days for d in days])
    ship_day = {x: (s - T0).days for x, s in zip(r["job_id"], r["ship_date"])}
    done = sum(o[6] * (np.searchsorted(day_no, ship_day.get(o[1], 10 ** 9), side="left") - np.searchsorted(day_no, int(o[5] // 24) + 1, side="left")) for o in shop.op_log)
    out["wip_standard_hours_worked"] = float(done / len(day_no))
    for wc, name in (("press_brake", "brake_utilization"), ("robotic_weld", "robotic_weld_utilization"), ("laser", "laser_utilization")):
        busy = sched = 0.0
        for m in shop.machines[wc]:
            if m.id == CELL:
                continue
            for (yr, qtr), h in m.busy_hours.items():
                if yr == REPORT_YEAR and qtr >= first_quarter:
                    busy += h
            for a, b, _ in m.windows:
                ts = T0 + pd.Timedelta(hours=a)
                if ts.year == REPORT_YEAR and ts.quarter >= first_quarter:
                    sched += b - a
            for (yr, qtr), h in m.sched_added.items():
                if yr == REPORT_YEAR and qtr >= first_quarter:
                    sched += h
        if wc == "press_brake":
            sched += sum(h for (yr, qtr), h in shop.saturday_scheduled.items() if yr == REPORT_YEAR and qtr >= first_quarter)
        out[name] = busy / sched
    def in_period(k):
        return k[0] == REPORT_YEAR and k[1] >= first_quarter

    brakes = shop.machines["press_brake"]
    out["brake_hours"] = float(sum(h for m in brakes if m.id != CELL for k, h in m.busy_hours.items() if in_period(k)))
    out["cell_hours"] = float(sum(h for m in brakes if m.id == CELL for k, h in m.busy_hours.items() if in_period(k)))
    out["brake_setup_hours"] = float(sum(h for m in brakes for k, h in m.setup_hours.items() if in_period(k)))
    out["b3_setup_hours"] = float(sum(h for m in brakes if m.id == "B3" for k, h in m.setup_hours.items() if in_period(k)))
    out["weld_second_shift_hours"] = float(sum(b - a for m in shop.machines["robotic_weld"] for a, b, _ in m.windows
                                               if (a % 24) >= SECOND[0] - 1e-9 and (T0 + pd.Timedelta(hours=a)).year == REPORT_YEAR
                                               and (T0 + pd.Timedelta(hours=a)).quarter >= first_quarter))
    # the three weeks from November 11, 2024: jobs waiting at the lasers at the end of each day, and delivery of the jobs released in them
    d0, d1 = hours("2024-11-11"), hours("2024-12-02")
    out["laser_queue_nov_2024"] = float(np.mean([x.get("laser", 0) for x in shop.daily if d0 < x["t"] <= d1]))
    nov = r[(pd.to_datetime(r["release_date"]) >= "2024-11-11") & (pd.to_datetime(r["release_date"]) < "2024-12-02")]
    out["on_time_released_nov_2024"] = float(nov["on_time"].mean())
    out["lead_time_released_nov_2024"] = float(nov["lead"].median())
    log = [x for x in shop.ot_log if x[0].year == REPORT_YEAR and x[0].quarter >= first_quarter]
    out["saturday_shifts"] = float(sum(1 for x in log if x[1] == "saturday"))
    out["saturday_hours"] = float(sum(x[2] for x in log if x[1] == "saturday"))                   # crewed brake hours on the Saturdays worked
    winter = [x for x in shop.ot_log if x[1] == "saturday" and pd.Timestamp(f"{REPORT_YEAR - 1}-11-01") <= x[0] < pd.Timestamp(f"{REPORT_YEAR}-03-01")]
    out["saturday_shifts_winter"], out["saturday_hours_winter"] = float(len(winter)), float(sum(x[2] for x in winter))
    out["extended_hours"] = float(sum(x[2] for x in log if x[1] == "extended"))
    if shop.gate is not None:
        out["release_hold_days"] = float(np.mean(shop.gate.held_days)) if shop.gate.held_days else 0.0
    return out
