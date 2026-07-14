# FastAPI 教学讲义

> 前置知识：Python 基础、类型注解、Pydantic（见 `pydantic.md`）  
> 目标：能独立写一个带校验、路由分层、依赖注入的 REST API  
> 答疑精讲：读完有疑问先看 [`fastapi_faq.md`](./fastapi_faq.md)（Starlette/uvicorn、Path vs Query、全局异常、Depends、CORS、JWT 等 17 问）

---

## 0. 为什么学 FastAPI？

做 AI / 后端时，你经常需要：

- 把 LLM 封装成 HTTP 接口给前端调用
- 接收 JSON、校验参数、返回结构化结果
- 自动生成接口文档（Swagger）

FastAPI 的核心优势：

| 特点 | 含义 |
|------|------|
| 基于类型注解 | 参数类型写清楚，框架自动校验 |
| 原生异步 | `async def`，适合 IO 密集（调 LLM、查库） |
| 自动文档 | 访问 `/docs` 就有可交互的 API 文档 |
| 深度整合 Pydantic | 请求体 / 响应体都用模型描述 |

一句话：**FastAPI = Starlette（高性能 Web） + Pydantic（数据校验）**。

---

## 1. 环境安装与第一个接口

### 1.1 安装

```bash
pip install fastapi uvicorn
# 或（推荐锁定环境）
pip install "fastapi[standard]"
```

- `fastapi`：框架本身
- `uvicorn`：ASGI 服务器（负责真正监听端口、收发 HTTP）

### 1.2 Hello World

```python
# main.py
from fastapi import FastAPI

app = FastAPI(title="我的第一个 API", version="0.1.0")

@app.get("/")
def root():
    return {"message": "Hello FastAPI"}
```

**怎么读：**

```
app = FastAPI(...)     → 创建应用实例（整个 API 的入口）
@app.get("/")          → 装饰器：注册「GET /」路由
def root():            → 处理函数，返回值会自动转成 JSON
```

### 1.3 启动

```bash
uvicorn main:app --reload --port 8000
```

**命令拆解：**

```
uvicorn        → ASGI 服务器
main:app       → 模块名:变量名（main.py 里的 app）
--reload       → 改代码自动重启（开发用）
--port 8000    → 端口
```

打开：

- 接口：http://127.0.0.1:8000/
- 交互文档：http://127.0.0.1:8000/docs
- 备用文档：http://127.0.0.1:8000/redoc

---

## 2. 路由与 HTTP 方法

### 2.1 常见方法

| 装饰器 | 语义 | 典型场景 |
|--------|------|----------|
| `@app.get` | 查询 | 获取列表 / 详情 |
| `@app.post` | 创建 | 新建资源、提交表单 |
| `@app.put` | 整体更新 | 替换整条记录 |
| `@app.patch` | 部分更新 | 只改几个字段 |
| `@app.delete` | 删除 | 删除资源 |

```python
@app.get("/users")
def list_users():
    return [{"id": 1, "name": "Alice"}]

@app.post("/users")
def create_user():
    return {"ok": True}
```

### 2.2 路径参数（Path）

```python
@app.get("/users/{user_id}")
def get_user(user_id: int):
    return {"user_id": user_id}
```

**怎么读：**

- URL 里的 `{user_id}` 会注入到函数参数
- `user_id: int` → 自动把字符串转成 int；转不了会 **422 校验错误**

访问 `/users/42` → `{"user_id": 42}`  
访问 `/users/abc` → 报错（不是整数）

### 2.3 查询参数（Query）

URL 里 `?` 后面的就是查询参数：`/items?q=phone&limit=10`

```python
from typing import Annotated
from fastapi import Query

@app.get("/items")
def search_items(
    q: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
):
    return {"q": q, "limit": limit}
```

**怎么读：**

- 不在路径里出现的参数 → 默认当 Query
- `q: str | None = None` → 可选；不传就是 `None`
- `Query(ge=1, le=100)` → 限制范围（大于等于 1，小于等于 100）

