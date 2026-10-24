# Python 教学讲义：异步编程（asyncio）

> 前置知识：函数、`with` 语句、`for` 循环、异常处理。不需要任何并发经验。
> 相关代码：`week3_python_abilities/async_llm.py`、`ai_service/app/llm/deepseek.py`、`ai_service/app/main.py`
> 目标：读完能回答三个问题——异步到底在省什么时间；`await` 那一刻程序发生了什么；同步代码和异步代码的边界怎么跨。

所有示例都用 Python 3.11 以上语法。你的环境是 3.14，可以直接跑。

---

## 0. 先立三句话

1. **异步省的是等待时间，不是计算时间。** 程序在等网络、等磁盘、等数据库的时候，CPU 是空着的。异步让这段空闲去干别的事。
2. **`await` 是一个「我先让开」的标记。** 遇到它，当前函数暂停，把控制权交还给调度器；等它等的东西好了，再从这一行继续。
3. **整个异步程序只有一条线在跑。** 所以任何一处「不让开」的阻塞调用，会卡住所有人。

口诀：

> **等的时候让开，好了再回来。**
> **一个 `time.sleep`，全员罚站。**

---

## 1. 为什么要有异步：一个服务员的故事

一家餐厅只有一个服务员。三桌客人同时点菜，每道菜厨房要做 3 分钟。

**同步做法**：服务员给第一桌下单，站在厨房门口等 3 分钟，端菜；再给第二桌下单，再等 3 分钟……三桌全部上齐要 9 分钟。服务员的 9 分钟里有 9 分钟在**等**。

**异步做法**：服务员给第一桌下单，不等，转身给第二桌下单，再给第三桌下单。厨房哪道菜先好，就先端哪道。三桌全部上齐要 3 分钟出头。服务员还是一个人，只是**不在原地等**。

这就是异步的全部思想。服务员是你的程序（一条执行线），厨房是网络、磁盘、数据库这些**外部设备**，「做菜的 3 分钟」是 **IO 等待**（Input/Output，输入输出：程序把请求发出去、等结果回来这段时间）。

### 1.1 用代码看这 9 分钟

```python
# sync_demo.py
import time

def fetch(name: str) -> str:
  print(f"{name} 开始请求")
  time.sleep(1)                 # 模拟 1 秒的网络等待
  print(f"{name} 拿到结果")
  return f"{name} 的数据"

start = time.perf_counter()
results = [fetch("A"), fetch("B"), fetch("C")]
print(f"总耗时 {time.perf_counter() - start:.1f}s")
```

```text
A 开始请求
A 拿到结果
B 开始请求
B 拿到结果
C 开始请求
C 拿到结果
总耗时 3.0s
```

三次 1 秒的等待串成了 3 秒。`time.sleep(1)` 期间程序什么都没做，但也没让开。

### 1.2 同一件事的异步写法

```python
# async_demo.py
import asyncio
import time

async def fetch(name: str) -> str:
  print(f"{name} 开始请求")
  await asyncio.sleep(1)        # 模拟 1 秒的网络等待，但这次「让开」
  print(f"{name} 拿到结果")
  return f"{name} 的数据"

async def main():
  start = time.perf_counter()
  results = await asyncio.gather(fetch("A"), fetch("B"), fetch("C"))
  print(results)
  print(f"总耗时 {time.perf_counter() - start:.1f}s")

asyncio.run(main())
```

```text
A 开始请求
B 开始请求
C 开始请求
A 拿到结果
B 拿到结果
C 拿到结果
['A 的数据', 'B 的数据', 'C 的数据']
总耗时 1.0s
```

三个请求的等待**重叠**了。注意输出顺序：三个「开始请求」连在一起，然后才是三个「拿到结果」。A 刚说完「开始」就在 `await` 处让开了，B 才有机会说「开始」。

这就是本讲全部内容的缩影。后面每一节都在解释这 15 行代码里的某个词。

### 1.3 什么任务适合异步

| 任务类型                           | 时间花在哪           | 异步有没有用                      |
| ---------------------------------- | -------------------- | --------------------------------- |
| 调用 LLM API、抓网页、查远程数据库 | 等网络回包           | **有**，这是异步的主场            |
| 读写大文件、等用户输入             | 等磁盘 / 等人        | 有                                |
| 同时处理几百个用户的 HTTP 请求     | 大部分请求都在等上游 | **有**，这是 FastAPI 用异步的原因 |
| 矩阵乘法、图片压缩、排序一亿个数   | CPU 一直在算         | **没有**，没有「等待」可以省      |

判断方法：这段代码在跑的时候，CPU 占用是不是接近 0。接近 0 说明它在等，异步能帮上忙。

---

## 2. 三种并发方式，异步是其中一种

**并发**（concurrency）：多件事在同一时间段内交替推进。**并行**（parallelism）：多件事在同一时刻真的同时执行。一个服务员照顾三桌是并发，三个服务员各照顾一桌是并行。

Python 里实现并发有三条路：

| 方式                         | 一句话                                    | 适合                    | 代价                                                 |
| ---------------------------- | ----------------------------------------- | ----------------------- | ---------------------------------------------------- |
| **多进程** `multiprocessing` | 开多个独立的 Python 解释器                | CPU 密集计算            | 进程间不共享内存，启动慢，通信要序列化               |
| **多线程** `threading`       | 一个进程里开多条执行线，操作系统轮流切换  | IO 密集，且必须用同步库 | 切换由操作系统决定，你控制不了在哪切；共享数据要加锁 |
| **异步** `asyncio`           | 一条执行线，程序自己决定在 `await` 处切换 | IO 密集，有异步库可用   | 一处阻塞全员卡住；整套库都得是异步版本               |

