select
    transaction_id,
    job_id,
    cast(op_seq as integer) as op_seq,
    employee_id,
    "type" as labor_type,
    cast("start" as timestamp) as start_ts,
    cast("end" as timestamp) as end_ts,
    cast(qty_complete as integer) as qty_complete,
    cast(qty_scrap as integer) as qty_scrap,
    work_center,
    machine_id,
    clock_off
from {{ source('mes', 'mes__labor_transactions') }}
