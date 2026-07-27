from pydantic import BaseModel, Field
from typing import Literal
  
  
class ChatMessage(BaseModel):
  role: Literal["user", "system", "assistant"]
  content: str
  
  
class ChatRequest(BaseModel):
  messages: list[ChatMessage]
  model_provider: Literal["deepseek"] = "deepseek"
  model: str = "deepseek-chat"
  temperature: float = Field(default=0.7, ge=0, le=2)
  max_token: int | None = None
  
  
class ChatResponse(BaseModel):
  content: str
  model: str
  usage: None # TODO