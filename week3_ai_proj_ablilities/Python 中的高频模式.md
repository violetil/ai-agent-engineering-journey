# 第二阶段：语法之上的高频模式（细讲版）

## 模式 1：字典和列表的「安全访问」

### 1.1 `dict["key"]` vs `dict.get("key", default)`

``` python
# 方式 A：直接取键 —— 键不存在会崩溃
city = fake_weather_data["北京"] # KeyError 如果 "北京" 不存在

# 方式 B：安全取键 —— 不存在返回默认值
city = fake_weather_data.get("北京", "未知天气")
```


为什么不用 `if city in dict`？ 可以，但 `.get` 一行搞定，是 Python 惯用法。

### 1.2 嵌套字典：一层一层剥

LLM API 的返回值几乎都是「字典套字典套列表」：

```python
response.choices[0].message.content
```

翻译步骤（从外到内）：

```
response          → API 返回的整个对象
.choices          → 候选回复列表（通常只要第 0 个）
[0]               → 取第一个候选
.message          → 消息对象
.content          → 真正的文本字符串
```

记忆口诀： `.` 是「往里拿属性」，`[0]` 是「从列表里拿第几个」。

### 1.3 访问 message 里的字段

OpenAI 格式的 message 是固定结构：

```json
{
	"role": "user", # 或 "assistant" / "system" / "tool"
	"content": "你好"
}
```

读循环时：

```python
for msg in messages:
	total += len(encoding.encode(msg["content"]))
	#                            ↑ 每个 msg 是 dict，用 ["content"] 取文本
```

---

## 模式 2：列表的两种「加东西」—— `append` vs `extend`

```python
messages = [{"role": "system", "content": "你是助手"}]

# append：把整个对象当作「一个元素」追加
messages.append({"role": "user", "content": "hi"})
# 结果长度 +1

# extend：把另一个列表里的元素「逐个」并入
messages.extend([
	{"role": "user", "content": "hello"},
	{"role": "assistant", "content": "world"}
])
# 结果长度 +2（不是 +1！）
```


怎么读：

- `append(一个东西)` → 列表末尾加 1 项
- `extend(一个列表)` → 把列表 展开 后全部加进去

常见坑： 想合并两个列表却写了 `append`，结果变成「列表里套了一个列表」。

---

## 模式 3：字符串模板 —— f-string 与三引号

### 3.1 f-string：`f"..."`

```python
print(f"\n当前 token：{token_count}")
f.write(f"🔬 **实验组: temperature = {temp} | top_p = {p}**\n\n")
```

**怎么读：** `f` 前缀 + 花括号 `{}` → 把变量插进字符串。
花括号里几乎可以是任意 Python 表达式：

```python
f"长期记忆：{load_memory()['long_term_memory']}" # 可以调函数
f"{2 + 3}" # 可以是表达式
```

### 3.2 三引号多行字符串

```python
prompt = f"""
你是 AI 记忆系统。

旧记忆：
{old_memory}

新对话：
{new_messages}
"""
```

**怎么读：** `"""..."""` 可以跨多行，适合写 prompt。前面的 `f` 表示里面 `{}` 仍会被替换。
和 `\n` 拼接的区别： 三引号写 prompt 更易读，这是 AI 项目里的标准做法。

---

## 模式 4：上下文管理器 —— `with open(...) as f`

```python
with open(MEMORY_FILE, "r", encoding="utf-8") as f:
	return json.load(f)
```

等价于「打开文件 → 用完 → **保证关闭**」，即使中间出错也会关。
**怎么读：**

```
with open(路径, 模式, encoding=...) as f:
	... 用 f 读或写 ...
# 出了 with 块，文件自动关
```

- `"r"` = read 读
- `"w"` = write 写（会覆盖原文件）
- `encoding="utf-8"` = 正确处理中文

---

## 模式 5：推导式 —— 一行生成新列表/字典

这是觉得别人代码「花样多」的头号来源。

### 5.1 列表推导式

**普通写法：**

```python
total = 0
for msg in messages:
	total += len(encoding.encode(msg["content"]))
```

**推导式写法：**

```python
token_counts = [len(encoding.encode(msg["content"])) for msg in messages]
total = sum(token_counts)
```

**结构拆解：**

```
[ 表达式(对每个元素算什么) for 变量 in 可迭代对象 ]
    ↑                         ↑          ↑
 len(...)                    msg       messages
```

**怎么读：** 从左到右 —— 「对每个 msg in messages，算一个 len(...)，收集成列表」。

### 5.2 带条件的推导式

```python
# 只保留 user 发的消息
user_messages = [msg for msg in messages if msg["role"] == "user"]
```

结构：`[表达式 for x in xs if 条件]`

### 5.3 字典推导式

```python
# 普通写法
result = {}
for city, weather in fake_weather_data.items():
	result[city] = weather.upper()

# 推导式
result = {city: weather.upper() for city, weather in fake_weather_data.items()}
```

