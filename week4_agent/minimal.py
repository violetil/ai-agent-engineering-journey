from openai import OpenAI
from dotenv import load_dotenv
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, asdict
from pydantic import BaseModel, Field, ValidationError
from typing import Annotated
from datetime import datetime, timezone
from pathlib import Path
import os
import ast
import math
import operator
import json
import logging
import time


load_dotenv()


base_url = "https://api.deepseek.com"
api_key = os.getenv("DEEPSEEK_API_KEY")


client = OpenAI(
  base_url=base_url,
  api_key=api_key
)


@dataclass(frozen=True)
class Tool:
  name: str
  description: str
  args_model: type[BaseModel]
  func: Callable[[BaseModel], str]
  
@dataclass
class StepTrace:
  index: int
  thought: str | None
  tool_name: str | None
  tool_args: str | None
  tool_result: str | None
  prompt_tokens: int
  completion_tokens: int
  latency_ms: int
  
  
REGISTRY: dict[str, Tool] = {}


LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

_file_handler = logging.FileHandler(LOG_DIR / "agent.log", encoding="utf-8")
_file_handler.setLevel(logging.INFO)

_console_handler = logging.StreamHandler()
_console_handler.setLevel(logging.WARNING)

logging.basicConfig(
  level=logging.INFO,
  format="%(asctime)s %(levelname)-8s | %(message)s",
  handlers=[_file_handler, _console_handler]
)

logger = logging.getLogger("agent")


_BINOPS = {
  ast.Add: operator.add,
  ast.Sub: operator.sub,
  ast.Mult: operator.mul,
  ast.Div: operator.truediv,
  ast.FloorDiv: operator.floordiv,
  ast.Mod: operator.mod,
  ast.Pow: operator.pow,
}
_UNOPS = {
  ast.UAdd: operator.pos,
  ast.USub: operator.neg,
}

_GRAMMAR = "只支持数字、括号和 + - * / // % ** 运算。"

_OP_HINTS = {
  ast.BitXor: "^ 在这里是按位异或，乘方请用 **",
  ast.BitOr: "不支持按位或 |",
  ast.BitAnd: "不支持按位与 &",
  ast.LShift: "不支持位移 <<",
  ast.RShift: "不支持位移 >>",
}
_NODE_HINTS = {
  ast.Call: "不支持函数调用，例如 sqrt(16) 请改写成 16 ** 0.5",
  ast.Name: "不支持变量或常量名，例如 pi、e，请直接填写数字",
  ast.Attribute: "不支持属性访问",
  ast.Tuple: "表达式里出现了逗号，数字不要写千分位分隔符，1,000 请写成 1000",
  ast.Compare: "不支持比较运算",
  ast.BoolOp: "不支持 and / or",
  ast.IfExp: "不支持条件表达式",
  ast.Lambda: "不支持 lambda",
  ast.Subscript: "不支持下标取值",
  ast.NamedExpr: "不支持海象运算符 :=",
}


def register(tool: Tool) -> None:
  REGISTRY[tool.name] = tool
  
  
def tools_schema() -> list[dict]:
  """把注册表翻译成函数说明书"""
  return [{
    "type": "function",
    "function": {
      "name": t.name,
      "description": t.description,
      "parameters": t.args_model.model_json_schema(),
    }
  } for t in REGISTRY.values()]


class GetWeatherArgs(BaseModel):
  city: Annotated[str, Field(description="城市名，如 北京")]

def get_weather(args: GetWeatherArgs) -> str:
  fake_db = {
    "北京": "晴天 25度",
    "上海": "小雨 20度",
    "深圳": "暴雨 18度"
  }
  
  return fake_db.get(args.city, "未知天气")

register(Tool(
  name="get_weather",
  description="获取某个城市的当前天气。需要知道某地天气时使用。",
  args_model=GetWeatherArgs,
  func=get_weather
))


_WEEKDAYS = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")

class NowArgs(BaseModel):
  pass

def now(args: NowArgs) -> str:
  t = datetime.now(timezone.utc).astimezone()
  return f"{t.isoformat(sep=' ', timespec="seconds")} {_WEEKDAYS[t.weekday()]}"

