-- Scheduled and absent employee-days per day and shift.
select
    {{ batch_id() }} as export_batch_id,
    a.work_date, e.shift, count(*) as scheduled, sum((not a.present)::int) as absent
from {{ ref('stg_hr__attendance') }} a
join {{ ref('stg_hr__employees') }} e using (employee_id)
where a.scheduled_hours > 0
group by 2, 3
