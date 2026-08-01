# Python / FastAPI 教学讲义：身份认证与授权

> 前置知识：`password_security.md`（密码哈希）、`fastapi.md`（Depends / Header）、一点 HTTP  
> 相关实践：`ai_service/`（注册登录）、`fastapi_demo/`（Bearer JWT 演示）  
> 目标：分清认证与授权；理解 Session / JWT；能在 FastAPI 里做登录发令牌 + 保护路由

---

## 0. 先立三句话

1. **认证（Authentication，AuthN）**：你是谁？——验身份  
2. **授权（Authorization，AuthZ）**：你能做什么？——验权限  
3. **登录成功 ≠ 以后每次都再传密码**——通常换成 **令牌 / 会话**，后续请求出示它

口诀：

> **先认证，后授权。**  
> **密码用来证明身份一次；令牌用来代表身份一段时间。**

---

## 1. 为什么需要认证与授权？

没有认证时：

```text
任何人 → POST /chat/completions → 花掉你的 DeepSeek 额度
```

只有认证、没有授权时：

```text
用户 A 登录成功 → DELETE /users/B 的数据  → 越权
```

做成互联网服务时，几乎总要回答两个问题：

| 问题 | 对应 |
|------|------|
| 这个请求是谁发的？ | 认证 |
| 这个人是否允许做这件事？ | 授权 |

---

## 2. 认证 vs 授权（务必分清）

| | 认证 Authentication | 授权 Authorization |
|--|---------------------|--------------------|
| 英文缩写 | AuthN | AuthZ |
| 问句 | Who are you? | What are you allowed to do? |
| 失败常见状态码 | **401 Unauthorized**（未认证/令牌无效） | **403 Forbidden**（已认证但没权限） |
| 例子 | 邮箱密码登录、校验 JWT | 仅 admin 能删用户；只能改自己的订单 |

注意命名坑：HTTP 里 401 叫 Unauthorized，语义上更接近 **未认证**；没权限其实更常是 403。

```text
没带令牌 / 令牌假的     → 401
令牌有效，但是普通用户删全库 → 403
```

---

## 3. 一次完整登录链路（心智模型）

```text
① 注册
   密码 → bcrypt 哈希 → 存 password_hash
   （见 password_security.md）

② 登录（认证）
   邮箱 + 密码
   → verify_password
   → 成功：签发「凭证」（Session ID 或 JWT）
   → 失败：401

③ 访问受保护接口
   请求携带凭证（Cookie 或 Authorization 头）
   → 服务端识别出当前用户（认证）
   → 检查是否有权执行该操作（授权）
   → 放行或 401/403

④ 登出 / 过期
   凭证失效，需重新登录
```

你现在的 `ai_service` 多半完成了 ① 和「验密码」的一部分；  
本讲重点补齐 ②③： **令牌怎么发、怎么带、怎么验、怎么做权限。**

---

## 4. 两种主流会话方案

### 4.1 Session（服务端会话）

```text
登录成功
  → 服务器创建 session，存「用户 id」等
  → 给浏览器 Set-Cookie: session_id=xxx

之后请求自动带 Cookie
  → 服务器用 session_id 查表，找回用户
```

特点：

- 服务器要存会话（内存 / Redis / DB）  
- 容易主动登出（删掉 session 即可）  
- 浏览器场景很经典  

### 4.2 JWT（JSON Web Token，常见无状态方案）

```text
登录成功
  → 服务器用密钥「签名」生成一串 token
  → 返回给客户端：{"access_token":"...", "token_type":"bearer"}

之后请求
  → Header: Authorization: Bearer <token>
  → 服务器验签 + 检查过期 → 解析出用户 id
```

特点：

- 服务器可不存会话（无状态，易扩展）  
- 默认难以「立刻作废某一枚已发出的 token」（除非黑名单/短过期+刷新）  
- API / 移动端 / SPA 非常常见  

本讲义以 **JWT + Bearer** 为主（和 FastAPI / AI API 服务最搭）。

---

## 5. JWT 到底是什么？

JWT 通常长这样（三段，用 `.` 连接）：

```text
xxxxx.yyyyy.zzzzz
Header.Payload.Signature
```

| 段 | 含义 |
|----|------|
| Header | 算法等元数据，如 `HS256` |
| Payload | 声明（claims）：用户 id、过期时间 `exp` 等 |
| Signature | 用服务器密钥对前两段做签名，防篡改 |

### 5.1 重要真相

1. **默认 Payload 不是加密的**——用 Base64 解码往往能看见内容  
   → **不要把密码放进 JWT**  
2. 安全核心是 **签名**：没有密钥就难以伪造合法 token  
3. 一定要设 **过期时间 `exp`**

