-- Utilization per work center and week: machine time over scheduled hours net of downtime.
with weeks as (
    select work_center, cast(date_trunc('week', calendar_date) as date) as week_start,
        sum(scheduled_hours) as scheduled_hours,
        count(distinct calendar_date) filter (where dayofweek(calendar_date) between 1 and 5) as weekdays,
        sum(saturday::int) as saturday_shifts,
        sum(extended_hours) as extended_hours
    from {{ ref('stg_erp__work_center_calendar') }}
    group by 1, 2
),
machine as (
    select work_center, cast(date_trunc('week', start_ts) as date) as week_start, sum(hours) as machine_hours
    from {{ ref('int_machine_time') }}
    group by 1, 2
),
down as (
    select work_center, cast(date_trunc('week', start_ts) as date) as week_start, sum(epoch(end_ts - start_ts)) / 3600.0 as downtime_hours
    from {{ ref('stg_maintenance__downtime_events') }}
    group by 1, 2
)
select
    w.work_center, w.week_start, w.weekdays, w.scheduled_hours, w.saturday_shifts, w.extended_hours,
    coalesce(m.machine_hours, 0) as machine_hours,
    coalesce(d.downtime_hours, 0) as downtime_hours,
    coalesce(m.machine_hours, 0) / nullif(w.scheduled_hours - coalesce(d.downtime_hours, 0), 0) as utilization,
    1 - coalesce(d.downtime_hours, 0) / nullif(w.scheduled_hours, 0) as uptime
from weeks w
left join machine m using (work_center, week_start)
left join down d using (work_center, week_start)
