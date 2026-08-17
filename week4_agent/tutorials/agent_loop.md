# Python 教学讲义：Agent 主循环（Agent Loop）

> 前置知识：`week1/test_func_call.py`（一次工具调用）、`week1/day6_chat_summarizer/`（对话循环 + 记忆）、`week3/tutorials/pydantic.md`
> 相关实践：本周将手写 `week4_agent/agent/`
> 目标：能不看任何资料，从空文件手写一个带工具、能多轮迭代、有预算和错误恢复的 agent 主循环

---

## 0. 先立三句话

1. **Agent = LLM + 工具 + 循环 + 终止条件**。去掉循环，它只是一次函数调用；去掉终止条件，它是一个会烧光你钱包的 while True。
2. **`messages` 就是 agent 的全部状态**。模型本身没有记忆，每一步你都在重新递交完整卷宗。
3. **工具的错误不是异常，是给模型的观察结果**。这一条和你 week3 学的错误处理正好相反，也是本讲最重要的一句。

口诀：

> **一次调用是函数，反复调用是 agent。**
> **循环的每一轮只做一件事：把新观察塞进 messages，再问一次模型。**

---

## 1. 你已经写过 agent 的两半

翻一下自己 week1 的代码，你会发现 agent 的两个零件都在，只是没有拼起来。

**上半：会用工具，但不会循环。**`week1/test_func_call.py`：

```python
message = tool_call_llm(messages, tools)      # 问一次
tool_call = message.tool_calls[0]             # 只取第 0 个
if function_name == "get_weather":            # 写死的分派
    result = get_weather(arguments)
    messages.append(message)
    messages.append({"role": "tool", ...})
    response = call_llm(messages)             # 再问一次，结束
```

这段代码的形状是**直线**：问 → 调 → 再问 → 完。它能处理"北京天气怎么样"，处理不了"北京和上海哪个更暖和"（要调两次工具），更处理不了"帮我查天气，如果下雨就把明天的会议改成线上"（第二步依赖第一步的结果）。

**下半：会循环、有记忆，但不会用工具。**`week1/day6_chat_summarizer/main.py`：

```python
while True:
    user_input = input("\nAsk >> ")
    add_message("user", user_input)
    response = client.chat.completions.create(...)
    add_message("assistant", ...)
    maybe_summarize()
```

它的循环是**由人驱动的**：每一轮都要等一次 `input()`。

Agent loop 的关键改动只有一处：**把驱动循环的人换成模型自己**。循环不再等用户输入，而是等模型的下一个决定；模型说"我要调工具"就继续转，模型说"我说完了"才停。

```text
对话循环（week1 day6）        Agent 循环（week4）
  等人说话  ──┐                 等模型决定 ──┐
  问模型      │                 执行工具     │
  记录回答  ──┘                 记录观察   ──┘
  （人来决定是否继续）           （模型来决定是否继续）
```

一句话：**agent loop 是一个把控制权交给模型的 while 循环。**

---

## 2. messages 协议：agent 的状态机

在写任何代码之前，必须先把消息协议吃透。90% 的 agent bug 都是协议违约，表现为一个莫名的 400。

### 2.1 四种角色

| role        | 谁产生 | 作用                                                |
| ----------- | ------ | --------------------------------------------------- |
| `system`    | 你     | 身份、规则、可用工具的使用约定                      |
| `user`      | 用户   | 任务                                                |
| `assistant` | 模型   | 说话内容 `content`，**或**工具调用请求 `tool_calls` |
| `tool`      | 你     | 工具执行结果，必须带 `tool_call_id`                 |

### 2.2 一轮工具调用在 messages 里的完整长相

