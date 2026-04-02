"""What the report renderers share: appendix tables numbered by first reference, links to the other reports, chart titles and the page."""
from analytics.reports.combine import REPORTS
from analytics.style.style import DOCS, report_shell

REST, RT = "Q2 to Q4", "Q2-Q4"


def link(key, text=None):
    """Another report by its title, or by the text given, as a link."""
    stem, title, _ = REPORTS[key]
    return f"<a href='{stem}.html'>{text or title}</a>"


def join_and(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


class Tables:
    """The appendix tables, numbered in the order the text first refers to them."""

    def __init__(self):
        self.held, self.order = {}, []

    def add(self, key, title, html):
        self.held[key] = (title, html)

    def number(self, key):
        return self.order.index(key) + 1

    def see(self, *keys):
        for k in keys:
            assert k in self.held and k not in self.order, k
            self.order.append(k)
        links = [f"<a href='#t{self.number(k)}'>{self.number(k)}</a>" for k in keys]
        return f"See Appendix Table{'s' if len(links) > 1 else ''} {join_and(links)} for additional detail."

    def appendix(self):
        assert set(self.order) == set(self.held), set(self.held) - set(self.order)
        return "\n".join(f"<h3 id='t{n}'>Table {n}. {self.held[k][0]}</h3>{self.held[k][1]}" for n, k in enumerate(self.order, 1))


def chart(title, img):
    return f"<div class='chart-title'>{title}</div>{img}"


def titled(img, title):
    """A figure under its title, with the title as its alt text."""
    i = img.index('alt="') + 5
    return chart(title, img[:i] + title + img[img.index('"', i):])


def block(title, html):
    """A titled part of an appendix table that has more than one."""
    return f"<p><b>{title}</b></p>{html}"


def page(key, body, toc):
    """Write the report: its numbered sections and the appendix in the contents, the ordinary quarters written Q2-Q4."""
    stem, title, _ = REPORTS[key]
    out = DOCS / "reports"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{stem}.html").write_text(report_shell(f"Report: {title}", "", "", body.replace(REST, RT), toc + [("appendix", "Appendix")]), encoding="utf8")
    return f"docs/reports/{stem}.html"
