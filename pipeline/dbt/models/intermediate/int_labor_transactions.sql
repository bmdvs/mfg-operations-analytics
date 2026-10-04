-- Labor transactions with auto-closed clock-offs set to the median hours of operator-closed transactions of the same work center and type.
with l as (
    select *, epoch(end_ts - start_ts) / 3600.0 as clocked_hours
    from {{ ref('stg_mes__labor_transactions') }}
),
med as (
    select work_center, labor_type, median(clocked_hours) as median_hours
    from l
    where clock_off = 'operator'
    group by 1, 2
),
adj as (
    select
        l.*,
        case when l.clock_off = 'auto' then least(l.clocked_hours, coalesce(m.median_hours, l.clocked_hours)) else l.clocked_hours end as hours
    from l
    left join med m on m.work_center = l.work_center and m.labor_type = l.labor_type
)
select
    transaction_id, job_id, op_seq, employee_id, labor_type, work_center, machine_id, clock_off, qty_complete, qty_scrap,
    start_ts,
    case when clock_off = 'auto'
         then date_trunc('minute', start_ts + to_microseconds(cast(round(hours * 3600e6) as bigint)) + interval 30 second)
         else end_ts end as end_ts,
    hours
from adj
