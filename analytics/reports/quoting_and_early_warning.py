"""Quoting and early warning from load: the report, from its two halves.

Usage: python -m analytics.reports.quoting_and_early_warning
"""
from analytics.quoting import sections as first
from analytics.leading_indicators import sections as second
from analytics.reports.combine import write


def main():
    write("quoting", first, second, ("Lead-time quoting and quote analytics", "Leading indicators"), lead="[[S:second]] cover the weekly measures tested as early warning of a decline in on-time delivery.", same_target=False, header=True)


if __name__ == "__main__":
    main()