```python
[
  {"role": "system",    "content": "你是一个可以调用工具的助手"},
  {"role": "user",      "content": "北京和上海哪个更暖和？"},

  # 模型的决定：我要调两次工具
  {"role": "assistant", "content": None, "tool_calls": [
      {"id": "call_001", "type": "function",
       "function": {"name": "get_weather", "arguments": '{"city":"北京"}'}},
      {"id": "call_002", "type": "function",
       "function": {"name": "get_weather", "arguments": '{"city":"上海"}'}}
  ]},

  # 你的回答：每个 id 一条，一条都不能少
  {"role": "tool", "tool_call_id": "call_001", "content": "晴天 25度"},
  {"role": "tool", "tool_call_id": "call_002", "content": "小雨 22度"},

  # 拿到观察后模型才给出最终答案
  {"role": "assistant", "content": "北京更暖和，25 度对 22 度。"}
]
```

### 2.3 三条铁律

**铁律一：`tool_calls` 是一个列表，不是一个对象。**
你 week1 写的 `message.tool_calls[0]` 在单工具时能跑，但模型完全可以一次要求调三个工具。漏掉的那些永远不会被回答，于是直接违反铁律二。

**铁律二：每一个 `tool_call.id` 必须有且只有一条 `tool` 消息与之对应。**
少一条、多一条、id 拼错，下一次请求都会被拒。这是新手最常见的 400。

**铁律三：顺序不能乱。**
`tool` 消息必须紧跟在发出该请求的那条 `assistant` 消息之后。你不能先追加自己的一条 `user` 消息再补 `tool`。

心智模型：

```text
assistant(tool_calls=[a, b])  ← 一次提问
    tool(a)                    ← 必须答 a
    tool(b)                    ← 必须答 b
assistant(...)                 ← 模型才会继续
```

### 2.4 一个实践坑：SDK 对象 vs 字典

`client.chat.completions.create()` 返回的 `message` 是一个 pydantic 对象，OpenAI SDK 允许你直接 `messages.append(message)`（你 week1 就是这么写的，能跑）。但一旦你要把 `messages` 存成 JSON、写日志、或者存进数据库，混着对象和字典的列表就会咬你。

建议统一成字典：

```python
messages.append(msg.model_dump(exclude_none=True))
```

`exclude_none=True` 很重要：SDK 对象里有一堆值为 `None` 的字段（`function_call`、`refusal` 等），原样发回去有些服务端会不高兴。

---

## 3. 最小可运行主循环（这段要能背下来）

先看完整的 30 行，再逐句解释。这一版故意保留缺陷，后面五节逐个补。

```python
# week4_agent/agent/minimal.py
from openai import OpenAI
from dotenv import load_dotenv
import json
import os

load_dotenv()
client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")

TOOLS_SCHEMA = [{
  "type": "function",
  "function": {
    "name": "get_weather",
    "description": "获取某个城市的当前天气",
    "parameters": {
      "type": "object",
      "properties": {"city": {"type": "string", "description": "城市名"}},
      "required": ["city"]
    }
  }
}]


def get_weather(city: str) -> str:
  fake = {"北京": "晴天 25度", "上海": "小雨 22度", "深圳": "多云 30度"}
  return fake.get(city, "未知天气")


def run_agent(user_input: str, max_steps: int = 8) -> str:
  messages = [
    {"role": "system", "content": "你是一个可以调用工具的助手。需要外部信息时调用工具，信息足够时直接回答。"},
    {"role": "user", "content": user_input},
  ]

  for step in range(max_steps):
    resp = client.chat.completions.create(
      model="deepseek-chat",
      messages=messages,
      tools=TOOLS_SCHEMA,
    )
    msg = resp.choices[0].message
    messages.append(msg.model_dump(exclude_none=True))

    # 终止条件：模型不再要求工具，说明它认为任务完成了
    if not msg.tool_calls:
      return msg.content

    # 模型要求工具：全部执行，全部回填
    for tc in msg.tool_calls:
      args = json.loads(tc.function.arguments)
      result = get_weather(**args)
      messages.append({
        "role": "tool",
        "tool_call_id": tc.id,
        "content": result,
      })

  return "达到步数上限，任务未完成"


if __name__ == "__main__":
  print(run_agent(input(">> ")))
```

### 逐句读

