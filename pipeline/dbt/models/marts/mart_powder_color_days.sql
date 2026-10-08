-- Scheduled powder color days per week, by color.
select
    {{ batch_id() }} as export_batch_id,
    color,
    count(*) / count(distinct week_start) as days_per_week,
    string_agg(distinct dayname(schedule_date), ', ') as weekdays
from {{ ref('stg_mes__powder_color_schedule') }}
group by color
