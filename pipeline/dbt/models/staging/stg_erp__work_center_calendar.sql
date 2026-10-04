select
    work_center,
    cast(calendar_date as date) as calendar_date,
    cast(scheduled_hours as double) as scheduled_hours,
    cast(machines as integer) as machines,
    cast(shifts as integer) as shifts,
    cast(saturday as boolean) as saturday,
    cast(extended_hours as double) as extended_hours
from {{ source('erp', 'erp__work_center_calendar') }}
