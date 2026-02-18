select
    po_line_id,
    po_id,
    vendor_id,
    item_id,
    job_id,
    cast(op_seq as integer) as op_seq,
    "type" as line_type,
    cast(order_date as date) as order_date,
    cast(promised_date as date) as promised_date,
    cast(received_date as date) as received_date,
    cast(qty as integer) as qty
from {{ source('erp', 'erp__po_lines') }}
