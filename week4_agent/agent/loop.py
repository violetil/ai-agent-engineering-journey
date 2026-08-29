# agent/loop.py
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

from .config import client, MODEL
from .trace import StepTrace, logger
from .tools import tools_schema
from .context import compact, truncate
from .dispatch import dispatch

# 类型别名
OnStep = Callable[[StepTrace], None]

NO_PROGRESS_HINT = (
  "你已经用完全相同的参数调用过这个工具两次，结果不会改变。"
  "请换一种方法，或者直接基于现有信息给出结论。"
)
BUDGET_HINT = (
  "已达到工具调用次数上限。请基于目前已获得的信息，"
  "直接给出你的最佳答案，并说明还缺什么信息。"
)

@dataclass
class LoopResult:
  answer: str
  stop_reason: str
  steps: list[StepTrace] = field(default_factory=list)
  messages: list[dict] = field(default_factory=list)
  

def run_loop(
  messages: list[dict],
  *,
  max_steps: int = 10,
  token_budget: int = 6000,
  on_step: OnStep | None = None
) -> LoopResult:
  """通用主循环。会就地修改并最终返回 messages。
  
  调用方负责准备 messages (system + user)，负责决定如何消费 on_step 事件。
  """
  steps: list[StepTrace] = []
  seen: Counter[tuple[str, str]] = Counter()
  
  def emit(t: StepTrace) -> None:
    steps.append(t)
    if on_step is not None:
      on_step(t)
  
  for step in range(1, max_steps + 1):
    compact(messages, budget=token_budget)    # 调 API 之前先治理
    
    t0 = time.perf_counter()
    res = client.chat.completions.create(
      model=MODEL,
      messages=messages,
      tools=tools_schema(),
    )
    latency_ms = int((time.perf_counter() - t0) * 1000)
    
    message = res.choices[0].message
    messages.append(message.model_dump(exclude_none=True))
    usage = res.usage
    
    if not message.tool_calls:
      emit(StepTrace(step, message.content, None, None, None, usage.prompt_tokens, usage.completion_tokens, latency_ms))
      return LoopResult(message.content, "done", steps, messages)
    
    for tc in message.tool_calls:
      key = (tc.function.name, tc.function.arguments)
      seen[key] += 1
      result = NO_PROGRESS_HINT if seen[key] >= 3 else truncate(dispatch(tc))
      messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
      logger.info("step %d %s(%s)", step, tc.function.name, tc.function.arguments)
      emit(StepTrace(step, message.content, tc.function.name, tc.function.arguments, result, usage.prompt_tokens, usage.completion_tokens, latency_ms))
      
  # 步数耗尽，逼一个最终答案
  messages.append({"role": "user", "content": BUDGET_HINT})
  final = client.chat.completions.create(
    model=MODEL,
    messages=messages,
    tools=tools_schema(),
    tool_choice="none",
  )
  answer = final.choices[0].message.content
  messages.append({"role": "assistant", "content": answer})
  return LoopResult(answer, "budget_exhausted", steps, messages)
  