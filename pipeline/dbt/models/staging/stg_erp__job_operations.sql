select
    job_id,
    cast(op_seq as integer) as op_seq,
    work_center,
    vendor_id,
    cast(planned_start as timestamp) as planned_start,
    cast(planned_finish as timestamp) as planned_finish,
    cast(setup_std as double) as setup_std,
    cast(run_std as double) as run_std,
    cast(qty as integer) as qty
from {{ source('erp', 'erp__job_operations') }}
