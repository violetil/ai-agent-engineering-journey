# minicode/config.py
import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

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


def set_workspace(path: str | Path) -> Path:
  global WORKSPACE
  p = Path(path).resolve()
  if not p.is_dir():
    raise NotADirectoryError(f"工作目录不存在：{p}")
  WORKSPACE = p
  return p