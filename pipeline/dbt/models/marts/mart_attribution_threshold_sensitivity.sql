-- Constraint-queue and not-attributable lost days with the constraint rule set at the 70th, 80th and 90th queue percentile.
-- The 80th percentile is the rule; the other two show how much of the not-attributable share is queue between the thresholds.
with runs as (
    select 70 as queue_percentile, * from ({{ late_job_attribution(0.7) }})
    union all
    select 80, * from ({{ late_job_attribution(0.8) }})
    union all
    select 90, * from ({{ late_job_attribution(0.9) }})
),
dated as (
    select r.*, year(l.ship_date) as ship_year, quarter(l.ship_date) as ship_quarter
    from runs r
    join {{ ref('int_job_lead_time') }} l using (job_id)
    where year(l.ship_date) = {{ var('report_year') }}
),
periods as (
    select 'year' as period, * from dated
    union all
    select 'Q2 to Q4', * from dated where ship_quarter >= 2
)
select
    {{ batch_id() }} as export_batch_id,
    period, queue_percentile, cause,
    sum(attributed_days) as lost_days,
    sum(attributed_days) / sum(sum(attributed_days)) over (partition by period, queue_percentile) as share_of_lost_days,
    count(distinct job_id) as late_jobs
from periods
group by period, queue_percentile, cause
