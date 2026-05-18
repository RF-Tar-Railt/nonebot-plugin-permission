from arclet.cithun.model import (
    AclDependency,
    AclEntry,
    InheritMode,
    Permission,
    ResourceNode,
    Role,
    SubjectType,
    Track,
    TrackLevel,
    User,
)
from nonebot_plugin_orm.model import Model
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.schema import ForeignKey
from sqlalchemy.sql.sqltypes import Integer, String


class UserModel(Model):
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)

    def dump(self):
        return User(id=self.id, name=self.name)


class RoleModel(Model):
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)

    def dump(self):
        return Role(id=self.id, name=self.name)


class UserRolesModel(Model):
    user_id: Mapped[str] = mapped_column(ForeignKey(UserModel.id, ondelete="CASCADE"), primary_key=True)
    role_id: Mapped[str] = mapped_column(ForeignKey(RoleModel.id, ondelete="CASCADE"), primary_key=True)


class RoleInheritsModel(Model):
    role_id: Mapped[str] = mapped_column(ForeignKey(RoleModel.id, ondelete="CASCADE"), primary_key=True)
    parent_role_id: Mapped[str] = mapped_column(ForeignKey(RoleModel.id, ondelete="CASCADE"), primary_key=True)


class ResourceModel(Model):
    id: Mapped[str] = mapped_column(String(256), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("nonebot_plugin_permission_resourcemodel.id", ondelete="CASCADE"), nullable=True
    )
    inherit_mode: Mapped[InheritMode] = mapped_column(String(32), nullable=False, default=InheritMode.MERGE.value)
    type: Mapped[str] = mapped_column(String(64), nullable=False, default="GENERIC")  # FILE / DIR / PROJECT / etc.

    def dump(self):
        return ResourceNode(
            id=self.id,
            name=self.name,
            parent_id=self.parent_id,
            inherit_mode=InheritMode(self.inherit_mode),
            type=self.type,
        )

    parent: Mapped["ResourceModel | None"] = relationship("ResourceModel", back_populates="children", remote_side=[id])
    children: Mapped[list["ResourceModel"]] = relationship(back_populates="parent")


class AclEntryModel(Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject_type: Mapped[SubjectType] = mapped_column(String(16), nullable=False)  # 'USER' or 'ROLE'
    subject_id: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str] = mapped_column(ForeignKey(ResourceModel.id, ondelete="CASCADE"), nullable=False)
    allow_mask: Mapped[int] = mapped_column(Integer, nullable=False)
    deny_mask: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    dependencies: Mapped[list["AclDependencyModel"]] = relationship(
        "AclDependencyModel", back_populates="acl_entry", cascade="all, delete-orphan"
    )

    def dump(self):
        return AclEntry(
            subject_type=SubjectType(self.subject_type),
            subject_id=self.subject_id,
            resource_id=self.resource_id,
            allow_mask=Permission(self.allow_mask),
            deny_mask=Permission(self.deny_mask),
            dependencies=[dep.dump() for dep in self.dependencies],
        )


class AclDependencyModel(Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    acl_id: Mapped[int] = mapped_column(ForeignKey(AclEntryModel.id, ondelete="CASCADE"), nullable=False)
    dep_subject_type: Mapped[SubjectType] = mapped_column(String(16), nullable=False)  # 'USER' or 'ROLE'
    dep_subject_id: Mapped[str] = mapped_column(String(64), nullable=False)
    dep_resource_id: Mapped[str] = mapped_column(ForeignKey(ResourceModel.id, ondelete="CASCADE"), nullable=False)
    required_mask: Mapped[int] = mapped_column(Integer, nullable=False)

    acl_entry: Mapped[AclEntryModel] = relationship(AclEntryModel, back_populates="dependencies")

    def dump(self):
        return AclDependency(
            subject_type=SubjectType(self.dep_subject_type),
            subject_id=self.dep_subject_id,
            resource_id=self.dep_resource_id,
            required_mask=Permission(self.required_mask),
        )


class TrackModel(Model):
    id: Mapped[str] = mapped_column(String(256), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)

    levels: Mapped[list["TrackLevelModel"]] = relationship(
        "TrackLevelModel", back_populates="track", cascade="all, delete-orphan"
    )

    def dump(self):
        levels = sorted(self.levels, key=lambda level: level.index)
        return Track(
            id=self.id,
            name=self.name,
            levels=[level.dump() for level in levels],
        )


class TrackLevelModel(Model):
    index: Mapped[int] = mapped_column(Integer, nullable=False)
    track_id: Mapped[str] = mapped_column(ForeignKey(TrackModel.id, ondelete="CASCADE"), primary_key=True)
    role_id: Mapped[str] = mapped_column(ForeignKey(RoleModel.id, ondelete="CASCADE"), primary_key=True)
    level_name: Mapped[str] = mapped_column(String(256), nullable=False)

    track: Mapped[TrackModel] = relationship(TrackModel, back_populates="levels")

    def dump(self):
        return TrackLevel(
            role_id=self.role_id,
            level_name=self.level_name,
        )