- **`for step in range(max_steps)` 而不是 `while True`**。这是我唯一要求你在第一版就写对的地方。忘记加上限的 agent 会在两个工具之间反复横跳，直到你的 API 账单出问题。
- **`messages.append(msg...)` 在判断之前**。不管模型说了什么，先入档。跳过这一步，模型下一轮就不知道自己上一轮说过什么。
- **`if not msg.tool_calls: return`** 就是终止条件的主体。翻译成人话：**模型不再提问，循环就结束。**
- **`for tc in msg.tool_calls`** 遍历全部，不是 `[0]`。这是铁律一。
- **`return` 在循环里，兜底 `return` 在循环外**。跑满步数还没结束，必须有个明确的出口。

先把这段跑通，用"北京和上海哪个更暖和"验证一下 —— 你会看到模型一次要了两个 tool_call，循环转了两轮。这时候你就已经有一个 agent 了。

---

## 4. 硬化一：用注册表干掉 if/else

上面那版有两处硬编码：schema 是手写的 JSON，分派是写死的函数名。加到第三个工具时你会同时在三个地方改代码，并且一定会漏。

一个工具其实是四件东西绑在一起：**名字、说明、参数类型、实现**。那就把它们绑成一个对象。

```python
# week4_agent/agent/tools.py
from collections.abc import Callable
from dataclasses import dataclass
from pydantic import BaseModel


@dataclass(frozen=True)
class Tool:
  name: str
  description: str
  args_model: type[BaseModel]
  func: Callable[[BaseModel], str]


REGISTRY: dict[str, Tool] = {}


def register(tool: Tool) -> None:
  REGISTRY[tool.name] = tool


def tools_schema() -> list[dict]:
  """把注册表翻译成模型能看懂的"函数说明书"。"""
  return [{
    "type": "function",
    "function": {
      "name": t.name,
      "description": t.description,
      "parameters": t.args_model.model_json_schema(),
    }
  } for t in REGISTRY.values()]
```

注册一个工具：

```python
class GetWeatherArgs(BaseModel):
  city: Annotated[str, Field(description="城市名，如 北京")]


register(Tool(
  name="get_weather",
  description="获取某个城市的当前天气。需要知道某地天气时使用。",
  args_model=GetWeatherArgs,
  func=lambda a: FAKE_WEATHER.get(a.city, "未知天气"),
))
```

`model_json_schema()` 你在 week1 已经用过了，它把 pydantic 类直接变成 JSON Schema —— **参数定义只写一遍，模型看到的和你校验用的是同一份**。这是 pydantic 在 agent 工程里最大的价值。

### 关于 description：这是提示词，不是注释

模型对工具的全部认知，就是 `name` + `description` + 参数 schema。它看不到你的实现。所以：

- 写清楚**什么时候该用**，而不只是"做什么"。`"获取天气"` 不如 `"获取某个城市的当前天气。需要知道某地天气时使用。"`
- 写清楚**参数的格式约定**。城市名要中文还是拼音？日期是 `YYYY-MM-DD` 还是自然语言？不写，模型就自己编。
- 工具太多时模型会选错。**超过十几个工具就该考虑分组，或者先让模型选一个工具组。**

调试 agent 时，如果模型总是选错工具或者不肯调工具，**先改 description，再改代码**。这是性价比最高的调试动作。

---

## 5. 硬化二：模型会编造参数

模型返回的 `arguments` 是一个 JSON **字符串**，而且它由概率采样产生。它可能：JSON 语法错误、少必填字段、类型不对（`"city": 123`）、多出你没定义的字段、甚至编一个不存在的工具名。

所以 `json.loads(...)` 之后直接 `**args` 传进函数，是在拿用户请求的运气赌你的服务不崩。用 pydantic 挡住：

```python
args = tool.args_model.model_validate_json(tc.function.arguments)
```

`model_validate_json` 一步做完"解析 JSON + 校验字段 + 类型转换"，失败抛 `ValidationError`。

你 week1 已经写对了这一步：

```python
try:
  arguments = GetWeatherArgs.model_validate_json(tool_call.function.arguments)
except ValidationError as e:
  print(f"参数校验失败: {e}")
  raise            # ← 但这里错了
```

`raise` 是对的选择吗？下一节回答。

---

## 6. 硬化三：错误要回喂给模型（本讲最重要的一节）

