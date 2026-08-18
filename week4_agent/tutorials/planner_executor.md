# Python 教学讲义：Planner / Executor（规划器与执行器）

> 前置知识：`agent_loop.md`（必须先能手写主循环）、`week1` 实验四（API 级结构化输出）
> 相关实践：`week4_agent/agent/planner.py`、`executor.py`
> 目标：讲清纯循环在什么时候不够用；能手写"规划 → 执行 → 重规划"三段式，并知道什么时候**不该**用它

---

## 0. 先立三句话

1. **Planner/Executor 是把"想"和"做"拆开**。规划器只输出计划不碰工具，执行器只执行不做决策。
2. **计划必须是结构化输出**。让模型用自然语言写计划、你再去解析，是 week1 实验四已经证明过会被击穿的方案。
3. **它最大的收益经常不是"规划得更好"，而是上下文隔离和可审批**。这一条想明白了，你才知道什么时候该用它。

口诀：

> **循环是走一步看一步，计划是先画地图再上路。**
> **地图画错了，比没有地图更危险。**

---

## 1. 纯循环在什么时候不够用

上一讲那个硬化过的循环已经能干不少事了。它的工作方式是**贪心**的：每一步只看当前上下文，决定下一个动作，不做全局考虑。这带来四个具体问题。

**① 会跑偏，而且没人拦得住**。十步的任务，第三步选错方向，后面七步全在错误的分支上努力。等你看到最终答案时，钱已经花完了。循环内部没有任何机制能发现"我整体方向错了"。

**② 天然串行**。"分别查北京、上海、深圳三地天气再对比"，一个循环里模型**可能**一次发三个 tool_calls，也可能一次发一个转三轮。你无法控制。而如果三个子任务需要各自多步完成，循环就一定是串行的。

**③ 上下文单调膨胀**。上一讲第 8 节说过输入是 O(n²)。十步任务里第 9 步还背着第 1 步的原始工具输出，既贵又干扰注意力。

**④ 对用户是个黑盒**。跑了 40 秒，用户不知道进行到哪、还剩多少、要花多少钱，也没有机会在它动手之前喊停。任务一旦涉及写文件、发邮件、改数据库，"事前审批"就是硬需求。

Planner/Executor 就是冲着这四条来的。

---

## 2. 三种编排模式

| 模式                    | 形状                              | 适合                                     |
| ----------------------- | --------------------------------- | ---------------------------------------- |
| **ReAct（纯循环）**     | 想→做→观察→想→做…                 | 步数少（≤3）、路径不确定、需要边看边调整 |
| **Plan-and-Execute**    | 先规划一次 → 依次执行 → 汇总      | 步骤可预见、彼此独立、需要并行或需要审批 |
| **Plan-Execute-Replan** | 规划 → 执行 → 发现偏差 → 重新规划 | 长任务、环境会变、失败率高               |

```text
ReAct                    Plan-and-Execute              Plan-Execute-Replan

 ┌─────────┐              ┌─────────┐                    ┌─────────┐
 │  LLM    │◄──┐          │ Planner │                    │ Planner │◄────┐
 └────┬────┘   │          └────┬────┘                    └────┬────┘     │
      │        │               │ plan                        │ plan     │
      ▼        │               ▼                             ▼          │
   ┌─────┐     │        ┌──────────────┐              ┌──────────────┐   │
   │工具 ├─────┘        │ Executor ×N  │              │ Executor ×N  │   │
   └─────┘              └──────┬───────┘              └──────┬───────┘   │
                               ▼                             ▼           │
                            汇总答案                     偏差检测 ────────┘
```

三者不是替代关系。**真实系统里，Executor 执行单个步骤时，内部跑的就是一个 ReAct 循环**。所以上一讲不是被这一讲取代了，而是成了这一讲的零件。

---

## 3. 计划必须是结构化输出

你在 week1 实验四已经验证过一次这件事：靠 system prompt 约束模型输出 JSON，遇到干扰就会被击穿，下游代码直接崩。**计划是要被代码逐条执行的数据结构，格式一旦坏掉，整个执行器就废了**。所以这里绝不能靠"请你输出 JSON"。

### 3.1 先定义计划的类型

