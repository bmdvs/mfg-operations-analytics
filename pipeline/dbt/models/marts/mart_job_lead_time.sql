-- One row per shipped job: routing class, quoted lead time, lead time and delivery against the promise.
select
    {{ batch_id() }} as export_batch_id,
    l.job_id, l.customer_id, c.key_account, c.required_otd_pct, l.part_id, l.family, l.qty, l.routing_class, l.quoted_lead_days, l.rush_flag,
    l.release_date, l.due_date, l.ship_date, l.on_time, l.days_late, l.lead_time_wd, l.wip_days, l.promised_lead_wd
from {{ ref('int_job_lead_time') }} l
left join {{ ref('stg_erp__customers') }} c using (customer_id)
where l.ship_date is not null
