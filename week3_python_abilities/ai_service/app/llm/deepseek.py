from dotenv import load_dotenv
from app.schemas.chat import ChatMessage, ChatResponse
import httpx
import os


load_dotenv()


URL = "https://api.deepseek.com/chat/completions"
API_KEY = os.getenv("DEEPSEEK_API_KEY")


header = {
  "Authorization": f"Bearer {API_KEY}",
  "Content-Type": "application/json"
}


def ask_llm(messages: list[ChatMessage], temperature: float = 0.7) -> ChatResponse:
  payload = {
    "model": "deepseek-chat",
    "temperature": temperature,
    "messages": [m.model_dump() for m in messages]
  }
  
  response = httpx.post(url=URL, headers=header, json=payload)
  response.raise_for_status()
  data = response.json()
  
  return ChatResponse(
    content=data["choices"][0]["message"]["content"],
    model="deepseek-chat"
  )
  