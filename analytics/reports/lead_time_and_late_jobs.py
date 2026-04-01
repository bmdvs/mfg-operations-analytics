"""Lead time and late jobs: the report, from its two halves.

Usage: python -m analytics.reports.lead_time_and_late_jobs
"""
import re

from analytics.lead_time import sections as first
from analytics.late_jobs import sections as second
from analytics.reports.combine import write


ORDER = [("Work in Process", [3]), ("Lead time", [1, 2]), ("Why jobs are late", [4, 5, 6, 7, 9, 8])]


def arrange(body, toc):
    """Three sections: work in process, lead time, and why jobs are late, the last two with the earlier sections as subsections under their own headings.
    The opening sentence on the two periods moves to the top of the first."""
    start = body.index("<h2 id='f1'>")
    end = body.index("<h2 id='rec'>")
    parts = re.split(r"<h2 id='f(\d+)'>\d+\. (.*?)</h2>", body[start:end])
    old = {int(parts[k]): (parts[k + 1], parts[k + 2]) for k in range(1, len(parts), 3)}
    short = {int(i[1:]): t for i, t in toc}
    opening = re.match(r"\s*<p>.*?</p>", old[1][1], flags=re.S).group(0)
    old[1] = (old[1][0], old[1][1].replace(opening, "", 1))
    out, new_toc = [], []
    for n, (title, members) in enumerate(ORDER, 1):
        out.append(f"<h2 id='f{n}'>{n}. {title}</h2>")
        new_toc.append((f"f{n}", title))
        if len(members) == 1:
            out.append(opening.strip() + old[members[0]][1] if n == 1 else old[members[0]][1])
            continue
        for k, m in enumerate(members, 1):
            out.append(f"<h3 id='f{n}_{k}'>{n}.{k} {old[m][0]}</h3>" + old[m][1])
            new_toc.append((f"f{n}_{k}", short[m], "sub"))
    return body[:start] + "\n".join(out) + body[end:], new_toc


def main():
    write("lead", first, second, ("Lead time decomposition", "Why jobs are late"), lead=None, same_target=False, header=False, arrange=arrange)


if __name__ == "__main__":
    main()
