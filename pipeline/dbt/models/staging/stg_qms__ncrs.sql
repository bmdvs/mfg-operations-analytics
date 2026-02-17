select
    ncr_id,
    job_id,
    cast(op_seq as integer) as op_seq,
    work_center,
    cast(qty as integer) as qty,
    defect_code,
    disposition,
    cast(opened as timestamp) as opened_ts,
    cast(closed as timestamp) as closed_ts
from {{ source('qms', 'qms__ncrs') }}
