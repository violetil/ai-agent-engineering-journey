# Python 异常与错误处理讲义(下):HTTP 与 FastAPI 错误处理

> 前置阅读:`01_python_exceptions.md`。
>
> 本篇把上篇的异常机制接入 HTTP 世界,所有示例都基于你的 `week3_python_abilities/ai_service` 项目,最后给出一套可以直接落地的重构方案。

---

## 目录

1. [HTTP 错误的两个视角](#1-http-错误的两个视角)
2. [状态码语义:该返回哪个码?](#2-状态码语义该返回哪个码)
3. [FastAPI 的错误处理机制](#3-fastapi-的错误处理机制)
4. [设计统一的错误响应格式](#4-设计统一的错误响应格式)
5. [全局异常处理器:exception_handler](#5-全局异常处理器exception_handler)
6. [作为 HTTP 客户端:httpx 的错误处理](#6-作为-http-客户端httpx-的错误处理)
7. [实战:重构你的 ai_service](#7-实战重构你的-ai_service)
8. [安全细节:错误信息该暴露多少?](#8-安全细节错误信息该暴露多少)
9. [练习题](#9-练习题)
10. [总结:一张完整的错误流转图](#10-总结一张完整的错误流转图)

---

## 1. HTTP 错误的两个视角

你的 `ai_service` 在错误处理上同时扮演两个角色,别混淆:

- **作为服务端**:客户端调你的 `/auth/sign_up`、`/chat/completions`,你要用**状态码 + 响应体**告诉它出了什么错。工具是 FastAPI 的 `HTTPException` 和 exception handler。
- **作为客户端**:你的 `deepseek.py` 调 DeepSeek 的 API,对方也用状态码告诉你出了什么错。工具是 `httpx` 的异常体系。

而且两个角色会串联:**DeepSeek 返回 429(上游错误)时,你要决定给你的用户返回什么(下游响应)**。这种"错误翻译"是 AI 网关类服务的核心逻辑,第 6、7 节详讲。

---

## 2. 状态码语义:该返回哪个码?

第一原则:**4xx = 客户端的错,重试同样的请求也没用;5xx = 服务端的错,客户端没做错什么。** 这个区分直接影响调用方行为(5xx 通常触发重试,4xx 不会),必须选对。

后端日常用到的码,按你项目的场景对号入座:

| 状态码 | 语义 | 你项目中的场景 |
|---|---|---|
| 200 OK | 成功 | chat 补全成功 |
| 201 Created | 创建成功 | 注册成功(你已经用对了) |
| 400 Bad Request | 请求有问题,不细分 | 通用业务错误 |
| 401 Unauthorized | **未认证**(没带 token / token 无效) | 未登录调 chat;JWT 过期 |
| 403 Forbidden | **已认证但无权限** | 将来做角色/配额时用 |
| 404 Not Found | 资源(URL 指向的东西)不存在 | 访问不存在的路由 |
| 409 Conflict | 与服务器当前状态冲突 | **注册时用户已存在(比 400 更精确)** |
| 422 Unprocessable Entity | 格式对但内容无法处理 | FastAPI 校验失败自动返回;**不支持的 model_provider** |
| 429 Too Many Requests | 触发限流 | 将来给 chat 加限流时用 |
| 500 Internal Server Error | 服务端未预期错误 | 代码 bug、磁盘写不进 |
| 502 Bad Gateway | **上游服务返回了错误** | DeepSeek 返回 4xx/5xx |
| 503 Service Unavailable | 服务暂时不可用 | 依赖全挂、维护中 |
| 504 Gateway Timeout | **上游服务超时** | DeepSeek 请求超时 |

三个易错点,结合你的代码:

1. **401 vs 403**:名字有误导性(Unauthorized 其实指"未认证")。没登录 → 401;登录了但不许你干 → 403。你的 `deps.py` 用 401 是对的。
2. **404 的对象是"URL 指向的资源"**。你的 `chat_service.py` 对不支持的模型返回 404 是不合适的——`/chat/completions` 这个资源明明存在,是请求**内容**不被接受,应该用 422(或 400)。404 会误导调用方以为 URL 写错了。
3. **"用户已存在"更适合 409** 而不是 400:请求本身格式合法,只是与服务器已有状态(该邮箱已注册)冲突。用 400 不算错,但 409 让客户端能精确分支。

---

## 3. FastAPI 的错误处理机制

FastAPI 内建三层错误处理,先弄清楚"你不写任何代码时会发生什么":

### 3.1 请求校验失败 → 自动 422

Pydantic 模型校验失败时,FastAPI 自动返回 422,响应体长这样:

```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "password"],
      "msg": "String should have at least 8 characters",
      "input": "123"
    }
  ]
}
```

这就是为什么 schema 要写准:你的 `ChatRequest.model_provider` 声明了 `Literal["deepseek", "openai"]`,但 service 层实际只支持 deepseek。如果把 `Literal` 收窄为只含真正支持的值,"不支持的模型"这个错误在**校验阶段**就会以标准 422 返回,service 层的判断就可以删掉——**能用类型系统挡住的错误,不要留到运行时**。

### 3.2 HTTPException → 你手动指定的状态码

```python
from fastapi import HTTPException

raise HTTPException(status_code=409, detail="用户已存在")
```

FastAPI 捕获它并渲染成:

```json
{ "detail": "用户已存在" }
```

注意 `HTTPException` 的定位:它是**表现层(HTTP 层)的概念**,`detail` 会原样发给客户端。因此它只应该出现在路由函数和依赖(`deps.py`)里;service 层、repository 层不应该 import 它——你的 `chat_service.py` 里 `raise HTTPException(404, ...)` 就把 HTTP 泄漏进了业务层,导致这个函数将来没法被 CLI、定时任务复用,单测也必须理解 HTTP。业务层应该抛业务异常(上篇第 6 节),由 API 层翻译。

### 3.3 未捕获的异常 → 500

任何没被捕获的异常传到框架顶层,FastAPI 返回纯文本 `Internal Server Error`(500),并在服务端打印 traceback。客户端得不到任何有用信息——这是最后的兜底,不该是常态。

### 3.4 问题:三种错误,三种格式

汇总一下,你的服务目前对外有**三种互不兼容的错误响应形状**:

| 触发方式 | 状态码 | 响应体形状 |
|---|---|---|
| Pydantic 校验失败 | 422 | `{"detail": [ {...}, ... ]}`(列表) |
| HTTPException | 4xx | `{"detail": "字符串"}` |
| 未捕获异常 | 500 | 纯文本 `Internal Server Error` |

客户端要写三套解析逻辑。解决方案就是接下来的两节:统一格式 + 全局 handler。

---

## 4. 设计统一的错误响应格式

工程上通行的做法是定义一个所有错误共用的响应结构:

```json
{
  "error": {
    "code": "USER_ALREADY_EXISTS",
    "message": "用户 a@b.com 已存在",
    "request_id": "d4f8a2"
  }
}
```

三个字段的分工:

- **`code`:机器读的**。稳定的字符串枚举,客户端用它做分支(`if code == "USER_ALREADY_EXISTS"`)。绝不要让客户端去解析 message 文案——文案一改客户端就崩。
- **`message`:人读的**。可以随时调整措辞,可以做多语言。
- **`request_id`:排障用的**。用户报错时报上这个 id,你在日志里一搜就能找到对应请求的完整上下文。(入门阶段可先省略,但要知道它存在的意义。)

对应的 Pydantic 模型:

```python
# app/schemas/error.py
from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
```

> 参考:OpenAI 的 API 错误就是这个思路,形如 `{"error": {"type": "invalid_request_error", "code": "model_not_found", "message": "..."}}`。你在 week1 调 LLM 时见过的报错正是统一格式的实例。

---

## 5. 全局异常处理器:exception_handler

`@app.exception_handler(SomeError)` 向 FastAPI 注册"当 `SomeError`(或其子类)冒到框架层时怎么渲染响应"。这是整套方案的枢纽——**它让路由函数里的 try/except 全部消失**。

```python
# app/core/error_handlers.py
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.errors import (
    AppError,
    InvalidCredentialsError,
    UnsupportedModelError,
    UpstreamServiceError,
    UpstreamTimeoutError,
    UserAlreadyExistsError,
)

logger = logging.getLogger(__name__)

# 业务异常类型 → (HTTP 状态码, 错误 code) 的映射表
ERROR_MAP: dict[type[AppError], tuple[int, str]] = {
    UserAlreadyExistsError: (409, "USER_ALREADY_EXISTS"),
    InvalidCredentialsError: (401, "INVALID_CREDENTIALS"),
    UnsupportedModelError:   (422, "UNSUPPORTED_MODEL"),
    UpstreamServiceError:    (502, "UPSTREAM_ERROR"),
    UpstreamTimeoutError:    (504, "UPSTREAM_TIMEOUT"),
}


def _error_json(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def register_error_handlers(app: FastAPI) -> None:

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        """所有业务异常:查表翻译成 HTTP 响应。"""
        status_code, code = ERROR_MAP.get(type(exc), (400, "BAD_REQUEST"))
        if status_code >= 500:
            # 上游故障值得记日志;4xx 业务错误是正常现象,不刷日志
            logger.warning("上游错误 %s %s: %s", request.method, request.url.path, exc)
        return _error_json(status_code, code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        """把 FastAPI 自带的 422 也收编成统一格式。"""
        first = exc.errors()[0]
        field = ".".join(str(x) for x in first["loc"])
        return _error_json(422, "VALIDATION_ERROR", f"{field}: {first['msg']}")

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception):
        """最后的兜底:真正的 bug 走这里。"""
        # 服务端:记下完整 traceback —— 这是全项目唯一一处"捕获 Exception"
        logger.exception("未处理异常 %s %s", request.method, request.url.path)
        # 客户端:只给通用信息,绝不暴露 str(exc)(可能含路径、SQL、密钥)
        return _error_json(500, "INTERNAL_ERROR", "服务器内部错误,请稍后重试")
```

理解这段代码的四个关键:

1. **handler 的匹配也认继承**:注册在 `AppError` 上的 handler 能接住所有子类,所以新增一种业务异常只需在 `ERROR_MAP` 加一行。
2. **映射表放在 API 层,异常类里不写状态码**。`UserAlreadyExistsError` 不应该知道 HTTP 的存在(业务层和表现层解耦);"它对应 409"是表现层的决定。
3. **对比上篇反模式①**:裸 `except:` 把 bug 伪装成业务错误;而这里 bug 走 `Exception` 兜底 handler——服务端有完整 traceback,客户端收到诚实的 500。**错误被"如实分类"了,这就是可调试性的来源。**
4. 日志策略:4xx 不记(正常业务现象)、502/504 记 warning、500 记 exception(带 traceback)。同一个错误只在这里记一次。

---

## 6. 作为 HTTP 客户端:httpx 的错误处理

现在换到客户端视角。先看你 `deepseek.py` 的现状:

```python
response = httpx.post(url=URL, headers=header, json=payload)
response.raise_for_status()
data = response.json()
```

三个隐患:

1. **没设超时**。httpx 默认 5 秒,而 LLM 生成长回复经常超过 5 秒——你的接口会莫名其妙地大量超时失败。必须显式设置。
2. **`raise_for_status()` 抛的异常没人接**。DeepSeek 返回 401(你的 key 失效)、429(限流)、500 时,`httpx.HTTPStatusError` 一路冒到顶层,你的用户收到裸 500,而真实原因(比如"该充钱了")被完全掩盖。
3. **`data["choices"][0]` 无保护**。上游返回意外结构时 `KeyError`,同样变成裸 500。

### httpx 的异常树(记这四个就够)

```text
httpx.HTTPError                     ← httpx 所有错误的基类
├── httpx.RequestError              ← 请求根本没完成(没拿到响应)
│   ├── httpx.ConnectError          ← 连不上(DNS、拒绝连接)
│   └── httpx.TimeoutException     ← 超时
└── httpx.HTTPStatusError           ← 拿到响应了,但 raise_for_status() 发现是 4xx/5xx
      属性: .response.status_code / .response.text
```

关键区分:**"没拿到响应"(`RequestError`)和"拿到了错误响应"(`HTTPStatusError`)是两种病**,前者适合翻译成 504/503,后者适合 502,重试策略也不同(前者常可重试,后者看状态码)。

### 修正后的 deepseek.py

```python
import httpx
from app.core.errors import UpstreamServiceError, UpstreamTimeoutError
from app.schemas.chat import ChatMessage, ChatResponse

TIMEOUT = httpx.Timeout(60.0, connect=5.0)   # 总 60s,连接 5s

def ask_llm(model: str, messages: list[ChatMessage], temperature: float = 0.7) -> ChatResponse:
    payload = {
        "model": model,
        "temperature": temperature,
        "messages": [m.model_dump() for m in messages],
    }
    try:
        response = httpx.post(URL, headers=header, json=payload, timeout=TIMEOUT)
        response.raise_for_status()
    except httpx.TimeoutException as e:
        raise UpstreamTimeoutError("LLM 服务响应超时") from e
    except httpx.HTTPStatusError as e:
        # 把上游状态码带进 message,排障时一眼看到根因
        raise UpstreamServiceError(
            f"LLM 服务返回错误: HTTP {e.response.status_code}"
        ) from e
    except httpx.RequestError as e:
        raise UpstreamServiceError(f"无法连接 LLM 服务: {e}") from e

    data = response.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise UpstreamServiceError("LLM 返回了无法解析的响应结构") from e

    return ChatResponse(content=content, model=data.get("model", model))
```

注意这个函数展示了上篇讲的完整套路:**精确捕获(三种 httpx 异常分开处理)→ 翻译成自己的业务异常 → `from e` 保留异常链**。它抛出的 `UpstreamServiceError` 会被第 5 节的 handler 接住,翻译成 502——上游的错误就这样有序地流经了整个系统。

---

## 7. 实战:重构你的 ai_service

把前面所有内容组装起来。改动共五个文件,每个都很小:

### ① 新增 `app/core/errors.py` —— 业务异常

```python
class AppError(Exception):
    """本项目所有业务异常的基类。"""
    def __init__(self, message: str):
        super().__init__(message)
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


class UpstreamServiceError(AppError):
    """上游(LLM)返回错误。"""


class UpstreamTimeoutError(AppError):
    """上游(LLM)超时。"""
```

### ② 新增 `app/core/error_handlers.py` —— 见第 5 节完整代码

### ③ 修改 `app/services/auth_service.py` —— 抛业务异常

```python
from app.core.errors import InvalidCredentialsError, UserAlreadyExistsError


def register_user(user: UserCreate) -> UserOut:
    if get_user(user.email) is not None:
        raise UserAlreadyExistsError(user.email)     # 原来是 raise Exception({...})
    add_user(UserRecord(
        email=user.email,
        username=user.username,
        password_hash=hash_password(user.password),
    ))
    return UserOut(email=user.email, username=user.username)


def login(body: SignInIn) -> TokenOut:
    user = get_user(body.email)
    if user is None or not verify_password(body.password, user.password_hash):
        raise InvalidCredentialsError()              # 原来是 raise Exception({...})
    return TokenOut(access_token=create_access_token(body.email))
```

### ④ 修改 `app/services/chat_service.py` —— 去掉 HTTPException

```python
from app.core.errors import UnsupportedModelError    # 不再 import HTTPException


def chat_completions(body: ChatRequest) -> ChatResponse:
    if body.model_provider == "deepseek":
        return llm.deepseek.ask_llm(
            model=body.model,
            messages=body.messages,
            temperature=body.temperature,
        )
    raise UnsupportedModelError(body.model_provider)  # 原来是 HTTPException(404)
```

(以及第 6 节修正后的 `deepseek.py`。)

### ⑤ 修改 `app/main.py` —— 路由层的 try/except 全部消失

```python
from fastapi import FastAPI, status
from app.core.error_handlers import register_error_handlers
from app.schemas.auth import UserCreate, UserOut, SignInIn, TokenOut
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import chat_completions
from app.services.auth_service import register_user, login
from app.api.deps import CurrentUser

app = FastAPI(title="Violet AI API Service")
register_error_handlers(app)


@app.post("/chat/completions", response_model=ChatResponse)
def _chat_completions(body: ChatRequest, user: CurrentUser):
    return chat_completions(body)


@app.post("/auth/sign_up", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def _sign_up(user: UserCreate):
    return register_user(user)      # 没有 try/except!


@app.post("/auth/sign_in", response_model=TokenOut)
def _sign_in(body: SignInIn):
    return login(body)              # 没有 try/except!
```

### 重构前后对比

| | 重构前 | 重构后 |
|---|---|---|
| 注册时代码有 bug | 返回 400"用户已存在"(说谎) | 返回 500,服务端日志有完整 traceback |
| DeepSeek 限流 429 | 裸 500,无信息 | 502 + `UPSTREAM_ERROR` + 可读 message |
| DeepSeek 超时 | 裸 500(且 5 秒就超) | 504 + `UPSTREAM_TIMEOUT`,超时上限 60 秒 |
| 错误响应格式 | 三种形状 | 全部是 `{"error": {code, message}}` |
| 错误文案维护 | service 和路由两处重复 | 只在异常类一处 |
| 路由函数 | 每个都缠着 try/except | 一行转发,零错误处理代码 |

用 curl 验证(启动服务后):

```bash
# 409 + USER_ALREADY_EXISTS:注册同一邮箱两次
curl -s -X POST localhost:8000/auth/sign_up \
  -H 'Content-Type: application/json' \
  -d '{"email":"a@b.com","username":"violet","password":"12345678"}'

# 401 + INVALID_CREDENTIALS:错误密码登录
curl -s -X POST localhost:8000/auth/sign_in \
  -H 'Content-Type: application/json' \
  -d '{"email":"a@b.com","password":"wrongpass"}'

# 422 + VALIDATION_ERROR:密码太短(被 Pydantic 挡住)
curl -s -X POST localhost:8000/auth/sign_up \
  -H 'Content-Type: application/json' \
  -d '{"email":"c@d.com","username":"violet","password":"123"}'
```

---

## 8. 安全细节:错误信息该暴露多少?

错误信息是给两拨人看的,尺度完全不同:

- **给客户端(对外)**:够用就好,多说是漏洞。
  - 500 响应**绝不**包含 `str(exc)`、traceback、文件路径、SQL 语句——这些可能泄漏密钥、内网结构,是渗透测试的第一挖掘点。第 5 节兜底 handler 只返回"服务器内部错误"就是这个原因。
  - **登录失败要模糊**:统一说"邮箱或密码错误",不说"该邮箱未注册"——否则攻击者可以批量探测哪些邮箱注册过(用户枚举攻击)。你的 `login` 把 `user is None` 和密码错误合并成一个分支,这一点写对了,保持住。
  - 注册接口的"用户已存在"天然会泄漏注册状态,这是易用性与安全的权衡,一般服务可接受;对隐私敏感的产品会改用"发确认邮件"的流程绕开。
- **给自己(日志)**:越详细越好。完整 traceback、request_id、关键参数(但**不要记密码原文和完整 token**)。

一个基础但常被忽略的点:你的 `security.py` 里 `SECRET_KEY = os.getenv("JWT_SECRET_KEY")` 在环境变量缺失时得到 `None`,服务照常启动,直到第一次签发 token 才报错。配置类错误应该 **fail-fast**——启动时就炸:

```python
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("环境变量 JWT_SECRET_KEY 未设置,服务拒绝启动")
```

宁可部署失败,不要带病运行。

---

## 9. 练习题

按顺序做,难度递增。做完对照第 7 节和上篇自查清单复盘。

1. **读 traceback**:故意在 `register_user` 里写一行 `undefined_variable`,分别在"重构前(裸 except)"和"重构后"调用注册接口,对比客户端响应和服务端日志。体会"错误被如实分类"的价值。
2. **落地重构**:把第 7 节的五个文件改动真正实现到你的 `ai_service` 里,用第 7 节末尾的 curl 命令逐一验证状态码和响应体。
3. **新增一种业务错误**:给 chat 接口加"消息列表不能为空"的校验。要求分别用两种方式实现并对比:(a) 在 `ChatRequest` 上用 Pydantic 的 `Field(min_length=1)`;(b) 定义 `EmptyMessagesError` 走异常体系。思考:哪种更好?为什么?(提示:3.1 节最后一句。)
4. **修复静默失败**:按上篇 7.3 节把 `save_users` 改成失败抛异常而不是返回 `bool`,并思考:抛出的 `OSError` 会被哪个 handler 接住?客户端会看到什么?
5. **异常链侦查**:在 `deepseek.py` 里把 API key 改错,调用 chat 接口,在服务端日志里找到 `UpstreamServiceError` 和它 `from` 出来的 `httpx.HTTPStatusError`,确认异常链两段都在。
6. **(进阶)request_id 中间件**:写一个 FastAPI middleware,为每个请求生成短随机 id,放进 `request.state`,在错误响应和日志里都带上它。模拟一次"用户拿着 request_id 来报障,你在日志里定位"的全流程。

---

## 10. 总结:一张完整的错误流转图

```text
                      ┌────────────────────────────────────────────┐
 客户端请求 ──────────▶│ Pydantic 校验失败? ──▶ 422 VALIDATION_ERROR │
                      └───────────────┬────────────────────────────┘
                                      │ 通过
                                      ▼
     ┌─────────── 路由层(main.py):一行转发,零 try/except ───────────┐
     │                                                                │
     ▼                                                                │
 service 层:业务规则不满足 ──raise──▶ UserAlreadyExistsError 等       │
     │                                        │                       │
     ▼                                        │                       │
 llm/repo 层:httpx/OSError ──翻译(from e)──▶ UpstreamServiceError 等  │
                                              │                       │
                                              ▼                       ▼
                              ┌──────────────────────────┐   真正的 bug(KeyError…)
                              │ @exception_handler(AppError)│          │
                              │ 查 ERROR_MAP → 409/401/    │          ▼
                              │ 422/502/504 + 统一 JSON    │  @exception_handler(Exception)
                              └──────────────────────────┘  logger.exception + 500 通用响应
```

核心思想只有一句:**每一层用自己领域的语言表达错误(repo 层抛 OSError,service 层抛业务异常,API 层说 HTTP),层与层之间用 `raise ... from e` 翻译,最终由全局 handler 统一渲染;真正的 bug 永远走 500 兜底而不是被伪装成业务错误。**

做到这一点,你在上一次自查中发现的所有问题——"提示不统一、任何 bug 都显示'用户已存在'、上游错误变裸 500、难以 debug"——就全部解决了。