```python
# week4_agent/agent/schemas.py
from pydantic import BaseModel, Field
from typing import Literal


class PlanStep(BaseModel):
  id: int = Field(description="步骤编号，从 1 开始")
  goal: str = Field(description="这一步要达成的目标，一句话，必须可独立执行")
  depends_on: list[int] = Field(default_factory=list, description="依赖哪些步骤的结果")
  suggested_tool: str | None = Field(default=None, description="建议使用的工具名，可为空")


class Plan(BaseModel):
  reasoning: str = Field(description="为什么这样拆分，两三句话")
  steps: list[PlanStep] = Field(max_length=8, description="步骤列表，最多 8 步")
```

字段设计的取舍，逐个说：

- **`goal` 而不是 `action`**。计划描述"要达成什么"，不描述"怎么做"。怎么做是执行器（和它内部的模型）的自由 —— 规划时模型手里没有数据，指定具体做法多半是瞎猜。
- **`depends_on` 是并行的前提**。没有它你只能顺序执行。有了它，同一层的步骤可以并发。
- **`suggested_tool` 只是建议，不是约束**。规划器对工具的了解是二手的，硬绑会让执行器在明显更好的工具面前动不了。
- **`reasoning` 放在 `steps` 前面**。字段顺序会影响生成质量 —— 先写理由，再写步骤，相当于给模型一个内建的思考区。
- **`max_length=8`**。不设上限，模型能给你规划出 25 步。步数是成本，也是失败面。

### 3.2 两种拿到结构化计划的方式

**方式一：API 级 JSON 模式 + pydantic 校验。**

```python
def make_plan(task: str, tools_desc: str) -> Plan:
  resp = client.chat.completions.create(
    model="deepseek-chat",
    response_format={"type": "json_object"},        # API 级约束，不是提示词级
    messages=[
      {"role": "system", "content": PLANNER_PROMPT.format(
          tools=tools_desc,
          schema=json.dumps(Plan.model_json_schema(), ensure_ascii=False))},
      {"role": "user", "content": task},
    ],
  )
  return Plan.model_validate_json(resp.choices[0].message.content)
```

用 `json_object` 模式时，**schema 仍然要写进 prompt** —— 这个模式只保证"是合法 JSON"，不保证"符合你的结构"。真正的结构保证来自 `Plan.model_validate_json` 那一行。

**方式二：把规划做成一个工具。**

给规划器一个 `submit_plan` 工具，参数就是 `Plan`。模型必须通过调用它来交计划，于是复用了工具调用那套天然的 schema 约束。好处是和你的循环基础设施统一；坏处是多一层间接。

两种都行。**入门用方式一**，代码更直白。

### 3.3 校验失败要重试一次，把错误告诉模型

和上一讲"错误回喂"是同一个道理：

```python
for attempt in range(2):
  raw = ask_planner(task, extra=error_hint)
  try:
    return Plan.model_validate_json(raw)
  except ValidationError as e:
    error_hint = f"上一次的输出不符合 schema：{e.errors()[:3]}。请严格按 schema 重新输出。"
raise PlanningError("规划器连续两次输出非法结构")
```

注意最后是 `raise` 而不是回喂 —— **规划失败是"模型换个做法也救不了"的那一类**（参见上一讲第 6 节的判据），没有计划就没有后续，该向上抛。

---

## 4. Executor：每一步是一个小 agent loop

执行器的核心认知是：**它不是一个"函数调度器"，而是一个目标更小、工具更少、上下文更干净的 agent。**

```python
def execute_step(step: PlanStep, board: dict[int, str], max_steps: int = 5) -> str:
  """执行单个步骤。内部就是上一讲那个循环。"""
  context = "\n".join(f"步骤 {i} 的结果：{board[i]}" for i in step.depends_on if i in board)

  messages = [
    {"role": "system", "content": EXECUTOR_PROMPT},
    {"role": "user", "content": f"当前目标：{step.goal}\n\n已知信息：\n{context or '（无）'}"},
  ]
  # ↓ 这里调用的就是 agent_loop.md 第 10 节那个 run_agent 的内核
  return run_loop(messages, tools=tools_schema(), max_steps=max_steps).answer
```

请注意这里最要紧的一件事：**每个步骤都用一个全新的 `messages`。**

