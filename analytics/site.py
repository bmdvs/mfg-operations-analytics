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
PAGES = "https://brimsystems.github.io/mfg-operations-analytics/"          # where the pages under docs/ are served
SHOP = "Custom sheet-metal fabrication job shop, about 120 employees, one plant."
SCOPE = "Eight improvement projects and an operations dashboard on the shop's records from January 2023 to December 2025."

def page_links(text):
    """Links to the pages under docs/ as their served addresses, so they open the page and not its source."""
    return re.sub(r"\]\((docs/[^)]+\.html)\)", lambda m: f"]({PAGES}{m.group(1)})", text)


LEAD, BRAKES, OPTIONS, QUOTING = "lead_time_and_late_jobs", "brakes_capacity_and_setups", "options_tested", "quoting_and_early_warning"


def _lead_time():
    share, late, on_time = re.search(r"the brake queue was ([\d.]+%) of all jobs' lead time .*?: ([\d.]+) days against ([\d.]+) for on-time jobs\.",
                                     report_text(LEAD, "f2_2")).groups()
    median, quote, rest = re.search(r"shipped in ([\d.]+) working days vs\. an average quoted lead time of ([\d.]+); in Q2-Q4, it was ([\d.]+) vs\.",
                                    section_text(LEAD, "f2_1")).groups()
    causes = re.search(r"In 2025, jobs waiting at work centers .*? respectively\.", section_text(LEAD, "f3_1")).group(0)
    return (f"Queue at the brakes is {share} of lead time and the stage that separates late jobs from on-time jobs ({late} days against {on_time}); the median job "
            f"ships in {median} working days against an average quoted lead time of {quote}, {rest} in Q2-Q4. " + causes)


def _brakes():
    return finding(BRAKES, "f1", 0) + " " + finding(BRAKES, "f8", 0)


def _options():
    t = finding(OPTIONS, "f9", 1)
    year, gain, rest = re.search(r"takes the year to ([\d.]+%) on time, up ([\d.]+ points \([\d.]+ to [\d.]+\)).*Q2-Q4 reaches ([\d.]+%)", t).groups()
    t = finding(OPTIONS, "f15", 1)
    cell, changer = re.search(r"robotic cell pays back in ([\d.]+) years, the tool changer on B3 in ([\d.]+), the tower not at all", t).groups()
    return (f"A WIP cap and dispatch rules do not help; the setup program, a second shift on the robotic weld cell and planned Saturdays from November through "
            f"February take the year to {year} on time, up {gain}, and Q2-Q4 to {rest}. " + finding(OPTIONS, "f15", 0) +
            f" With half the released brake hours sold, the robotic cell pays back in {cell} years, the tool changer on B3 in {changer}, the laser tower not at all.")


def _quoting():
    t = finding(QUOTING, "f3", 0)
    y, r, fy, fr, ly, lr = re.search(r"is met on ([\d.]+%) of non-rush jobs for the year and ([\d.]+%) in Q2-Q4 .* against ([\d.]+%) and ([\d.]+%) for the fixed "
                                     r"quote; it is longer than the fixed quote on ([\d.]+%) and ([\d.]+%)", t).groups()
    assert "moved before all four" in report_text(QUOTING, "f13")
    return (f"The fixed quote is met on {fy} of non-rush jobs for the year and {fr} in Q2-Q4; a quote by routing class and brake backlog at release, never below "
            f"the fixed quote, is met on {y} and {r} out of sample and lengthens {ly} and {lr} of promises. " + finding(QUOTING, "f11", 0) +
            " It moved before all four declines in on-time delivery; no other weekly measure leads in ordinary weeks.")