### 2.1 GIL：为什么 Python 多线程算不快

**GIL**（Global Interpreter Lock，全局解释器锁）：CPython 解释器里的一把锁，规定**同一时刻只有一条线程在执行 Python 字节码**。开 8 条线程做纯计算，它们轮流拿锁，总速度和 1 条线程差不多。

但线程在等 IO 时会**释放 GIL**。所以多线程对 IO 密集任务依然有效——这也是第 7 节里 `asyncio.to_thread` 能把同步的网络调用塞进线程、不拖慢事件循环的原因。

### 2.2 异步和多线程的核心区别：谁决定在哪切换

多线程：操作系统随时可能把你的线程暂停、切到另一条。两条线程同时改一个字典，改到一半被切走，数据就乱了。所以要加锁。

异步：切换只发生在 `await` 这个你亲手写下的位置。两个 `await` 之间的代码**绝对不会被打断**。这叫**协作式调度**（cooperative scheduling）——每个任务自觉让出，而不是被抢走。

```python
# 异步里这段代码是安全的，中间没有 await，不会被切走
counter["n"] += 1
counter["log"].append("加了一")
```

同样两行放在多线程里就有风险。这是异步比多线程好写的根本原因。

---

## 3. 协程：可以暂停的函数

### 3.1 `async def` 定义的是协程函数

```python
async def greet(name: str) -> str:
  return f"你好，{name}"
```

`async def` 定义出来的叫**协程函数**（coroutine function）。它和普通函数最大的区别：**调用它不会执行函数体**，只会返回一个**协程对象**（coroutine object）。

```python
>>> c = greet("小明")
>>> c
<coroutine object greet at 0x...>
>>> type(c)
<class 'coroutine'>
```

函数体一行都没跑。`c` 是一张「待办卡片」，上面写着「以后要执行 greet('小明')」。

类比：普通函数像按下电饭锅的开关，立刻开始煮。协程函数像写一张「煮饭」的便签，便签本身不会煮饭，要交给某个人（事件循环）去执行。

### 3.2 `await`：执行一个协程并等它的结果

```python
async def main():
  result = await greet("小明")
  print(result)
```

`await greet("小明")` 做了三件事：真正开始执行 `greet` 的函数体；如果它中途需要等待，就让开；拿到返回值赋给 `result`。

`await` 后面能跟的东西叫**可等待对象**（awaitable），一共三种：

| 可等待对象 | 是什么                                      | 来自哪                     |
| ---------- | ------------------------------------------- | -------------------------- |
| 协程对象   | 一张待办卡片                                | 调用 `async def` 函数      |
| Task       | 已经交给事件循环、正在排队或运行的协程      | `asyncio.create_task(...)` |
| Future     | 一个「以后会有值」的占位符，Task 是它的子类 | 底层库，日常很少直接碰     |

### 3.3 `await` 只能写在 `async def` 里

```python
def main():
  result = await greet("小明")     # SyntaxError: 'await' outside async function
```

普通函数没有「暂停再恢复」的能力，所以不允许 `await`。这条规则会向上传染：一个函数要 `await`，它自己必须是 `async def`；调用它的人要拿它的结果，也得 `await`，于是也必须是 `async def`……一直传到最顶层。

### 3.4 `asyncio.run`：顶层的那个入口

传染链总要有个尽头。最顶层用 `asyncio.run(协程对象)`：

```python
import asyncio

async def main():
  print(await greet("小明"))

asyncio.run(main())
```

`asyncio.run` 做的事：创建一个事件循环（第 4 节），把 `main()` 这张卡片交给它执行，等它跑完，关掉事件循环。**一个程序通常只调用一次**，放在 `if __name__ == "__main__":` 下面。

你 `async_llm.py` 最后一行就是它：

```python
if __name__ == "__main__":
  asyncio.run(main())
```

### 3.5 最常见的新手错误：忘了 `await`

```python
async def main():
  greet("小明")           # 忘了 await
  print("结束")

asyncio.run(main())
```

```text
结束
RuntimeWarning: coroutine 'greet' was never awaited
```

`greet("小明")` 创建了卡片，没人执行它，程序结束时 Python 发出警告。看到 `was never awaited` 就去找哪一行调了协程函数却没加 `await`。

---

## 4. 事件循环：那个唯一的服务员

### 4.1 它是什么

**事件循环**（event loop）是一个一直在转的 `while` 循环，手里拿着一份任务清单。它每一圈做的事：

1. 看清单里哪些任务**可以继续跑**（等的东西已经好了，或者刚被创建）。
2. 挑一个，跑到它下一个 `await` 处停下。
3. 如果这个 `await` 等的东西还没好，就把它放回清单，标记「在等 X」。
4. 顺便检查有没有网络回包、定时器到期，把对应任务标记成「可以继续」。
5. 回到第 1 步。

