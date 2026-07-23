from fastapi import HTTPException
from app import llm
from app.schemas.chat import ChatRequest, ChatResponse


def chat_completions(body: ChatRequest) -> ChatResponse:
  if body.model_provider == "deepseek":
    return llm.deepseek.ask_llm(
      model=body.model,
      messages=body.messages, 
      temperature=body.temperature
    )
  else:
    raise HTTPException(status_code=404, detail="暂不支持该模型")