select
    job_id,
    order_line_id,
    sales_order_id,
    customer_id,
    part_id,
    cast(qty as integer) as qty,
    cast(release_date as date) as release_date,
    cast(due_date as date) as due_date,
    status,
    cast(close_date as date) as close_date,
    cast(ship_date as date) as ship_date,
    late_reason_code,
    planner
from {{ source('erp', 'erp__jobs') }}
