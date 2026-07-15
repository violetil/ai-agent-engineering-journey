## 什么是 pydantic？

pydantic 是一个 Python 的三方库，用于创建数据结构的模板，模板中设定每个字段的类型与限制。

在使用模板创建数据结构时能够自动检查并报错。

## 样例讲解

下面一个 pydantic 的样例：

```python
from typing import Annotated, Literal
from pydantic import BaseModel, Field, EmailStr, SecretStr, field_validator, ConfigDict

class User(BaseModel):
  model_config = ConfigDict(
    populate_by_name=True, # 允许别名字段
    strict=True, # 不进行自动类型转换
    extra="allow", # 允许添加额外的字段
    validate_assignment=True # 修改值时也进行检查
  )

  username: Annotated[str, Field(min_length=3)]
  email: EmailStr # 内置类型
  password: SecretStr
  role: Literal["user", "admin"] = "user" # 限定取值

  @field_validator("username")
  @classmethod
  def valid_username(cls, v: str) -> str:
    if not v.replace('_', '').isalnum():
      raise ValueError("username must be alphanumeric (underline allowed)")
    return v.lower()


class Post(BaseModel):
  title: Annotated[str, Field(min_length=3)]
  content: Annotated[str, Field(min_length=10)]
  author: User # 嵌套类型
  tags: Annotated[list[str], Field(default_factory=list)]

user = User(username="violet", email="violet@gmail.com", password="secret123")

print(user.model_dump_json()) # 转换为 json 格式
print(user.model_dump()) # 转换为字典格式
```
