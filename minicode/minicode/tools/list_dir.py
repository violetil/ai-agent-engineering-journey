# minicode/tools/list_dir.py
from typing import Annotated
from pydantic import BaseModel, Field
from pathlib import Path

from .fs import resolve_path, display_path
from ..tools import Tool, ToolError, register

IGNORED_DIRS = {
  ".git", ".hg", ".svn", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
  "node_modules", ".venv", "venv", "env", "dist", "build", ".idea", ".vscode",
}
MAX_ENTRIES = 200


class ListDirArgs(BaseModel):
  path: Annotated[str, Field(default=".", description="相对于工作目录的目录路径，默认工作目录本身")]
  depth: Annotated[int, Field(default=2, ge=1, le=4, description="向下展开几层，默认 2")]
  
  
def _walk(root: Path, depth: int, prefix: str, out: list[str]) -> bool:
  """返回 True 表示因为条数上限没列完。depth 用尽不算这种截断。"""
  if depth == 0:
    return False
  try:
    entries = sorted(root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
  except PermissionError:
    if len(out) >= MAX_ENTRIES:
      return True
    out.append(f"{prefix}[无权限读取]")
    return False
  
  for p in entries:
    if len(out) >= MAX_ENTRIES:
      return True
    if p.is_dir():
      if p.name in IGNORED_DIRS:
        out.append(f"{prefix}{p.name}/  （已忽略）")
        continue
      out.append(f"{prefix}{p.name}/")
      if _walk(p, depth - 1, prefix + "  ", out):
        return True
    else:
      out.append(f"{prefix}{p.name}")
  return False
  
  
def list_dir(args: ListDirArgs) -> str:
  target = resolve_path(args.path)
  if not target.is_dir():
    raise ToolError(f"{args.path!r} 不是目录。")
  out: list[str] = []
  truncated = _walk(target, args.depth, "", out)
  if not out:
    return f"[{display_path(target) or '.'} 是空目录]"
  header = f"[{display_path(target) or '.'}，深度 {args.depth}]\n"
  footer = (
    f"\n...（超过 {MAX_ENTRIES} 条，已截断。请指定子目录或减小 depth）"
    if truncated else ""
  )
  return header + "\n".join(out) + footer


register(Tool(
  name="list_dir",
  description=(
    "列出工作目录内某个目录的文件和子目录，目录名以 / 结尾，缩进表示层级。"
    "自动跳过 .git、__pycache__、node_modules 等噪音目录。"
    "进入陌生仓库时先用它了解结构，再用 grep 定位。"
  ),
  args_model=ListDirArgs,
  func=list_dir,
))