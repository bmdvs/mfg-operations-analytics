select
    quote_id,
    customer_id,
    cast(rfq_received_date as date) as rfq_received_date,
    cast(quote_sent_date as date) as quote_sent_date,
    estimator,
    status,
    lost_reason,
    cast(decision_date as date) as decision_date
from {{ source('erp', 'erp__quotes') }}