```text
事件循环的一圈：

   ┌────────────────────────────────────────────┐
   │  清单：[A 在等网络, B 可运行, C 在等 1 秒]    │
   │                                            │
   │  → 跑 B，直到它 await 某个东西              │
   │  → B 变成「在等」，放回清单                  │
   │  → 检查：A 等的网络回包到了！标记 A 可运行     │
   │  → 检查：C 的 1 秒还没到                     │
   └──────────────────┬─────────────────────────┘
                      │ 下一圈
                      ▼
```

你永远只有这一个服务员。他跑得飞快，但一次只能做一件事。

### 4.2 用时间线看第 1 节那三个请求

```text
时间 →   0s                              1s
事件循环: 跑A到await → 跑B到await → 跑C到await → [空转等定时器] → A醒 → B醒 → C醒
          │           │           │                              │
A:        开始请求─────┼───────────┼──── 等 1 秒 ────────────────┤拿到结果
B:                    开始请求─────┼──── 等 1 秒 ────────────────────┤拿到结果
C:                                开始请求──── 等 1 秒 ──────────────────┤拿到结果
```

三段「等 1 秒」在时间轴上重叠。事件循环在它们等待期间只是空转（真实场景下会去处理别的请求）。

### 4.3 阻塞：唯一会毁掉一切的东西

**阻塞**（blocking）：一个调用发出去之后，在它返回之前，当前线程什么也做不了。`time.sleep`、`requests.get`、`open().read()`、`input()`，以及你 week4 `agent` 里用的 OpenAI 同步 SDK `client.chat.completions.create`，都是阻塞调用。

把 1.2 的 `await asyncio.sleep(1)` 换成 `time.sleep(1)`：

```python
async def fetch(name: str) -> str:
  print(f"{name} 开始请求")
  time.sleep(1)                 # 阻塞！没有让开
  print(f"{name} 拿到结果")
  return f"{name} 的数据"
```

```text
A 开始请求
A 拿到结果
B 开始请求
B 拿到结果
C 开始请求
C 拿到结果
总耗时 3.0s
```

又回到 3 秒了。`time.sleep` 不认识事件循环，它直接让整条线程睡着，事件循环也跟着睡。B 和 C 连「开始」的机会都没有。

更糟的是在 Web 服务里：你的 FastAPI 路由里一个 `time.sleep(10)`，这 10 秒内**所有用户的所有请求**都排队。这就是 week3 博客里说的「异步客户端的生命周期」问题的根源，也是 week4 收尾时必须把 `run_loop` 丢进线程的原因。

规则：**`async def` 里面只能出现两种东西——不耗时的纯计算，和带 `await` 的异步调用。** 一个阻塞调用都不能有。

---

## 5. 并发运行多个协程

### 5.1 顺序 `await` 不是并发

```python
async def main():
  a = await fetch("A")    # 等 A 完全结束
  b = await fetch("B")    # 才开始 B
  c = await fetch("C")
```

这段代码是异步语法，但三个请求依然串行，3 秒。`await` 的意思是「等这一个好了再往下走」。要让它们重叠，必须**先把三个都启动，再一起等**。

### 5.2 `asyncio.gather`：一起启动，一起等

```python
results = await asyncio.gather(fetch("A"), fetch("B"), fetch("C"))
```

`gather` 接收任意多个可等待对象，把它们**全部**交给事件循环，然后等**全部**完成，返回一个列表。**列表顺序和你传入的顺序一致**，和谁先完成无关。

`async_llm.py` 里是这么用的：

```python
tasks = [ask_llm(client, p) for p in prompts]   # 一列协程对象，还没执行
results = await asyncio.gather(*tasks)          # 全部启动，一起等
```

`*tasks` 是把列表拆开当作多个参数传进去。`gather(*[a, b, c])` 等于 `gather(a, b, c)`。

**`return_exceptions` 参数**：默认情况下，任何一个协程抛异常，`gather` 立刻把这个异常抛给你，其他协程的结果拿不到。加上 `return_exceptions=True`，异常会被当作**返回值**放进列表对应位置：

```python
results = await asyncio.gather(
  fetch("A"), fetch_that_fails("B"), fetch("C"),
  return_exceptions=True,
)
# results == ['A 的数据', ValueError('B 失败'), 'C 的数据']
for r in results:
  if isinstance(r, Exception):
    print("失败：", r)
```

week4 讲义里「并行执行同一层步骤，一个失败不能带走其他结果」就是靠它。

### 5.3 `asyncio.create_task`：启动但先不等

有时你想先启动一个任务，自己接着干别的，稍后再要结果：

```python
async def main():
  task_a = asyncio.create_task(fetch("A"))    # 立刻交给事件循环，开始排队
  task_b = asyncio.create_task(fetch("B"))

  print("两个任务已经在跑了，我先做点别的")
  await asyncio.sleep(0.5)
  print("别的事做完了，现在要结果")

  a = await task_a      # 如果 A 已经完成，这里立刻返回
  b = await task_b
```

`create_task` 把协程对象包成一个 **Task**，并**立刻**排进事件循环。这是「启动」和「等待」分离的方式。`gather` 内部就是对每个参数做了 `create_task`。

一个必须记住的坑：**要保存 Task 的引用**。如果写成 `asyncio.create_task(fetch("A"))` 却不赋给变量，Python 可能在它跑完之前把它当垃圾回收掉。把它存进变量、列表或集合里。

### 5.4 `asyncio.TaskGroup`：结构化并发（3.11+）

`gather` 的问题：如果 B 抛了异常，A 和 C 还在后台跑，没人管。`TaskGroup` 的规则是**一个失败，全组取消，然后一起报错**：

