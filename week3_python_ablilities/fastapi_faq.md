# FastAPI 讲义答疑（17 问精讲）

> 对应主讲义：`fastapi.md`  
> 读法：每问先给「一句话结论」，再展开机制与代码。

---

## 1. 什么是 Starlette？

**一句话：** Starlette 是一个轻量、高性能的 **ASGI Web 框架/工具包**；FastAPI 站在它肩膀上。

### 分层关系

```
你的业务代码（路由函数）
        ↓
     FastAPI          ← 负责：路由装饰器、依赖注入、Pydantic 校验、自动文档
        ↓
    Starlette         ← 负责：Request/Response、路由底层、中间件、WebSocket、静态文件…
        ↓
     uvicorn          ← 负责：监听端口、收发字节流（ASGI 服务器）
        ↓
      操作系统网络
```

可以把 Starlette 想成「引擎」，FastAPI 想成「带自动挡和仪表盘的整车」：

| 能力 | 谁提供 |
|------|--------|
| `Request` / `Response` | Starlette |
| 中间件机制 | Starlette |
| CORSMiddleware | Starlette（FastAPI 再导出） |
| 路径匹配底层 | Starlette |
| 参数校验、OpenAPI 文档、`Depends` | **FastAPI 自己加的** |
| Pydantic 模型绑定 | **FastAPI 自己加的** |

所以讲义里写「FastAPI = Starlette + Pydantic」的意思是：

- Web 底层能力来自 Starlette
- 数据校验/文档来自 Pydantic + FastAPI 的胶水代码

你平时写 `@app.get`、`Depends`、`BaseModel`，不必直接碰 Starlette；但读报错栈、看中间件源码时会见到它。

---

## 2. uvicorn 是什么？为什么要和 FastAPI 一起用？

**一句话：** uvicorn 是 **ASGI 服务器**；FastAPI 是 **应用**。服务器负责「听端口」，应用负责「处理请求」。

### 类比

| 角色 | 生活类比 | 例子 |
|------|----------|------|
| 服务器（uvicorn） | 饭店的门面、传菜员 | 接收 HTTP，转成 ASGI 事件 |
| 应用（FastAPI `app`） | 厨房 | 根据路径做业务、返回结果 |

FastAPI **自己不会监听 8000 端口**。你写的是：

```python
app = FastAPI()
```

这只是一个符合 ASGI 规范的「可调用对象」。必须有人去跑它：

```bash
uvicorn main:app --reload
```

### 还有别的服务器吗？

有：`hypercorn`、`daphne`、生产里常见 `gunicorn + uvicorn workers`。  
对学习阶段：**uvicorn 就是标准搭档**。

### WSGI vs ASGI（稍微知道即可）

- 旧框架 Flask/Django 传统上用 **WSGI**（同步为主）
- FastAPI/Starlette 用 **ASGI**（原生支持 async、WebSocket）
- uvicorn 就是实现 ASGI 的那一层

---

## 3. `pip install "fastapi[standard]"` 是什么语法？

**一句话：** 这是 **extras（可选依赖组）** 语法：装 fastapi 的同时，把官方标成「标准套装」的额外包一起装上。

### 普通安装 vs extras

```bash
pip install fastapi
# 只装 fastapi 核心（以及它声明的必需依赖，如 starlette、pydantic）

pip install "fastapi[standard]"
# 装 fastapi + [standard] 这一组额外推荐依赖
# 通常包括：uvicorn、httpx、python-multipart、email-validator 等（以当前版本文档为准）
```

### 语法拆解

```
"fastapi[standard]"
   │        │
   │        └── extras 名字（在包的 pyproject/setup 里定义）
   └── 包名

外层引号：因为 [] 在某些 shell 里有特殊含义，加引号更安全
```

同类例子：

```bash
pip install "uvicorn[standard]"   # uvicorn + 高性能可选组件（如 uvloop、httptools）
pip install "pydantic[email]"     # 需要 EmailStr 时
```

**和「多写几个包名」的区别：**

```bash
pip install fastapi uvicorn python-multipart
# 你自己点菜

pip install "fastapi[standard]"
# 用官方搭配菜单（版本兼容由维护者维护）
```

