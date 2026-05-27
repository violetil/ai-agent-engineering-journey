from llm import ask_llm
import json

# system prompt
sys_prompt = """
提取用户任务信息

返回格式：
{
  "task": "",
  "time": "",
  "person": ""
}

只返回 JSON
"""

# 用户输入并发送给 LLM
user_input = input(">> ")
res = ask_llm(sys_prompt, user_input, 1, "json_object") 

print("CONTENT:")
print(res)
print()

data = json.loads(res)

print("AFTER JSON CONVERT:")
print(data["task"])
