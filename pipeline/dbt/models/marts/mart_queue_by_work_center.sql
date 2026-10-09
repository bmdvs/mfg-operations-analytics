-- Queue time by work center in the report year, whole and for the second to fourth quarters:
-- operations after the first, powder scheduling wait excluded.
with q as (
    select work_center, queue_net_wd, scheduling_wait_wd, quarter(first_start) as start_quarter
    from {{ ref('int_operation_queue') }}
    where year(first_start) = {{ var('report_year') }} and work_center <> 'outside_processing' and not is_first_op
),
periods as (
    select 'year' as period, * from q
    union all
    select 'Q2 to Q4', * from q where start_quarter >= 2
)
select
    {{ batch_id() }} as export_batch_id,
    period,
    work_center,
    count(*) as operations,
    sum(queue_net_wd) as queue_days,
    sum(queue_net_wd) / sum(sum(queue_net_wd)) over (partition by period) as share_of_queue,
    avg(queue_net_wd) as mean_queue_days,
    median(queue_net_wd) as median_queue_days,
    quantile_cont(queue_net_wd, 0.9) as p90_queue_days,
    sum(scheduling_wait_wd) as scheduling_wait_days
from periods
group by period, work_center
