"""Shared Claude helper: pick the single best-matching link out of a list.

Used by both career_finder and job_finder so the "which link is right" logic
(the part that has to generalize across arbitrary, unknown site layouts)
lives in one place.
"""

import re
from typing import List, Optional, Tuple

from anthropic import Anthropic

from . import config

_client: Optional[Anthropic] = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        config.require_keys("ANTHROPIC_API_KEY")
        _client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def pick_link(
    instructions: str,
    links: List[Tuple[str, str]],
    extra_context: str = "",
    max_candidates: int = 100,
) -> Optional[str]:
    """Ask Claude to choose one link from `links` (list of (text, href)).

    Returns the chosen href, or None if Claude found no suitable match.
    """
    if not links:
        return None

    trimmed = links[:max_candidates]
    numbered = "\n".join(
        f"{i}: text={text!r} url={href}" for i, (text, href) in enumerate(trimmed)
    )
    prompt = (
        f"{instructions}\n\n"
        f"{extra_context}\n\n"
        f"Links (index: text, url):\n{numbered}\n\n"
        "Reply with ONLY the index number of the single best matching link, "
        "or the word NONE if nothing qualifies. No other text, no explanation."
    )

    resp = _get_client().messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=16,
        messages=[{"role": "user", "content": prompt}],
    )
    reply = "".join(
        block.text for block in resp.content if getattr(block, "type", "") == "text"
    ).strip()

    if reply.upper().startswith("NONE"):
        return None

    match = re.search(r"\d+", reply)
    if not match:
        return None
    idx = int(match.group())
    if 0 <= idx < len(trimmed):
        return trimmed[idx][1]
    return None
