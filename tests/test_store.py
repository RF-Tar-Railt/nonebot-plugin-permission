import asyncio

from arclet.cithun import Permission
from nonebug import App
import pytest
from sqlalchemy import func, select


def install_session_barrier(monkeypatch: pytest.MonkeyPatch) -> None:
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


async def test_get_or_create_user_is_concurrency_safe(app: App, monkeypatch: pytest.MonkeyPatch):
    from nonebot_plugin_orm import get_session

    from nonebot_plugin_permission import system
    from nonebot_plugin_permission.model import UserModel

    install_session_barrier(monkeypatch)

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


async def test_user_inherit_is_concurrency_safe(app: App, monkeypatch: pytest.MonkeyPatch):
    from nonebot_plugin_orm import get_session

    from nonebot_plugin_permission import system
    from nonebot_plugin_permission.model import UserRolesModel

    user = await system.get_or_create_user("user:inherit", "User")
    role = await system.create_role("group:inherit", "Inherit")
    install_session_barrier(monkeypatch)

    results = await asyncio.gather(
        system.inherit(user, role),
        system.inherit(user, role),
        return_exceptions=True,
    )

    exceptions = [result for result in results if isinstance(result, BaseException)]
    assert exceptions == []

    async with get_session() as session:
        inherit_count = await session.scalar(
            select(func.count())
            .select_from(UserRolesModel)
            .where(UserRolesModel.user_id == user.id)
            .where(UserRolesModel.role_id == role.id)
        )

    assert inherit_count == 1


async def test_role_inherit_is_concurrency_safe(app: App, monkeypatch: pytest.MonkeyPatch):
    from nonebot_plugin_orm import get_session

    from nonebot_plugin_permission import system
    from nonebot_plugin_permission.model import RoleInheritsModel

    child = await system.create_role("group:child", "Child")
    parent = await system.create_role("group:parent", "Parent")
    install_session_barrier(monkeypatch)

    results = await asyncio.gather(
        system.inherit(child, parent),
        system.inherit(child, parent),
        return_exceptions=True,
    )

    exceptions = [result for result in results if isinstance(result, BaseException)]
    assert exceptions == []

    async with get_session() as session:
        inherit_count = await session.scalar(
            select(func.count())
            .select_from(RoleInheritsModel)
            .where(RoleInheritsModel.role_id == child.id)
            .where(RoleInheritsModel.parent_role_id == parent.id)
        )

    assert inherit_count == 1


async def test_assign_acl_is_concurrency_safe(app: App, monkeypatch: pytest.MonkeyPatch):
    from nonebot_plugin_orm import get_session

    from nonebot_plugin_permission import system
    from nonebot_plugin_permission.model import AclEntryModel

    install_session_barrier(monkeypatch)

    results = await asyncio.gather(
        system.assign(system.default_role, "concurrent.acl", Permission.AVAILABLE),
        system.assign(system.default_role, "concurrent.acl", Permission.AVAILABLE),
        return_exceptions=True,
    )

    exceptions = [result for result in results if isinstance(result, BaseException)]
    assert exceptions == []

    async with get_session() as session:
        acl_count = await session.scalar(
            select(func.count())
            .select_from(AclEntryModel)
            .where(AclEntryModel.subject_type == system.default_role.type)
            .where(AclEntryModel.subject_id == system.default_role.id)
            .where(AclEntryModel.resource_id == "concurrent.acl")
        )

    assert acl_count == 1
