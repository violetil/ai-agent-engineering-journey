# minicode/policy.py
import re
import shlex
from typing import Literal
from dataclasses import dataclass
from . import config

Level = Literal["allow", "confirm", "deny"]

@dataclass(frozen=True)
class Verdict:
  level: Level
  reason: str
  
  
_PATH_LIKE = re.compile(r"(?:[a-zA-Z]:[\\/]|\.\.[\\/]|~[\\/]|^/)[^\s\"']*")

# 直接放行：只读、无副作用、或副作用限于工作目录内的常规开发命令
ALLOW_PREFIXES: tuple[tuple[str, ...], ...] = (
  ("python",), ("python3",), ("py",), ("pytest",), ("pip", "list"), ("pip", "show"),
  ("git", "status"), ("git", "diff"), ("git", "log"), ("git", "show"), ("git", "branch"),
  ("dir",), ("type",), ("findstr",), ("find",), ("echo",), ("where",), ("tree",),
  ("ls",), ("cat",), ("grep",), ("head",), ("tail",), ("wc",), ("pwd",),
)

# 直接拒绝：不可逆、影响范围超出仓库、或典型的注入载荷
DENY_PATTERNS: tuple[tuple[str, str], ...] = (
  (r"\bformat\s+[a-z]:", "格式化磁盘"),
  (r"\b(rd|rmdir)\s+/s\b.*\b[a-z]:\\?(\s|$)", "递归删除整个盘符"),
  (r"\brm\s+-[a-z]*r[a-z]*\s+(/|~|\$HOME)(\s|$)", "递归删除根目录或家家目录"),
  (r"\b(rd|rmdir)\s+(/[sq]\s+)*(\.|\.\\|%cd%)(\s|$)", "递归删除当前目录"),
  (r"\bdel\s+(/[a-z]\s+)*\*(\.\*)?(\s|$)", "删除当前目录下的所有文件"),
  (r"\bgit\s+(checkout\s+--\s+\.|restore\s+\.)(\s|$)", "丢弃全部未提交改动"),
  (r"\bgit\s+push\b.*(--force|-f\b)", "强制推送会覆盖远端历史"),
  (r"\bgit\s+(reset\s+--hard|clean\s+-[a-z]*f)", "丢弃未提交的改动，不可恢复"),
  (r"\b(shutdown|reboot|logoff)\b", "关机或注销"),
  (r"\breg\s+(add|delete)\b", "修改注册表"),
  (r"\b(curl|wget|iwr|Invoke-WebRequest)\b.*\|\s*(sh|bash|python|powershell|iex)\b", "下载并执行远程脚本"),
  (r"\bpowershell\b.*-(e|enc|encodedcommand)\b", "编码的 powershell 命令，无法审查内容"),
)

_SEP_TOKENS = {"&&", "||", "&", "|", ";"}


def _escapes_workspace(command: str) -> bool:
  root = config.WORKSPACE
  for m in _PATH_LIKE.finditer(command):
    try:
      p = (root / m.group(0)).resolve()
    except (OSError, ValueError):
      return True
    if not p.is_relative_to(root):
      return True
  return False


def _segments(command: str) -> list[list[str]] | None:
  """把一条复合命令切成若干段，每段是小写 token 列表。引号内的分隔符不切。
  引号不配对等无法解析的情况返回 None，由调用方归入 Confirm。"""
  lexer = shlex.shlex(command, posix=False, punctuation_chars=True)
  lexer.whitespace_split = True
  try:
    tokens = list(lexer)
  except ValueError:
    return None
  segments: list[list[str]] = [[]]
  for tok in tokens:
    if tok in _SEP_TOKENS:
      if segments[-1]:
        segments.append([])
      continue
    segments[-1].append(tok.strip('"').lower())
  return [s for s in segments if s]


def classify(command: str) -> Verdict:
  """返回最严格的一段的判定。deny > confirm > allow。"""
  lowered = command.lower()
  for pattern, reason in DENY_PATTERNS:
    if re.search(pattern, lowered):
      return Verdict("deny", reason)
    
  if _escapes_workspace(command):
    return Verdict("confirm", "命令引用了工作目录之外的路径")
  
  segs = _segments(command)
  if segs is None:
    return Verdict("confirm", "命令无法解析 (引号不配对？)")
    
  worst: Verdict = Verdict("allow", "常规开发命令")
  for tokens in segs:
    if any(tuple(tokens[: len(p)]) == p for p in ALLOW_PREFIXES):
      continue
    worst = Verdict("confirm", f"{' '.join(tokens)!r} 不在免确认列表中")
  return worst
  