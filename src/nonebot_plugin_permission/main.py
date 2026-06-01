import asyncio
from collections.abc import Awaitable, Callable
import fnmatch
import re
from typing import TypeAlias, TypedDict, TypeVar, overload

from arclet.cithun import Permission, ResourceNode, Role, User
from arclet.cithun.async_ import AsyncPermissionEngine, AsyncPermissionExecutor, AsyncPermissionService
from nonebot.adapters import Bot, Event
from nonebot_plugin_user.models import UserSession

from .store import ORMStore


class Context(TypedDict):
    event: Event
    bot: Bot
    session: UserSession


Attach: TypeAlias = Callable[
    [User, Context | None, Permission, Callable[[User | Role, Context | None], Awaitable[Permission]]],
    Awaitable[Permission | tuple[Permission, str]],
]
TAttach = TypeVar("TAttach", bound=Attach)
Attach1: TypeAlias = Callable[
    [User, str, Context | None, Permission, Callable[[User | Role, Context | None], Awaitable[Permission]]],
    Awaitable[Permission | tuple[Permission, str]],
]
TAttach1 = TypeVar("TAttach1", bound=Attach1)


class System(ORMStore, AsyncPermissionService[Context], AsyncPermissionExecutor[Context]):
    def __init__(self):
        ORMStore.__init__(self)
        AsyncPermissionService.__init__(self, engine=AsyncPermissionEngine[Context](), storage=self)
        AsyncPermissionExecutor.__init__(self, self, self)
        self.attaches: list[tuple[Callable[[str], bool], Attach1]] = []
        self.engine.register_strategy(self._run_attachs)

    async def _run_attachs(
        self,
        user: User,
        resource: ResourceNode,
        context: Context | None,
        current_mask: Permission,
        permission_lookup: Callable[[User | Role, Context | None], Awaitable[Permission]],
    ) -> Permission:
        """内部策略回调，遍历所有已绑定的 attach 函数并依次应用。

        Args:
            user: 当前用户。
            resource: 目标资源节点。
            context: 权限计算上下文。
            current_mask: 静态 ACL 计算出的初始掩码。
            permission_lookup: 查询其他主体权限的回调。

        Returns:
            Permission: 所有 attach 函数应用后的最终权限掩码。
        """
        result = current_mask
        tasks = []
        for pattern, func in self.attaches:
            if pattern(resource.id):
                tasks.append(func(user, resource.id, context, current_mask, permission_lookup))
        if not tasks:
            return current_mask
        for task in asyncio.as_completed(tasks):
            ret = await task
            if isinstance(ret, tuple):
                mask, mode = ret
                if mode == "+":
                    result |= mask
                elif mode == "-":
                    result &= ~mask
                elif mode == "=":
                    result = mask
            else:
                result |= ret
        return result

    @overload
    def attach(self, pattern: str) -> Callable[[TAttach], TAttach]: ...

    @overload
    def attach(self, pattern: Callable[[str], bool]) -> Callable[[TAttach1], TAttach1]: ...

    def attach(self, pattern):  # type: ignore
        """注册资源级权限回调。

        当 pattern 为字符串时，支持 glob 通配 (``*`` / ``?`` / ``[]``)。
        回调在对应资源节点被访问时触发。

        Args:
            pattern: 资源匹配模式。字符串精确匹配或 glob 通配，或自定义谓词函数。

        Returns:
            装饰器，将函数注册为 attach 回调。

        - 裸 ``Permission``: 与当前掩码叠加 (等价 ``"+"``)
        - ``(Permission, "+")``: 叠加
        - ``(Permission, "-")``: 从当前掩码中移除
        - ``(Permission, "=")``: 覆盖当前掩码
        """
        if isinstance(pattern, str):

            def decorator(func: Attach, /):
                if re.search(r"[*?\[\]]", pattern):
                    predicate = lambda p: fnmatch.fnmatch(p, pattern)
                else:
                    predicate = lambda p: p == pattern
                self.attaches.append((predicate, lambda u, _, c, m, pl: func(u, c, m, pl)))
                return func

            return decorator

        def wrapper(func: Attach1, /):
            self.attaches.append((pattern, func))
            return func

        return wrapper


system = System()
