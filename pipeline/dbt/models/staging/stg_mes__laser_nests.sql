select
    nest_id,
    machine_id,
    sheet_item_id,
    jobs,
    cast(job_count as integer) as job_count,
    cast(sheet_qty as integer) as sheet_qty,
    cast(utilization_pct as double) as utilization_pct,
    cast(cut_date as date) as cut_date
from {{ source('mes', 'mes__laser_nests') }}
