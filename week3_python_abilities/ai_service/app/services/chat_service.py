from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.auth import UserRecord
from app.core.errors import UnsupportedModelError, QuotaExceededError
from app.repositories.user_repo import update_user
from app.services.quota_service import ensure_daily_quota
from app import llm
import httpx


MODEL_PROVIDERS = ['deepseek']


# ---------- CHAT METHODS ----------
async def chat_completions(
  body: ChatRequest, 
  user: UserRecord,
  client: httpx.AsyncClient
) -> ChatResponse:
  ensure_daily_quota(user)
  
  if user.daily_quota <= 0:
    raise QuotaExceededError("额度不够")
  
  if body.model_provider not in MODEL_PROVIDERS:
    raise UnsupportedModelError(body.model_provider)
  
  result = await llm.deepseek.ask_llm(
    client=client,
    model=body.model,
    messages=body.messages, 
    temperature=body.temperature
  )
  
  user.daily_quota -= 1
  update_user(email=user.email, user=user)
  return result