# minicode/tools/fs.py
from pathlib import Path
from .registry import ToolError
from .. import config


MAX_FILE_BYTES = 2 * 1024 * 1024    # 超过 2MB 的文件不整读


def resolve_path(rel: str) -> Path:
  """把模型给的路径解析到工作目录内的绝对路径，越界则拒绝。"""
  root = config.WORKSPACE
  target = (root / rel).resolve()
  if not target.is_relative_to(root):
    raise ToolError(
      f"路径 {rel!r} 解析到工作目录 {root} 之外，不允许访问。"
      "请使用相对于工作目录的路径。"
    )
  return target


def display_path(p: Path) -> str:
  """给模型看的路径：相对于工作目录，正斜杠。"""
  return p.relative_to(config.WORKSPACE).as_posix()


def read_text(p: Path) -> tuple[str, str]:
  """返回（统一成 \\n 的文本，原文件的换行符）。
  
  写回时要用原换行符，否则 Windows 上的 LF 文件会被悄悄改成 CRLF，
  git diff 里会显示整个文件都变了。
  """
  if not p.is_file():
    raise ToolError(f"文件不存在：{display_path(p)}。如需新建请用 write_file。")
  if p.stat().st_size > MAX_FILE_BYTES:
    raise ToolError(f"文件 {display_path(p)} 超过 {MAX_FILE_BYTES // 1024 // 1024}MB，不支持读取。")
  raw = p.read_bytes()
  try:
    text = raw.decode("utf-8")
  except UnicodeDecodeError:
    raise ToolError(f"文件 {display_path(p)} 不是 UTF-8 文本（可能是二进制文件），无法读取。")
  newline = "\r\n" if "\r\n" in text else "\n"
  return text.replace("\r\n", "\n"), newline


def write_text(p: Path, text: str, newline: str = "\n") -> None:
  p.parent.mkdir(parents=True, exist_ok=True)
  p.write_text(text, encoding="utf-8", newline=newline)