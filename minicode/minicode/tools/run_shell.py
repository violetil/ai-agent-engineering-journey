# minicode/tools/run_shell.py
import os
import subprocess
from typing import Annotated
from pydantic import BaseModel, Field

from .registry import Tool, ToolError, register
from .. import config

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
  
  
def run_shell(args: RunShellArgs) -> str:
  env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
  try:
    proc = subprocess.run(
      args.command,
      shell=True,
      cwd=config.WORKSPACE,
      capture_output=True,
      encoding="utf-8",
      errors="replace",
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
    parts.append("stdout:\n" + _clip(proc.stdout.rstrip()))
  if proc.stderr.strip():
    parts.append("stderr:\n" + _clip(proc.stderr.rstrip()))
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