这是从"写服务"切换到"写 agent"最反直觉的一处。

week3 里你学到的原则是：出错就抛异常，让上层的处理器把它翻译成 HTTP 响应返回给客户端。**在 agent 循环里，这个原则会毁掉你的 agent。**

因为 agent 循环里的"错误"大多不是故障，而是**信息**：

- 参数校验失败 → 模型该知道自己参数写错了，然后改一遍重试
- 工具名不存在 → 模型该知道可用工具有哪些，然后换一个
- 查询的城市不存在 → 模型该知道这条路不通，然后问用户或者换个思路
- 上游 API 超时 → 模型该知道要重试，或者告诉用户拿不到数据

一旦你 `raise`，整个循环就死了，模型永远没有机会自我修正。而它明明有这个能力 —— 你把错误信息作为 `tool` 消息塞回去，它下一轮就会改。

所以分派函数的正确形状是：**返回字符串，永不抛出。**

```python
# week4_agent/agent/dispatch.py
from pydantic import ValidationError
import json


def dispatch(tool_call) -> str:
  """执行一个工具调用，任何情况下都返回一段给模型看的文本。"""
  name = tool_call.function.name

  tool = REGISTRY.get(name)
  if tool is None:
    return f"错误：不存在名为 {name} 的工具。可用工具：{', '.join(REGISTRY)}"

  try:
    args = tool.args_model.model_validate_json(tool_call.function.arguments)
  except ValidationError as e:
    # 只回传字段和原因，别把整个 pydantic 报告塞进上下文
    brief = "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors())
    return f"参数校验失败：{brief}。请修正参数后重新调用。"
  except json.JSONDecodeError:
    return "参数不是合法 JSON，请重新生成。"

  try:
    return tool.func(args)
  except Exception as e:
    # 工具内部的真实故障：日志留全量，回给模型的只要一句
    logger.exception("工具 %s 执行失败", name)
    return f"工具执行失败：{type(e).__name__}: {e}"
```

三个细节值得注意：

**错误消息是写给模型看的提示词。**`"错误：不存在名为 X 的工具。可用工具：a, b, c"` 比 `"KeyError: X"` 有用得多 —— 后者模型只能猜，前者直接给了它下一步该干什么。**把错误信息当提示词来写。**

**回给模型的要短，写日志的要全。**上下文里的每个字符都要花钱，而且都在挤占模型的注意力。完整堆栈进 `logger.exception`，回模型的就一行。

**`except Exception` 在这里是对的。**这是我少数会推荐裸捕获的地方 —— 工具是最外层的不可信代码（可能是网络、可能是别人写的库），而循环必须活下去。但一定要配 `logger.exception`，否则你会瞎。

### 那什么错误才该真的中断循环？

区分标准是：**模型换个做法有没有可能好起来？**

| 情况                                   | 处理                                |
| -------------------------------------- | ----------------------------------- |
| 参数错、工具名错、查不到数据、上游超时 | 回喂给模型                          |
| API key 无效、余额不足、网络完全不通   | 中断循环，这是你的问题不是模型的    |
| 用户额度耗尽、请求被拒                 | 中断循环，向上抛（回到 week3 那套） |
| 工具需要的确权没通过                   | 中断，等用户确认                    |

一句话：**模型能补救的错误留在循环里，模型无能为力的错误抛出循环。**

---

## 7. 硬化四：预算与终止条件

`max_steps` 只是最粗的一道闸。一个能上线的循环通常要四道。

### 7.1 四种终止条件

```text
① 自然终止：模型不再返回 tool_calls        ← 正常出口
② 预算耗尽：步数 / token / 墙上时间超限     ← 保护出口
③ 无进展：模型反复做同一件事               ← 死循环出口
④ 显式终止：模型调用了 finish 工具          ← 可选，见下
```

### 7.2 无进展检测

最常见的死循环长这样：模型调 `get_weather("火星")`，拿到"未知天气"，不服气，再调一次，一模一样的参数，一模一样的结果，转到步数上限为止。

检测很简单 —— 把"工具名 + 参数原文"当指纹计数：

