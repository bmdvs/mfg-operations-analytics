select
    rework_op_id,
    job_id,
    cast(op_seq_reworked as integer) as op_seq_reworked,
    work_center,
    cast(hours as double) as hours,
    cast(rework_date as date) as rework_date
from {{ source('qms', 'qms__rework_ops') }}
