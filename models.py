from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from database import Base


class Config(Base):
    """Stores Instagram credentials (one row, upserted on save)."""
    __tablename__ = "config"

    id = Column(Integer, primary_key=True, index=True, default=1)
    access_token = Column(String, nullable=True)
    page_id = Column(String, nullable=True)
    instagram_business_account_id = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Campaign(Base):
    """One campaign = one Instagram post with trigger keywords and auto-responses."""
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(String, nullable=False)
    post_caption = Column(Text, nullable=True)
    post_thumbnail_url = Column(String, nullable=True)
    keywords = Column(String, nullable=False)        # comma-separated, e.g. "link,send me,info"
    comment_reply = Column(Text, nullable=False)
    dm_message = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def keyword_list(self):
        return [k.strip().lower() for k in self.keywords.split(",") if k.strip()]


class ProcessedComment(Base):
    """Tracks comment IDs we've already handled — prevents duplicate replies/DMs."""
    __tablename__ = "processed_comments"

    id = Column(Integer, primary_key=True, index=True)
    comment_id = Column(String, unique=True, nullable=False, index=True)
    campaign_id = Column(Integer, nullable=True)
    processed_at = Column(DateTime, default=datetime.utcnow)
