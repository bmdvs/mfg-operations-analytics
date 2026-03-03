-- Run and setup hours against standard per operation, with the part's standard date and whether it was set at first quote and never revised.
select
    {{ batch_id() }} as export_batch_id,
    o.job_id, o.op_seq, o.work_center, o.machine_id, o.start_year, o.start_quarter, o.qty, o.family, o.routing_class,
    o.setup_hours, o.setup_std, o.run_hours, o.run_std_hours,
    j.part_id, r.standard_set_date, p.first_quoted_date, p.active,
    r.standard_set_date is not null as has_routing,
    r.standard_set_date is not null and r.standard_set_date = p.first_quoted_date as stale_standard
from {{ ref('mart_operations') }} o
join {{ ref('stg_erp__jobs') }} j using (job_id)
left join {{ ref('stg_erp__parts') }} p on p.part_id = j.part_id
left join {{ ref('stg_erp__routings') }} r on r.part_id = j.part_id and r.op_seq = o.op_seq and r.work_center = o.work_center
