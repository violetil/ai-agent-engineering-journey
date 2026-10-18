# agent/planner.py
import json

from pydantic import ValidationError

from .schemas import Plan, Blackboard
from .config import client, MODEL
from .tools import REGISTRY
from .trace import USAGE, note


class PlanningError(Exception):
  """计划结构连续两次非法，或图里有环。模型换个说法也救不了，向上抛。"""


PLANNER_PROMPT = """你是规划器，只输出计划，不调用工具。

可用工具（仅供参考，步骤里写 goal 不写具体调用）：
{tools}

必须输出符合下列 JSON Schema 的对象，不要 Markdown 围栏：
{schema}

规则：
1. steps 最多 8 步，id 从 1 连续编号。
2. goal 必须可独立执行，禁止写「继续上一步」。
3. depends_on 只引用已经出现的 id，不要自环。
4. suggested_tool 只能是上面列出的工具名，或 null。
5. 三步以内能做完的任务，就只规划必要的步，不要注水。
"""


def tools_desc() -> str:
  return "\n".join(f"- {t.name}: {t.description}" for t in REGISTRY.values())


def make_plan(
  task: str,
  *,
  previous: Plan | None = None,
  board: Blackboard | None = None
) -> Plan:
  extra = ""
  if previous is not None and board is not None:
    done = "\n".join(f"- 步骤 {i} 已完成: {out}" for i, out in board.results.items())
    failed = "\n".join(f"- 步骤 {i} 失败: {why}" for i, why in board.failures.items())
    extra = (
      f"\n上一份计划：{previous.model_dump_json(ensure_ascii=False)}"
      f"\n已完成（不要重做）：\n{done or '（无）'}"
      f"\n已失败：\n{failed or '（无）'}"
      "\n请只规划剩余工作。"
    )
  
  schema = json.dumps(Plan.model_json_schema(), ensure_ascii=False)
  error_hint = ""
  
  for attempt in range(2):
    resp = client.chat.completions.create(
      model=MODEL,
      response_format={"type": "json_object"},
      messages=[
        {"role": "system", "content": PLANNER_PROMPT.format(tools=tools_desc(), schema=schema)},
        {"role": "user", "content": task + extra + error_hint},
      ],
    )
    note(resp)
    
    raw = resp.choices[0].message.content
    try:
      return Plan.model_validate_json(raw)
    except ValidationError as e:
      error_hint = f"\n上一次输出不符合 schema：{e.errors()[:3]}。请严格按照 schema 重新输出。"
      
  raise PlanningError("规划器连续两次输出非法结构")