# minicode/main.py
import time
import argparse

from minicode import config
from minicode.loop import LoopResult, StepTrace, run_loop
from minicode.prompts import build_system_prompt
from minicode.trace import dump_trace


def print_step(t: StepTrace) -> None:
  if t.tool_name is None:
    return
  print(f"  ▸ {t.tool_name} {t.tool_args}")
  first_line = (t.tool_result or "").split("\n", 1)[0]
  print(f"    {first_line[:120]}")
  
  
def summarize(result: LoopResult, elapsed: float) -> tuple[int, int]:
  per_step = {t.index: (t.prompt_tokens, t.completion_tokens) for t in result.steps}
  total_in = sum(p for p, _ in per_step.values())
  total_out = sum(c for _, c in per_step.values())
  print(f"  [{len(per_step)} 步 · {total_in:,} in / {total_out:,} out · {elapsed:.1f}s · {result.stop_reason}]")
  return total_in, total_out


def repl(max_steps: int) -> None:
  messages: list[dict] = [{"role": "system", "content": build_system_prompt()}]
  session_in = session_out = 0
  print(f"minicode · 工作目录 {config.WORKSPACE}\n/reset 清空对话，/quit 退出\n")
  
  while True:
    try:
      user = input(">> ").strip()
    except (EOFError, KeyboardInterrupt):
      print()
      break
    if not user:
      continue
    if user == "/quit":
      break
    if user == "/reset":
      messages = [{"role": "system", "content": build_system_prompt()}]
      print("  已清空对话")
      continue
    
    messages.append({"role": "user", "content": user})
    started = time.perf_counter()
    try:
      result = run_loop(messages, max_steps=max_steps, token_budget=60000, on_step=print_step)
    except KeyboardInterrupt:
      print("\n  已中断本轮")
      # 中断发生在某次 API 调用或工具执行中途，messages 末尾可能是没有 tool 回应的 assistant(tool_calls)
      while messages and messages[-1]["role"] != "user":
        messages.pop()
      messages.pop()
      continue
    print(f"\n{result.answer}\n")
    i, o = summarize(result, time.perf_counter() - started)
    session_in += i
    session_out += o
    dump_trace(user, result.steps, result.messages, result.stop_reason)
  
  print(f"本次会话共 {session_in:,} in / {session_out:,} out")
  

if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="minicode：终端编码 Agent")
  parser.add_argument("--workspace", "-w", default=".", help="目标仓库，默认当前目录")
  parser.add_argument("--max-steps", type=int, default=20)
  ns = parser.parse_args()
  config.set_workspace(ns.workspace)
  repl(ns.max_steps)