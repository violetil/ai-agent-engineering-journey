# minicode/config.py
import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from collections.abc import Callable

load_dotenv(Path(__file__).resolve().parent / ".env")


MODEL = "deepseek-chat"

client = OpenAI(base_url="https://api.deepseek.com", api_key=os.getenv("DEEPSEEK_API_KEY"))

PKG_ROOT = Path(__file__).resolve().parent.parent   # minicode/ 项目目录，放 logs 和 traces
LOG_DIR = PKG_ROOT / "logs"
TRACE_DIR = PKG_ROOT / "traces"
LOG_DIR.mkdir(exist_ok=True)
TRACE_DIR.mkdir(exist_ok=True)

# 工具操作的目标仓库，main.py 可用 set_workspace 覆盖
WORKSPACE: Path = Path.cwd().resolve()

# 确认钩子：(命令, 原因) -> 是否放行。默认拒绝一切，非交互环境下不会悄悄执行任何需确认的命令。
ConfirmHook = Callable[[str, str], bool]

def _deny_all(command: str, reason: str) -> bool:
  return False

confirm_hook: ConfirmHook = _deny_all


def set_workspace(path: str | Path) -> Path:
  global WORKSPACE
  p = Path(path).resolve()
  if not p.is_dir():
    raise NotADirectoryError(f"工作目录不存在：{p}")
  WORKSPACE = p
  return p