---

## 3. 请求体与 Pydantic（重点）

FastAPI 最强的地方：**用 Pydantic 模型描述请求体**。

### 3.1 基本请求体

```python
from pydantic import BaseModel, Field, EmailStr

class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=20)
    email: EmailStr
    age: int = Field(ge=0, le=150)

@app.post("/users")
def create_user(user: UserCreate):
    # user 已经是校验通过的对象
    return {"username": user.username, "email": user.email}
```

**怎么读：**

1. 客户端发 JSON：`{"username":"bob","email":"a@b.com","age":20}`
2. FastAPI 看到参数类型是 `BaseModel` 子类 → 当作 **请求体（Body）**
3. 自动解析 + 校验；失败返回 422 和详细错误

这和你在 `pydantic.md` 里学的完全一致，只是挂到了 HTTP 入口上。

### 3.2 响应模型（Response Model）

控制「返回给客户端什么字段」——别把密码之类的漏出去。

```python
class UserOut(BaseModel):
    id: int
    username: str
    email: EmailStr

@app.post("/users", response_model=UserOut)
def create_user(user: UserCreate):
    # 内部可以有更多字段；response_model 会过滤
    return {"id": 1, "username": user.username, "email": user.email, "password": "secret"}
    # 实际响应里不会有 password
```

### 3.3 多模型分层（推荐习惯）

| 模型 | 用途 |
|------|------|
| `XxxCreate` | 创建时客户端提交的字段 |
| `XxxUpdate` | 更新时允许改的字段 |
| `XxxOut` / `XxxRead` | 返回给客户端的字段 |
| `XxxInDB` | 数据库里存的完整结构 |

---

## 4. 状态码与异常处理

### 4.1 指定成功状态码

```python
from fastapi import status

@app.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate):
    return user
```

### 4.2 主动抛业务错误

```python
from fastapi import HTTPException

fake_db = {1: {"id": 1, "name": "Alice"}}

@app.get("/users/{user_id}")
def get_user(user_id: int):
    if user_id not in fake_db:
        raise HTTPException(status_code=404, detail="用户不存在")
    return fake_db[user_id]
```

**怎么读：** `raise HTTPException(...)` → FastAPI 转成对应 HTTP 响应，不是让程序崩溃。

### 4.3 全局异常（进阶）

```python
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})
```

---

## 5. 依赖注入（Dependency Injection）

这是 FastAPI 的「灵魂功能」之一。把「取当前用户 / 开数据库连接」等逻辑抽成依赖，多个路由复用。

### 5.1 最简单的依赖

```python
from fastapi import Depends

def common_params(skip: int = 0, limit: int = 10):
    return {"skip": skip, "limit": limit}

@app.get("/items")
def read_items(commons: dict = Depends(common_params)):
    return commons
```

**怎么读：**

```
Depends(common_params)
    → 先执行 common_params(...)
    → 把返回值注入到 commons
```

访问 `/items?skip=5&limit=20` 时，`common_params` 会先吃到 query 参数。

### 5.2 模拟「当前登录用户」

```python
from typing import Annotated

def get_current_user(token: str = Query(...)):
    if token != "secret-token":
        raise HTTPException(status_code=401, detail="未授权")
    return {"id": 1, "name": "Alice"}

CurrentUser = Annotated[dict, Depends(get_current_user)]

@app.get("/me")
def read_me(user: CurrentUser):
    return user
```

生产环境会换成 Header 里的 JWT；模式一样：`Depends` + 校验 + `HTTPException`。

### 5.3 依赖的依赖（可嵌套）

```python
def get_db():
    db = {"conn": "fake-db"}
    try:
        yield db          # yield：用完后还能清理
    finally:
        print("关闭连接")

def get_user_repo(db=Depends(get_db)):
    return {"db": db}

@app.get("/profile")
def profile(repo=Depends(get_user_repo)):
    return repo
```

