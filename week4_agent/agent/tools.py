# agent/tools.py
import ast
import math
import operator

from pathlib import Path
from pydantic import BaseModel, Field
from dataclasses import dataclass
from datetime import datetime, timezone
from collections.abc import Callable
from typing import Annotated

from .config import PKG_ROOT
from .context import MAX_TOOL_CHARS


@dataclass(frozen=True)
class Tool:
  name: str
  description: str
  args_model: type[BaseModel]
  func: Callable[[BaseModel], str]
  
REGISTRY: dict[str, Tool] = {}

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
  
  
# ----------- TOOLS   --------------

## --- calculator ---

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

## --- get_weather ---

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

# --- now   ---

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


# --- read_file   ---

READ_PAGE_CHARS = MAX_TOOL_CHARS - 300

class ReadFileArgs(BaseModel):
  path: Annotated[str, Field(description="相对于工作目录的文件路径，如 tutorials/agent_loop.md")]
  offset: Annotated[int, Field(
    default=0, ge=0,
    description="从第几个字符开始读，默认0。当结果提示被截断时，按提示的 offset 继续读取后续内容。",
  )]
  

def read_file(args: ReadFileArgs) -> str:
  target = (PKG_ROOT / args.path).resolve()
  if not target.is_relative_to(PKG_ROOT):
    return "错误：不允许访问工作目录之外的文件。"
  if not target.is_file():
    return f"错误：文件不存在：{args.path}"
  
  
  text = target.read_text(encoding="utf-8")
  if args.offset >= len(text):
    return f"错误：offset={args.offset} 超出文件长度 {len(text)}"
  
  end = min(args.offset + READ_PAGE_CHARS, len(text))
  header = f"[{args.path} 第 {args.offset}-{end} 字符，共 {len(text)}]\n"
  footer = f"\n... (未完，继续用 offset={end})" if end < len(text) else ""
  return header + text[args.offset:end] + footer
  


register(Tool(
  name="read_file",
  description="读取工作目录内的一个文本文件的全部内容。查看文件、回答关于文件的问题时使用。",
  args_model=ReadFileArgs,
  func=read_file,
))