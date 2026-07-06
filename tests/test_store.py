import asyncio

from nonebug import App
import pytest
from sqlalchemy import func, select


async def test_get_or_create_user_is_concurrency_safe(app: App, monkeypatch: pytest.MonkeyPatch):
    from nonebot_plugin_orm import get_session

    from nonebot_plugin_permission import system
    from nonebot_plugin_permission.model import UserModel
    import nonebot_plugin_permission.store as store_module

    original_get_session = store_module.get_session
    release = asyncio.Event()
    waiters = 0

    class BarrierSession:
        def __init__(self, context_manager):
            self.context_manager = context_manager

        async def __aenter__(self):
            nonlocal waiters

            waiters += 1
            if waiters == 2:
                release.set()
            try:
                await asyncio.wait_for(release.wait(), timeout=0.1)
            except TimeoutError:
                release.set()
            return await self.context_manager.__aenter__()

        async def __aexit__(self, exc_type, exc, traceback):
            return await self.context_manager.__aexit__(exc_type, exc, traceback)

    def get_session_with_barrier(*args, **kwargs):
        return BarrierSession(original_get_session(*args, **kwargs))

    monkeypatch.setattr(store_module, "get_session", get_session_with_barrier)

    results = await asyncio.gather(
        system.get_or_create_user("user:1", "QQClient-417557420"),
        system.get_or_create_user("user:1", "QQClient-417557420"),
        return_exceptions=True,
    )

    exceptions = [result for result in results if isinstance(result, BaseException)]
    assert exceptions == []

    users = [result for result in results if not isinstance(result, BaseException)]
    assert {user.id for user in users} == {"user:1"}

    async with get_session() as session:
        user_count = await session.scalar(select(func.count()).select_from(UserModel).where(UserModel.id == "user:1"))

    assert user_count == 1
