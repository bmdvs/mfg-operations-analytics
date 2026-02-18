select
    sales_order_id,
    customer_id,
    cast(order_date as date) as order_date,
    customer_po
from {{ source('erp', 'erp__sales_orders') }}
