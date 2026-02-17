-- On-time delivery and lead time by quarter shipped.
select
    {{ batch_id() }} as export_batch_id,
    cast(date_trunc('quarter', ship_date) as date) as quarter_start,
    count(*) as jobs_shipped,
    count(*) filter (where not on_time) as late_jobs,
    avg(on_time::int) as on_time_delivery,
    median(lead_time_wd) as lead_time_median,
    quantile_cont(lead_time_wd, 0.9) as lead_time_p90
from {{ ref('int_job_lead_time') }}
where ship_date >= (select period_start from {{ ref('stg_erp__export_batch') }})
group by 2
