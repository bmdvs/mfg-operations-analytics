"""Shared palette, chart helpers and the HTML shells for the reports and the dashboard."""
import re
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

BRAND_BLUE = "#3D5166"
ACCENT = "#6B8FA8"
LIGHT_BLUE = "#A8C0D1"
AMBER = "#D4881E"
RED = "#CC0000"
GREEN = "#1A7A3A"
GREY = "#AAAAAA"
DARK_GREY = "#555555"
TEXT = "#222222"
CREDIT = "Created by Brian Davis, 2026"

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
CHART_W, CHART_H, CHART_DPI = 8.2, 3.8, 130
plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white", "axes.edgecolor": "#DDDDDD", "axes.grid": False,
    "font.family": "sans-serif", "font.size": 11, "axes.titlesize": 13, "axes.titleweight": "bold",
    "axes.labelsize": 11, "xtick.labelsize": 10, "ytick.labelsize": 10, "legend.fontsize": 10, "figure.dpi": CHART_DPI,
})


def chart_style(ax, grid="y"):
    (ax.yaxis if grid == "y" else ax.xaxis).grid(True, color="#EEEEEE", linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#DDDDDD")


def fig(h=None, w=None, ncols=1, nrows=1, grid="y", **kw):
    f, ax = plt.subplots(nrows, ncols, figsize=(w or CHART_W, h or CHART_H), **kw)
    for a in (ax.ravel() if hasattr(ax, "ravel") else [ax]):
        chart_style(a, grid)
    return f, ax


def sig(x, digits=6):
    """Values rounded to a number of significant digits before plotting, so a figure does not depend on the last digits of a sum."""
    a = np.asarray(x, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        mag = np.where((a == 0) | ~np.isfinite(a), 0.0, np.floor(np.log10(np.abs(a))))
    scale = 10.0 ** (digits - 1 - mag)
    return np.round(a * scale) / scale


def save(f, name, alt="", up=1):
    """Write the figure under docs/figures and return the img tag for a page `up` levels below docs."""
    out = DOCS / "figures"
    out.mkdir(parents=True, exist_ok=True)
    f.savefig(out / f"{name}.png", format="png", bbox_inches="tight", dpi=CHART_DPI)
    plt.close(f)
    return f'<img alt="{alt}" src="{"../" * up}figures/{name}.png">'


def save_conformed(f, name, alt="", up=1):
    """save, with the report convention applied first: the ordinary quarters written Q2-Q4, and one legend along the bottom of the figure."""
    from matplotlib.text import Text
    from matplotlib.ticker import FixedFormatter
    fix = lambda t: t.replace("Q2 to Q4", "Q2-Q4")
    for ax in f.axes:
        for axis in (ax.xaxis, ax.yaxis):
            fmt = axis.get_major_formatter()
            if isinstance(fmt, FixedFormatter):
                fmt.seq = [fix(x) for x in fmt.seq]
    for t in f.findobj(Text):
        if "Q2 to Q4" in t.get_text():
            t.set_text(fix(t.get_text()))
    # panels whose legends differ keep them; one shared legend moves to the bottom of the figure
    own = {tuple(t.get_text() for t in ax.get_legend().get_texts()) for ax in f.axes if ax.get_legend() is not None}
    if not f.legends and len(own) == 1:
        handles, labels = [], []
        for ax in f.axes:
            leg = ax.get_legend()
            if leg is None:
                continue
            for h, t in zip(leg.legend_handles, leg.get_texts()):
                if t.get_text() not in labels:
                    handles.append(h)
                    labels.append(t.get_text())
            leg.remove()
        if handles:
            f.legend(handles, labels, frameon=False, fontsize=9, ncol=min(len(labels), 4), loc="upper center", bbox_to_anchor=(0.5, 0.02))
    return save(f, name, alt, up)


def pct(x, d=1):
    return f"{x * 100:.{d}f}%"


def table(df, fmt=None, cls="data"):
    fmt = fmt or {}
    head = "".join(f"<th>{c}</th>" for c in df.columns)
    body = ""
    for _, r in df.iterrows():
        cells = ""
        for c in df.columns:
            v = r[c]
            f = fmt.get(c)
            s = f(v) if f and v == v and v is not None else ("" if v != v or v is None else str(v))
            num = isinstance(v, (int, float)) and not isinstance(v, bool)
            cells += f'<td class="{"num" if num else ""}">{s}</td>'
        body += f"<tr>{cells}</tr>"
    return f'<table class="{cls}"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


CSS = f"""
:root {{ --brand: {BRAND_BLUE}; --accent: {ACCENT}; --text: {TEXT}; --muted: {DARK_GREY}; --rule: #DDDDDD; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: #F4F5F7; color: var(--text); font-family: "Segoe UI", Helvetica, Arial, sans-serif;
        font-size: 15px; line-height: 1.55; }}
.page {{ max-width: 980px; margin: 0 auto; background: white; padding: 40px 56px 64px; }}
header.doc {{ border-bottom: 3px solid var(--brand); padding-bottom: 14px; margin-bottom: 28px; }}
header.doc .kicker {{ color: var(--accent); font-size: 12px; letter-spacing: 1.2px; text-transform: uppercase; font-weight: 600; }}
header.doc h1 {{ margin: 4px 0 6px; font-size: 28px; color: var(--brand); }}
header.doc .meta {{ color: var(--muted); font-size: 13px; }}
header.doc .credit {{ color: var(--muted); font-size: 11px; margin-top: 4px; }}
h2 {{ color: var(--brand); font-size: 21px; margin: 36px 0 8px; border-bottom: 1px solid var(--rule); padding-bottom: 4px; }}
h3 {{ color: var(--brand); font-size: 16px; margin: 22px 0 6px; }}
p {{ margin: 8px 0 12px; }}
img {{ max-width: 100%; display: block; margin: 10px 0 4px; }}
.caption {{ color: var(--muted); font-size: 12.5px; margin-bottom: 18px; }}
table.data {{ border-collapse: collapse; width: 100%; font-size: 13px; margin: 10px 0 16px; }}
table.data th {{ background: var(--brand); color: white; text-align: left; padding: 6px 8px; font-weight: 600; }}
table.data td {{ border-bottom: 1px solid #EEE; padding: 5px 8px; }}
table.data td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
table.data tr.total td {{ font-weight: 600; border-top: 1px solid var(--rule); }}
.kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin: 16px 0 22px; }}
.kpi {{ border: 1px solid var(--rule); border-top: 3px solid var(--accent); padding: 10px 12px; }}
.kpi .v {{ font-size: 24px; font-weight: 700; color: var(--brand); }}
.kpi .l {{ font-size: 12px; color: var(--muted); }}
.note {{ background: #F7F9FB; border-left: 3px solid var(--accent); padding: 10px 14px; margin: 14px 0; font-size: 14px; }}
.glossary {{ color: var(--muted); font-size: 12.5px; margin-top: 28px; border-top: 1px solid var(--rule); padding-top: 10px; }}
nav.toc {{ font-size: 13.5px; margin: 0 0 24px; }}
nav.toc a {{ color: var(--accent); text-decoration: none; margin-right: 14px; }}
@media (max-width: 700px) {{ .page {{ padding: 20px 16px 40px; }} }}
@media print {{ body {{ background: white; }} .page {{ padding: 0; max-width: none; }} }}
"""

REPORT_CSS = CSS + """
body { background: white; }
.page-header { background: var(--brand); color: white; padding: 14px 40px; display: flex; justify-content: space-between; align-items: center; gap: 24px; }
.page-header h1 { margin: 0; font-size: 21px; font-weight: 700; letter-spacing: -0.3px; color: white; }
.page-header .sub { font-size: 12px; white-space: nowrap; }
.layout { display: flex; max-width: 1200px; margin: 0 auto; padding: 0 40px; }
nav.toc { width: 210px; flex-shrink: 0; margin: 0; padding: 36px 20px 40px 0; position: sticky; top: 0; height: 100vh; overflow-y: auto;
          border-right: 1px solid var(--rule); font-size: 13px; }
nav.toc .toc-title { font-size: 10px; letter-spacing: 2px; text-transform: uppercase; color: var(--muted); margin-bottom: 14px; font-weight: 700; }
nav.toc a { display: block; color: var(--muted); margin-right: 0; padding: 4px 0 4px 10px; border-left: 2px solid transparent; line-height: 1.4; }
nav.toc a:hover { color: var(--brand); border-left-color: var(--brand); }
nav.toc a.sub { font-size: 12px; padding-left: 22px; }
.content { flex: 1; min-width: 0; max-width: 880px; padding: 30px 0 80px 52px; }
.content header.doc { border-bottom: 1px solid var(--rule); padding-bottom: 12px; margin-bottom: 8px; }
.content > h2:first-child { margin-top: 6px; }
.chart-title { color: var(--brand); font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; text-align: center; margin: 20px 0 0; }
@media (max-width: 900px) {
  .page-header { padding: 12px 16px; } .layout { display: block; padding: 0 16px; }
  nav.toc { position: static; width: auto; height: auto; border-right: 0; border-bottom: 1px solid var(--rule); padding: 16px 0 12px; }
  .content { padding: 16px 0 40px; }
}
@media print { nav.toc { display: none; } .layout { display: block; max-width: none; padding: 0; } .content { max-width: none; padding: 0; } }
"""


def shell(title, kicker, meta, body, toc=None):
    nav = ""
    if toc:
        nav = '<nav class="toc">' + "".join(f'<a href="#{a}">{t}</a>' for a, t in toc) + "</nav>"
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><style>{CSS}</style></head>
<body><div class="page">
<header class="doc"><div class="kicker">{kicker}</div><h1>{title}</h1><div class="meta">{meta}</div><div class="credit">{CREDIT}</div></header>
{nav}{body}
</div></body></html>"""


def report_shell(title, kicker, meta, body, toc):
    """A report page: the title in a bar across the top, the contents down the left, the report beside them."""
    nav = ('<nav class="toc"><div class="toc-title">Contents</div>'
           + "".join(f'<a{" class=" + chr(34) + "sub" + chr(34) if len(x) > 2 else ""} href="#{x[0]}">{x[1]}</a>' for x in toc) + "</nav>")
    head = f'<header class="doc"><div class="kicker">{kicker}</div><div class="meta">{meta}</div></header>\n' if kicker or meta else ""
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><style>{REPORT_CSS}</style></head>
<body><div class="page-header"><h1>{title}</h1><div class="sub">{CREDIT}</div></div>
<div class="layout">{nav}
<main class="content">{head}{body}
</main></div></body></html>"""
