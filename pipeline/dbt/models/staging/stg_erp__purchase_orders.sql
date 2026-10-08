select
    po_id,
    vendor_id,
    cast(order_date as date) as order_date
from {{ source('erp', 'erp__purchase_orders') }}
