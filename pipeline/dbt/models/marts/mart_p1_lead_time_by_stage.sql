-- Lead time by stage for jobs shipped in the report year, whole and for the second to fourth quarters:
-- all jobs, on-time jobs and late jobs. Mean working days per job.
with jobs as (
    select job_id, on_time, lead_time_wd, quarter(ship_date) as ship_quarter
    from {{ ref('int_job_lead_time') }}
    where year(ship_date) = {{ var('report_year') }}
),
periods as (
    select 'year' as period, * from jobs
    union all
    select 'Q2 to Q4', * from jobs where ship_quarter >= 2
),
classes as (
    select period, job_id, 'all' as job_class, lead_time_wd from periods
    union all
    select period, job_id, case when on_time then 'on time' else 'late' end, lead_time_wd from periods
),
totals as (
    select period, job_class, count(*) as jobs, avg(lead_time_wd) as lead_time_mean, median(lead_time_wd) as lead_time_median
    from classes
    group by 1, 2
),
staged as (
    select c.period, c.job_class,
        case when s.stage = 'queue' then 'queue: ' || replace(s.work_center, '_', ' ') else s.stage end as stage,
        sum(s.days) as days
    from classes c
    join {{ ref('int_job_stage_days') }} s using (job_id)
    group by 1, 2, 3
)
select
    {{ batch_id() }} as export_batch_id,
    s.period, s.job_class, s.stage,
    -- stages in routing order
    case
        when s.stage = 'release to traveler print' then 1
        when s.stage = 'first-operation queue' then 2
        when s.stage = 'material wait at first operation' then 3
        when s.stage = 'queue: press brake' then 5
        when s.stage = 'queue: hardware' then 6
        when s.stage = 'queue: weld' then 7
        when s.stage = 'queue: robotic weld' then 8
        when s.stage = 'queue: grind deburr' then 9
        when s.stage = 'powder scheduling wait' then 10
        when s.stage = 'queue: powder coat' then 11
        when s.stage = 'queue: assembly' then 12
        when s.stage = 'queue: inspection pack' then 13
        when s.stage = 'setup and run' then 14
        when s.stage = 'move' then 15
        when s.stage like 'hold:%' then 16
        when s.stage = 'outside processing' then 17
        when s.stage = 'complete to ship' then 18
        else 4
    end as stage_order,
    t.jobs,
    s.days / t.jobs as mean_days,
    s.days / (t.jobs * t.lead_time_mean) as share_of_lead_time,
    t.lead_time_mean, t.lead_time_median
from staged s
join totals t using (period, job_class)
