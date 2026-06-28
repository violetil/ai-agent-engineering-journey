# 标准库：读写 JSON 文件（把 Python dict/list 和 .json 文件互转）
import json

# 记忆文件路径；相对于运行 Python 时的工作目录，不是 .py 文件本身
MEMORY_FILE = "memory.json"


def load_memory():
  """从 memory.json 读取记忆，返回 dict。"""
  
  # with: 自动关闭文件；"r" 只读；utf-8 支持中文
  with open(MEMORY_FILE, "r", encoding="utf-8") as f:
    # 解析 JSON -> Python dict，并作为函数返回值
    return json.load(f)
  

def save_memory(memory):
  """把 memory dict 写回 memory.json (覆盖原文件)。"""
  
  # "w" 覆盖写入；ensure_ascii=False 保留中文；indent=2 格式化
  with open(MEMORY_FILE, "w", encoding="utf-8") as f:
    json.dump(memory, f, ensure_ascii=False, indent=2)
    

def add_message(role, content):
  """追加一条对话到 recent_messages 并保存。"""
  
  memory = load_memory()
  
  # 在 recent_messages 列表末尾追加一条 {role, content}
  memory["recent_messages"].append({
    "role": role,
    "content": content
  })
  
  save_memory(memory)