from dotenv import load_dotenv
from app.schemas.chat import ChatMessage, ChatResponse
from app.core.errors import UpstreamServiceError, UpstreamTimeoutError
import httpx
import os


load_dotenv()


URL = "https://api.deepseek.com/chat/completions"
API_KEY = os.getenv("DEEPSEEK_API_KEY")
TIMEOUT = httpx.Timeout(60.0, connect=5.0)


header = {
  "Authorization": f"Bearer {API_KEY}",
  "Content-Type": "application/json"
}


def ask_llm(model: str, messages: list[ChatMessage], temperature: float = 0.7) -> ChatResponse:
  payload = {
    "model": model,
    "temperature": temperature,
    "messages": [m.model_dump() for m in messages]
  }
  try:
    response = httpx.post(url=URL, headers=header, json=payload, timeout=TIMEOUT)
    response.raise_for_status()
  except httpx.TimeoutException as e:
    raise UpstreamTimeoutError("LLM 服务响应超时") from e
  except httpx.HTTPStatusError as e:
    raise UpstreamServiceError(f"LLM 服务返回错误：HTTP {e.response.status_code}") from e
  except httpx.RequestError as e:
    raise UpstreamServiceError(f"无法连接 LLM 服务：{e}") from e
  
  data = response.json()
  try:
    content = data["choices"][0]["message"]["content"]
  except (KeyError, IndexError) as e:
    raise UpstreamServiceError("LLM 返回了无法解析的响应结构") from e
  
  return ChatResponse(
    content=content,
    model=data.get("model", model)
  )
  