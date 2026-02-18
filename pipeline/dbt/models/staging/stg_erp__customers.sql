select
    customer_id,
    customer_name,
    industry,
    terms,
    cast(required_otd_pct as double) as required_otd_pct,
    cast(key_account as boolean) as key_account
from {{ source('erp', 'erp__customers') }}
