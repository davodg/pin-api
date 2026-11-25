import logging
import os
import secrets
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.config import Config
from app.models.employee_feedback import (
    FeedbackCreate,
    FeedbackDeleted,
    FeedbackEnvelope,
    FeedbackReplace,
    FeedbackResponse,
    FeedbackUpdate,
)
from app.models.feedback_filters import FeedbackFilters
from app.repositories.feedback_repository import FeedbackNotFound, FeedbackRepository
from app.repositories.user_repository import UserRepository
from app.security.auth import (
    AuthService,
    get_auth_service,
    get_current_user,
    limit_login,
    password_hasher,
    require_role,
)
from app.services.feedback_service import FeedbackService
from app.storage.postgres import Postgres

APP_NAME = os.getenv("APP_NAME", "pin-api")
API_ENV = os.getenv("API_ENV", "dev")

logger = logging.getLogger("uvicorn.error")

@asynccontextmanager
async def lifespan(app: FastAPI):
    config = Config()
    config.validate_auth()
    dummy_hash = await run_in_threadpool(password_hasher.hash, secrets.token_urlsafe(32))
    db = Postgres()
    try:
        await db.open()
        app.state.auth_service = AuthService(UserRepository(db), config, dummy_hash)
        app.state.feedback_service = FeedbackService(FeedbackRepository(db))
        logger.info("Starting %s (env=%s)", APP_NAME, API_ENV)
        yield
    finally:
        await db.close()


app = FastAPI(title=APP_NAME, version="0.1.0", lifespan=lifespan)
router = APIRouter(prefix="/api/v1", dependencies=[Depends(get_current_user)])


async def get_feedback_service(request: Request):
    return request.app.state.feedback_service


@app.get("/health")
async def health():
    return {"status": "ok", "app": APP_NAME, "env": API_ENV}

@app.get("/")
async def root():
    return {"message": f"{APP_NAME} is running", "env": API_ENV}

@router.post(
    "/feedback",
    response_model=FeedbackEnvelope[FeedbackResponse],
    dependencies=[Depends(require_role("admin"))],
)
async def create_feedback(
    feedback: FeedbackCreate,
    feedback_service: FeedbackService = Depends(get_feedback_service),
):
    return await feedback_service.create(feedback)

@router.get(
    "/feedback",
    response_model=FeedbackEnvelope[list[FeedbackResponse] | FeedbackResponse | None],
    dependencies=[Depends(require_role("viewer", "admin"))],
)
async def get_feedback(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    filters: FeedbackFilters = Depends(),
    feedback_service: FeedbackService = Depends(get_feedback_service),
):
    return await feedback_service.get(page, limit, filters)

@router.delete(
    "/feedback/{feedback_id}",
    response_model=FeedbackEnvelope[FeedbackDeleted],
    dependencies=[Depends(require_role("admin"))],
)
async def delete_feedback(
    feedback_id: UUID,
    feedback_service: FeedbackService = Depends(get_feedback_service),
):
    return await feedback_service.delete(feedback_id)

@router.put(
    "/feedback/{feedback_id}",
    response_model=FeedbackEnvelope[FeedbackResponse],
    dependencies=[Depends(require_role("admin"))],
)
async def update_feedback(
    feedback_id: UUID,
    feedback: FeedbackReplace,
    feedback_service: FeedbackService = Depends(get_feedback_service),
):
    return await feedback_service.update(feedback_id, feedback)

@router.patch('/feedback/{feedback_id}', response_model=FeedbackEnvelope[FeedbackResponse],
              dependencies=[Depends(require_role('admin'))])
async def patch_feedback(
    feedback_id: UUID,
    feedback: FeedbackUpdate,
    feedback_service: FeedbackService = Depends(get_feedback_service),
):
    return await feedback_service.patch(feedback_id, feedback)


@app.exception_handler(FeedbackNotFound)
async def feedback_not_found(request: Request, exc: FeedbackNotFound):
    return JSONResponse(status_code=404, content={'detail': 'Feedback not found'})


app.include_router(router)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=128)


@app.post('/auth/token', dependencies=[Depends(limit_login)])
async def login(credentials: LoginRequest, response: Response, service: AuthService = Depends(get_auth_service)):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Pragma'] = 'no-cache'
    return await service.authenticate(credentials.username, credentials.password)
