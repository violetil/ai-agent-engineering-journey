# minicode/tools/grep.py
import re
from pathlib import Path
from fnmatch import fnmatch
from typing import Annotated
from pydantic import BaseModel, Field

from .fs import resolve_path, display_path, read_text
from .list_dir import IGNORED_DIRS
from .registry import Tool, ToolError, register

MAX_MATCHES = 50
MAX_LINE_CHARS = 200


class GrepArgs(BaseModel):
  pattern: Annotated[str, Field(min_length=1, description="Python 正则表达式。搜字面量时注意转译 . ( ) [ ] 等字符。")]
  path: Annotated[str, Field(default=".", description="搜索范围：目录或单个文件，默认整个工作目录")]
  glob: Annotated[str | None, Field(default=None, description="只搜索匹配此通配符的文件名，如 *.py、test_*.py")]
  ignore_case: Annotated[bool, Field(default=False, description="忽略大小写")]
  
  
def _iter_files(root: Path):
  """递归产出 root 下的文件，跳过噪音目录。root 本身是文件时只产出它。"""
  if root.is_file():
    yield root
    return
  for p in root.rglob("*"):
    if not p.is_file():
      continue
    if any(part in IGNORED_DIRS for part in p.relative_to(root).parts[:-1]):
      continue
    yield p
  
  
def grep(args: GrepArgs) -> str:
  try:
    rx = re.compile(args.pattern, re.IGNORECASE if args.ignore_case else 0)
  except re.error as e:
    raise ToolError(f"正则表达式无效：{e}。如果你想搜字面量，请把特殊字符转义，例如 foo\\(\\)。")
  
  target = resolve_path(args.path)
  if not target.exists():
    raise ToolError(f"路径不存在：{args.path!r}")
  
  hits: list[str] = []
  files_scanned = 0
  truncated = False
  
  for f in _iter_files(target):
    if args.glob and not fnmatch(f.name, args.glob):
      continue
    try:
      text, _ = read_text(f)
    except ToolError:
      continue                  # 二进制，超大文件：跳过不报错
    files_scanned += 1
    for n, line in enumerate(text.split("\n"), start=1):
      if not rx.search(line):
        continue
      if len(hits) >= MAX_MATCHES:
        truncated = True
        break
      shown = line if len(line) <= MAX_LINE_CHARS else line[:MAX_LINE_CHARS] + "..."
      hits.append(f"{display_path(f)}:{n}: {shown}")
    if truncated:
      break
    
  if not hits:
    return f"在 {files_scanned} 个文件中没有找到匹配 {args.pattern!r} 的内容。"
  footer = f"\n... (已达 {MAX_MATCHES} 条上限，结果不完整。请缩小 path 或加 glob)" if truncated else ""
  return f"[{len(hits)} 处匹配，扫描了 {files_scanned} 个文件]\n" + "\n".join(hits) + footer


register(Tool(
  name="grep",
  description=(
    "在工作目录内按正则表达式搜索文件内容，返回「路径:行号: 该行内容」。"
    "用来定位函数定义、调用点、字符串出现位置。自动跳过二进制文件和噪音目录。"
    "找到位置后用 read_file 带 offset 查看上下文。"
  ),
  args_model=GrepArgs,
  func=grep,
))