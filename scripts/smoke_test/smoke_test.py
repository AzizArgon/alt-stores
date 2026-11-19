"""Smoke test of the public site (Phase 20): opens the main pages like a buyer would and says "all OK" or what failed.

Run: smoke.bat (the server) or smoke.bat local (http://localhost:5173). Read-only: no logins, no forms sent,
nothing is changed on the site. The only thing it "does" is switching the language, which lives in this browser.
Browser: Microsoft Edge of Windows (no download); if it is missing - Playwright's Chromium.
"""
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

SITE = "https://pcmarket.khudoberdi.uz"
TIMEOUT_MS = 20_000
# A guest gets 401 from "who am I" requests: that is normal, not an error of the page
IGNORED = re.compile(r"status of 401|401 \(Unauthorized\)|favicon", re.I)
# "Failed to load resource" has no address in the console: the response listener reports it with the address
FAILED_LOAD = re.compile(r"Failed to load resource", re.I)


class Check:
    def __init__(self, page, base):
        self.page, self.base = page, base
        self.results = []      # (name, ok, details)
        self.errors = []       # console errors / crashes of the current step
        page.on("console", lambda m: m.type == "error" and not IGNORED.search(m.text)
                and not FAILED_LOAD.search(m.text) and self.errors.append(m.text[:300]))
        page.on("pageerror", lambda e: self.errors.append(f"JS: {str(e)[:300]}"))
        page.on("response", self._response)

    def _response(self, r):
        # Anything of the site that did not load (pages, API, pictures) - with its address; 401 = guest, normal
        # The search first asks whether the words are a known barcode: 404 there = "no such code", normal
        if r.status == 404 and "/api/catalog/barcode/" in r.url:
            return
        if r.status >= 400 and r.status != 401 and r.url.startswith(self.base):
            self.errors.append(f"HTTP {r.status} {r.url[len(self.base):][:150]}")

    def open(self, path):
        resp = self.page.goto(self.base + path, wait_until="load", timeout=TIMEOUT_MS)
        if resp is not None and resp.status >= 400:
            raise AssertionError(f"HTTP {resp.status}")

    def need(self, selector, what):
        try:
            self.page.locator(selector).first.wait_for(state="visible", timeout=TIMEOUT_MS)
        except PlaywrightError:
            raise AssertionError(f"not found: {what}")

    def first_href(self, selector, what):
        self.need(selector, what)
        return self.page.locator(selector).first.get_attribute("href")

    def step(self, name, fn):
        self.errors = []
        started = time.time()
        try:
            details = fn() or ""
            self.page.wait_for_timeout(800)  # late console errors of the page
            ok = not self.errors
            if self.errors:
                details = "; ".join(dict.fromkeys(self.errors))[:600]
        except (AssertionError, PlaywrightError) as e:
            ok, details = False, str(e).splitlines()[0][:300]
        self.results.append((name, ok, f"{details} ({time.time() - started:.1f} s)".strip()))
        print(f"  {'OK  ' if ok else 'FAIL'}  {name}  {details}", flush=True)


def run(base):
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge")
        except PlaywrightError:
            browser = p.chromium.launch()
        page = browser.new_context(locale="ru-RU", viewport={"width": 1366, "height": 900}).new_page()
        c = Check(page, base)

        def home():
            c.open("/")
            c.need("header", "header")
            c.need('form[role="search"]', "search row")
            c.need('a[href^="/catalog"]', "link to the catalog")

        def catalog():
            c.open("/catalog")
            links = 'a[href^="/products/"]'
            c.need(links, "product cards")
            return f"{c.page.locator(links).count()} links to products"

        def search():
            c.open("/")
            box = c.page.locator('form[role="search"] input[type="search"]').first
            box.fill("12400f")
            box.press("Enter")
            # An exact model goes straight to its card, otherwise the catalog with results
            c.page.wait_for_url(re.compile(r"/(catalog\?.*q=12400f|products/\d+)"), timeout=TIMEOUT_MS)
            if "/products/" in c.page.url:
                c.need("h1", "product title")
                return "went to the card: " + c.page.locator("h1").first.inner_text()[:60]
            c.need('a[href^="/products/"]', "search results")
            text = c.page.locator("main").inner_text().lower()
            if "12400" not in text:
                raise AssertionError("no 12400F in the results")
            return "results found"

        def product():
            c.open("/catalog?q=12400f")
            href = c.first_href('a[href^="/products/"]', "a product")
            c.open(href)
            c.need("h1", "product title")
            return f"{href}: {c.page.locator('h1').first.inner_text()[:60]}"

        def used():
            c.open("/used")
            c.need("h1", "page title")

        def build():
            c.open("/builds")
            href = c.first_href('a[href^="/builds/"]', "a build")
            c.open(href)
            c.need("h1", "build title")
            return f"{href}: {c.page.locator('h1').first.inner_text()[:60]}"

        def for_sellers():
            c.open("/for-sellers")
            c.need("h1", "page title")

        def login():
            c.open("/login")
            c.need('input[type="email"]', "email field")
            c.need('input[type="password"]', "password field")
            c.need('button[type="submit"]', "login button")
            return "form is there (nothing sent)"

        def languages():
            c.open("/")
            seen = []
            for lng in ("uz", "en", "ru"):
                c.page.locator(f'header button[lang="{lng}"]').first.click()
                c.page.wait_for_function(f"document.documentElement.lang === '{lng}'", timeout=TIMEOUT_MS)
                seen.append(c.page.locator("header nav, header").first.inner_text().split("\n")[0][:20])
            return " / ".join(f"{l.upper()}" for l in ("uz", "en", "ru")) + " switched"

        def store():
            c.open("/stores")
            href = c.first_href('a[href^="/store/"]', "a store")
            c.open(href)
            c.need("h1", "store name")
            return f"{href}: {c.page.locator('h1').first.inner_text()[:60]}"

        print(f"Smoke test of {base}  ({datetime.now():%d.%m.%Y %H:%M})\n", flush=True)
        for name, fn in [("Home page", home), ("Catalog", catalog), ("Search 12400f", search),
                         ("Product card", product), ("Used (b/u)", used), ("Build", build),
                         ("For sellers", for_sellers), ("Login page", login),
                         ("Languages RU/UZ/EN", languages), ("Store page", store)]:
            c.step(name, fn)
        browser.close()
    return c.results


def main():
    base = SITE
    if len(sys.argv) > 1:
        base = "http://localhost:5173" if sys.argv[1] == "local" else sys.argv[1]
    base = base.rstrip("/")
    results = run(base)
    failed = [r for r in results if not r[1]]
    lines = [f"Smoke test {base}  {datetime.now():%Y-%m-%d %H:%M}", ""]
    lines += [f"{'OK  ' if ok else 'FAIL'}  {name}  {details}" for name, ok, details in results]
    lines.append("")
    if failed:
        lines.append(f"PROBLEMS: {len(failed)} of {len(results)} did not open correctly: " + ", ".join(r[0] for r in failed))
        lines.append("What to do: docs/maintenance.md, table 'Something broke'. If it started after a deploy - rollback.bat.")
    else:
        lines.append(f"ALL OK: {len(results)} of {len(results)} checks passed.")
    print("\n" + lines[-2 if failed else -1] + ("\n" + lines[-1] if failed else ""))
    # The report is kept next to the other things outside git
    local = Path(__file__).resolve().parents[2] / "_local"
    if local.is_dir():
        (local / "smoke").mkdir(exist_ok=True)
        out = local / "smoke" / f"{datetime.now():%Y-%m-%d_%H%M}_smoke.txt"
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"report: {out}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
