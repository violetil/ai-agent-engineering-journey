from dotenv import load_dotenv
from pydantic import BaseModel, Field
import asyncio
import httpx
import os


load_dotenv()


URL = "https://api.deepseek.com/chat/completions"
API_KEY = os.getenv("DEEPSEEK_API_KEY")


# ---------- Schemas ----------
class Message(BaseModel):
  role: str
  content: str


# --------- Dependces ----------
async def async_call_llm(
  client: httpx.AsyncClient, 
  message: Message
) -> str:
  """Single LLM request"""
  
  payload = {
    "model": "deepseek-chat",
    "messages": [message]
  }
  
  response = await client.post(URL, json=payload)
  response.raise_for_status()
  data = response.json()
  return data["choices"][0]["message"]["content"]


async def async_call_llm_many(messages: list[Message]) -> list[str]:
  """Async multiple LLM requests"""
  
  headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
  }
  
  async with httpx.AsyncClient(headers=headers, timeout=15) as client:
    tasks = [async_call_llm(client, message) for message in messages]
    responses = await asyncio.gather(*tasks)
    return responses
  

# ---------- APIs ----------
async def ask_llm(prompt: str) -> str:
  """Take user prompt, get LLM response."""
  
  headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
  }
  
  async with httpx.AsyncClient(headers=headers, timeout=15) as client:
    return await async_call_llm(client, { "role": "user", "content": prompt })
  
  
async def ask_llm_many(prompts: list[str]) -> list[str]:
  """Take multiple user prompts, get LLM responses."""
  
  return await async_call_llm_many([{ "role": "user", "content": prompt } for prompt in prompts])