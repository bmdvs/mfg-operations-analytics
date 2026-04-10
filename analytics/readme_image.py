"""The images at the top of the README: five charts from the three reports, under docs/readme/.

Usage: python -m analytics.readme_image
Each image is a chart as its report shows it, the chart title and the figure beneath it and nothing else from the page, captured with Playwright at
1280 px wide. The pages are rendered in the installed Edge or Chrome, or in Playwright's own Chromium where neither is installed; where no browser is
available the committed images are left as they are.
"""
from playwright.sync_api import sync_playwright

from analytics.style.style import DOCS

WIDTH = 1280
OUT = DOCS / "readme"
FLOW, CAPACITY, OPTIONS = "lead_time_and_late_jobs", "capacity_constraints_and_setups", "options_tested"
# file, report, chart title: the title is the image's alt text in the README
IMAGES = [
    ("job_flow.png", FLOW, "Job Flow, Release to Shipment"),
    ("lead_time_decomposition.png", FLOW, "Lead Time Decomposition by Stage, 2025 and Q2-Q4"),
    ("queue_by_work_center.png", CAPACITY, "Queue Time per Operation by Work Center, 2025"),
    ("scenario_results.png", OPTIONS, "Scenario Results: Change in On-time Delivery vs. Status Quo, 2025"),
    ("recommended_scenarios.png", OPTIONS, "On-time Delivery, Status Quo vs. Recommended Scenarios, 2025"),
]
# the chart title and the figure under it, as one box in page coordinates
BOX = """(title) => {
    const head = [...document.querySelectorAll('div.chart-title')].filter(d => d.textContent.trim() === title);
    if (head.length !== 1) return null;
    const img = head[0].nextElementSibling;
    if (!img || img.tagName !== 'IMG') return null;
    const a = head[0].getBoundingClientRect(), b = img.getBoundingClientRect();
    const x = Math.min(a.left, b.left), right = Math.max(a.right, b.right);
    return {x: x + window.scrollX, y: a.top + window.scrollY, width: right - x, height: b.bottom - a.top};
}"""
PAD = 6          # white space around the chart, in page pixels
# every image on the page decoded and the fonts loaded, so that a capture does not depend on how far the page has painted
DECODED = "Promise.all([document.fonts.ready, ...[...document.images].map(i => i.decode().catch(() => null))]).then(() => true)"


# drawn in software with one color profile, so that the same page gives the same pixels on every run
ARGS = ["--disable-gpu", "--force-color-profile=srgb", "--disable-lcd-text", "--font-render-hinting=none"]


def launch(p):
    for channel in ("msedge", "chrome", None):
        try:
            return p.chromium.launch(channel=channel, args=ARGS) if channel else p.chromium.launch(args=ARGS)
        except Exception:
            continue
    return None


def capture(browser, name, stem, title):
    """One chart at 1280 px wide: measured at the page's own scale, then captured at the scale that brings its box to that width."""
    url = (DOCS / "reports" / f"{stem}.html").as_uri()
    page = browser.new_page(viewport={"width": WIDTH, "height": 900}, device_scale_factor=1)
    page.goto(url)
    page.wait_for_load_state("networkidle")
    box = page.evaluate(BOX, title)
    page.close()
    assert box, (stem, title)
    clip = {"x": box["x"] - PAD, "y": box["y"] - PAD, "width": box["width"] + 2 * PAD, "height": box["height"] + 2 * PAD}
    page = browser.new_page(viewport={"width": WIDTH, "height": 900}, device_scale_factor=WIDTH / clip["width"])
    page.goto(url)
    page.wait_for_load_state("networkidle")
    page.evaluate(DECODED)
    page.screenshot(path=str(OUT / name), full_page=True, clip=clip)
    page.close()
    return round(clip["height"] * WIDTH / clip["width"])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = launch(p)
        if browser is None:
            print("no browser available; the images under docs/readme left as committed")
            return
        for name, stem, title in IMAGES:
            height = capture(browser, name, stem, title)
            print(f"wrote docs/readme/{name} ({WIDTH} x {height})")
        browser.close()


if __name__ == "__main__":
    main()