```python
from collections import Counter

seen: Counter[tuple[str, str]] = Counter()

# 循环内，执行工具之前
key = (tc.function.name, tc.function.arguments)
seen[key] += 1
if seen[key] >= 3:
  result = "你已经用完全相同的参数调用过这个工具两次，结果不会改变。请换一种方法，或者直接基于现有信息给出结论。"
else:
  result = dispatch(tc)
```

注意这里也是**回喂**而不是中断 —— 给模型一次自救的机会，比直接掐死体验好得多。

### 7.3 步数上限撞到之后不要只 return 一句"失败"

跑满 8 步的 agent 手里往往已经有大量有用信息，直接返回"任务未完成"是把它全扔了。更好的做法是**追加一条指令，再问模型一次，但这次不给工具**：

```python
messages.append({
  "role": "user",
  "content": "已达到工具调用次数上限。请基于目前已获得的信息，直接给出你的最佳答案，并说明还缺什么信息。"
})
final = client.chat.completions.create(
  model="deepseek-chat",
  messages=messages,
  tools=tools_schema(),
  tool_choice="none",     # 关键：禁止再调工具，逼它给出文字答案
)
return final.choices[0].message.content
```

`tool_choice` 一般支持 `"auto"`（默认，模型自己决定）和 `"none"`（禁止调用）。强制指定某个具体工具各家写法不一致，用之前查文档。

### 7.4 要不要 finish 工具？

一种流派是给模型一个 `finish(answer: str)` 工具，规定它必须靠调这个工具来结束。

- **好处**：终止变成一个显式的、可校验的动作；最终答案有结构（可以要求 `answer` 之外还带 `confidence`、`sources`）。
- **坏处**：多一次工具调用的开销；模型有时会忘了调，你还得处理"它直接说话了"的情况。

我的建议：**入门先用"没有 tool_calls 就结束"**，简单且不会错。等你需要结构化的最终产出（比如必须返回一个 JSON 报告）时再引入 `finish`。

---

## 8. 硬化五：上下文是会二次增长的

这是 agent 和普通对话最大的成本差异，也是最容易被忽略的一点。

**每一轮循环，你都要把完整的 messages 重新发一遍**。假设每轮新增的内容差不多，那么第 1 轮发 1 份，第 2 轮发 2 份，第 n 轮发 n 份 —— 总输入量是 **O(n²)**。一个 10 步的 agent，输入 token 大约是单轮的 55 倍。

而 agent 的上下文膨胀主要来自工具结果：一次网页抓取、一次数据库查询、一次文件读取，动辄几千 token，而模型真正需要的可能就一行。

四个对策，按性价比排序：

**① 让工具自己节流**。最有效的一条。工具的返回值应该是"给模型的摘要"，不是"原始数据转储"。读文件就只返回相关片段，查数据库就只返回需要的列并限制行数，抓网页就先抽正文。

```python
MAX_TOOL_CHARS = 2000

def truncate(text: str) -> str:
  if len(text) <= MAX_TOOL_CHARS:
    return text
  return text[:MAX_TOOL_CHARS] + f"\n...（已截断，原文共 {len(text)} 字符）"
```

截断时**一定要告诉模型你截断了**，否则它会把残缺的数据当成完整数据来推理。

**② 丢弃旧的工具结果**。第 8 步的时候，第 1 步那个工具的原始输出通常已经没用了 —— 它的结论已经体现在后续的 assistant 消息里。可以把超过 N 步之前的 `tool` 消息内容替换成 `"[已省略的历史工具结果]"`。注意：**消息本身不能删**，否则违反第 2 节的铁律二，只能替换 `content`。

**③ 摘要压缩**。你 week1 的 `day6_chat_summarizer` 就是干这个的，`summarize_chat` 和 `count_tokens` 可以直接搬过来。触发点从"对话轮数"改成"messages 的 token 总量"。注意摘要的边界要落在一组完整的 `assistant(tool_calls) + tool(...)` 之外，不能把它们劈开。

**④ 外置存储 + 引用**。大块结果写进文件或 KV，工具只返回一个 id 和摘要，模型需要细节时再用另一个工具按 id 取回。这是处理长文档任务的标准做法。