```python
async def main():
  async with asyncio.TaskGroup() as tg:
    task_a = tg.create_task(fetch("A"))
    task_b = tg.create_task(fetch("B"))
    task_c = tg.create_task(fetch("C"))
  # 走出 async with 时，三个任务要么全部完成，要么因为某个失败而全部被取消
  print(task_a.result(), task_b.result(), task_c.result())
```

如果有任务抛异常，`async with` 结束时抛出一个 **`ExceptionGroup`**（异常组，一个能装多个异常的容器），用 `except*` 来拆：

```python
try:
  async with asyncio.TaskGroup() as tg:
    ...
except* ValueError as eg:
  for e in eg.exceptions:
    print("有任务抛了 ValueError：", e)
```

新代码优先用 `TaskGroup`，它不会留下没人管的后台任务。`gather(..., return_exceptions=True)` 适合「我就是要收集每个结果，包括失败的」这种场景。

### 5.5 `asyncio.as_completed`：谁先好先处理谁

```python
async def main():
  coros = [fetch("A"), fetch("B"), fetch("C")]
  for finished in asyncio.as_completed(coros):
    result = await finished
    print("先完成的：", result)
```

`gather` 要等全部完成才返回，`as_completed` 则每完成一个就交给你一个。适合「搜索三个数据源，谁先回来先展示」。

### 5.6 超时：`asyncio.timeout` 与 `wait_for`

```python
async def main():
  try:
    async with asyncio.timeout(2):          # 3.11+
      result = await fetch_slow("A")        # 如果超过 2 秒
  except TimeoutError:
    print("超时了")
```

超时发生时，`fetch_slow` 会被**取消**（第 8 节），然后抛 `TimeoutError`。旧写法 `await asyncio.wait_for(fetch_slow("A"), timeout=2)` 效果相同。

---

## 6. `async with`、`async for` 与异步生成器

### 6.1 普通 `with` 在做什么

```python
with open("a.txt") as f:
  data = f.read()
```

`with` 保证：进入时执行**准备工作**（打开文件），离开时**无论是否出错**都执行**清理工作**（关闭文件）。背后是两个方法：`__enter__`（进入时调）和 `__exit__`（离开时调）。实现了这两个方法的对象叫**上下文管理器**（context manager）。

### 6.2 `async with`：准备和清理本身需要等待

打开一个网络连接池、建立数据库连接，这些准备工作本身就是 IO，要 `await`。普通 `with` 的 `__enter__` 里不能 `await`，于是有了 `async with`，背后是 `__aenter__` 和 `__aexit__`，两个都可以是协程。

```python
async with httpx.AsyncClient() as client:
  r = await client.get(url)
# 离开时 await client.aclose()，关闭所有连接
```

`async_llm.py` 和 `ai_service/app/main.py` 的 `lifespan` 都是这个用法。`lifespan` 那段更进一步：`yield` 之前是服务启动时的准备（建一个全应用共用的 `AsyncClient`），`yield` 之后是服务关闭时的清理。

### 6.3 `async for`：每取一个元素都要等

普通 `for` 背后是 `__iter__` 和 `__next__`，`__next__` 每次返回下一个元素。如果「取下一个」本身要等网络（比如从流式响应里读下一行），就需要 `async for`，背后是 `__aiter__` 和 `__anext__`。

```python
async for line in response.aiter_lines():
  print(line)
```

`deepseek.py` 的 `stream_llm` 就是这样读 SSE 流的：每来一行就处理一行，不用等整个响应结束。

### 6.4 异步生成器：你自己写一个 `async for` 的数据源

普通生成器：函数体里有 `yield`，每 `yield` 一次吐出一个值，调用方 `for` 一次取一个。

```python
def countdown(n):
  while n > 0:
    yield n
    n -= 1

for x in countdown(3):
  print(x)        # 3 2 1
```

**异步生成器**（async generator）：`async def` 里有 `yield`。吐值之前可以 `await`：

```python
async def ticker(n: int):
  for i in range(n):
    await asyncio.sleep(1)      # 每秒产出一个
    yield i

async def main():
  async for i in ticker(3):
    print(i)                    # 每隔 1 秒打印 0 1 2
```

`deepseek.py` 的 `stream_llm` 就是一个异步生成器：

```python
async def stream_llm(...):
  async with client.stream("POST", url=DEEPSEEK_URL, json=payload) as response:
    async for line in response.aiter_lines():
      ...
      if content:
        yield content         # 每解析出一段文字就吐出去
```

`chat_service.py` 的 `chat_completions_stream` 也是，它 `async for` 消费上面这个，再 `yield` 出 SSE 格式的字符串。FastAPI 的 `StreamingResponse` 再 `async for` 消费它，每拿到一段就写进 HTTP 响应。三层异步生成器串起来，数据像水管一样流过去。

### 6.5 异步生成器最隐蔽的坑：调用时不执行

和协程函数一样，**调用异步生成器函数不会执行任何函数体**，只是返回一个生成器对象。函数体要等到第一次 `async for` 取值时才开始跑。

week3 博客里的「坑二」就是这个：

```python
async def chat_completions_stream(body, user, client):
  _prepare_chat(body, user)      # 你以为在路由函数里执行
  async for piece in ...:
    yield ...
```

