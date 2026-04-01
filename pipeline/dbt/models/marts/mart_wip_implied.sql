-- Floor WIP in the report year against the WIP the quoted lead times imply at measured throughput, whole and for the second
-- to fourth quarters. One clock: WIP is sampled and throughput counted on every working day, scheduled Saturdays included.
with days as (
    select calendar_date, sum(jobs) as wip
    from {{ ref('int_wip_daily') }}
    where year(calendar_date) = {{ var('report_year') }}
    group by 1
),
jobs as (
    select ship_date, quoted_lead_days, wip_days, lead_time_wd
    from {{ ref('int_job_lead_time') }}
    where year(ship_date) = {{ var('report_year') }}
),
periods as (
    select 'year' as period, 1 as first_quarter
    union all
    select 'Q2 to Q4', 2
),
w as (
    select p.period, avg(d.wip) as wip_mean, count(*) as working_days
    from periods p
    join days d on quarter(d.calendar_date) >= p.first_quarter
    group by 1
),
s as (
    select p.period, count(*) as jobs_shipped, avg(j.quoted_lead_days) as quoted_lead_mean, avg(j.wip_days) as days_in_wip_mean,
        avg(j.lead_time_wd) as lead_time_mean
    from periods p
    join jobs j on quarter(j.ship_date) >= p.first_quarter
    group by 1
)
select
    {{ batch_id() }} as export_batch_id,
    w.period,
    w.working_days,
    s.jobs_shipped,
    w.wip_mean,
    s.jobs_shipped / w.working_days as throughput_per_day,
    s.quoted_lead_mean,
    s.jobs_shipped / w.working_days * s.quoted_lead_mean as wip_at_quoted_lead_times,
    w.wip_mean / (s.jobs_shipped / w.working_days * s.quoted_lead_mean) as wip_ratio,
    w.wip_mean / (s.jobs_shipped / w.working_days) as wip_over_throughput_days,
    s.days_in_wip_mean,
    s.lead_time_mean
from w
join s using (period)
