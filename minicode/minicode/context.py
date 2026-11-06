# minicode/context.py
import re
import json
import tiktoken
from pathlib import PurePosixPath
from collections.abc import Callable

from . import config
from .config import client, MODEL
from .trace import logger
from .tools import tools_schema

encoding = tiktoken.get_encoding("cl100k_base")

MAX_TOOL_CHARS = 12000
KEEP_RECENT = 8
STALE_NOTE = "[内容已过期：{path} 在此之后被 {tool} 修改过，需要时请重新 read_file]"
DUP_NOTE = "[与后面一次相同调用的结果重复，已省略。参数：{args}]"
SUPERSEDED_NOTE = "[此次读取（{path} 第 {a}-{b} 行）已被后面一次覆盖该范围的读取取代，已省略]"
_MUTATORS = {"write_file"}
_RANGE_RE = re.compile(r"第 (\d+)-(\d+) 行")
_REWRITTEN = ("[内容已过期", "[与后面", "[此次读取", "[已归档", "[前情摘要")   # 治理改写过的内容的前缀


# ----------  工具调用索引   ----------

def _index_tool_calls(messages: list[dict]) -> dict[str, tuple[str, str]]:
  """tool_call_id -> (工具名，参数 JSON 字符串)"""
  return {
    tc["id"]: (tc["function"]["name"], tc["function"]["arguments"])
    for m in messages
    if m.get("role") == "assistant" and m.get("tool_calls")
    for tc in m["tool_calls"]
  }
  
  
def _arg_path(args_json: str) -> str | None:
  """从参数里取出规范化的 path，取不到返回 None。"""
  try:
    p = json.loads(args_json).get("path")
  except (json.JSONDecodeError, AttributeError):
    return None
  if not isinstance(p, str):
    return None
  return PurePosixPath(p.replace("\\", "/")).as_posix().removeprefix("./")


def _read_range(content: str) -> tuple[int, int] | None:
  """从 read_file 结果的页眉 `[path 第 a-b 行，共 n 行]` 取出 (a, b)。错误信息没有页眉，返回 None。"""
  m = _RANGE_RE.search(content.split("\n", 1)[0])
  return (int(m.group(1)), int(m.group(2))) if m else None


# ----------  过期标记（正确性，每步跑）   ----------

def mark_stale(messages: list[dict]) -> int:
  """被 write_file 整体覆盖过的文件，覆盖之前的所有读取标为过期。就地改写，返回改写条数。"""
  calls = _index_tool_calls(messages)
  
  last_mutation: dict[str, tuple[int, str]] = {}      # path -> (消息下标，工具名)
  for i, m in enumerate(messages):
    if m.get("role") != "tool":
      continue
    name, args = calls.get(m["tool_call_id"], (None, ""))
    if name in _MUTATORS and m["content"].startswith(("修改成功", "已新建", "已覆盖")):
      path = _arg_path(args)
      if path:
        last_mutation[path] = (i, name)
  if not last_mutation:
    return 0
  
  changed = 0
  for i, m in enumerate(messages):
    if m.get("role") != "tool":
      continue
    name, args = calls.get(m["tool_call_id"], (None, ""))
    if name != "read_file" or m["content"].startswith(_REWRITTEN):
      continue
    path = _arg_path(args)
    mut = last_mutation.get(path) if path else None
    if mut and mut[0] > i:
      m["content"] = STALE_NOTE.format(path=path, tool=mut[1])
      changed += 1
  return changed


# ----------  去重与取代（省钱，只在超预算时跑）   ----------

def dedupe_reads(messages: list[dict]) -> int:
  """相同调用只留最新一次；read_file 若被更晚、范围覆盖它的读取取代，也省略。就地改写，返回改写条数。"""
  calls = _index_tool_calls(messages)
  changed = 0
  seen_latest: set[tuple[str, str]] = set()                 # 已见过的 (工具名，参数)
  newest_ranges: dict[str, list[tuple[int, int]]] = {}      # path -> 更晚出现的读取范围
  
  for i in range(len(messages) - 1, -1, -1):
    m = messages[i]
    if m.get("role") != "tool":
      continue
    name, args = calls.get(m["tool_call_id"], (None, ""))
    if name is None:
      continue
    
    key = (name, args)
    if key in seen_latest:
      if not m["content"].startswith(_REWRITTEN):
        m["content"] = DUP_NOTE.format(args=args[:120])
        changed += 1
      continue
    seen_latest.add(key)
    
    if name != "read_file" or m["content"].startswith(_REWRITTEN):
      continue
    path = _arg_path(args)
    rng = _read_range(m["content"])
    if not path or rng is None:
      continue
    a, b = rng
    if any(na <= a and nb >= b for na, nb in newest_ranges.get(path, [])):
      m["content"] = SUPERSEDED_NOTE.format(path=path, a=a, b=b)
      changed += 1
      continue
    newest_ranges.setdefault(path, []).append(rng)
  return changed


# ----------  单条截断   ----------

def truncate(text: str, limit: int = MAX_TOOL_CHARS) -> str:
  if len(text) <= limit:
    return text
  return text[:limit] + f"\n...（已截断，原文共 {len(text)} 字符）"


# ----------  计数    ----------

_schema_tokens: int | None = None