# file stem, title, question, the finding composed from the report's sentences
REPORTS = [
    (LEAD, "Flow and On-time Delivery",
     "Where does the lead time go, and does the floor's WIP match the quoted lead times? What makes jobs late, and do the shop's late-reason codes say so?", _lead_time),
    (BRAKES, "The brakes: capacity, utilization and setups",
     "Which work center is the constraint, and how does its queue respond to load? What do setups cost at the brakes, and where is the overrun?", _brakes),
    (OPTIONS, "Options tested: release rules, scheduling, shifts and equipment",
     "Do release control and dispatch rules help, and what does? Do the capital options pay back?", _options),
    (QUOTING, "Quoting and early warning from load",
     "What lead time should be quoted, and what wins quotes? Which weekly measures move before on-time delivery does?", _quoting),
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
            "late-job attribution) and the marts, with tests on keys. The scripts under `analytics/` read the marts and write the four reports and their figures "
            "under `docs/`, the dashboard and this file. The shop model under `analytics/release_control/` replays the released jobs for the scenarios of the options report; "
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


INTRO = ("Delivery, flow, capacity and quoting analytics on a custom sheet-metal fabrication job shop, January 2023 to December 2025, computed on the shop's complete ERP and MES record.")
INCLUDED = [
    "Eight connected studies, each delivered as a client report: lead-time decomposition, late-job attribution, the constraint and variability, setups "
    "against standards, release control on a discrete-event model of the floor, leading indicators, lead-time quoting and quote analytics, technology ROI.",
    "One operations dashboard: on-time delivery, lead time, WIP, utilization and queue by work center, setup against standard, overtime, the leading indicators; weekly grain, 13-week view, "
    "three-year trend.",
    "A data pipeline from raw system exports to analysis-ready marts: DuckDB, dbt with schema tests, one build command that regenerates every table, figure and page byte-identically.",
]
CONTEXT = [
    "The shop is a custom sheet-metal fabricator: about 120 employees, ISO 9001, one plant, about 2,000 active part numbers, 450 customers, about 5,200 jobs a year in lots from 1 to 500 pieces. Laser "
    "cutting, CNC punching, press brake forming, hardware insertion, welding, powder coating and light assembly in house; plating, anodizing and heat treat at outside vendors. Two shifts on the "
    "lasers and brakes, one elsewhere, Saturdays when behind.",
    "The shop quotes a fixed lead time by routing class, measures on-time delivery weekly, and records a late reason on each late job. In 2025 it delivered 76.6% on time. The late-reason codes did "
    "not explain the misses: a large share (36%) of late reasons were blank, and the coded ones pointed at the operation where the job was found late rather than where it lost the time. A first-quarter decline that "
    "year was felt on the floor as a brake-capacity problem, and the shop was weighing a second press brake with automatic tooling against a laser tower and a bending cell.",
    "The engagement put the ERP order and quote records beside the MES operation timestamps for three years, every job and every operation, to answer what the reports could not: where lead time "
    "goes, which stage each late job lost its days at, which work center sets the lead time and what variability at it costs, which indicators move before delivery slips, what lead time the shop "
    "should quote at its current load, and which of the capital options pays back on measured hours. The studies below are the result, in the order they were built.",
]
METHODS = [
    "Operations analysis: lead-time decomposition and Little's Law; utilization and queue-time curves on the shop's own data; late-job attribution by stage against the stage's own normal; setup "
    "and standard variance by lot size and work center; a reproducible discrete-event model of the floor with 19 scenarios, replications and intervals; lead-time quoting from the actual "
    "distribution by routing class and load, evaluated out of sample; leading-indicator tests against shuffled and shifted chance series; ROI with payback and break-even analysis on stated "
    "assumptions.",
    "Data engineering: raw system exports loaded to DuckDB; a dbt project with schema tests on every mart; one build command that regenerates every table, figure and page byte-identically from "
    "the committed inputs; fixed input ordering and per-scenario seeding so that the floor model reproduces to the digit.",
    "Framing: the improvement projects are written as DMAIC projects. Every report describes the findings and what to do, in the form a client receives at the end of an engagement.",
]
RECORD = ("The record carries what these systems carry in practice: blank and miscoded late reasons, operations closed in batches at the end of a shift, standards not updated after routing "
          "changes, and a 2024 year-end build that shows in every queue. The analyses work with the record as it stands and say so where it limits a finding.")
AUTHOR = "Brian Davis. Data engineering and applied analytics/ML for manufacturers. Other work: [github.com/brimsystems](https://github.com/brimsystems?tab=repositories)."


def current_week():
    """The current week as the dashboard header states it."""
    meta = (DOCS / "dashboard" / "index.html").read_text(encoding="utf8")
    name, day, year = re.search(r"Week of (\w+) (\d+), (\d{4}) \(current week", meta).groups()
    return f"{int(day)} {name} {year}"


def readme():
    lines = ["# mfg-operations-analytics", "", INTRO, "", "![Operations dashboard](docs/readme/dashboard.png)", "", "## What is included", ""]
    lines += [f"- {x}" for x in INCLUDED]
    lines += ["", "## Business context", ""]
    for x in CONTEXT:
        lines += [x, ""]
    lines += ["## Studies", "", "| Report | Question | Finding | Deliverable |", "|---|---|---|---|"]
    for stem, title, question, spec in REPORTS:
        lines.append(f"| {title} | {question} | {spec()} | [report](docs/reports/{stem}.html) |")
    lines += ["", "**Dashboard.** [docs/dashboard/index.html](docs/dashboard/index.html). Index of deliverables: [docs/index.html](docs/index.html). "
              f"The week of {current_week()} is the current week; every panel carries a one-line definition in the reports' wording.", "", "## Methods", ""]
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
