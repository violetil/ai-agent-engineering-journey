# minicode/tools/read_file.py
from typing import Annotated
from pydantic import BaseModel, Field

from .fs import resolve_path, read_text, display_path
from ..tools import ToolError, Tool, register


DEFAULT_LIMIT = 200


class ReadFileArgs(BaseModel):
  path: Annotated[str, Field(description="相对于工作目录的文件路径，如 src/app.py")]
  offset: Annotated[int, Field(
    default=1, ge=1,
    description="从第几行开始读（从 1 计数）。结果末尾提示未读完时，用提示的 offset 继续。",
  )]
  limit: Annotated[int, Field(
    default=DEFAULT_LIMIT, ge=1, le=1000,
    description=f"最多读多少行，默认 {DEFAULT_LIMIT}。"
  )]
  
  
def read_file(args: ReadFileArgs) -> str:
  target = resolve_path(args.path)
  text, _ = read_text(target)
  lines = text.split("\n")
  if text.endswith("\n"):
    lines.pop()                           # 去掉默认换行符后面的空串
  total = len(lines)
  
  if total == 0:
    return f"[{display_path(target)} 是空文件]"
  if args.offset > total:
    raise ToolError(f"offset={args.offset} 超出文件总行数 {total}。")
  
  start = args.offset - 1                 # 转成 0 基下标
  end = min(start + args.limit, total)
  body = "\n".join(
    f"{n:>6}|{line}" for n, line in enumerate(lines[start:end], start=args.offset)
  )
  header = f"[{display_path(target)} 第 {args.offset}-{end} 行，共 {total} 行]\n"
  footer = f"\n...（未完，继续用 offset={end + 1}）" if end < total else ""
  
  return header + body + footer


register(Tool(
  name="read_file",
  description=(
    "读取工作目录内的一个文本文件的内容，按行分页，每行前面带行号。"
    "修改文件前必须先用它查看目标区域内的精确内容（包括缩进和空行）。"
    "结果末尾出现「未完」时，按提示的 offset 继续读取。"
  ),
  args_model=ReadFileArgs,
  func=read_file
))