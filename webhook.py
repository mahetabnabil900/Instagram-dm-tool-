"""
Webhook endpoints for the Instagram Graph API.
GET  /webhook/instagram  — hub challenge verification
POST /webhook/instagram  — receives comment events
"""

import hashlib
import hmac
import json
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

import instagram as ig
from database import get_db
from models import Campaign, Config, ProcessedComment

log = logging.getLogger(__name__)
router = APIRouter()


def _verify_signature(body: bytes, signature_header: str) -> bool:
    """Validate X-Hub-Signature-256 to confirm payload is from Facebook."""
    app_secret = os.getenv("FACEBOOK_APP_SECRET", "")
    if not app_secret:
        log.warning("FACEBOOK_APP_SECRET not set — skipping signature check")
        return True  # Permissive in dev; set secret in production!

    expected = "sha256=" + hmac.new(
        app_secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header or "")


@router.get("/webhook/instagram")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """Facebook sends a GET to verify our webhook URL during setup."""
    verify_token = os.getenv("WEBHOOK_VERIFY_TOKEN", "")
    if hub_mode == "subscribe" and hub_verify_token == verify_token:
        log.info("Webhook verified successfully")
        return int(hub_challenge)
    log.warning("Webhook verification failed — token mismatch")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook/instagram")
async def receive_webhook(request: Request, db: Session = Depends(get_db)):
    """Process incoming comment events from the Instagram Graph API."""
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not _verify_signature(body, signature):
        log.error("Invalid webhook signature — rejecting")
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    log.debug("Received webhook payload: %s", payload)

    # Facebook expects a fast 200 — process async-ish
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "comments":
                continue
            value = change.get("value", {})
            await _handle_comment_event(value, db)

    return {"status": "ok"}


async def _handle_comment_event(value: dict, db: Session):
    """Core logic: match comment → reply + DM."""
    comment_id = value.get("id")
    media_id = value.get("media", {}).get("id") or value.get("media_id")
    comment_text = (value.get("text") or "").lower()
    commenter_id = value.get("from", {}).get("id")

    if not comment_id or not media_id or not commenter_id:
        log.warning("Incomplete comment event, skipping: %s", value)
        return

    # Deduplication check
    already_done = db.query(ProcessedComment).filter_by(comment_id=comment_id).first()
    if already_done:
        log.info("Comment %s already processed, skipping", comment_id)
        return

    # Find matching active campaign
    campaigns = db.query(Campaign).filter_by(is_active=True).all()
    matched_campaign = None
    for campaign in campaigns:
        if campaign.post_id != media_id:
            continue
        for kw in campaign.keyword_list:
            if kw in comment_text:
                matched_campaign = campaign
                break
        if matched_campaign:
            break

    if not matched_campaign:
        log.debug("No campaign match for comment %s on post %s", comment_id, media_id)
        return

    log.info(
        "Matched campaign #%s for comment %s — replying and DMing",
        matched_campaign.id,
        comment_id,
    )

    # Load credentials from DB (override env if saved via dashboard)
    config = db.query(Config).filter_by(id=1).first()
    token = (config.access_token if config else None) or os.getenv("INSTAGRAM_ACCESS_TOKEN")
    page_id = (config.page_id if config else None) or os.getenv("PAGE_ID")

    errors = []

    try:
        await ig.reply_to_comment(
            comment_id=comment_id,
            message=matched_campaign.comment_reply,
            token=token,
        )
    except Exception as exc:
        log.error("Failed to reply to comment %s: %s", comment_id, exc)
        errors.append(str(exc))

    try:
        await ig.send_dm(
            instagram_user_id=commenter_id,
            message=matched_campaign.dm_message,
            token=token,
            page_id=page_id,
        )
    except Exception as exc:
        log.error("Failed to send DM to %s: %s", commenter_id, exc)
        errors.append(str(exc))

    # Mark as processed regardless of errors to avoid infinite retries
    db.add(ProcessedComment(comment_id=comment_id, campaign_id=matched_campaign.id))
    db.commit()

    if errors:
        log.warning("Comment %s processed with errors: %s", comment_id, errors)
    else:
        log.info("Comment %s fully handled", comment_id)