路由函数里写 `StreamingResponse(chat_completions_stream(...))` 时，`_prepare_chat` **还没有执行**。它要等 `StreamingResponse` 开始消费这个生成器——而那时 HTTP 200 响应头已经发出去了，再抛额度不足的异常也改不了状态码。所以**所有校验必须在生成器外面、创建 `StreamingResponse` 之前做完**。

---

## 7. 跨越边界：同步代码与异步世界

现实中你总会遇到只有同步版本的库：OpenAI 官方 SDK 的同步客户端、很多数据库驱动、`time.sleep`、读大文件。第 4 节说过，这些东西直接放进 `async def` 会卡住事件循环。解法是把它们丢到**另一条线程**里跑。

### 7.1 `asyncio.to_thread`：把阻塞调用丢进线程

```python
import asyncio
import time

def blocking_work(name: str) -> str:
  time.sleep(2)                 # 同步阻塞，没法改
  return f"{name} 完成"

async def main():
  start = time.perf_counter()
  results = await asyncio.gather(
    asyncio.to_thread(blocking_work, "A"),
    asyncio.to_thread(blocking_work, "B"),
    asyncio.to_thread(blocking_work, "C"),
  )
  print(results, f"{time.perf_counter() - start:.1f}s")    # 2.0s，不是 6.0s

asyncio.run(main())
```

`asyncio.to_thread(func, *args)` 把 `func(*args)` 交给一个**线程池**（thread pool，一组预先创建好、可以反复使用的线程）里的线程去跑，然后返回一个可等待对象。事件循环在 `await` 它时让开，线程在后台阻塞，互不影响。三个阻塞调用在三条线程里同时睡 2 秒，总共 2 秒。

注意参数写法：`to_thread(blocking_work, "A")`，函数和参数分开传，**不要**写成 `to_thread(blocking_work("A"))`——那样在当前线程就已经把它调用了。

week4 收尾的 `agent_service.py` 里：

```python
answer = await asyncio.to_thread(_run_sync, body, emit)
```

`_run_sync` 内部是整个 agent 循环，几十秒的同步 API 调用。丢进线程之后，这几十秒里事件循环照常服务其他用户。

### 7.2 线程里的代码想通知事件循环：`call_soon_threadsafe`

`to_thread` 解决了「事件循环等线程」的方向。反过来，**线程里的代码想把消息传回事件循环**怎么办？

直接碰 asyncio 的对象是不行的。`asyncio.Queue`、Task、Future 都**不是线程安全的**（thread-safe：多条线程同时操作它不会出错）。它们假设自己只被事件循环那一条线程使用。

正规途径是 `loop.call_soon_threadsafe(回调函数, *参数)`：

```python
import asyncio

async def main():
  loop = asyncio.get_running_loop()         # 拿到当前事件循环
  queue: asyncio.Queue[str] = asyncio.Queue()

  def from_thread(msg: str) -> None:
    # 这个函数会在工作线程里被调用
    loop.call_soon_threadsafe(queue.put_nowait, msg)   # 请事件循环代为执行 queue.put_nowait(msg)

  def worker():
    import time
    for i in range(3):
      time.sleep(1)
      from_thread(f"第 {i} 条")               # 线程 → 事件循环

  task = asyncio.create_task(asyncio.to_thread(worker))
  for _ in range(3):
    print(await queue.get())                  # 事件循环这边逐条收
  await task

asyncio.run(main())
```

`call_soon_threadsafe` 的意思是：「我在别的线程，请事件循环在它下一圈有空的时候，替我执行这个函数」。它是线程安全的，专门用来从外部线程唤醒事件循环。

`asyncio.get_running_loop()` 必须在 `async def` 里调用，拿到的是当前正在跑的那个循环。`from_thread` 作为闭包捕获了 `loop` 和 `queue`，线程里才能用到它们。

### 7.3 队列：生产者与消费者

**生产者/消费者**（producer/consumer）是异步编程里最常用的模式：一方不断产出数据放进队列，另一方不断从队列取出处理。两边不直接认识，通过队列解耦，速度可以不一致。

```python
import asyncio
import random

async def producer(queue: asyncio.Queue, n: int):
  for i in range(n):
    await asyncio.sleep(random.random())      # 模拟不规律的产出
    await queue.put(f"商品 {i}")
    print(f"生产了商品 {i}")
  await queue.put(None)                       # 哨兵：告诉消费者没有更多了

async def consumer(queue: asyncio.Queue):
  while (item := await queue.get()) is not None:
    print(f"    消费了 {item}")
  print("    消费者收工")

async def main():
  queue: asyncio.Queue[str | None] = asyncio.Queue()
  await asyncio.gather(producer(queue, 5), consumer(queue))

asyncio.run(main())
```

三个要点：

**`queue.get()` 是可等待的**。队列空时消费者在这里让开，不占 CPU；生产者一 `put`，消费者就被唤醒。

**哨兵**（sentinel）：一个约定好的特殊值，表示「流结束了」。这里用 `None`。没有哨兵，消费者永远不知道该不该继续等，`while` 会卡在 `queue.get()` 上。哨兵必须**保证发出**——如果生产者可能抛异常，要把 `put(None)` 放在 `finally` 里。

**`:=` 海象运算符**：在表达式中赋值并返回这个值。`while (item := await queue.get()) is not None` 等于三行：取一个、赋给 `item`、判断是不是哨兵。

### 7.4 把三件事拼起来：SSE 推送的完整结构