### 5.2 常见 claims

| 字段 | 含义 |
|------|------|
| `sub` | subject，常用用户 id |
| `exp` | 过期时间（UTC 时间戳） |
| `iat` | 签发时间 |
| `role` / `scopes` | 可选，放粗粒度角色或权限提示 |

---

## 6. HTTP 里怎么携带身份？

### 6.1 Authorization Bearer（API 最常见）

```http
GET /auth/me HTTP/1.1
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

FastAPI 可用：

- `Header` 自己拆 `Authorization`  
- 或 `HTTPBearer` / `OAuth2PasswordBearer`（更省事、文档更友好）

### 6.2 Cookie

浏览器自动带；要注意 CSRF。前后端分离 API 课设阶段更常见 Bearer。

### 6.3 不要把长期 token 放进 URL Query

```text
❌ /chat?token=xxxxx
```

易进日志、历史记录、代理记录。教学 demo 可以，生产不要。

---

## 7. FastAPI 实战：登录发 JWT + 保护路由

> 依赖：`PyJWT`、`bcrypt`（密码哈希见上一讲）  
> `pip install PyJWT bcrypt`

### 7.1 配置与工具函数

```python
# app/core/security.py
from datetime import datetime, timedelta, timezone
import jwt
from pwd_helpers import verify_password  # 你的 bcrypt 封装

SECRET_KEY = "change-me-in-env"  # 必须放环境变量
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


def create_access_token(subject: str, expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES) -> str:
    payload = {
        "sub": subject,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
```

**怎么读：**

- `sub`：放用户唯一标识（如 email 或 user id）  
- `jwt.encode`：签发  
- `jwt.decode`：验签 + 校验 `exp`；失败抛异常  

### 7.2 登录接口：成功返回 token，失败 401

```python
from pydantic import BaseModel

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


@app.post("/auth/sign_in", response_model=TokenOut)
def sign_in(body: SignInIn):
    user = get_user_by_email(body.email)
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")

    token = create_access_token(subject=user.email)
    return TokenOut(access_token=token)
```

对比不良写法：

```python
return True   # 合法 JSON，但没有「后续怎么证明身份」
```

### 7.3 依赖注入：解析「当前用户」

```python
from typing import Annotated
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer()


def get_current_user(
    cred: Annotated[HTTPAuthorizationCredentials, Depends(security)],
):
    token = cred.credentials
    try:
        payload = decode_access_token(token)
        email = payload.get("sub")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="无效或过期的令牌")

    user = get_user_by_email(email)
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


CurrentUser = Annotated[UserRecord, Depends(get_current_user)]
```

### 7.4 保护业务路由

```python
@app.post("/chat/completions")
async def chat(body: ChatIn, user: CurrentUser):
    # 到这里：一定已登录
    # 可按 user.email 做限流、记账、隔离数据
    return await ask_llm(body.prompt)
```

未带 token / token 错误 → 在 `Depends` 阶段就被 401拦下，进不了业务函数。

---

## 8. 授权：登录之后还要问「能不能」

认证只解决「是合法用户」。授权例子：

### 8.1 角色（RBAC 入门）

```text
role = "user" | "admin"
```

```python
def require_admin(user: CurrentUser):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


@app.delete("/users/{email}")
def delete_user(email: str, _: Annotated[UserRecord, Depends(require_admin)]):
    ...
```

### 8.2 资源归属（最常见）

```python
@app.get("/todos/{todo_id}")
def get_todo(todo_id: int, user: CurrentUser):
    todo = db.get(todo_id)
    if todo is None:
        raise HTTPException(404, detail="不存在")
    if todo.owner_email != user.email:
        raise HTTPException(403, detail="不能查看他人数据")
    return todo
