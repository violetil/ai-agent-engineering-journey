import os
import httpx
import asyncio
from dotenv import load_dotenv


load_dotenv()

URL = "https://api.deepseek.com/chat/completions"
API_KEY = os.getenv("DEEPSEEK_API_KEY")


async def ask_llm(
  client: httpx.AsyncClient,
  user_prompt: str
) -> str:
  """单个异步 LLM 请求"""
  
  payload = {
    "model": "deepseek-chat",
    "messages": [{ "role": "user", "content": user_prompt }],
  }
  response = await client.post(URL, json=payload)
  response.raise_for_status() # 检查返回的状态码
  data = response.json() # 解析返回的数据
  return data["choices"][0]["message"]["content"]


async def ask_many(prompts: list[str]) -> list[str]:
  """并发请求多个 prompt"""
  
  headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
  }
  async with httpx.AsyncClient(headers=headers, timeout=60) as client:
    tasks = [ask_llm(client, p) for p in prompts] # 创建例程列表
    results = await asyncio.gather(*tasks) # 同时启动多个例程
    return results


async def main():
  prompts = [
    "1+1等于几？",
    "用一句话解释Python。",
    "一句话说明无畏契约和CS2的区别。"
  ]
  results = await ask_many(prompts)
  for prompt, answer in zip(prompts, results):
    print(f"Q: {prompt}")
    print(f"A: {answer}\n")


if __name__ == "__main__":
  asyncio.run(main()) # 创建事件循环支持异步操作


# async with 是什么语法，with 的作用是什么？
# zip 是什么？作用和基本用法？