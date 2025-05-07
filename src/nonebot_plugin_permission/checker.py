from arclet.cithun import PE, NodeState, define
from nonebot.adapters import Bot, Event
from nonebot.params import Depends

from .monitor import monitor


def require_permission(permission: str, default_available: bool = True, prompt: bool = False):
    """
    标记需要权限的函数

    Args:
        permission (str): 权限名称
        default_available (bool): 是否默认可用，默认为True
        prompt (bool): 是否提示
    """

    define(permission)
    monitor.add_default_permission(permission, NodeState("v-a") if default_available else NodeState("v--"))

    async def _check_permission(event: Event, bot: Bot):
        try:
            user = await monitor.get_or_new_owner(f"user:{event.get_user_id()}")
        except ValueError:
            return False
        if PE.root.get(user, permission).available:
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
    return Depends(require_permission(permission, default_available, prompt))
