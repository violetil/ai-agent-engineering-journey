# Python 教学讲义：加密、用户密码存储与显示

> 前置知识：函数、字典/JSON、Pydantic 基础（见 `pydantic.md`）、一点 FastAPI  
> 相关实践：`ai_service/`（当前若仍明文存密码，学完本讲可对照改造）  
> 目标：分清编码 / 加密 / 哈希；会用 bcrypt 做注册哈希与登录校验；接口永不回显密码原文  
> 答疑精讲：[`password_security_faq.md`](./password_security_faq.md)（base64、盐、SHA-256、hashlib、encode、彩虹表/撞库、bcrypt/passlib、hashpw/checkpw）

---

## 0. 三条铁律（先背下来）

1. **用户密码只做哈希存储，不做可逆加密存储。**
2. **任何时候都不要把密码原文返回给前端，也不要写进日志。**
3. **登录时：对用户输入做校验函数比对哈希；永远不要「解密密码再比较」。**

一句话：

> **密码不是「锁进保险箱以后还能取出来」，而是「留下指纹，以后只对指纹」。**

---

## 1. 编码、加密、哈希：先别混

口语里常说「密码加密」，专业上要分开：

| 概念 | 可否还原 | 典型用途 | 例子 |
|------|----------|----------|------|
| **编码 Encoding** | 可以（不是保密） | 传输/表示 | Base64、URL encoding |
| **加密 Encryption** | 可以（有密钥就能解密） | 保密数据、通信 | AES、RSA、TLS |
| **哈希 Hashing** | **不可以**（单向） | 密码存储、完整性校验 | SHA-256、bcrypt、Argon2 |

### 1.1 编码不是加密

```python
import base64

password = "violet123"
print(base64.b64encode(password.encode()).decode())
# dmlvbGV0MTIz  ← 谁都会解，零安全性
```

**怎么读：** Base64 只是换一种写法，和「保密」无关。

### 1.2 加密是可逆的（有钥匙就能开）

```text
明文 + 密钥  →  密文
密文 + 密钥  →  明文
```

适合：需要以后再读出来的隐私数据（加密笔记、特定合规字段），且密钥管理要单独设计。  
**不适合当密码主存储方案**：系统若能解密，攻击者拿到密钥也能解密。

### 1.3 哈希是单向的

```text
明文  →  哈希值
哈希值 ↛ 明文（实际上不可逆）
```

同一明文（配合正确盐与算法）可以再次校验；但没法从哈希「算出密码」。

---

## 2. 为什么不能明文，也不能裸奔 `sha256`？

### 2.1 明文存储

```json
{ "email": "a@b.com", "password": "violet123" }
```

数据库或 `users.json` 一泄露 = 全部账号沦陷；用户还可能在别的网站复用同一密码。

### 2.2 普通 SHA-256 也不够

```python
import hashlib

def bad_hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()
```

问题：

1. **太快**：暴力破解成本低  
2. **无盐或盐用法不对**：相同密码得到相同哈希 → 彩虹表/撞库友好  
3. **不是为密码存储设计的算法**

`hashlib` 适合文件校验、一般摘要；**密码请用专用算法**。

### 2.3 正确方向：Password Hashing

| 算法 | 说明 |
|------|------|
| **bcrypt** | 老牌、普及、学习与项目都够用 |
| **Argon2** | 现代更推荐（进阶） |
| PBKDF2 / scrypt | 也常见，看生态 |

共同特征：

- **盐（salt）**：同一密码，不同用户哈希不同  
- **可调成本（慢）**：故意算得慢，抬高撞库成本  
- 输出里通常 **自带盐与参数**（一个字符串存库即可）

---

## 3. 标准流程心智模型

### 注册

```text
用户提交 password
  → password_hash = hash(password)
  → 数据库只存 password_hash
  → 原文立刻丢弃（不日志、不返回）
```

### 登录

```text
用户提交 email + password
  → 按 email 找到 password_hash
  → verify(password, password_hash) → True/False
  → True：发 Session / JWT
  → False：401
```

