"""The brakes: capacity, utilization and setups: the report, from its two halves.

Usage: python -m analytics.reports.brakes_capacity_and_setups
"""
from analytics.constraint import sections as first
from analytics.setups import sections as second
from analytics.reports.combine import write


def main():
    write("brakes", first, second, ("The constraint, utilization and variability", "Setups and standards"), lead="[[S:second]] cover brake setups against their standards, and the run standards.", same_target=False, header=True)


if __name__ == "__main__":
    main()
