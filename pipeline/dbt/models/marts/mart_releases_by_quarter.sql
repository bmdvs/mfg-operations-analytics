-- Jobs and standard hours released by calendar quarter.
with hours as (
    select job_id,
        sum(setup_std + run_std * qty) filter (where work_center = 'press_brake') as brake_std_hours,
        sum(setup_std + run_std * qty) filter (where work_center = 'laser') as laser_std_hours
    from {{ ref('stg_erp__job_operations') }}
    group by 1
)
select
    {{ batch_id() }} as export_batch_id,
    cast(date_trunc('quarter', j.release_date) as date) as quarter_start,
    count(*) as releases,
    sum(h.brake_std_hours) as brake_std_hours,
    sum(h.laser_std_hours) as laser_std_hours
from {{ ref('stg_erp__jobs') }} j
left join hours h using (job_id)
where j.release_date >= (select period_start from {{ ref('stg_erp__export_batch') }})
group by 2
