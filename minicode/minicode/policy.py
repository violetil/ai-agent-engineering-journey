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
  (r"\bgit\s+push\b.*(--force|-f\b)", "强制推送会覆盖远端历史"),
  (r"\bgit\s+(reset\s+--hard|clean\s+-[a-z]*f)", "丢弃未提交的改动，不可恢复"),
  (r"\b(shutdown|reboot|logoff)\b", "关机或注销"),
  (r"\breg\s+(add|delete)\b", "修改注册表"),
  (r"\b(curl|wget|iwr|Invoke-WebRequest)\b.*\|\s*(sh|bash|python|powershell|iex)\b", "下载并执行远程脚本"),
  (r"\bpowershell\b.*-(e|enc|encodedcommand)\b", "编码的 powershell 命令，无法审查内容"),
)


# 命令分隔符：&& || & | ; 。把一条复合命令拆成多段，每段单独判
_SEPARATORS = re.compile(r"\s*(?:&&|\|\||[&|;])\s*")


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


def _spilt_segments(command: str) -> list[str]:
  return [s for s in _SEPARATORS.split(command) if s.strip()]


def _first_tokens(segment: str) -> tuple[str, ...]:
  try:
    tokens = shlex.split(segment, posix=False)
  except ValueError:
    return ()
  return tuple(t.strip('"').lower() for t in tokens[:2])


def classify(command: str) -> Verdict:
  """返回最严格的一段的判定。deny > confirm > allow。"""
  lowered = command.lower()
  for pattern, reason in DENY_PATTERNS:
    if re.search(pattern, lowered):
      return Verdict("deny", reason)
    
  if _escapes_workspace(command):
    return Verdict("confirm", "命令引用了工作目录之外的路径")
    
  worst: Verdict = Verdict("allow", "常规开发命令")
  for seg in _spilt_segments(command):
    tokens = _first_tokens(seg)
    if not tokens:
      return Verdict("confirm", f"无法解析命令片段：{seg!r}")
    if any(tokens[: len(p)] == p for p in ALLOW_PREFIXES):
      continue
    worst = Verdict("confirm", f"{seg.strip()!r} 不在免确认列表中")
  return worst
  