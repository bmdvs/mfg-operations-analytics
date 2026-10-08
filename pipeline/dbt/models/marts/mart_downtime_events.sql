-- Downtime events with hours.
select {{ batch_id() }} as export_batch_id, downtime_id, machine_id, work_center, start_ts, end_ts, cause,
    epoch(end_ts - start_ts) / 3600.0 as hours, cast(date_trunc('week', start_ts) as date) as week_start
from {{ ref('stg_maintenance__downtime_events') }}
