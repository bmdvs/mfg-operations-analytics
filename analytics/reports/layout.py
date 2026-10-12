"""What the report renderers share: appendix tables numbered by first reference, links to the other reports, chart titles and the page."""
from analytics.reports.combine import REPORTS
from analytics.style.style import DOCS, report_shell

REST, RT = "Q2 to Q4", "Q2-Q4"


def link(key, text=None, anchor=None):
    """Another report by its title, or by the text given, as a link; to a section of it when an anchor is given."""
    stem, title, _ = REPORTS[key]
    return f"<a href='{stem}.html{'#' + anchor if anchor else ''}'>{text or title}</a>"


def join_and(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


class Tables:
    """The appendix tables, numbered in the order the text first refers to them; each is linked once, by `see`."""

    def __init__(self, start=0):
        self.held, self.order, self.linked, self.start = {}, [], set(), start          # start: tables already numbered ahead of these

    def add(self, key, title, html):
        self.held[key] = (title, html)

    def reserve(self, *keys):
        for k in keys:
            assert k in self.held, k
            if k not in self.order:
                self.order.append(k)

    def number(self, key):
        self.reserve(key)
        return self.start + self.order.index(key) + 1

    def plain(self, key):
        """The table by its number, without a link: for a mention apart from the sentence that links it."""
        return f"Table {self.number(key)}"

    def see(self, *keys, again=()):
        """The sentence that links the tables in `keys`; tables in `again`, linked earlier, are named in it by number alone."""
        self.reserve(*keys)
        assert not self.linked & set(keys) and set(again) <= self.linked, (keys, again)
        self.linked |= set(keys)
        cited = sorted([(self.number(k), True) for k in keys] + [(self.number(k), False) for k in again])
        links = [f"<a href='#t{n}'>{n}</a>" if new else str(n) for n, new in cited]
        return f"See Appendix Table{'s' if len(links) > 1 else ''} {join_and(links)} for additional detail."

    def span(self, *keys):
        """The sentence for a run of tables, named by its first and last numbers."""
        self.reserve(*keys)
        assert not self.linked & set(keys), keys
        self.linked |= set(keys)
        n = [self.number(k) for k in keys]
        assert len(n) > 2 and n == list(range(n[0], n[0] + len(n))), n
        return f"See Appendix Tables <a href='#t{n[0]}'>{n[0]}</a> to <a href='#t{n[-1]}'>{n[-1]}</a> for additional detail."

    def cite(self, *keys):
        """The tables in `keys` linked inside a sentence, where `see` would be a sentence of its own."""
        self.reserve(*keys)
        assert not self.linked & set(keys), keys
        self.linked |= set(keys)
        links = [f"<a href='#t{self.number(k)}'>{self.number(k)}</a>" for k in keys]
        return f"Appendix Table{'s' if len(links) > 1 else ''} {join_and(links)}"

    def appendix(self):
        assert set(self.order) == set(self.held) == self.linked, (set(self.held) - set(self.order), set(self.held) - self.linked)
        return "\n".join(f"<h3 id='t{n}'>Table {n}. {self.held[k][0]}</h3>{self.held[k][1]}" for n, k in enumerate(self.order, self.start + 1))


def chart(title, img):
    return f"<div class='chart-title'>{title}</div>{img}"


def titled(img, title):
    """A figure under its title, with the title as its alt text."""
    i = img.index('alt="') + 5
    return chart(title, img[:i] + title + img[img.index('"', i):])


def block(title, html):
    """A titled part of an appendix table that has more than one."""
    return f"<p><b>{title}</b></p>{html}"


def page(key, body, toc, heading=None):
    """Write the report: its numbered sections and the appendix in the contents, the ordinary quarters written Q2-Q4. The heading is the title after
    "Report:" unless one is given."""
    stem, title, _ = REPORTS[key]
    out = DOCS / "reports"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{stem}.html").write_text(report_shell(heading or f"Report: {title}", "", "", body.replace(REST, RT), toc + [("appendix", "Appendix")]), encoding="utf8")
    return f"docs/reports/{stem}.html"
