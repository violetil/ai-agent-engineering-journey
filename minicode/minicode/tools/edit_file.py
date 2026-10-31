# minicode/tools/edit_file.py
from pydantic import BaseModel, Field
from typing import Annotated
import difflib

from .fs import read_text, write_text, resolve_path, display_path
from ..tools import Tool, ToolError, register


CONTEXT_LINES = 2


class EditFileArgs(BaseModel):
  path: Annotated[str, Field(description="相对于工作目录的文件路径")]
  old_string: Annotated[str, Field(
    min_length=1,
    description="要被替换的原文，必须与文件内容逐字符一致（含缩进、空行），且在文件中只出现一次。",
  )]
  new_string: Annotated[str, Field(description="替换后的新文本，可以为空字符串表示删除。")]
  
  
def _show_occurrences(text: str, needle: str, limit: int = 3) -> str:
  """告诉模型重复出现在哪几行，便于它补充上下文。"""
  hits: list[int] = []
  pos = text.find(needle)
  while pos != -1 and len(hits) < limit:
    hits.append(text.count("\n", 0, pos) + 1)
    pos = text.find(needle, pos + 1)
  return "、".join(f"第 {n} 行" for n in hits)
  
  
def edit_file(args: EditFileArgs) -> str:
  if args.old_string == args.new_string:
    raise ToolError("old_string 和 new_string 相同，没有可做的修改。")
  
  target = resolve_path(args.path)
  text, newline = read_text(target)
  
  count = text.count(args.old_string)
  if count == 0:
    raise ToolError(
      f"在 {display_path(target)} 中没有找到 old_string。"
      "请先用 read_file 查看该区域的精确内容，注意缩进、空格和空行必须完全一致。"
    )
  if count > 1:
    raise ToolError(
      f"old_string 在 {display_path(target)} 中出现了 {count} 次（{_show_occurrences(text, args.old_string)}），"
      "无法确定要改哪一处。请在 old_string 前后多带几行独特的上下文，使其唯一。"
    )
    
  new_text = text.replace(args.old_string, args.new_string, 1)
  write_text(target, new_text, newline)
  
  diff = difflib.unified_diff(
    text.split("\n"), new_text.split("\n"),
    fromfile=display_path(target), tofile=display_path(target),
    n=CONTEXT_LINES, lineterm="",
  )
  return "修改成功。变更如下：\n" + "\n".join(diff)


register(Tool(
  name="edit_file",
  description=(
    "对已有文件做一处精确替换：把 old_string 替换为 new_string。"
    "old_string 必须逐字符匹配文件中唯一的一段文本，匹配不到或匹配多处都会拒绝执行并说明原因。"
    "修改前先用 read_file 确认原文。一次只改一处；多处修改请多次调用。"
    "返回 unified diff 以便确认改动。"
  ),
  args_model=EditFileArgs,
  func=edit_file,
))
  