"""
FastAPI 教学示例：待办事项 API
启动：
  uvicorn week3_python_ablilities.fastapi_demo.main:app --reload --port 8000
或在本目录下：
  uvicorn main:app --reload --port 8000
文档：http://127.0.0.1:8000/docs
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status
from pydantic import BaseModel, Field

app = FastAPI(
    title="Todo API 教学示例",
    description="配合 fastapi.md 讲义的迷你实战",
    version="0.1.0",
)


# ---------- Schemas ----------
class TodoCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100, examples=["学习 FastAPI"])
    done: bool = False


class TodoOut(TodoCreate):
    id: int


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


# ---------- Routes ----------
@app.get("/", tags=["health"])
def root():
    return {"message": "Todo API is running", "docs": "/docs"}


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