学习建议：开发环境用 `"fastapi[standard]"`；若只要最小体积，再精简安装。

---

## 4. 路径参数和查询参数都注入函数参数吗？怎么区分？何时用 `Query`？

**一句话：** 都注入函数参数；FastAPI 按 **「参数名是否出现在路径里」** 来区分，必要时用 `Path` / `Query` / `Body` 显式声明。

### 默认推断规则（最重要）

```python
@app.get("/users/{user_id}/items")
def read_item(
    user_id: int,          # ① 路径里有 {user_id} → Path 参数
    q: str | None = None,  # ② 路径里没有 q，且是简单类型 → Query 参数
    item: Item,            # ③ 类型是 Pydantic 模型 → Body（JSON 请求体）
):
    ...
```

| 判定 | 来源 | URL / 请求示例 |
|------|------|----------------|
| 参数名在 `{...}` 路径里 | Path | `/users/3/items` |
| 简单类型（int/str/bool…）且不在路径里 | Query | `/users/3/items?q=phone` |
| `BaseModel` 子类 | Body | JSON：`{"name":"..."}` |
| `UploadFile` / `Form` | 表单/文件 | `multipart/form-data` |

### 什么时候必须/建议写 `Query(...)`？

**可以不写**（默认推断就够）：

```python
def search(q: str | None = None, limit: int = 10):
    ...
```

**建议写 `Query` 的场景：**

1. **加校验/文档元数据**（最小值、描述、别名）
2. **强制必填**（没有默认值时，简单类型本就必填；用 `Query(...)` 更明确）
3. **参数名和 Query 键不一致**（`alias`）
4. **避免被误判**（少数复杂情况）

```python
from typing import Annotated
from fastapi import Query

def search(
    q: Annotated[str | None, Query(min_length=1, description="搜索词")] = None,
    limit: Annotated[int, Query(ge=1, le=100, example=10)] = 10,
):
    ...
```

路径参数同理可用 `Path(...)`：

```python
from fastapi import Path

def get_user(user_id: Annotated[int, Path(ge=1, description="用户 ID")]):
    ...
```

### 记忆口诀

> **在花括号里 → Path；不在花括号且是简单类型 → Query；是模型 → Body。**  
> **只有当你要「加限制 / 写文档 / 改别名」时，才显式套 `Query`/`Path`。**

---

## 5. `status_code=status.HTTP_201_CREATED` 是什么意思？

**一句话：** 是的——该路由 **成功时默认返回的 HTTP 状态码**，从默认的 200 改成 201。

### HTTP 状态码心智模型

| 码 | 含义 | 典型场景 |
|----|------|----------|
| 200 OK | 成功 | GET 查询、一般 POST 处理成功 |
| 201 Created | 成功且 **创建了新资源** | `POST /users` 新建用户 |
| 204 No Content | 成功但无响应体 | DELETE 删除成功 |
| 4xx | 客户端错 | 404 找不到、422 校验失败 |
| 5xx | 服务器错 | 未捕获异常 |

```python
@app.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate):
    return user
```

- **不写 `status_code`**：成功默认 **200**
- **写成 201**：成功响应的状态行变成 `HTTP/1.1 201 Created`，body 仍是你 `return` 的内容
- `status.HTTP_201_CREATED` 只是常量，值就是整数 `201`，可读性更好

注意：这只影响 **「函数正常 return 时」** 的成功码。  
你 `raise HTTPException(404)` 时，返回的是 404，不会变成 201。

---

## 6. `raise HTTPException(...)` 会自动返回给客户端吗？和手动 return 404 有何区别？

**一句话：** 会。FastAPI/Starlette 捕获 `HTTPException`，转成对应状态码 + JSON（默认含 `detail`）。这和「普通 return」语义完全不同。

### 机制

```python
raise HTTPException(status_code=404, detail="用户不存在")
```

框架行为大致是：

1. 中断当前路由函数（后面的代码不执行）
2. 生成响应：状态码 `404`，body 类似 `{"detail":"用户不存在"}`
3. **不把它当成未处理崩溃**（不会变成 500）

### 和「手动返回」的对比

