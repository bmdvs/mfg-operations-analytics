select
    export_batch_id,
    cast(exported_at as timestamp) as exported_at,
    cast(period_start as date) as period_start,
    cast(period_end as date) as period_end
from {{ source('erp', 'erp__export_batch') }}
