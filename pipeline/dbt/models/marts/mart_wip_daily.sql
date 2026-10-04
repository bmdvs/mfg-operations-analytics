-- WIP per working day and location.
select {{ batch_id() }} as export_batch_id, calendar_date, location, jobs
from {{ ref('int_wip_daily') }}
