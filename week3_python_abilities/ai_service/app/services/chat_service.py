from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.auth import UserRecord
from app.core.errors import UnsupportedModelError, QuotaExceededError
from app.repositories.user_repo import update_user
from app.services.quota_service import ensure_daily_quota
from app import llm

from collections.abc import AsyncIterator
import json
import httpx


MODEL_PROVIDERS = ['deepseek']


# ---------- DEPENDS ----------
def _prepare_chat(body: ChatRequest, user: UserRecord) -> None:
  ensure_daily_quota(user)
    
  if user.daily_quota <= 0:
    raise QuotaExceededError("额度不够")
  
  if body.model_provider not in MODEL_PROVIDERS:
    raise UnsupportedModelError(body.model_provider)


# ---------- CHAT METHODS ----------
async def chat_completions(
  body: ChatRequest, 
  user: UserRecord,
  client: httpx.AsyncClient
) -> ChatResponse:
  _prepare_chat(body, user)
  
  result = await llm.deepseek.ask_llm(
    client=client,
    model=body.model,
    messages=body.messages, 
    temperature=body.temperature
  )
  
  user.daily_quota -= 1
  update_user(email=user.email, user=user)
  return result


async def chat_completions_stream(
  body: ChatRequest,
  user: UserRecord,
  client: httpx.AsyncClient
) -> AsyncIterator[str]:
  _prepare_chat(body, user)
  
  async for piece in llm.deepseek.stream_llm(
    client=client,
    model=body.model,
    messages=body.messages,
    temperature=body.temperature
  ):
    payload = json.dumps({"content": piece}, ensure_ascii=False)
    yield f"data: {payload}\n\n"
    
  yield "data: [DONE]\n\n"
  
  user.daily_quota -= 1
  update_user(email=user.email, user=user)