```python
# ❌ 不推荐：看起来像成功业务返回，语义混乱
@app.get("/users/{user_id}")
def get_user(user_id: int):
    if user_id not in db:
        return {"error": "用户不存在"}   # 默认仍是 200！客户端以为成功
    return db[user_id]

# ❌ 别扭：你自己拼 Response，丢掉统一异常处理/文档约定
from fastapi.responses import JSONResponse
return JSONResponse(status_code=404, content={"detail": "用户不存在"})

# ✅ 推荐：业务失败用异常表达
raise HTTPException(status_code=404, detail="用户不存在")
```

| 方式 | 状态码 | 是否中断后续逻辑 | 是否符合 REST/文档习惯 |
|------|--------|------------------|------------------------|
| `return {"error": ...}` | 常为 200 | 否 | 差 |
| `return JSONResponse(404, ...)` | 404 | 否（函数还能继续写，易踩坑） | 可以，但分散 |
| `raise HTTPException(404, ...)` | 404 | 是 | 好 |

**原则：** 正常结果用 `return`；「这个请求按 HTTP 语义失败了」用 `raise HTTPException`。

---

## 7. 全局异常处理（加深版）

**一句话：** 全局异常处理 = 给你自定义一类（或所有）异常的「统一出口」，把 Python 异常翻译成 HTTP 响应。

### 7.1 为什么需要它？

路由里到处写：

```python
raise HTTPException(400, detail="xxx")
```

可以，但如果你有自己的领域异常：

```python
class InsufficientBalance(Exception):
    def __init__(self, balance: float):
        self.balance = balance
```

希望 **全项目统一** 变成：

```json
{"detail": "余额不足", "balance": 3.14}
```

就用 `exception_handler` 注册一次，处处 `raise InsufficientBalance(...)` 即可。

### 7.2 完整可运行心智模型

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

class InsufficientBalance(Exception):
    def __init__(self, balance: float):
        self.balance = balance


@app.exception_handler(InsufficientBalance)
async def insufficient_balance_handler(request: Request, exc: InsufficientBalance):
    # request：当前请求（可取 url、headers）
    # exc：被抛出的异常实例
    return JSONResponse(
        status_code=400,
        content={
            "detail": "余额不足",
            "balance": exc.balance,
            "path": str(request.url.path),
        },
    )


@app.post("/pay")
def pay(amount: float):
    balance = 10.0
    if amount > balance:
        raise InsufficientBalance(balance)  # ← 被上面的 handler 接住
    return {"ok": True}
```

**执行顺序：**

```
路由 raise InsufficientBalance
        ↓
FastAPI 查找「有没有注册这个异常类的 handler」
        ↓ 有
调用 handler(request, exc) → 得到 Response → 发给客户端
        ↓ 没有
若是 HTTPException → 框架默认处理
否则 → 通常变成 500 Internal Server Error
```

### 7.3 和 `HTTPException` 的关系

| 异常 | 谁处理 | 典型用途 |
|------|--------|----------|
| `HTTPException` | FastAPI **内置** handler | 404/401/403 等标准 HTTP 错误 |
| 你的自定义 `Exception` | 你注册的 `@app.exception_handler` | 业务错误统一格式 |
| `RequestValidationError` | 内置（可覆盖） | 参数校验失败 → 默认 422 |
| 未捕获的任意异常 | 默认 500 | 程序 bug、未预料错误 |

覆盖校验错误示例（了解即可）：

```python
from fastapi.exceptions import RequestValidationError

@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"msg": "参数不对", "errors": exc.errors()},
    )
```

### 7.4 `try/except` 写在路由里 vs 全局 handler

| 写法 | 适用 |
|------|------|
| 路由内 `try/except` | 只在这一处特殊处理 |
| 全局 `exception_handler` | 同一类错误全项目统一响应格式 |

---

## 8. `Annotated[dict, Depends(...)]`：Depends 谁处理？类型谁校验？

**一句话：** `Annotated` 的元数据给 **FastAPI（不是 Pydantic、也不是 Python 运行时）** 读；FastAPI 发现 `Depends`，先执行依赖函数，再把返回值注入参数。

### 8.1 拆开看

```python
from typing import Annotated
from fastapi import Depends