先做 ① 和 ②，简单且立刻见效。③ 等你真的做多轮长任务时再上。

---

## 9. 可观测性：没有 trace 就没法调 agent

普通函数出错，你看堆栈。agent 出错，堆栈啥也不说 —— 它每一步都"正常执行"了，只是决策很蠢。**你唯一的调试手段是完整记录每一步的决策。**

每一步至少记这些：

```python
from dataclasses import dataclass, field

@dataclass
class StepTrace:
  index: int
  thought: str | None          # 模型这轮说的话（有些模型会边说边调）
  tool_name: str | None
  tool_args: str | None
  tool_result: str | None
  prompt_tokens: int
  completion_tokens: int
  latency_ms: int
```

`resp.usage` 里有 token 数，直接取。

一个够用的实时打印格式：

```text
┌ step 1  (1,204 in / 38 out, 1.8s)
│ tool  get_weather {"city":"北京"}
└ obs   晴天 25度

┌ step 2  (1,301 in / 42 out, 1.9s)
│ tool  get_weather {"city":"上海"}
└ obs   小雨 22度

┌ step 3  (1,398 in / 61 out, 2.1s)
└ done  北京更暖和，25 度对 22 度。

总计 3 步，3,903 in / 141 out，5.8s
```

盯着这个输出，你能立刻看出三类问题：**输入 token 每步涨多少**（第 8 节的问题）、**模型在哪一步选错工具**（第 4 节的 description 问题）、**有没有重复调用**（第 7 节的无进展问题）。

把 trace 存成 JSON 落盘。你会需要反复回看同一个失败案例 —— 而 agent 有随机性，跑第二次不一定重现。

---

## 10. 把五道硬化装起来

到这里，一个可以拿来用的循环长这样。**建议你不要抄，照着结构自己写一遍。**

```python
# week4_agent/agent/loop.py
def run_agent(
  user_input: str,
  max_steps: int = 8,
  system_prompt: str = DEFAULT_SYSTEM_PROMPT,
) -> AgentResult:
  messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_input},
  ]
  traces: list[StepTrace] = []
  seen: Counter[tuple[str, str]] = Counter()

  for step in range(1, max_steps + 1):
    # 1. 问模型（这里可能抛出真正该中断的错误：鉴权、余额、网络）
    resp = call_model(messages, tools_schema())
    msg = resp.choices[0].message
    messages.append(msg.model_dump(exclude_none=True))

    # 2. 没有工具请求 → 自然终止
    if not msg.tool_calls:
      traces.append(...)
      return AgentResult(answer=msg.content, traces=traces, stop_reason="finished")

    # 3. 执行每一个工具请求，一个都不能漏
    for tc in msg.tool_calls:
      key = (tc.function.name, tc.function.arguments)
      seen[key] += 1
      if seen[key] >= 3:
        result = "你已用相同参数调用过该工具两次，请改变策略。"
      else:
        result = truncate(dispatch(tc))      # 永不抛出

      messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
      traces.append(...)

    # 4. 上下文治理
    messages = compact(messages)

  # 5. 预算耗尽：逼一个答案出来，而不是丢弃全部工作
  return force_final_answer(messages, traces)
```

五个位置对应五道硬化，顺序不要改：**先入档，再判终止，再执行全部工具，再治理上下文，最后兜底。**

---

## 11. 常见错误（Code Review 必抓）

1. **只处理 `tool_calls[0]`**。多工具请求时必崩，而且崩在下一轮，很难定位。
2. **`tool` 消息漏了 `tool_call_id`，或者 id 对不上**。下一次请求 400。
3. **执行工具之前忘了把 assistant 消息入档**。模型会失忆，反复要求同一个工具。
4. **`while True` 没有步数上限。**
5. **工具里的异常直接往外抛**。模型失去自救机会，一个可恢复的小错变成整个任务失败。
6. **把完整堆栈 / 完整 pydantic 报告回喂给模型**。上下文爆炸，注意力被垃圾占满。
7. **工具返回上万字符的原始数据**。第 3 步就把上下文撑爆。
8. **删除历史消息来省 token**。破坏 assistant/tool 配对，直接 400。只能替换 content。
9. **步数用尽只返回一句"失败"**。扔掉了已经花钱买到的全部信息。
10. **`arguments` 当成 dict 用**。它是字符串，必须 `json.loads` 或 `model_validate_json`。
11. **没有 trace**。出问题时你只能靠猜，而且案例不可重现。
12. **system prompt 里不写工具使用规则**。比如"信息足够时直接回答，不要为了调用而调用"。

