select
    item_id,
    description,
    item_type,
    material,
    thickness,
    sheet_size,
    cast(min_qty as integer) as min_qty,
    cast(max_qty as integer) as max_qty,
    cast(on_hand as integer) as on_hand,
    abc_class
from {{ source('erp', 'erp__inventory_items') }}
