# mfg-operations-analytics

Delivery, flow, capacity and quoting analytics on a custom sheet-metal fabrication job shop, January 2023 to December 2025, computed on the shop's complete ERP and MES record.

![Operations dashboard](docs/readme/dashboard.png)

## What is included

- Eight connected studies, each delivered as a client report: lead-time decomposition, late-job attribution, the constraint and variability, setups against standards, release control on a discrete-event model of the floor, leading indicators, lead-time quoting and quote analytics, technology ROI.
- One operations dashboard: on-time delivery, lead time, WIP, utilization and queue by work center, setup against standard, overtime, the leading indicators; weekly grain, 13-week view, three-year trend.
- A data pipeline from raw system exports to analysis-ready marts: DuckDB, dbt with schema tests, one build command that regenerates every table, figure and page byte-identically.

## Business context

The shop is a custom sheet-metal fabricator: about 120 employees, ISO 9001, one plant, about 2,000 active part numbers, 450 customers, about 5,200 jobs a year in lots from 1 to 500 pieces. Laser cutting, CNC punching, press brake forming, hardware insertion, welding, powder coating and light assembly in house; plating, anodizing and heat treat at outside vendors. Two shifts on the lasers and brakes, one elsewhere, Saturdays when behind.

The shop quotes a fixed lead time by routing class, measures on-time delivery weekly, and records a late reason on each late job. In 2025 it delivered 76.6% on time. The late-reason codes did not explain the misses: a large share (36%) of late reasons were blank, and the coded ones pointed at the operation where the job was found late rather than where it lost the time. A first-quarter decline that year was felt on the floor as a brake-capacity problem, and the shop was weighing a second press brake with automatic tooling against a laser tower and a bending cell.

The engagement put the ERP order and quote records beside the MES operation timestamps for three years, every job and every operation, to answer what the reports could not: where lead time goes, which stage each late job lost its days at, which work center sets the lead time and what variability at it costs, which indicators move before delivery slips, what lead time the shop should quote at its current load, and which of the capital options pays back on measured hours. The studies below are the result, in the order they were built.

## Studies