它带来的好处比"规划得更好"实在得多：

- **上下文隔离**。步骤 5 看不到步骤 1 的原始工具输出，只看到 `board[1]` 里那条被提炼过的结论。
- **成本从 O(n²) 变成 n 个小 O(k²)**。这是 planner/executor 最被低估的收益。十步的单循环，第十步要背九步的全部历史；十步的 planner/executor，每步只背自己那点上下文加几条依赖结论。
- **失败被围住了**。某一步陷入死循环，只烧掉那一步的预算，不污染其他步骤的上下文。

代价是：**跨步骤的隐性信息会丢失。**步骤 1 顺手发现的某个细节，如果没写进它的返回值，步骤 5 就永远看不到。所以执行器的返回值该写成什么，是要设计的 —— 见下一节。

---

## 5. 状态传递：黑板

步骤之间要交换数据。有两种做法：

**做法一：全量传递 transcript。**把前面所有步骤的完整对话拼给下一步。简单，但等于放弃了上下文隔离，退化成一个更贵的单循环。**不推荐。**

**做法二：黑板（blackboard）**。一个 `step_id -> 结果` 的字典，每步执行完把提炼后的结果写上去，下一步按 `depends_on` 取用。

```python
@dataclass
class Blackboard:
  results: dict[int, str] = field(default_factory=dict)
  failures: dict[int, str] = field(default_factory=dict)

  def context_for(self, step: PlanStep) -> str:
    lines = []
    for dep in step.depends_on:
      if dep in self.results:
        lines.append(f"步骤 {dep} 的结果：{self.results[dep]}")
      elif dep in self.failures:
        lines.append(f"步骤 {dep} 执行失败：{self.failures[dep]}")
    return "\n".join(lines)
```

黑板要不要记失败？**要**。下游步骤知道"上一步没拿到数据"，和"上一步根本没跑"，行为应该是不一样的。

### 写进黑板的应该是什么

不要把执行器循环的最后一条 assistant 消息原样丢进去。它经常是"好的，我已经查到北京今天晴天 25 度了，希望这对您有帮助！"这种带客套的自然语言。

更好的做法是**要求执行器返回结构化结果**：

```python
class StepResult(BaseModel):
  status: Literal["success", "failed", "partial"]
  output: str = Field(description="给后续步骤用的事实性结论，不要客套话")
  note: str | None = Field(default=None, description="遇到的问题或不确定之处")
```

`status` 是重规划的触发信号，`output` 是给黑板的，`note` 是给规划器判断要不要调整的。

---

## 6. 依赖与并行

有了 `depends_on`，计划就是一张有向无环图。按拓扑分层，同一层可以并发 —— 而你 week3 的异步功底正好用在这里。

```python
def topological_levels(steps: list[PlanStep]) -> list[list[PlanStep]]:
  """把步骤分层，同一层内互不依赖，可并发执行。"""
  done: set[int] = set()
  remaining = {s.id: s for s in steps}
  levels = []
  while remaining:
    ready = [s for s in remaining.values() if set(s.depends_on) <= done]
    if not ready:
      raise PlanningError(f"计划存在循环依赖：{list(remaining)}")
    levels.append(ready)
    done |= {s.id for s in ready}
    for s in ready:
      del remaining[s.id]
  return levels
```

```python
for level in topological_levels(plan.steps):
  results = await asyncio.gather(
    *(execute_step_async(s, board) for s in level),
    return_exceptions=True,
  )
  ...
```

两个必须注意的点：

**`return_exceptions=True` 不能省**。否则同层里一个步骤炸了，`gather` 会直接把异常抛出来，其他已经跑完的步骤结果全丢。

**一定要检测循环依赖**。模型完全可能生成 `1 依赖 2、2 依赖 1`。上面那个 `if not ready` 分支就是干这个的 —— 少了它，`while` 会空转成死循环。

并行不是免费的：几个步骤同时打同一个上游 API 可能触发限流，同时写同一个文件会互相覆盖。**只有确认无副作用冲突的步骤才并行。**

---

## 7. Replan：什么时候重新规划

规划器是在**没有任何数据**的情况下画的地图，它一定会错。三个典型触发点：

