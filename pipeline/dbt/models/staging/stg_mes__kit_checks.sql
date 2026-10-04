select
    job_id,
    cast(check_date as date) as check_date,
    result,
    short_item,
    cast(short_qty as integer) as short_qty
from {{ source('mes', 'mes__kit_checks') }}
