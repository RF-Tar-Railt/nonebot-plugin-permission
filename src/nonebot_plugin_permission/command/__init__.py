from typing import Union

from arclet.alconna import Alconna, Args, CommandMeta, Option, Subcommand, store_true
from arclet.cithun import PE, ROOT, NodeState
from nonebot import get_driver, get_plugin_config, require
from nonebot.adapters import Bot, Event
from nonebot.plugin import PluginMetadata, inherit_supported_adapters
from nonebot.typing import T_State

require("nonebot_plugin_permission")
require("nonebot_plugin_alconna")
require("nonebot_plugin_user")
require("nonebot_plugin_uninfo")

from nonebot_plugin_alconna import At, Match, on_alconna
from nonebot_plugin_user import get_user
from nonebot_plugin_uninfo import Uninfo
from nonebot_plugin_permission import SUPER_USER, UserOwner, depends_permission, monitor

from .config import Config

driver = get_driver()
global_config = driver.config
_config = get_plugin_config(Config)
__version__ = "0.5.0"
__plugin_meta__ = PluginMetadata(
    name="Permission 附属指令",
    description="为权限系统提供附属指令",
    usage="""\
/permission set <permission> <state> [user:At] - 设置权限
/permission get <permission> [user:At] - 获取权限
""",
    homepage="https://github.com/RF-Tar-Railt/nonebot-plugin-permission",
    type="application",
    config=Config,
    supported_adapters=inherit_supported_adapters("nonebot_plugin_alconna"),
    extra={
        "author": "RF-Tar-Railt",
        "priority": 3,
        "version": __version__,
    },
)

cmd = Alconna(
    f"{_config.permission_command_name}",
    Args["user?", At],
    Subcommand("set", Args["permission", str]["state", Union[bool, str, int]]),
    Subcommand("get", Args["permission", str]),
    Subcommand("inherit", Args["name", str], Option("cancel", action=store_true, default=False)),
    meta=CommandMeta("权限指令"),
)

perm = on_alconna(cmd, comp_config={})


@perm.assign("set", parameterless=[depends_permission("command.permission.set", default_available=False)])
async def set_permission(permission: str, user: Match[At], state: Union[bool, str, int], current: UserOwner, session: Uninfo):
    if isinstance(state, bool):
        _state = NodeState("v-a" if state else "v--")
    else:
        try:
            _state = NodeState(state)
        except ValueError:
            await perm.send(f"Invalid state: {state}")
            await perm.finish()
    available = _state.available
    if user.available:
        target_user = await get_user(session.scope, user.result.target)
        _target = await monitor.get_or_new_owner(f"user:{target_user.id}")
        try:
            PE(current).set(_target, permission, _state)
            await perm.finish(f"Permission {permission} {'enabled' if available else 'disabled'} for user:{target_user.id}")
        except FileNotFoundError:
            await perm.finish(f"Permission {permission} not found")
        except PermissionError as e:
            await perm.finish(str(e))
    else:
        try:
            PE.root.set(current, permission, _state)
            await perm.finish(f"Permission {permission} {'enabled' if available else 'disabled'} for {current.name}")
        except FileNotFoundError:
            await perm.finish(f"Permission {permission} not found")


@perm.assign("get", parameterless=[depends_permission("command.permission.get")])
async def get_permission(permission: str, user: Match[At], current: UserOwner, session: Uninfo):
    if user.available:
        target_user = await get_user(session.scope, user.result.target)
        _target = await monitor.get_or_new_owner(f"user:{target_user.id}")
        try:
            state = PE(current).get(_target, permission)
            await perm.finish(
                f"Permission {permission} for user:{target_user.id} is {'enabled' if state.available else 'disabled'}"
            )
        except FileNotFoundError:
            await perm.finish(f"Permission {permission} not found")
        except PermissionError as e:
            await perm.finish(str(e))
    else:
        try:
            state = PE.root.get(current, permission)
            await perm.finish(
                f"Permission {permission} for {current.name} is {'enabled' if state.available else 'disabled'}"
            )
        except FileNotFoundError:
            await perm.finish(f"Permission {permission} not found")


@perm.assign(
    "inherit.cancel.value",
    False,
    parameterless=[depends_permission("command.permission.inherit", default_available=False)],
)
async def add_inherit(name: str, user: Match[At], current: UserOwner, bot: Bot, event: Event, state: T_State, session: Uninfo):
    if name not in monitor.OWNER_TABLE:
        await perm.finish(f"Owner {name} not found")
    if user.available:
        target_user = await get_user(session.scope, user.result.target)
        current = await monitor.get_or_new_owner(f"user:{target_user.id}")
    if name in monitor.inherit_checker and not monitor.inherit_checker[name](current, bot, event, state):
        await perm.finish(f"{current.name} inherit {name} failed")
    await monitor.inherit(current, await monitor.get_or_new_owner(name))
    await perm.finish(f"{current.name} inherit {name} success")


@perm.assign(
    "inherit.cancel.value",
    True,
    parameterless=[depends_permission("command.permission.inherit", default_available=False)],
)
async def cancel_inherit(name: str, user: Match[At], current: UserOwner, session: Uninfo):
    if name not in monitor.OWNER_TABLE:
        await perm.finish(f"Owner {name} not found")
    if user.available:
        target_user = await get_user(session.scope, user.result.target)
        current = await monitor.get_or_new_owner(f"user:{target_user.id}")
    await monitor.cancel_inherit(current, await monitor.get_or_new_owner(name))
    await perm.finish(f"{current.name} cancel inherit {name} success")


ROOT.set(SUPER_USER, "command.permission.set", NodeState("vma"))
ROOT.set(SUPER_USER, "command.permission.inherit", NodeState("vma"))