def get_current_user(token: str):
    if token != "secret-token":
        raise HTTPException(401, detail="未授权")
    return {"id": 1, "name": "Alice"}  # 返回普通 dict

CurrentUser = Annotated[dict, Depends(get_current_user)]

@app.get("/me")
def read_me(user: CurrentUser):
    return user
```

等价于：

```python
def read_me(user: dict = Depends(get_current_user)):
    ...
```

`Annotated[类型, 元数据...]` 是 PEP 593：**把额外信息挂在类型旁边**。  
Python 自己 **不会** 因为看到 `Depends` 就去执行函数；是 **FastAPI 在分析路由签名时** 读到它才处理。

### 8.2 FastAPI 做了什么？

1. 解析函数参数注解
2. 看见 `Depends(get_current_user)` → 先调用 `get_current_user(...)`
3. （若依赖函数自己还有参数）继续按 Path/Query/Header 规则注入
4. 把依赖的 **返回值** 赋给 `user`
5. 再执行 `read_me`

### 8.3 「这里没写 Pydantic，类型谁校验？」

分两层：

| 层 | 谁负责 | 本例中 |
|----|--------|--------|
| 依赖函数的 **入参**（如 `token: str`） | FastAPI + 其内部校验（简单类型 / 或 Pydantic） | `token` 会按 Query/Header 等规则解析校验 |
| 依赖函数的 **返回值** 注入到 `user: dict` | **默认不做深度校验** | 只是类型提示；`user` 实际是你 `return` 的那个对象 |
| 若写成 `user: UserOut` 且 `UserOut` 是 `BaseModel`，并配合 `response_model` 等 | 响应出口常由 FastAPI/Pydantic 处理 | 请求体/响应模型场景更常见 |

所以：

- `Depends` → **FastAPI 的依赖系统**处理
- `dict` 注解 → 主要给人看、给 IDE 看；**不会**自动变成「返回值必须符合某 schema」除非你在依赖里自己用 Pydantic 校验

更严谨的写法：

```python
class User(BaseModel):
    id: int
    name: str

def get_current_user(token: str) -> User:
    ...
    return User(id=1, name="Alice")

CurrentUser = Annotated[User, Depends(get_current_user)]
```

这里返回值在依赖函数末尾由你构造 `User(...)` 时，**Pydantic 会校验构造参数**。

---

## 9. `yield db` 和 `return` 有何区别？没有 except 会怎样？

**一句话：** 在 Depends 里，`yield` 把依赖分成「请求前准备」和「请求后清理」两段；`return` 只有前半段。`try/finally` 不需要 except；失败不会「返回 None」，而是异常继续抛出。

### 9.1 生成器版依赖

```python
def get_db():
    db = {"conn": "fake-db"}
    try:
        yield db          # ① 把 db 交给路由；路由执行期间停在这里
    finally:
        print("关闭连接")  # ② 路由结束后（成功或失败）一定会走
```

对比：

```python
def get_db():
    db = {"conn": "fake-db"}
    return db   # 只能交出 db，无法自动在「请求结束后」跑清理代码
```

| | `return db` | `yield db` |
|--|-------------|------------|
| 路由拿到什么 | `db` | `db` |
| 请求结束后自动清理 | 否 | 是（`yield` 之后的代码 / `finally`） |
| 类似 | 普通函数 | 上下文管理器 `with` |

### 9.2 为什么可以没有 `except`？

```python
try:
    yield db
finally:
    print("关闭连接")
```

- `try/finally` 的意义是：**无论 try 里成功还是抛错，finally 都执行**
- 不写 `except` = **不在这里吞掉异常**，异常会继续向外抛（给 FastAPI 变成 500 或被别的 handler 处理）
- `finally` 本来就不是用来 `return` 业务值的；它负责收尾

### 9.3 「try 失败了会返回 None 吗？」

**不会。** 典型流程：

1. `yield db` 之前就失败（例如连库失败）→ 依赖建立失败，路由函数 **根本不会执行**，异常向上传  
2. `yield` 之后、路由执行中失败 → `finally` 仍执行清理，然后异常继续向上  
3. 没有「失败就默默 return None」这种事，除非你自己 `except` 后写了 `return None`（依赖里一般不要这么干）

普通生成器知识（帮助理解 `yield`）：

```python
def g():
    yield 1
    print("after")

