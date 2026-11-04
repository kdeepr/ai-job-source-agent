"""Thin Playwright wrapper: render a URL and extract normalized links.

Handles JS-rendered pages (React/Vue SPA career sites, embedded ATS widgets)
that plain `requests` + regex can't see.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, List, Optional
from urllib.parse import urljoin, urlparse

from playwright.sync_api import Page, sync_playwright

from . import config

# Common Applicant Tracking System domains. Career pages very often embed or
# redirect to one of these rather than listing jobs on the company's own
# domain, so we check for them explicitly.
KNOWN_ATS_DOMAINS = [
    "boards.greenhouse.io",
    "job-boards.greenhouse.io",
    "jobs.lever.co",
    "myworkdayjobs.com",
    "jobs.smartrecruiters.com",
    "jobs.ashbyhq.com",
    "recruiting.paylocity.com",
    "jobs.jobvite.com",
    "icims.com",
    "bamboohr.com",
    "workable.com",
    "breezy.hr",
]


@dataclass
class Link:
    text: str
    href: str


@dataclass
class RenderedPage:
    url: str
    html: str
    links: List[Link]
    ats_iframe_url: Optional[str]


class BrowserSession:
    def __init__(self, browser):
        self._browser = browser

    def render(self, url: str) -> RenderedPage:
        page: Page = self._browser.new_page()
        try:
            page.goto(
                url, timeout=config.PAGE_TIMEOUT_MS, wait_until="domcontentloaded"
            )
            try:
                page.wait_for_load_state(
                    "networkidle", timeout=config.PAGE_TIMEOUT_MS
                )
            except Exception:
                pass  # some pages never idle (polling widgets); best effort is fine

            final_url = page.url
            html = page.content()
            links = self._extract_links(page, final_url)
            ats_iframe_url = self._find_ats_iframe(page)
            return RenderedPage(
                url=final_url, html=html, links=links, ats_iframe_url=ats_iframe_url
            )
        finally:
            page.close()

    @staticmethod
    def _extract_links(page: Page, base_url: str) -> List[Link]:
        raw = page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => ({text: e.innerText.trim(), href: e.getAttribute('href')}))",
        )
        seen = set()
        links: List[Link] = []
        for item in raw:
            href = item.get("href") or ""
            if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
                continue
            absolute = urljoin(base_url, href)
            if absolute in seen:
                continue
            seen.add(absolute)
            links.append(Link(text=(item.get("text") or "").strip(), href=absolute))
        return links

    @staticmethod
    def _find_ats_iframe(page: Page) -> Optional[str]:
        for frame in page.frames:
            if frame == page.main_frame:
                continue
            host = urlparse(frame.url).netloc.lower()
            if any(ats in host for ats in KNOWN_ATS_DOMAINS):
                return frame.url
        return None


@contextmanager
def browser_session() -> Iterator[BrowserSession]:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=config.HEADLESS)
        try:
            yield BrowserSession(browser)
        finally:
            browser.close()
