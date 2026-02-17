select
    event_id,
    job_id,
    status,
    cast(event_ts as timestamp) as event_ts
from {{ source('mes', 'mes__job_status_events') }}
