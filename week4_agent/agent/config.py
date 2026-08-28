# agent/config.py
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MODEL = "deepseek-chat"

client = OpenAI(
  base_url="https://api.deepseek.com",
  api_key=os.getenv("DEEPSEEK_API_KEY"),
)

PKG_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PKG_ROOT / "logs"
TRACE_DIR = PKG_ROOT / "traces"
LOG_DIR.mkdir(exist_ok=True)
TRACE_DIR.mkdir(exist_ok=True)