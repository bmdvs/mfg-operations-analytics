-- The quote table: 80th-percentile lead time, rounded up, by routing class and brake backlog band at release, on every job shipped,
-- and the quote never below the fixed quote. Bands are under 2, 2 to 3, 3 to 5 and over 5 days of brake backlog; a band with fewer
-- than 20 jobs takes the fixed quote.
with j as (
    select l.routing_class, l.quoted_lead_days, l.wip_days,
        case when c.brake_backlog_days <= 2 then 'under 2' when c.brake_backlog_days <= 3 then '2 to 3'
             when c.brake_backlog_days <= 5 then '3 to 5' else 'over 5' end as backlog_band
    from {{ ref('mart_job_lead_time') }} l
    join {{ ref('mart_job_release_conditions') }} c using (job_id)
    where l.ship_date is not null
)
select
    {{ batch_id() }} as export_batch_id,
    routing_class, backlog_band, routing_class || ', ' || backlog_band as quote_table_key,
    max(quoted_lead_days) as fixed_quote, count(*) as jobs,
    case when count(*) >= 20 then ceil(quantile_cont(wip_days, 0.8)) end as lead_time_p80,
    greatest(coalesce(case when count(*) >= 20 then ceil(quantile_cont(wip_days, 0.8)) end, max(quoted_lead_days)), max(quoted_lead_days)) as quote_days
from j
group by 1, 2, 3, 4
