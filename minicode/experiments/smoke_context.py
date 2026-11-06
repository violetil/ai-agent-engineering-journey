# minicode/experiments/smoke_context.py
# 不走模型的上下文治理测试。运行：在 minicode/ 目录下 python -m experiments.smoke_context
from minicode import config
from minicode.context import (
  mark_stale, dedupe_reads, archive_old_tool_results, compact, count_tokens, _read_range,
)

# ---------- 构造器：数据长得和真实 trace 一样 ----------

def call(cid: str, name: str, args: str) -> dict:
  return {"role": "assistant", "content": "", "tool_calls": [
    {"id": cid, "type": "function", "function": {"name": name, "arguments": args}}
  ]}

def tool(cid: str, content: str) -> dict:
  return {"role": "tool", "tool_call_id": cid, "content": content}

def page(path: str, a: int, b: int, total: int) -> str:
  """和 tools/read_file.py 输出一样的格式：页眉 + 行号|内容。"""
  return f"[{path} 第 {a}-{b} 行，共 {total} 行]\n" + "\n".join(f"{i:>6}|line{i}" for i in range(a, b + 1))

def check(label: str, ok: bool, detail: str = "") -> None:
  print(f"[{'ok' if ok else 'FAIL'}] {label}" + (f": {detail}" if detail else ""))


def scenario() -> list[dict]:
  """读全文 → edit → 读尾页 → 读头 60 行（./ 前缀）→ write_file 覆盖 b.py → 读 b.py。下标写在注释里。"""
  return [
    {"role": "system", "content": "s"},                                                            # 0
    {"role": "user", "content": "u"},                                                              # 1
    call("c1", "read_file", '{"path": "a.py"}'),                                                   # 2
    tool("c1", page("a.py", 1, 200, 228)),                                                         # 3
    call("c2", "edit_file", '{"path": "a.py", "old_string": "x", "new_string": "y"}'),             # 4
    tool("c2", "修改成功。变更如下：\n--- a.py\n+++ a.py\n-x\n+y"),                                    # 5
    call("c3", "read_file", '{"path": "a.py", "offset": 218, "limit": 12}'),                       # 6
    tool("c3", page("a.py", 218, 228, 228)),                                                       # 7
    call("c4", "read_file", '{"path": "./a.py", "offset": 1, "limit": 60}'),                       # 8
    tool("c4", page("a.py", 1, 60, 228)),                                                          # 9
    call("c5", "write_file", '{"path": "b.py", "content": "..."}'),                                # 10
    tool("c5", "已覆盖 b.py：原 3 行 -> 新 5 行。"),                                                   # 11
    call("c6", "read_file", '{"path": "b.py"}'),                                                   # 12
    tool("c6", page("b.py", 1, 5, 5)),                                                             # 13
  ]


# ---------- mark_stale ----------
m = scenario()
n = mark_stale(m)
check("stale：edit_file 不再使旧读取过期", m[3]["content"].startswith("[a.py 第 1-200"), m[3]["content"][:30])
check("stale：write_file 之前没有 b.py 的读取 → 0 条", n == 0, f"n={n}")

m = scenario()
m.insert(10, tool("c0", page("b.py", 1, 3, 3)))        # 在 write_file 之前插入一次 b.py 读取 → 新下标 10,11
m.insert(10, call("c0", "read_file", '{"path": "b.py"}'))
n = mark_stale(m)
check("stale：write_file 之前的 b.py 读取被标过期", m[11]["content"].startswith("[内容已过期：b.py"), m[11]["content"][:50])
check("stale：write_file 之后的 b.py 读取保留", m[15]["content"].startswith("[b.py 第 1-5"), m[15]["content"][:30])
check("stale：只改 1 条", n == 1, f"n={n}")
check("stale：再跑一次 0 条", mark_stale(m) == 0)