x = next(g())  # 先得到 1；函数停在 yield
# 生成器关闭/再迭代结束时，才会跑 yield 后面的代码
```

FastAPI 对 `yield` 依赖做了同样的事：请求期间停在 `yield`，响应结束后继续跑后面。

---

## 10. `from routers import users` 合法吗？Python 有哪些 import 语法？

**一句话：** 合法——前提是 `routers` 是包（目录下通常有 `__init__.py`，或符合命名空间包规则），且其中有 `users.py`（或 `users` 子包）。

### 10.1 目录对应关系

```
app/
  main.py
  routers/
    __init__.py      # 可为空；标记这是包
    users.py         # 模块名 users
```

```python
# 在 app/ 作为工作目录 / 包根时
from routers import users
# 然后用 users.router

from routers.users import router
# 直接拿 router
```

### 10.2 常见 import 语法一览

```python
# 1) 导入整个模块
import json
import routers.users

# 2) 起别名
import numpy as np
import routers.users as user_routes

# 3) 从模块导入指定对象
from pathlib import Path
from routers.users import router

# 4) 一次导入多个
from typing import Annotated, Optional

# 5) 相对导入（仅在包内部）
from .users import router          # 同级
from ..schemas.user import UserOut # 上级

# 6) 导入包（实际执行包的 __init__.py）
import routers
from routers import users
```

不推荐：

```python
from routers.users import *   # 污染命名空间，难以追踪来源
```

### 10.3 常见报错

`ModuleNotFoundError: No module named 'routers'`  
→ 通常是启动目录不对。应在包含 `routers` 的那一层启动，或把项目装成包 / 设置 `PYTHONPATH`。

---

## 11. `with` 是什么？哪里用？`async with` 有何区别？

**一句话：** `with` 用于 **上下文管理**：进入时获取资源，离开时 **保证释放**（即使中间报错）。`async with` 是异步版。

### 11.1 本质

```python
with open("a.txt", "r", encoding="utf-8") as f:
    data = f.read()
# 到这里文件一定关闭
```

约等于：

```python
f = open(...)
try:
    data = f.read()
finally:
    f.close()
```

### 11.2 常见使用场景（列表）

| 场景 | 例子 |
|------|------|
| 文件读写 | `with open(...) as f` |
| 线程锁 | `with lock:` |
| 数据库会话/连接 | `with Session() as session` |
| 临时改目录/环境 | `with chdir(...):` |
| 测试中的 mock patch | `with patch(...):` |
| 网络客户端（部分库） | `with httpx.Client() as client` |
| 自己写的资源类 | 实现 `__enter__` / `__exit__` |

### 11.3 `async with` vs `with`

| | `with` | `async with` |
|--|--------|--------------|
| 用在 | 同步函数 | `async def` 里 |
| 协议方法 | `__enter__` / `__exit__` | `__aenter__` / `__aexit__` |
| 典型对象 | 普通文件、同步锁 | `httpx.AsyncClient`、异步 DB 连接池 |

```python
# 同步
with httpx.Client() as client:
    r = client.get(url)

# 异步（FastAPI 的 async 路由里常用）
async with httpx.AsyncClient() as client:
    r = await client.get(url)
```

规则：在 `async def` 里优先用异步库 + `async with` / `await`，避免阻塞事件循环。

---

## 12. `r.raise_for_status()` 做什么？会被 FastAPI 自动变成客户端响应吗？

**一句话：** `raise_for_status()` 在 **状态码是 4xx/5xx 时抛出 httpx/requests 的异常**；默认 **不会** 自动变成漂亮的业务 HTTP 响应，未捕获时往往会变成 **500**。

### 12.1 行为

```python
r = await client.get(url)
r.raise_for_status()  # 200–299：什么都不做；否则 raise
```

对 `httpx`：抛 `httpx.HTTPStatusError`  
对 `requests`：抛 `requests.HTTPError`

注意：是 **「非 2xx」**（准确说是 `r.is_success` 为假），不是只看「是不是 2 开头」这句口语——但你的理解方向对。

### 12.2 和 FastAPI 的关系

```python
@app.get("/weather")
async def weather():
    async with httpx.AsyncClient() as client:
        r = await client.get("https://httpbin.org/status/503")
        r.raise_for_status()  # 抛 HTTPStatusError
        return r.json()
