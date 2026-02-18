-- One row per job operation worked: first start, last end, and setup and run hours as the union of transaction intervals.
with lab as (
    select * from {{ ref('int_labor_transactions') }}
),
span as (
    select job_id, op_seq, min(start_ts) as first_start, max(end_ts) as last_end, min(work_center) as work_center
    from lab
    group by 1, 2
),
first_setup as (
    select job_id, op_seq, employee_id as setup_employee_id, start_ts as setup_start
    from lab
    where labor_type = 'setup'
    qualify row_number() over (partition by job_id, op_seq order by start_ts, transaction_id) = 1
),
setup_emp as (
    select job_id, op_seq, count(distinct employee_id) as setup_employees
    from lab
    where labor_type = 'setup'
    group by 1, 2
),
islands as (
    {{ interval_islands('lab', ['job_id', 'op_seq', 'labor_type'], 'start_ts', 'end_ts') }}
),
hours as (
    select job_id, op_seq,
        sum(case when labor_type = 'setup' then epoch(island_end - island_start) / 3600.0 else 0 end) as setup_hours,
        sum(case when labor_type = 'run' then epoch(island_end - island_start) / 3600.0 else 0 end) as run_hours
    from islands
    group by 1, 2
),
machine as (
    select job_id, op_seq, machine_id
    from lab
    qualify row_number() over (partition by job_id, op_seq order by start_ts, transaction_id) = 1
)
select
    s.job_id, s.op_seq, s.work_center, m.machine_id, s.first_start, s.last_end,
    h.setup_hours, h.run_hours,
    jo.setup_std, jo.run_std, jo.qty,
    f.setup_employee_id, f.setup_start, e.setup_employees
from span s
join hours h using (job_id, op_seq)
left join machine m using (job_id, op_seq)
left join first_setup f using (job_id, op_seq)
left join setup_emp e using (job_id, op_seq)
left join {{ ref('stg_erp__job_operations') }} jo using (job_id, op_seq)
