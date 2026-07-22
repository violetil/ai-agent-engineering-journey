from app import llm
from app.schemas.chat import ChatRequest, ChatResponse


def chat_completions(body: ChatRequest) -> ChatResponse:
  if "deepseek" in body.model:
    return llm.deepseek.ask_llm(
      messages=body.messages, 
      temperature=body.temperature
    )