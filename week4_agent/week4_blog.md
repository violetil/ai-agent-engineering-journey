# Agent 主循环只有 30 行，剩下的工程都在它跑起来之后

不用 LangChain、不用任何 Agent 框架，从一个空文件手写了一个 Agent：工具注册表、参数校验、主循环、预算与终止、上下文治理、Planner/Executor、最后挂到上周那个 API 网关上用 SSE 推进度。动手前我以为核心是那个"把控制权交给模型的 while 循环"。循环确实是核心，但它只有 30 行，一天就写完了。剩下三周的时间全花在循环跑起来之后的事上：上下文怎么不爆、钱怎么不白烧、模型不肯停怎么办、拆成多步之后状态放哪。这几件事我都做了对照实验，有三个实验的结果和我动手前的预期相反。这篇文章主要写这三个。

## 一、先看成品

**计划模式下的 SSE 输出**（`POST /agent/run`，复用上周的 JWT 和额度。节选：每个步骤收尾时那帧没有工具调用的 `step` 被省掉了，完整帧序见 [Day 7 记录](./experiments/day7_sse.md)）：

```ps
event: plan
data: {"reasoning": "需要分别获取北京和上海的当前气温，再比较哪个更高。两个查询互相独立，可分别执行。", "steps": [{"id": 1, "goal": "获取北京当前的天气和气温", "depends_on": [], "suggested_tool": "get_weather"}, {"id": 2, "goal": "获取上海当前的天气和气温", "depends_on": [], "suggested_tool": "get_weather"}, {"id": 3, "goal": "比较两地的气温，判断哪个城市更暖和", "depends_on": [1, 2], "suggested_tool": null}]}

event: step
data: {"plan_step": 1, "index": 1, "thought": "", "tool_name": "get_weather", "tool_args": "{\"city\": \"北京\"}", "tool_result": "晴天 25度", "prompt_tokens": 843, "completion_tokens": 38, "latency_ms": 919}

event: step_result
data: {"plan_step": 1, "status": "success", "output": "北京当前天气：晴，气温 25℃。", "note": null}

event: step
data: {"plan_step": 2, "index": 1, "thought": "", "tool_name": "get_weather", "tool_args": "{\"city\": \"上海\"}", "tool_result": "小雨 20度", "prompt_tokens": 843, "completion_tokens": 38, "latency_ms": 569}

event: step_result
data: {"plan_step": 2, "status": "success", "output": "上海当前天气为小雨，气温20度。", "note": null}

event: step_result
data: {"plan_step": 3, "status": "success", "output": "北京 25℃，上海 20℃，北京比上海高 5℃，北京更暖和。", "note": null}

event: done
data: {"answer": "根据当前天气数据，北京的气温是25℃，天气晴朗；上海的气温是20℃，有小雨。北京比上海高出5℃，因此北京更暖和。"}
```

**额度耗尽时**，响应在任何帧之前就以 403 结束，不是 200 空流：

```text
HTTP/1.1 403 Forbidden
content-type: application/json

{"error":{"code":"QUOTA_EXCEEDED","message":"额度不够"}}
```

代码的组织：

```text
week4_agent/
├── agent/
│   ├── config.py      # client、模型名、路径
│   ├── tools.py       # Tool / REGISTRY / tools_schema，四个工具
│   ├── dispatch.py    # 执行工具，永不抛出
│   ├── loop.py        # run_loop：主循环与预算
│   ├── context.py     # 截断、归档、摘要
│   ├── trace.py       # StepTrace、落盘、USAGE 计数
│   ├── schemas.py     # Plan / PlanStep / StepResult / Blackboard
│   ├── planner.py     # make_plan：结构化计划，失败重试一次
│   └── executor.py    # execute_step / execute_plan / 重规划
├── main.py            # CLI 入口，--plan 切换模式
├── experiments/       # 四份实验记录和对比脚本
└── traces/            # 每次运行的 JSON
```

