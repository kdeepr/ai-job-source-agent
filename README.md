# AI Job Source Agent

Given LinkedIn job posting URLs, finds each company's careers page and one
live open position on it, generically across arbitrary site layouts.

```
LinkedIn job URL
    -> (RapidAPI)         company name + company website
    -> (Playwright+Claude) careers/jobs listing page
    -> (Playwright+Claude) one specific open position URL
```

Output: `company_name,career_page_url,job_opening_url` per row (CSV + stdout).

## Why it generalizes

Company career pages have no shared structure — some are custom React
pages, some redirect straight to an ATS (Greenhouse, Lever, Workday,
SmartRecruiters, Ashby, ...), some embed the ATS in an `<iframe>`. Instead of
hardcoding per-site rules, the agent:

1. Renders pages with Playwright (handles JS-rendered SPAs and ATS widgets),
   and detects ATS iframes by domain.
2. Applies cheap heuristics first — common URL paths (`/careers`, `/jobs`,
   ...) and keyword matching over link text/hrefs — to shrink the candidate
   set and avoid unnecessary LLM calls.
3. Falls back to Claude when heuristics are ambiguous (which is most of the
   time for the "pick one specific job posting out of a full listing" step)
   to choose the single best-matching link, the same way a human would scan
   the page.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
```

Fill in `.env`:
- `ANTHROPIC_API_KEY` — used for the link-disambiguation steps.
- `RAPIDAPI_KEY` / `RAPIDAPI_HOST` — a LinkedIn scraper on RapidAPI. Defaults
  to the `linkedin-data-api` host; if you subscribe to a different LinkedIn
  API, update `RAPIDAPI_HOST` and adjust the field-name lookups in
  `src/linkedin_source.py` (`_pick(...)` calls) to match its response shape —
  RapidAPI LinkedIn scrapers don't share a common schema.

## Run

```bash
python main.py "https://www.linkedin.com/jobs/view/1234567890/"

# multiple jobs, from a file (one URL per line, '#' comments allowed)
python main.py --file urls.txt --out results.csv
```

Progress and per-company success/failure prints to stderr; results write to
`results.csv` (default) and print as `company,career_page_url,job_url` to
stdout.

## Project layout

- `src/linkedin_source.py` — LinkedIn job URL -> company name + website
  (RapidAPI, with a plain web-search fallback if the API has no website field)
- `src/browser.py` — Playwright wrapper: render a page, extract normalized
  links, detect known-ATS iframes
- `src/career_finder.py` — homepage -> careers/jobs listing page
- `src/job_finder.py` — careers page -> one specific open position URL
- `src/llm.py` — shared Claude "pick the best link" helper
- `src/agent.py` — orchestrates the three stages per job URL, isolating
  failures per stage so one bad company doesn't abort a batch run
- `main.py` — CLI entrypoint

## Notes / limitations

- LinkedIn actively rate-limits scraping; the RapidAPI layer is a thin,
  swappable adapter for exactly that reason — swap providers by changing
  `RAPIDAPI_HOST` and the parsing in `linkedin_source.py`.
- `find_one_opening` picks *one* posting per company by design (per the
  spec); it doesn't enumerate every opening.
- Sites that gate their career page behind a CAPTCHA or login aren't
  handled — that's out of scope here (see the "Prohibited actions" policy
  this agent should respect if extended: never attempt to solve CAPTCHAs).

## Demo video checklist

To show this working end-to-end:
1. Prepare a small `urls.txt` with 3-5 real LinkedIn job posting URLs across
   different companies (ideally a mix of custom career sites and
   ATS-hosted ones, to show the generality).
2. Run `python main.py --file urls.txt --out results.csv` with the terminal
   visible so the per-stage stderr progress lines are on screen.
3. Open the resulting `results.csv` and show each row's career page URL and
   job opening URL actually load in a browser.
4. Optionally run once against a company whose career page needs the Claude
   disambiguation fallback (most ATS-hosted listing pages will) to show that
   step firing, not just the fast heuristic path.
