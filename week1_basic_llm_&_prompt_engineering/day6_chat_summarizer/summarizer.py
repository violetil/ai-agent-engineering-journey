# OpenAI 官方 SDK；Deepseek 等兼容 API 也用这个客户端
from openai import OpenAI
# 从 .env 文件加载环境变量（如 API key）
from dotenv import load_dotenv
import os

# 读取项目根目录（或当前工作目录）下的 .env 文件
load_dotenv()

# 全局客户端，整个文件复用；base_url 指向 DeepSeek 而非 OpenAI
client = OpenAI(
  api_key=os.getenv("DEEPSEEK_API_KEY"),
  base_url="https://api.deepseek.com"
)

def summarize_chat(old_memory, new_messages):
  """调用 LLM，融合旧记忆与新对话，返回压缩后的摘要字符串。"""

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