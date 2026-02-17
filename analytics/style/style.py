"""Shared palette, chart helpers and the HTML shells for the reports, the A3 pages and the dashboard."""
from pathlib import Path

import matplotlib

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


def save(f, name, alt="", up=1):
    """Write the figure under docs/figures and return the img tag for a page `up` levels below docs."""
    out = DOCS / "figures"
    out.mkdir(parents=True, exist_ok=True)
    f.savefig(out / f"{name}.png", format="png", bbox_inches="tight", dpi=CHART_DPI)
    plt.close(f)
    return f'<img alt="{alt}" src="{"../" * up}figures/{name}.png">'


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

A3_CSS = CSS + """
.a3 { max-width: 1500px; padding: 26px 32px 30px; }
.a3 header.doc { margin-bottom: 14px; padding-bottom: 8px; }
.a3 header.doc h1 { font-size: 22px; margin: 2px 0 4px; }
.a3 .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px 22px; }
.a3 .grid > div { display: grid; gap: 12px; align-content: start; }
.a3 section { border: 1px solid var(--rule); border-top: 3px solid var(--brand); padding: 8px 12px 10px; font-size: 12.5px; line-height: 1.4; }
.a3 section h2 { font-size: 14px; margin: 0 0 4px; border: 0; padding: 0; text-transform: uppercase; letter-spacing: 0.6px; }
.a3 section p { margin: 4px 0 6px; }
.a3 section ul { margin: 4px 0 4px 16px; padding: 0; }
.a3 section li { margin-bottom: 3px; }
.a3 img { margin: 4px 0 2px; max-height: 360px; }
.a3 .caption { font-size: 11px; margin-bottom: 4px; }
.a3 table.data { font-size: 11.5px; margin: 4px 0 4px; }
.a3 table.data th, .a3 table.data td { padding: 3px 6px; }
@page { size: A3 landscape; margin: 9mm; }
@media print { .a3 { max-width: none; padding: 0; } .a3 .grid { gap: 8px 14px; } .a3 section { break-inside: avoid; } }
@media (max-width: 900px) { .a3 .grid { grid-template-columns: 1fr; } }
"""


def shell(title, kicker, meta, body, toc=None):
    nav = ""
    if toc:
        nav = '<nav class="toc">' + "".join(f'<a href="#{a}">{t}</a>' for a, t in toc) + "</nav>"
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><style>{CSS}</style></head>
<body><div class="page">
<header class="doc"><div class="kicker">{kicker}</div><h1>{title}</h1><div class="meta">{meta}</div></header>
{nav}{body}
</div></body></html>"""


def a3_shell(title, kicker, meta, left, right):
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><style>{A3_CSS}</style></head>
<body><div class="page a3">
<header class="doc"><div class="kicker">{kicker}</div><h1>{title}</h1><div class="meta">{meta}</div></header>
<div class="grid"><div>{left}</div><div>{right}</div></div>
</div></body></html>"""
