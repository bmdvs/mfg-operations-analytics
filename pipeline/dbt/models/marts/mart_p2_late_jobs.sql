-- One row per late job: the late-reason code as entered, the dominant attributed cause and whether the two agree.
-- Code equivalents of the causes: constraint queue and setup overrun are capacity; released late, other hold and not attributable are other.
with by_cause as (
    select job_id, cause, sum(attributed_days) as days
    from {{ ref('int_late_job_attribution') }}
    group by 1, 2
),
dominant as (
    select job_id, cause as dominant_cause, days as dominant_days
    from by_cause
    qualify row_number() over (partition by job_id order by days desc, cause) = 1
),
assigned as (
    select job_id, sum(days) filter (where cause <> 'not attributable') as assigned_days, sum(days) as total_days
    from by_cause
    group by 1
)
select
    {{ batch_id() }} as export_batch_id,
    l.job_id, l.customer_id, c.customer_name, c.key_account, l.routing_class, l.family, l.rush_flag, l.promise_revision_count,
    l.ship_date, year(l.ship_date) as ship_year, quarter(l.ship_date) as ship_quarter, l.days_late,
    l.late_reason_code,
    d.dominant_cause,
    case d.dominant_cause
        when 'constraint queue' then 'capacity'
        when 'setup overrun' then 'capacity'
        when 'material' then 'material'
        when 'outside processing' then 'outside processing'
        when 'quality' then 'quality'
        else 'other'
    end as dominant_cause_code,
    coalesce(a.assigned_days, 0) as assigned_days,
    a.total_days,
    coalesce(a.assigned_days, 0) > 0 as has_assigned_cause
from {{ ref('int_job_lead_time') }} l
join dominant d using (job_id)
join assigned a using (job_id)
left join {{ ref('stg_erp__customers') }} c using (customer_id)
where l.ship_date is not null and not l.on_time
