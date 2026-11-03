# minicode/tools/run_shell.py
import os
import locale
import subprocess
from datetime import datetime
from typing import Annotated
from pydantic import BaseModel, Field

from .registry import Tool, ToolError, register
from .. import config
from ..policy import classify

DEFAULT_TIMEOUT = 60
MAX_TIMEOUT = 300
HEAD_CHARS = 3000
TAIL_CHARS = 3000


class RunShellArgs(BaseModel):
  command: Annotated[str, Field(min_length=1, description="要执行的命令行，在工作目录下执行")]
  timeout: Annotated[int, Field(default=DEFAULT_TIMEOUT, ge=1, le=MAX_TIMEOUT, description=f"超时秒数，默认 {DEFAULT_TIMEOUT}")]
  
  
def _clip(text: str) -> str:
  """太长保留头和尾，中间省略。报错和测试结论通常在尾部。"""
  if len(text) <= HEAD_CHARS + TAIL_CHARS:
    return text
  omitted = len(text) - HEAD_CHARS - TAIL_CHARS
  return text[:HEAD_CHARS] + f"\n... (中间省略 {omitted} 字符) ...\n" + text[-TAIL_CHARS:]


def _decode(raw: bytes) -> str:
  for enc in ("utf-8", locale.getpreferredencoding(False)):
    try:
      return raw.decode(enc)
    except UnicodeDecodeError:
      continue
  return raw.decode("utf-8", errors="replace")
  
  
def _audit(command: str, decision: str, reason: str) -> None:
  with (config.LOG_DIR / "commands.log").open("a", encoding="utf-8") as f:
    f.write(f"{datetime.now().isoformat(timespec="seconds")}\t{decision}\t{reason}\t{command}\n")

  
def run_shell(args: RunShellArgs) -> str:
  verdict = classify(args.command)
  if verdict.level == "deny":
    _audit(args.command, "deny", verdict.reason)
    raise ToolError(f"命令被拒绝执行 {verdict.reason}。请换一种不具破环性的做法，或把这一步交给用户手动完成。")
  if verdict.level == "confirm":
    if not config.confirm_hook(args.command, verdict.reason):
      _audit(args.command, "rejected", verdict.reason)
      raise ToolError("用户拒绝了这条命令。不要原样重试；如果任务必须依赖它，请说明原因并询问用户。")
  _audit(args.command, verdict.level, verdict.reason)
  
  env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
  try:
    proc = subprocess.run(
      args.command,
      shell=True,
      cwd=config.WORKSPACE,
      capture_output=True,
      timeout=args.timeout,
      env=env,
      stdin=subprocess.DEVNULL,
    )
  except subprocess.TimeoutExpired:
    raise ToolError(
      f"命令超过 {args.timeout} 秒未结束，已被终止。"
      "如果是长时间运行的服务或会等待输入的命令，不要用本工具运行；"
      f"如果确实需要更久，可以把 timeout 调大 (上限 {MAX_TIMEOUT} 秒)"
    )
    
  parts = [f"[exit code {proc.returncode}]"]
  if proc.stdout.strip():
    parts.append("stdout:\n" + _clip(_decode(proc.stdout).rstrip()))
  if proc.stderr.strip():
    parts.append("stderr:\n" + _clip(_decode(proc.stderr).rstrip()))
  if len(parts) == 1:
    parts.append("(没有输出)")
  return "\n".join(parts)


register(Tool(
  name="run_shell",
  description=(
    f"在工作目录下执行一条 shell 命令 ({'cmd.exe' if os.name == 'nt' else 'sh'})，"
    "返回退出码、stdout 和 stderr。用来运行测试、脚本、查看 git 状态。"
    "命令必须是非交互的，不能等待用户输入。输出过长时保留开头和结尾。"
  ),
  args_model=RunShellArgs,
  func=run_shell,
))