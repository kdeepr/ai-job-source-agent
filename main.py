#!/usr/bin/env python3
"""CLI entrypoint for the AI Job Source agent.

Usage:
    python main.py <linkedin_job_url> [<linkedin_job_url> ...]
    python main.py --file urls.txt
    python main.py --file urls.txt --out results.csv
"""

import argparse
import sys
from typing import List

from src.agent import process_linkedin_job
from src.browser import browser_session
from src.output import print_summary, write_csv


def _load_urls(args: argparse.Namespace) -> List[str]:
    urls = list(args.urls)
    if args.file:
        with open(args.file) as f:
            urls.extend(
                line.strip()
                for line in f
                if line.strip() and not line.startswith("#")
            )
    if not urls:
        print("No LinkedIn job URLs provided.", file=sys.stderr)
        sys.exit(1)
    return urls


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("urls", nargs="*", help="LinkedIn job posting URLs")
    parser.add_argument(
        "--file", help="Path to a text file with one LinkedIn job URL per line"
    )
    parser.add_argument(
        "--out", default="results.csv", help="Output CSV path (default: results.csv)"
    )
    args = parser.parse_args()

    urls = _load_urls(args)
    results = []
    with browser_session() as session:
        for i, url in enumerate(urls, 1):
            print(f"[{i}/{len(urls)}] Processing {url} ...", file=sys.stderr)
            results.append(process_linkedin_job(session, url))

    write_csv(results, args.out)
    print()
    print_summary(results)
    print(f"\nWrote {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
