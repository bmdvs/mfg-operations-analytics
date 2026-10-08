-- Lead time by stage for shipped jobs, in working days. One row per job, operation and stage; the stages sum to the lead time.
-- Move is the time from the end of an operation to the arrival of the job at the next work center (the queued status event);
-- queue is arrival to first start, less the powder scheduling wait. Recorded holds are taken out of move and queue and shown by reason.
-- Material wait at the first operation is the part of the first-operation wait covered by a recorded material hold or by the wait
-- for a job-specific receipt that arrived after the traveler print.
with jobs as (
    select job_id, release_ts, ship_ts, lead_time_wd from {{ ref('int_job_lead_time') }} where ship_date is not null
),
ops as (
    select q.*, greatest(q.prev_end, j.release_ts) as from_ts
    from {{ ref('int_operation_queue') }} q
    join jobs j using (job_id)
),
arrive as (
    -- the first queued event between the end of the previous operation and the first start of this one
    select o.job_id, o.op_seq, min(e.event_ts) as arrival_ts
    from ops o
    join {{ ref('stg_mes__job_status_events') }} e
      on e.job_id = o.job_id and e.status = 'queued' and e.event_ts > o.from_ts and e.event_ts <= o.first_start
    group by 1, 2
),
timed as (
    select
        o.job_id, o.op_seq, o.work_center, o.is_first_op, o.from_ts, o.first_start, o.last_end, o.scheduling_wait_wd,
        least(coalesce(a.arrival_ts, o.from_ts), o.first_start) as arrival_ts
    from ops o
    left join arrive a using (job_id, op_seq)
),
clocked as (
    select
        t.*,
        {{ wd('t.from_ts', 'c1') }} as from_wd,
        {{ wd('t.arrival_ts', 'c2') }} as arrival_wd,
        {{ wd('t.first_start', 'c3') }} as start_wd,
        {{ wd('t.last_end', 'c4') }} as end_wd
    from timed t
    left join {{ ref('int_working_days') }} c1 on c1.calendar_date = cast(t.from_ts as date)
    left join {{ ref('int_working_days') }} c2 on c2.calendar_date = cast(t.arrival_ts as date)
    left join {{ ref('int_working_days') }} c3 on c3.calendar_date = cast(t.first_start as date)
    left join {{ ref('int_working_days') }} c4 on c4.calendar_date = cast(t.last_end as date)
),
receipt as (
    -- last job-specific receipt for the job
    select job_id, max(transaction_ts) as received_ts
    from {{ ref('stg_erp__inventory_transactions') }}
    where transaction_type = 'receipt' and job_id is not null
    group by 1
),
intervals as (
    -- recorded holds against the operation, cut to its move window and its queue window
    select t.job_id, t.op_seq, h.hold_reason as reason, 'move' as win,
        greatest(h.start_ts, t.from_ts) as a, least(coalesce(h.end_ts, t.first_start), t.arrival_ts) as b
    from timed t
    join {{ ref('stg_mes__holds') }} h using (job_id, op_seq)
    union all
    select t.job_id, t.op_seq, h.hold_reason, 'queue',
        greatest(h.start_ts, t.arrival_ts), least(coalesce(h.end_ts, t.first_start), t.first_start)
    from timed t
    join {{ ref('stg_mes__holds') }} h using (job_id, op_seq)
    union all
    select t.job_id, t.op_seq, 'material receipt', 'queue', t.arrival_ts, least(r.received_ts, t.first_start)
    from timed t
    join receipt r using (job_id)
    where t.is_first_op and r.received_ts > t.arrival_ts
),
interval_days as (
    select i.job_id, i.op_seq, i.reason, i.win, greatest({{ wd('i.b', 'cb') }} - {{ wd('i.a', 'ca') }}, 0) as days
    from intervals i
    left join {{ ref('int_working_days') }} ca on ca.calendar_date = cast(i.a as date)
    left join {{ ref('int_working_days') }} cb on cb.calendar_date = cast(i.b as date)
    where i.b > i.a
),
by_reason as (
    -- a material hold and a late job-specific receipt on the same operation cover the same wait: the longer of the two counts
    select job_id, op_seq, win, grp as reason,
        case when grp = 'material'
             then greatest(coalesce(sum(days) filter (where reason = 'material'), 0), coalesce(max(days) filter (where reason = 'material receipt'), 0))
             else sum(days) end as days
    from (select *, case when reason in ('material', 'material receipt') then 'material' else reason end as grp from interval_days)
    group by 1, 2, 3, 4
),
held as (
    select job_id, op_seq,
        coalesce(sum(days) filter (where win = 'move'), 0) as hold_in_move_raw,
        coalesce(sum(days) filter (where win = 'queue'), 0) as hold_in_queue_raw
    from by_reason
    group by 1, 2
),
capped as (
    -- holds cannot exceed the window they sit in
    select
        k.*,
        greatest(k.arrival_wd - k.from_wd, 0) as move_window,
        greatest(k.start_wd - k.arrival_wd, 0) as queue_window,
        least(k.scheduling_wait_wd, greatest(k.start_wd - k.arrival_wd, 0)) as scheduling_wait,
        coalesce(h.hold_in_move_raw, 0) as hold_in_move_raw,
        coalesce(h.hold_in_queue_raw, 0) as hold_in_queue_raw,
        least(coalesce(h.hold_in_move_raw, 0), greatest(k.arrival_wd - k.from_wd, 0)) as hold_in_move,
        least(coalesce(h.hold_in_queue_raw, 0),
              greatest(k.start_wd - k.arrival_wd, 0) - least(k.scheduling_wait_wd, greatest(k.start_wd - k.arrival_wd, 0))) as hold_in_queue
    from clocked k
    left join held h using (job_id, op_seq)
),
hold_rows as (
    select r.job_id, r.op_seq, c.work_center,
        case when r.reason = 'material' and c.is_first_op then 'material wait at first operation' else 'hold: ' || r.reason end as stage,
        case when r.win = 'move' then r.days * c.hold_in_move / nullif(c.hold_in_move_raw, 0)
             else r.days * c.hold_in_queue / nullif(c.hold_in_queue_raw, 0) end as days
    from by_reason r
    join capped c using (job_id, op_seq)
),
parts as (
    select job_id, op_seq, work_center,
        case when is_first_op then 'release to traveler print' when work_center = 'outside_processing' then 'outside processing' else 'move' end as stage,
        move_window - hold_in_move as days
    from capped
    union all
    select job_id, op_seq, work_center,
        case when is_first_op then 'first-operation queue' when work_center = 'outside_processing' then 'outside processing' else 'queue' end,
        queue_window - scheduling_wait - hold_in_queue
    from capped
    union all
    select job_id, op_seq, work_center, 'powder scheduling wait', scheduling_wait
    from capped
    where work_center = 'powder_coat'
    union all
    select job_id, op_seq, work_center,
        case when work_center = 'outside_processing' then 'outside processing' else 'setup and run' end,
        greatest(end_wd - start_wd, 0)
    from capped
    union all
    select job_id, op_seq, work_center, stage, days from hold_rows where days > 0
),
last_op as (
    select job_id, max(end_wd) as end_wd from clocked group by 1
),
ship as (
    select j.job_id, {{ wd('j.ship_ts', 'c') }} as ship_wd
    from jobs j
    left join {{ ref('int_working_days') }} c on c.calendar_date = cast(j.ship_ts as date)
)
select job_id, op_seq, work_center, stage, days from parts
union all
select s.job_id, null, null, 'complete to ship', greatest(s.ship_wd - l.end_wd, 0)
from ship s
join last_op l using (job_id)
