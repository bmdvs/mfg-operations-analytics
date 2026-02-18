select
    downtime_id,
    machine_id,
    work_center,
    cast("start" as timestamp) as start_ts,
    cast("end" as timestamp) as end_ts,
    cause
from {{ source('maintenance', 'maintenance__downtime_events') }}
