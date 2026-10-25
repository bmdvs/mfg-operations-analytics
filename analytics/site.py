"""README.md and docs/index.html: the project table with each report's headline sentence, the data sources and the links.

Usage: python -m analytics.site
The finding of each project is a sentence taken from its report under docs/reports, so the reports are built first.
"""
import csv
import html
import re
from pathlib import Path

import pandas as pd

from analytics.style.style import DOCS, shell, table

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PAGES = "https://bmdvs.github.io/mfg-operations-analytics/"          # where the pages under docs/ are served
SHOP = "Custom sheet-metal fabrication job shop, about 120 employees, one plant."
SCOPE = "Eight improvement projects and an operations dashboard on the shop's records from January 2023 to December 2025."

def page_links(text):
    """Links to the pages under docs/ as their served addresses, so they open the page and not its source."""
    return re.sub(r"\]\((docs/[^)]+\.html)\)", lambda m: f"]({PAGES}{m.group(1)})", text)


LEAD, CAPACITY, OPTIONS = "lead_time_and_late_jobs", "capacity_constraints_and_setups", "options_tested"


def _lead_time():
    share, late, on_time = re.search(r"the brake queue was ([\d.]+%) of all jobs' lead time .*?: ([\d.]+) days against ([\d.]+) for on-time jobs\.",
                                     section_text(LEAD, "f3_2")).groups()
    median, quote, rest = re.search(r"shipped in ([\d.]+) working days vs\. an average quoted lead time of ([\d.]+); in Q2-Q4, it was ([\d.]+) vs\.",
                                    section_text(LEAD, "f2_2")).groups()
    causes = re.search(r"In 2025, jobs waiting at work centers .*? respectively\.", section_text(LEAD, "f3_3")).group(0)
    quoting = re.search(r"The shop's quoted lead time was off .*? in both directions\.", section_text(LEAD, "f4")).group(0)
    return (f"Queue at the brakes is {share} of lead time and the stage that separates late jobs from on-time jobs ({late} days against {on_time}); the median job "
            f"ships in {median} working days against an average quoted lead time of {quote}, {rest} in Q2-Q4. " + causes + " " + quoting)


def _capacity():
    load = re.search(r"In 2025, the press brakes ran at .*? the smallest of all work centers\.", section_text(CAPACITY, "f1_1")).group(0)
    week, points = re.search(r"Setups over standard are not: ([\d,]+) hours a week, which is ([\d.]+) points of brake utilization", section_text(CAPACITY, "f3")).groups()
    over = re.search(r"Setups over standard on the brakes ran ([\d,]+) hours in 2025", section_text(CAPACITY, "f3_1")).group(1)
    return f"{load} Brake setups ran {over} hours over standard in 2025, {week} a week, {points} points of brake utilization."


def _options():
    results = section_text(OPTIONS, "f2")
    lead = re.search(r"Scenarios that added brake capacity improved on-time delivery\.", results).group(0) + " " + re.search(
        r"Among the release and dispatch rules, only earliest due date improved on-time delivery\.", results).group(0)
    package = re.search(r"The .Operating Package. combines .*? points to on-time delivery\.", results).group(0)
    money = re.search(r"The operating package is recommended first ?: .*? and return \$[\d.]+M\.", section_text(OPTIONS, "f3")).group(0) + " " + re.search(
        r"The robotic bending cell is the recommended capital investment option ?: .*?-year payback\.", section_text(OPTIONS, "f3")).group(0)
    money = money.replace(" :", ":")
    return f"{lead} {package} {money}"


# file stem, title, question, the finding composed from the report's sentences
REPORTS = [
    (LEAD, "Flow and On-time Delivery",
     "Where does the lead time go, and does the floor's WIP match the quoted lead times? What makes jobs late, and do the shop's late-reason codes say so? What lead "
     "time should be quoted in a build, and which measures warn of a decline?", _lead_time),
    (CAPACITY, "Capacity, Constraints and Setups",
     "Which work centers run hot, and how do their queues respond to load? What do setups cost at the brakes, and where is the overrun?", _capacity),
    (OPTIONS, "Discrete Event Simulation: On-time Delivery",
     "Do release and dispatch rules raise on-time delivery, or only added brake hours? What do the changes that work cost and return?", _options),
]
SYSTEMS = [
    ("erp", "ERP", "customer, part, routing operation, quote, quote line, sales order, order line, job, job operation, inventory item, inventory transaction, "
                   "purchase order, PO line, shipment, work center and day, export batch"),
    ("mes", "Shop-floor data collection", "labor transaction, job status event, hold, kit check, laser nest, powder color and day"),
    ("qms", "QMS", "nonconformance, rework operation"),
    ("maintenance", "Maintenance", "downtime event"),
    ("hr", "HR", "employee, employee and day"),
]


def sentences(text):
    return re.split(r"(?<=[a-z0-9\)%])\. (?=[A-Z\"])", text)


