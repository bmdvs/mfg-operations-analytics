-- Lost days of late jobs by stage, cause and work center. Days at a stage are placed at the work centers where the job spent them.
with a as (
    select * from {{ ref('int_late_job_attribution') }}
),
stage_wc as (
    select job_id,
        case when stage = 'queue' then 'queue: ' || replace(work_center, '_', ' ') else stage end as stage,
        coalesce(work_center, 'shipping') as work_center,
        sum(days) as days
    from {{ ref('int_job_stage_days') }}
    group by 1, 2, 3
),
shares as (
    select job_id, stage, work_center, days / nullif(sum(days) over (partition by job_id, stage), 0) as share
    from stage_wc
    where days > 0
),
placed as (
    select a.job_id, a.stage, a.cause,
        coalesce(s.work_center, case when a.cause = 'released late' then 'order entry' else 'none' end) as work_center,
        a.lost_days * coalesce(s.share, 1) as lost_days,
        a.attributed_days * coalesce(s.share, 1) as attributed_days
    from a
    left join shares s on s.job_id = a.job_id and s.stage = a.stage
)
select
    {{ batch_id() }} as export_batch_id,
    p.job_id, l.customer_id, l.routing_class, l.ship_date, year(l.ship_date) as ship_year, quarter(l.ship_date) as ship_quarter, l.days_late,
    p.stage, p.cause, p.work_center, p.lost_days, p.attributed_days
from placed p
join {{ ref('int_job_lead_time') }} l using (job_id)
