# Python 基础概念
## 1. 变量

变量的作用域只有函数和模块，没有块级作用域。

## 2. 基础数据类型

- `int`
- `float`
- `str`
- `bool`
- `list` : 可变 (mutable)
- `tuple` : 不可变 (immutable)
- `set` : 唯一性 (unique)
- `dict` : 键值对 (key and value)

## 3. 类型注解

Python 中在变量创建时没有要求提供变量类型，而是隐式推导，类型注解目的是为了给开发者提供便利。

## 4. 常量

Python 中的不变量通常用约定全大写。

## 5. 函数

关键字 - `def`。

## 6. 类

代码的蓝本，关键字 - `class`.

双下划线方法 (**double underline methods**):
- `__init__()`
- `__str__()`
- `__add__()`
- ...

# Python Install Manager 

安装之后会有 `py` 命令。

- 版本检查：`py --version` 或者 `pymanager --version`
- 动态选择版本：`py -3.14`, `py -3.11`
- 查看已安装python：`py --list` 或者 `py -0`
- 执行脚本：`py -3.14 app.py`
- 使用指定版本创建虚拟环境：`py -3.14 -m venv <env_name>`
- 安装库：`py -3.14 -m pip install <package_name>`
