-- One row per quote: turnaround in weekdays from RFQ received to quote sent, the outcome, and the RFQ's complexity.
-- A quote with no decision counts as not won.
with q as (
    select q.quote_id, q.customer_id, q.rfq_received_date, q.quote_sent_date, q.estimator, q.status, q.lost_reason, q.decision_date,
        l.quote_line_id, l.part_id, l.family, l.new_part, l.bend_count, l.outside_processing, l.qty, l.quoted_price, l.quoted_lead_time_days, l.rush_rfq
    from {{ ref('stg_erp__quotes') }} q
    join {{ ref('stg_erp__quote_lines') }} l using (quote_id)
),
turnaround as (
    select q.quote_id, count(d.calendar_date) as turnaround_days
    from q
    left join {{ ref('int_working_days') }} d
        on d.calendar_date > q.rfq_received_date and d.calendar_date <= q.quote_sent_date and dayofweek(d.calendar_date) between 1 and 5
    group by 1
)
select
    {{ batch_id() }} as export_batch_id,
    q.*, c.customer_name, c.key_account,
    t.turnaround_days, t.turnaround_days > 3 as slow_turnaround,
    q.status = 'won' as won,
    year(q.rfq_received_date) as rfq_year, quarter(q.rfq_received_date) as rfq_quarter,
    case when q.outside_processing then 20 when q.new_part then 15 else 10 end as standard_lead_days
from q
join turnaround t using (quote_id)
join {{ ref('stg_erp__customers') }} c using (customer_id)
