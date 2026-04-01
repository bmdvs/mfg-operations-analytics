-- Lead time against the quoted lead time by routing class, jobs shipped in the report year, whole and for the second to fourth quarters.
with jobs as (
    select * from {{ ref('int_job_lead_time') }} where year(ship_date) = {{ var('report_year') }}
),
periods as (
    select 'year' as period, * from jobs
    union all
    select 'Q2 to Q4', * from jobs where quarter(ship_date) >= 2
),
classes as (
    select 'all' as class, * from periods
    union all
    select routing_class as class, * from periods
)
select
    {{ batch_id() }} as export_batch_id,
    period,
    class as routing_class,
    count(*) as jobs,
    avg(quoted_lead_days) as quoted_lead_days,
    median(lead_time_wd) as lead_time_median,
    avg(lead_time_wd) as lead_time_mean,
    quantile_cont(lead_time_wd, 0.8) as lead_time_p80,
    quantile_cont(lead_time_wd, 0.9) as lead_time_p90,
    avg((wip_days <= quoted_lead_days)::int) as share_within_quoted,
    avg(on_time::int) as on_time_delivery,
    count(*) filter (where not on_time) as late_jobs,
    median(lead_time_wd) filter (where on_time) as lead_time_median_on_time,
    median(lead_time_wd) filter (where not on_time) as lead_time_median_late
from classes
group by period, class
