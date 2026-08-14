# Week 4 - Agent 工程化

本周目标只有一句：**能从空文件手写一个 agent 主循环，并说清每一行为什么必须在那里。**

框架（LangChain / LlamaIndex / Agno 之类）本周一律不用。它们把循环藏起来了，而这周要学的恰好就是那个循环。

---

## 讲义

| 讲义 | 内容 |
|------|------|
| [`tutorials/agent_loop.md`](./tutorials/agent_loop.md) | messages 协议、最小循环、五道硬化、可观测性 |
| [`tutorials/planner_executor.md`](./tutorials/planner_executor.md) | 三种编排模式、结构化计划、黑板、并行、重规划、**什么时候不该用** |

先把第一篇吃透再看第二篇。planner/executor 的执行器内部跑的就是主循环，顺序颠倒会学得很别扭。

---

## 六天路线

每天的产出都要能跑，且都要留下一次真实运行的输出。

### Day 1 - 最小主循环

**做**：`agent/minimal.py`，一个工具（`get_weather`），三十行以内。

**验收**：

- "北京和上海哪个更暖和" → 观察到模型一次返回两个 `tool_calls`，循环转了两轮
- "你好" → 零工具调用直接返回
- 故意只回填 `tool_calls[0]`，亲眼看一次 400 报错，理解铁律二

**这一关的意义**：把"控制权交给模型的 while 循环"这件事变成肌肉记忆。

### Day 2 - 工具注册表与参数校验

**做**：`agent/tools.py`（`Tool` + `REGISTRY` + `tools_schema`）、`agent/dispatch.py`。加两个工具：`calculator`、`now`。

**验收**：

- 加第三个工具时只改一处代码
- "现在几点？三小时后是几点？" → 连续两次工具调用
- 传非法参数 → `dispatch` 返回错误文本而**不抛异常**，模型自己改对重试
- 问"火星的天气" → 循环没崩，模型说明情况

**这一关的意义**：错误回喂。这是 agent 和普通服务在错误处理上最根本的分歧。

### Day 3 - 预算、终止与 trace

**做**：`agent/loop.py` 整合五道硬化，`agent/trace.py` 记录每步。

**验收**：

- `max_steps=3` 撞上限时，能用 `tool_choice="none"` 逼出一个基于已有信息的答案
- 无进展检测生效（同参数第三次调用被拦下并提示换策略）
- trace 打印出每步的 token 和耗时，落盘成 JSON
- **算一遍输入 token 随步数的增长曲线，确认 O(n²)**

**这一关的意义**：从"能跑"到"能调"。没有 trace 的 agent 是不可调试的。

### Day 4 - 上下文治理

**做**：加 `read_file` 工具读一个长文件，看上下文爆炸，然后压回去。把 week1 的 `day6_chat_summarizer/token_manager.py` 和 `summarizer.py` 搬过来接上。

**验收**：

- 工具结果截断时明确告知模型"已截断"
- 旧 `tool` 消息的 content 被替换而**不是删除**（删了就违反配对铁律）
- 摘要的切割边界不会劈开 `assistant(tool_calls)` + `tool(...)` 这一组
- 同一个任务，治理前后的总 token 对比

### Day 5 - Planner 与 Executor

**做**：`agent/schemas.py`（`Plan` / `PlanStep` / `StepResult`）、`agent/planner.py`、`agent/executor.py`。串行版本先跑通。

**验收**：

- 计划是 API 级 JSON + pydantic 校验，非法结构能重试一次再抛
- 每个步骤用全新的 `messages`（上下文隔离）
- 黑板里存的是提炼后的 `output`，不是客套话
- 手工造一个循环依赖的计划，确认被检测出来而不是死循环

### Day 6 - 并行、重规划与对比实验

**做**：拓扑分层 + `asyncio.gather` 并发；重规划（限 2 次）。然后做**对比实验**。

**验收**：同一组任务（建议 5 个，含 1 步 / 3 步独立 / 5 步有依赖 / 必然失败四类），分别用纯循环和 planner/executor 跑，记四个指标：

| 任务 | 模式 | 成功 | 步数 | 总 token | 墙上时间 |
|------|------|------|------|----------|----------|
| ... | 纯循环 | | | | |
| ... | planner | | | | |

这张表就是 week4 博客的核心证据。大概率的结论是短任务纯循环胜、可并行的长任务 planner 胜 —— **但你要用自己的数字说这句话**。

### 收尾项目（Day 6 之后，可选但强烈建议）

把 agent 挂进 week3 的 `ai_service`：

- 新增 `POST /agent/run`，复用现成的 `CurrentUser` 鉴权和额度限制
- 用 SSE 把每一步的 trace 实时推给客户端（`event: step` / `event: plan` / `event: done`）
- 注意上周踩的那两个坑：**所有前置校验必须在创建 `StreamingResponse` 之前做完**，扣费别放在生成器末尾

这个项目把 week3 和 week4 缝在一起，也是博客最好的收尾素材。

---

## 目录规划

```text
week4_agent/
├── README.md
├── tutorials/
│   ├── agent_loop.md
│   └── planner_executor.md
├── agent/
│   ├── minimal.py        # Day 1：留着别删，它是最好的对照组
│   ├── tools.py          # Tool / REGISTRY / tools_schema
│   ├── dispatch.py       # 执行工具，永不抛出
│   ├── loop.py           # 主循环
│   ├── context.py        # 截断、丢弃、摘要
│   ├── trace.py          # StepTrace 与打印/落盘
│   ├── schemas.py        # Plan / PlanStep / StepResult
│   ├── planner.py
│   └── executor.py
├── experiments/          # 每天的真实运行记录，博客要用
└── traces/               # trace JSON 落盘
```

`minimal.py` 不要在重构时删掉。写博客时，"三十行的版本"和"硬化后的版本"放在一起对比，是最有说服力的叙事。

---

## 毕业测试

六天结束后做一次自测：**打开一个空文件，不查任何资料，三十分钟内写出一个能跑的主循环。**

写完对照检查这九点，缺一条就回去补对应的讲义章节：

- [ ] 循环有步数上限，不是 `while True`
- [ ] assistant 消息在判断终止之前就入档
- [ ] 遍历**全部** `tool_calls`，不是 `[0]`
- [ ] 每个 `tool_call.id` 都有一条 `tool` 消息回填
- [ ] 工具参数走 pydantic 校验
- [ ] 工具的错误被转成文本回喂给模型，没有 `raise`
- [ ] 分得清哪些错误该抛出循环（鉴权、余额、额度）
- [ ] 步数耗尽时会逼出一个答案，不是返回"失败"
- [ ] 每步都有 trace

能默写出来，week4 的目标就达到了。

---

## 前置代码盘点

本周不是从零开始，你已经有的零件：

| 已有 | 位置 | 本周怎么用 |
|------|------|------------|
| 工具调用（单次） | `week1/test_func_call.py` | Day 1 的起点，把它改造成循环 |
| 对话循环 + 记忆 + 摘要 | `week1/day6_chat_summarizer/` | Day 4 直接搬 `token_manager` / `summarizer` |
| 结构化输出的教训 | `week1/experiments/day4_structured_output.md` | Day 5 计划为什么必须 API 级约束 |
| 异步与并发 | `week3/ai_service/`、`async_llm.py` | Day 6 的并行执行 |
| 分层与错误处理 | `week3/ai_service/app/core/` | 全周的代码组织与异常边界 |
| SSE 流式输出 | `week3/ai_service/app/main.py` | 收尾项目推送 trace |

---

*相关博客：[week3 - 手写一个 LLM API 网关](../week3_python_abilities/week3_blog.md)*
