# agent/trace.py
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

import logging
import json

from .config import LOG_DIR, TRACE_DIR


@dataclass
class StepTrace:
  index: int
  thought: str | None
  tool_name: str | None
  tool_args: str | None
  tool_result: str | None
  prompt_tokens: int
  completion_tokens: int
  latency_ms: int
  

_file_handler = logging.FileHandler(LOG_DIR / "agent.log", encoding="utf-8")
_file_handler.setLevel(logging.INFO)
_console_handler = logging.StreamHandler()
_console_handler.setLevel(logging.WARNING)

logging.basicConfig(
  level=logging.INFO,
  format="%(asctime)s %(levelname)-8s | %(message)s",
  handlers=[_file_handler, _console_handler]
)

logger = logging.getLogger("agent")

def dump_trace(user_input: str, traces: list[StepTrace], messages: list[dict], stop_reason: str) -> Path:
  path = TRACE_DIR / f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
  path.write_text(
    json.dumps(
      {
        "input": user_input,
        "stop_reason": stop_reason,
        "steps": [asdict(t) for t in traces],
        "messages": messages,
      },
      ensure_ascii=False,
      indent=2,
    ),
    encoding="utf-8",
  )
  return path