`yield` 版依赖 ≈ 上下文管理器：请求结束会执行 `finally`。

---

## 6. 路由拆分：APIRouter

项目一大，不要全写在 `main.py`。

```
app/
  main.py
  routers/
    users.py
    items.py
  schemas/
    user.py
```

`routers/users.py`：

```python
from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/")
def list_users():
    return [{"id": 1}]

@router.get("/{user_id}")
def get_user(user_id: int):
    return {"id": user_id}
```

`main.py`：

```python
from fastapi import FastAPI
from routers import users

app = FastAPI()
app.include_router(users.router)
```

**怎么读：**

- `prefix="/users"` → 路由自动变成 `/users/`、`/users/{id}`
- `tags=["users"]` → `/docs` 里分组显示
- `include_router` → 把子路由挂到主应用

---

## 7. 异步接口 async / await

调 LLM、读网络、查数据库都是 **IO 等待**。用异步可以让服务器在等待时去处理别的请求。

```python
import httpx

@app.get("/weather/{city}")
async def weather(city: str):
    async with httpx.AsyncClient() as client:
        # 这里是示例 URL，真实项目换你的 API
        r = await client.get(f"https://httpbin.org/get", params={"city": city})
        r.raise_for_status()
        return r.json()
```

**规则心智模型：**

| 函数类型 | 适合做什么 |
|----------|------------|
| `def` | CPU 计算、同步库、简单 CRUD（内存/SQLite 同步） |
| `async def` | `await` 网络请求、异步数据库、异步文件 IO |

注意：在 `async def` 里不要写阻塞的 `time.sleep()` / 同步 `requests.get()`，会卡住事件循环。阻塞操作用 `asyncio.to_thread(...)` 或换异步库。

---

## 8. 中间件与 CORS

### 8.1 简单计时中间件

```python
import time
from fastapi import Request

@app.middleware("http")
async def add_process_time(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    cost = time.perf_counter() - start
    response.headers["X-Process-Time"] = str(cost)
    return response
```

**怎么读：** 每个请求都先经过中间件 → `call_next` 进路由 → 回来还能改响应头。

### 8.2 跨域（前端联调必备）

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # 前端地址
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

浏览器从 `localhost:5173` 调 `localhost:8000` 会跨域；不加 CORS 会被拦。

---

## 9. 文件上传与表单

```python
from fastapi import File, UploadFile, Form

@app.post("/upload")
async def upload(
    description: str = Form(...),
    file: UploadFile = File(...),
):
    content = await file.read()
    return {
        "filename": file.filename,
        "content_type": file.content_type,
        "size": len(content),
        "description": description,
    }
```

`UploadFile` 适合大文件（流式），不要一上来就 `file.file.read()` 读爆内存。

---

## 10. 一个迷你实战：待办事项 API

下面把前面知识点串起来（完整可运行代码见同目录 `fastapi_demo/`）。

### 10.1 数据模型

```python
from pydantic import BaseModel, Field

class TodoCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    done: bool = False

class TodoOut(TodoCreate):
    id: int
```

### 10.2 内存 CRUD

```python
from fastapi import FastAPI, HTTPException

app = FastAPI(title="Todo API")
db: dict[int, TodoOut] = {}
next_id = 1

@app.post("/todos", response_model=TodoOut, status_code=201)
def create_todo(todo: TodoCreate):
    global next_id
    item = TodoOut(id=next_id, **todo.model_dump())
    db[next_id] = item
    next_id += 1
    return item

@app.get("/todos", response_model=list[TodoOut])
def list_todos(done: bool | None = None):
    items = list(db.values())
    if done is not None:
        items = [t for t in items if t.done == done]
    return items

@app.get("/todos/{todo_id}", response_model=TodoOut)
def get_todo(todo_id: int):
    if todo_id not in db:
        raise HTTPException(404, detail="Todo 不存在")
    return db[todo_id]

@app.patch("/todos/{todo_id}", response_model=TodoOut)
def update_todo(todo_id: int, todo: TodoCreate):
    if todo_id not in db:
        raise HTTPException(404, detail="Todo 不存在")
    updated = TodoOut(id=todo_id, **todo.model_dump())
    db[todo_id] = updated
    return updated

@app.delete("/todos/{todo_id}", status_code=204)
def delete_todo(todo_id: int):
    if todo_id not in db:
        raise HTTPException(404, detail="Todo 不存在")
    del db[todo_id]
```

