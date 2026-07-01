from openai import OpenAI
from dotenv import load_dotenv
from typing import TypedDict
import os
import json

# -- 类型定义 ---------------------------------------


class ChatMessage(TypedDict):
  role: str
  content: str
  
class AttackLogEntry(TypedDict):
  attack: str
  response: str


# -- 全局客户端 -------------------------------------


load_dotenv()

client = OpenAI(
  api_key=os.getenv("DEEPSEEK_API_KEY"),
  base_url="https://api.deepseek.com"
)


# -- 函数 -------------------------------------------


def load_system_prompt(path: str) -> str:
  with open(path, "r", encoding="utf-8") as f:
    return f.read()
  
  
def load_attack_logs(path: str) -> list[AttackLogEntry]:
  if os.path.exists(path):
    with open(path, "r", encoding="utf-8") as f:
      return json.load(f)
  return []
  
  
def save_attack_logs(path: str, logs: list[AttackLogEntry]) -> None:
  with open(path, "w", encoding="utf-8") as f:
    json.dump(logs, f, ensure_ascii=False, indent=2)
    
    
def read_multiline_input() -> tuple[str, bool]:
  lines: list[str] = []
  is_exit_triggered: bool = False
  
  while True:
    try:
      line = input(">> ")
      
      if line == "exit" and not lines:
        is_exit_triggered = True
        break
      
      if line == ":q":
        break
      
      lines.append(line)
      
    except EOFError:
      break
    
  return "\n".join(lines).strip(), is_exit_triggered

def call_llm(system_prompt: str, user_input: str) -> str | None:
  messages: list[ChatMessage] = [
    { "role": "system", "content": system_prompt },
    { "role": "user", "content": user_input }
  ]
  
  response = client.chat.completions.create(
    model="deepseek-chat",
    messages=messages,
  )
  
  return response.choices[0].message.content

def main() -> None:
  file_path: str = "logs/attack_logs.json"
  system_prompt: str = load_system_prompt("prompts/system_prompt.txt")
  attack_logs: list[AttackLogEntry] = load_attack_logs(file_path)
  
  print("===== LLM 红蓝对抗测试终端 =====")
  print("提示：支持多行输入。输入完成后，在【新的一行】输入 :q 并回车，或直接输入 exit 退出程序。")
  print("==============================\n")
    
  while True:
    print("Attack> (请输入载荷，结束后换行输入 :q 提交)")
    user_input, is_exit_triggered = read_multiline_input()
    
    if is_exit_triggered:
      print("\n退出测试程序")
      break
    
    if not user_input:
      print("\n输入为空，请重新输入。\n")
      break
    
    print("\n[正在发送请求至 Deepseek ...]")
    
    try:
      answer = call_llm(system_prompt, user_input)
      
      if answer is None:
        print("\n[错误] 模型返回为空\n")
        continue
      
      print("\n===== RESPONSE =====")
      print(answer)
      print("=====================\n")
      
      attack_logs.append({
        "attack": user_input,
        "response": answer,
      })
    
    except Exception as e:
      print(f"\n[错误] API 调用失败: {e}\n")
      
  save_attack_logs(file_path, attack_logs)
  
  
if __name__ == "__main__":
  main()