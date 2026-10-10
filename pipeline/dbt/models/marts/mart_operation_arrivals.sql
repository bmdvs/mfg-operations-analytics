-- One row per operation after the first: when the job arrived at the work center (its first queued event after the previous
-- operation ended, or that operation's end where no event was recorded), the working days from the arrival day to the start day,
-- the work center it came from and, for the powder line, the color.
with o as (
    select q.job_id, q.op_seq, q.work_center, q.part_id, q.prev_end, q.first_start, q.queue_net_wd, q.scheduling_wait_wd
    from {{ ref('int_operation_queue') }} q
    where not q.is_first_op and q.work_center <> 'outside_processing'
),
arrive as (
    select o.job_id, o.op_seq, min(e.event_ts) as arrival_ts
    from o
    join {{ ref('stg_mes__job_status_events') }} e
      on e.job_id = o.job_id and e.status = 'queued' and e.event_ts > o.prev_end and e.event_ts <= o.first_start
    group by 1, 2
),
previous as (
    select o.job_id, o.op_seq, max(p.op_seq) as previous_op_seq
    from o
    join {{ ref('int_operation_queue') }} p on p.job_id = o.job_id and p.op_seq < o.op_seq
    group by 1, 2
),
routing as (
    select job_id, max((work_center = 'robotic_weld')::int) = 1 as has_robotic_weld, max((work_center = 'weld')::int) = 1 as has_manual_weld
    from {{ ref('int_operation_queue') }}
    group by 1
)
select
    {{ batch_id() }} as export_batch_id,
    o.job_id, o.op_seq, o.work_center, year(o.first_start) as start_year, quarter(o.first_start) as start_quarter,
    cast(date_trunc('week', o.first_start) as date) as week_start,
    coalesce(a.arrival_ts, o.prev_end) as arrival_ts, a.arrival_ts is not null as arrival_recorded,
    cast(date_trunc('week', coalesce(a.arrival_ts, o.prev_end)) as date) as arrival_week,
    hour(coalesce(a.arrival_ts, o.prev_end)) + minute(coalesce(a.arrival_ts, o.prev_end)) / 60.0 as arrival_hour,
    o.first_start, greatest(cs.wd_index - ca.wd_index, 0) as working_days_to_start,
    o.queue_net_wd, o.scheduling_wait_wd,
    pw.work_center as previous_work_center, r.has_robotic_weld, r.has_manual_weld,
    case when o.work_center = 'powder_coat' then pt.powder_color end as powder_color,
    l.ship_date
from o
left join arrive a using (job_id, op_seq)
left join previous p using (job_id, op_seq)
left join {{ ref('int_operation_queue') }} pw on pw.job_id = o.job_id and pw.op_seq = p.previous_op_seq
left join routing r using (job_id)
left join {{ ref('stg_erp__parts') }} pt on pt.part_id = o.part_id
left join {{ ref('int_job_lead_time') }} l using (job_id)
left join {{ ref('int_working_days') }} ca on ca.calendar_date = cast(coalesce(a.arrival_ts, o.prev_end) as date)
left join {{ ref('int_working_days') }} cs on cs.calendar_date = cast(o.first_start as date)