**练习建议：**

1. 用 `/docs` 把五条接口都点一遍
2. 把 `db` 改成读写 JSON 文件
3. 加 `Depends`：只有带正确 token 才能 `DELETE`

---

## 11. 和 AI 项目怎么结合？

典型模式：FastAPI 包一层 LLM。

```python
from pydantic import BaseModel, Field

class ChatIn(BaseModel):
    message: str = Field(min_length=1)
    temperature: float = Field(default=0.7, ge=0, le=2)

class ChatOut(BaseModel):
    reply: str

@app.post("/chat", response_model=ChatOut)
async def chat(body: ChatIn):
    # 伪代码：调用你已有的 ask_llm / OpenAI SDK
    reply = await call_llm(body.message, temperature=body.temperature)
    return ChatOut(reply=reply)
```

你 week1 里的 `llm.py`、token 统计、摘要逻辑，都可以变成：

- `POST /chat`
- `POST /summarize`
- `GET /health`

前端或其它服务只负责 HTTP，模型细节藏在服务端。

---

## 12. 常见坑（老师最常改的）

1. **路径顺序**：固定路径写在动态路径前面  
   `GET /users/me` 要写在 `GET /users/{user_id}` 之前，否则 `me` 会被当成 id。

2. **可变默认参数**：别写 `tags: list = []`，用 `Field(default_factory=list)`。

3. **异步里调用同步阻塞库**：`requests` 会卡住；改用 `httpx.AsyncClient`。

4. **忘记 `response_model`**：容易把内部字段（密码、token）返回出去。

5. **422 不是你业务 404**：422 = 参数校验失败；先看响应里的 `detail` 数组。

6. **`main:app` 写错**：模块路径不对会导致 `Could not import module`。

---

## 13. 学习路径（建议一周）

| 天 | 目标 |
|----|------|
| Day 1 | 安装、Hello World、`/docs`、Path / Query |
| Day 2 | Pydantic 请求体 + response_model + HTTPException |
| Day 3 | APIRouter 拆分 + Depends |
| Day 4 | async + httpx；给 LLM 包一个 `/chat` |
| Day 5 | CORS、中间件、Todo 小项目收尾 |

---

## 14. 速查表

| 想做的事 | 写法 |
|----------|------|
| 定义应用 | `app = FastAPI()` |
| GET 路由 | `@app.get("/path")` |
| 路径参数 | `/items/{id}` + `id: int` |
| 查询参数 | 函数参数（或不在 Path 里的参数） |
| JSON 请求体 | 参数类型为 `BaseModel` 子类 |
| 限制查询参数 | `Query(ge=1, le=100)` |
| 依赖注入 | `Depends(func)` |
| 业务错误 | `raise HTTPException(status_code, detail)` |
| 挂子路由 | `app.include_router(router)` |
| 启动 | `uvicorn main:app --reload` |
| 文档 | `/docs` |

---

## 15. 下一步

学完本讲义后，建议继续：

1. **SQLAlchemy / SQLModel**：把内存 `dict` 换成真数据库  
2. **JWT 鉴权**：`python-jose` / `PyJWT` + OAuth2PasswordBearer  
3. **测试**：`pytest` + `TestClient` / `httpx.AsyncClient`  
4. **部署**：Docker + uvicorn / gunicorn workers

---

*讲义对应示例代码：`fastapi_demo/`*  
*答疑精讲：`fastapi_faq.md`*  
*相关前置：`pydantic.md`、`started_with_python.md`、`python_modes.md`*
