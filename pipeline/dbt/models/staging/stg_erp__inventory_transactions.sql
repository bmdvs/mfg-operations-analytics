select
    transaction_id,
    item_id,
    "type" as transaction_type,
    cast(qty as integer) as qty,
    job_id,
    cast(transaction_ts as timestamp) as transaction_ts
from {{ source('erp', 'erp__inventory_transactions') }}
