-- Utilization, uptime and queue per work center and week. Queue is per operation started in the week: operations after the first,
-- less the powder scheduling wait; for first operations (laser and punch), traveler print to first cut less material wait.
with q as (
    select work_center, cast(date_trunc('week', first_start) as date) as week_start, queue_net_wd as queue_days, scheduling_wait_wd
    from {{ ref('int_operation_queue') }}
    where not is_first_op and work_center <> 'outside_processing'
    union all
    select s.work_center, cast(date_trunc('week', o.first_start) as date), s.days, 0
    from {{ ref('int_job_stage_days') }} s
    join {{ ref('int_operation_queue') }} o using (job_id, op_seq)
    where s.stage = 'first-operation queue'
),
qw as (
    select work_center, week_start, count(*) as operations, avg(queue_days) as queue_mean, median(queue_days) as queue_median,
        quantile_cont(queue_days, 0.9) as queue_p90, avg(scheduling_wait_wd) as scheduling_wait_mean
    from q
    group by 1, 2
),
machines as (
    select work_center, max(machines) as machines from {{ ref('stg_erp__work_center_calendar') }} group by 1
)
select
    {{ batch_id() }} as export_batch_id,
    u.work_center, u.week_start, year(u.week_start + 3) as week_year, quarter(u.week_start + 3) as week_quarter, u.weekdays,
    m.machines, u.scheduled_hours, u.machine_hours, u.downtime_hours, u.saturday_shifts, u.extended_hours, u.utilization, u.uptime,
    qw.operations, qw.queue_mean, qw.queue_median, qw.queue_p90, qw.scheduling_wait_mean
from {{ ref('int_utilization_weekly') }} u
left join qw using (work_center, week_start)
left join machines m using (work_center)