| Report | Question | Finding | Deliverable |
|---|---|---|---|
| Flow and On-time Delivery | Where does the lead time go, and does the floor's WIP match the quoted lead times? What makes jobs late, and do the shop's late-reason codes say so? What lead time should be quoted in a build, and which measures warn of a decline? | Queue at the brakes is 24% of lead time and the stage that separates late jobs from on-time jobs (5.76 days against 2.50); the median job ships in 11.2 working days against an average quoted lead time of 12.9, 9.2 in Q2-Q4. In 2025, jobs waiting at work centers (i.e., queue constraints) accounted for 42% of the 3,473 lost days, while jobs that were released late accounted for 21%, and jobs that waited on material and outside processing accounted for 7% and 3%, respectively. The shop's quoted lead time was off by 4.8 days on average from 2023 to 2025. The current practice of quoting standard lead times based on the part's routing class, and then adjusting this higher during periods of low capacity, proved to be inaccurate in both directions. | [report](https://brimsystems.github.io/mfg-operations-analytics/docs/reports/lead_time_and_late_jobs.html) |
| Capacity, Constraints and Setups | Which work centers run hot, and how do their queues respond to load? What do setups cost at the brakes, and where is the overrun? | In 2025, the press brakes ran at 91% average utilization and the robotic weld cell at 82%. Against their 97% uptime, the average production capacity buffer was only 6 points for the press brakes and 15 points for the robotic weld cell, the smallest of all work centers. Brake setups ran 1,847 hours over standard in 2025, 36 a week, 10.4 points of brake utilization. | [report](https://brimsystems.github.io/mfg-operations-analytics/docs/reports/capacity_constraints_and_setups.html) |
| Discrete Event Simulation: On-time Delivery | Do release and dispatch rules raise on-time delivery, or only added brake hours? What do the changes that work cost and return? | Scenarios that added brake capacity improved on-time delivery. Among the release and dispatch rules, only earliest due date improved on-time delivery. The "Operating Package" combines the brake setup program and additional Saturday shifts on both brakes, the two low cost capacity scenarios. This combination added 7.7 points to on-time delivery. The operating package is recommended first: it raises on-time delivery 7.7 points; the $60,000 initial investment and $15,400 a year pay back in 0.4 years and return $0.69M. The robotic bending cell is the recommended capital investment option: on top of the package it adds 2.2 points and returns $1.52M with a 2.0-year payback. | [report](https://brimsystems.github.io/mfg-operations-analytics/docs/reports/options_tested.html) |

**Dashboard.** [docs/dashboard/index.html](https://brimsystems.github.io/mfg-operations-analytics/docs/dashboard/index.html). Index of deliverables: [docs/index.html](https://brimsystems.github.io/mfg-operations-analytics/docs/index.html). The week of 15 December 2025 is the current week; every panel carries a one-line definition in the reports' wording.

## Methods

Operations analysis: lead-time decomposition and Little's Law; utilization and queue-time curves on the shop's own data; late-job attribution by stage against the stage's own normal; setup and standard variance by lot size and work center; a reproducible discrete-event model of the floor with 19 scenarios, replications and intervals; lead-time quoting from the actual distribution by routing class and load, evaluated out of sample; leading-indicator tests against shuffled and shifted chance series; ROI with payback and break-even analysis on stated assumptions.

Data engineering: raw system exports loaded to DuckDB; a dbt project with schema tests on every mart; one build command that regenerates every table, figure and page byte-identically from the committed inputs; fixed input ordering and per-scenario seeding so that the floor model reproduces to the digit.

Framing: the improvement projects are written as DMAIC projects. Every report describes the findings and what to do, in the form a client receives at the end of an engagement.

## Data

The record carries what these systems carry in practice: blank and miscoded late reasons, operations closed in batches at the end of a shift, standards not updated after routing changes, and a 2024 year-end build that shows in every queue. The analyses work with the record as it stands and say so where it limits a finding.

| System | Export | Tables | Grain | Batch |
|---|---|---|---|---|
| ERP | data/raw/erp/ (16 CSV files) | customers, export_batch, inventory_items, inventory_transactions, job_operations, jobs, order_lines, parts, po_lines, purchase_orders, quote_lines, quotes, routings, sales_orders, shipments, work_center_calendar | customer, part, routing operation, quote, quote line, sales order, order line, job, job operation, inventory item, inventory transaction, purchase order, PO line, shipment, work center and day, export batch | 20261012T153907Z-20250101 |
| Shop-floor data collection | data/raw/mes/ (6 CSV files) | holds, job_status_events, kit_checks, labor_transactions, laser_nests, powder_color_schedule | labor transaction, job status event, hold, kit check, laser nest, powder color and day | 20261012T153907Z-20250101 |
| QMS | data/raw/qms/ (2 CSV files) | ncrs, rework_ops | nonconformance, rework operation | 20261012T153907Z-20250101 |
| Maintenance | data/raw/maintenance/ (1 CSV file) | downtime_events | downtime event | 20261012T153907Z-20250101 |
| HR | data/raw/hr/ (2 CSV files) | attendance, employees | employee, employee and day | 20261012T153907Z-20250101 |

`pipeline/load` loads the CSV exports under `data/raw` into DuckDB with dlt, one text table per file. The dbt project under `pipeline/dbt` builds the staging models (one per export, typed), the intermediate models (working-day clock, machine time, queue, lead time by stage, WIP, utilization, setups, late-job attribution) and the marts, with tests on keys. The scripts under `analytics/` read the marts and write the three reports and their figures under `docs/`, the dashboard and this file. The shop model under `analytics/release_control/` replays the released jobs for the scenarios of the simulation report; its runs are saved under `results/` and each run repeats exactly from its scenario and replication number.

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
python -m analytics.release_control.scenarios 30 6
python -m analytics.technology_roi.scenarios 30 6
python -m analytics.technology_roi.scenarios 30 6 laser_queue
```

## Author

Brian Davis. Data engineering and applied analytics/ML for manufacturers. Other work: [github.com/brimsystems](https://github.com/brimsystems?tab=repositories).