和上周一样，这个结构不是一开始就有的。Day 1 到 Day 3 的代码全在一个 400 行的 `minimal.py` 里，循环、工具、打印、落盘糊在一起。拆包的触发点不是"文件太长"，而是 Day 5 的执行器要复用主循环时，发现 `run_agent(user_input)` 把 `messages` 的构造写死在函数里，执行器塞不进自己的上下文。这次重构只改了两个接口：入参从"用户一句话"改成"完整的 messages"，终端打印改成一个 `on_step` 回调。后面接 SSE 时，循环一行没动，只是换了一个回调。

## 二、循环本身：30 行，三条铁律

去掉所有硬化之后，循环长这样：

```python
# agent/loop.py，去掉预算、治理和 trace 之后的骨架
for step in range(1, max_steps + 1):
  res = client.chat.completions.create(model=MODEL, messages=messages, tools=tools_schema())
  message = res.choices[0].message
  messages.append(message.model_dump(exclude_none=True))   # 先入档

  if not message.tool_calls:                                # 再判终止
    return LoopResult(message.content, "done", steps, messages)

  for tc in message.tool_calls:                             # 全部执行
    result = truncate(dispatch(tc))
    messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
```

和上周网关里那种"一问一答"相比，变化只有一处：驱动循环的从 `input()` 换成了模型的下一个决定。模型返回 `tool_calls` 就继续，不返回就停。

这段代码里有三件事不能错，错了就是一个莫名其妙的 400。`assistant` 消息要在判断终止之前就 append，否则模型下一轮不知道自己上一轮说过什么。`tool_calls` 是列表，要遍历全部，不能只取 `[0]`。每一个 `tool_call.id` 后面都必须紧跟一条 `tool_call_id` 配对的 `tool` 消息，少一条、多一条、顺序乱了，下一次请求都会被拒。

第三条在后面上下文治理那一节会再咬我一次。

**结论与发现**：`messages` 就是 Agent 的全部状态，模型自己没有记忆，每一轮都在重新递交完整卷宗。这件事决定了后面所有的成本问题。

## 三、工具的错误是观察，不是异常

上周网关的原则是"出错就抛，让顶层处理器翻译成 HTTP"。这条原则搬进循环里会毁掉 Agent：模型传错了参数、编了一个不存在的工具名、查了一个数据库里没有的城市，这些都不是故障，是模型下一轮需要知道的信息。一旦 `raise`，循环就死了，模型永远没有机会改。

所以分派函数的形状是**返回字符串，永不抛出**：

```python
# agent/dispatch.py
try:
  args = tool.args_model.model_validate_json(tool_call.function.arguments)
except ValidationError as e:
  brief = "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors())
  return f"参数校验失败：{brief}。请修正参数之后重新调用。"

try:
  return tool.func(args)
except Exception as e:
  logger.exception("工具 %s 执行失败", name)
  return f"工具执行失败：{type(e).__name__}: {e}"
```

错误信息是写给模型看的提示词，不是给人看的日志。计算器工具里我为此做了一张表：`sqrt(16)` 会得到"不支持函数调用，请改写成 16 \*\* 0.5"，`1,000` 会得到"数字不要写千分位分隔符"。每条都告诉模型下一步该怎么改，而不是只说"错了"。

### 一个没有被测试抓到的 bug

主循环里有两段给模型看的提示语，一段用在无进展检测，一段用在步数耗尽。我是这么写的：

```python
NO_PROGRESS_HINT = (
  "你已经用完全相同的参数调用过这个工具两次，结果不会改变。",
  "请换一种方法，或者直接基于现有信息给出结论。"
)
```

括号里两个字符串之间有一个逗号。有逗号，这是一个二元组；没有逗号，Python 会把相邻的字符串字面量拼成一个字符串。创造元组的是逗号，不是括号。

