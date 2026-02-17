-- Machine time: the union of transaction intervals on each machine, one row per unbroken interval.
with islands as (
    {{ interval_islands(ref('int_labor_transactions'), ['work_center', 'machine_id'], 'start_ts', 'end_ts') }}
)
select work_center, machine_id, island_start as start_ts, island_end as end_ts, epoch(island_end - island_start) / 3600.0 as hours
from islands