week4 收尾那段 `agent_run_stream` 就是 7.1 + 7.2 + 7.3 的组合。拆开看它的骨架：

```python
async def agent_run_stream(body) -> AsyncIterator[str]:
  loop = asyncio.get_running_loop()
  queue: asyncio.Queue[dict | None] = asyncio.Queue()

  def emit(event: dict | None) -> None:
    loop.call_soon_threadsafe(queue.put_nowait, event)     # 7.2：线程 → 事件循环

  async def producer() -> None:
    try:
      answer = await asyncio.to_thread(_run_sync, body, emit)   # 7.1：同步 agent 丢进线程
      emit({"event": "done", "data": {"answer": answer}})
    except Exception as e:
      emit({"event": "error", "data": {"message": str(e)}})
    finally:
      emit(None)                                            # 7.3：哨兵必须发出

  task = asyncio.create_task(producer())                    # 5.3：启动但不等
  try:
    while (item := await queue.get()) is not None:          # 7.3：消费者
      yield _frame(item["event"], item["data"])             # 6.4：异步生成器
  finally:
    task.cancel()                                           # 8：客户端断开时清理
```

| 角色                      | 在哪条线程       | 做什么                                       |
| ------------------------- | ---------------- | -------------------------------------------- |
| `_run_sync`（agent 循环） | 工作线程         | 阻塞地调 API，每步调一次 `emit`              |
| `emit`                    | 工作线程里被调用 | 用 `call_soon_threadsafe` 把事件扔给事件循环 |
| `producer`                | 事件循环         | 等线程跑完，补上 `done` 帧和哨兵             |
| 生成器本体                | 事件循环         | 从队列取事件，变成 SSE 帧 `yield` 出去       |
| `StreamingResponse`       | 事件循环         | `async for` 这个生成器，每帧写进 HTTP 响应   |

这是异步编程里一个完整的、生产可用的模式。读懂它，这一讲的主要内容就都用上了。

### 7.5 `run_in_executor`：`to_thread` 的底层

`asyncio.to_thread` 是 3.9 加的便捷写法，底层是：

```python
loop = asyncio.get_running_loop()
result = await loop.run_in_executor(None, blocking_work, "A")
```

第一个参数 `None` 表示用默认线程池。如果想用**进程池**跑 CPU 密集任务（绕过 GIL），换成 `concurrent.futures.ProcessPoolExecutor()`。日常用 `to_thread` 就够了，知道它的底下是这个即可。

---

## 8. 取消与清理

### 8.1 取消是怎么发生的

```python
async def long_job():
  try:
    print("开始")
    await asyncio.sleep(10)
    print("完成")              # 不会打印
  except asyncio.CancelledError:
    print("被取消了，做清理")
    raise                      # 重要：清理完要重新抛出
  finally:
    print("finally 总会执行")

async def main():
  task = asyncio.create_task(long_job())
  await asyncio.sleep(1)
  task.cancel()
  try:
    await task
  except asyncio.CancelledError:
    print("main 确认任务已取消")

asyncio.run(main())
```

```text
开始
被取消了，做清理
finally 总会执行
main 确认任务已取消
```

`task.cancel()` 不是立刻杀掉任务，而是在任务**下一次回到 `await` 处**时，往那里**注入**一个 `CancelledError` 异常。任务从 `await asyncio.sleep(10)` 那行醒来，发现是个异常，正常走 `except` / `finally`。

### 8.2 捕获了 `CancelledError` 必须重新抛出

```python
except asyncio.CancelledError:
  print("清理")
  # 忘了 raise
```

这样写等于「吞掉」了取消信号，任务会继续往下跑，调用方以为它已经停了。规则：**可以捕获 `CancelledError` 做清理，但清理完必须 `raise`**。

更常见的写法是不捕获，只用 `finally`：

```python
async def long_job():
  conn = await open_connection()
  try:
    await do_work(conn)
  finally:
    await conn.close()        # 被取消时也会执行到
```

### 8.3 `asyncio.shield`：保护一段不被取消

```python
await asyncio.shield(save_to_database(data))
```

外面的任务被取消时，`shield` 里面的协程会继续跑完。用在「这步必须完成，否则数据不一致」的地方，比如已经开始的扣费写入。

### 8.4 线程无法被取消

这是 `to_thread` 的根本局限。`task.cancel()` 能取消等待线程的那个 Task，但**正在线程里跑的同步函数不会停**——Python 没有从外部终止一条线程的手段。它会一直跑到自己结束，结果没人要，白白浪费。

week4 收尾那段 `finally: task.cancel()` 就只能做到这一步：客户端断开后，SSE 生成器停止，但线程里的 agent 循环会继续调 API 直到自然结束。

正规修法是**协作式取消**：传一个 `threading.Event` 进去，同步代码每轮循环开头检查它：

```python
import threading

def run_loop(messages, *, cancel: threading.Event | None = None, ...):
  for step in range(1, max_steps + 1):
    if cancel is not None and cancel.is_set():
      return LoopResult(answer="已取消", stop_reason="cancelled", ...)
    ...

# 事件循环这边
cancel = threading.Event()
task = asyncio.create_task(asyncio.to_thread(run_loop, messages, cancel=cancel))
...
cancel.set()      # 请线程在下一轮自己停下
```

和异步的 `await` 让出一样，这也是「自觉配合」而不是「被强制」。

---

## 9. 同步原语：当多个任务要共享东西

