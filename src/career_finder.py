"""Step 2: company homepage -> careers/jobs listing page.

Generic across site formats on purpose: cheap heuristics first (common URL
paths + keyword matching over the homepage's rendered links), then Claude
disambiguates when heuristics turn up more than one plausible candidate.
This mirrors how a human would scan a homepage for a "Careers" link instead
of hardcoding per-site rules.
"""

import re
from typing import List, Optional
from urllib.parse import urlparse

import requests

from .browser import BrowserSession, Link
from .llm import pick_link

CAREER_KEYWORDS = re.compile(
    r"career|jobs?\b|hiring|join.?(us|our team)|work with us|open position"
    r"|vacanc|opportunit|life at ",
    re.IGNORECASE,
)

COMMON_PATHS = [
    "/careers",
    "/career",
    "/jobs",
    "/join-us",
    "/about/careers",
    "/company/careers",
    "/about-us/careers",
    "/work-with-us",
    "/en/careers",
    "/join",
]


def _keyword_candidates(links: List[Link]) -> List[Link]:
    return [
        l for l in links if CAREER_KEYWORDS.search(l.text) or CAREER_KEYWORDS.search(l.href)
    ]


def _probe_common_paths(homepage_url: str) -> Optional[str]:
    parsed = urlparse(homepage_url)
    root = f"{parsed.scheme}://{parsed.netloc}"
    for path in COMMON_PATHS:
        candidate = root + path
        try:
            resp = requests.head(candidate, timeout=8, allow_redirects=True)
            if resp.status_code == 405:  # some servers reject HEAD
                resp = requests.get(
                    candidate, timeout=8, allow_redirects=True, stream=True
                )
            if resp.status_code < 400:
                return resp.url
        except requests.RequestException:
            continue
    return None


def find_career_page(session: BrowserSession, homepage_url: str) -> str:
    rendered = session.render(homepage_url)
    candidates = _keyword_candidates(rendered.links)

    if len(candidates) == 1:
        return candidates[0].href

    if candidates:
        chosen = pick_link(
            "You are looking at links extracted from a company's homepage. "
            "Pick the single link that leads to the company's careers/jobs "
            "listing page (not a specific job posting, not an unrelated page "
            "like press, investor relations, or a social profile).",
            [(l.text, l.href) for l in candidates],
            extra_context=f"Homepage: {homepage_url}",
        )
        if chosen:
            return chosen

    probed = _probe_common_paths(homepage_url)
    if probed:
        return probed

    # Last resort: let Claude scan every link on the homepage.
    chosen = pick_link(
        "You are looking at every link extracted from a company's homepage. "
        "Pick the single link most likely to lead to the company's "
        "careers/jobs listing page.",
        [(l.text, l.href) for l in rendered.links],
        extra_context=f"Homepage: {homepage_url}",
    )
    if chosen:
        return chosen

    raise RuntimeError(f"Could not find a careers page from homepage: {homepage_url}")