这个元组会被塞进 `tool` 消息的 `content`，下一轮循环开头 `count_tokens` 对它调 `tiktoken.encode`，在一个离案发现场很远的地方抛 `TypeError`。它一直没炸，是因为前三次测试里模型最多只重复了两次同参数调用，差一次就触发。这个 bug 是 code review 看出来的，不是测试跑出来的。如果当时模型再犟一次，我看到的会是 tiktoken 的堆栈，而不是这两行。

**结论与发现**：模型能补救的错误留在循环里，模型无能为力的错误（鉴权、余额、额度）才抛出循环。至于那个元组，教训是任何只在"罕见分支"里用到的常量，都要专门造一次触发。

## 四、上下文：O(n²) 的曲线，我两次都没治对

每一轮循环都要把完整的 `messages` 重新发一遍。第 1 轮发 1 份，第 n 轮发 n 份，总输入是 O(n²)。而 Agent 的上下文膨胀主要来自工具结果：一次文件读取几千 token，模型真正需要的可能就一行。

治理分三级，便宜的先上：截断单条工具结果；把保留窗口之外的旧 `tool` 消息内容替换成占位符（消息本身不删，不然就违反第二节的配对铁律）；再不够，把最老的一段历史交给模型摘要成一条。切点有一条规则：

```python
# agent/context.py
cut = len(messages) - KEEP_RECENT
while cut > 1 and messages[cut].get("role") == "tool":
  cut -= 1          # 切点落在 tool 消息上就往左退，退到它所属的 assistant(tool_calls)
summary = summarize_history(messages[1:cut])
messages[1:cut] = [{"role": "user", "content": f"[前情摘要，供参考]\n{summary}"}]
```

逻辑写对了。实验做了三轮，前两轮都没测到我想测的东西。

### 第一轮：什么都没发生

任务是"读 `tutorials/agent_loop.md` 并总结"。三次运行，`token_budget` 一次 2500、两次 60000。预算 2500 的那次和预算 60000 的其中一次，每步输入 token 完全相同：712、1600、2488，合计 4800，最终 messages 里既没有归档标记也没有摘要。预算差 24 倍而数字一模一样，说明治理一次都没改变任何东西。

原因是算术：任务全程只有 6 条消息，`KEEP_RECENT = 6`，"最近 6 条完整保留"意味着一条都轮不到治理。实验设计和参数不匹配，任务短到没有东西可治。

这一轮还暴露了另一件事：文件 17608 字符，工具截断在 2000 字符，模型看到"已截断"之后想读剩下的部分，但工具没有给它任何拿到剩余内容的手段。它唯一能做的就是原参数重试，于是白烧了一步，拿回一模一样的结果，最后基于文件前 11% 的内容写了一份"核心观点总结"。三次运行的答案全部只覆盖到第 2 节。

修法是给 `read_file` 加分页，截断提示里写清楚下一步：

```python
# agent/tools.py
footer = f"\n... (未完，继续用 offset={end})" if end < len(text) else ""
return header + text[args.offset:end] + footer
```

之后的每一次运行里，模型都沿着 offset 0、1700、3400 一路翻到 17000，没有再重复读过同一页。

### 第二轮：治理是负收益

换成"完整读取全文并逐节总结"，11 页。`max_steps=10`，`token_budget=2500`。每步输入 token：

| step          | 1   | 2    | 3    | 4    | 5    | 6    | 7    | 8    | 9    | 10   |
| ------------- | --- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- |
| prompt_tokens | 776 | 1594 | 2370 | 3229 | 3145 | 3191 | 3269 | 3490 | 3504 | 3493 |

前 3 步线性增长，第 4 步起被摁平在 3200 到 3500。这是我想看到的曲线。

但日志里从第 4 步起每一步都多出一次 HTTP 请求，一共 7 次。那是摘要器。稳态上下文有一个不可压缩的地板：system、工具 schema、前情摘要、再加 `KEEP_RECENT` 那 6 条窗口，用 tiktoken 估算大约五六千 token。而预算 2500 低于地板。于是 `compact` 每一步都判超支、每一步都重新摘要、摘要完还是超支，它在做一个永远达不成的指标。这 7 次摘要调用的 token 没进 trace，按每次约 3000 输入估算，额外烧掉两万左右。循环本身 2.8 万加摘要约 2 万，反而略高于不治理时按前三步斜率外推的 4.5 万。

更糟的是结尾。11 页的任务在第 10 步被 `max_steps` 掐断，收尾调用用 `tool_choice="none"` 禁止工具、要求基于已有信息作答。模型的回答是这样：

```text
<｜DSML｜tool_calls>
<｜DSML｜invoke name="read_file">
<｜DSML｜parameter name="offset" string="false">17000</｜DSML｜parameter>
...
```

`tool_choice="none"` 只约束 API 的解析行为，不约束模型的生成倾向。模型看着上下文里满屏的工具调用先例和一条写着"继续读"的摘要，还是生成了工具调用，API 不再把它解析成结构化的 `tool_calls`，于是 DeepSeek 内部的标记语言以纯文本泄漏进了 `content`。它想请求的 offset 恰好是 17000，下一页。模型完全清醒，是我把它摁住了。

这次运行花了近五万 token，最终答案是一段乱码。修法是收尾调用干脆不传 `tools` 参数，让工具定义从上下文里彻底消失，而不只是禁止解析。

### 第三轮：省了 15%，代价是丢了八节内容

`max_steps=15`，治理组 `token_budget=9000`，对照组 999999。两组都读完了 11 页，都自然结束：

|              | 治理组                      | 对照组                  |
| ------------ | --------------------------- | ----------------------- |
| 循环总输入   | 52,747                      | 62,289                  |
| 循环总输出   | 1,918                       | 3,098                   |
| 摘要调用次数 | 0                           | 0                       |
| 归档条数     | 7                           | 0                       |
| 第 11 步输入 | 4,170                       | 9,027                   |
| 是否完成任务 | 形式上完成，前 8 节细节丢失 | 完成，第 0 到 14 节齐全 |

前 10 步两组几乎重合。第 11 步，治理组的 7 条旧 `tool` 消息被换成 `[已归档] 原结果开头：…`，输入从 8175 掉到 4170。配对完整，全程没有 400。节省约 9500 输入 token。

然后看答案。治理组的最终回答自己写道："文档第 1 到 8 节的内容在读档时被抽离了部分详细输出。"归档只留了每页前 80 个字符的页眉，正文被扔掉了。本该由摘要器把这些事实压成 300 字备忘，但归档已经把 tiktoken 的估算压回预算之下，摘要器的门槛没有跨过，一次都没跑。对照组没有这个问题，从第 0 节写到第 14 节，输出也长了一倍。

**结论与发现**：三件事。第一，预算必须高于上下文的地板，否则治理会在每一步空转，净收益为负。第二，分级治理有一个结构性问题：便宜的那一级如果单独就能压过预算，更贵但保信息的那一级就永远轮不到。第三，截断提示必须给出路，否则模型只能重试或放弃。还有一条关于实验本身的：两个预算跑出一模一样的 token 数，不是治理没用，是实验没测到东西。

## 五、Planner/Executor：我以为它至少会赢在三城任务上

纯循环是贪心的，每一步只看当前上下文。十步的任务第三步走偏，后面七步全在错误的分支上努力。Planner/Executor 的思路是先让模型输出一份结构化计划，再由执行器逐步执行，每一步用一份全新的 `messages`，步骤之间只通过一块"黑板"传递提炼过的结论。

计划必须是 API 级的结构化输出加 pydantic 校验，不能靠提示词说"请输出 JSON"。`response_format={"type": "json_object"}` 只保证括号能对上，不保证字段是我要的，结构保证来自 `Plan.model_validate_json`。校验失败带着错误重试一次，两次都不行就抛 `PlanningError`，没有计划就没有后续，不该回喂。

执行器的每一步就是第二节那个循环，只是上下文更干净：

```python
# agent/executor.py
messages = [
  {"role": "system", "content": EXECUTOR_PROMPT},
  {"role": "user", "content": f"当前目标：{step.goal}\n\n已知信息：\n{board.context_for(step) or '（无）'}"},
]
loop = run_loop(messages, max_steps=max_steps)
return extract_result(loop.answer)
```

`extract_result` 把循环的最终回答再过一遍模型，收成 `{status, output, note}`。不这么做，黑板里存的就是"好的，我已经查到北京今天晴天 25 度了，希望这对您有帮助"，下游步骤得从客套话里抠事实。

### 对比实验

同一组五个任务，两种模式各跑一次。planner 的 token 含规划、各步循环和总结，不含 `extract_result`（它没接进计数器，所以 planner 实际比表上更贵）：

| 任务                  | 模式    | 成功 | 总输入 | 总输出 | 墙上时间 |
| --------------------- | ------- | ---- | ------ | ------ | -------- |
| 现在几点              | 纯循环  | 是   | 1558   | 46     | 1.4s     |
| 现在几点              | planner | 是   | 2433   | 129    | 6.1s     |
| 北京和上海哪个更暖和  | 纯循环  | 是   | 1618   | 127    | 1.7s     |
| 北京和上海哪个更暖和  | planner | 是   | 5094   | 352    | 8.3s     |
| 三城天气对比          | 纯循环  | 是   | 1666   | 258    | 1.8s     |
| 三城天气对比          | planner | 是   | 6870   | 457    | 9.8s     |
| 读第 0 节并一句话概括 | 纯循环  | 是   | 2350   | 103    | 1.8s     |
| 读第 0 节并一句话概括 | planner | 是   | 3302   | 278    | 4.9s     |
| 火星和北京            | 纯循环  | 是   | 1617   | 222    | 2.4s     |
| 火星和北京            | planner | 是   | 6070   | 1051   | 13.8s    |

五个任务 planner 全输，三城任务输得最多：输入 6870 对 1666，时间 9.8 秒对 1.8 秒。

我原本预期三城任务 planner 能赢，因为三路查询互不依赖。结果没赢的原因在 trace 里一眼能看到：纯循环在第一步就一次返回了三个 `tool_calls`，一次模型调用查完三个城市，两步结束。planner 把同一件事拆成规划一次、三个各自两轮的小循环、三次结果提取、一次总结，九次模型调用。隔离买到了，但这个任务根本不需要隔离。

规划质量本身是好的。三份计划里查询步的 `depends_on` 都是空，对比步依赖前面全部，没有被串成一条链。"现在几点"被规划成 1 步，没有注水。

### 黑板里的一个设计错误

火星任务本来是用来测重规划的：查火星会失败，重规划应绕开它，并且不重做已经查过的北京。跑完的输出里有一处不对，终端打印的黑板上，`黑板[1]` 是北京 25 度，`黑板[2]` 是一段火星观测体系的长文。

对照代码才看明白。第一份计划把火星排在步骤 1，失败后 `execute_plan` 立即返回，同层的北京被取消，黑板上没有北京。重规划生成的第二份计划又从 id 1 开始编号。两份计划共用同一块黑板，键是整数 id，于是 `results[1]` 被写成北京，而第一份计划留下的 `failures[1]` 是火星，没有删。同一个键同时是成功和失败，而且说的不是同一件事，最后的总结把两边都读了进去。答案还能读通，是因为总结模型自己把矛盾圆过去了。

修法是每次重规划之后把旧黑板清空，让新计划的 id 从空字典写起；上一份计划的事实按内容存进一个不带 id 的列表，执行器和总结都读它。

顺便，这个样本没有测到它本来要测的东西。北京在第一份计划里从未被执行，第二份计划才第一次查，"不重做已完成步骤"这条没有被覆盖。要测它，失败步必须排在成功步后面。

**结论与发现**：planner 的收益不是"规划得更好"，而是上下文隔离、可审批、可展示进度。这三条在我这五个任务里一条都用不上，所以它全输。什么时候该用它，判据是能不能说清要买这三条里的哪一条。说不清，就是不需要。至于黑板，任何跨计划复用的状态都不能用计划内部的编号做键。

## 六、挂到网关：上周留的两个坑在这里补上

上周博客第五节留了两个流式的坑：扣费写在生成器末尾，客户端一断开就永远执行不到；额度校验藏在异步生成器里，等它执行时 200 已经发出去了，报不了 403。

这次 `POST /agent/run` 的路由层把两件事都做在 `return StreamingResponse(...)` 之前：

```python
# ai_service/app/main.py
@app.post("/agent/run")
async def _agent_run(body: AgentRunRequest, user: CurrentUser):
  prepare_agent_run(user)        # 校验 + 扣费，在这里抛的异常还能变成 403
  return StreamingResponse(agent_run_stream(body), media_type="text/event-stream", ...)
```

扣费在开始时扣。上游的费用在第一个 token 产生时就已经发生了，用户中途取消不该免单。

### 同步的循环不能直接放进 async 函数

`run_loop` 内部是阻塞的 `client.chat.completions.create`。在 FastAPI 的 async 函数里直接调用它，事件循环会卡住几十秒，期间所有用户的所有请求都停摆。上周那个"每次新建 AsyncClient"的坑是静默吃掉异步收益，这个坑是服务整个假死。

解法是把循环丢进线程，事件用队列传回：

```python
# ai_service/app/services/agent_service.py
loop = asyncio.get_running_loop()
queue: asyncio.Queue[dict | None] = asyncio.Queue()

def emit(event: dict) -> None:
  loop.call_soon_threadsafe(queue.put_nowait, event)   # 工作线程 → 事件循环

async def producer() -> None:
  try:
    answer = await asyncio.to_thread(_run_sync, body, emit)
    emit({"event": "done", "data": {"answer": answer}})
  except Exception as e:
    emit({"event": "error", "data": {"type": type(e).__name__, "message": str(e)}})
  finally:
    emit(None)                                          # 哨兵

task = asyncio.create_task(producer())
try:
  while (item := await queue.get()) is not None:
    yield _frame(item["event"], item["data"])
finally:
  task.cancel()
```

`asyncio.Queue` 不是线程安全的，工作线程不能直接往里 `put`，`call_soon_threadsafe` 是从外部线程唤醒事件循环的唯一正规途径。哨兵放在 `finally` 里，不管线程是正常结束还是抛异常都要发，否则消费者会在 `queue.get()` 上永远等下去。到了生成器里，错误只能用 `event: error` 帧报，因为 200 已经出去了。

第一节那段 SSE 就是这套东西的输出。`on_step` 回调在第一节设计时说"塞一个写队列的函数进来就是 SSE"，这里兑现了，循环本身一行没改。

**结论与发现**：流式接口把"响应"从一个瞬间拉长成一段时间，所有校验和状态变更都要在第一个字节之前做完。这条上周就写过了，这周多了一条：任何同步阻塞的调用都不能直接出现在 async 函数里，哪怕它"只阻塞几秒"。

## 七、这个版本还不能上生产

**客户端断开后，工作线程停不下来。** `task.cancel()` 只取消了生产者任务，正在线程里跑的 `run_loop` 没有办法从外面杀掉，它会继续调 API 直到自然结束。用户点"停止"，上游费用照付。修法是给 `run_loop` 加一个 `threading.Event`，每轮开头检查。

**token 计数器是进程级全局变量。** `USAGE` 是 `trace.py` 里的一个字典，两个请求同时跑会串数。目前 SSE 没有把它推给客户端，所以不影响输出，但要按请求统计成本就得改成每次运行独立的累加器。

**归档会丢事实。** 第四节第三轮的结论。归档之后如果砍掉了还没写进摘要的工具结果，应该强制再走一遍摘要，或者让归档保留的不是页眉而是该页的要点。

**每个实验只跑了一次。** Agent 有随机性。第四节第一轮里，同一个输入三次运行，一次模型读一遍就作答，两次犟着重读。单次运行的数字说明机制，说明不了分布。正经的做法是每个用例跑多次取成功率，这是下一阶段要补的评测基础设施。

**并行执行器写了，没测。** `execute_plan_parallel` 用 `asyncio.gather` 加 `asyncio.to_thread` 按拓扑层并发，但第五节那张表全是串行数据。三城任务理论上并行能把三路查询的墙上时间压成一路，这个数字我还没有。

**重规划的"不重做"没有被覆盖。** 第五节说过。需要一个失败步排在成功步后面的用例。

**week4 是靠改 `sys.path` 接进网关的。** `agent_bridge.py` 把 `week4_agent` 插进搜索路径，`load_dotenv()` 读的是启动 uvicorn 时的工作目录，日志写到 `week4_agent/logs/` 而不是网关目录。独立成项目时要换成正规的包安装。

## 写在最后

这三周真正带走的几条：

- **`messages` 就是全部状态**。每一轮都在重新递交完整卷宗，这决定了成本是 O(n²)，也决定了任何删消息的操作都要先想配对。
- **工具的错误回喂给模型，不要抛**。错误信息是写给模型看的提示词。
- **截断必须给出路**。只说"已截断"，模型的选项只剩重试和放弃。
- **预算要高于地板**。低于地板的治理每一步都在空转，净收益为负。
- **便宜的治理手段会挡住贵的**。归档一旦压过预算，摘要就永远轮不到。
- **`tool_choice="none"` 拦不住一个想干活的模型**。要让工具消失，不只是禁止解析。
- **planner 买的是隔离、审批和进度，不是更好的规划**。说不清要买哪一条就别用。
- **跨计划的状态不能用计划内编号做键**。
- **同步调用不能出现在 async 函数里**。丢进线程，用队列和 `call_soon_threadsafe` 传回来。
- **两个参数跑出一样的数字，先怀疑实验没测到东西**。

回头看，那个 30 行的循环在整个项目里占的时间不到十分之一。剩下九成是在处理它跑起来之后的事：上下文、预算、终止、状态、并发。和上周的结论一样，所谓 Agent 工程化，大部分还是普通的工程化，只是对象从 HTTP 请求换成了一个会自己做决定的循环。

不过这个 Agent 现在只会查天气和读一个目录下的文件。下一步是把工具集换成真实的：读写文件、精确编辑、在仓库里搜索、执行命令，让它能进一个陌生的代码仓库修一个真实的 bug。循环不用换，第一节那次重构就是为这件事做的。

---

## 延伸阅读

- 讲义：[Agent 主循环](./tutorials/agent_loop.md) / [Planner 与 Executor](./tutorials/planner_executor.md)
- 实验记录：[Day 4 上下文治理](./experiments/day4_context.md) / [Day 5 纯循环 vs Planner](./experiments/day5_planner.md) / [Day 7 SSE](./experiments/day7_sse.md)
- 文中引用的 trace：[9/2 负收益与 DSML 泄漏](./traces/trace_20260902_144114.json) / [9/8 治理组](./traces/trace_20260908_200950.json) / [9/8 对照组](./traces/trace_20260908_201119.json)
- 完整代码：[agent](./agent/) / [网关接入](../week3_python_abilities/ai_service/app/services/agent_service.py)
- 上周：[手写一个 LLM API 网关](../week3_python_abilities/week3_blog.md)