| 触发       | 判断方式                        | 动作                         |
| ---------- | ------------------------------- | ---------------------------- |
| 步骤失败   | `StepResult.status == "failed"` | 带着失败原因重新规划剩余部分 |
| 前提被推翻 | 执行结果和计划假设矛盾          | 重新规划                     |
| 发现新分支 | 结果里出现计划外的必要工作      | 追加步骤                     |

```python
MAX_REPLANS = 2

def run(task: str) -> str:
  plan = make_plan(task)
  board = Blackboard()
  replans = 0

  while True:
    outcome = execute_plan(plan, board)          # 逐层执行，遇失败提前返回
    if outcome.ok or replans >= MAX_REPLANS:
      break
    replans += 1
    plan = make_plan(task, previous=plan, board=board)   # 带上已有进展重新规划

  return summarize(task, board)
```

三条实践经验：

**重规划次数必须有上限**。没有上限，planner 和 executor 会互相甩锅到天荒地老。2 到 3 次足够。

**重规划要带上已完成的成果**。否则新计划会让你把已经做完的事再做一遍。把黑板里的成功结果作为"已知信息"喂给规划器，并明确告诉它"这些不用再做"。

**失败的步骤要带原因。**"步骤 3 失败了"没有信息量；"步骤 3 失败：目标网站返回 403，需要登录"才能让规划器绕路。

---

## 8. 什么时候**不该**用 Planner

这一节比前面七节加起来都重要，因为 planner 是被滥用得最狠的一个模式。

**① 任务在三步以内**。规划本身要花一次完整的 LLM 调用（几秒 + 一笔 token），而三步任务的循环自己就能走对。你付了规划的钱，买到零收益。

**② 计划错了比没计划更糟**。这是最要命的一点。纯循环走错一步，下一步看到坏结果**有机会自我纠正**；而 planner/executor 里，执行器是"忠实的傻子"，它会一丝不苟地执行一个愚蠢的计划，一路执行到底。**你等于把纠错能力换成了并行能力。**

**③ 规划器是瞎的**。它在看到任何真实数据之前就要决定全部步骤。任务越依赖"先看看情况"，规划质量越差。典型反例：排查线上故障——第一步查到什么，完全决定第二步查哪里，这种任务规划出来的地图纯属虚构。

**④ 多一层，多一层的失败面**。计划结构非法、循环依赖、步骤目标写得含混导致执行器理解偏差、黑板里的结论丢了关键细节 —— 这些故障模式在纯循环里统统不存在。

那什么时候它真的划算？

- **步骤多且彼此独立**（能并行，收益是墙上时间）
- **需要事前审批**（要写文件、发消息、花钱之前，先给人看一眼计划）
- **需要展示进度**（"3/7 步已完成"，纯循环给不出这个）
- **长任务的上下文治理**（第 4 节说的隔离收益，通常比规划本身更值钱）

我的建议非常明确：**先把上一讲那个硬化过的循环写扎实，遇到具体的痛点了再上 planner**。如果你说不清自己要买上面四条里的哪一条，那就是不需要。

---

## 9. 和 week3 分层的对应关系

你上周搭的那套分层在这里能原样复用，只是名字换了：

| week3 `ai_service` | week4 agent           | 职责                         |
| ------------------ | --------------------- | ---------------------------- |
| 路由层 `main.py`   | Orchestrator          | 只做编排，不含业务判断       |
| service 层         | Planner / Executor    | 决策与流程                   |
| repository 层      | Tools                 | 唯一产生副作用的地方         |
| schemas            | `Plan` / `StepResult` | 层与层之间的数据契约         |
| `core/errors.py`   | agent 异常体系        | 区分"回喂给模型"和"抛出循环" |

一条依然成立的原则：**每一层只允许知道一件事**。规划器不知道工具怎么实现，执行器不知道整体任务长什么样，工具不知道自己被谁调用。

一条需要改写的原则：week3 里"异常一路抛到最外层翻译成 HTTP"，在 agent 里要拆成两条路 —— 模型能补救的错误留在循环内部，模型无能为力的才抛出去交给 week3 那套处理器。

---

## 10. 常见错误（Code Review 必抓）

