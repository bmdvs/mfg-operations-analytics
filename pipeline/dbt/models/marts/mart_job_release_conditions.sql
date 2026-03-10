-- One row per job: the brake backlog on the release date at 10:00, the promise against the standard lead time, and the kit check.
-- Brake backlog is the standard hours of brake operations waiting (previous operation ended, brake operation not started), at the brakes'
-- actual-over-standard ratio, in days of crewed brake capacity.
with brake_ops as (
    select q.job_id, q.op_seq, q.prev_end, coalesce(q.first_start, timestamp '2099-12-31') as first_start,
        jo.setup_std + jo.run_std * jo.qty as std_hours
    from {{ ref('int_operation_queue') }} q
    join {{ ref('stg_erp__job_operations') }} jo using (job_id, op_seq)
    where q.work_center = 'press_brake' and q.prev_end is not null
),
ratio as (
    select sum(setup_hours + run_hours) / sum(setup_std + run_std_hours) as actual_over_standard
    from {{ ref('mart_operations') }}
    where work_center = 'press_brake'
),
capacity as (
    select sum(crewed_shifts) * 8.0 as daily_hours from {{ ref('int_machine_shifts') }} where work_center = 'press_brake'
),
backlog as (
    select j.job_id, count(b.job_id) as brake_jobs_waiting, coalesce(sum(b.std_hours), 0) as brake_std_hours_waiting
    from {{ ref('int_job_lead_time') }} j
    left join brake_ops b on b.prev_end <= j.release_ts and b.first_start > j.release_ts
    group by 1
)
select
    {{ batch_id() }} as export_batch_id,
    j.job_id, j.release_date, cast(date_trunc('week', j.release_date) as date) as release_week, j.ship_date, j.routing_class, j.family, j.rush_flag,
    j.quoted_lead_days, j.promised_lead_wd, j.promised_lead_wd < j.quoted_lead_days as promised_inside_standard,
    j.on_time, j.days_late,
    b.brake_jobs_waiting, b.brake_std_hours_waiting,
    b.brake_std_hours_waiting * r.actual_over_standard / c.daily_hours as brake_backlog_days,
    k.result as kit_result, k.check_date as kit_check_date
from {{ ref('int_job_lead_time') }} j
join backlog b using (job_id)
cross join ratio r
cross join capacity c
left join {{ ref('stg_mes__kit_checks') }} k using (job_id)
