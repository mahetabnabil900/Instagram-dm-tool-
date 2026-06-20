"""
REST API routes for campaigns and config — consumed by the dashboard JS.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

import instagram as ig
from database import get_db
from models import Campaign, Config

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ConfigIn(BaseModel):
    access_token: str
    page_id: str
    instagram_business_account_id: str


class CampaignIn(BaseModel):
    post_id: str
    keywords: str
    comment_reply: str
    dm_message: str
    is_active: bool = True


class CampaignUpdate(BaseModel):
    post_id: Optional[str] = None
    keywords: Optional[str] = None
    comment_reply: Optional[str] = None
    dm_message: Optional[str] = None
    is_active: Optional[bool] = None


# ---------------------------------------------------------------------------
# Config endpoints
# ---------------------------------------------------------------------------

@router.get("/config")
def get_config(db: Session = Depends(get_db)):
    config = db.query(Config).filter_by(id=1).first()
    if not config:
        return {"access_token": "", "page_id": "", "instagram_business_account_id": ""}
    return {
        "access_token": config.access_token or "",
        "page_id": config.page_id or "",
        "instagram_business_account_id": config.instagram_business_account_id or "",
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }


@router.post("/config")
def save_config(data: ConfigIn, db: Session = Depends(get_db)):
    config = db.query(Config).filter_by(id=1).first()
    if config:
        config.access_token = data.access_token
        config.page_id = data.page_id
        config.instagram_business_account_id = data.instagram_business_account_id
        config.updated_at = datetime.utcnow()
    else:
        config = Config(
            id=1,
            access_token=data.access_token,
            page_id=data.page_id,
            instagram_business_account_id=data.instagram_business_account_id,
        )
        db.add(config)
    db.commit()
    return {"status": "saved"}


@router.post("/config/verify")
async def verify_config(data: ConfigIn):
    """Test that the token can reach the IG account."""
    try:
        result = await ig.verify_token_and_account(
            token=data.access_token,
            ig_account_id=data.instagram_business_account_id,
        )
        return {"status": "ok", "account": result}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Campaign endpoints
# ---------------------------------------------------------------------------

@router.get("/campaigns")
def list_campaigns(db: Session = Depends(get_db)):
    campaigns = db.query(Campaign).order_by(Campaign.created_at.desc()).all()
    return [_campaign_dict(c) for c in campaigns]


@router.post("/campaigns")
def create_campaign(data: CampaignIn, db: Session = Depends(get_db)):
    campaign = Campaign(
        post_id=data.post_id,
        keywords=data.keywords,
        comment_reply=data.comment_reply,
        dm_message=data.dm_message,
        is_active=data.is_active,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return _campaign_dict(campaign)


@router.get("/campaigns/{campaign_id}")
def get_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = _get_or_404(db, campaign_id)
    return _campaign_dict(campaign)


@router.patch("/campaigns/{campaign_id}")
def update_campaign(campaign_id: int, data: CampaignUpdate, db: Session = Depends(get_db)):
    campaign = _get_or_404(db, campaign_id)
    for field, val in data.model_dump(exclude_none=True).items():
        setattr(campaign, field, val)
    campaign.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(campaign)
    return _campaign_dict(campaign)


@router.delete("/campaigns/{campaign_id}")
def delete_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = _get_or_404(db, campaign_id)
    db.delete(campaign)
    db.commit()
    return {"status": "deleted"}


@router.post("/campaigns/{campaign_id}/toggle")
def toggle_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = _get_or_404(db, campaign_id)
    campaign.is_active = not campaign.is_active
    campaign.updated_at = datetime.utcnow()
    db.commit()
    return {"is_active": campaign.is_active}


# ---------------------------------------------------------------------------
# Post preview endpoint (calls Graph API)
# ---------------------------------------------------------------------------

@router.get("/post-preview")
async def post_preview(post_id: str, db: Session = Depends(get_db)):
    config = db.query(Config).filter_by(id=1).first()
    token = (config.access_token if config else None) or None
    try:
        details = await ig.get_post_details(post_id=post_id, token=token)
        return {
            "id": details.get("id"),
            "caption": details.get("caption", ""),
            "thumbnail_url": details.get("thumbnail_url", ""),
            "media_type": details.get("media_type", ""),
            "permalink": details.get("permalink", ""),
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_404(db: Session, campaign_id: int) -> Campaign:
    campaign = db.query(Campaign).filter_by(id=campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


def _campaign_dict(c: Campaign) -> dict:
    return {
        "id": c.id,
        "post_id": c.post_id,
        "post_caption": c.post_caption or "",
        "post_thumbnail_url": c.post_thumbnail_url or "",
        "keywords": c.keywords,
        "keyword_list": c.keyword_list,
        "comment_reply": c.comment_reply,
        "dm_message": c.dm_message,
        "is_active": c.is_active,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }
