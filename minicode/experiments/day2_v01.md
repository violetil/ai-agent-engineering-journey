# Day 2：v0.1 验收——读 → 改 → 跑

六个工具（read_file / write_file / edit_file / list_dir / grep / run_shell），系统提示词 v1，模型 deepseek-chat，`--workspace scratch`，`max_steps=20`，`token_budget=60000`（治理基本不触发）。

`scratch/app.py` 8 行、114 字节、CRLF 换行（`Format-Hex` 确认每行以 `0D 0A` 结尾，末行无换行）。

跑了两个会话。第一个会话在任务 B 暴露出 grep 的路径显示 bug，修完后重开会话从头跑，下表是第二个会话。token 来自 REPL 摘要行（按 step index 去重），时间是 `perf_counter`。

## 对照表（第二个会话，同一次 REPL 连续六轮）

| # | 输入 | 步数 | 输入 token | 输出 token | 时间 | 工具序列 | trace |
|---|---|---|---|---|---|---|---|
| A | 把 greet 里的 hell 改成 hello，运行确认 | 4 | 8,259 | 309 | 6.5s | list_dir + read_file（同一步）→ edit_file → run_shell → 总结 | `trace_20261101_135817` |
| B | 哪些地方调用了 print | 2 | 4,814 | 159 | 2.6s | grep → 总结 | `trace_20261101_135835` |
| C | 把 return None 改成 return ""（文件里有两处） | 2 | 5,332 | 281 | 5.1s | read_file → **停下来问用户** | `trace_20261101_135948` |
| C' | 两处都改 | 5 | 16,157 | 352 | 6.6s | edit_file → edit_file → run_shell → read_file → 总结 | `trace_20261101_140034` |
| D | 刚才改的那个文件现在有几行 | 1 | 3,555 | 81 | 1.5s | 无工具，直接作答 | `trace_20261101_140210` |
| E | `/reset` 后：app.py 现在有几行 | 2 | 3,795 | 72 | 2.5s | run_shell（`find /c /v "" & dir`）→ 总结 | `trace_20261101_140250` |
| 合计 | | 16 | 41,912 | 1,254 | | | |

第一个会话的两条：A 跑了 4 步 8,297 in（`trace_20261101_135250`）；B 跑了 3 步 7,414 in（`trace_20261101_135546`），多出来的一步是绕过 grep bug 的 `findstr`。

## 验收项逐条

**先读再改。** 四次 `edit_file` 调用（A 一次、C' 两次，另有第一个会话 A 一次）之前都有同轮或上一轮的 `read_file`。A 里模型把 `list_dir` 和 `read_file` 放在同一次 `tool_calls` 里并行发出。

**old_string 没有行号前缀。** 四次 `edit_file` 的 `old_string` 全部是竖线之后的原文，没有出现过 `     2|`。提示词「读文件的格式」那一段生效，这一讲最担心的问题没有出现。

**唯一性策略。** C' 的两次 `old_string` 分别是 `def greet(name: str):\n  print(f"hello {name}")\n  return None`（3 行）和 `def Hello(name):\n  return None`（2 行）。模型主动把函数签名带进来做锚点，第一次就唯一，没有被拒绝。

**改完验证。** A 和 C' 都跑了 `python app.py`，C' 还额外 `read_file` 读回。退出码都在返回第一行。

**总结格式。** A、C' 的最终回答都按第 6 条写了「改了什么 + 验证结果」，没有复述代码。A 顺带指出了 `def Hello(name)` 命名不一致，没动它。

**CRLF。** 三次编辑之后 `app.py` 仍是 `0D 0A`，第一讲的 `newline` 保留在真实代码文件上成立。

## 发现

### 1. 模型主动规避了「碰壁」测试

任务 C 的设计目的是让 `edit_file` 因 `count > 1` 拒绝，看模型第二次怎么改参数。实际发生的是：模型先 `read_file`，看到两处 `return None`，**没有调用 `edit_file`**，而是停下来问用户改哪一处，并指出 `None → ""` 是接口变更。

这是比预期更好的行为，但意味着 `count > 1` 这条拒绝路径只在烟雾测试里被触发过，没有经过模型。`count == 0`（old_string 写错）同样没有被模型触发过。两条路径对模型的「说明是否看得懂」仍未验证。

### 2. 模型会掩盖工具的 bug

第一个会话里 grep 的输出是 `.:2:   print(...)` 和 `.:1: print('hi')`，路径全显示成了 `.`（`display_path` 传错了对象）。模型的反应是：「grep 返回的路径显示为 `.`，看起来是两个不同文件名被简化显示」，然后用 `run_shell` 跑 `dir /s /b *.py & findstr /s /n /c:"print" *.py` 复核，最终答案是对的。

如果不看 trace 只看答案，这个 bug 不会被发现。模型的补救能力在这里是双刃剑：它让系统更鲁棒，也让工具缺陷更难暴露。**工具的正确性要靠烟雾测试，不能靠端到端结果。**

### 3. run_shell 的编码只覆盖了 Python 子进程

任务 E 模型用 `dir app.py` 看文件信息，返回里出现 `������ E �еľ��� �¼Ӿ�`。`dir` 是 cmd.exe 内建命令，按系统代码页（GBK/cp936）输出，父进程按 UTF-8 解码失败后用 `�` 替换。`PYTHONIOENCODING=utf-8` 只对子进程里的 Python 有效，对 `dir`、`findstr`、`git` 的中文输出都无效。

模型这次没受影响（它只需要 `8` 和 `114` 两个数字），但 pytest 之外的任何带中文的命令输出都会变乱码。修法：按字节捕获，先尝试 UTF-8，失败再按系统编码解码。

### 4. 多轮上下文的收益和代价

D 在同一会话里问「刚才改的文件有几行」，模型没调工具，3,555 in 直接答对——因为 C' 的 `read_file` 结果还在上下文里。`/reset` 后问同一个问题（E），模型必须调工具，3,795 in。

代价是每轮起点越来越高：A 第一步 1,835 in，C' 第一步 2,961 in，一个会话累计 41,912。其中 1,835 是系统提示词 + 6 个工具 schema 的固定开销，每一步都付。第四讲的治理要在这个基础上做。

### 5. 模型会说出工具没告诉它的事

D 的回答里说「第 8 行的 `greet("violet")` 后面没有换行符，所以共 8 行」。这句话是对的（hex 确认末尾没有 `0D 0A`），但 `read_file` 的输出里没有任何信息能区分「末尾有换行」和「末尾没有换行」——`split` 之后 `pop` 掉了那个空串。这是一个恰好正确的推断，不是观察。编码 Agent 的总结里混进这类「未经工具证实的断言」是常态，评测时要区分「答案对」和「论据对」。

### 6. 模型会用 shell 替代专用工具

E 里模型用 `find /c /v "" app.py` 数行数，而不是 `read_file`。更省 token（1,810 对比 read_file 的约 2,000+），但撞上了发现 3 的编码问题。模型对 cmd.exe 的掌握比预期好，`find /c /v ""` 和 `2>nul` 都是正确的 cmd 习语。

## 未覆盖

- 模型触发 `edit_file` 的 `count == 0` 和 `count > 1` 拒绝
- 模型调用 `write_file`
- `run_shell` 超时、长输出的头尾截断
- `list_dir` 的 `(已忽略)` 和 `MAX_ENTRIES` 截断
- 第二讲的 `Ctrl+C` 清理逻辑

## 待修

1. `run_shell` 解码：按字节捕获，UTF-8 失败回退到 `locale.getpreferredencoding(False)`。
2. `edit_file` 不唯一消息里的省略号：只在命中数超过显示上限时出现。
3. `list_dir` 深度之外的目录不显示任何内容，`new/dir/` 下有文件但看不出来。考虑对未展开目录标注文件数。
