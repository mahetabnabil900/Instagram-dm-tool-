"""
Instagram Comment-to-DM Automation Tool
Entry point — run with: uvicorn main:app --reload
"""

import logging
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from database import Base, engine
from routes.webhook import router as webhook_router
from routes.api import router as api_router
from routes.dashboard import router as dashboard_router

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Create DB tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Instagram Comment-to-DM Automation",
    description="Automate comment replies and DMs based on keywords.",
    version="1.0.0",
    docs_url="/docs",
)

# Static files (CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Routers
app.include_router(webhook_router)
app.include_router(api_router)
app.include_router(dashboard_router)


@app.get("/health")
def health():
    return {"status": "ok"}
