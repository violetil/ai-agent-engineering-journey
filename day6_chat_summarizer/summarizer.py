from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

client = OpenAI(
  api_key=os.getenv("DEEPSEEK_API_KEY"),
  base_url="https://api.deepseek.com"
)

def summarize_chat(old_memory, new_messages):

  prompt = f"""
你是 AI 记忆系统。

任务：
融合旧记忆和新对话。

旧记忆：
{old_memory}

新对话：
{new_messages}

要求：
1. 保留长期重要信息
2. 删除重复信息
3. 删除短期无意义内容
4. 不超过200字
5. 只输出字符串，不能是其他任何格式，如Markdown和JSON
"""

  messages = [
    {
      "role": "user",
      "content": prompt
    }
  ]
  
  response = client.chat.completions.create(
    model="deepseek-chat",
    messages=messages
  )
  
  return response.choices[0].message.content