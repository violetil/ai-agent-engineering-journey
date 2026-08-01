# 密码安全讲义答疑（9 问精讲）

> 对应主讲义：`password_security.md`  
> 读法：每问先给结论，再展开机制与代码。

---

## 1. Python 中的 `base64` 是什么库？什么时候需要？怎么用？

**一句话：** `base64` 是 Python **标准库**，用来做 Base64 **编码/解码**（换一种可打印的文本表示），**不是加密，也不保密。**

### 它做什么？

计算机底层常是任意字节（可能有不可见字符）。Base64 把字节变成只含：

```text
A-Z a-z 0-9 + / =
```

这类「安全可打印字符」，方便放进 JSON、URL 参数、邮件、配置文本里。

### 什么时候会需要？

| 场景 | 例子 |
|------|------|
| 二进制要当文本传输 | 小图片、文件片段放进 JSON |
| HTTP Basic 认证 | `Authorization: Basic base64(user:pass)` |
| JWT 的一段 | Header/Payload 常用 Base64URL 编码（仍不是加密） |
| 某些密钥/证书的文本形态 | PEM 相关场景会见到 |
| 调试打印字节 | 把 bytes 变成可读字符串 |

**不会**用它来「保护用户密码」。

### 基本用法

```python
import base64

data = b"hello"  # bytes
text = base64.b64encode(data).decode("ascii")  # 'aGVsbG8='
back = base64.b64decode(text)                  # b'hello'
```

字符串要先变成字节：

```python
s = "violet123"
encoded = base64.b64encode(s.encode("utf-8")).decode("ascii")
decoded = base64.b64decode(encoded).decode("utf-8")
```

还有 `urlsafe_b64encode`（用 `-_` 代替 `+/`，更适合放 URL）。

---

## 2. 哈希中的「盐」是什么？

**一句话：** 盐（salt）是在哈希前混入的一串 **随机值**，用来让「相同密码」也产生 **不同哈希**，并让预计算攻击（彩虹表）失效。

### 没有盐时

```text
hash("123456") → 永远是同一个值 H
```

攻击者可以提前算好：

```text
123456 → H
password → H2
...
```

泄露数据库后，拿 H 去表里一查就知道原密码。

### 有盐时

```text
hash(salt1 + "123456") → H1
hash(salt2 + "123456") → H2   # 同密码，不同盐，不同结果
```

每个用户一份随机盐；盐可以 **公开存储**（通常就嵌在哈希字符串里），秘密是「密码本身」，不是盐。

### 盐解决什么 / 不解决什么

| 盐能做的 | 盐不能单独做的 |
|----------|----------------|
| 相同密码 → 不同哈希 | 弱密码本身仍可能被猜中 |
| 让通用彩虹表失效 | 还需要「慢哈希」（bcrypt 成本）抬高猜测成本 |

bcrypt 里 `gensalt()` 就是在生成随机盐；`hashpw` 会把盐和结果一起编码进最终字符串。

---

## 3. SHA-256 是什么？

**一句话：** SHA-256 是一种 **通用密码学哈希算法**（SHA-2 家族），把任意长度输入压成固定 **256 位（32 字节）** 摘要。

特征：

- 同样输入 → 同样输出（确定性）  
- 输出长度固定（常写成 64 个十六进制字符）  
- 难以从输出反推输入  
- **计算很快**（这对文件校验是优点，对密码存储是缺点）

常见用途：

- 文件完整性校验（下完软件对一下哈希）  
- Git 对象/内容寻址相关场景  
- HMAC、数字签名流程中的摘要步骤  

**不太适合单独拿来存用户密码**（太快、还需自己认真设计盐与迭代）。密码请用 bcrypt / Argon2。

```python
import hashlib
print(hashlib.sha256(b"hello").hexdigest())
# 2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824
```

---

## 4. `hashlib` 是什么库？什么时候需要？怎么用？

**一句话：** `hashlib` 是 Python **标准库**，提供 SHA-256、SHA-1、MD5、BLAKE2 等常见哈希算法接口。

### 什么时候需要？

| 适合 | 不适合当主方案 |
|------|----------------|
| 校验文件是否损坏/被篡改 | 用户密码存储（请用 bcrypt/Argon2） |
| 给内容算指纹、去重 | 以为「哈希了就等于安全存密码」 |
| 实现 HMAC 等协议细节 | |
| 学习理解「摘要」概念 | |

### 基本用法

```python
import hashlib

# 方式 A：一行
digest = hashlib.sha256(b"hello").hexdigest()

# 方式 B：流式更新（大文件）
h = hashlib.sha256()
h.update(b"hel")
h.update(b"lo")
print(h.hexdigest())
print(h.digest())     # 原始 bytes，长度 32
```

常用方法：

