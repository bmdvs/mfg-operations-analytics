-- Candidate leading indicators by week (Monday start) beside on-time delivery by ship week.
with weeks as (
    select week_start, weekdays, jobs_shipped, on_time_delivery, releases, brake_std_hours_released, wip_at_laser, wip_at_brakes,
        brake_utilization, brake_extended_hours
    from {{ ref('mart_weekly_floor') }}
),
ops as (
    select jo.job_id, jo.op_seq, jo.work_center, o.machine_id, o.first_start, jo.planned_start,
        cast(jo.planned_start as date) < j.release_date as planned_before_release
    from {{ ref('stg_erp__job_operations') }} jo
    join {{ ref('stg_erp__jobs') }} j using (job_id)
    left join {{ ref('mart_operations') }} o using (job_id, op_seq)
    where jo.work_center <> 'outside_processing'
),
-- operations planned to start in the week that had started by the planned date; an operation planned before its job's release
-- cannot start on time and is counted apart
on_time_start as (
    select cast(date_trunc('week', planned_start) as date) as week_start,
        count(*) filter (where not planned_before_release) as operations_planned,
        count(*) filter (where planned_before_release) as operations_planned_before_release,
        avg((first_start is not null and cast(first_start as date) <= cast(planned_start as date))::int)
            filter (where not planned_before_release) as on_time_start_rate,
        avg((first_start is not null and cast(first_start as date) <= cast(planned_start as date))::int) as on_time_start_rate_all_operations
    from ops
    group by 1
),
-- operations started in the week in the planned order: planned start no earlier than that of the operation the machine started before it
adherence as (
    select cast(date_trunc('week', first_start) as date) as week_start, avg((planned_start >= previous_planned_start)::int) as schedule_adherence
    from (
        select first_start, planned_start, lag(planned_start) over (partition by machine_id order by first_start) as previous_planned_start
        from ops
        where first_start is not null
    )
    where previous_planned_start is not null
    group by 1
),
setups as (
    select cast(date_trunc('week', setup_start) as date) as week_start, sum(setup_std) / sum(setup_hours) as brake_setup_efficiency
    from {{ ref('mart_setups') }}
    where work_center = 'press_brake' and setup_hours > 0
    group by 1
),
overtime as (
    select week_start, sum(labor_hours) as overtime_labor_hours
    from {{ ref('mart_overtime_hours') }}
    where work_center = 'press_brake'
    group by 1
),
outside as (
    select cast(date_trunc('week', received_date) as date) as week_start, count(*) as outside_lines_received,
        avg((received_date <= promised_date)::int) as outside_receipt_on_time
    from {{ ref('stg_erp__po_lines') }}
    where line_type = 'outside processing' and received_date is not null
    group by 1
),
kits as (
    select cast(date_trunc('week', kit_check_date) as date) as week_start, count(*) as kit_checks, avg((kit_result = 'complete')::int) as kit_complete_rate
    from {{ ref('mart_job_release_conditions') }}
    where kit_result is not null
    group by 1
),
release as (
    select release_week as week_start, avg(brake_backlog_days) as brake_backlog_days_at_release,
        avg(promised_inside_standard::int) as promised_inside_standard_share
    from {{ ref('mart_job_release_conditions') }}
    group by 1
)
select
    {{ batch_id() }} as export_batch_id,
    w.week_start, w.weekdays, w.jobs_shipped, w.on_time_delivery,
    s.on_time_start_rate, s.on_time_start_rate_all_operations, s.operations_planned, s.operations_planned_before_release,
    e.brake_setup_efficiency, a.schedule_adherence,
    coalesce(v.overtime_labor_hours, 0) as brake_overtime_labor_hours,
    o.outside_receipt_on_time, o.outside_lines_received, k.kit_complete_rate, k.kit_checks,
    r.brake_backlog_days_at_release, r.promised_inside_standard_share,
    w.releases, w.brake_std_hours_released, w.wip_at_laser, w.wip_at_brakes, w.brake_utilization
from weeks w
left join on_time_start s using (week_start)
left join adherence a using (week_start)
left join setups e using (week_start)
left join overtime v using (week_start)
left join outside o using (week_start)
left join kits k using (week_start)
left join release r using (week_start)
