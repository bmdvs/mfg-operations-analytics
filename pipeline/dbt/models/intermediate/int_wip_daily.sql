-- WIP per working day and location: jobs released and not shipped at the end of the day, placed at the work center
-- of the operation they are waiting for or running. A job released on the day counts; a job shipped on the day does not.
with outside as (
    select job_id, op_seq,
        cast(order_date as timestamp) + interval 8 hour as first_start,
        cast(received_date as timestamp) + interval 11 hour as last_end
    from {{ ref('stg_erp__po_lines') }}
    where line_type = 'outside processing' and op_seq is not null
),
actual as (
    select job_id, op_seq, first_start, last_end from {{ ref('int_operation_actuals') }}
    union all
    select job_id, op_seq, first_start, last_end from outside
),
seq as (
    select
        jo.job_id, jo.op_seq, jo.work_center, a.last_end,
        lag(a.last_end) over (partition by jo.job_id order by jo.op_seq) as prev_end,
        row_number() over (partition by jo.job_id order by jo.op_seq) as op_no
    from {{ ref('stg_erp__job_operations') }} jo
    left join actual a on a.job_id = jo.job_id and a.op_seq = jo.op_seq
),
spans as (
    -- at a work center from the end of the previous operation (or release) until this operation ends
    select s.job_id, s.work_center as location,
        case when s.op_no = 1 then cast(j.release_date as timestamp) else s.prev_end end as from_ts,
        coalesce(s.last_end, timestamp '2099-12-31') as to_ts
    from seq s
    join {{ ref('stg_erp__jobs') }} j using (job_id)
    where s.op_no = 1 or s.prev_end is not null
    union all
    select s.job_id, 'complete, not shipped', max(s.last_end), timestamp '2099-12-31'
    from seq s
    group by s.job_id
    having count(*) = count(s.last_end)
),
days as (
    select calendar_date, cast(calendar_date as timestamp) + interval 1 day as sample_ts
    from {{ ref('int_working_days') }}
    where is_working_day
      and calendar_date between (select min(calendar_date) from {{ ref('stg_erp__work_center_calendar') }})
                            and (select max(calendar_date) from {{ ref('stg_erp__work_center_calendar') }})
),
open_jobs as (
    select d.calendar_date, d.sample_ts, j.job_id
    from days d
    join {{ ref('stg_erp__jobs') }} j on j.release_date <= d.calendar_date and (j.ship_date is null or j.ship_date > d.calendar_date)
),
placed as (
    select o.calendar_date, o.job_id, s.location
    from open_jobs o
    left join spans s on s.job_id = o.job_id and s.from_ts < o.sample_ts and s.to_ts >= o.sample_ts
    qualify row_number() over (partition by o.calendar_date, o.job_id order by s.from_ts desc) = 1
)
select calendar_date, coalesce(location, 'not placed') as location, count(*) as jobs
from placed
group by 1, 2
