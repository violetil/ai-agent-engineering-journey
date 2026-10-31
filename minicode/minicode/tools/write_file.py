# minicode/tools/write_file.py
from typing import Annotated
from pydantic import BaseModel, Field

from .fs import resolve_path, display_path, read_text, write_text
from ..tools import Tool, ToolError, register


class WriteFileArgs(BaseModel):
  path: Annotated[str, Field(description="相对于工作目录的文件路径，父目录不存在时会自动创建")]
  content: Annotated[str, Field(description="文件的完整内容")]
  
  
def write_file(args: WriteFileArgs) -> str:
  target = resolve_path(args.path)
  new_lines = args.content.count("\n") + (0 if args.content.endswith("\n") or not args.content else 1)
  
  if target.exists():
    old_text, newline = read_text(target)
    old_lines = old_text.count("\n") + (0 if old_text.endswith("\n") or not old_text else 1)
    write_text(target, args.content, newline)
    return f"已覆盖 {display_path(target)}：原 {old_lines} 行 -> 新 {new_lines} 行。"
  
  write_text(target, args.content)
  return f"已新建 {display_path(target)}：共 {new_lines} 行。"


register(Tool(
  name="write_file",
  description=(
    "新建文件，或用完整内容覆盖一个已有文件。"
    "修改已有文件的局部请用 edit_file，不要用本工具重写整个文件。"
    "覆盖时会在返回里说明原文件行数，便于发现误覆盖。"
  ),
  args_model=WriteFileArgs,
  func=write_file,
))