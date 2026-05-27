from openai import OpenAI
from dotenv import load_dotenv
import os
import json
import sys

# 加载全局环境变量
load_dotenv()

# 创建 OpenAI 规范客户端
client = OpenAI(
  api_key=os.getenv("DEEPSEEK_API_KEY"),
  base_url="https://api.deepseek.com"
)

# 加载系统提示词 (system prompt)
with open("prompts/system_prompt.txt", "r", encoding="utf-8") as f:
  system_prompt = f.read()
  
# 攻击日志
file_path = "logs/attack_logs.json"

if os.path.exists(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        attack_logs = json.load(f)
else:
    attack_logs = []
    
print("===== LLM 红蓝对抗测试终端 =====")
print("提示：支持多行输入。输入完成后，在【新的一行】输入 :q 并回车，或直接输入 exit 退出程序。")
print("==============================\n")

# 提示词攻击主循环
while True:
  print("Attack> (请输入载荷，结束后换行输入 :q 提交)")
  
  # 获取多行输入
  lines = []
  is_exit_triggered = False # 控制程序退出的变量
  
  while True:
    try:
      line = input(">> ")
      
      # 1. 完全没有输入内容，直接 exit，表示想退出程序
      if line == "exit" and not lines:
        is_exit_triggered = True
        break
      
      # 2. 输入了 :q，表示当前载荷输入完毕，准备提交 API
      if line == ":q":
        break
      
      lines.append(line)
    
    except EOFError:
      # 支持 Ctrl+D / Ctrl+Z 结束当前输入
      break
    
  # 是否退出程序
  if is_exit_triggered:
    print("\n退出测试程序")
    break
  
  user_input = "\n".join(lines).strip()
  
  if not user_input:
    print("\n输入为空，请重新输入。\n")
    continue
  
  print("\n[正在发送请求至 Deepseek ...]")
  
  try:
    response = client.chat.completions.create(
      model="deepseek-chat",
      messages=[
        {
          "role": "system",
          "content": system_prompt
        },
        {
          "role": "user",
          "content": user_input
        }
      ]
    )
    
    answer = response.choices[0].message.content
    
    print("\n===== RESPONSE =====")
    print(answer)
    print("=====================\n")
    
    attack_logs.append({
      "attack": user_input,
      "response": answer
    })
  
  except Exception as e:
    print("\n[错误] API 调用失败: {e}\n")
  
# 记录攻击日志
with open(file_path, "w", encoding="utf-8") as f:
    json.dump(attack_logs, f, ensure_ascii=False, indent=2)