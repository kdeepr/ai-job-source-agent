"""Step 1: LinkedIn job listing -> (company name, company website).

Uses a RapidAPI-hosted LinkedIn scraper by default (see .env.example). Field
names returned by these third-party APIs vary provider to provider, so the
parsing here tries several common shapes defensively. If you subscribe to a
different API than the default ("linkedin-data-api"), adjust `_pick` calls
below to match its actual response schema.

If the LinkedIn data source doesn't expose a direct company website (some
don't), we fall back to a plain web search for "<company name> official
site" and take the first non-LinkedIn/non-social result. This keeps the
pipeline generic instead of hard failing when one provider is missing a field.
"""

import re
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlparse

import requests

from . import config

_SOCIAL_DOMAINS = {
    "linkedin.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    "youtube.com",
    "wikipedia.org",
    "crunchbase.com",
    "glassdoor.com",
    "indeed.com",
}


@dataclass
class CompanyInfo:
    company_name: str
    company_website: str
    linkedin_company_url: Optional[str] = None


def _pick(d: dict, *keys: str) -> Optional[Any]:
    """Return the first present, truthy value among nested dotted key paths."""
    for key in keys:
        node: Any = d
        for part in key.split("."):
            if not isinstance(node, dict):
                node = None
                break
            node = node.get(part)
        if node:
            return node
    return None


def _extract_job_id(job_url: str) -> str:
    match = re.search(r"(?:currentJobId=|/view/)(\d+)", job_url)
    if not match:
        raise ValueError(
            f"Could not find a numeric job id in LinkedIn job URL: {job_url}"
        )
    return match.group(1)


def _rapidapi_get(path: str, params: dict) -> dict:
    config.require_keys("RAPIDAPI_KEY")
    resp = requests.get(
        f"https://{config.RAPIDAPI_HOST}{path}",
        headers={
            "X-RapidAPI-Key": config.RAPIDAPI_KEY,
            "X-RapidAPI-Host": config.RAPIDAPI_HOST,
        },
        params=params,
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def _web_search_company_site(company_name: str) -> Optional[str]:
    """Best-effort fallback: search the web and return the first plausible
    official site (skips LinkedIn/social/aggregator domains)."""
    try:
        resp = requests.get(
            "https://duckduckgo.com/html/",
            params={"q": f"{company_name} official website"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        resp.raise_for_status()
    except requests.RequestException:
        return None

    for raw_url in re.findall(r'href="(https?://[^"]+)"', resp.text):
        domain = urlparse(raw_url).netloc.lower().removeprefix("www.")
        if any(domain == d or domain.endswith("." + d) for d in _SOCIAL_DOMAINS):
            continue
        return raw_url
    return None


def get_company_from_job_url(job_url: str) -> CompanyInfo:
    job_id = _extract_job_id(job_url)
    job_data = _rapidapi_get("/get-job-details", {"id": job_id})

    company_name = _pick(
        job_data,
        "company.name",
        "companyName",
        "company_name",
        "data.companyName",
        "data.company.name",
    )
    company_username = _pick(
        job_data,
        "company.universalName",
        "companyUsername",
        "company_username",
        "data.company.universalName",
    )
    linkedin_company_url = _pick(
        job_data,
        "company.url",
        "companyLinkedinUrl",
        "data.company.url",
    )

    if not company_name:
        raise RuntimeError(
            "Could not extract company name from job details response. "
            "Inspect the raw response and update the key paths in "
            "src/linkedin_source.py: " + str(job_data)[:500]
        )

    company_website = None
    if company_username:
        try:
            company_data = _rapidapi_get(
                "/get-company-details", {"username": company_username}
            )
            company_website = _pick(
                company_data,
                "website",
                "data.website",
                "companyWebsite",
            )
        except requests.RequestException:
            company_website = None

    if not company_website:
        company_website = _web_search_company_site(company_name)

    if not company_website:
        raise RuntimeError(
            f"Could not resolve an official website for '{company_name}' "
            "via the LinkedIn API or web search fallback."
        )

    return CompanyInfo(
        company_name=company_name,
        company_website=company_website,
        linkedin_company_url=linkedin_company_url,
    )
