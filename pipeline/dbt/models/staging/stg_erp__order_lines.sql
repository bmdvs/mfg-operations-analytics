select
    order_line_id,
    sales_order_id,
    cast(line_no as integer) as line_no,
    customer_id,
    part_id,
    cast(qty as integer) as qty,
    cast(order_date as date) as order_date,
    cast(requested_date as date) as requested_date,
    cast(promised_date as date) as promised_date,
    cast(original_promised_date as date) as original_promised_date,
    cast(promise_revision_count as integer) as promise_revision_count,
    cast(unit_price as double) as unit_price,
    cast(rush_flag as boolean) as rush_flag,
    quote_line_id,
    line_status
from {{ source('erp', 'erp__order_lines') }}
