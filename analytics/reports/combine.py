"""Two section builders as one report: sections, tables and figures numbered through, one recommendation, one method note, one appendix."""
import re

import pandas as pd

from analytics.style.style import DOCS, report_shell, table

REPORTS = {
    "lead": ("lead_time_and_late_jobs", "Flow and On-time Delivery", "the flow report"),
    "capacity": ("capacity_constraints_and_setups", "Capacity, Constraints and Setups", "the capacity report"),
    "options": ("options_tested", "Options Tested", "the options report"),
    "quoting": ("quoting_and_early_warning", "Quoting and Early Warning from Load", "the quoting report"),
}
SHOP = "Custom sheet-metal fabrication job shop, about 120 employees, one plant. "
TABLES = re.compile(r"\b(Tables?) (\d+[a-z]?(?:(?:, | and | to )\d+[a-z]?)*)")


def split(body):
    """A builder's page body as its sections, recommendation, method note, appendix tables and glossary line."""
    i, j, k = body.index("<h2 id='rec'>"), body.index("<h2 id='method'>"), body.index("<h2 id='appendix'>")
    strip = lambda s: re.sub(r"^<h2 id='\w+'>.*?</h2>", "", s, count=1, flags=re.S)
    appendix = strip(body[k:])
    g = re.search(r"<div class='glossary'>.*?</div>", appendix, flags=re.S)
    glossary = g.group(0) if g else ""
    return {"sections": body[:i], "rec": strip(body[i:j]), "method": strip(body[j:k]), "appendix": appendix.replace(glossary, ""), "glossary": glossary}


def shift_tables(s, by):
    one = lambda m: m.group(1) + " " + re.sub(r"\d+", lambda d: str(int(d.group(0)) + by), m.group(2))
    return TABLES.sub(one, s)


def shift_sections(s, by):
    return re.sub(r"<h2 id='f(\d+)'>(\d+)\. ", lambda m: f"<h2 id='f{int(m.group(1)) + by}'>{int(m.group(2)) + by}. ", s)


def chart_titles(s):
    """Each figure under a title, which is its alt text, with no numbered caption line."""
    s = re.sub(r"(<img alt=\"([^\"]*)\"[^>]*>)\s*<div class='caption'>Figure \d+\.[^<]*</div>", r"<div class='chart-title'>\2</div>\1", s)
    assert not re.search(r"Figure \d", s), re.findall(r".{60}Figure \d.{40}", s)[:3]
    return s


def table_anchors(s):
    return re.sub(r"<h3(?: id='[^']*')?>Table (\d+[a-z]?)\.", r"<h3 id='t\1'>Table \1.", s)


def unique_sentences(second, first):
    """The second method note without the sentences the first already states word for word."""
    dropped = []

    def keep(m):
        t = m.group(0)
        if len(t.strip()) > 40 and t.strip() in first:
            dropped.append(t.strip())
            return ""
        return t
    return re.sub(r"[^.<>]+(?:\.(?!\s|<|$)[^.<>]*)*\.(?:\s+|(?=<)|$)", keep, second), dropped


def references(body):
    """Another report by its full title at its first mention in the text, and by its short name after that and in every table cell; each a link."""
    seen = set()

    def one(m):
        kind, key = m.group(1), m.group(2)
        stem, title, short = REPORTS[key]
        before = body[:m.start()]
        in_cell = before.rfind("<td") > before.rfind("</td>")
        if kind == "R" and not in_cell and key not in seen:
            seen.add(key)
            return f"<a href='{stem}.html'>{title}</a>"
        opens = before.rstrip()[-1:] in (".", ">", "")
        return f"<a href='{stem}.html'>{short[0].upper() + short[1:] if opens else short}</a>"
    return re.sub(r"\[\[([RN]):(\w+)\]\]", one, body)


def write(key, first, second, titles, lead=None, same_target=False, header=True, arrange=None, heading=None, closing=True):
    stem, title, _ = REPORTS[key]
    a, b = first.report(), second.report()
    A, B = split(a["body"]), split(b["body"])
    n_sections = len(re.findall(r"<h2 id='f\d+'>", A["sections"]))
    n_second = len(re.findall(r"<h2 id='f\d+'>", B["sections"]))
    last_table = max(int(x) for x in re.findall(r"\bTable (\d+)", a["body"]))
    for part in B:
        B[part] = shift_tables(B[part], last_table)
    B["sections"] = shift_sections(B["sections"], n_sections)
    if lead:
        B["sections"] = re.sub(r"(<h2 id='f\d+'>.*?</h2>)", rf"\1\n<p class='lead'>{lead}</p>", B["sections"], count=1, flags=re.S)
    (t1, rows1, f1), (t2, rows2, f2) = first.control(), second.control()
    t2, f2 = shift_tables(t2, last_table), shift_tables(f2, last_table) if f2 else f2
    targets = f"<p>Target: {t1}</p>" + ("" if same_target else f"<p>Target: {t2}</p>")
    rows = pd.DataFrame(list(rows1) + [(shift_tables(x, last_table), o, w) for x, o, w in rows2], columns=["Action", "Owner", "When"])
    follow = "<p>Follow-up: " + " ".join(x for x in (f1, f2) if x) + "</p>"
    method2, dropped = unique_sentences(B["method"], A["method"])
    scope1 = scope2 = ""
    if not header:                       # no header block on the page: each half's scope and sources open its method note
        scope1, scope2 = f"<p>{a['meta']}</p>", f"<p>{b['meta'].replace(SHOP, '', 1)}</p>"
    ending = ["<h2 id='rec'>Recommendation</h2>", A["rec"], B["rec"], targets, table(rows), follow,
              "<h2 id='method'>Method and data</h2>", f"<h3>{titles[0]}</h3>", scope1, A["method"], f"<h3>{titles[1]}</h3>", scope2, method2]
    body = "\n".join([
        A["sections"], B["sections"], *(ending if closing else []),      # a report can end at its sections, with the appendix after them
        "<h2 id='appendix'>Appendix</h2>", table_anchors(A["appendix"]), table_anchors(B["appendix"]), A["glossary"], B["glossary"]])
    body = chart_titles(body)
    span = {"first": (1, n_sections), "second": (n_sections + 1, n_sections + n_second)}
    body = re.sub(r"\[\[S:(\w+)\]\]", lambda m: f"<a href='#f{span[m.group(1)][0]}'>Sections {span[m.group(1)][0]} to {span[m.group(1)][1]}</a>", body)
    body = references(body).replace("Q2 to Q4", "Q2-Q4")
    assert "[[" not in body
    sections_toc = list(a["toc"]) + [(f"f{int(i[1:]) + n_sections}", t) for i, t in b["toc"]]
    if arrange:
        body, sections_toc = arrange(body, sections_toc)
    toc = (sections_toc
           + ([("rec", "Recommendation"), ("method", "Method and data")] if closing else []) + [("appendix", "Appendix")])
    meta = ""
    if header:
        rest = b["meta"].replace(SHOP, "", 1)
        meta = (a["meta"] + ("<br>" + rest if rest and rest != a["meta"] else "")).replace("Q2 to Q4", "Q2-Q4")
    out = DOCS / "reports"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{stem}.html").write_text(report_shell(heading or title, "", meta, body, toc), encoding="utf8")
    print(f"wrote docs/reports/{stem}.html: sections 1 to {n_sections} and {n_sections + 1} to {n_sections + n_second}; tables of the second half moved up by {last_table}; "
          f"{len(rows)} countermeasures; method sentences stated once: {len(dropped)}")
    return dropped
