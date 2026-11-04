"""Step 3: careers page -> URL of one specific open position.

Career pages come in three broad shapes, and this handles all three
generically:
  1. Custom-built page that lists jobs inline with plain <a> links.
  2. Page that embeds a third-party ATS (Greenhouse, Lever, Workday, ...) in
     an <iframe> - we detect that and follow it.
  3. Page that redirects outright to an ATS-hosted listing page.

After rendering, we shrink the link list to plausible job-posting URLs with
regex, then let Claude pick one specific posting (as opposed to a listing/
index/filter link) from that shortlist.
"""

import re
from typing import List
from urllib.parse import urlparse

from .browser import KNOWN_ATS_DOMAINS, BrowserSession, Link, RenderedPage
from .llm import pick_link

# Path shapes seen across common ATS platforms and typical custom career
# sites for a *single job posting* (as opposed to the listing/index page).
JOB_POSTING_PATTERN = re.compile(
    r"/(jobs?|positions?|openings?|postings?|careers?|req|opportunities)"
    r"/[^/?#]*[A-Za-z0-9][^/?#]*",
    re.IGNORECASE,
)

# Links that are clearly not a specific posting even if they match the
# pattern above (pagination, filters, the listing page itself, etc).
NON_POSTING_HINTS = re.compile(
    r"page=\d|filter|department|location=|search|\?q=|/all$|/all/?$",
    re.IGNORECASE,
)


def _is_known_ats_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(ats in host for ats in KNOWN_ATS_DOMAINS)


def _job_posting_candidates(links: List[Link], listing_url: str) -> List[Link]:
    listing_netloc = urlparse(listing_url).netloc
    listing_path = urlparse(listing_url).path.rstrip("/")
    ats_listing = _is_known_ats_url(listing_url)

    out = []
    for link in links:
        parsed = urlparse(link.href)
        path = parsed.path.rstrip("/")
        if not path or path == listing_path or parsed.netloc != listing_netloc:
            continue
        if NON_POSTING_HINTS.search(link.href):
            continue
        if ats_listing:
            # On a known ATS listing page almost every deeper same-host link
            # is a specific posting - many ATS platforms (e.g. Lever's
            # /<company>/<uuid>) don't put the word "job" in the path at all,
            # so the generic keyword pattern below would miss them.
            if len(path) > len(listing_path):
                out.append(link)
        elif JOB_POSTING_PATTERN.search(path):
            out.append(link)
    return out


def _resolve_listing_page(session: BrowserSession, career_page_url: str) -> RenderedPage:
    rendered = session.render(career_page_url)
    if rendered.ats_iframe_url:
        return session.render(rendered.ats_iframe_url)
    return rendered


def find_one_opening(session: BrowserSession, career_page_url: str) -> str:
    listing = _resolve_listing_page(session, career_page_url)
    candidates = _job_posting_candidates(listing.links, listing.url)

    if len(candidates) == 1:
        return candidates[0].href

    if candidates:
        chosen = pick_link(
            "You are looking at links extracted from a company's job "
            "listing page. Pick the single link that leads to ONE specific "
            "open job posting (a real role with a title), not a listing "
            "page, department/location filter, pagination link, or search "
            "page.",
            [(l.text, l.href) for l in candidates],
            extra_context=f"Job listing page: {listing.url}",
        )
        if chosen:
            return chosen
        # Fall back to the first heuristic candidate if Claude was unsure.
        return candidates[0].href

    # No regex hits at all: let Claude scan every link on the listing page.
    chosen = pick_link(
        "You are looking at every link extracted from a company's careers "
        "page. Pick the single link most likely to lead to ONE specific "
        "open job posting (a real role with a title), not a listing/index "
        "page or an unrelated page.",
        [(l.text, l.href) for l in listing.links],
        extra_context=f"Careers page: {listing.url}",
    )
    if chosen:
        return chosen

    raise RuntimeError(
        f"Could not find a specific job opening on careers page: {career_page_url}"
    )
