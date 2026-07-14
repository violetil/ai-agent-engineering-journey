"""
FastAPI 教学示例：待办事项 API + Header/JWT 鉴权演示
启动（在 fastapi_demo 目录）：
  uvicorn main:app --reload --port 8000
文档：http://127.0.0.1:8000/docs

说明：
- Todo 的 DELETE 仍可用 query token=secret-token（演示 Depends）
- /auth/login 发放演示用 JWT
- /auth/me 从 Authorization: Bearer <token> 读取并校验
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

app = FastAPI(
    title="Todo API 教学示例",
    description="配合 fastapi.md / fastapi_faq.md 的迷你实战",
    version="0.2.0",
)

# 仅教学用，生产环境务必换掉并放进环境变量
JWT_SECRET = "fastapi-demo-secret"
JWT_ALG = "HS256"


# ---------- Schemas ----------
class TodoCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100, examples=["学习 FastAPI"])
    done: bool = False


class TodoOut(TodoCreate):
    id: int


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    name: str


# ---------- In-memory DB ----------
db: dict[int, TodoOut] = {}
_next_id = 1


# ---------- Dependencies ----------
def get_token(
    token: Annotated[str | None, Query(description="演示用：正确值为 secret-token")] = None,
) -> str | None:
    return token


def require_token(token: Annotated[str | None, Depends(get_token)]) -> str:
    """删除接口需要 token，演示 Depends + HTTPException。"""
    if token != "secret-token":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要 query 参数 token=secret-token",
        )
    return token


def _try_import_jwt():
    try:
        import jwt  # PyJWT
    except ImportError as e:  # pragma: no cover
        raise HTTPException(
            status_code=500,
            detail="缺少 PyJWT：请执行 pip install PyJWT",
        ) from e
    return jwt


def create_access_token(user_id: int, name: str) -> str:
    jwt = _try_import_jwt()
    payload = {
        "sub": str(user_id),
        "name": name,
        "exp": datetime.now(timezone.utc) + timedelta(hours=2),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


security = HTTPBearer(auto_error=False)


def get_current_user(
    cred: Annotated[HTTPAuthorizationCredentials | None, Depends(security)] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> UserOut:
    """
    演示两种读请求头的方式（实际项目选一种即可）：
    1) HTTPBearer → Authorization: Bearer <jwt>
    2) 原始 Header → authorization 字符串（了解 Header 注入）
    """
    token: str | None = None
    if cred is not None:
        token = cred.credentials
    elif authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少 Authorization: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    jwt = _try_import_jwt()
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        return UserOut(id=int(payload["sub"]), name=str(payload.get("name", "")))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"无效令牌: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


CurrentUser = Annotated[UserOut, Depends(get_current_user)]


# ---------- Routes ----------
@app.get("/", tags=["health"])
def root():
    return {
        "message": "Todo API is running",
        "docs": "/docs",
        "auth": {"login": "POST /auth/login", "me": "GET /auth/me"},
    }


@app.post("/auth/login", response_model=TokenOut, tags=["auth"])
def login(username: str = Query(default="Alice", description="演示：任意用户名")):
    """教学登录：不查库，直接发 JWT。"""
    token = create_access_token(user_id=1, name=username)
    return TokenOut(access_token=token)


@app.get("/auth/me", response_model=UserOut, tags=["auth"])
def read_me(user: CurrentUser):
    """需要请求头 Authorization: Bearer <access_token>。"""
    return user


@app.post(
    "/todos",
    response_model=TodoOut,
    status_code=status.HTTP_201_CREATED,
    tags=["todos"],
)
def create_todo(todo: TodoCreate):
    global _next_id
    item = TodoOut(id=_next_id, **todo.model_dump())
    db[_next_id] = item
    _next_id += 1
    return item


@app.get("/todos", response_model=list[TodoOut], tags=["todos"])
def list_todos(done: bool | None = None):
    items = list(db.values())
    if done is not None:
        items = [t for t in items if t.done is done]
    return items


@app.get("/todos/{todo_id}", response_model=TodoOut, tags=["todos"])
def get_todo(todo_id: int):
    if todo_id not in db:
        raise HTTPException(status_code=404, detail="Todo 不存在")
    return db[todo_id]


@app.patch("/todos/{todo_id}", response_model=TodoOut, tags=["todos"])
def update_todo(todo_id: int, todo: TodoCreate):
    if todo_id not in db:
        raise HTTPException(status_code=404, detail="Todo 不存在")
    updated = TodoOut(id=todo_id, **todo.model_dump())
    db[todo_id] = updated
    return updated


@app.delete(
    "/todos/{todo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["todos"],
)
def delete_todo(
    todo_id: int,
    _: Annotated[str, Depends(require_token)],
):
    if todo_id not in db:
        raise HTTPException(status_code=404, detail="Todo 不存在")
    del db[todo_id]