```

若你 **不** `try/except`，也 **没有** 注册该异常的 `exception_handler`：

→ FastAPI 当作未处理异常 → 客户端常收到 **500**，而不是上游的 503。

若你希望「上游失败就转成自己的 502」：

```python
import httpx
from fastapi import HTTPException

@app.get("/weather")
async def weather():
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get("https://example.com/api")
            r.raise_for_status()
            return r.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"上游错误: {e.response.status_code}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"上游不可达: {e}")
```

**结论：** `raise_for_status()` 只负责在 **当前 Python 进程里抛异常**；转换成给浏览器/前端的 HTTP 响应，要靠你的 `except` + `HTTPException` 或全局 handler。

---

## 13. `@app.middleware("http")` 是什么？参数含义？

**一句话：** 中间件是包在所有路由外面的钩子：**每个 HTTP 请求进出时都能插手**（记日志、加头、计时、鉴权等）。

### 13.1 写法

```python
@app.middleware("http")
async def add_process_time(request: Request, call_next):
    # 请求进入、还未到路由
    response = await call_next(request)  # 把请求交给下一层（其它中间件/路由）
    # 路由已经跑完，拿到 response
    response.headers["X-Process-Time"] = "..."
    return response
```

### 13.2 「参数」分别是什么？

这里有两层「参数」：

**（1）装饰器参数 `"http"`**

```python
@app.middleware("http")
```

- 目前你实务上就写 `"http"`
- 表示注册的是 **HTTP 中间件**（相对 Starlette 里其它可能的中间件类型语境）
- 日常开发记住：`@app.middleware("http")` 是固定写法即可

**（2）中间件函数的两个参数**

| 参数 | 类型/角色 | 作用 |
|------|-----------|------|
| `request` | `starlette.requests.Request` | 当前请求：路径、头、客户端、查询参数等 |
| `call_next` | 可调用对象 | **必须** `await call_next(request)` 才能进入后续中间件和路由；返回 `Response` |

### 13.3 执行顺序示意

```
Client
  → middleware1 前半
    → middleware2 前半
      → 路由函数
    ← middleware2 后半
  ← middleware1 后半
Client
```

后注册的中间件更靠外（具体以文档/实验为准；团队项目里少叠太多中间件）。

### 13.4 和 Depends 的区别

| | 中间件 | Depends |
|--|--------|---------|
| 作用范围 | 几乎所有请求 | 某个路由 / 某组路由 |
| 能否方便拿到「已校验的业务用户模型」 | 可以，但不如 Depends 清晰 | 很适合鉴权 |
| 典型用途 | CORS、日志、统一头、计时 | 获取 DB、当前用户 |

鉴权更推荐 **Depends**；中间件适合横切基础设施。

---

## 14. 跨域（CORS）专业讲解 + `add_middleware` 参数

### 14.1 什么是「域」？

一个源（Origin）由三部分组成：

```
协议 + 主机 + 端口
https://www.example.com:443
http://localhost:5173
```

只要三者有一个不同，就是 **不同源**。

### 14.2 什么是跨域？

浏览器里的前端页面如果源是 `http://localhost:5173`，却用 JS 去请求 `http://localhost:8000/api`：

→ 这叫 **跨域请求**（Cross-Origin）。

注意：

- **浏览器**会执行同源策略，限制前端 JS 读跨域响应
- 用 `curl`、Postman、服务器对服务器请求，通常 **没有** 这套浏览器限制
- 所以你「后端单独测通了，前端一接就报 CORS error」非常常见

### 14.3 浏览器怎么做？（简化版）

