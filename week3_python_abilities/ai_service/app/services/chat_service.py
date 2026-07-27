from app.schemas.chat import ChatRequest, ChatResponse
from app.core.errors import UnsupportedModelError
from app import llm


# ---------- CHAT METHODS ----------
def chat_completions(body: ChatRequest) -> ChatResponse:
  if body.model_provider == "deepseek":
    return llm.deepseek.ask_llm(
      model=body.model,
      messages=body.messages, 
      temperature=body.temperature
    )
  raise UnsupportedModelError(body.model_provider)