# ---------- dedupe_reads ----------
m = scenario()
n = dedupe_reads(m)
check("dedupe：更早的 1-200 不被更晚的 1-60 取代", m[3]["content"].startswith("[a.py 第 1-200"), m[3]["content"][:30])
check("dedupe：218-228 之后没有覆盖它的读取 → 保留", m[7]["content"].startswith("[a.py 第 218-228"))
check("dedupe：1-60 是该文件最新读取 → 保留", m[9]["content"].startswith("[a.py 第 1-60"))
check("dedupe：无可改 → 0 条", n == 0, f"n={n}")

m = scenario()
m += [call("c7", "read_file", '{"path": "a.py"}'), tool("c7", page("a.py", 1, 200, 228))]   # 14,15：再次读全文
n = dedupe_reads(m)
check("dedupe：旧的 1-200 与新读取参数相同 → 去重", m[3]["content"].startswith("[与后面"), m[3]["content"][:40])
check("dedupe：旧的 1-60 被新的 1-200 取代", m[9]["content"].startswith("[此次读取（a.py 第 1-60 行）"), m[9]["content"][:50])
check("dedupe：218-228 不在 1-200 内 → 保留", m[7]["content"].startswith("[a.py 第 218-228"))
check("dedupe：最新的 1-200 保留", m[15]["content"].startswith("[a.py 第 1-200"))
check("dedupe：改 2 条", n == 2, f"n={n}")
check("dedupe：再跑一次 0 条", dedupe_reads(m) == 0)
check("dedupe：错误信息没有页眉 → 不参与", _read_range("错误：offset=999 超出文件范围") is None)

# ---------- archive ----------
m = scenario()
n = archive_old_tool_results(m, keep_recent=4)          # 保留下标 10..13；1..9 里的 tool 消息 3,5,7,9 被归档
check("archive：窗口外 read_file 只留页眉", m[3]["content"].startswith("[已归档 read_file] [a.py 第 1-200"), m[3]["content"][:60])
check("archive：窗口外 edit_file 保留全文", m[5]["content"] == "[已归档 edit_file] 修改成功。变更如下：\n--- a.py\n+++ a.py\n-x\n+y")
check("archive：窗口内的不动", m[13]["content"].startswith("[b.py 第 1-5"))
check("archive：条数 4", n == 4, f"n={n}")
m2 = scenario()
m2 += [call("c7", "read_file", '{"path": "a.py"}'), tool("c7", page("a.py", 1, 200, 228))]
dedupe_reads(m2); archive_old_tool_results(m2, keep_recent=4)
check("archive：跳过已改写的条目", m2[3]["content"].startswith("[与后面") and m2[9]["content"].startswith("[此次读取"))

# ---------- compact 的门 ----------
config.GOVERNANCE_ENABLED = True
m = scenario()
m += [call("c7", "read_file", '{"path": "a.py"}'), tool("c7", page("a.py", 1, 200, 228))]
compact(m, budget=10**9)
check("compact：不超预算时 dedupe 不跑", m[3]["content"].startswith("[a.py 第 1-200"), m[3]["content"][:30])
before = count_tokens(m)
compact(m, budget=before - 1)                            # 刚好超一点：dedupe 跑完就够了，不该归档
check("compact：超预算时 dedupe 跑了", m[3]["content"].startswith("[与后面") and m[9]["content"].startswith("[此次读取"))
check("compact：dedupe 够用就不归档", m[7]["content"].startswith("[a.py 第 218-228"), m[7]["content"][:30])
check("compact：压到预算内", count_tokens(m) <= before - 1, f"{count_tokens(m)} <= {before - 1}")

config.GOVERNANCE_ENABLED = False
m = scenario()
m.insert(10, tool("c0", page("b.py", 1, 3, 3))); m.insert(10, call("c0", "read_file", '{"path": "b.py"}'))
compact(m, budget=1)
check("compact：关掉治理时什么都不动", m[11]["content"].startswith("[b.py 第 1-3") and m[3]["content"].startswith("[a.py 第 1-200"))