def count_tokens(messages: list[dict]) -> int:
  """估算整个 messages 的 token 数。
  
  cl100k 和 DeepSeek 的分词器不完全一致，只是‘量级正确’
  """
  total = 0
  for msg in messages:
    total += len(encoding.encode(msg.get("content", "")))
    for tc in msg.get("tool_calls", []):
      total += len(encoding.encode(tc["function"]["name"]))
      total += len(encoding.encode(tc["function"]["arguments"]))
    total += 4    # 每条消息的结构开销
  return total

def context_size(messages: list[dict]) -> int:
  """这次请求实际会发给模型的 token 估算 = messages + 工具 schema。
  
  工具 schema 每次请求都随 tools= 参数发送，算在 prompt_tokens 里，
  但不在 messages 里；只数 messages 会系统性低估 1,200-1,500。"""
  global _schema_tokens
  if _schema_tokens is None:
    _schema_tokens = len(encoding.encode(json.dumps(tools_schema(), ensure_ascii=False)))
  return count_tokens(messages) + _schema_tokens


# ----------  归档旧工具结果   -----------

def _keep_head(text: str, n: int = 80) -> str:
  return text[:n]

def _keep_shell(text: str) -> str:
  lines = text.rstrip().split("\n")
  head = lines[0]                               # [exit code N]
  tail = lines[-4:] if len(lines) > 5 else lines[1:]
  return "\n".join([head, "..."] + tail)

def _keep_all(text: str) -> str:
  return text

def _keep_grep(text: str) -> str:
  return text.split("\n", 1)[0]                 # [N 处匹配，扫描了 M 个文件]

ARCHIVE_POLICY: dict[str, Callable[[str], str]] = {
  "read_file": _keep_head,        # 页眉：路径和行范围。
  "list_dir": _keep_head,
  "grep": _keep_grep,
  "run_shell": _keep_shell,       # 退出码 + 最后几行：测试结论在这里
  "edit_file": _keep_all,         # diff 是"我改了什么"的唯一记录，保留
  "write_file": _keep_all,        # 一行，本来就短
}

def archive_old_tool_results(messages: list[dict], keep_recent: int) -> int:
  """把保留窗口之外的的 tool 消息内容替换成占位符。返回处理条数。"""
  calls = _index_tool_calls(messages)
  cutoff = max(len(messages) - keep_recent, 0)
  changed = 0
  for m in messages[1:cutoff]:
    if m.get("role") != "tool" or m["content"].startswith(_REWRITTEN):
      continue
    name, _ = calls.get(m["tool_call_id"], (None, ""))
    keep = ARCHIVE_POLICY.get(name, _keep_head)
    m["content"] = f"[已归档 {name}] " + keep(m["content"])
    changed += 1
  return changed


# ----------  摘要压缩   ----------

_SUMMARY_PROMPT = """你是 agent 的记忆压缩器。下面是一段任务执行历史，\
请压缩成不超过 300 字的摘要，必须保留：
1. 用户的原始任务和关键约束
2. 每个工具调用得到的事实型结论（数字、日期、结果原文的关键部分）
3. 已经排除的方向和失败原因
不要客套话，不要 Markdown，只输出纯文本。

执行历史：
{transcript}"""


def _render(messages: list[dict]) -> str:
  """把 messages 渲染成给摘要器看的纯文本。"""
  lines = []
  for m in messages:
    role = m.get("role")
    if role == "assistant" and m.get("tool_calls"):
      calls = "，".join(
        f'{tc["function"]["name"]}({tc["function"]["arguments"]})'
        for tc in m["tool_calls"]
      )
      lines.append(f"assistant 调用工具：{calls}")
    elif m.get("content"):
      lines.append(f"{role}: {m['content']}")
  return "\n".join(lines)
  
  
def summarize_history(messages: list[dict]) -> str:
  resp = client.chat.completions.create(
    model=MODEL,
    messages=[{"role": "user", "content": _SUMMARY_PROMPT.format(transcript=_render(messages))}]
  )
  return resp.choices[0].message.content


# ----------  总入口    -----------

def compact(messages: list[dict], budget: int = 32000) -> None:
  """把 messages 压到预算之内。就地修改，无返回值。
  
  分两层：
  - 正确性层（mark_stale）每步跑：被整体覆盖的文件，旧读取必须拿掉，否则模型会拿错内容。
  - 省钱层（dedupe_reads -> archive -> summarize）只在超预算时跑：每一次改写历史都会让改写点之后的前缀缓存失效一次，不超预算时任何改写都是亏的。
  """
  if not config.GOVERNANCE_ENABLED:
    return
  
  n = mark_stale(messages)
  if n:
    logger.info("上下文：标记过期 %d 条", n)
    
  if context_size(messages) <= budget:
    return
  
  n = dedupe_reads(messages)
  if n:
    logger.info("上下文：去重/取代 %d 条", n)
  if context_size(messages) <= budget:
    return
  
  n = archive_old_tool_results(messages, KEEP_RECENT)
  if n:
    logger.info("上下文：归档 %d 条", n)
  if context_size(messages) <= budget:
    return
  
  cut = len(messages) - KEEP_RECENT
  while cut > 1 and messages[cut].get("role") == "tool":
    cut -= 1
  if cut <= 1:
    return
  
  summary = summarize_history(messages[1:cut])
  messages[1:cut] = [{"role": "user", "content": f"[前情摘要，供参考]\n{summary}"}]
  logger.info("上下文：摘要压缩，剩余 %d 消息", len(messages))
  
  if context_size(messages) > budget:
    logger.warning("预算 %d 低于上下文地板（当前 %d），治理无法达标", budget, context_size(messages))