1. 有时先发 **预检请求** `OPTIONS`（尤其是自定义头、JSON POST 等）
2. 看服务器响应头里有没有允许的 `Access-Control-Allow-Origin` 等
3. 不符合 → 浏览器 **拦截**，前端看到 CORS 错误（实际请求可能到了服务器，但 JS 读不到结果）

### 14.4 FastAPI 里怎么配？

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # 允许的前端源列表
    allow_credentials=True,                   # 是否允许带 Cookie 等凭证
    allow_methods=["*"],                      # 允许的 HTTP 方法
    allow_headers=["*"],                      # 允许的请求头
)
```

### 14.5 参数含义

| 参数 | 作用 |
|------|------|
| `CORSMiddleware` | 中间件类（第一个位置参数是中间件类型） |
| `allow_origins` | 哪些前端 Origin 被允许；`"*"` 表示任意（但与 credentials 组合有限制） |
| `allow_credentials` | `True` 时响应会带 `Access-Control-Allow-Credentials`，允许浏览器发送 Cookie/Authorization 类凭证 |
| `allow_methods` | 允许的方法列表，如 `["GET","POST"]`；`"*"` 表示全部 |
| `allow_headers` | 允许的请求头；前端若发 `Authorization`、`Content-Type` 等，需被允许 |
| `expose_headers` | （可选）允许前端 JS 读取哪些响应头 |
| `max_age` | （可选）预检结果缓存秒数 |

### 14.6 重要坑

```python
# 危险/无效组合（浏览器规则）：
allow_origins=["*"]
allow_credentials=True
# 需要带 Cookie 时，allow_origins 必须写成具体源，不能 *
```

生产环境：把 `allow_origins` 写成你的真实前端域名列表，不要无脑 `"*"`。

---

## 15. `File` / `UploadFile` / `Form` 是什么？`UploadFile` 有哪些属性？

**一句话：** 三者都用于 **表单**（尤其 `multipart/form-data`），不是 JSON Body。

| 符号 | 作用 |
|------|------|
| `Form` | 声明普通表单字段（字符串、数字等） |
| `File` | 声明文件字段（可得到 `bytes` 或配合 UploadFile） |
| `UploadFile` | 文件的高级封装（流式、带文件名/类型），大文件更合适 |

```python
from fastapi import File, UploadFile, Form

@app.post("/upload")
async def upload(
    description: str = Form(...),          # 表单文本字段
    file: UploadFile = File(...),          # 表单文件字段
):
    content = await file.read()
    return {
        "filename": file.filename,
        "content_type": file.content_type,
        "size": len(content),
        "description": description,
    }
```

### `UploadFile` 常用属性/方法

| 属性/方法 | 含义 |
|-----------|------|
| `filename` | 上传时的文件名（可能为 `None`） |
| `content_type` | MIME 类型，如 `image/png` |
| `file` | 底层类文件对象（Starlette/`SpooledTemporaryFile`） |
| `headers` | 该文件部分的头 |
| `read(size)` | 异步读内容（`await file.read()`） |
| `write(data)` | 异步写 |
| `seek(pos)` | 移动指针 |
| `close()` | 关闭 |

小文件也可以：

```python
@app.post("/upload-bytes")
async def upload_bytes(file: Annotated[bytes, File()]):
    return {"size": len(file)}
```

但大文件优先 `UploadFile`，避免一次性进内存。

另：要用表单上传，需安装 `python-multipart`（`fastapi[standard]` 通常已包含）。

---

## 16. `del` 关键字做什么？哪里会用到？

**一句话：** `del` 用于 **删除名字绑定**（变量、下标元素、对象属性）；不是「销毁对象」的魔法，只是去掉引用。

### 16.1 常见用法

```python
# 1) 删除变量名（减少一次引用）
x = [1, 2, 3]
del x

# 2) 删除列表元素 / 切片
nums = [0, 1, 2, 3]
del nums[1]       # [0, 2, 3]
del nums[0:2]

# 3) 删除字典键（Todo 示例里就是这种）
db = {1: "a", 2: "b"}
del db[1]         # 等价于去掉键 1

