import asyncio
from arclet.cithun.async_ import AsyncStore
from arclet.cithun import Role, User, ResourceNode, InheritMode
from arclet.cithun.model import AclEntry, Track, TrackLevel

from nonebot_plugin_orm import get_session
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import select

from .model import UserModel, RoleModel, TrackModel, UserRolesModel, RoleInheritsModel, ResourceModel, AclEntryModel, AclDependencyModel, TrackLevelModel


class ORMStore(AsyncStore):
    def __init__(self):
        self.loaded = asyncio.Event()
        self.resources: dict[str, ResourceNode] = {}
        self.users: dict[str, User] = {}
        self.roles: dict[str, Role] = {}
        self.acls: dict[int, AclEntry] = {}
        self.tracks: dict[str, Track] = {}
        self.default_role = Role("$default", "Default")

        self._predefine_resources = []
        self._predefine_users = []
        self._predefine_roles = [("$default", "Default")]

    async def create_user(self, uid: str, name: str) -> User:
        await self.loaded.wait()
        if uid in self.users:
            return self.users[uid]
        async with get_session() as session, session.begin() as _:
            user_model = UserModel(id=uid, name=name)
            session.add(user_model)
        user = user_model.dump()
        self.users[uid] = user
        await self.inherit(user, self.default_role)
        return user

    async def get_or_create_user(self, uid: str, name: str) -> User:
        await self.loaded.wait()
        if uid in self.users:
            return self.users[uid]
        return await self.create_user(uid, name)

    async def create_role(self, rid: str, name: str) -> Role:
        await self.loaded.wait()
        if rid in self.roles:
            return self.roles[rid]
        async with get_session() as session, session.begin() as _:
            role_model = RoleModel(id=rid, name=name)
            session.add(role_model)
        role = role_model.dump()
        self.roles[rid] = role
        return role

    async def create_track(self, tid: str, name: str | None = None) -> Track:
        await self.loaded.wait()
        if tid in self.tracks:
            return self.tracks[tid]
        async with get_session() as session, session.begin() as _:
            track_model = TrackModel(id=tid, name=name or tid)
            session.add(track_model)
        track = track_model.dump()
        self.tracks[tid] = track
        return track

    async def _add_resource(self, res: ResourceNode):
        await self.loaded.wait()
        self.resources[res.id] = res
        async with get_session() as session, session.begin() as _:
            resource_model = ResourceModel(
                id=res.id,
                name=res.name,
                parent_id=res.parent_id,
                inherit_mode=res.inherit_mode,
                type=res.type,
            )
            session.add(resource_model)

    async def get_resource(self, rid: str) -> ResourceNode:
        # async with get_session() as session:
        #     resource_model = await session.get(ResourceModel, rid)
        #     if not resource_model:
        #         raise KeyError(rid)
        #     return resource_model.dump()
        return self.resources[rid]

    async def get_resource_chain(self, rid: str) -> list[ResourceNode]:
        chain = []
        # async with get_session() as session:
        #     current = await session.get(ResourceModel, rid)
        #     while current:
        #         chain.append(current.dump())
        #         if not current.parent_id:
        #             break
        #         current = await session.get(ResourceModel, current.parent_id)
        #     return chain
        current = self.resources.get(rid)
        while current:
            chain.append(current)
            if not current.parent_id:
                break
            current = self.resources.get(current.parent_id)
        return chain

    async def _add_acl(self, acl: AclEntry):
        await self.loaded.wait()
        async with get_session() as session, session.begin() as _:
            target = await session.scalar(
                select(AclEntryModel)
                .where(AclEntryModel.subject_type == acl.subject_type)
                .where(AclEntryModel.subject_id == acl.subject_id)
                .where(AclEntryModel.resource_id == acl.resource_id)
            )
            if target:
                return
            acl_model = AclEntryModel(
                subject_type=acl.subject_type, subject_id=acl.subject_id, allow_mask=acl.allow_mask, deny_mask=acl.deny_mask,
            )
            session.add(acl_model)
            await session.refresh(acl_model)
            self.acls[acl_model.id] = acl

    async def get_primary_acl(
        self,
        subject: User | Role,
        resource_id: str,
    ) -> AclEntry | None:
        await self.loaded.wait()
        async with get_session() as session:
            target = await session.scalar(
                select(AclEntryModel)
                .where(AclEntryModel.subject_type == subject.type)
                .where(AclEntryModel.subject_id == subject.id)
                .where(AclEntryModel.resource_id == resource_id)
            )
            if target:
                return self.acls[target.id]

    async def depend(
        self,
        target_subject: User | Role,
        target_resource_id: str,
        dep_subject: User | Role,
        dep_resource_path: str,
        required_mask: int,
    ) -> AclEntry:
        await self.loaded.wait()
        async with get_session() as session, session.begin() as _:
            target = await session.scalar(
                select(AclEntryModel)
                .where(AclEntryModel.subject_type == target_subject.type)
                .where(AclEntryModel.subject_id == target_subject.id)
                .where(AclEntryModel.resource_id == target_resource_id)
            )
            if not target:
                raise ValueError("Target ACL does not exist.")
            target_acl = self.acls[target.id]
            dep_res = await self.define(dep_resource_path)
            dep_model = AclDependencyModel(
                dep_subject_type=dep_subject.type,
                dep_subject_id=dep_subject.id,
                dep_resource_id=dep_res.id,
                required_mask=required_mask,
            )
            dep = dep_model.dump()
            if dep in target_acl.dependencies:
                return target_acl
            target_acl.dependencies.append(dep)
            target.dependencies.append(dep_model)
            return target_acl

    async def inherit(self, child: User | Role, parent: Role):
        await self.loaded.wait()
        if isinstance(child, Role):
            child_role = self._ensure_role(child)
            self._ensure_role(parent)
            if parent.id not in child_role.parent_role_ids:
                async with get_session() as session, session.begin() as _:
                    role_inherit_model = RoleInheritsModel(role_id=child_role.id, parent_role_id=parent.id)
                    session.add(role_inherit_model)
                child_role.parent_role_ids.append(parent.id)
        else:
            user = self._ensure_user(child)
            self._ensure_role(parent)
            if parent.id not in user.role_ids:
                async with get_session() as session, session.begin() as _:
                    user_roles_model = UserRolesModel(user_id=user.id, role_id=parent.id)
                    session.add(user_roles_model)
                user.role_ids.append(parent.id)

    async def add_track_level(self, track: Track, role: Role, name: str | None = None) -> None:
        await self.loaded.wait()
        level = TrackLevel(role.id, name or role.name)
        if level in track.levels:
            return
        track.levels.append(level)
        async with get_session() as session, session.begin() as _:
            session.add(
                TrackLevelModel(
                    index=len(track.levels) - 1,
                    track_id=track.id,
                    role_id=level.role_id,
                    level_name=level.level_name,
                )
            )

    async def insert_track_level(self, track: Track, index: int, role: Role, name: str | None = None) -> None:
        await self.loaded.wait()
        level = TrackLevel(role.id, name or role.name)
        if level in track.levels:
            return
        track.levels.insert(index, level)
        async with get_session() as session, session.begin() as _:
            levels_to_update = (await session.scalars(
                select(TrackLevelModel)
                .where(TrackLevelModel.track_id == track.id)
                .where(TrackLevelModel.index >= index)
            )).all()
            for lvl in levels_to_update:
                lvl.index += 1
                session.add(lvl)
            await session.flush()
            track_level_model = TrackLevelModel(
                index=index,
                track_id=track.id,
                role_id=level.role_id,
                level_name=level.level_name,
            )
            session.add(track_level_model)

    async def set_user_track_level(self, user: User, track: Track, level_index: int) -> None:
        """将用户在某个 Track 上设置到指定等级。

        会清理该用户在该 Track 上已有的其他角色，并赋予新等级对应的角色。

        Args:
            user (User): 用户对象。
            track (Track): Track 对象。
            level_index (int): 目标等级索引。

        Raises:
            ValueError: 当 Track 没有等级或索引无效时抛出。
        """
        levels = track.levels
        if not levels:
            raise ValueError("Track has no levels.")
        if level_index >= len(levels):
            raise ValueError("Invalid level index.")
        track_role_ids = {level.role_id for level in levels}
        user.role_ids = [rid for rid in user.role_ids if rid not in track_role_ids]
        if level_index < 0:
            return
        if levels[level_index].role_id not in user.role_ids:
            user.role_ids.append(levels[level_index].role_id)
        async with get_session() as session, session.begin() as _:
            user_roles_to_delete = (await session.scalars(
                select(UserRolesModel)
                .where(UserRolesModel.user_id == user.id)
                .where(UserRolesModel.role_id.in_(track_role_ids))
            )).all()
            for ur in user_roles_to_delete:
                await session.delete(ur)
            new_role_id = levels[level_index].role_id
            user_roles_model = UserRolesModel(user_id=user.id, role_id=new_role_id)
            session.add(user_roles_model)

    async def update_acl(self, acl: AclEntry, allow_mask: int, deny_mask: int | None = None) -> None:
        await self.loaded.wait()
        async with get_session() as session, session.begin() as _:
            target = await session.scalar(
                select(AclEntryModel)
                .where(AclEntryModel.subject_type == acl.subject_type)
                .where(AclEntryModel.subject_id == acl.subject_id)
                .where(AclEntryModel.resource_id == acl.resource_id)
            )
            if not target:
                raise ValueError("ACL entry does not exist.")
            target.allow_mask = allow_mask
            if deny_mask is not None:
                target.deny_mask = deny_mask
            acl.allow_mask = allow_mask
            if deny_mask is not None:
                acl.deny_mask = deny_mask

    async def load(self):
        async with get_session() as session, session.begin() as _:
            users = (await session.scalars(select(UserModel))).all()
            for user_model in users:
                user = user_model.dump()
                self.users[user.id] = user
                role_ids = (await session.scalars(
                    select(UserRolesModel.role_id).where(UserRolesModel.user_id == user.id)
                )).all()
                user.role_ids.extend(role_ids)
            roles = (await session.scalars(select(RoleModel))).all()
            for role_model in roles:
                role = role_model.dump()
                self.roles[role.id] = role
                parent_role_ids = (await session.scalars(
                    select(RoleInheritsModel.parent_role_id).where(RoleInheritsModel.role_id == role.id)
                )).all()
                role.parent_role_ids.extend(parent_role_ids)
            resources = (await session.scalars(select(ResourceModel))).all()
            for resource_model in resources:
                resource = resource_model.dump()
                self.resources[resource.id] = resource
            acls = (await session.scalars(select(AclEntryModel).options(
                selectinload(AclEntryModel.dependencies)
            ))).all()
            for acl_model in acls:
                acl = acl_model.dump()
                self.acls[acl_model.id] = acl
            tracks = (await session.scalars(select(TrackModel).options(
                selectinload(TrackModel.levels)
            ))).all()
            for track_model in tracks:
                track = track_model.dump()
                self.tracks[track.id] = track
        self.loaded.set()
        for path, inherit_mode, type_ in self._predefine_resources:
            if path not in self.resources:
                await self.define(path, inherit_mode=inherit_mode, type_=type_)
        for uid, name in self._predefine_users:
            if uid not in self.users:
                await self.create_user(uid, name)
        for rid, name in self._predefine_roles:
            if rid not in self.roles:
                await self.create_role(rid, name)

    def predefine(
        self,
        path: str,
        inherit_mode: InheritMode | None = None,
        type_: str = "GENERIC",
    ):
        self._predefine_resources.append((path, inherit_mode, type_))

    def pre_user(self, uid: str, name: str) -> User:
        user = User(uid, name)
        user.role_ids.append(self.default_role.id)
        self._predefine_users.append((uid, name))
        return user

    def pre_role(self, rid: str, name: str) -> Role:
        role = Role(rid, name)
        self._predefine_roles.append((rid, name))
        return role
