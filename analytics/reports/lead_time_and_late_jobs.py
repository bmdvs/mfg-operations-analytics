"""Lead time and late jobs: the report, from its two halves.

Usage: python -m analytics.reports.lead_time_and_late_jobs
"""
from analytics.lead_time import sections as first
from analytics.late_jobs import sections as second
from analytics.reports.combine import write


def main():
    write("lead", first, second, ("Lead time decomposition", "Why jobs are late"), lead=None, same_target=False, header=False)


if __name__ == "__main__":
    main()
