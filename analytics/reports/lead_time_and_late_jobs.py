"""Flow and on-time delivery: the report, from its two halves.

Usage: python -m analytics.reports.lead_time_and_late_jobs
"""
import re

from analytics.lead_time import sections as first
from analytics.late_jobs import sections as second
from analytics.reports.combine import write


ORDER = [("Work in Process", [3]), ("Lead Time", [1, 2]), ("Late Jobs", [4, 5])]
# appendix tables in the order the three sections use them: the number each carries as merged, and the number it takes
TABLES = [("5", "1"), ("6", "2"), ("7", "3"), ("1", "4"), ("5a", "5"), ("2a", "6a"), ("2b", "6b"), ("3", "7"), ("8", "8"), ("12", "9a"), ("13", "9b"),
          ("16", "10"), ("17", "11"), ("14", "12a"), ("15", "12b"), ("9", "13"), ("10", "14"), ("11", "15")]


def arrange(body, toc):
    """Three sections: work in process, lead time and late jobs, the last two with their parts under unnumbered headings; the appendix tables follow that order."""
    start = body.index("<h2 id='f1'>")
    end = body.index("<h2 id='appendix'>")
    parts = re.split(r"<h2 id='f(\d+)'>\d+\. (.*?)</h2>", body[start:end])
    old = {int(parts[k]): (parts[k + 1], parts[k + 2]) for k in range(1, len(parts), 3)}
    out, new_toc = [], []
    for n, (title, members) in enumerate(ORDER, 1):
        out.append(f"<h2 id='f{n}'>{n}. {title}</h2>")
        new_toc.append((f"f{n}", f"{n}. {title}"))
        if len(members) == 1:
            out.append(old[members[0]][1])
            continue
        for k, m in enumerate(members, 1):
            out.append(f"<h3 id='f{n}_{k}'>{old[m][0]}</h3>" + old[m][1])
    body = body[:start] + "\n".join(out) + body[end:]

    new = dict(TABLES)
    link = lambda t: f"<a href='#t{new[t]}'>{new[t]}</a>"
    body = re.sub(r"<a href='#t(\w+)'>\1</a>", lambda m: link(m.group(1)), body)
    body = re.sub(r"(Appendix Tables? )(\d+[a-z]?(?:(?:, | and | to )\d+[a-z]?)*)",
                  lambda m: m.group(1) + re.sub(r"\d+[a-z]?", lambda d: link(d.group(0)), m.group(2)), body)
    i, j = body.index("<h2 id='appendix'>"), body.index("<div class='glossary'>")
    blocks = re.split(r"(?=<h3 id='t)", body[i:j])
    held = {re.match(r"<h3 id='t(\w+)'>", x).group(1): x for x in blocks[1:]}
    assert sorted(held) == sorted(new), sorted(set(held) ^ set(new))
    tables = [re.sub(r"^<h3 id='t\w+'>Table \w+\.", f"<h3 id='t{to}'>Table {to}.", held[frm]) for frm, to in TABLES]
    body = body[:i] + blocks[0] + "".join(tables)          # the appendix ends at its last table, with no glossary lines
    return body, new_toc


def main():
    write("lead", first, second, ("Lead time decomposition", "Late jobs"), lead=None, same_target=False, header=False, arrange=arrange,
          heading="Report: Flow and On-time Delivery", closing=False)


if __name__ == "__main__":
    main()
