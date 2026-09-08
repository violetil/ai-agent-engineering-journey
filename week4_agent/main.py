# week4_agent/main.py
import time

from agent.loop import LoopResult, StepTrace, run_loop
from agent.trace import dump_trace

SYSTEM_PROMPT = "你是一个可以调用工具的助手"


def print_step(t: StepTrace) -> None:
  """on_step 回调，把每一步打印到终端。"""
  if t.tool_name is None:
    print(f"┌ step {t.index}  done ({t.latency_ms / 1000:.1f}s)")
    return
  print(f"┌ step {t.index}  ({t.prompt_tokens:,} in /{t.completion_tokens:,} out)")
  if t.thought:
    print(f"| think {t.thought[:100]}")
  print(f"| tool  {t.tool_name} {t.tool_args}")
  print(f"└ obs   {(t.tool_result or '')[:100]}")


def print_summary(result: LoopResult, elapsed: float) -> None:
  # 同一步的多个工具调用共享同一次的 API 的 usage，先按 index 去重再求和
  per_step = {t.index: (t.prompt_tokens, t.completion_tokens) for t in result.steps}
  total_in = sum(p for p, _ in per_step.values())
  total_out = sum(c for _, c in per_step.values())
  print(f"\n总计 {len(per_step)} 步，{total_in:,} in / {total_out:,} out，"
        f"{elapsed:.1f}s，结束原因：{result.stop_reason}")


def run_agent(user_input: str) -> str:
  messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": user_input},
  ]
  started = time.perf_counter()
  result = run_loop(messages, on_step=print_step, max_steps=15, token_budget=999999)
  print_summary(result, time.perf_counter() - started)
  path = dump_trace(user_input, result.steps, result.messages, result.stop_reason)
  print(f"trace 已写入 {path}")
  return result.answer


if __name__ == "__main__":
  print(run_agent(input(">> ")))