1. **靠提示词约束计划的 JSON 格式**。week1 实验四已经证明会被击穿，必须 API 级 + pydantic 校验。
2. **计划步数不设上限**。模型能给你规划 25 步。
3. **不检测循环依赖**。拓扑排序空转成死循环。
4. **`asyncio.gather` 忘了 `return_exceptions=True`**。一个失败带走整层结果。
5. **重规划不带已完成的进展**。同样的工作做两遍。
6. **黑板里存执行器的原始客套回答**。下游步骤要从"希望对您有帮助"里抠事实。
7. **`suggested_tool` 被当成强制约束**。执行器被绑死在一个次优工具上。
8. **规划失败时回喂给模型无限重试**。该抛的时候要抛，两次就够。
9. **给三步的任务上 planner**。纯粹的负优化。
10. **执行器共享同一个 `messages`**。上下文隔离的收益全没了，还多付了规划的钱。
11. **步骤 `goal` 写得不可独立执行**（如"继续上一步"）。执行器拿到一个空白上下文，根本不知道"上一步"是什么。

---

## 11. 动手练习

**第 1 关：只做规划器**。输入一个任务，输出一个 `Plan` 并打印。先不执行。用三个难度递增的任务测：单步的、三步独立的、有依赖的。观察它在什么任务上会规划得离谱。

**第 2 关：串行执行器**。按 `id` 顺序执行，黑板用最简单的 `dict[int, str]`。跑通"查北京、上海、深圳天气并对比"。

**第 3 关：结构化步骤结果**。把执行器的返回换成 `StepResult`，让黑板里存 `output` 而不是原始回答。对比一下前后，下游步骤的表现差多少。

**第 4 关：拓扑分层 + 并发**。实现第 6 节的分层，用 `asyncio.gather` 并发同层步骤。测总耗时相对串行版降了多少 —— 这是本关唯一有意义的验收指标。手工构造一个循环依赖的计划，确认能被检测出来而不是死循环。

**第 5 关：重规划**。造一个必然失败的步骤（比如查一个不存在的城市），验证重规划能绕开它，并且不会重做已完成的步骤。

**第 6 关（关键）：对比实验**。同一组任务，分别用纯循环和 planner/executor 跑，记录**成功率、总 token、墙上时间、步数**四个指标。你大概率会发现：短任务纯循环全面胜出，长任务和可并行任务 planner 才开始赢。**把这个表格写进你的 week4 博客**，它比任何转述的结论都有说服力。

---

## 12. 速查表

| 概念               | 一句话                                     |
| ------------------ | ------------------------------------------ |
| Planner            | 只输出计划，不碰工具                       |
| Executor           | 执行单个步骤，内部是一个小 agent loop      |
| Blackboard         | `step_id → 提炼后的结果`，步骤间唯一的通道 |
| 计划格式           | API 级 JSON + pydantic 校验，绝不靠提示词  |
| `goal` vs `action` | 计划说目标，执行器决定做法                 |
| `depends_on`       | 并行的前提，也是循环依赖的风险来源         |
| 上下文隔离         | 每步全新 messages，O(n²) 降成 n 个小 O(k²) |
| 重规划             | 必须限次数、必须带进展、必须带失败原因     |
| 最大隐性收益       | 上下文隔离 + 可审批 + 可展示进度           |
| 最大风险           | 执行器会忠实执行一个愚蠢的计划             |
| 什么时候别用       | 三步以内、需要边看边调整的任务             |

---

## 13. 下一步学什么

1. **子 agent（层级 agent）** —— 让某个步骤本身也是一个完整的 planner/executor。
2. **人在环中（human-in-the-loop）** —— 计划生成后暂停，等用户批准或修改再执行。这是 planner 模式最实用的落地形态。
3. **评估** —— 攒一组固定任务当作回归测试集，每次改提示词或改结构都跑一遍。agent 没有单元测试，只有 eval。
4. **接进 `ai_service`** —— 用 SSE 把"计划已生成""第 3/7 步完成"实时推给前端。week3 的流式输出正好在这里变现。

---

_相关讲义：`agent_loop.md`（本讲的基础，必须先掌握）_
_相关代码：`week1/experiments/day4_structured_output.md`（为什么必须 API 级结构化）、`week3/ai_service/`（分层与异步）_
