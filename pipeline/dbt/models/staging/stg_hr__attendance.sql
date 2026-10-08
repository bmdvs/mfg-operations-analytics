select
    employee_id,
    cast(work_date as date) as work_date,
    cast(scheduled_hours as double) as scheduled_hours,
    cast(present as boolean) as present,
    cast(overtime_hours as double) as overtime_hours,
    absence_reason
from {{ source('hr', 'hr__attendance') }}
