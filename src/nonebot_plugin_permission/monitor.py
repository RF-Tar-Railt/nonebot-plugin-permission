import asyncio
from collections.abc import Iterable
from typing import Optional

from arclet.cithun import PE, NodeState
from arclet.cithun.monitor import AsyncMonitor
from arclet.cithun.node import NODE_DEPENDS, NODES
from nonebot_plugin_orm import get_session
from sqlalchemy.sql import select

from .model import DependencyModel, Owner, OwnerInheritsModel, OwnerModel, OwnerPermissionModel, PermissionModel


class Monitor(AsyncMonitor):

    def predefine_owner(self, name: str, priority: Optional[int] = None) -> Owner:
        if name in self.OWNER_TABLE:
            return self.OWNER_TABLE[name]
        ow = Owner(name, priority)
        ow.inherits.append(self.default_group)
        self.OWNER_TABLE[name] = ow
        self.predefined.add(name)
        return ow

    def __init__(self):
        self.OWNER_TABLE = {"group:default": Owner("group:default", 100)}
        self.predefined = {"group:default"}
        self.loaded = asyncio.Event()

    @property
    def default_group(self) -> Owner:
        return self.OWNER_TABLE["group:default"]

    async def load(self):
        session = get_session()
        async with session:
            owners = (await session.scalars(select(OwnerModel))).all()
            permissions = (await session.scalars(select(PermissionModel))).all()
            dependencies = (await session.scalars(select(DependencyModel))).all()
            for p in permissions:
                NODES.setdefault(p.name, set()).update(p.subs)
            for d in dependencies:
                NODE_DEPENDS.setdefault(d.name, set()).update(d.subs)
            new_owners = {owner.name: Owner.parse(owner) for owner in owners}
            for ow in owners:
                ow_permissions = (
                    await session.scalars(
                        select(OwnerPermissionModel).where(OwnerPermissionModel.owner_name == ow.name)
                    )
                ).all()
                new_owners[ow.name].nodes = {perm.permission: NodeState(perm.state) for perm in ow_permissions}
                ow_inherits = (
                    await session.scalars(select(OwnerInheritsModel).where(OwnerInheritsModel.owner_name == ow.name))
                ).all()
                new_owners[ow.name].inherits = [new_owners[inherit.inherits_name] for inherit in ow_inherits]
            for name, owner in new_owners.items():
                if name not in self.OWNER_TABLE:
                    self.OWNER_TABLE[name] = owner
                else:
                    self.OWNER_TABLE[name].nodes.update(owner.nodes)
                    self.OWNER_TABLE[name].inherits = list(set(self.OWNER_TABLE[name].inherits) | set(owner.inherits))
        self.loaded.set()

    async def save(self):
        await self.loaded.wait()
        session = get_session()
        async with session:
            for owner in self.OWNER_TABLE.values():
                model, inherits, permissions = owner.dump()
                await session.merge(model)
                for inherit in inherits:
                    await session.merge(inherit)
                for permission in permissions:
                    await session.merge(permission)
            for node, subs in NODES.items():
                await session.merge(PermissionModel(name=node, subs=list(subs)))
            for node, subs in NODE_DEPENDS.items():
                await session.merge(DependencyModel(name=node, subs=list(subs)))
            await session.commit()

    async def get_or_new_owner(self, name: str, priority: Optional[int] = None) -> Owner:
        await self.loaded.wait()
        if name in self.OWNER_TABLE:
            return self.OWNER_TABLE[name]
        session = get_session()
        async with session.begin():
            owner = Owner(name, priority)
            owner.inherits.append(self.default_group)
            session.add(owner.dump()[0])
        self.OWNER_TABLE[name] = owner
        return owner

    async def get_or_new_user(self, user_id: str):
        return await self.get_or_new_owner(f"user:{user_id}")

    async def get_or_new_group(self, group_id: str):
        return await self.get_or_new_owner(f"group:{group_id}")

    async def inherit(self, target: Owner, source: Owner, *sources: Owner):
        await self.loaded.wait()
        session = get_session()
        async with session:
            for src in [source, *sources]:
                if src not in target.inherits:
                    target.inherits.append(src)
                    if not (
                        (await session.scalars(select(OwnerModel).where(OwnerModel.name == src.name))).one_or_none()
                    ):
                        session.add(src.dump()[0])
                        await session.commit()
                    await session.merge(OwnerInheritsModel(owner_name=target.name, inherits_name=src.name))
            await session.commit()

    async def cancel_inherit(self, target: Owner, source: Owner):
        await self.loaded.wait()
        session = get_session()
        async with session:
            if source in target.inherits:
                target.inherits.remove(source)
                await session.delete(OwnerInheritsModel(owner_name=target.name, inherits_name=source.name))
                await session.commit()

    async def all_owners(self) -> Iterable[Owner]:
        return self.OWNER_TABLE.values()

    def add_default_permission(self, node: str, state: NodeState, missing_ok: bool = False, recursive: bool = False):
        PE.root.set(self.default_group, node, state, missing_ok, recursive)


monitor = Monitor()
