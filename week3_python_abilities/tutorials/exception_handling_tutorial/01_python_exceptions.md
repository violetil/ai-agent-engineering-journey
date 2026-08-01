# Python 异常与错误处理讲义(上):Python 异常机制

> 面向对象:已能写出可运行的 Python 程序,但对异常机制不熟悉、习惯用裸 `except:` 或返回 `None`/`bool` 表示失败的同学。
>
> 配套下篇:`02_http_error_handling.md`(HTTP 与 FastAPI 错误处理,结合你的 `ai_service` 项目)。

---

## 目录

1. [为什么要认真学异常](#1-为什么要认真学异常)
2. [异常是什么:从一条 Traceback 说起](#2-异常是什么从一条-traceback-说起)
3. [try / except / else / finally 完整语法](#3-try--except--else--finally-完整语法)
4. [异常的类型体系](#4-异常的类型体系)
5. [抛出异常:raise 与异常链](#5-抛出异常raise-与异常链)
6. [自定义异常类](#6-自定义异常类)
7. [异常处理的设计哲学](#7-异常处理的设计哲学)
8. [五个最常见的反模式(你的代码里有三个)](#8-五个最常见的反模式)
9. [异常与日志](#9-异常与日志)
10. [本篇小结与自查清单](#10-本篇小结与自查清单)

---

## 1. 为什么要认真学异常

程序运行时,"失败"是常态而非例外:文件不存在、网络超时、用户输入非法、上游 API 返回 429……语言必须提供一种机制来表达"这里出错了,我处理不了,交给调用者"。

Python 选择的机制是**异常(exception)**。它有三个关键性质:

1. **异常会沿调用栈向上传播**,直到被某一层 `except` 捕获,或者到达顶层导致程序终止并打印 traceback。这意味着"发现错误的地方"和"处理错误的地方"可以分离——底层函数只管 `raise`,由知道业务上下文的上层决定怎么办。
2. **异常携带类型和信息**。`FileNotFoundError` 和 `PermissionError` 都是"打不开文件",但类型不同,调用者可以区别对待。
3. **异常无法被无声忽略**(除非你显式地吞掉它)。这与 C 语言"返回错误码但调用者忘记检查"形成对比——你项目里 `add_user` 调了 `save_users`,而 `save_users` 失败时返回 `False`,这个返回值从没被检查过,注册可能静默失败。这正是"错误码风格"的经典事故,异常机制就是为了消灭它。

**一句话:异常处理不是"让程序不崩",而是"让失败以可控、可观测、可区分的方式呈现"。**

---

## 2. 异常是什么:从一条 Traceback 说起

先学会读报错,这是调试的第一技能。运行下面的代码:

```python
def get_price(data: dict) -> float:
    return data["price"]

def main():
    order = {"name": "book"}
    print(get_price(order))

main()
```

输出:

```text
Traceback (most recent call last):
  File "demo.py", line 8, in <module>
    main()
  File "demo.py", line 6, in main
    print(get_price(order))
  File "demo.py", line 2, in get_price
    return data["price"]
KeyError: 'price'
```

读法(记住这三条):

- **从下往上读**。最后一行 `KeyError: 'price'` 是异常类型和信息,这是"发生了什么"。
- 倒数第二行 `return data["price"]` 是**异常真正发生的位置**,这是"在哪发生"。
- 再往上是调用链:`main()` 调了 `get_price()`。这是"怎么走到这里的"。

Traceback 是你最好的朋友。后面讲到"裸 `except` 为什么是大忌"时你会看到:很多错误处理的坏习惯,本质上是**亲手销毁了 traceback**,把最有价值的调试信息丢掉了。

### 异常对象

异常本身是一个**对象**,是某个异常类的实例:

```python
try:
    int("abc")
except ValueError as e:
    print(type(e))    # <class 'ValueError'>
    print(e)          # invalid literal for int() with base 10: 'abc'
    print(e.args)     # ("invalid literal for int() with base 10: 'abc'",)
```

`as e` 把异常对象绑定到变量 `e`,你可以读取它携带的信息。注意:`e` 只在 `except` 块内有效,出了块就被删除(这是 Python 3 的刻意设计,避免循环引用)。

---

## 3. try / except / else / finally 完整语法

完整形态如下,四个部分各司其职:

```python
try:
    # ① 可能出错的代码 —— 尽量只包住真正可能出错的那几行
    f = open("config.json")
except FileNotFoundError:
    # ② 某种错误发生时的处理
    print("配置文件不存在,使用默认配置")
    config = {}
except (PermissionError, IsADirectoryError) as e:
    # ③ 可以有多个 except;用元组一次捕获多种类型
    print(f"无法读取配置:{e}")
    raise            # 处理不了,重新抛出
else:
    # ④ 只有 try 块【没有】抛异常时才执行
    config = json.load(f)
    f.close()
finally:
    # ⑤ 无论是否出错【都】执行,用于清理资源
    print("配置加载流程结束")
```

逐条说明:

### 3.1 except 的匹配规则

- 按书写顺序**从上到下**逐个匹配,匹配成功一个就不再看后面的。
- 匹配规则是 `isinstance`:`except ValueError` 也能捕获 `ValueError` 的子类。
- 因此**子类要写在父类前面**,否则永远轮不到:

```python
try:
    ...
except OSError:            # FileNotFoundError 是 OSError 的子类
    print("永远走这里")
except FileNotFoundError:  # 死代码,永远不会执行!
    print("永远走不到")
```

### 3.2 else:比你想象的有用

新手常把成功路径也塞进 `try`:

```python
# 不好:json.load 的 KeyError 也会被当成"文件不存在"处理
try:
    f = open("config.json")
    config = json.load(f)
    port = config["port"]
except FileNotFoundError:
    port = 8000
```

`try` 块越大,"误捕获"的风险越大。`else` 的意义就是**把"成功之后才做的事"移出 try**,让 `except` 只对准你真正想保护的那一行。

### 3.3 finally:保证清理

`finally` 无论如何都会执行——正常结束、抛异常、甚至 `try` 块里有 `return`:

```python
def read_data():
    f = open("data.txt")
    try:
        return f.read()
    finally:
        f.close()   # 即使上面 return 了,这里也会执行
```

但在实际工程里,**资源清理优先用 `with`(上下文管理器)**,它就是 `try/finally` 的语法糖,更短且不会忘:

```python
def read_data():
    with open("data.txt") as f:
        return f.read()   # 离开 with 块时自动 close,即使中途抛异常
```

你项目里的 `httpx` 也支持:`with httpx.Client(timeout=30) as client: ...`。

---

## 4. 异常的类型体系

Python 所有异常构成一棵继承树,记住主干即可:

```text
BaseException                 ← 所有异常的根,平时【不要】捕获它
├── SystemExit                ← sys.exit() 触发
├── KeyboardInterrupt         ← 用户按 Ctrl+C
└── Exception                 ← ★ 所有"普通错误"的基类,你该关心的是这一支
    ├── ValueError            ← 类型对但值不对:int("abc")
    ├── TypeError             ← 类型就不对:len(3)
    ├── KeyError              ← 字典缺键:d["missing"]
    ├── IndexError            ← 序列越界:lst[99]
    ├── AttributeError        ← 对象没有该属性:None.foo
    ├── OSError               ← 操作系统层错误
    │   ├── FileNotFoundError
    │   ├── PermissionError
    │   └── TimeoutError
    ├── RuntimeError          ← 不好归类的运行时错误
    ├── LookupError           ← KeyError/IndexError 的共同父类
    └── ...(以及所有第三方库和你自定义的异常)
```

三个实用推论:

1. **`except Exception` 是"捕获一切普通错误"的正确写法**;裸 `except:` 等价于 `except BaseException:`,会连 `Ctrl+C`(`KeyboardInterrupt`)和 `sys.exit()` 一起吞掉——你的程序会变得连杀都杀不掉。这是裸 `except` 的第一宗罪。
2. **第三方库的异常也在这棵树上**。例如 `httpx.HTTPStatusError` 和 `httpx.TimeoutException` 都继承自 `httpx.HTTPError`;`jwt.ExpiredSignatureError` 继承自 `jwt.PyJWTError`(所以你的 `deps.py` 里 `except jwt.PyJWTError` 能同时抓住"过期"和"篡改"两种情况——这一处你写对了)。
3. **捕获尽量精确,宁窄勿宽**。想抓"文件不存在"就写 `FileNotFoundError`,不要写 `OSError`,更不要写 `Exception`。

---

## 5. 抛出异常:raise 与异常链

### 5.1 基本用法

```python
def set_temperature(value: float):
    if not 0 <= value <= 2:
        raise ValueError(f"temperature 必须在 0~2 之间,收到 {value}")
```

两个要点:

- **抛类型合适的异常**:值不对用 `ValueError`,类型不对用 `TypeError`,业务错误用自定义异常(下一节)。
- **错误信息要能帮人定位**:带上非法值本身、期望范围等上下文。`raise ValueError("参数错误")` 是不合格的错误信息。

### 5.2 重新抛出:`raise`(不带参数)

在 `except` 块里裸写 `raise`,表示"我记录/清理一下,但处理不了,原样上抛":

```python
try:
    process(order)
except Exception:
    logger.exception("处理订单 %s 失败", order.id)  # 记日志
    raise                                            # 原样上抛,traceback 完整保留
```

这是"日志 + 上抛"模式,服务端代码极常用。

### 5.3 异常链:`raise ... from e`

当你想**把底层异常翻译成高层异常**时,用 `from` 保留因果关系:

```python
class ConfigError(Exception):
    pass

def load_config(path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError as e:
        raise ConfigError(f"配置文件 {path} 不存在") from e
    except json.JSONDecodeError as e:
        raise ConfigError(f"配置文件 {path} 不是合法 JSON") from e
```

调用者只需要关心 `ConfigError`(不必知道底层是文件问题还是 JSON 问题),而 traceback 里会同时打印两个异常,中间用一行连接:

```text
json.JSONDecodeError: Expecting value: line 1 column 1 (char 0)

The above exception was the direct cause of the following exception:

ConfigError: 配置文件 config.json 不是合法 JSON
```

**"翻译异常"是分层架构的核心技巧**:repository 层抛底层异常,service 层翻译成业务异常,API 层再翻译成 HTTP 响应。下篇会用你的 `ai_service` 完整演示。

> 顺带一提:如果你在 `except` 块里抛新异常但**忘了写 `from e`**,Python 也会打印两个异常,但连接语变成 "During handling of the above exception, another exception occurred"——意思是"处理 A 时又出了 B",通常暗示你的错误处理代码本身有 bug。看到这句话要警觉。

---

## 6. 自定义异常类

### 6.1 为什么需要

看你 `auth_service.py` 里的现状:

```python
def register_user(user: UserCreate) -> UserOut:
  if get_user(user.email) is not None:
    raise Exception({ "content": "用户已存在" })   # ← 问题所在
```

抛裸 `Exception` 有两个致命问题:

1. **调用者无法精确捕获**。上层想区分"用户已存在"和其他错误,只能 `except Exception`——而这会把 `NameError`、`KeyError` 等真正的 bug 也一起抓进来,于是任何 bug 都被报告成"用户已存在"。这正是你 `main.py` 里发生的事。
2. **信息塞在 `args` 里没有结构**。`{"content": "..."}` 这种字典要靠约定去取,类型检查器也帮不了你。

### 6.2 怎么写

自定义异常就是继承 `Exception`(或它的子类)的普通类:

```python
# app/core/errors.py

class AppError(Exception):
    """本项目所有业务异常的基类。"""
    def __init__(self, message: str):
        super().__init__(message)   # 让 str(e) 和 traceback 能显示 message
        self.message = message


class UserAlreadyExistsError(AppError):
    def __init__(self, email: str):
        super().__init__(f"用户 {email} 已存在")
        self.email = email


class InvalidCredentialsError(AppError):
    def __init__(self):
        super().__init__("邮箱或密码错误")


class UnsupportedModelError(AppError):
    def __init__(self, provider: str):
        super().__init__(f"暂不支持模型提供方: {provider}")
        self.provider = provider
```

设计要点:

- **给项目定义一个共同基类 `AppError`**。好处:上层可以一把捕获"所有业务错误"(`except AppError`)而不误伤真正的 bug(`KeyError` 等不会被抓到);下篇的 FastAPI 全局 handler 也只需注册这一个基类。
- **异常类名以 `Error` 结尾**,是 Python 社区惯例。
- **把结构化信息存为属性**(如 `self.email`),而不是拼进字符串完事——处理方可能需要这些字段。
- 异常类通常**不需要任何方法**,空类加一个 `__init__` 就够了。它的价值在于"类型本身可被 `except` 区分"。

### 6.3 使用后的对比

```python
# service 层:抛出精确的业务异常
def register_user(user: UserCreate) -> UserOut:
    if get_user(user.email) is not None:
        raise UserAlreadyExistsError(user.email)
    ...

# 调用层:精确捕获,bug 不会被误伤
try:
    register_user(user)
except UserAlreadyExistsError as e:
    ...  # 只有"用户已存在"走这里;NameError 等 bug 会正常上抛、暴露出来
```

---

## 7. 异常处理的设计哲学

### 7.1 EAFP vs LBYL

Python 社区推崇 **EAFP**(Easier to Ask Forgiveness than Permission,先做再说,出错再处理),而不是 **LBYL**(Look Before You Leap,做之前先检查):

```python
# LBYL:先检查
if "price" in data:
    price = data["price"]
else:
    price = 0

# EAFP:直接做,失败再处理 —— 更 Pythonic
try:
    price = data["price"]
except KeyError:
    price = 0
```

EAFP 的实际优势在**并发和外部资源**场景:`if os.path.exists(path): open(path)` 在检查和打开之间文件可能被删除(TOCTOU 竞态),而 `try: open(path) except FileNotFoundError:` 没有这个窗口。你项目里注册用户的 `if get_user(...) is not None` + 后续写文件,严格说也存在同类竞态(两个并发注册同时通过检查),换数据库唯一索引 + 捕获冲突异常才是根治。

### 7.2 在哪一层处理异常?

黄金法则:**在"有足够信息决定怎么办"的那一层处理;没有就别捕获,让它上抛。**

- `user_repo.py`(repository 层):不知道"用户已存在"该返回 400 还是重试,所以**不该捕获**,顶多翻译成仓储层异常。
- `auth_service.py`(service 层):知道业务规则,负责**抛出业务异常**(`UserAlreadyExistsError`)。
- `main.py` / 全局 handler(API 层):知道 HTTP 协议,负责**把业务异常翻译成状态码和响应体**。

反过来说,**每一层都写 try/except 是过度防御**。大部分函数应该一行异常处理都没有——这是正常的、健康的。

### 7.3 抛异常 vs 返回 None / bool

| 场景 | 推荐 |
|---|---|
| "查不到"是正常业务情况(如 `get_user` 查无此人) | 返回 `None`,并在类型标注里写明 `-> UserRecord \| None` |
| 操作失败意味着流程无法继续(如写文件失败) | **抛异常**,不要返回 `False` |
| 失败需要调用者区分原因 | 抛不同类型的异常 |

你的 `save_users` 返回 `bool` 就是踩了第二条:返回 `False` 太容易被忽略(事实上也真的被忽略了),而异常不处理就会炸出来,**逼着**调用者面对失败。修正:

```python
def save_users(users: list[UserRecord]) -> None:
    USER_REPO_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = [user.model_dump() for user in users]
    # 不再 try/except:写失败就让 OSError 上抛,由上层统一处理
    USER_REPO_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
```

---

## 8. 五个最常见的反模式

### 反模式 ①:裸 `except:`(你的 `main.py` 两处都是)

```python
try:
    return register_user(user)
except:                          # ← 三宗罪
    raise HTTPException(400, detail="用户已存在")
```

三宗罪:

1. 连 `KeyboardInterrupt` / `SystemExit` 都捕获(见第 4 节)。
2. **把所有 bug 翻译成同一句业务提示**。`register_user` 里若有 `NameError`、磁盘写满的 `OSError`,用户看到的都是"用户已存在",你排查时毫无线索。
3. 销毁 traceback,没有留下任何日志。

修正:只捕获你定义的业务异常,其余放行:

```python
try:
    return register_user(user)
except UserAlreadyExistsError as e:
    raise HTTPException(status_code=400, detail=e.message)
# 其他异常自动上抛 → 由全局 handler 记日志、返回 500(见下篇)
```

### 反模式 ②:捕获后静默吞掉

```python
try:
    send_notification(user)
except Exception:
    pass    # ← 出错了?当没看见
```

只有极少数场景允许"吞掉"(如通知失败不影响主流程),且即便如此也**必须留日志**:

```python
except Exception:
    logger.exception("发送通知失败,不影响主流程")
```

### 反模式 ③:`try` 块包得太大

`try` 里的代码越多,`except` 误捕获的可能性越大(见 3.2 节)。只包住真正可能抛目标异常的一两行,成功路径放 `else`。

### 反模式 ④:用异常做正常流程控制

```python
# 不好:把"存在"这个正常分支用异常表达给调用者
def check_user_exists(email):
    if get_user(email):
        raise Exception("exists")
```

异常表达的是"**不该发生/无法继续**"。"查询结果为空"这类正常分支用返回值。

### 反模式 ⑤:捕获了却丢失原始异常

```python
except json.JSONDecodeError:
    raise ConfigError("配置错误")          # 原始异常的位置信息丢了
# 应该:
except json.JSONDecodeError as e:
    raise ConfigError("配置错误") from e   # 异常链保留完整现场
```

---

## 9. 异常与日志

服务端程序没人盯着控制台,**日志是异常的最终归宿**。三个 API 记住就够用:

```python
import logging

logger = logging.getLogger(__name__)

try:
    do_something()
except SomeError:
    logger.exception("处理失败,order_id=%s", order_id)
```

- `logger.exception(msg)`:**只能在 `except` 块里用**,自动附带完整 traceback。这是最常用的。
- `logger.error(msg, exc_info=True)`:效果同上,可在任意位置用。
- `logger.warning(msg)`:预期内的、不需要 traceback 的问题(如"配置缺失,使用默认值")。

原则:**同一个异常,日志只记一次**(通常在最终处理它的那一层记)。每层都 `logger.exception` 再上抛,会让一次错误在日志里出现五遍,反而干扰排查。

---

## 10. 本篇小结与自查清单

写完(或审查)一段错误处理代码时,过一遍这个清单:

- [ ] 没有裸 `except:`;最宽只到 `except Exception`,且仅用于"最外层兜底 + 记日志"。
- [ ] 每个 `except` 捕获的类型尽可能精确,子类在前父类在后。
- [ ] 业务错误用自定义异常类表达,项目有统一的 `AppError` 基类。
- [ ] 跨层翻译异常时用了 `raise ... from e`。
- [ ] "操作失败"靠抛异常而不是返回 `False`;"查无结果"才返回 `None`。
- [ ] `try` 块尽量小,成功路径在 `else` 里。
- [ ] 资源清理用 `with`,而不是手写 `try/finally`。
- [ ] 被吞掉的异常一定有 `logger.exception`/`logger.warning` 留痕。
- [ ] 错误信息带上下文(非法值、id、路径),能直接指导排查。

掌握以上内容后,继续阅读下篇 `02_http_error_handling.md`:如何把这套机制接到 HTTP 世界——状态码语义、FastAPI 的 `HTTPException` 与全局 exception handler、httpx 客户端错误处理,以及对你 `ai_service` 的完整重构示范。