```text
❌ 错误：把库里的密码解密出来 == 用户输入
✅ 正确：用用户输入走 verify，和库里的哈希比对
```

---

## 4. 实战：bcrypt 存储与校验

### 4.1 安装

```bash
pip install bcrypt
# 或（FastAPI 生态常见）
pip install "passlib[bcrypt]"
```

### 4.2 注册时哈希

```python
import bcrypt

def hash_password(plain: str) -> str:
    hashed = bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")  # 存进 JSON / DB 的字符串


h1 = hash_password("violet123")
h2 = hash_password("violet123")
print(h1)
print(h2)
print(h1 == h2)  # False：盐不同，这是正确现象
```

库中字段示例：

```text
$2b$12$.............一长串.............
```

里面编码了：算法标识、成本因子、盐、哈希结果。

### 4.3 登录时校验

```python
import bcrypt

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(
        plain.encode("utf-8"),
        hashed.encode("utf-8"),
    )
```

### 4.4 用户记录字段怎么命名

```python
# ✅ 存储
user_record = {
    "email": "violet@demo.com",
    "username": "Violet",
    "password_hash": hash_password("violet123"),
}

# ❌ 不要
# "password": "violet123"
```

---

## 5. passlib 写法（可选，生态友好）

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)
```

以后若迁到 Argon2，可在 `schemes` 里平滑过渡。

---

## 6. 「密码显示」：正确做法是几乎不显示

### 6.1 原则

| 场景 | 正确做法 |
|------|----------|
| 注册/登录接口响应 | 返回用户公开信息，**不含密码** |
| 个人资料页 | 不显示密码；只提供「修改密码」 |
| 登录输入框 | 前端 `type="password"`（UI 掩码，不是加密） |
| 忘记密码 | **重置**（链接/验证码），不是找回旧密码 |
| 管理员后台 | 也不能看原文；最多帮用户重置 |
| 日志 / 异常 | 禁止打印请求里的 `password` |

前端的 `••••••` 只是输入掩码，和后端哈希无关。

### 6.2 Schema 分层（和 FastAPI 强相关）

```python
from pydantic import BaseModel, EmailStr, Field

class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str = Field(min_length=8)  # 仅入站

class UserOut(BaseModel):
    email: EmailStr
    username: str
    # 故意没有 password / password_hash

class UserInDB(BaseModel):
    email: EmailStr
    username: str
    password_hash: str  # 仅内部存储
```

FastAPI 示例：

```python
@app.post("/auth/sign_up", response_model=UserOut)
def sign_up(user: UserCreate):
    record = {
        "email": user.email,
        "username": user.username,
        "password_hash": hash_password(user.password),
    }
    save(record)
    return UserOut(email=user.email, username=user.username)
```

**怎么读：**

- `UserCreate`：允许接收密码  
- `UserOut`：响应里根本没有密码字段  
- `password_hash`：只存在服务器侧存储里  

### 6.3 可以「显示」什么？

可以：

- 密码规则（至少 8 位、需含数字等）  
- 前端强度提示  

不可以：

- API 返回 `{ "password": "violet123" }`  
- 邮件写「您的密码是 xxx」  

---

## 7. 和其它「安全技术」对照，避免张冠李戴

| 需求 | 该用什么 |
|------|----------|
| 存储登录密码 | **密码哈希**（bcrypt / Argon2） |
| 登录态 | Session 或 **JWT 签名** |
| 防传输窃听 | **HTTPS / TLS** |
| 需要以后解密再读的数据 | 对称加密（AES 等）+ 密钥管理 |
| API Key | 环境变量 / 密钥管理，不进 git |

易混点：

- **JWT**：主要是签名防篡改；payload 常可被解码看见——**别把密码放进 JWT**  
- **HTTPS**：保护路上；到了服务器仍要哈希后再落库  

---

## 8. 最小完整示例（注册 / 登录 / 不回显）

```python
import json
from pathlib import Path

import bcrypt
from pydantic import BaseModel, Field

DB = Path(__file__).resolve().parent / "users.json"


class UserCreate(BaseModel):
    email: str
    username: str
    password: str = Field(min_length=8)


