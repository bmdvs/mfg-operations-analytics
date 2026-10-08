-- Operation sequence per job with queue time: first start of the operation less last end of the previous operation, in working days.
-- The wait of the first operation is release to first start. The powder scheduling wait (to the next scheduled day of the color) is split out.
with outside as (
    select job_id, op_seq, 'outside_processing' as work_center,
        cast(order_date as timestamp) + interval 8 hour as first_start,
        cast(received_date as timestamp) + interval 11 hour as last_end
    from {{ ref('stg_erp__po_lines') }}
    where line_type = 'outside processing' and op_seq is not null
),
actual as (
    select job_id, op_seq, work_center, first_start, last_end from {{ ref('int_operation_actuals') }}
    union all
    select job_id, op_seq, work_center, first_start, last_end from outside
),
seq as (
    select
        jo.job_id, jo.op_seq, jo.work_center, a.first_start, a.last_end,
        j.release_date, j.part_id,
        coalesce(lag(a.last_end) over (partition by jo.job_id order by jo.op_seq), cast(j.release_date as timestamp) + interval 10 hour) as prev_end,
        jo.op_seq = min(jo.op_seq) over (partition by jo.job_id) as is_first_op
    from {{ ref('stg_erp__job_operations') }} jo
    join {{ ref('stg_erp__jobs') }} j using (job_id)
    left join actual a on a.job_id = jo.job_id and a.op_seq = jo.op_seq and a.work_center = jo.work_center
),
started as (
    select * from seq where first_start is not null
),
color_day as (
    -- first scheduled day of the powder color on or after the day the job reached the line
    select s.job_id, s.op_seq, min(c.schedule_date) as color_date
    from started s
    join {{ ref('stg_erp__parts') }} p using (part_id)
    join {{ ref('stg_mes__powder_color_schedule') }} c on c.color = p.powder_color and c.schedule_date >= cast(s.prev_end as date)
    where s.work_center = 'powder_coat'
    group by 1, 2
),
clocked as (
    select
        s.*,
        greatest(s.prev_end, cast(cd.color_date as timestamp) + interval 6 hour) as color_ready,
        {{ wd('s.prev_end', 'c1') }} as prev_end_wd,
        {{ wd('s.first_start', 'c2') }} as first_start_wd,
        {{ wd('s.last_end', 'c4') }} as last_end_wd
    from started s
    left join color_day cd using (job_id, op_seq)
    left join {{ ref('int_working_days') }} c1 on c1.calendar_date = cast(s.prev_end as date)
    left join {{ ref('int_working_days') }} c2 on c2.calendar_date = cast(s.first_start as date)
    left join {{ ref('int_working_days') }} c4 on c4.calendar_date = cast(s.last_end as date)
),
waits as (
    select
        k.*,
        greatest(first_start_wd - prev_end_wd, 0) as queue_wd,
        case when k.color_ready is null then 0 else {{ wd('k.color_ready', 'c3') }} - prev_end_wd end as scheduling_wait_wd
    from clocked k
    left join {{ ref('int_working_days') }} c3 on c3.calendar_date = cast(k.color_ready as date)
)
select
    job_id, op_seq, work_center, part_id, is_first_op, prev_end, first_start, last_end,
    prev_end_wd, first_start_wd, last_end_wd,
    queue_wd,
    scheduling_wait_wd,
    greatest(queue_wd - scheduling_wait_wd, 0) as queue_net_wd,
    greatest(last_end_wd - first_start_wd, 0) as processing_wd
from waits