**怎么读：** `{键: 值 for ...}` → 批量造字典。

### 5.4 你需要掌握到什么程度？

**读：** 必须能拆解结构，知道它在「过滤 / 转换 / 收集」  
**写：** 先写 for 循环，熟练后再改推导式  
**不要：** 为了炫技写嵌套三层推导式 —— 可读性会变差

---

## 模式 6：解包（Unpacking）

### 6.1 多重赋值

```python
function_name = tool_call.function.name
arguments = json.loads(tool_call.function.arguments)
```

也可以一行解包：

```python
name, args = tool_call.function.name, json.loads(tool_call.function.arguments)
```

### 6.2 遍历 dict 时解包

```python
for city, weather in fake_weather_data.items():
	print(city, weather)
```

`.items()` 返回 `(键, 值)` 对，for 循环自动拆成两个变量。

**怎么读：** `for a, b in xxx.items()` → 每次循环 a 是键，b 是值。

### 6.3 函数返回多个值

```python
def parse_tool_call(message):
	tc = message.tool_calls[0]
	return tc.function.name, json.loads(tc.function.arguments)

name, args = parse_tool_call(message) # 接收两个返回值
```

Python 函数「返回多个值」其实是返回一个 tuple，然后被解包。

---

## 模式 7：函数 —— 默认参数、类型注解、`*args` / `**kwargs`

### 7.1 默认参数

```python
def ask_llm(sys_prompt, user_prompt, temperature=0, output_type="text"):
```

**怎么读:** 后两个参数有 `=默认值`，调用时可省略：

```python
ask_llm("你是助手", "你好") # temperature=0, output_type="text"
ask_llm("你是助手", "你好", temperature=0.7) # 只改 temperature
```

**重要规则：** 默认参数必须放在没有默认值的参数后面。

### 7.2 类型注解（Type Hints）

```python
def count_tokens(messages: list[dict]) -> int:
	...
```

**怎么读：**

- `messages: list[dict]` → 期望 messages 是「字典的列表」
- `-> int` → 返回值是整数

注意： Python 不会因为类型不对就报错（除非你用 mypy 等工具检查）。注解主要是：

- 给人看
- 给 IDE 做自动补全

AI 工程里常见：

```python
def summarize_chat(old_memory: str, new_messages: list[dict]) -> str:
def get_weather(city: str) -> str:
```

### 7.3 `*args` 和 `**kwargs`（读库代码必备）

读第三方库时会大量见到：

```python
def wrapper(*args, **kwargs):
	print("位置参数:", args) # 打包成 tuple
	print("关键字参数:", kwargs) # 打包成 dict
```

**典型场景：** 包装函数，把参数原样传给另一个函数：

```python
def my_create(**kwargs):
	kwargs["model"] = "deepseek-chat" # 偷偷改一个参数
	return client.chat.completions.create(**kwargs)
	# **kwargs 把 dict 拆成关键字参数传进去
```

**怎么读：**

- `*args` → 「多出来的位置参数，全收进 tuple」
- `**kwargs` → 「多出来的关键字参数，全收进 dict」
- 调用时 `func(**d)` → 「把 dict 拆开当关键字参数传」

---

## 模式 8：异常处理 —— `try / except`

```python
try:
	response = client.chat.completions.create(...)
	answer = response.choices[0].message.content
	attack_logs.append({...})
except Exception as e:
	print(f"\n[错误] API 调用失败: {e}\n")
```

**怎么读：**

```
try:
	可能出错的代码（网络、API、文件、JSON 解析）
except Exception as e:
	出错后走这里，e 是错误信息
```

**为什么 AI 代码里常见：** API 调用会超时、限流、key 无效；JSON 可能格式不对。

**更精细的写法：**

```python
try:
	data = json.loads(raw)
except json.JSONDecodeError:
	print("不是合法 JSON")
```

只捕获特定错误，而不是笼统的 `Exception`。

---

## 模式 9：模块与 import —— 项目怎么拼起来

### 9.1 三种 import

```python
import json # 用 json.load(...)
from openai import OpenAI # 直接用 OpenAI(...)
from memory_manager import load_memory, save_memory # 直接用 load_memory(...)
```

**怎么读：**

- `import json` → 模块名作为前缀：`json.load`
- `from X import Y` → 只拿 Y，代码里直接写 `Y(...)`

### 9.2 你项目的模块关系

```
main.py
	├── memory_manager.py (load/save/add_message, 操作 memory.json)
	├── token_manager.py (count_tokens, 用 tiktoken)
	└── summarizer.py (summarize_chat, 调 LLM 做摘要)

llm.py (ask_llm, tool_call_llm, call_llm — 被 day2-day5 等脚本 import)

test_func_call.py
	└── from llm import tool_call_llm, call_llm
```

**读新项目的第一步：** 找 `main.py` 或 `app.py`（入口），顺着 import 往下看。

### 9.3 `if __name__ == "__main__":`

