-- Jobs released per working day, with the releases of the top customer and the last three working days of each month marked.
with days as (
    select calendar_date,
        row_number() over (partition by date_trunc('month', calendar_date) order by calendar_date desc) as days_to_month_end
    from {{ ref('int_working_days') }}
    where is_working_day and dayofweek(calendar_date) between 1 and 5
      and calendar_date between (select period_start from {{ ref('stg_erp__export_batch') }}) and (select max(calendar_date) from {{ ref('stg_erp__work_center_calendar') }})
),
top_customer as (
    select customer_id from {{ ref('stg_erp__jobs') }} group by 1 order by count(*) desc limit 1
),
rel as (
    select j.release_date, count(*) as releases, count(*) filter (where j.customer_id = (select customer_id from top_customer)) as top_customer_releases
    from {{ ref('stg_erp__jobs') }} j
    group by 1
)
select
    {{ batch_id() }} as export_batch_id,
    d.calendar_date, dayname(d.calendar_date) as weekday_name, dayofweek(d.calendar_date) as weekday_no, d.days_to_month_end <= 3 as month_end,
    coalesce(r.releases, 0) as releases, coalesce(r.top_customer_releases, 0) as top_customer_releases
from days d
left join rel r on r.release_date = d.calendar_date
