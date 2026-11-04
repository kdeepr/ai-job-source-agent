"""Orchestrates the full pipeline: LinkedIn job URL -> one result row.

LinkedIn job URL
    --(linkedin_source)--> company name + company website
    --(career_finder)-->   careers/jobs listing page URL
    --(job_finder)-->      one specific open position URL
"""

from dataclasses import dataclass
from typing import Union

from .browser import BrowserSession
from .career_finder import find_career_page
from .job_finder import find_one_opening
from .linkedin_source import get_company_from_job_url


@dataclass
class JobSourceResult:
    company_name: str
    career_page_url: str
    job_opening_url: str


@dataclass
class JobSourceError:
    linkedin_job_url: str
    stage: str
    error: str


def process_linkedin_job(
    session: BrowserSession, linkedin_job_url: str
) -> Union[JobSourceResult, JobSourceError]:
    """Run the full pipeline for one LinkedIn job URL.

    Returns a JobSourceResult on success, or a JobSourceError naming which
    stage failed, so one bad company doesn't abort an entire batch run.
    """
    try:
        company = get_company_from_job_url(linkedin_job_url)
    except Exception as exc:
        return JobSourceError(linkedin_job_url, "linkedin_extraction", str(exc))

    try:
        career_page_url = find_career_page(session, company.company_website)
    except Exception as exc:
        return JobSourceError(linkedin_job_url, "career_page_lookup", str(exc))

    try:
        job_opening_url = find_one_opening(session, career_page_url)
    except Exception as exc:
        return JobSourceError(linkedin_job_url, "job_opening_lookup", str(exc))

    return JobSourceResult(
        company_name=company.company_name,
        career_page_url=career_page_url,
        job_opening_url=job_opening_url,
    )
