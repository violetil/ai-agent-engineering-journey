import json

MEMORY_FILE = "memory.json"


def load_memory():
  with open(MEMORY_FILE, "r", encoding="utf-8") as f:
    return json.load(f)
  

def save_memory(memory):
  with open(MEMORY_FILE, "w", encoding="utf-8") as f:
    json.dump(memory, f, ensure_ascii=False, indent=2)
    

def add_message(role, content):
  memory = load_memory()
  
  memory["recent_messages"].append({
    "role": role,
    "content": content
  })
  
  save_memory(memory)