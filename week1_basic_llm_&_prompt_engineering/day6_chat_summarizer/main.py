from memory_manager import (
  load_memory,
  save_memory,
  add_message
)

from token_manager import count_tokens
from summarizer import summarize_chat
from openai import OpenAI
from dotenv import load_dotenv
import os


TOKNE_LIMIT = 2000


messages = [
  { "role": "system", "content": "你是一个 AI 助手" }
]

load_dotenv()

client = OpenAI(
  api_key=os.getenv("DEEPSEEK_API_KEY"),
  base_url="https://api.deepseek.com"
)

def maybe_summarize():
  memory = load_memory()
  
  recent_messages = memory["recent_messages"]
  
  token_count = count_tokens(recent_messages)
  
  print(f"\n当前 token：{token_count}")
  
  if token_count > TOKNE_LIMIT:
    print("\n超过限制，开始摘要...")
    
    summary = summarize_chat(memory["long_term_memory"], recent_messages)
    
    # 覆盖摘要，清空最近消息
    memory["long_term_memory"] = summary
    memory["recent_messages"] = []
    
    save_memory(memory)
    
    print("摘要完成")

# System loop
while True:
  # 获取用户输入
  user_input = input("\nAsk >> ")
  
  # 加入最近记忆
  add_message("user", user_input)
  
  # 发送给 LLM 获取回复
  messages.append({
    "role": "system",
    "content": f"长期记忆：{load_memory()["long_term_memory"]}"
  })
  messages.extend(load_memory()["recent_messages"])
  
  response = client.chat.completions.create(
    model="deepseek-chat",
    messages=messages
  )
  
  # 记录回复
  add_message("assistant", response.choices[0].message.content)
  
  print("\n===== 回复 =====")
  print(response.choices[0].message.content)
  print("==================")
  
  # 检查是否需要摘要
  maybe_summarize()