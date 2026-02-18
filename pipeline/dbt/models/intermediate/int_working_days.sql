-- Working-day clock: every day a work center is scheduled, scheduled Saturdays included. Outside the calendar range, weekdays.
with cal as (
    select distinct calendar_date from {{ ref('stg_erp__work_center_calendar') }}
),
bounds as (
    select min(calendar_date) as lo, max(calendar_date) as hi from cal
),
spine as (
    select cast(d as date) as calendar_date
    from generate_series(date '2022-01-03', date '2027-12-31', interval 1 day) as t(d)
),
flagged as (
    select
        s.calendar_date,
        case when s.calendar_date between b.lo and b.hi then c.calendar_date is not null
             else dayofweek(s.calendar_date) between 1 and 5 end as is_working_day
    from spine s
    cross join bounds b
    left join cal c on c.calendar_date = s.calendar_date
)
select
    calendar_date,
    is_working_day,
    coalesce(sum(is_working_day::int) over (order by calendar_date rows between unbounded preceding and 1 preceding), 0) as wd_index
from flagged
