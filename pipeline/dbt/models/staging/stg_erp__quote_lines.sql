select
    quote_line_id,
    quote_id,
    part_id,
    family,
    cast(new_part as boolean) as new_part,
    cast(bend_count as integer) as bend_count,
    cast(outside_processing as boolean) as outside_processing,
    cast(qty as integer) as qty,
    qty_breaks,
    cast(quoted_price as double) as quoted_price,
    cast(quoted_lead_time_days as integer) as quoted_lead_time_days,
    cast(rush_rfq as boolean) as rush_rfq
from {{ source('erp', 'erp__quote_lines') }}