register(Tool(
  name="now",
  description=(
    "获取服务器所在时区的当前日期时间。"
    "返回格式为「YYYY-MM-DD HH:MM:SS+时区偏移 星期X」，"
    "例如 2026-08-15 15:20:35+08:00 星期六。"
    "需要知道今天几号、现在几点、今天星期几时使用。"
  ),
  args_model=NowArgs,
  func=now
))


class ExpressionError(ValueError):
  """表达式不合法：可预期的业务失败，文本喂回给模型。"""

MAX_EXPONENT = 1000
MAX_RESULT_DIGITS = 100
MAX_DEPTH = 50

  
def _check_pow(base: int | float, exponent: int | float) -> None:
  if not (isinstance(base, int) and isinstance(exponent, int)):
    return
  if exponent < 0 or abs(base) <= 1:
    return
  if exponent > MAX_EXPONENT:
    raise ExpressionError(f"指数 {exponent} 太大，上限是 {MAX_EXPONENT}。")
  if exponent * math.log10(abs(base)) > MAX_RESULT_DIGITS:
    raise ExpressionError(f"{base} ** {exponent} 的结果超过 {MAX_RESULT_DIGITS} 位数字，请换成更小的数。")

def _eval_node(node: ast.AST, depth: int = 0) -> int | float:
  if depth > MAX_DEPTH:
    raise ExpressionError(f"表达式嵌套超过 {MAX_DEPTH} 层，太复杂了。")
  
  if isinstance(node, ast.Expression):
    return _eval_node(node.body, depth + 1)
  
  if isinstance(node, ast.Constant):
    if type(node.value) in (int, float):
      return node.value
    raise ExpressionError(f"不支持的值 {node.value!r}, {_GRAMMAR}")
  
  if isinstance(node, ast.UnaryOp):
    func = _UNOPS.get(type(node.op))
    if func is None:
      raise ExpressionError(f"不支持这个一元运算符。{_GRAMMAR}")
    return func(_eval_node(node.operand, depth + 1))
  
  if isinstance(node, ast.BinOp):
    func = _BINOPS.get(type(node.op))
    if func is None:
      hint = _OP_HINTS.get(type(node.op), "不支持这个运算符")
      raise ExpressionError(f"{hint}。{_GRAMMAR}")
    left = _eval_node(node.left, depth + 1)
    right = _eval_node(node.right, depth + 1)
    if isinstance(node.op, ast.Pow):
      _check_pow(left, right)
    return func(left, right)
  
  hint = _NODE_HINTS.get(type(node), "表达式里有不支持的语法")
  raise ExpressionError(f"{hint}。{_GRAMMAR}")

def _format(value: int | float) -> str:
  if not isinstance(value, (int, float)):
    raise ExpressionError("结果不是实数（例如负数开平方），无法表示。")
  if isinstance(value, float):
    if math.isinf(value) or math.isnan(value):
      raise ExpressionError("结果超出浮点数范围。")
    if value.is_integer():
      return str(int(value))
    return f"{value:.12g}"
  return str(value)

class CalculatorArgs(BaseModel):
  expression: Annotated[str, Field(
    description=(
      "纯数学表达式，只能包含数字、括号和 + - * / // % ** 。"
      "不支持函数（sqrt、abs）、变量名（pi、e）和千分位逗号。"
      "开平方请写成 16 ** 0.5。"
    )
  )]
  
def calculator(args: CalculatorArgs) -> str:
  try:
    tree = ast.parse(args.expression, mode="eval")
    return _format(_eval_node(tree))
  except ExpressionError as e:
    return f"计算失败: {e}"
  except SyntaxError:
    return f"计算失败: 表达式语法错误。{_GRAMMAR}"
  except ZeroDivisionError:
    return "计算失败: 除数不能为 0。"
  except OverflowError:
    return "计算失败: 结果超出浮点数范围。"
  
register(Tool(
  name="calculator",
  description=(
    "计算一个数学表达式并返回结果字符串。"
    "只支持数字、括号和 + - * / // % ** 运算，"
    "不支持函数调用、变量名和千分位逗号，开平方请写成 16 ** 0.5。"
    "结果保留 12 位有效数字，整数结果不带小数点。"
    "表达式非法时返回以「计算失败:」开头的说明，请按说明修改后重试。"
  ),
  args_model=CalculatorArgs,
  func=calculator
))


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
  

