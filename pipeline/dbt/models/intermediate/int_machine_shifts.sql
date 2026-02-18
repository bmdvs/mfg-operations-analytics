-- Crewed shifts per machine: a machine is crewed on second shift when it has labor starting at or after 14:00 on more than half of its working weekdays.
with days as (
    select machine_id, work_center, cast(start_ts as date) as d, max((hour(start_ts) >= 14)::int) as second_shift
    from {{ ref('int_labor_transactions') }}
    where dayofweek(start_ts) between 1 and 5
    group by 1, 2, 3
)
select machine_id, work_center, avg(second_shift) as second_shift_share, case when avg(second_shift) > 0.5 then 2 else 1 end as crewed_shifts
from days
group by 1, 2
