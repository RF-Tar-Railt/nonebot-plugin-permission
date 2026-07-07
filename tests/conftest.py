import os
from pathlib import Path

import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter
from nonebug import NONEBOT_INIT_KWARGS, NONEBOT_START_LIFESPAN, App
import pytest
from pytest_asyncio import is_async_test
from sqlalchemy import delete
from sqlalchemy.pool import NullPool, StaticPool

POOL_CLASSES = {
    "NullPool": NullPool,
    "StaticPool": StaticPool,
}


def get_database_url() -> str:
    url = os.getenv("SQLALCHEMY_DATABASE_URL", "sqlite+aiosqlite://")
    if url != "sqlite+aiosqlite://":
        return url

    worker_id = os.getenv("PYTEST_XDIST_WORKER", "master")
    database = Path(".pytest_cache") / f"{worker_id}.sqlite3"
    database.parent.mkdir(exist_ok=True)
    database.unlink(missing_ok=True)
    return f"sqlite+aiosqlite:///{database.as_posix()}"


def pytest_configure(config: pytest.Config) -> None:
    pool_class = POOL_CLASSES[os.getenv("SQLALCHEMY_POOL_CLASS", "StaticPool")]

    config.stash[NONEBOT_INIT_KWARGS] = {
        "sqlalchemy_database_url": get_database_url(),
        "sqlalchemy_engine_options": {"poolclass": pool_class},
        "driver": "~fastapi",
        "alembic_startup_check": False,
        "permission_load_command": False,
        "permission_superusers": [],
    }
    config.stash[NONEBOT_START_LIFESPAN] = False


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    pytest_asyncio_tests = (item for item in items if is_async_test(item))
    session_scope_marker = pytest.mark.asyncio(loop_scope="session")
    for async_test in pytest_asyncio_tests:
        async_test.add_marker(session_scope_marker, append=False)


def reset_permission_system(permission_system) -> None:
    from arclet.cithun import Role, User
    from arclet.cithun.model import Track

    roles = {
        role_id: permission_system.roles.get(role_id) or Role(role_id, name)
        for role_id, name in permission_system._predefine_roles
    }
    users = {
        user_id: permission_system.users.get(user_id) or User(user_id, name)
        for user_id, name in permission_system._predefine_users
    }
    tracks = {
        track_id: permission_system.tracks.get(track_id) or Track(track_id, name or track_id)
        for track_id, name in permission_system._predefine_tracks
    }

    permission_system.loaded.clear()
    permission_system.resources.clear()
    permission_system.users.clear()
    permission_system.users.update(users)
    permission_system._user_locks.clear()
    permission_system._acl_locks.clear()
    permission_system._role_inherit_locks.clear()
    permission_system._user_role_locks.clear()
    permission_system.roles.clear()
    permission_system.roles.update(roles)
    permission_system.acls.clear()
    permission_system.tracks.clear()
    permission_system.tracks.update(tracks)


async def clear_database() -> None:
    from nonebot_plugin_orm import get_session

    from nonebot_plugin_permission.model import (
        AclEntryModel,
        RoleInheritsModel,
        RoleModel,
        TrackLevelModel,
        TrackModel,
        UserModel,
        UserRolesModel,
    )

    async with get_session() as session, session.begin():
        await session.execute(delete(AclEntryModel))
        await session.execute(delete(TrackLevelModel))
        await session.execute(delete(TrackModel))
        await session.execute(delete(UserRolesModel))
        await session.execute(delete(RoleInheritsModel))
        await session.execute(delete(UserModel))
        await session.execute(delete(RoleModel))


@pytest.fixture(scope="session", autouse=True)
async def after_nonebot_init(after_nonebot_init: None) -> None:
    driver = nonebot.get_driver()
    driver.register_adapter(OneBotV11Adapter)

    nonebot.load_plugin("nonebot_plugin_permission")


@pytest.fixture
async def app(app: App, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    import nonebot_plugin_orm
    from nonebot_plugin_orm import init_orm

    orm_dir = tmp_path / "orm"
    orm_dir.mkdir()
    monkeypatch.setattr(nonebot_plugin_orm, "_data_dir", orm_dir)

    await init_orm()

    from nonebot_plugin_permission import system as permission_system

    await clear_database()
    reset_permission_system(permission_system)
    await permission_system.load()

    yield app

    await clear_database()
    reset_permission_system(permission_system)
