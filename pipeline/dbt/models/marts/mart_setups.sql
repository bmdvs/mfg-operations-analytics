-- Setups with their context, one row per operation with a setup.
select {{ batch_id() }} as export_batch_id, s.*,
    year(s.setup_start) as setup_year, quarter(s.setup_start) as setup_quarter,
    case when s.qty < 25 then 'under 25' when s.qty < 100 then '25 to 99' else '100 and over' end as lot_band,
    l.routing_class, l.rush_flag
from {{ ref('int_setups') }} s
left join {{ ref('int_job_lead_time') }} l using (job_id)