```

心智：

```text
401：你还没证明自己 / 证明无效
403：系统认识你，但这件事不属于你的权限
404：也可以在「资源存在但不属于你」时统一返回 404，防探测（进阶策略）
```

---

## 9. 和密码、HTTPS、CORS 的关系

| 层级 | 作用 |
|------|------|
| HTTPS/TLS | 防传输途中被窃听（密码、token 都怕明文信道） |
| 密码哈希 | 防数据库泄露后直接拿原文 |
| JWT 签名密钥 | 防伪造令牌 |
| CORS | 浏览器跨域是否允许前端读响应（不是认证本身） |

常见误解：

- 「有了 JWT 就不用哈希密码」→ 错，登录仍要哈希校验  
- 「JWT 是加密的」→ 默认多是签名，Payload 可读  
- 「CORS 配好了就安全了」→ CORS 不替代鉴权  

---

## 10. 状态码速查（认证授权场景）

| 状态码 | 场景 |
|--------|------|
| 200 | 登录成功并返回 token；或受保护接口成功 |
| 201 | 注册成功 |
| 401 | 未登录、密码错误、token 无效/过期 |
| 403 | 已登录但权限不足 |
| 409 | 注册时邮箱已存在（可选） |
| 422 | 参数校验失败（邮箱格式、密码太短） |

登录失败时：

```text
建议：邮箱不存在 和 密码错误 用同一句「邮箱或密码错误」
目的：降低账号枚举风险
```

---

## 11. 安全实践清单（做项目够用）

1. **密钥放环境变量**，不要写死进 git（`SECRET_KEY` / `JWT_SECRET`）  
2. Token **设过期**；越权接口用短过期更稳妥  
3. 密码只走哈希；token 不含密码  
4. 受保护路由统一 `Depends(get_current_user)`，不要每个函数手写复制粘贴漏检  
5. 授权检查「资源归属」，不要只检查「是否登录」  
6. 生产环境必须 HTTPS  
7. 前端把 token 放内存或稳妥存储策略；注意 XSS 偷 token  
8. 日志不要打印完整 token / 密码  

---

## 12. 对照改造 `ai_service`（练习路径）

若当前登录仍类似：

```python
@app.post("/auth/sign_in")
def sign_in(input: SignInIn) -> bool:
    return login(input)  # True/False
```

建议演进顺序：

| 步 | 目标 |
|----|------|
| 1 | `login` 失败抛异常或返回明确失败；路由层统一 401 |
| 2 | 成功返回 `TokenOut`，不再返回裸 `bool` |
| 3 | 新增 `get_current_user` 依赖 |
| 4 | 给 `/chat/*` 加上 `CurrentUser` |
| 5 | （可选）`UserRecord.role` + 管理员接口 403 |
| 6 | （可选）刷新令牌、登出黑名单——进阶再做 |

文件建议：

```text
app/
  core/
    security.py          # JWT 签发/校验
  api/deps.py            # get_current_user
  services/auth_service.py
  schemas/auth.py        # TokenOut, UserCreate, UserOut...
```

---

## 13. 最小端到端示意

```text
1) POST /auth/sign_up
   {"email":"a@b.com","username":"A","password":"secret123"}
   → 201 {"email":"a@b.com","username":"A"}

2) POST /auth/sign_in
   {"email":"a@b.com","password":"secret123"}
   → 200 {"access_token":"eyJ...","token_type":"bearer"}

3) POST /chat/completions
   Header: Authorization: Bearer eyJ...
   Body: {"prompt":"你好"}
   → 200 模型回复

4) 同请求不带 Header
   → 401
```

---

## 14. 常见错误（Code Review 必抓）

1. 登录返回 `true/false`，却没有任何后续凭证  
2. 聊天接口忘记加 `Depends`，等于裸奔  
3. JWT 密钥写死为 `123456` 还提交到 GitHub  
4. 不设 `exp`，token 永久有效  
5. 把 `role=admin` 只藏在前端；后端不校验  
6. 混淆 401 / 403  
7. 在 JWT 里塞密码或过多隐私  
8. 用 Query 传递长期 token  

---

## 15. 动手练习

1. 画一张序列图：登录 → 带 Bearer 访问 `/me`  
2. 用 `PyJWT` 签发 1 分钟过期的 token，过期后请求应 401  
3. 把 `ai_service` 的 `sign_in` 改成返回 `TokenOut`  
4. 增加 `GET /auth/me`，返回当前用户 `UserOut`（不含密码哈希）  
5. 给聊天路由加鉴权；无 token 时确认是 401 不是 500  
6. （进阶）普通用户不能删别人资源，断言 403  

---

## 16. 速查表

| 概念 | 一句话 |
|------|--------|
| 认证 | 你是谁 |
| 授权 | 你能做什么 |
| Session | 服务端存会话，Cookie 持 id |
| JWT | 客户端持签名令牌，服务端验签 |
| Bearer | `Authorization: Bearer <token>` |
| 401 | 未认证 / 令牌无效 |
| 403 | 已认证但无权限 |
| Depends | FastAPI 注入当前用户的最佳位置 |
| 密码哈希 | 登录时验证身份，不是令牌本身 |

---

## 17. 下一步学什么？

1. OAuth2 / 第三方登录（用 GitHub/Google 登录）概念  
2. Refresh Token + Access Token 双令牌  
3. RBAC / 权限表设计  
4. API Key（给程序用）与用户 JWT（给人用）的区别  
5. 率限流：按用户维度保护 LLM 额度  

---

*相关讲义：`password_security.md`、`fastapi.md`、`fastapi_faq.md`（Header/JWT 问）*  
*相关代码：`ai_service/`、`fastapi_demo/`*
