-- Mean WIP by location: the report year, and each calendar quarter.
with days as (
    select calendar_date, location, jobs from {{ ref('int_wip_daily') }}
),
n as (
    select cast(date_trunc('quarter', calendar_date) as date) as period_start, count(distinct calendar_date) as working_days
    from days
    group by 1
),
quarters as (
    select 'quarter' as period_type, cast(date_trunc('quarter', d.calendar_date) as date) as period_start, d.location,
        sum(d.jobs) / any_value(n.working_days) as wip_mean
    from days d
    join n on n.period_start = cast(date_trunc('quarter', d.calendar_date) as date)
    group by 1, 2, 3
),
year_days as (
    select count(distinct calendar_date) as working_days from days where year(calendar_date) = {{ var('report_year') }}
),
report_year as (
    select 'report year' as period_type, make_date({{ var('report_year') }}, 1, 1) as period_start, d.location,
        sum(d.jobs) / any_value(y.working_days) as wip_mean
    from days d
    cross join year_days y
    where year(d.calendar_date) = {{ var('report_year') }}
    group by 1, 2, 3
)
select {{ batch_id() }} as export_batch_id, * from quarters
union all
select {{ batch_id() }} as export_batch_id, * from report_year
