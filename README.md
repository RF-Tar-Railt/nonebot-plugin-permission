<div align="center">

  <a href="https://nonebot.dev/">
    <img src="https://nonebot.dev/logo.png" width="200" height="200" alt="nonebot">
  </a>

# nonebot-plugin-permission

_✨ [Nonebot2](https://github.com/nonebot/nonebot2) 通用权限插件 ✨_

<p align="center">
  <img src="https://img.shields.io/github/license/RF-Tar-Railt/nonebot-plugin-permission" alt="license">
  <img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/nonebot-2.3.0+-red.svg" alt="NoneBot">
  <a href="https://pypi.org/project/nonebot-plugin-permission">
    <img src="https://badgen.net/pypi/v/nonebot-plugin-permission" alt="pypi">
  </a>
</p>

</div>

本插件基于 [`arclet-cithun`](https://github.com/ArcletProject/Cithun), 提供了一套通用的权限管理系统

## 安装

- 使用 nb-cli

```
nb plugin install nonebot-plugin-permission
```

- 使用 pip

```
pip install nonebot-plugin-permission
```

## 使用

### 设置 Matcher 级别的权限

```python
from nonebot import on_command
from nonebot_plugin_permission import require_permission

matcher = on_command("test", rule=require_permission("command.test"))
```

### 设置 Handler 级别的权限

```python
from nonebot import on_command
from nonebot_plugin_permission import depends_permission

matcher = on_command("test")

@matcher.handle(parameterless=depends_permission("command.test"))
async def handle():
    ...
```

### 依赖注入权限所有者模型

```python
from nonebot import on_command
from nonebot_plugin_permission import UserOwner

matcher = on_command("test")

@matcher.handle()
async def handle(owner: UserOwner):
    # owner 表示当前用户所代表的权限所有者
    ...
```

### 查看具体权限

```python
from nonebot import on_command
from nonebot_plugin_permission import UserOwner, ROOT, NodeState

matcher = on_command("test")

@matcher.handle()
async def handle(owner: UserOwner):
    state: NodeState = ROOT.get(owner, "command.test")
```

### 通过指令设置权限

```
permission [@user] set <permission> <state>
```

### 通过代码设置权限

```python
from nonebot_plugin_permission import ROOT, NodeState, monitor

@matcher.handle()
async def _():
    owner = await monitor.get_or_new_user("xxx")
    # 设置权限
    ROOT.set(owner, "command.test", NodeState("vma"))
    # 取消权限
    ROOT.set(owner, "command.test", NodeState("v--"))
```
