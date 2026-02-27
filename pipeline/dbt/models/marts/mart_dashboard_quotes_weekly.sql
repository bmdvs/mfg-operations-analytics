-- One row per week (Monday start): the fixed quote and the quote table against lead time for non-rush jobs by release week,
-- and quote turnaround and win rate by the week the quote was sent. A quote is met when the working days from the release day to the
-- ship day are at or under it; a quote with no decision counts as not won.
with weeks as (
    select week_start, weekdays from {{ ref('mart_weekly_floor') }}
),
jobs as (
    select c.release_week as week_start, c.ship_date is not null as shipped, l.wip_days, c.quoted_lead_days, t.quote_days
    from {{ ref('mart_job_release_conditions') }} c
    left join {{ ref('mart_job_lead_time') }} l using (job_id)
    join {{ ref('mart_p7_quote_table') }} t
        on t.routing_class = c.routing_class
       and t.backlog_band = case when c.brake_backlog_days <= 2 then 'under 2' when c.brake_backlog_days <= 3 then '2 to 3'
                                 when c.brake_backlog_days <= 5 then '3 to 5' else 'over 5' end
    where not coalesce(c.rush_flag, false)
),
released as (
    select week_start, count(*) as non_rush_jobs_released, sum(shipped::int) as non_rush_jobs_shipped,
        avg((wip_days <= quoted_lead_days)::int) filter (where shipped) as fixed_quote_met,
        avg((wip_days <= quote_days)::int) filter (where shipped) as quote_table_met,
        avg(quote_days) as quote_table_mean_days,
        avg((quote_days > quoted_lead_days)::int) as quote_table_longer_than_fixed
    from jobs
    group by 1
),
quotes as (
    select cast(date_trunc('week', quote_sent_date) as date) as week_start, count(*) as quotes_sent,
        avg((not slow_turnaround)::int) as sent_within_3_days,
        avg(won::int) as win_rate,
        sum((not slow_turnaround)::int) as quotes_within_3_days,
        sum(slow_turnaround::int) as quotes_over_3_days,
        coalesce(sum(won::int) filter (where not slow_turnaround), 0) as won_within_3_days,
        coalesce(sum(won::int) filter (where slow_turnaround), 0) as won_over_3_days,
        sum((status = 'no decision')::int) as quotes_undecided
    from {{ ref('mart_quotes') }}
    group by 1
)
select
    {{ batch_id() }} as export_batch_id,
    w.week_start, w.weekdays,
    r.non_rush_jobs_released, r.non_rush_jobs_shipped, r.non_rush_jobs_shipped / nullif(r.non_rush_jobs_released, 0) as shipped_share,
    r.fixed_quote_met, r.quote_table_met, r.quote_table_mean_days, r.quote_table_longer_than_fixed,
    q.quotes_sent, q.sent_within_3_days, q.win_rate, q.quotes_within_3_days, q.quotes_over_3_days, q.won_within_3_days, q.won_over_3_days,
    q.quotes_undecided
from weeks w
left join released r using (week_start)
left join quotes q using (week_start)
