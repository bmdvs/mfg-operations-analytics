"""Build every deliverable from the marts and the saved model runs: the four reports, the dashboard, the README and the index.

Usage: python -m analytics.build_all
"""
import subprocess
import sys

MODULES = ["analytics.reports.lead_time_and_late_jobs", "analytics.reports.brakes_capacity_and_setups", "analytics.reports.options_tested",
           "analytics.reports.quoting_and_early_warning", "analytics.dashboard.build", "analytics.readme_image", "analytics.site"]


def main():
    for m in MODULES:
        print(m, flush=True)
        subprocess.run([sys.executable, "-m", m], check=True)


if __name__ == "__main__":
    main()