异步里两个 `await` 之间不会被打断，但**跨 `await` 的多步操作**依然可能交错：

```python
async def transfer(balance: dict, amount: int):
  current = balance["n"]          # 读
  await asyncio.sleep(0)          # 这里会让开！
  balance["n"] = current - amount # 写——基于可能已经过时的 current
```

两个 `transfer` 并发，都读到 100，都写回 100 - 10 = 90，实际应该是 80。要让「读 - 等 - 写」成为一个整体，用锁。

### 9.1 `asyncio.Lock`：同一时刻只能有一个任务进入

```python
lock = asyncio.Lock()

async def transfer(balance: dict, amount: int):
  async with lock:                # 拿不到锁就在这里等
    current = balance["n"]
    await asyncio.sleep(0)
    balance["n"] = current - amount
```

`async with lock` 进入时等待拿锁，离开时自动释放。week3 博客结尾提到的「额度扣减不是原子的（TOCTOU）」就是这类问题，`Lock` 是单进程内的解法。

### 9.2 `asyncio.Semaphore`：最多同时 N 个

**信号量**（semaphore）是「有 N 个名额的锁」。最常见用途是**限流**：你有 100 个请求要发给 LLM API，但对方限制同时 5 个连接。

```python
sem = asyncio.Semaphore(5)

async def limited_fetch(client, url):
  async with sem:                 # 最多 5 个任务同时在这里面
    return await client.get(url)

results = await asyncio.gather(*(limited_fetch(client, u) for u in urls))
```

100 个协程全部启动，但任何时刻只有 5 个真正在发请求，其余在 `async with sem` 处排队。

### 9.3 `asyncio.Event`：等一个信号

```python
ready = asyncio.Event()

async def waiter():
  await ready.wait()              # 一直等，直到有人 set
  print("收到信号，开始干活")

async def setter():
  await asyncio.sleep(2)
  ready.set()                     # 所有在 wait 的任务同时被唤醒
```

用于「等某个初始化完成再开始」之类的场景。

---

## 10. 揭开盖子：协程本质上是生成器

这一节不影响使用，但能让前面所有「让开」「回来」变得具体。

Python 的生成器天然就能「暂停在 `yield` 处，稍后从那里继续」：

```python
def worker(name):
  print(f"{name} 第一步")
  yield                           # 暂停，交出控制权
  print(f"{name} 第二步")
  yield
  print(f"{name} 第三步")

# 一个最简陋的「事件循环」：轮流推进每个生成器
tasks = [worker("A"), worker("B")]
while tasks:
  for t in list(tasks):
    try:
      next(t)                     # 推进到下一个 yield
    except StopIteration:
      tasks.remove(t)             # 跑完了，移出清单
```

```text
A 第一步
B 第一步
A 第二步
B 第二步
A 第三步
B 第三步
```

两个函数**交替**执行，但全程只有一条线程、没有操作系统参与。`yield` 就是「让开」，`next()` 就是「回来」。`asyncio` 的协程在底层就是这个机制的加强版：`await` 对应 `yield`，事件循环对应这个 `while` + `for`，再加上「等的东西好了才推进」的判断。

理解了这一点，第 4 节的「一个阻塞调用卡住所有人」就不需要死记了：`time.sleep` 卡在 `next(t)` 里面不返回，`for` 循环自然轮不到下一个。

---

## 11. 常见错误（Code Review 必抓）

1. **忘了 `await`**。协程对象被创建但从不执行，程序结束时报 `was never awaited`。
2. **`async def` 里用阻塞调用**。`time.sleep`、`requests.get`、同步数据库驱动、同步 SDK。表现是「明明用了异步，怎么还是串行」或「一个慢请求拖死整个服务」。
3. **顺序 `await` 当并发**。`a = await f(); b = await g()` 是串行。要并发必须 `gather` / `TaskGroup` / `create_task`。
4. **`create_task` 不保存引用**。任务可能被垃圾回收。
5. **`gather` 忘了 `return_exceptions=True`**（当你需要收集全部结果时）。一个失败带走全部。
6. **在线程里直接操作 `asyncio.Queue` / Task**。要用 `call_soon_threadsafe`。
7. **生产者可能异常，但哨兵不在 `finally` 里**。消费者永远等下去。
8. **捕获 `CancelledError` 后不重新抛出**。取消信号被吞，任务「假死不停」。
9. **把校验写在异步生成器里面**。生成器函数被调用时不执行函数体，校验要等到开始消费才跑，那时响应头已经发出。
10. **每个请求新建一个 `AsyncClient`**。连接池的意义全没了，还多了建连开销。全应用建一次，放进 `lifespan`。
11. **`to_thread(func(arg))`**。括号写错位置，函数在当前线程就被调用了。正确是 `to_thread(func, arg)`。
12. **以为 `task.cancel()` 能停掉线程里的代码**。只能停等待它的 Task，线程内的同步函数要靠协作式取消。

---

## 12. 调试

**打开 debug 模式**：`asyncio.run(main(), debug=True)` 或环境变量 `PYTHONASYNCIODEBUG=1`。它会在一个任务**连续运行超过 100 毫秒不让出**时打印警告，这是找阻塞调用最快的办法。

**`was never awaited`**：去找哪个 `async def` 函数被调用了却没加 `await`。

**程序挂着不结束**：多半是消费者在 `queue.get()` 上等一个永远不会来的哨兵，或者某个 `await` 等的事件永远不会被 `set`。

