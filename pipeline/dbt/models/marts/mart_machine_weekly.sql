-- Machine time, downtime and queue per machine and week. Scheduled hours are the crewed weekday shifts; Saturday and extended hours are apart.
with weeks as (
    select work_center, cast(date_trunc('week', calendar_date) as date) as week_start,
        count(distinct calendar_date) filter (where dayofweek(calendar_date) between 1 and 5) as weekdays
    from {{ ref('stg_erp__work_center_calendar') }}
    group by 1, 2
),
mt as (
    select machine_id, cast(date_trunc('week', start_ts) as date) as week_start, sum(hours) as machine_hours,
        sum(hours) filter (where dayofweek(start_ts) = 6) as saturday_hours
    from {{ ref('int_machine_time') }}
    group by 1, 2
),
dt as (
    select machine_id, cast(date_trunc('week', start_ts) as date) as week_start, sum(epoch(end_ts - start_ts)) / 3600.0 as downtime_hours
    from {{ ref('stg_maintenance__downtime_events') }}
    group by 1, 2
),
qm as (
    select machine_id, week_start, count(*) as operations, avg(queue_net_wd) as queue_mean
    from {{ ref('mart_operations') }}
    where not is_first_op
    group by 1, 2
)
select
    {{ batch_id() }} as export_batch_id,
    s.machine_id, s.work_center, s.crewed_shifts, w.week_start, year(w.week_start + 3) as week_year, quarter(w.week_start + 3) as week_quarter, w.weekdays,
    w.weekdays * 8 * s.crewed_shifts as scheduled_hours,
    coalesce(mt.machine_hours, 0) as machine_hours, coalesce(mt.saturday_hours, 0) as saturday_hours, coalesce(dt.downtime_hours, 0) as downtime_hours,
    qm.operations, qm.queue_mean
from {{ ref('int_machine_shifts') }} s
join weeks w using (work_center)
left join mt on mt.machine_id = s.machine_id and mt.week_start = w.week_start
left join dt on dt.machine_id = s.machine_id and dt.week_start = w.week_start
left join qm on qm.machine_id = s.machine_id and qm.week_start = w.week_start
