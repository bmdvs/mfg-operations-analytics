# Manufacturing Operations Analytics: Metal Fabrication 

On-time delivery, lead time, and capacity analytics, built on the shop's complete ERP and MES record over the past three years (Jan. '23 to Dec. '25). A data pipeline was built to clean and merge the ERP and MES records. Analytics were then built on the following methodologies:  

**On-time delivery**
- Root cause analysis: attributes each late job's lost days to a driver (constraint queue, late release, material, outside processing), measured against on-time jobs of the same routing class using the shop's data record
- Chance-corrected agreement analysis: tests whether the shop's current late-reason codes adequately map to the root causes identified above
- Distribution analysis: measures how many days jobs ship early or late, revealing slack in the quoted dates as well as the extent of misses 
- Discrete event simulation: tests release, dispatch and capacity changes for their effect on on-time delivery, and analyzes those changes' NPV and ROI

**Lead time**
- Lead time decomposition: shows where lead time concentrates, stage by stage, between release and shipment  
- Forecast error analysis: measures how accurately the quoted lead time predicts actual lead time, and under which conditions it fails
- Out-of-sample validation: selects new lead time quoting rules that meet their target on data they were not fit to
- Little's Law analysis: links work in process to lead time, sets how much work the floor can hold within the quoted lead times

**Capacity**
- Capacity utilization analysis: shows how close each work center runs to its available hours
- Queueing curves: measure machine utilization against queue time to identify the constraints and maximum utilization levels at which queue time climbs steeply 
- Pareto analysis: shows where queue times concentrate by work center
- Lagged correlation analysis: separates load-driven from schedule-driven queue times
- Segmentation analysis: finds the conditions where machine setup times overrun their standards (lot size, shift handover, operator familiarity, part family) and estimates the queue time recovered by removing setup overrun
- Variance analysis (planned against actual): tests whether outdated standards understate the load

<br> 

Three reports were built: 

**[Flow and On-Time Delivery](https://brimsystems.github.io/mfg-operations-analytics/docs/reports/lead_time_and_late_jobs.html)** asks: why do jobs ship late, in what stages between release and shipment do late jobs lose time, and how well does the quoted lead time align with actual shipment dates? 

**[Capacity, Constraints and Setups](https://brimsystems.github.io/mfg-operations-analytics/docs/reports/capacity_constraints_and_setups.html)** asks: which machines are the shop's primary constraints, how does machine utilization levels impact queue time, and how much capacity is lost to setups and outdated standards? 

**[Discrete Event Simulation](https://brimsystems.github.io/mfg-operations-analytics/docs/reports/options_tested.html)** asks: which changes to release, dispatch, and capacity raise on-time delivery rates, and of those changes that work, which are the best investments to make?  

## Business context

The shop is a custom sheet-metal fabricator: about $25 million revenue, ISO 9001. It has 25 machines across 10 work centers: laser cutting, CNC punching, press brake forming, hardware insertion, robotic and manual welding, grind and deburr, powder coating, assembly and inspection. It has about 2,000 different active part numbers and runs over 5,000 jobs a year in lots from 1 to 500 pieces.  

The shop quotes lead times by routing class standards plus capacity adjustments, measures on-time delivery weekly, and records a late reason on each late job. In 2025 it delivered 80.8% of jobs on time. The late-reason codes did not explain the misses: a large share (36%) of late reasons were blank, and the coded ones pointed at the operation where the job was found late rather than where it lost the time. In Q1 2025, on-time delivery fell to 52.4%, which the shop saw as a press brake capacity problem. It weighed three capital options: replacing a press brake with an automatic tool-changing model, an automated sheet tower on a laser, and a robotic bending cell.

This project began by uncovering the root causes of late jobs, as detailed in the Flow and On-time Delivery and Capacity, Constraints, and Setup reports. Then, in the Discrete Event Simulation, options are tested to improve on-time delivery (the three capital options above, plus others) and determines which options represent are the best investment for the shop to make. 

## Data

The data record carries the standard quality issues found in ERP and MES systems in practice: blank and miscoded late reasons, operations closed in batches at the end of a shift, standards not updated after routing changes, and a 2024 year-end build that skews every queue for months after. The analyses work with the record as it stands and say so where it limits a finding.

| System | Export | Tables | Grain | Batch |
|---|---|---|---|---|
| ERP | data/raw/erp/ (16 CSV files) | customers, export_batch, inventory_items, inventory_transactions, job_operations, jobs, order_lines, parts, po_lines, purchase_orders, quote_lines, quotes, routings, sales_orders, shipments, work_center_calendar | customer, part, routing operation, quote, quote line, sales order, order line, job, job operation, inventory item, inventory transaction, purchase order, PO line, shipment, work center and day, export batch | 20261012T153907Z-20250101 |
| Shop-floor data collection | data/raw/mes/ (6 CSV files) | holds, job_status_events, kit_checks, labor_transactions, laser_nests, powder_color_schedule | labor transaction, job status event, hold, kit check, laser nest, powder color and day | 20261012T153907Z-20250101 |
| QMS | data/raw/qms/ (2 CSV files) | ncrs, rework_ops | nonconformance, rework operation | 20261012T153907Z-20250101 |
| Maintenance | data/raw/maintenance/ (1 CSV file) | downtime_events | downtime event | 20261012T153907Z-20250101 |
| HR | data/raw/hr/ (2 CSV files) | attendance, employees | employee, employee and day | 20261012T153907Z-20250101 |

`pipeline/load` loads the CSV exports under `data/raw` into DuckDB with dlt, one text table per file. The dbt project under `pipeline/dbt` builds the staging models (one per export, typed), the intermediate models (working-day clock, machine time, queue, lead time by stage, WIP, utilization, setups, late-job attribution) and the marts, with tests on keys. The scripts under `analytics/` read the marts and write the three reports and their figures under `docs/`, and this file. The shop model under `analytics/release_control/` replays the released jobs for the scenarios of the simulation report; its runs are saved under `results/` and each run repeats exactly from its scenario and replication number.

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
