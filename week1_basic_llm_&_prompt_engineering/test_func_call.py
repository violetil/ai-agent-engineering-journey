from llm import tool_call_llm
from llm import call_llm
from typing import Annotated
from pydantic import BaseModel, Field, ValidationError
import json


class GetWeatherArgs(BaseModel):
  city: Annotated[str, Field(description="城市名")]


# tools “给模型看的函数说明书”
tools = [
  {
    "type": "function",
    "function": {
      "name": "get_weather",
      "description": "获取某个城市的天气",
      "parameters": GetWeatherArgs.model_json_schema(),
    }
  }
]

# 定义函数
def get_weather(args: GetWeatherArgs) -> str:
    fake_weather_data = {
        "北京": "晴天 25度",
        "上海": "小雨 22度",
        "深圳": "多云 30度"
    }
    
    return fake_weather_data.get(args.city, "未知天气")

# 获取用户输入
user_input = input(">> ")

# 写入 messages
messages = [
    {
        "role": "user",
        "content": user_input
    }
]

# 请求模型
print("-> thinking...\n")
message = tool_call_llm(messages, tools)
print(f"-> RES:\n{message}\n")

# 解析函数调用
tool_call = message.tool_calls[0]
function_name = tool_call.function.name # 函数名

try:
  arguments = GetWeatherArgs.model_validate_json(tool_call.function.arguments) # 函数参数，解析 JSON 为 Python 类
except ValidationError as e:
  print(f"参数校验失败: {e}")
  raise

# 调用函数
if function_name == "get_weather":
    print("-> getting weather informations...")
    result = get_weather(arguments)
    
    # 把结果重新发给模型
    messages.append(message)
    messages.append({
        "role": "tool",
        "tool_call_id": tool_call.id,
        "content": result
    })
    
    print("-> thinking...")
    response = call_llm(messages)
    print("-> Done\n")
    print(response)
else:
    print("调用天气工具失败...")
    print("退出")