-- One row per job: quoted lead time class, promise, ship, lead time in working days and lateness.
-- Lead time runs from the release date at 10:00 to the ship date at 15:00 on the working-day clock.
with outside as (
    select distinct job_id from {{ ref('stg_erp__job_operations') }} where work_center = 'outside_processing'
),
line as (
    -- a new-part line is the first order against a new-part quote line, placed within 60 days of the quote decision;
    -- later orders against the same quote line are repeat parts
    select ol.order_line_id, ol.rush_flag, ol.order_date, ol.promised_date, ol.original_promised_date, ol.promise_revision_count,
        coalesce(ql.new_part, false)
            and row_number() over (partition by ol.quote_line_id order by ol.order_date, ol.order_line_id) = 1
            and ol.order_date - q.decision_date <= 60 as new_part
    from {{ ref('stg_erp__order_lines') }} ol
    left join {{ ref('stg_erp__quote_lines') }} ql using (quote_line_id)
    left join {{ ref('stg_erp__quotes') }} q using (quote_id)
),
base as (
    select
        j.job_id, j.part_id, j.customer_id, j.order_line_id, j.qty, j.release_date, j.due_date, j.ship_date, j.status, j.late_reason_code,
        p.family,
        l.rush_flag, l.original_promised_date, l.promise_revision_count,
        case when o.job_id is not null then 'outside processing' when l.new_part then 'new part' else 'repeat part' end as routing_class,
        case when o.job_id is not null then 20 when l.new_part then 15 else 10 end as quoted_lead_days,
        s.on_time,
        cast(j.release_date as timestamp) + interval 10 hour as release_ts,
        cast(j.ship_date as timestamp) + interval 15 hour as ship_ts
    from {{ ref('stg_erp__jobs') }} j
    join {{ ref('stg_erp__parts') }} p using (part_id)
    left join line l using (order_line_id)
    left join outside o using (job_id)
    left join {{ ref('stg_erp__shipments') }} s using (job_id)
)
select
    b.*,
    {{ wd('b.ship_ts', 'c2') }} - {{ wd('b.release_ts', 'c1') }} as lead_time_wd,
    -- working days from the release day (counted) to the ship day (not counted): the days the job is in WIP
    c2.wd_index - c1.wd_index as wip_days,
    c3.wd_index - c1.wd_index as promised_lead_wd,
    greatest(c2.wd_index - c3.wd_index, 0) as days_late
from base b
left join {{ ref('int_working_days') }} c1 on c1.calendar_date = b.release_date
left join {{ ref('int_working_days') }} c2 on c2.calendar_date = b.ship_date
left join {{ ref('int_working_days') }} c3 on c3.calendar_date = b.due_date