---

## 12. 动手练习

按顺序做，每一关都要能跑起来再进下一关。

**第 1 关：最小循环**。照第 3 节写 `minimal.py`，只有 `get_weather` 一个工具。用"北京和上海哪个更暖和"验证多工具调用，用"你好"验证零工具调用直接返回。

**第 2 关：注册表**。加两个工具：`calculator(expression)` 和 `now()`（返回当前时间）。把 if/else 换成注册表 + `dispatch`。验证：问"现在几点？三小时后是几点？"看它是否连续调两个工具。

**第 3 关：错误回喂**。故意问"火星的天气"。观察模型拿到"未知天气"之后的行为。然后给 `calculator` 传一个非法表达式，确认循环没有崩，且模型改了参数重试。

**第 4 关：预算与无进展**。把 `max_steps` 设成 3，构造一个需要 5 步的任务，实现第 7.3 节的强制收尾。再实现无进展检测，用"火星天气"验证。

**第 5 关：trace**。实现第 9 节的打印和落盘。跑一个 5 步任务，看输入 token 每步涨了多少，算一下 O(n²) 是否成立。

**第 6 关：上下文治理**。加一个 `read_file(path)` 工具读一个长文件，观察上下文爆炸，然后用截断 + 丢弃旧工具结果把它压回去。

**进阶（可选）**：把 `dispatch` 改成 `async`，用 `asyncio.gather` 并发执行同一轮里的多个 `tool_calls`（week3 的异步功底正好用上）。注意：回填顺序要和 `tool_calls` 一致。

---

## 13. 速查表

| 概念         | 一句话                                           |
| ------------ | ------------------------------------------------ |
| agent loop   | 把控制权交给模型的 while 循环                    |
| 状态         | 全部在 `messages` 里，模型自己没有记忆           |
| 终止         | 模型不再返回 `tool_calls`                        |
| 铁律         | 每个 `tool_call.id` 必须有且只有一条 `tool` 回复 |
| 工具 =       | 名字 + 说明 + 参数 schema + 实现                 |
| description  | 是提示词，不是注释；调不对工具先改它             |
| 参数         | 是 JSON 字符串，必须 pydantic 校验               |
| 工具错误     | 回喂给模型，不要抛出                             |
| 该抛出的错误 | 模型换个做法也救不了的（鉴权、余额、额度）       |
| 预算         | 步数 + token + 时间，三个都要                    |
| 撞上限       | `tool_choice="none"` 逼一个答案，别丢工作        |
| 成本         | 输入 token 随步数 O(n²) 增长                     |
| 省 token     | 先让工具少说话，再丢旧工具结果，最后才上摘要     |
| 压缩禁忌     | 不能删消息，只能替换 content                     |
| 调试         | 没有 trace 就没法调 agent                        |

---

## 14. 下一步学什么

1. **`planner_executor.md`** —— 当任务需要五步以上、或者需要在动手前给用户看一遍计划时，纯循环就不够了。
2. **上下文工程** —— 把 week1 的 `day6_chat_summarizer` 正式接进循环。
3. **子 agent** —— 一个工具的实现本身就是另一个 agent loop。
4. **把 agent 挂到 week3 的 `ai_service` 上** —— 用 SSE 把每一步的 trace 实时推给前端。这是本周的收尾项目，也正好复用你上周的流式功底。

---

_相关代码：`week1/test_func_call.py`（工具调用的起点）、`week1/day6_chat_summarizer/`（循环与记忆）、`week3/ai_service/`（异步与错误处理）_
