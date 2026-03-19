-- One row per week (Monday start): delivery and lead time by ship week, lost days by attributed cause by ship week,
-- and the job-level flags by release week and kit-check week.
with weeks as (
    select week_start, weekdays from {{ ref('mart_weekly_floor') }}
),
shipped as (
    select cast(date_trunc('week', ship_date) as date) as week_start, count(*) as jobs_shipped, avg(on_time::int) as on_time_delivery,
        median(lead_time_wd) as lead_time_median, quantile_cont(lead_time_wd, 0.9) as lead_time_p90,
        sum((not on_time)::int) as late_jobs, sum(days_late) as lost_days
    from {{ ref('mart_job_lead_time') }}
    where ship_date is not null
    group by 1
),
codes as (
    select cast(date_trunc('week', ship_date) as date) as week_start, sum((late_reason_code is null)::int) as late_jobs_without_reason_code
    from {{ ref('mart_p2_late_jobs') }}
    group by 1
),
causes as (
    select cast(date_trunc('week', ship_date) as date) as week_start,
        sum(attributed_days) filter (where cause = 'constraint queue') as lost_days_constraint_queue,
        sum(attributed_days) filter (where cause = 'released late') as lost_days_released_late,
        sum(attributed_days) filter (where cause = 'material') as lost_days_material,
        sum(attributed_days) filter (where cause = 'outside processing') as lost_days_outside_processing,
        sum(attributed_days) filter (where cause = 'setup overrun') as lost_days_setup_overrun,
        sum(attributed_days) filter (where cause = 'quality') as lost_days_quality,
        sum(attributed_days) filter (where cause = 'other hold') as lost_days_other_hold,
        sum(attributed_days) filter (where cause = 'not attributable') as lost_days_not_attributable
    from {{ ref('mart_p2_attribution') }}
    group by 1
),
released as (
    select release_week as week_start, count(*) as jobs_released,
        sum((brake_backlog_days > 3)::int) as released_above_3_days_backlog,
        sum(promised_inside_standard::int) as promised_inside_standard
    from {{ ref('mart_job_release_conditions') }}
    group by 1
),
kits as (
    select cast(date_trunc('week', kit_check_date) as date) as week_start, count(*) as kit_checks, sum((kit_result = 'short')::int) as short_kits
    from {{ ref('mart_job_release_conditions') }}
    where kit_result is not null
    group by 1
)
select
    {{ batch_id() }} as export_batch_id,
    w.week_start, w.weekdays,
    coalesce(s.jobs_shipped, 0) as jobs_shipped, s.on_time_delivery, s.lead_time_median, s.lead_time_p90,
    coalesce(s.late_jobs, 0) as late_jobs, coalesce(s.lost_days, 0) as lost_days, coalesce(c.late_jobs_without_reason_code, 0) as late_jobs_without_reason_code,
    coalesce(a.lost_days_constraint_queue, 0) as lost_days_constraint_queue, coalesce(a.lost_days_released_late, 0) as lost_days_released_late,
    coalesce(a.lost_days_material, 0) as lost_days_material, coalesce(a.lost_days_outside_processing, 0) as lost_days_outside_processing,
    coalesce(a.lost_days_setup_overrun, 0) as lost_days_setup_overrun, coalesce(a.lost_days_quality, 0) as lost_days_quality,
    coalesce(a.lost_days_other_hold, 0) as lost_days_other_hold, coalesce(a.lost_days_not_attributable, 0) as lost_days_not_attributable,
    coalesce(r.jobs_released, 0) as jobs_released, coalesce(r.released_above_3_days_backlog, 0) as released_above_3_days_backlog,
    coalesce(r.promised_inside_standard, 0) as promised_inside_standard,
    coalesce(k.kit_checks, 0) as kit_checks, coalesce(k.short_kits, 0) as short_kits
from weeks w
left join shipped s using (week_start)
left join codes c using (week_start)
left join causes a using (week_start)
left join released r using (week_start)
left join kits k using (week_start)