# 4) 删除对象属性
del obj.attr
```

### 16.2 和 `dict.pop` 对比

```python
del db[todo_id]           # 键不存在 → KeyError
db.pop(todo_id, None)     # 键不存在 → 返回默认值，不炸
```

FastAPI demo 里先判断 `if todo_id not in db`，再 `del`，所以安全。

### 16.3 使用场景列表

- 从 `dict`/`list` 里移除元素
- 去掉对象上不想保留的属性
- 显式断开大对象引用（少数内存敏感场景）
- 实现 `__delitem__` 的容器类型支持 `del obj[key]`

注意：`del` **不会立刻保证** 内存回收；只是删除引用，回收由垃圾回收器决定。

---

## 17. 怎样处理请求头？如何验证 JWT？（讲义补强）

**一句话：** 用 `Header` 提取请求头，或用 `HTTPBearer`/`OAuth2PasswordBearer`；在 `Depends` 里解析校验 JWT，再注入当前用户。

### 17.1 读取自定义请求头

```python
from typing import Annotated
from fastapi import Header, HTTPException

@app.get("/demo-header")
def demo_header(
    x_token: Annotated[str | None, Header()] = None,
):
    # 客户端头：X-Token: abc
    # FastAPI 把 X-Token 转成参数名 x_token（大小写不敏感，- 变 _）
    return {"x_token": x_token}
```

### 17.2 Authorization: Bearer \<JWT\>

```python
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer()

def get_current_user(
    cred: Annotated[HTTPAuthorizationCredentials, Depends(security)],
):
    token = cred.credentials  # Bearer 后面那一串
    user = decode_and_verify_jwt(token)  # 你自己的解析函数
    if user is None:
        raise HTTPException(status_code=401, detail="无效令牌")
    return user

@app.get("/me")
def me(user=Depends(get_current_user)):
    return user
```

### 17.3 最小 JWT 示意（教学用）

```python
# pip install PyJWT
import jwt
from datetime import datetime, timedelta, timezone

SECRET = "change-me"
ALGO = "HS256"

def create_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(hours=2),
    }
    return jwt.encode(payload, SECRET, algorithm=ALGO)

def decode_and_verify_jwt(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGO])
        return {"id": int(payload["sub"])}
    except jwt.PyJWTError:
        return None
```

### 17.4 为什么讲义主文没展开？

主线先抓：路由、Pydantic、Depends、异常。  
鉴权是 Depends + Header/Security 的组合拳，放在答疑/进阶更合适。  
**模式记住：**

> **Security 方案提取 token → Depends 里验签 → raise 401/403 → 路由只拿「当前用户」。**

---

## 附：把 17 问压成一张复习卡

| # | 结论 |
|---|------|
| 1 | Starlette = FastAPI 的 Web 底层 |
| 2 | uvicorn = 跑 ASGI 应用的服务器 |
| 3 | `包[extra]` = 官方可选依赖套装 |
| 4 | Path/Query 都注入参数；看是否在 `{}` 里；要加校验再用 `Query` |
| 5 | `status_code=201` 改的是成功默认状态码 |
| 6 | `HTTPException` 由框架转成 HTTP 错误响应 |
| 7 | `exception_handler` = 自定义异常 → 统一 HTTP 出口 |
| 8 | `Depends` 元数据由 FastAPI 读；返回值默认不靠注解做深度校验 |
| 9 | `yield` 依赖可在请求后清理；`finally` 保清理；失败不返回 None |
| 10 | `from routers import users` 是正规包导入 |
| 11 | `with` 管资源生命周期；异步用 `async with` |
| 12 | `raise_for_status` 抛客户端库异常；需自己转 `HTTPException` |
| 13 | HTTP 中间件拿 `request` + `call_next` |
| 14 | CORS 是浏览器同源策略；用 `CORSMiddleware` 放行前端源 |
| 15 | `Form`/`File`/`UploadFile` 处理表单上传 |
| 16 | `del` 删绑定/元素；`del db[id]` 删字典键 |
| 17 | 请求头用 `Header`/`HTTPBearer`，JWT 放 Depends 里验 |

---

*建议阅读顺序：本答疑 → 回看 `fastapi.md` 对应章节 → 在 `fastapi_demo` 里改一版 Header 鉴权试手。*
