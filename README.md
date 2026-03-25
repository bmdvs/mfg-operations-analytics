# Operations analytics for a sheet-metal job shop

Custom sheet-metal fabrication job shop, about 120 employees, one plant.  
Eight improvement projects and an operations dashboard on the shop's records from January 2023 to December 2025.

## Projects

| Project | Question | Finding | Deliverable |
|---|---|---|---|
| P1. Lead time decomposition | Where does the lead time go, and does the floor's WIP match the quoted lead times? | The brakes hold 56% of queue time for the year and 40% in Q2 to Q4. The median job ships in 11.2 working days against an average quoted lead time of 12.4; 9.2 in Q2 to Q4. | [report](docs/reports/p1_lead_time.html), [A3](docs/a3/p1_lead_time.html) |
| P2. Why jobs are late | What makes jobs late, and do the shop's late-reason codes say so? | For the year, constraint queue is 36% of the 4,647 lost days, unexplained 33%, released late 17%, material 6.5% and outside processing 3%; the year is the 2024 year-end build shipping in the first quarter. | [report](docs/reports/p2_late_jobs.html), [A3](docs/a3/p2_late_jobs.html) |
| P3. The constraint, utilization and variability | Which work center is the constraint, and how does its queue respond to load? | The brakes run at 0.91 of scheduled hours net of downtime, the robotic weld cell at 0.83, the lasers at 0.74, assembly through hardware at 0.66 to 0.69 and the powder line at 0.56. | [report](docs/reports/p3_constraint.html), [A3](docs/a3/p3_constraint.html) |
| P4. Setups and standards | What do setups cost at the brakes, and where is the overrun? | Brake setups ran 6,077 hours against 4,235 standard in 2025: 1,842 hours over, 35 a week, 11% of brake machine time. | [report](docs/reports/p4_setups.html), [A3](docs/a3/p4_setups.html) |
| P5. Release control and the shop model | Do release control and dispatch rules help, and what does? | A WIP cap and dispatch rules do not help; the setup program, a second shift on the robotic weld cell and planned Saturdays from November through February take the year to 88.0% on time, up 6.0 points (5.0 to 6.9), and Q2 to Q4 to 91.8%. | [report](docs/reports/p5_release_control.html), [A3](docs/a3/p5_release_control.html) |
| P6. Leading indicators | Which weekly measures move before on-time delivery does? | The on-time start rate correlates +0.62 with on-time delivery 1 week later, against a 95th percentile of +0.24 on shuffled series and +0.21 on shifted series. It moved before all four declines in on-time delivery; no other weekly measure leads in ordinary weeks. | [report](docs/reports/p6_leading_indicators.html), [A3](docs/a3/p6_leading_indicators.html) |
| P7. Lead-time quoting and quote analytics | What lead time should be quoted, and what wins quotes? | The fixed quote is met on 53.0% of non-rush jobs for the year and 70.5% in Q2 to Q4; a quote by routing class and brake backlog at release, never below the fixed quote, is met on 67.0% and 82.1% out of sample and lengthens 43.6% and 33.9% of promises. | [report](docs/reports/p7_quoting.html), [A3](docs/a3/p7_quoting.html) |
| P8. Technology ROI | Do the capital options pay back? | On overtime and labor alone no option pays back within the 7-year horizon, and the no-capital package is net negative ($70,000 a year, the weld cell's second shift). With half the released brake hours sold, the robotic cell pays back in 1.6 years, the tool changer on B3 in 3.9, the laser tower not at all. | [report](docs/reports/p8_technology_roi.html), [A3](docs/a3/p8_technology_roi.html) |

Dashboard: [docs/dashboard/index.html](docs/dashboard/index.html). Index of deliverables: [docs/index.html](docs/index.html).

## Data sources

| System | Export | Tables | Grain | Batch |
|---|---|---|---|---|
| ERP | data/raw/erp/ (16 CSV files) | customers, export_batch, inventory_items, inventory_transactions, job_operations, jobs, order_lines, parts, po_lines, purchase_orders, quote_lines, quotes, routings, sales_orders, shipments, work_center_calendar | customer, part, routing operation, quote, quote line, sales order, order line, job, job operation, inventory item, inventory transaction, purchase order, PO line, shipment, work center and day, export batch | 20261003T152921Z-20250101 |
| Shop-floor data collection | data/raw/mes/ (6 CSV files) | holds, job_status_events, kit_checks, labor_transactions, laser_nests, powder_color_schedule | labor transaction, job status event, hold, kit check, laser nest, powder color and day | 20261003T152921Z-20250101 |
| QMS | data/raw/qms/ (2 CSV files) | ncrs, rework_ops | nonconformance, rework operation | 20261003T152921Z-20250101 |
| Maintenance | data/raw/maintenance/ (1 CSV file) | downtime_events | downtime event | 20261003T152921Z-20250101 |
| HR | data/raw/hr/ (2 CSV files) | attendance, employees | employee, employee and day | 20261003T152921Z-20250101 |

## Pipeline

`pipeline/load` loads the CSV exports under `data/raw` into DuckDB with dlt, one text table per file. The dbt project under `pipeline/dbt` builds the staging models (one per export, typed), the intermediate models (working-day clock, machine time, queue, lead time by stage, WIP, utilization, setups, late-job attribution) and the marts, with tests on keys. The scripts under `analytics/` read the marts and write each project's report, A3 and figures under `docs/`, the dashboard and this file. The shop model under `analytics/p5_release_control/` replays the released jobs for the scenarios of P5 and P8; its runs are saved under `results/` and each run repeats exactly from its scenario and replication number.

## How to run

Python 3.12 or later, from a clean clone:

```
python -m venv .venv
.venv\Scripts\activate            # Windows; on Linux or macOS: source .venv/bin/activate
pip install -e .
python -m pipeline.load.load_exports
cd pipeline/dbt
dbt build --profiles-dir .
cd ../..
python -m analytics.build_all
```

`analytics.build_all` uses the saved model runs. To repeat the runs (several hours on six processes):

```
python -m analytics.p5_release_control.scenarios 30 6
python -m analytics.p8_technology_roi.scenarios 30 6
python -m analytics.p8_technology_roi.scenarios 30 6 laser_queue
```
