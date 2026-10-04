select
    hold_id,
    job_id,
    cast(op_seq as integer) as op_seq,
    hold_reason,
    cast("start" as timestamp) as start_ts,
    cast("end" as timestamp) as end_ts,
    entered_by
from {{ source('mes', 'mes__holds') }}
