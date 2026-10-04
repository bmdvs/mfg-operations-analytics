-- One row per operation worked: work center, machine, hours against standard and queue.
select
    {{ batch_id() }} as export_batch_id,
    a.job_id, a.op_seq, a.work_center, a.machine_id, a.first_start, a.last_end,
    cast(date_trunc('week', a.first_start) as date) as week_start, year(a.first_start) as start_year, quarter(a.first_start) as start_quarter,
    a.setup_hours, a.run_hours, a.setup_std, a.run_std * a.qty as run_std_hours, a.qty,
    a.setup_employee_id, a.setup_start, a.setup_employees,
    q.is_first_op, q.queue_wd, q.queue_net_wd, q.scheduling_wait_wd,
    p.family, p.bend_count, p.thickness, l.rush_flag, l.routing_class
from {{ ref('int_operation_actuals') }} a
left join {{ ref('int_operation_queue') }} q using (job_id, op_seq)
left join {{ ref('int_job_lead_time') }} l using (job_id)
left join {{ ref('stg_erp__parts') }} p on p.part_id = l.part_id