def _preview(text: str | None, limit: int = 100) -> str:
  if not text:
    return ""
  flat = " ".join(text.split())
  return flat if len(flat) <= limit else flat[:limit] + "..."


def _dump_trace(user_input: str, traces: list[StepTrace], messages: list[dict]) -> Path:
  path = LOG_DIR / f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
  path.write_text(
    json.dumps(
      {
        "input": user_input,
        "steps": [asdict(t) for t in traces],
        "messages": messages,
      },
      ensure_ascii=False,
      indent=2,
    ),
    encoding="utf-8",
  )
  return path


def _finish(user_input: str, traces: list[StepTrace], messages: list[dict],
            answer: str, started: float) -> str:
  per_step = {t.index: (t.prompt_tokens, t.completion_tokens) for t in traces}
  total_in = sum(p for p, _ in per_step.values())
  total_out = sum(c for _, c in per_step.values())
  elapsed = time.perf_counter() - started
  print(f"总计 {len(per_step)} 步，{total_in:,} in / {total_out:,} out，{elapsed:.1f}s")
  path = _dump_trace(user_input, traces, messages)
  logger.info("会话结束：%d 步 %d in / %d out %.1fs -> %s",
              len(per_step), total_in, total_out, elapsed, path.name)
  print(f"trace 已写入 {path}")
  return answer


MAX_TOOL_CHARS = 2000

def truncate(text: str) -> str:
  if len(text) <= MAX_TOOL_CHARS:
    return text
  return text[:MAX_TOOL_CHARS] + f"\n...（已截断，原文共 {len(text)} 字符）"


def run_agent(user_input: str, max_steps: int = 10) -> str:
  messages = [
    {"role": "system", "content": "你是一个可以调用工具的助手"},
    {"role": "user", "content": user_input}
  ]
  traces: list[StepTrace] = []
  started = time.perf_counter()
  logger.info("=== 新会话 === %s", user_input)
  seen: Counter[tuple[str, str]] = Counter()
  
  for step in range(1, max_steps + 1):
    t0 = time.perf_counter()
    res = client.chat.completions.create(
      model="deepseek-chat",
      messages=messages,
      tools=tools_schema()
    )
    latency_ms = int((time.perf_counter() - t0) * 1000)
    
    message = res.choices[0].message
    messages.append(message.model_dump(exclude_none=True))
    usage = res.usage
    
    print(f"\n┌ step {step}  ({usage.prompt_tokens:,} in / "
          f"{usage.completion_tokens:,} out, {latency_ms / 1000:.1f}s)")
    if not message.tool_calls:
      print(f"└ done  {_preview(message.content)}\n")
      traces.append(StepTrace(step, message.content, None, None, None,
                              usage.prompt_tokens, usage.completion_tokens, latency_ms))
      return _finish(user_input, traces, messages, message.content, started)
    
    if message.content:
      print(f"│ think {_preview(message.content)}")
    
    for tc in message.tool_calls:
      key = (tc.function.name, tc.function.arguments)
      seen[key] += 1
      if seen[key] >= 3:
        result = "你已经用完全相同的参数调用过这个工具两次，结果不会改变。请换一种方法，或者直接基于现有信息给出结论。"
      else:
        result = truncate(dispatch(tc))
      messages.append({
        "role": "tool",
        "tool_call_id": tc.id,
        "content": result
      })
      print(f"│ tool  {tc.function.name} {tc.function.arguments}")
      print(f"│ obs   {_preview(result)}")
      logger.info("step %d %s(%s) -> %s", step, tc.function.name,
                  tc.function.arguments, _preview(result))
      traces.append(StepTrace(step, message.content, tc.function.name,
                              tc.function.arguments, result,
                              usage.prompt_tokens, usage.completion_tokens, latency_ms))
      
    print(f"└ 本步执行 {len(message.tool_calls)} 个工具")
  
  messages.append({
    "role": "user",
    "content": "已达到工具调用次数上限。请基于目前已获得的信息，直接给出你的最佳答案，并说明还缺什么信息。"
  })
  final = client.chat.completions.create(
    model="deepseek-chat",
    messages=messages,
    tools=tools_schema(),
    tool_choice="none",
  )
  return _finish(user_input, traces, messages, final.choices[0].message.content, started)


if __name__ == "__main__":
  print(run_agent(input(">> ")))