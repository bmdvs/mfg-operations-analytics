-- The floor by week: releases, shipments, on-time delivery, WIP in total and at the laser and the brakes, and laser and brake utilization.
with weeks as (
    select distinct week_start, weekdays from {{ ref('int_utilization_weekly') }} where work_center = 'press_brake'
),
rel as (
    select cast(date_trunc('week', j.release_date) as date) as week_start, count(*) as releases, sum(b.hours) as brake_std_hours_released
    from {{ ref('stg_erp__jobs') }} j
    left join (
        select job_id, sum(setup_std + run_std * qty) as hours
        from {{ ref('stg_erp__job_operations') }}
        where work_center = 'press_brake'
        group by 1
    ) b using (job_id)
    group by 1
),
shp as (
    select cast(date_trunc('week', ship_date) as date) as week_start, count(*) as jobs_shipped, avg(on_time::int) as on_time_delivery,
        median(lead_time_wd) as lead_time_median
    from {{ ref('int_job_lead_time') }}
    where ship_date is not null
    group by 1
),
wip as (
    select cast(date_trunc('week', calendar_date) as date) as week_start,
        avg(total) as wip_mean, avg(at_laser) as wip_at_laser, avg(at_brakes) as wip_at_brakes, max(total) as wip_peak
    from (
        select calendar_date, sum(jobs) as total,
            coalesce(sum(jobs) filter (where location = 'laser'), 0) as at_laser,
            coalesce(sum(jobs) filter (where location = 'press_brake'), 0) as at_brakes
        from {{ ref('int_wip_daily') }}
        group by 1
    )
    group by 1
),
util as (
    select week_start,
        max(utilization) filter (where work_center = 'laser') as laser_utilization,
        max(utilization) filter (where work_center = 'press_brake') as brake_utilization,
        max(saturday_shifts) filter (where work_center = 'press_brake') as brake_saturday_shifts,
        max(extended_hours) filter (where work_center = 'press_brake') as brake_extended_hours,
        max(downtime_hours) filter (where work_center = 'press_brake') as brake_downtime_hours
    from {{ ref('int_utilization_weekly') }}
    group by 1
),
bq as (
    select cast(date_trunc('week', first_start) as date) as week_start, avg(queue_wd) as brake_queue_days
    from {{ ref('int_operation_queue') }}
    where work_center = 'press_brake'
    group by 1
)
select
    {{ batch_id() }} as export_batch_id,
    w.week_start, w.weekdays,
    coalesce(r.releases, 0) as releases, r.brake_std_hours_released,
    coalesce(s.jobs_shipped, 0) as jobs_shipped, s.on_time_delivery, s.lead_time_median,
    p.wip_mean, p.wip_peak, p.wip_at_laser, p.wip_at_brakes,
    u.laser_utilization, u.brake_utilization, u.brake_saturday_shifts, u.brake_extended_hours, u.brake_downtime_hours,
    q.brake_queue_days
from weeks w
left join rel r using (week_start)
left join shp s using (week_start)
left join wip p using (week_start)
left join util u using (week_start)
left join bq q using (week_start)
