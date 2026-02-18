select
    shipment_id,
    job_id,
    cast(ship_date as date) as ship_date,
    cast(qty as integer) as qty,
    cast(promised_date as date) as promised_date,
    cast(on_time as boolean) as on_time,
    late_reason_code
from {{ source('erp', 'erp__shipments') }}
