# agent/dispatch.py
import json
import logging

from pydantic import ValidationError

from .tools import REGISTRY

logger = logging.getLogger("agent")


def dispatch(tool_call) -> str:
  """执行一个工具调用，返回一段给模型看的字符串。"""
  name = tool_call.function.name
  
  tool = REGISTRY.get(name)
  if tool is None:
    logger.warning("工具名不存在: %s", name)
    return f"错误：不存在名为 {name} 的工具。可用工具：{'，'.join(REGISTRY)}"
  
  try:
    args = tool.args_model.model_validate_json(tool_call.function.arguments)
  except ValidationError as e:
    brief = "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors())
    logger.warning("参数校验失败 %s(%s): %s", name, tool_call.function.arguments, brief)
    return f"参数校验失败：{brief}。请修正参数之后重新调用。"
  except json.JSONDecodeError:
    logger.warning("参数不是合法 JSON %s: %s", name, tool_call.function.arguments)
    return "参数不是合法 JSON，请重新生成。"
  
  try:
    return tool.func(args)
  except Exception as e:
    logger.exception("工具 %s 执行失败", name)
    return f"工具执行失败：{type(e).__name__}: {e}"