def report_text(stem, section):
    s = (DOCS / "reports" / f"{stem}.html").read_text(encoding="utf8")
    m = re.search(rf"<h[23] id='{section}'>.*?</h[23]>\s*(?:<p class='lead'>.*?</p>\s*)?<p>(.*?)</p>", s, flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", m.group(1)))).strip()


def section_text(stem, section):
    """Every paragraph of a report section as one line of text."""
    s = (DOCS / "reports" / f"{stem}.html").read_text(encoding="utf8")
    m = re.search(rf"<h[23] id='{section}'>.*?</h[23]>(.*?)(?=<h[23] id=|$)", s, flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", " ".join(re.findall(r"<p>(.*?)</p>", m.group(1), flags=re.S))))).strip()


def finding(stem, section, k):
    out = sentences(report_text(stem, section))[k].strip()
    return out if out.endswith(".") else out + "."


def batch_id():
    with open(RAW / "erp" / "export_batch.csv", newline="", encoding="utf8") as f:
        return next(csv.DictReader(f))["export_batch_id"]


def sources():
    b = batch_id()
    rows = []
    for folder, name, grain in SYSTEMS:
        files = sorted(p.stem for p in (RAW / folder).glob("*.csv"))
        rows.append([name, f"data/raw/{folder}/ ({len(files)} CSV file{'s' if len(files) > 1 else ''})", ", ".join(files), grain, b])
    return rows


PIPELINE = ("`pipeline/load` loads the CSV exports under `data/raw` into DuckDB with dlt, one text table per file. The dbt project under `pipeline/dbt` builds the "
            "staging models (one per export, typed), the intermediate models (working-day clock, machine time, queue, lead time by stage, WIP, utilization, setups, "
            "late-job attribution) and the marts, with tests on keys. The scripts under `analytics/` read the marts and write the three reports and their figures "
            "under `docs/`, and this file. The shop model under `analytics/release_control/` replays the released jobs for the scenarios of the simulation report; "
            "its runs are saved under `results/` and each run repeats exactly from its scenario and replication number.")
RUN = """```
python -m venv .venv
.venv\\Scripts\\activate            # Windows; on Linux or macOS: source .venv/bin/activate
pip install -e .
python -m pipeline.load.load_exports
cd pipeline/dbt
dbt build --profiles-dir .
cd ../..
python -m analytics.build_all
```"""
RERUN = """```
python -m analytics.release_control.scenarios 30 6
python -m analytics.technology_roi.scenarios 30 6
python -m analytics.technology_roi.scenarios 30 6 laser_queue
```"""


INTRO = ("Three client reports on a custom sheet-metal fabrication job shop, built on its complete ERP and MES record for January 2023 to December 2025. Flow and On-time Delivery "
         "traces where lead time goes between release and shipment, attributes each late job's lost days to the stage that lost them, and measures how accurately the shop's quote "
         "predicts lead time. Capacity, Constraints and Setups identifies the press brakes as the shop's constraint and measures what setups over standard cost them. Discrete Event "
         "Simulation: On-time Delivery replays the shop's jobs on a validated model of the floor, tests 16 release, dispatch and capacity changes, and sets the cost, NPV and payback of "
         "those that work against their gain in on-time delivery.")
INCLUDED = [
    "A data pipeline from raw system exports to analysis-ready marts: DuckDB, dbt with schema tests, one build command that regenerates every table, figure and page byte-identically.",
]
# the question and the finding of each report as the README states them, by file stem
README_REPORTS = {
    LEAD: ("Where does lead time go, why are jobs late, and how accurate is the quoted lead time?",
           "Queue at the press brakes is 24% of lead time and where late jobs lose the most time (5.76 days against 2.50 for on-time jobs). Waiting at work centers caused 42% of the "
           "3,473 days lost in 2025 and late release 21%, and 36% of late jobs carry no reason code. The quote misses actual lead time by 4.8 days on average: too long in ordinary "
           "months, too short in the year-end build."),
    CAPACITY: ("Which work center sets lead time, and what do brake setups cost?",
               "The press brakes are the constraint: 91% utilized against 97% uptime, a buffer of 6 points, and 53% of queue time. Brake setups ran 1,847 hours over standard in 2025, "
               "36 hours a week or 10.4 points of brake utilization."),
    OPTIONS: ("Which changes raise on-time delivery, and what do they cost and return?",
              "Only changes that add brake capacity move on-time delivery materially; release and dispatch rules add at most 1.9 points. The operating package, a brake setup program "
              "plus planned Saturdays on both brakes, raises 2025 on-time delivery 7.7 points to 87.9% for $60,000 once, with a 0.4-year payback. A robotic bending cell adds 2.2 "
              "points on top, with an NPV of $1.52M and a 2.0-year payback. The model reproduces all ten validation measures within tolerance."),
}
CONTEXT = [
    "The shop is a custom sheet-metal fabricator: about 120 employees, ISO 9001, one plant, about 2,000 active part numbers, 450 customers, about 5,200 jobs a year in lots from 1 to 500 pieces. Laser "
    "cutting, CNC punching, press brake forming, hardware insertion, welding, powder coating and light assembly in house; plating, anodizing and heat treat at outside vendors. Two shifts on the "
    "lasers and brakes, one elsewhere, Saturdays when behind.",
    "The shop quotes a fixed lead time by routing class, measures on-time delivery weekly, and records a late reason on each late job. In 2025 it delivered 80.8% on time. The late-reason codes did "
    "not explain the misses: a large share (36%) of late reasons were blank, and the coded ones pointed at the operation where the job was found late rather than where it lost the time. A first-quarter decline that "
    "year was felt on the floor as a brake-capacity problem, and the shop was weighing three capital options: replacing a press brake with an automatic tool-changing model, an automated sheet tower on a laser, and a robotic bending cell.",
    "The engagement put the ERP order and quote records beside the MES operation timestamps for three years, every job and every operation, to answer what the reports could not: where lead time "
    "goes, which stage each late job lost its days at, which work center sets the lead time and what variability at it costs, what lead time the shop "
    "should quote at its current load, and which of the capital options pays back on measured hours. The three reports below are the result.",
]
METHODS = [
    "Lead-time decomposition by stage and Little's Law; late-job attribution of lost days by stage against the stage's own normal, checked against the shop's reason codes; utilization and "
    "queue-time curves by work center; setup against standard by lot size and work center; quote accuracy by condition at release, with a candidate quote evaluated out of sample; a discrete "
    "event model of the floor validated against ten measures set before it was run, testing 16 changes and combinations over 30 runs each with 95% intervals; NPV, payback and break-even on "
    "stated assumptions.",
    "Data engineering: raw system exports loaded to DuckDB; a dbt project with schema tests on every mart; one build command that regenerates every table, figure and page byte-identically from "
    "the committed inputs; fixed input ordering and per-scenario seeding so that the floor model reproduces to the digit.",
]
RECORD = ("The record carries what these systems carry in practice: blank and miscoded late reasons, operations closed in batches at the end of a shift, standards not updated after routing "
          "changes, and a 2024 year-end build that shows in every queue. The analyses work with the record as it stands and say so where it limits a finding.")
AUTHOR = "Brian Davis. Data engineering and applied analytics/ML for manufacturers. Other work: [github.com/bmdvs](https://github.com/bmdvs?tab=repositories)."


# the images at the top of the README, written by analytics.readme_image: file and chart title
IMAGES = [("job_flow.png", "Job Flow, Release to Shipment"), ("lead_time_decomposition.png", "Lead Time Decomposition by Stage, 2025 and Q2-Q4"),
          ("queue_by_work_center.png", "Queue Time per Operation by Work Center, 2025"),
          ("scenario_results.png", "Scenario Results: Change in On-time Delivery vs. Status Quo, 2025"),
          ("recommended_scenarios.png", "On-time Delivery, Status Quo vs. Recommended Scenarios, 2025")]


def readme():
    lines = ["# mfg-operations-analytics", "", INTRO, ""]
    lines += [f"- {x}" for x in INCLUDED]
    lines += [""]
    for name, title in IMAGES:
        lines += [f"![{title}](docs/readme/{name})", ""]
    lines += ["## Business context", ""]
    for x in CONTEXT:
        lines += [x, ""]
    lines += ["## Reports", "", "| Report | Question | Finding | Deliverable |", "|---|---|---|---|"]
    for stem, title, _, _ in REPORTS:
        question, found = README_REPORTS[stem]
        lines.append(f"| {title} | {question} | {found} | [report](docs/reports/{stem}.html) |")
    lines += ["", "Index of deliverables: [docs/index.html](docs/index.html).", "", "## Methods", ""]
    for x in METHODS:
        lines += [x, ""]
    lines += ["## Data", "", RECORD, "", "| System | Export | Tables | Grain | Batch |", "|---|---|---|---|---|"]
    lines += ["| " + " | ".join(r) + " |" for r in sources()]
    lines += ["", PIPELINE, "", "## How to run", "", "Python 3.12 or later, from a clean clone:", "", RUN, "",
              "`analytics.build_all` uses the saved model runs. To repeat the runs (several hours on six processes):", "", RERUN, "", "## Author", "", AUTHOR, ""]
    (ROOT / "README.md").write_text(page_links("\n".join(lines)), encoding="utf8")


def index():
    rows = []
    for stem, title, question, spec in REPORTS:
        rows.append([title, question, spec(), f"<a href='reports/{stem}.html'>Report</a>"])
    body = (table(pd.DataFrame(rows, columns=["Report", "Question", "Finding", "Deliverable"])) +
            "<p><a href='dashboard/index.html'>Operations dashboard</a></p>")
    meta = f"{SHOP}<br>{SCOPE} Sources: ERP, shop-floor data collection, QMS, maintenance and HR exports (batch {batch_id()})."
    (DOCS / "index.html").write_text(shell("Operations analytics", "Deliverables", meta, body), encoding="utf8")


def main():
    readme()
    index()
    print("wrote README.md and docs/index.html")


if __name__ == "__main__":
    main()
