# agent/executor.py
import json
import asyncio
from dataclasses import dataclass
from pydantic import ValidationError

from .schemas import Plan, PlanStep, Blackboard, StepResult
from .loop import run_loop
from .planner import PlanningError, make_plan
from .config import client, MODEL


EXECUTOR_PROMPT = """你是执行器。只完成当前这一步的目标，不要做计划里的其他步。

规则：
1. 需要外部信息就调用工具；信息足够就给出事实性结论。
2. 不要客套，不要总结「希望对您有帮助」。
3. suggested_tool 只是建议，选更合适的工具也可以。
"""

EXTRACT_PROMPT = """把执行器最终的回答提炼成 JSON，符合下列 schema，不要 markdown：
{schema}

原回答：
{answer}
"""


def extract_result(answer: str) -> StepResult:
  schema = json.dumps(StepResult.model_json_schema(), ensure_ascii=False)
  raw = client.chat.completions.create(
    model=MODEL,
    response_format={"type": "json_object"},
    messages=[{"role": "user", "content": EXTRACT_PROMPT.format(schema=schema, answer=answer)}],
  ).choices[0].message.content
  try:
    return StepResult.model_validate_json(raw)
  except ValidationError:
    return StepResult(status="partial", output=answer or "", note="结构化提取失败，已退回原文")


def execute_step(step: PlanStep, board: Blackboard, max_steps: int = 5) -> StepResult:
  hint = f"建议工具：{step.suggested_tool}" if step.suggested_tool else "无建议工具"
  messages = [
    {"role": "system", "content": EXECUTOR_PROMPT},
    {
      "role": "user", 
      "content": (
        f"当前目标：{step.goal}\n{hint}\n\n"
        f"已知信息：\n{board.context_for(step) or '（无）'}"
      ),
    },
  ]
  loop = run_loop(messages, max_steps=max_steps)
  return extract_result(loop.answer)


def topological_levels(steps: list[PlanStep]) -> list[list[PlanStep]]:
  """同一层互不依赖，可并行。如果某轮找不出 ready，就是环。"""
  done: set[int] = set()
  remaining = {s.id: s for s in steps}
  levels: list[list[PlanStep]] = []
  
  while remaining:
    ready = [s for s in remaining.values() if set(s.depends_on) <= done]
    if not ready:
      raise PlanningError(f"计划存在循环依赖：{list(remaining)}")
    levels.append(ready)
    done |= {s.id for s in ready}
    for s in ready:
      del remaining[s.id]
  return levels


@dataclass
class PlanOutcome:
  ok: bool
  board: Blackboard
  
  
def execute_plan(plan: Plan, board: Blackboard) -> PlanOutcome:
  for level in topological_levels(plan.steps):
    for step in level:
      result = execute_step(step, board)
      if result.status == "failed":
        board.failures[step.id] = result.note or result.output
        return PlanOutcome(ok=False, board=board)
      board.results[step.id] = result.output
  return PlanOutcome(ok=True, board=board)


async def execute_plan_parallel(plan: Plan, board: Blackboard) -> PlanOutcome:
  for level in topological_levels(plan.steps):
    results = await asyncio.gather(
      *(asyncio.to_thread(execute_step, s, board) for s in level),
      return_exceptions=True
    )
    for step, result in zip(level, results):
      if isinstance(result, Exception):
        board.failures[step.id] = f"{type(result).__name__}: {result}"
        return PlanOutcome(ok=False, board=board)
      if result.status == "failed":
        board.failures[step.id] = result.note or result.output
        return PlanOutcome(ok=False, board=board)
      board.results[step.id] = result.output
  return PlanOutcome(ok=True, board=board)


MAX_REPLANS = 2


def summarize(task: str, board: Blackboard) -> str:
  facts = "\n".join(f"- 步骤 {i}：{out}" for i, out in board.results.items())
  misses = "\n".join(f"- 步骤 {i} 失败：{why}" for i, why in board.failures.items())
  reps = client.chat.completions.create(
    model=MODEL,
    messages=[{
      "role": "user",
      "content": (
        f"任务：{task}\n\n已得到的事实：\n{facts or '（无）'}\n\n"
        f"失败：\n{misses or '（无）'}\n\n用几段话直接回答用户，不要提及步骤编号。"
      )
    }]
  )
  return reps.choices[0].message.content


def run(task: str) -> str:  
  plan = make_plan(task)
  print("计划：", plan.model_dump_json(indent=2, ensure_ascii=False))
  board = Blackboard()
  replans = 0
  
  while True:
    outcome = execute_plan(plan, board)
    if outcome.ok or replans >= MAX_REPLANS:
      break
    replans += 1
    print(f"重规划第 {replans} 次")
    plan = make_plan(task, previous=plan, board=board)
    
  return summarize(task, board)