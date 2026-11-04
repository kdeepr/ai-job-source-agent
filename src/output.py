"""CSV output for pipeline results."""

import csv
from typing import Sequence, Union

from .agent import JobSourceError, JobSourceResult

FIELDNAMES = ["company_name", "career_page_url", "job_opening_url"]


def write_csv(
    results: Sequence[Union[JobSourceResult, JobSourceError]], path: str
) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for r in results:
            if isinstance(r, JobSourceResult):
                writer.writerow(
                    {
                        "company_name": r.company_name,
                        "career_page_url": r.career_page_url,
                        "job_opening_url": r.job_opening_url,
                    }
                )


def print_summary(results: Sequence[Union[JobSourceResult, JobSourceError]]) -> None:
    for r in results:
        if isinstance(r, JobSourceResult):
            print(f"{r.company_name},{r.career_page_url},{r.job_opening_url}")
        else:
            print(f"[FAILED at {r.stage}] {r.linkedin_job_url}: {r.error}")
