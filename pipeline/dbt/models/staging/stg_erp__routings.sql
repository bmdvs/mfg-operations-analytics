select
    part_id,
    cast(op_seq as integer) as op_seq,
    work_center,
    cast(setup_std_hrs as double) as setup_std_hrs,
    cast(run_std_hrs_per_piece as double) as run_std_hrs_per_piece,
    vendor_id,
    tooling_set,
    cast(standard_set_date as date) as standard_set_date
from {{ source('erp', 'erp__routings') }}
