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
SHOP = "Custom sheet-metal fabrication job shop, about 120 employees, one plant."
SCOPE = "Eight improvement projects and an operations dashboard on the shop's records from January 2023 to December 2025."

# project, file stem, title, question, (finding section id, sentence number) of the headline
PROJECTS = [
    ("P1", "p1_lead_time", "Lead time decomposition", "Where does the lead time go, and does the floor's WIP match the quoted lead times?", ("f1", 0)),
    ("P2", "p2_late_jobs", "Why jobs are late", "What makes jobs late, and do the shop's late-reason codes say so?", ("f2", 0)),
    ("P3", "p3_constraint", "The constraint, utilization and variability", "Which work center is the constraint, and how does its queue respond to load?", ("f1", 0)),
    ("P4", "p4_setups", "Setups and standards", "What do setups cost at the brakes, and where is the overrun?", ("f1", 0)),
    ("P5", "p5_release_control", "Release control and the shop model", "Do release control and dispatch rules help, and what does?", ("f9", 1)),
    ("P6", "p6_leading_indicators", "Leading indicators", "Which weekly measures move before on-time delivery does?", ("f2", 0)),
    ("P7", "p7_quoting", "Lead-time quoting and quote analytics", "What lead time should be quoted, and what wins quotes?", ("f3", 0)),
    ("P8", "p8_technology_roi", "Technology ROI", "Do the capital options pay back?", ("f6", 0)),
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


def finding(stem, section, k):
    s = (DOCS / "reports" / f"{stem}.html").read_text(encoding="utf8")
    m = re.search(rf"<h2 id='{section}'>.*?</h2>\s*<p>(.*?)</p>", s, flags=re.S)
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", m.group(1)))).strip()
    out = sentences(text)[k].strip()
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
            "late-job attribution) and the marts, with tests on keys. The scripts under `analytics/` read the marts and write each project's report, A3 and figures "
            "under `docs/`, the dashboard and this file. The shop model under `analytics/p5_release_control/` replays the released jobs for the scenarios of P5 and "
            "P8; its runs are saved under `results/` and each run repeats exactly from its scenario and replication number.")
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
python -m analytics.p5_release_control.scenarios 30 6
python -m analytics.p8_technology_roi.scenarios 30 6
python -m analytics.p8_technology_roi.scenarios 30 6 laser_queue
```"""


def readme():
    lines = ["# Operations analytics for a sheet-metal job shop", "", SHOP + "  ", SCOPE, "", "## Projects", "",
             "| Project | Question | Finding | Deliverable |", "|---|---|---|---|"]
    for p, stem, title, question, (sec, k) in PROJECTS:
        lines.append(f"| {p}. {title} | {question} | {finding(stem, sec, k)} | [report](docs/reports/{stem}.html), [A3](docs/a3/{stem}.html) |")
    lines += ["", "Dashboard: [docs/dashboard/index.html](docs/dashboard/index.html). Index of deliverables: [docs/index.html](docs/index.html).", "",
              "## Data sources", "", "| System | Export | Tables | Grain | Batch |", "|---|---|---|---|---|"]
    lines += ["| " + " | ".join(r) + " |" for r in sources()]
    lines += ["", "## Pipeline", "", PIPELINE, "", "## How to run", "", "Python 3.11 or later, from a clean clone:", "", RUN, "",
              "`analytics.build_all` uses the saved model runs. To repeat the runs (several hours on six processes):", "", RERUN, ""]
    (ROOT / "README.md").write_text("\n".join(lines), encoding="utf8")


def index():
    rows = []
    for p, stem, title, question, (sec, k) in PROJECTS:
        rows.append([f"{p}. {title}", question, finding(stem, sec, k), f"<a href='reports/{stem}.html'>Report</a>", f"<a href='a3/{stem}.html'>A3</a>"])
    body = (table(pd.DataFrame(rows, columns=["Project", "Question", "Finding", "Report", "A3"])) +
            "<p><a href='dashboard/index.html'>Operations dashboard</a></p>")
    meta = f"{SHOP}<br>{SCOPE} Sources: ERP, shop-floor data collection, QMS, maintenance and HR exports (batch {batch_id()})."
    (DOCS / "index.html").write_text(shell("Operations analytics", "Deliverables", meta, body), encoding="utf8")


def main():
    readme()
    index()
    print("wrote README.md and docs/index.html")


if __name__ == "__main__":
    main()
