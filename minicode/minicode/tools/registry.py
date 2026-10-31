# minicode/tools/registry.py
from collections.abc import Callable
from dataclasses import dataclass
from pydantic import BaseModel


class ToolError(Exception):
  """工具无法完成任务、但模型看了说明之后有机会修正的那类失败。
  
  消息文本会原样回喂给模型，所以要写成「发生了什么 + 下一步怎么做」。
  不要用它包装 bug（比如 KeyError），那类异常让它自然抛出，dispatch 会兜底。
  """


@dataclass
class Tool:
  name: str
  description: str
  args_model: type[BaseModel]
  func: Callable[[BaseModel], str]
  
  
REGISTRY: dict[str, Tool] = {}


def register(tool: Tool) -> None:
  if tool.name in REGISTRY:
    raise RuntimeError(f"工具重名：{tool.name}")
  REGISTRY[tool.name] = tool
  
  
def tools_schema() -> list[dict]:
  return [{
    "type": "function",
    "function": {
      "name": t.name,
      "description": t.description,
      "parameters": t.args_model.model_json_schema(),
    },
  } for t in REGISTRY.values()]