**看当前有哪些任务**：`asyncio.all_tasks()` 返回一个集合，打印出来能看到谁还在跑。

---

## 13. 和项目代码的对应

| 项目代码                                            | 用到的概念                                                                  | 对应章节      |
| --------------------------------------------------- | --------------------------------------------------------------------------- | ------------- |
| `async_llm.py` 的 `ask_many`                        | `gather` 并发三个请求、`async with AsyncClient`                             | 5.2、6.2      |
| `ai_service/app/main.py` 的 `lifespan`              | 异步上下文管理器 + `yield` 分隔启动与关闭、全应用一个 `AsyncClient`         | 6.2、11 条 10 |
| `deepseek.py` 的 `stream_llm`                       | `async with client.stream`、`async for aiter_lines`、异步生成器 `yield`     | 6.3、6.4      |
| `chat_service.py` 的 `chat_completions_stream`      | 异步生成器套异步生成器；校验位置的坑                                        | 6.4、6.5      |
| week4 `executor.py` 的 `execute_plan_parallel`      | `gather(*(to_thread(...)))` + `return_exceptions=True`                      | 5.2、7.1      |
| week4 收尾 `agent_service.py` 的 `agent_run_stream` | `to_thread`、`call_soon_threadsafe`、`Queue`、哨兵、`create_task`、`cancel` | 7.4 整节      |

---

## 14. 动手练习

按顺序做，每关都要能跑。

**第 1 关：看见重叠**。把 1.1 和 1.2 各跑一遍，然后把 1.2 的 `asyncio.sleep` 换成 `time.sleep`，确认总耗时退回 3 秒。

**第 2 关：顺序 vs 并发**。写三个 `fetch`，分别用「顺序 `await`」「`gather`」「`create_task` 后再 `await`」三种方式调用，打印三种方式的耗时。

**第 3 关：收集失败**。让其中一个 `fetch` 抛异常，分别用 `gather`（不带参数）、`gather(return_exceptions=True)`、`TaskGroup` 跑，观察三种行为的区别。

**第 4 关：限流**。写一个 `Semaphore(2)`，启动 6 个每个睡 1 秒的任务，确认总耗时是 3 秒而不是 1 秒。

**第 5 关：生产者消费者**。照 7.3 写一遍，然后让生产者在第 3 个商品时抛异常，确认消费者还能正常收工（提示：哨兵放 `finally`）。

**第 6 关：跨线程**。照 7.2 写一遍。然后故意把 `call_soon_threadsafe` 换成直接 `queue.put_nowait`，多跑几次看会不会出错或丢消息（它可能偶尔正常，这正是线程不安全的特征）。

**第 7 关：取消**。照 8.1 写一遍。然后故意吞掉 `CancelledError` 不 `raise`，观察任务是否还在继续跑。

**第 8 关（综合）**：把你 week4 的 `run_loop` 用 7.4 的结构包成一个异步生成器，每步 `yield` 一个字典，用 `async for` 在终端逐步打印。这就是 SSE 接口的核心，接上 FastAPI 只差一层 `StreamingResponse`。

---

## 15. 速查表

| 概念                           | 一句话                                                                 |
| ------------------------------ | ---------------------------------------------------------------------- |
| 异步省什么                     | IO 等待时间，不是计算时间                                              |
| 事件循环                       | 一条线程上的任务调度器，轮流推进每个协程到下一个 `await`               |
| `async def`                    | 定义协程函数，调用它只得到卡片，不执行                                 |
| `await`                        | 执行并等待一个可等待对象，等待期间让出控制权                           |
| `asyncio.run`                  | 程序顶层唯一入口，创建并运行事件循环                                   |
| 阻塞                           | 不让出控制权的等待，会卡住整个事件循环                                 |
| `gather`                       | 一起启动一起等，结果按传入顺序，`return_exceptions=True` 收集失败      |
| `create_task`                  | 启动但不等，记得保存引用                                               |
| `TaskGroup`                    | 一个失败全组取消，新代码优先                                           |
| `async with`                   | 准备/清理本身要 `await` 的上下文管理器                                 |
| `async for`                    | 取每个元素都要 `await` 的迭代                                          |
| 异步生成器                     | `async def` + `yield`，调用时不执行                                    |
| `to_thread`                    | 阻塞函数丢进线程池，`to_thread(func, arg)` 不是 `to_thread(func(arg))` |
| `call_soon_threadsafe`         | 从别的线程唤醒事件循环的唯一正规途径                                   |
| `asyncio.Queue`                | 协程间传数据，不是线程安全的                                           |
| 哨兵                           | 约定的结束标记，必须保证发出（`finally`）                              |
| `cancel()`                     | 在下一个 `await` 处注入 `CancelledError`，清理后要 `raise`             |
| 线程取消                       | 做不到，只能协作式（`threading.Event` + 每轮检查）                     |
| `Lock` / `Semaphore` / `Event` | 互斥 / 限流 / 等信号                                                   |
| 调试                           | `debug=True` 抓超过 100ms 不让出的任务                                 |

---

_相关讲义：`fastapi.md` 第 7 节（异步路由）、`fastapi_faq.md` 第 11 节（`async with`）_
_相关博客：`week3_blog.md` 第三节（为什么 LLM 网关必须用 async）、第五节（流式输出的两个坑）_
