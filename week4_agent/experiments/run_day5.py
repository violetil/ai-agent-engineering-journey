import time
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import importlib.util
spec = importlib.util.spec_from_file_location(
  "week4_main",
  Path(__file__).resolve().parent.parent / "main.py"
)
week4_main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(week4_main)

from agent.planner import make_plan, PlanningError
from agent.schemas import Plan, PlanStep
from agent.executor import topological_levels, run
from agent.trace import USAGE, note

# ===== 1 =====
# OUT = Path(__file__).resolve().parent / "plans"
# OUT.mkdir(exist_ok=True)
# 
# TASKS = [
#   "01_now",
#   "02_two_cities",
#   "03_three_cities",
# ]
# 
# PROMPTS = {
#   "01_now": "现在几点",
#   "02_two_cities": "北京和上海哪个更暖和",
#   "03_three_cities": "查北京、上海、深圳的天气并对比谁更暖和",
# }
# 
# for name, prompt in PROMPTS.items():
#   plan = make_plan(prompt)
#   text = plan.model_dump_json(indent=2, ensure_ascii=False)
#   (OUT / f"{name}.json").write_text(text, encoding="utf-8")
#   print("\n====", name, "步数", len(plan.steps))
#   print(text)


# ===== 4 =====
# bad = Plan(
#   reasoning="测试",
#   steps=[
#     PlanStep(id=1, goal="A", depends_on=[2]),
#     PlanStep(id=2, goal="B", depends_on=[1]),
#   ],
# )
# try:
#   topological_levels(bad.steps)
#   print("失败：循环依赖没有被发现")
# except PlanningError as e:
#   print("通过：", e)


# ===== 2, 3, 5 =====
FULL = [
  ("现在几点", "答案里有今天的日期和时间"),
  ("北京和上海哪个更暖和", "北京 25 度，上海 20 度，北京更暖"),
  ("查北京、上海、深圳的天气并对比谁更暖和", "25 / 20 / 18，北京最暖，深圳最冷"),
  ("读 tutorials/agent_loop.md 的第 0 节，用一句话概括", "提到循环、终止条件、messages 这三句里的至少两句"),
  ("查火星和北京的天气并对比", "北京 25 度；火星是未知天气；重规划后不再次查询北京"),
]

for prompt, expect in FULL:
  print("\n########## PLANNER", prompt)
  USAGE["in"] = USAGE["out"] = USAGE["calls"] = 0
  t0 = time.perf_counter()
  answer = run(prompt, on_event=lambda e: print(e["event"], json.dumps(e["data"], ensure_ascii=False)))
  elapsed = time.perf_counter() - t0
  print(answer)
  print(f"METRIC planner in={USAGE['in']} out={USAGE['out']} calls={USAGE['calls']} wall={elapsed:.1f}s")
  print("期望:", expect)
  
  print("\n########## LOOP", prompt)
  t0 = time.perf_counter()
  answer = week4_main.run_agent(prompt)
  elapsed = time.perf_counter() - t0
  print(answer)
  print(f"METRIC loop wall={elapsed:.1f}s （in/out 用上面 print_summary 那一行）")