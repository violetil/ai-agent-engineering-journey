from app.schemas.chat import ChatMessage, ChatResponse
from app.core.errors import UpstreamServiceError, UpstreamTimeoutError
from app.core.config import DEEPSEEK_URL
import httpx
import json


async def ask_llm(
  client: httpx.AsyncClient,
  model: str, 
  messages: list[ChatMessage], 
  temperature: float = 0.7
) -> ChatResponse:
  payload = {
    "model": model,
    "temperature": temperature,
    "messages": [m.model_dump() for m in messages]
  }
  try:
    response = await client.post(url=DEEPSEEK_URL, json=payload)
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
  
  
async def stream_llm(
  client: httpx.AsyncClient,
  model: str,
  messages: list[ChatMessage],
  temperature: float = 0.7
):
  payload = {
    "model": model,
    "temperature": temperature,
    "stream": True,
    "messages": [m.model_dump() for m in messages]
  }
  
  try:
    async with client.stream("POST", url=DEEPSEEK_URL, json=payload) as response:
      response.raise_for_status()
      async for line in response.aiter_lines():
        if not line or not line.startswith("data: "):
          continue
        data = line[len("data: "):]
        if data == "[DONE]":
          break
        
        try:
          chunk = json.loads(data)
          content = chunk["choices"][0]["delta"].get("content")
        except (json.JSONDecodeError, TypeError, IndexError, KeyError) as e:
          raise UpstreamServiceError("LLM 返回了无法解析的流式响应体结构") from e
        
        if content:
          yield content
  
  except httpx.TimeoutException as e:
    raise UpstreamTimeoutError("LLM 服务响应超时") from e
  except httpx.HTTPStatusError as e:
    raise UpstreamServiceError(f"LLM 服务返回错误：HTTP {e.response.status_code}") from e
  except httpx.RequestError as e:
    raise UpstreamServiceError(f"无法连接 LLM 服务 {e}") from e
  