| 方法 | 含义 |
|------|------|
| `update(data)` | 喂入更多 bytes |
| `digest()` | 得到原始字节摘要 |
| `hexdigest()` | 得到十六进制字符串（便于打印/存储） |

---

## 5. `password.encode()` 是什么？做了什么？何时需要？

语句：

```python
hashlib.sha256(password.encode()).hexdigest()
```

### `str.encode()` 是什么？

字符串方法：把 **文本字符串 `str`** 按某种字符编码变成 **字节串 `bytes`**。

```python
s = "你好"
b = s.encode("utf-8")   # b'\xe4\xbd\xa0\xe5\xa5\xbd'
print(type(s), type(b))  # <class 'str'> <class 'bytes'>
```

默认编码通常是 `"utf-8"`：

```python
password.encode()          # 等价于 password.encode("utf-8")
password.encode("utf-8")
```

反向是：

```python
b.decode("utf-8")  # bytes → str
```

### 它做了什么事？

人看到的是字符；哈希函数吃的是 **字节**。  
`encode` 规定「这些字符对应哪些字节」，然后交给 `sha256`。

```text
"abc"（str）
  --encode('utf-8')-->
b"abc"（bytes）
  --sha256-->
摘要（bytes）
  --hexdigest-->
十六进制字符串
```

### 什么时候需要？

几乎所有「加密 / 哈希 / 网络发送 / 文件按字节处理」场景：

- `hashlib`、`bcrypt`、`hmac` 要 `bytes`  
- `httpx`/`requests` 某些底层场景  
- 文件以二进制读写  

口诀：

> **文本用 `str`，密码算法用 `bytes`；中间靠 `encode` / `decode` 桥接。**

---

## 6. 相同密码不同哈希，怎么比对？彩虹表 / 撞库是什么？

### 6.1 为什么「同密码不同哈希」不是问题？

因为校验 **不是** 拿「新哈希字符串 == 库里哈希字符串」。

而是：

```text
库里存的： 完整哈希串（里面已经嵌了盐和参数）
用户输入：  plain password

checkpw(plain, stored_hash):
  1. 从 stored_hash 里解析出盐、成本参数
  2. 用「同一盐、同一参数」对 plain 再算一遍
  3. 比较计算结果是否与 stored_hash 中的哈希部分一致
```

所以：

| 现象 | 是否正常 |
|------|----------|
| 注册两次同一密码，库里两串不同 | 正常（盐不同） |
| 登录时 `checkpw("violet123", 那一串)` 为 True | 正常（用该串自带的盐重算） |

这正是 bcrypt 设计好的地方：**盐存在哈希结果里，校验时自动取出使用。**

### 6.2 彩虹表（Rainbow Table）是什么？

攻击者 **提前** 计算大量「常见密码 → 哈希」对照表。  
数据库泄露后，不逐个猜，而是 **查表**，瞬间还原很多弱密码。

有随机盐之后：

- 不能做一张「全局通用」彩虹表覆盖所有用户  
- 因为同一密码在不同盐下结果不同，表会爆到不可行

### 6.3 撞库（Credential Stuffing）是什么？

用户常在多个网站 **复用同一邮箱+密码**。  
攻击者拿到 A 站泄露的账号密码，拿去 **批量尝试登录 B 站**。

这和彩虹表不同：

| | 彩虹表 | 撞库 |
|--|--------|------|
| 针对 | 泄露的哈希，离线破解 | 已有的「邮箱+明文密码」去别的站试 |
| 发生地 | 攻击者自己电脑上算/查 | 在线打登录接口 |
| 防护 | 盐 + 慢哈希 | 防复用（用户侧）+ 限流/二次验证/检测异常登录（网站侧） |

讲义说「相同密码相同哈希 → 彩虹表/撞库友好」是在强调：  
无盐快哈希让 **离线破解更容易**；弱密码复用则让 **撞库更容易得手**。慢哈希 + 盐主要狠打前者；撞库还要靠产品与风控。

---

## 7. `bcrypt` 提供什么？和 `passlib[bcrypt]` 有何区别？

### 7.1 `bcrypt` 库核心能力

安装：`pip install bcrypt`

常用：

| 函数 | 作用 |
|------|------|
| `bcrypt.gensalt(rounds=12)` | 生成随机盐（可调成本） |
| `bcrypt.hashpw(password, salt)` | 对密码做 bcrypt 哈希 |
| `bcrypt.checkpw(password, hashed)` | 校验密码是否匹配 |
| （另有）`kdf` 等 | 进阶密钥派生，密码存储入门可不先深挖 |

入门几乎只需：`gensalt` + `hashpw` + `checkpw`。

### 7.2 `passlib[bcrypt]` 是什么？

```bash
pip install "passlib[bcrypt]"
```

