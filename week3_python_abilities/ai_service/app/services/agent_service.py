# ai_service/app/services/agent_service.py
import json
import asyncio
import logging
from dataclasses import asdict
from collections.abc import AsyncIterator

from week3_python_abilities.ai_service.app.agent_bridge import run_loop, run_planned, StepTrace
from app.schemas.auth import UserRecord
from app.schemas.agent import AgentRunRequest
from app.services.quota_service import ensure_daily_quota
from app.core.errors import QuotaExceededError
from app.repositories.user_repo import update_user


logger = logging.getLogger(__file__)

AGENT_SYSTEM_PROMPT = "你是一个可以调用工具的助手"


# ---------- 路由层调用：校验 + 扣费，必须在第一个字节之前 ----------

def prepare_agent_run(user: UserRecord) -> None:
  ensure_daily_quota(user)
  if user.daily_quota <= 0:
    raise QuotaExceededError("额度不够")
  user.daily_quota -= 1
  update_user(email=user.email, user=user)
  
  
# ---------- 在工作线程里跑的同步函数 ----------

def _run_sync(body: AgentRunRequest, emit) -> str:
  if body.mode == "plan":
    return run_planned(body.task, on_event=emit)
  
  def relay(t: StepTrace) -> None:
    emit({"event": "step", "data": asdict(t)})
    
  messages = [
    {"role": "system", "content": AGENT_SYSTEM_PROMPT},
    {"role": "user", "content": body.task},
  ]
  result = run_loop(messages, max_steps=body.max_steps, on_step=relay)
  return result.answer


# ---------- SSE 生成器 ----------

def _frame(event: str, data: dict) -> str:
  return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def agent_run_stream(body: AgentRunRequest) -> AsyncIterator[str]:
  loop = asyncio.get_running_loop()
  queue: asyncio.Queue[dict | None] = asyncio.Queue()
  
  def emit(event: dict) -> None:
    loop.call_soon_threadsafe(queue.put_nowait, event)
    
  async def producer() -> None:
    try:
      answer = await asyncio.to_thread(_run_sync, body, emit)
      emit({"event": "done", "data": {"answer": answer}})
    except Exception as e:
      logger.exception("agent run 失败")
      emit({"event": "error", "data": {"type": type(e).__name__, "message": str(e)}})
    finally:
      emit(None)
      
  task = asyncio.create_task(producer())
  try:
    while (item := await queue.get()) is not None:
      yield _frame(item["event"], item["data"])
  finally:
    task.cancel()         # TODO: 工作线程依旧运行，修法给 run_loop 加一个 cancel_event: threading.Event；
                          # TODO: USAGE 现在是全局字典，两个用户同时跑会混在一起，目前不往外推 USAGE，以后要改成独立累加器