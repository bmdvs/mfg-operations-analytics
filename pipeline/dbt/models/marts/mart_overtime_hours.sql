-- Labor hours worked on Saturdays (every work center) and after 22:00 at the brakes on days with an extended second shift in the calendar,
-- by week, work center, part family and rush flag.
with t as (
    select t.job_id, t.work_center, t.start_ts, dayofweek(t.start_ts) = 6 as saturday, t.hours,
        greatest(epoch(t.end_ts - greatest(t.start_ts, cast(cast(t.start_ts as date) as timestamp) + interval 22 hour)) / 3600.0, 0) as hours_after_22
    from {{ ref('int_labor_transactions') }} t
),
o as (
    select job_id, work_center, start_ts, 'Saturday shift' as overtime_type, hours as labor_hours from t where saturday
    union all
    select t.job_id, t.work_center, t.start_ts, 'extended shift', t.hours_after_22
    from t
    join {{ ref('stg_erp__work_center_calendar') }} c on c.work_center = t.work_center and c.calendar_date = cast(t.start_ts as date)
    where not t.saturday and t.work_center = 'press_brake' and t.hours_after_22 > 0 and c.extended_hours > 0
)
select
    {{ batch_id() }} as export_batch_id,
    cast(date_trunc('week', o.start_ts) as date) as week_start,
    o.work_center, o.overtime_type, j.family, j.rush_flag,
    sum(o.labor_hours) as labor_hours,
    count(distinct o.job_id) as jobs
from o
join {{ ref('int_job_lead_time') }} j using (job_id)
group by all
