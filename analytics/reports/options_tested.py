"""Options tested: release rules, scheduling, shifts and equipment: the report, from its two halves.

Usage: python -m analytics.reports.options_tested
"""
from analytics.release_control import sections as first
from analytics.technology_roi import sections as second
from analytics.reports.combine import write


def main():
    write("options", first, second, ("Release control and the shop model", "Technology ROI"), lead="[[S:second]] cover the three capital options and the no-capital package on the same shop model, with payback and NPV.", same_target=True, header=True)


if __name__ == "__main__":
    main()
