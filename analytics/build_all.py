"""Build every deliverable from the marts and the saved model runs: the eight reports and A3s, the dashboard, the README and the index.

Usage: python -m analytics.build_all
"""
import subprocess
import sys

MODULES = ["analytics.p1_lead_time.build", "analytics.p2_late_jobs.build", "analytics.p3_constraint.build", "analytics.p4_setups.build",
           "analytics.p5_release_control.build", "analytics.p6_leading_indicators.build", "analytics.p7_quoting.build", "analytics.p8_technology_roi.build",
           "analytics.dashboard.build", "analytics.readme_image", "analytics.site"]


def main():
    for m in MODULES:
        print(m, flush=True)
        subprocess.run([sys.executable, "-m", m], check=True)


if __name__ == "__main__":
    main()
