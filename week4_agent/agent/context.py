# agent/context.py
import tiktoken

from .config import client, MODEL
from .trace import logger

encoding = tiktoken.get_encoding("cl100k_base")

MAX_TOOL_CHARS = 2000
KEEP_RECENT = 6
ARCHIVE_MARK = "[已归档]"


# ----------  第 0 级：单条截断   ----------

def truncate(text: str, limit: int = MAX_TOOL_CHARS) -> str:
  if len(text) <= limit:
    return text
  return text[:limit] + f"\n...（已截断，原文共 {len(text)} 字符）"


# ----------  计数    ----------

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


# ----------  第 1 级：归档旧工具结果   -----------

def archive_old_tool_results(messages: list[dict]) -> int:
  """把保留窗口之外的的 tool 消息内容替换成占位符。返回处理条数。"""
  changed = 0
  cutoff = max(len(messages) - KEEP_RECENT, 0)
  for msg in messages[:cutoff]:
    content = msg.get("content", "")
    if msg.get("role") == "tool" and not content.startswith(ARCHIVE_MARK):
      first_line = content.split("\n")[0][:80]
      msg["content"] = f"{ARCHIVE_MARK} 原结果开头：{first_line}"
      changed += 1
  return changed


# ----------  第 2 级：摘要压缩   ----------

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

def compact(messages: list[dict], budget: int = 6000) -> None:
  """把 messages 压到预算之内。就地修改，无返回值。"""
  if count_tokens(messages) <= budget:
    return
  
  archive_old_tool_results(messages)
  if count_tokens(messages) <= budget:
    return
  
  # 找切点：把 messages[1:cut] 摘要掉，保留 system(0) 和 messages[cut:]
  cut = len(messages) - KEEP_RECENT
  # 配对安全：切点落在 tool 消息上，往左退到它所属的 assistant(tool_calls),
  # 保证这个原子组完整地留在保留区
  while cut > 1 and messages[cut].get("role") == "tool":
    cut -= 1
  if cut <= 1:
    return
  
  summary = summarize_history(messages[1:cut])
  # 切片赋值
  messages[1:cut] = [{"role": "user", "content": f"[前情摘要，供参考]\n{summary}"}]
  
  if count_tokens(messages) > budget:
    logger.warning("预算 %d 低于上下文地板（当前 %d），治理无法达标", budget, count_tokens(messages))