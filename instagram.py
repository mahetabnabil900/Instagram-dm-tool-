"""
Instagram Graph API client.
All calls are async (httpx). Rate-limit errors trigger exponential backoff.
"""

import asyncio
import logging
import os
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.facebook.com/v19.0"
DEFAULT_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _request(
    method: str,
    path: str,
    token: Optional[str] = None,
    retries: int = 3,
    **kwargs,
) -> dict:
    """Make a Graph API request with retry/backoff on rate-limit (error code 4 / 32 / 613)."""
    url = f"{GRAPH_BASE}/{path.lstrip('/')}"
    access_token = token or DEFAULT_TOKEN

    params = kwargs.pop("params", {})
    params["access_token"] = access_token

    for attempt in range(retries):
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.request(method, url, params=params, **kwargs)

        data = resp.json()
        log.debug("Graph API %s %s → %s", method, path, data)

        if "error" in data:
            err = data["error"]
            code = err.get("code", 0)
            # Rate-limit codes
            if code in (4, 32, 613) and attempt < retries - 1:
                wait = 2 ** attempt
                log.warning("Rate limit hit (code %s). Retrying in %ss…", code, wait)
                await asyncio.sleep(wait)
                continue
            log.error("Graph API error: %s", err)
            raise RuntimeError(f"Graph API error {code}: {err.get('message')}")

        return data

    raise RuntimeError("Max retries exceeded for Graph API request")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def reply_to_comment(
    comment_id: str,
    message: str,
    token: Optional[str] = None,
) -> dict:
    """Post a public reply to an Instagram comment."""
    log.info("Replying to comment %s", comment_id)
    result = await _request(
        "POST",
        f"{comment_id}/replies",
        token=token,
        json={"message": message},
    )
    log.info("Reply posted: %s", result)
    return result


async def send_dm(
    instagram_user_id: str,
    message: str,
    token: Optional[str] = None,
    page_id: Optional[str] = None,
) -> dict:
    """
    Send a private DM to an Instagram user via the Messaging API.

    Requirements:
    - The user must have previously messaged the business, OR
    - The business must have the instagram_manage_messages permission approved.
    See README for how to apply for this permission.
    """
    _page_id = page_id or os.getenv("PAGE_ID", "")
    if not _page_id:
        raise ValueError("PAGE_ID is required to send DMs")

    log.info("Sending DM to Instagram user %s", instagram_user_id)
    result = await _request(
        "POST",
        f"{_page_id}/messages",
        token=token,
        json={
            "recipient": {"id": instagram_user_id},
            "message": {"text": message},
            "messaging_type": "RESPONSE",
        },
    )
    log.info("DM sent: %s", result)
    return result


async def get_post_details(
    post_id: str,
    token: Optional[str] = None,
) -> dict:
    """
    Fetch a post's caption and thumbnail URL for dashboard preview.
    Returns dict with keys: id, caption, thumbnail_url, media_type, permalink.
    """
    log.info("Fetching post details for %s", post_id)
    data = await _request(
        "GET",
        post_id,
        token=token,
        params={
            "fields": "id,caption,thumbnail_url,media_url,media_type,permalink",
        },
    )
    # Normalise: videos have thumbnail_url, images have media_url
    data.setdefault("thumbnail_url", data.get("media_url", ""))
    return data


async def verify_token_and_account(
    token: str,
    ig_account_id: str,
) -> dict:
    """Quick sanity-check: confirm the token can reach the IG business account."""
    return await _request(
        "GET",
        ig_account_id,
        token=token,
        params={"fields": "id,name,username"},
    )