- **passlib**：更高层的「密码哈希框架」  
- **`[bcrypt]`**：extras，表示顺带安装 bcrypt 后端依赖  

你写的是：

```python
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
pwd_context.hash("...")
pwd_context.verify("...", hashed)
```

### 7.3 区别对照

| | 只装 `bcrypt` | `passlib[bcrypt]` |
|--|---------------|-------------------|
| 层次 | 底层算法库 | 上层封装 + 依赖 bcrypt |
| API | `hashpw` / `checkpw` | `CryptContext.hash/verify` |
| 换算法 | 自己改代码 | 配置 `schemes` 更易迁移 |
| 学习清晰度 | 更直观看见盐 | 更省事、工程常见 |
| FastAPI 文档 | 较少直接用 | 官方教程常见 passlib |

学习建议：先会 `bcrypt` 三函数；做项目可用 passlib。两者都正确，不是对立关系。

---

## 8. 哈希密码过程：`encode`、盐、`hashpw` 各自干什么？

### 8.1 典型代码

```python
import bcrypt

plain = "violet123"
password_bytes = plain.encode("utf-8")     # str → bytes
salt = bcrypt.gensalt()                    # 随机盐（bytes）
hashed = bcrypt.hashpw(password_bytes, salt)  # 得到完整哈希（bytes）
stored = hashed.decode("utf-8")            # 可选：转 str 存 JSON
```

### 8.2 两个参数的类型与作用

| 参数 | 类型 | 作用 |
|------|------|------|
| `password.encode("utf-8")` | `bytes` | 密码的字节形式；算法只吃字节，不吃 `str` |
| `salt`（`gensalt()` 的返回值） | `bytes` | 随机盐 + 成本参数；让同密码不同用户结果不同，并控制「算得有多慢」 |

注意：传给 `hashpw` 的第二个参数常常是 `gensalt()` 的产物，它不只是裸随机数，还带有 bcrypt 格式前缀（如 `$2b$12$...`）。

### 8.3 `hashpw` 做了哪些事？（简化版）

```text
1. 读取盐里的参数（算法版本、cost rounds）
2. 把「密码字节 + 盐」送入 bcrypt 算法，进行较慢的密钥派生/哈希运算
3. 把结果编码成标准 bcrypt 字符串（bytes），形态类似：
   $2b$12$<盐与哈希混合编码的一长串>
```

所以返回值 **不是**「纯哈希数字」而已，而是 **可存储的自描述串**：以后 `checkpw` 只凭这一串就能完成校验。

---

## 9. 校验密码过程：`checkpw` 做了哪些事？

### 9.1 典型代码

```python
import bcrypt

ok = bcrypt.checkpw(
    "violet123".encode("utf-8"),  # 用户这次输入的密码
    stored.encode("utf-8"),       # 库里存的整串哈希
)
```

### 9.2 `checkpw` 做了哪些事？（简化版）

```text
1. 解析 stored 哈希串 → 取出盐、cost、算法标识、期望哈希
2. 用「同样的盐和 cost」对用户输入的 password bytes 再算一遍
3. 把新算结果与期望哈希做比较（库内部会尽量用安全比较）
4. 一致返回 True，否则 False
```

### 9.3 和「错误直觉」对比

```text
❌ 错误直觉：
   hash(输入) 得到 H1
   看 H1 字符串是否等于库里那串
   （若每次 gensalt 再 hash，永远对不上）

✅ 正确过程：
   必须使用「库里那串自带的盐」重算，再比哈希部分
   checkpw 已经替你做完
```

因此：注册时每次盐不同完全没问题；登录时带上 **该用户自己的那串** `password_hash` 即可验证。

---

## 附：把 9 问压成复习卡

| # | 结论 |
|---|------|
| 1 | `base64` 标准库，文本化字节；不是加密 |
| 2 | 盐=随机值，使同密码不同哈希，破彩虹表 |
| 3 | SHA-256=通用快哈希，适合校验，不适合单独存密码 |
| 4 | `hashlib` 标准库，算摘要；密码请用 bcrypt |
| 5 | `str.encode()`：`str`→`bytes`，哈希前必需 |
| 6 | 靠哈希串内嵌的盐重算比对；彩虹表=预计算查表，撞库=拿泄露账号试别的站 |
| 7 | bcrypt 提供 gensalt/hashpw/checkpw；passlib 是上层封装并依赖 bcrypt |
| 8 | `hashpw(密码bytes, 盐bytes)`：慢哈希并生成可存储整串 |
| 9 | `checkpw`：取出旧盐重算再比较，返回 True/False |

---

*建议阅读顺序：本答疑 → 回看 `password_security.md` → 在 `ai_service` 里把明文比较改成 `hashpw`/`checkpw`。*
