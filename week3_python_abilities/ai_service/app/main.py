from fastapi import FastAPI, status, Request
from contextlib import asynccontextmanager
import httpx

from app.schemas.auth import UserCreate, UserOut, SignInIn, TokenOut
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import chat_completions
from app.services.auth_service import register_user, login
from app.api.deps import CurrentUser
from app.core.error_handlers import register_error_handlers
from app.core.config import deepseek_headers, HTTP_TIMEOUT


@asynccontextmanager
async def lifesapn(app: FastAPI):
  async with httpx.AsyncClient(headers=deepseek_headers(), timeout=HTTP_TIMEOUT) as client:
    app.state.http_client = client
    yield


app = FastAPI(title="Violet AI API Service", lifespan=lifesapn)
register_error_handlers(app)


# ---------- Routers ----------
@app.get("/")
def root():
  return { "message": "Violet AI API Service" }
  

@app.post("/chat/completions", response_model=ChatResponse)
async def _chat_completions(body: ChatRequest, user: CurrentUser, request: Request):
  return await chat_completions(body, user, request.app.state.http_client)


@app.post("/auth/sign_up", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def _sign_up(user: UserCreate):
  """Create an user in database"""
  return register_user(user)


@app.post("/auth/sign_in", response_model=TokenOut)
def _sign_in(body: SignInIn):
  """Check email and password."""
  return login(body)