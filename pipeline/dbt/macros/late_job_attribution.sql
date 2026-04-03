{# Attribution of late jobs to causes; pctl is the queue percentile of the constraint rule. #}
{% macro late_job_attribution(pctl) %}
with jobs as (
    select job_id, routing_class, quoted_lead_days, promised_lead_wd, days_late, on_time, ship_date, customer_id,
        cast(date_trunc('quarter', ship_date) as date) as ship_quarter
    from {{ ref('int_job_lead_time') }}
    where ship_date is not null
),
stage_rows as (
    select job_id,
        case when stage = 'queue' then 'queue: ' || replace(work_center, '_', ' ') else stage end as stage,
        coalesce(work_center, 'none') as work_center,
        sum(days) as days
    from {{ ref('int_job_stage_days') }}
    where stage <> 'powder scheduling wait'
    group by 1, 2, 3
),
job_stage as (
    select job_id, stage, sum(days) as days from stage_rows group by 1, 2
),
stages as (
    select distinct stage from job_stage
),
grid as (
    select j.job_id, j.routing_class, j.ship_quarter, j.on_time, s.stage, coalesce(js.days, 0) as days
    from jobs j
    cross join stages s
    left join job_stage js on js.job_id = j.job_id and js.stage = s.stage
),
normal as (
    select routing_class, ship_quarter, stage, median(days) as normal_days
    from grid
    where on_time
    group by 1, 2, 3
),
lost as (
    select g.job_id, g.stage, greatest(g.days - n.normal_days, 0) as lost_days
    from grid g
    join normal n using (routing_class, ship_quarter, stage)
    where not g.on_time
),

-- rule: queue at a work center above the rule's percentile for the quarter
op_p80 as (
    select work_center, cast(date_trunc('quarter', first_start) as date) as q, quantile_cont(queue_net_wd, {{ pctl }}) as p80
    from {{ ref('int_operation_queue') }}
    where not is_first_op and work_center <> 'outside_processing'
    group by 1, 2
),
constraint_queue as (
    select distinct o.job_id, 'queue: ' || replace(o.work_center, '_', ' ') as stage
    from {{ ref('int_operation_queue') }} o
    join op_p80 p on p.work_center = o.work_center and p.q = cast(date_trunc('quarter', o.first_start) as date)
    where not o.is_first_op and o.queue_net_wd > p.p80
),
first_op as (
    select s.job_id, s.work_center, s.days, o.first_start,
        cast(date_trunc('quarter', o.first_start) as date) as q,
        cast(date_trunc('week', o.first_start) as date) as week_start
    from {{ ref('int_job_stage_days') }} s
    join {{ ref('int_operation_queue') }} o on o.job_id = s.job_id and o.op_seq = s.op_seq
    where s.stage = 'first-operation queue'
),
first_p80 as (
    select work_center, q, quantile_cont(days, {{ pctl }}) as p80 from first_op group by 1, 2
),
constraint_first as (
    select f.job_id from first_op f join first_p80 p using (work_center, q) where f.days > p.p80
),

-- rule: material (kit shortage recorded, a material hold, or an issue after planned start that follows a receipt of the same item
-- with capacity available at the first work center: its queue that week below its median week)
kit_short as (
    select distinct job_id from {{ ref('stg_mes__kit_checks') }} where result = 'short'
),
material_hold as (
    select distinct job_id from {{ ref('stg_mes__holds') }} where hold_reason = 'material'
),
first_week as (
    select work_center, week_start, avg(days) as week_queue from first_op group by 1, 2
),
first_week_median as (
    select work_center, median(week_queue) as median_week_queue from first_week group by 1
),
sheet_issue as (
    select t.job_id, t.item_id, min(t.transaction_ts) as issue_ts
    from {{ ref('stg_erp__inventory_transactions') }} t
    join {{ ref('stg_erp__inventory_items') }} i using (item_id)
    where t.transaction_type = 'issue' and i.item_type = 'sheet' and t.job_id is not null
    group by 1, 2
),
planned_first as (
    select job_id, min(planned_start) as planned_start from {{ ref('stg_erp__job_operations') }} group by 1
),
stock_wait as (
    select distinct si.job_id
    from sheet_issue si
    join planned_first pf using (job_id)
    join {{ ref('stg_erp__inventory_transactions') }} r
      on r.item_id = si.item_id and r.transaction_type = 'receipt' and r.job_id is null
     and r.transaction_ts > pf.planned_start and r.transaction_ts <= si.issue_ts
    join first_op f on f.job_id = si.job_id
    join first_week w on w.work_center = f.work_center and w.week_start = f.week_start
    join first_week_median m on m.work_center = f.work_center
    where si.issue_ts > pf.planned_start and w.week_queue < m.median_week_queue
),

-- rules: outside processing received after its promised date; setup overrun; quality hold or rework
outside_late as (
    select distinct job_id from {{ ref('stg_erp__po_lines') }}
    where line_type = 'outside processing' and received_date > promised_date
),
setup_overrun as (
    select distinct job_id from {{ ref('int_operation_actuals') }}
    where setup_hours > setup_std + 2 and setup_hours > 2 * setup_std
),
rework as (
    select distinct job_id from {{ ref('stg_qms__rework_ops') }}
),

matched as (
    select
        l.job_id, l.stage, l.lost_days,
        case
            when l.stage = 'material wait at first operation' and (k.job_id is not null or mh.job_id is not null) then 'material'
            when l.stage = 'hold: material' then 'material'
            when l.stage = 'first-operation queue' and sw.job_id is not null then 'material'
            when l.stage = 'first-operation queue' and cf.job_id is not null then 'constraint queue'
            when l.stage like 'queue:%' and cq.job_id is not null then 'constraint queue'
            when l.stage = 'outside processing' and ol.job_id is not null then 'outside processing'
            when l.stage = 'setup and run' and so.job_id is not null then 'setup overrun'
            when l.stage = 'setup and run' and rw.job_id is not null then 'quality'
            when l.stage = 'hold: quality' then 'quality'
            when l.stage in ('hold: engineering', 'hold: customer', 'hold: tooling') then 'other hold'
            else 'not attributable'
        end as cause
    from lost l
    left join kit_short k using (job_id)
    left join material_hold mh using (job_id)
    left join stock_wait sw using (job_id)
    left join constraint_first cf using (job_id)
    left join constraint_queue cq on cq.job_id = l.job_id and cq.stage = l.stage
    left join outside_late ol using (job_id)
    left join setup_overrun so using (job_id)
    left join rework rw using (job_id)
    where l.lost_days > 0
),
late as (
    select job_id, days_late,
        least(greatest(quoted_lead_days - promised_lead_wd, 0), days_late) as released_late_days
    from jobs
    where not on_time
),
totals as (
    select job_id, sum(lost_days) as lost_total, sum(lost_days) filter (where cause <> 'not attributable') as matched_total
    from matched
    group by 1
),
allocated as (
    select
        m.job_id, m.stage, m.cause, m.lost_days,
        case when t.lost_total >= (l.days_late - l.released_late_days)
             then m.lost_days * (l.days_late - l.released_late_days) / t.lost_total
             else m.lost_days end as attributed_days
    from matched m
    join late l using (job_id)
    join totals t using (job_id)
),
shortfall as (
    -- days late beyond the lost days found at any stage
    select l.job_id, 'no stage above normal' as stage, 'not attributable' as cause, 0.0 as lost_days,
        l.days_late - l.released_late_days - coalesce(t.lost_total, 0) as attributed_days
    from late l
    left join totals t using (job_id)
    where l.days_late - l.released_late_days - coalesce(t.lost_total, 0) > 0
),
released as (
    select job_id, 'promise inside the standard lead time' as stage, 'released late' as cause, released_late_days as lost_days,
        released_late_days as attributed_days
    from late
    where released_late_days > 0
)
select * from allocated where attributed_days > 0
union all
select * from shortfall
union all
select * from released
{% endmacro %}
