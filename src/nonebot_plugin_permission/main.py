import asyncio
from collections.abc import Callable
from typing import TypedDict, TypeAlias, TypeVar, Awaitable, overload
from arclet.cithun.async_ import AsyncPermissionExecutor, AsyncPermissionEngine, AsyncPermissionService
from arclet.cithun import Role, User, ResourceNode

from nonebot.adapters import Event, Bot
from .store import ORMStore


class Context(TypedDict):
    event: Event
    bot: Bot


Attach: TypeAlias = Callable[[User, Context | None, int, Callable[[User | Role, Context | None], Awaitable[int]]], Awaitable[int]]
TAttach = TypeVar("TAttach", bound=Attach)
Attach1: TypeAlias = Callable[[User, str, Context | None, int, Callable[[User | Role, Context | None], Awaitable[int]]], Awaitable[int]]
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
        current_mask: int,
        permission_lookup: Callable[[User | Role, Context | None], Awaitable[int]],
    ) -> int:
        tasks = []
        for pattern, func in self.attaches:
            if pattern(resource.id):
                tasks.append(func(user, resource.id, context, current_mask, permission_lookup))
        if not tasks:
            return current_mask
        for task in asyncio.as_completed(tasks):
            result = await task
            current_mask |= result
        return current_mask

    @overload
    def attach(self, pattern: str) -> Callable[[TAttach], TAttach]: ...

    @overload
    def attach(self, pattern: Callable[[str], bool]) -> Callable[[TAttach1], TAttach1]: ...

    def attach(self, pattern):  # type: ignore
        if isinstance(pattern, str):

            def decorator(func: Attach, /):
                self.attaches.append((lambda p: p == pattern, lambda u, _, c, m, pl: func(u, c, m, pl)))
                return func

            return decorator

        def wrapper(func: Attach1, /):
            self.attaches.append((pattern, func))
            return func

        return wrapper


system = System()
