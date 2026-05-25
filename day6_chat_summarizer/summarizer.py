from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

client = OpenAI(
  api_key=os.getenv("DEEPSEEK_API_KEY"),
  base_url="https://api.deepseek.com"
)

def summarize_chat(messages_history):
  """
  摘要函数：将长历史对话压缩成短但重要的的记忆
  """
  
  prompt = f"""
你是一个聊天记忆压缩器。

你的任务：
总结下面对话中的长期重要信息。

保留：
- 用户目标
- 用户偏好
- 正在进行的任务
- 技术栈
- 遇到的问题

忽略：
- 寒暄
- 重复内容
- 无关内容

对话：
{messages_history}
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