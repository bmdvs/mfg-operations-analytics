select
    cast(schedule_date as date) as schedule_date,
    cast(week_start as date) as week_start,
    color
from {{ source('mes', 'mes__powder_color_schedule') }}