class UserOut(BaseModel):
    email: str
    username: str


def _load() -> list[dict]:
    if not DB.exists():
        return []
    return json.loads(DB.read_text(encoding="utf-8"))


def _save(users: list[dict]) -> None:
    DB.write_text(
        json.dumps(users, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def register(user: UserCreate) -> UserOut:
    users = _load()
    if any(u["email"] == user.email for u in users):
        raise ValueError("email already exists")

    users.append(
        {
            "email": user.email,
            "username": user.username,
            "password_hash": hash_password(user.password),
        }
    )
    _save(users)
    return UserOut(email=user.email, username=user.username)


def login(email: str, password: str) -> bool:
    users = _load()
    for u in users:
        if u["email"] == email:
            return verify_password(password, u["password_hash"])
    return False
```

观察点：

1. 磁盘只有 `password_hash`  
2. `register` 返回 `UserOut`，无密码  
3. `login` 只返回是否成功（真实项目再签发 JWT）  
4. 数据路径用 `__file__` 定位，不依赖「碰巧在哪个目录启动」

---

## 9. 常见错误（Code Review 必抓）

1. Base64 / 可逆加密当密码存储  
2. 裸 `SHA256(password)`，无盐或盐固定  
3. 以为「前端先加密再传」就可以省略服务端哈希  
4. `response_model` / `UserOut` 仍包含 `password`  
5. 日志打印完整请求体（含 password）  
6. 「忘记密码」做成查询并发送旧密码  
7. 把密码放进 JWT  
8. 把含真实密码的 `users.json` 提交进 git  

---

## 10. 对照改造 `ai_service`（练习指引）

若你当前类似：

```python
class User(BaseModel):
    email: str
    username: str
    password: str  # 原文进 JSON
```

建议演进：

| 现在 | 改成 |
|------|------|
| 单一 `User` 含 `password` | `UserCreate` / `UserOut` / 存储用 `password_hash` |
| `write_user` 直接 `model_dump()` | 先 `hash_password`，再写入 |
| `check_password` 明文比较 | `verify_password(plain, password_hash)` |
| `sign_in` 返回假 token 字符串 | 校验通过后签发 JWT |
| 聊天接口无鉴权 | `Depends(get_current_user)` 保护 |

改造顺序建议：

1. 加 `hash_password` / `verify_password`  
2. 存储字段改名 `password_hash`  
3. 拆 Schema，注册响应用 `UserOut`  
4. （下一步）JWT 登录态  

---

## 11. 动手练习

1. 对同一密码哈希 3 次：字符串不同，但 `checkpw` 都为 `True`。  
2. 把练习项目里的明文 `password` 改成 `password_hash`。  
3. 写 `UserCreate` / `UserOut`，确保注册接口响应看不到密码。  
4. 故意 `print(password)` 一次，再删掉——建立日志洁癖。  
5. （进阶）登录成功签发 JWT；「修改密码」必须先 `verify` 旧密码。

---

## 12. 速查表

| 问题 | 答案 |
|------|------|
| 密码该加密还是哈希？ | **专用密码哈希**（bcrypt/Argon2） |
| 能从库里取出用户密码吗？ | **不能**；只能校验或重置 |
| 盐是什么？ | 随机值，使相同密码也产生不同哈希 |
| 为什么要慢？ | 增加暴力破解成本 |
| 前端圆点是加密吗？ | **不是**，只是 UI 掩码 |
| 接口如何显示密码？ | **不显示原文** |
| 有 HTTPS 还要哈希吗？ | **要**；HTTPS 管传输，哈希管存储 |

---

## 13. 下一步

1. JWT 签发与校验（登录态）——可对照 `fastapi_demo` / `fastapi_faq.md` 第 17 问  
2. 权限：登录了 ≠ 能操作别人的数据  
3. 重置密码流程（邮件/验证码 token）  
4. 密钥与配置管理（`.env`，不进 git）  
5. （可选）Argon2、二次验证 2FA  

---

*相关讲义：`pydantic.md`、`fastapi.md`、`fastapi_faq.md`*  
*相关代码：`ai_service/`、`fastapi_demo/`*