```python
def count_tokens(messages):
	...

if __name__ == "__main__":
	# 只有「直接运行这个文件」时才执行
	# 被 import 时不执行
	print(count_tokens([{"role":"user","content":"hi"}]))
```

**怎么读：** 文件既可以被 import 当模块，也可以直接 `py -3.14 token_manager.py` 做测试。

---

## 模式 10：JSON + 环境变量 + 配置（AI 项目三件套）

### 10.1 环境变量

```python
from dotenv import load_dotenv
import os

load_dotenv() # 读取 .env 文件到环境变量
api_key = os.getenv("DEEPSEEK_API_KEY") # 取名为 DEEPSEEK_API_KEY 的值
```

**为什么不用硬编码 key？** 安全；`.env` 不进 git。

**怎么读：** `load_dotenv()` → 启动时加载配置；`os.getenv("名字")` → 取配置值，没有则返回 `None`。

### 10.2 JSON 读写

```python
# Python 对象 → JSON 文件
json.dump(memory, f, ensure_ascii=False, indent=2)

# JSON 文件 → Python 对象
memory = json.load(f)

# JSON 字符串 → Python 对象（API 返回的 arguments 常是字符串）
arguments = json.loads(tool_call.function.arguments)
```

三个函数别混：

|函数|方向|场景|
|---|---|---|
|`json.dump(obj, f)`|Python → 写文件|保存 memory|
|`json.load(f)`|文件 → Python|读取 memory|
|`json.loads(s)`|字符串 → Python|解析 API 里的 JSON 字符串|
|`json.dumps(obj)`|Python → 字符串|调试打印|

`ensure_ascii=False`： 中文不被转成 `\u4e2d`  
`indent=2`： 保存时格式化，人类可读

### 10.3 用 dict 描述 API schema（tools 定义）

JSON Schema 嵌在 Python dict 里：

```python
tools = [
	{
		"type": "function",
		"function": {
			"name": "get_weather",
			"parameters": {
				"type": "object",
				"properties": {
					"city": {"type": "string", ...}
				},
				"required": ["city"]
			}
		}
	}
]
```

**怎么读：** 这就是「给模型看的说明书」，结构是 API 规范定的，不是 Python 特有语法。会读 nested dict 就够了。

---

## 模式 11：对象与第三方库 —— `.` 链式调用

```python
client = OpenAI(api_key=..., base_url=...)
response = client.chat.completions.create(model=..., messages=...)
```

**这不是 Python 语法，是库的 API 设计：**

```
client # OpenAI 客户端对象
	.chat # 聊天相关接口
	.completions # 补全/对话接口
	.create(...) # 发起一次请求，返回 response 对象
```

**读陌生库的方法：**

1. 看官方 Quickstart（3～5 行示例）
2. 把链式调用拆成「谁返回谁」
3. 打印 `type(x)` 和 `dir(x)` 看有哪些属性（调试时用）

同类还有：

```python
encoding = tiktoken.get_encoding("cl100k_base")
encoding.encode("hello") # tiktoken 库的对象方法
```

---

## 模式 12：控制流里的「早退」与「守卫」

### 12.1 `continue` — 跳过本轮

```python
if not user_input:
	print("\n输入为空，请重新输入。\n")
	continue # 不执行后面代码，回到 while 循环开头
```

### 12.2 布尔守卫

```python
if token_count > TOKNE_LIMIT:
	print("超过限制，开始摘要...")
	...
```

### 12.3 嵌套循环 + 标志变量

你 `app.py` 里用 `is_exit_triggered` 从内层循环「通知」外层退出 —— 这是控制流模式，不是新语法：

```python
is_exit_triggered = False
while True: # 内层：收多行输入
	if line == "exit" and not lines:
		is_exit_triggered = True
		break
if is_exit_triggered: # 外层：决定是否结束程序
	break
```

**怎么读：** 内层 `break` 只跳出内层 while；用布尔变量把「退出意图」传给外层。

---

## 一张「读码翻译表」—— 建议打印或做成 Anki

|看到什么|立刻翻译成|
|---|---|
|`x.get(k, d)`|安全取字典键，默认 d|
|`with open(...) as f:`|自动关文件|
|`f"..."` / `"""..."""`|字符串模板 / 多行文本|
|`.append(x)`|列表加 1 项|
|`.extend(xs)`|列表合并多项|
|`[f(x) for x in xs]`|对每个 x 算 f(x)，收集成列表|
|`[x for x in xs if cond]`|过滤后收集|
|`{k: v for ...}`|批量造字典|
|`for k, v in d.items()`|遍历键值对|
|`json.load/dump/loads/dumps`|JSON ↔ Python|
|`os.getenv("X")`|读环境变量|
|`a.b.c[d].e`|层层取属性/索引|
|`def f(x=0) -> int:`|默认参数 + 返回类型|
|`try/except`|出错走备用逻辑|
|`from m import f`|从模块 m 引入 f|
|`*args / **kwargs`|收可变参数 / 拆 dict 传参|