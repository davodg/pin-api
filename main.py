import os
import logging
from fastapi import FastAPI, Depends, APIRouter
from app.services.feedback_service import FeedbackService
from app.models.feedback_filters import FeedbackFilters

APP_NAME = os.getenv("APP_NAME", "pin-api")
API_ENV = os.getenv("API_ENV", "dev")

logger = logging.getLogger("uvicorn.error")

app = FastAPI(title=APP_NAME, version="0.1.0")
router = APIRouter(prefix="/api/v1")

feedback_service = FeedbackService()

@app.on_event("startup")
async def on_startup():
    logger.info("Starting %s (env=%s)", APP_NAME, API_ENV)

@app.get("/health")
async def health():
    return {"status": "ok", "app": APP_NAME, "env": API_ENV}

@app.get("/")
async def root():
    return {"message": f"{APP_NAME} is running", "env": API_ENV}

@router.post("/feedback")
async def create_feedback(feedback: dict):
    return feedback_service.create(feedback)

@router.get("/feedback")
async def get_feedback(
    page: int = 1,
    limit: int = 10,
    filters: FeedbackFilters = Depends(),
):
    return feedback_service.get(page, limit, filters)

@router.delete("/feedback/{feedback_id}")
async def delete_feedback(feedback_id: str):
    return feedback_service.delete(feedback_id)

@router.put("/feedback/{feedback_id}")
async def update_feedback(feedback_id: str, feedback: dict):
    return feedback_service.update(feedback_id, feedback)

app.include_router(router)
