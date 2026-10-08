-- WIP, throughput and lead time by calendar quarter, month and rolling 13-week window.
-- WIP: jobs released and not shipped, sampled every working day. Throughput: jobs shipped per working day.
-- Lead time: working days from the release day (counted) to the ship day (not counted), on jobs shipped in the period.
with days as (
    select calendar_date, sum(jobs) as wip
    from {{ ref('int_wip_daily') }}
    group by 1
),
ships as (
    select ship_date, count(*) as jobs_shipped, sum(wip_days) as wip_days
    from {{ ref('int_job_lead_time') }}
    where ship_date is not null
    group by 1
),
daily as (
    select d.calendar_date, d.wip, coalesce(s.jobs_shipped, 0) as jobs_shipped, coalesce(s.wip_days, 0) as wip_days
    from days d
    left join ships s on s.ship_date = d.calendar_date
),
fixed as (
    select 'quarter' as period_type, cast(date_trunc('quarter', calendar_date) as date) as period_start, max(calendar_date) as period_end,
        count(*) as working_days, avg(wip) as wip_mean, sum(jobs_shipped) as jobs_shipped, sum(wip_days) as wip_days
    from daily
    group by 1, 2
    union all
    select 'month', cast(date_trunc('month', calendar_date) as date), max(calendar_date),
        count(*), avg(wip), sum(jobs_shipped), sum(wip_days)
    from daily
    group by 1, 2
),
weeks as (
    select distinct cast(date_trunc('week', calendar_date) as date) + 6 as week_end from days
),
rolling as (
    select 'rolling 13 weeks' as period_type, w.week_end - 90 as period_start, w.week_end as period_end,
        count(*) as working_days, avg(d.wip) as wip_mean, sum(d.jobs_shipped) as jobs_shipped, sum(d.wip_days) as wip_days
    from weeks w
    join daily d on d.calendar_date between w.week_end - 90 and w.week_end
    where w.week_end - 90 >= (select min(calendar_date) from days) and w.week_end <= (select max(calendar_date) from days)
    group by 1, 2, 3
),
unioned as (
    select * from fixed
    union all
    select * from rolling
)
select
    {{ batch_id() }} as export_batch_id,
    period_type, period_start, period_end, working_days, jobs_shipped,
    jobs_shipped / working_days as throughput_per_day,
    wip_days / nullif(jobs_shipped, 0) as lead_time_days,
    wip_mean,
    wip_mean / nullif((jobs_shipped / working_days) * (wip_days / nullif(jobs_shipped, 0)), 0) as wip_over_throughput_x_lead_time
from unioned
