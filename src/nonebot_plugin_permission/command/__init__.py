from typing import Literal

from arclet.alconna import Alconna, Args, CommandMeta, Option, Subcommand, store_true
from arclet.cithun import Permission
from arclet.cithun.exceptions import PermissionDeniedError, ResourceNotFoundError
from nepattern import BasePattern, MatchFailed, MatchMode
from nonebot import get_driver, get_plugin_config, require
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_permission")
require("nonebot_plugin_alconna")
require("nonebot_plugin_user")
require("nonebot_plugin_uninfo")

from nonebot_plugin_alconna import At, Match, on_alconna
from nonebot_plugin_uninfo import Uninfo
from nonebot_plugin_user import get_user

from nonebot_plugin_permission import SUPER_USER, UserOwner, depends_permission, system

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


class PermissionPattern(BasePattern[tuple[Permission, str, bool], str, Literal[MatchMode.TYPE_CONVERT]]):
    def match(self, input_):
        if not isinstance(input_, str):
            raise MatchFailed(f"Expected str, got {type(input_)}")
        if input_.lower() in ["true", "false"]:
            return Permission("v-a" if input_.lower() == "true" else "v--"), "=", False
        try:
            return Permission.parse(input_)
        except ValueError:
            raise MatchFailed(f"Invalid permission format: {input_}")


state_pattern = PermissionPattern(
    mode=MatchMode.TYPE_CONVERT, origin=tuple[Permission, str, bool], accepts=str, alias="bool | [ad][+-=][0-7|vma]"
)

cmd = Alconna(
    f"{_config.permission_command_name}",
    Subcommand(
        "user",
        Args["user?", At],
        Subcommand("list"),
        Subcommand("set", Args["permission", str]["state", state_pattern]),
        Subcommand("get", Args["permission", str]),
        Subcommand("inherit", Args["name", str], Option("cancel", action=store_true, default=False)),
        Subcommand("promote", Args["track", str]),
        Subcommand("demote", Args["track", str]),
    ),
    Subcommand(
        "track",
        Args["track", str],
        Subcommand("info"),
        Subcommand("append", Args["role", str]),
        Subcommand("insert", Args["role", str]["index", int]),
        Subcommand("remove", Args["role", str]),
        Subcommand("clear"),
        Subcommand("rename", Args["name", str]),
    ),
    Subcommand("createtrack", Args["name", str]),
    Subcommand("deletetrack", Args["name", str]),
    meta=CommandMeta("权限指令"),
)

perm = on_alconna(cmd, comp_config={})
perm.shortcut(
    r"chmod (?P<expr>(?:[ad])?(?:[=+-])?(?:[*0-7]|[vmarwx]+)) (?P<permission>.+)",
    prefix=True,
    command=f"{_config.permission_command_name} user set {{permission}} {{expr}}",
    humanized="chmod <expr> <permission>",
)


@perm.assign("user.list", parameterless=[depends_permission("command.permission.list")])
async def list_permissions(user: Match[At], current: UserOwner, session: Uninfo):
    if user.available:
        target_user = await get_user(session.scope, user.result.target)
        _target = await system.get_or_create_user(f"user:{target_user.id}", target_user.name)
    else:
        _target = current
    try:
        await perm.finish(await system.permission_on(_target))
    except PermissionDeniedError as e:
        await perm.finish(str(e))


@perm.assign(
    "user.set", parameterless=[depends_permission("command.permission.set", default_available=False, prompt=True)]
)
async def set_permission(
    permission: str,
    user: Match[At],
    state: tuple[Permission, str, bool],
    current: UserOwner,
    session: Uninfo,
    event,
    bot,
):
    mask, mode, deny = state
    available = mask & Permission.AVAILABLE == Permission.AVAILABLE
    if mode == "-":
        available = not available
    if user.available:
        target_user = await get_user(session.scope, user.result.target)
        _target = await system.get_or_create_user(f"user:{target_user.id}", target_user.name)
        try:
            await system.set(current, _target, permission, mask, mode, deny, context={"event": event, "bot": bot})
            await perm.finish(
                f"Permission {permission} {'enabled' if available else 'disabled'} for user:{target_user.id}"
            )
        except ResourceNotFoundError:
            await perm.finish(f"Permission {permission} not found")
        except PermissionDeniedError as e:
            await perm.finish(str(e))
    else:
        try:
            await system.suset(current, permission, mask, mode, deny)
            await perm.finish(f"Permission {permission} {'enabled' if available else 'disabled'} for {current.name}")
        except ResourceNotFoundError:
            await perm.finish(f"Permission {permission} not found")


@perm.assign("user.get", parameterless=[depends_permission("command.permission.get")])
async def get_permission(permission: str, user: Match[At], current: UserOwner, session: Uninfo, event, bot):
    if user.available:
        target_user = await get_user(session.scope, user.result.target)
        _target = await system.get_or_create_user(f"user:{target_user.id}", target_user.name)
        try:
            state = await system.get(_target, permission, context={"event": event, "bot": bot})
            await perm.finish(f"Permission {permission} for user:{target_user.id} is {Permission(state)!r}")
        except ResourceNotFoundError:
            await perm.finish(f"Permission {permission} not found")
        except PermissionDeniedError as e:
            await perm.finish(str(e))
    else:
        try:
            state = await system.get(current, permission, context={"event": event, "bot": bot})
            await perm.finish(f"Permission {permission} for {current.name} is {Permission(state)!r}")
        except ResourceNotFoundError:
            await perm.finish(f"Permission {permission} not found")


@perm.assign(
    "user.inherit.cancel.value",
    False,
    parameterless=[depends_permission("command.permission.inherit", default_available=False)],
)
async def add_inherit(name: str, user: Match[At], current: UserOwner, session: Uninfo):
    if user.available:
        target_user = await get_user(session.scope, user.result.target)
        current = await system.get_or_create_user(f"user:{target_user.id}", target_user.name)
    try:
        await system.inherit(current, await system.get_role(name))
    except KeyError:
        await perm.finish(f"Role {name} not found")
    await perm.finish(f"{current.name} inherit {name} success")


@perm.assign(
    "user.inherit.cancel.value",
    True,
    parameterless=[depends_permission("command.permission.inherit", default_available=False)],
)
async def cancel_inherit(name: str, user: Match[At], current: UserOwner, session: Uninfo):
    if user.available:
        target_user = await get_user(session.scope, user.result.target)
        current = await system.get_or_create_user(f"user:{target_user.id}", target_user.name)
    try:
        await system.cancel_inherit(current, await system.get_role(name))
    except KeyError:
        await perm.finish(f"Role {name} not found")
    await perm.finish(f"{current.name} cancel inherit {name} success")


system.pre_assign(SUPER_USER, "command.permission.*", Permission("vma"))


@system.attach("command.permission")
async def _(*args):
    return Permission(7)
