-- One row per operation with a setup: setup against standard, the operator's familiarity with the part and tenure,
-- shift handover, and whether the setup followed a job on the same tooling set on the same machine.
with ops as (
    select a.job_id, a.op_seq, a.work_center, a.machine_id, a.setup_start, a.setup_employee_id, a.setup_employees,
        a.setup_hours, a.setup_std, a.run_hours, a.run_std * a.qty as run_std_hours, a.qty, j.part_id
    from {{ ref('int_operation_actuals') }} a
    join {{ ref('stg_erp__jobs') }} j using (job_id)
    where a.setup_hours > 0 and a.setup_start is not null
),
setup_tx as (
    select job_id, op_seq, employee_id, start_ts, end_ts
    from {{ ref('int_labor_transactions') }}
    where labor_type = 'setup'
),
pairs as (
    -- two setup transactions on the operation by different operators: one after the other is a handover, overlapping is a two-person setup
    select a.job_id, a.op_seq, b.start_ts >= a.end_ts as sequential, b.start_ts as second_start
    from setup_tx a
    join setup_tx b on b.job_id = a.job_id and b.op_seq = a.op_seq and b.employee_id <> a.employee_id and b.start_ts >= a.start_ts
),
handover as (
    select job_id, op_seq,
        bool_or(sequential) as shift_handover,
        bool_or(not sequential) as two_person_setup,
        min(second_start) filter (where sequential) as handover_ts
    from pairs
    group by 1, 2
),
familiarity as (
    -- prior setups of the same part by the same operator in the trailing 24 months
    select o.job_id, o.op_seq, count(p.job_id) as prior_setups
    from ops o
    left join ops p
      on p.setup_employee_id = o.setup_employee_id and p.part_id = o.part_id
     and p.setup_start < o.setup_start and p.setup_start > o.setup_start - interval 730 day
    group by 1, 2
),
tooling as (
    select part_id, op_seq, work_center, tooling_set, standard_set_date from {{ ref('stg_erp__routings') }}
),
seq as (
    select o.*, t.tooling_set, t.standard_set_date,
        lag(t.tooling_set) over (partition by o.machine_id order by o.setup_start, o.job_id) as previous_tooling_set
    from ops o
    left join tooling t on t.part_id = o.part_id and t.op_seq = o.op_seq and t.work_center = o.work_center
)
select
    s.job_id, s.op_seq, s.work_center, s.machine_id, s.part_id, s.setup_start, s.setup_employee_id,
    s.setup_hours, s.setup_std, s.setup_hours / nullif(s.setup_std, 0) as setup_ratio, s.setup_hours - s.setup_std as setup_overrun_hours,
    s.run_hours, s.run_std_hours, s.qty,
    f.prior_setups,
    datediff('day', e.hire_date, cast(s.setup_start as date)) as tenure_days,
    -- a setup handed from one operator to the next across a shift boundary (first shift 06:00 to 14:00, second 14:30 to 22:30);
    -- two operators on the setup at the same time is a two-person setup, not a handover
    coalesce(h.shift_handover, false) as spans_shift_change,
    coalesce(h.two_person_setup, false) as two_person_setup,
    case when not coalesce(h.shift_handover, false) then null
         when hour(h.handover_ts) = 14 then 'afternoon'
         when hour(h.handover_ts) = 6 then 'overnight'
         else 'other' end as handover_boundary,
    case when hour(s.setup_start) + minute(s.setup_start) / 60.0 < 14 then 14 - (hour(s.setup_start) + minute(s.setup_start) / 60.0)
         when hour(s.setup_start) + minute(s.setup_start) / 60.0 >= 14.5 then 22.5 - (hour(s.setup_start) + minute(s.setup_start) / 60.0) end as hours_to_shift_end,
    s.tooling_set,
    s.tooling_set is not null and s.tooling_set = s.previous_tooling_set as same_tooling_as_previous,
    p.family, p.bend_count, p.first_quoted_date,
    s.standard_set_date,
    s.standard_set_date is not null and s.standard_set_date = p.first_quoted_date as stale_standard
from seq s
join familiarity f using (job_id, op_seq)
left join handover h using (job_id, op_seq)
left join {{ ref('stg_hr__employees') }} e on e.employee_id = s.setup_employee_id
left join {{ ref('stg_erp__parts') }} p on p.part_id = s.part_id
