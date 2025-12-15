from arclet.cithun import Permission
from nonebot.adapters import Bot, Event
from nonebot.internal.matcher import Matcher
from nonebot.params import Depends
from nonebot_plugin_uninfo import Uninfo
from nonebot_plugin_user.utils import get_user

from .main import system


def require_permission(permission: str, default_available: bool = True, prompt: bool = False):
    """
    标记需要权限的函数

    Args:
        permission (str): 权限名称
        default_available (bool): 是否默认可用，默认为True
        prompt (bool): 是否提示
    """

    system.predefine(permission)

    @system.attach(permission)
    async def _(u, c, m, p):
        return m | (Permission("v-a") if default_available else Permission("v--"))

    async def _check_permission(event: Event, bot: Bot, sess: Uninfo):
        if event.get_type() == "meta_event":
            return False
        try:
            user_model = await get_user(sess.scope, sess.user.id)
            user = await system.get_or_create_user(str(user_model.id), user_model.name)
        except ValueError:
            return False
        if await system.has_permission(user, permission, Permission.AVAILABLE, context={"event": event, "bot": bot}):
            return True
        if prompt:
            await bot.send(event, f"Permission denied: {permission}")
        return False

    return _check_permission


def depends_permission(permission: str, default_available: bool = True, prompt: bool = False):
    """
    依赖权限的函数

    Args:
        permission (str): 权限名称
        default_available (bool): 是否默认可用，默认为True
        prompt (bool): 是否提示
    """
    wrapper = require_permission(permission, default_available, prompt)

    async def _check(event: Event, bot: Bot, sess: Uninfo, matcher: Matcher) -> bool:
        if not (ans := await wrapper(event, bot, sess)):
            matcher.skip()
        return ans

    return Depends(_check)
