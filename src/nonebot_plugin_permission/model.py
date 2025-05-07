from dataclasses import dataclass, field
from typing import Optional

from arclet.cithun.node import NodeState
from nonebot_plugin_orm.model import Model
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.schema import ForeignKey
from sqlalchemy.sql.sqltypes import JSON, Integer, String


class OwnerModel(Model):
    name: Mapped[str] = mapped_column(String(256), primary_key=True)
    priority: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    wildcards: Mapped[list[str]] = mapped_column(JSON, nullable=False)


class PermissionModel(Model):
    name: Mapped[str] = mapped_column(String(512), primary_key=True)
    subs: Mapped[list[str]] = mapped_column(JSON, nullable=False)


class DependencyModel(Model):
    name: Mapped[str] = mapped_column(String(512), primary_key=True)
    subs: Mapped[list[str]] = mapped_column(JSON, nullable=False)


class OwnerInheritsModel(Model):
    owner_name: Mapped[str] = mapped_column(ForeignKey(OwnerModel.name, ondelete="CASCADE"), primary_key=True)
    inherits_name: Mapped[str] = mapped_column(ForeignKey(OwnerModel.name, ondelete="CASCADE"), primary_key=True)


class OwnerPermissionModel(Model):
    owner_name: Mapped[str] = mapped_column(ForeignKey(OwnerModel.name, ondelete="CASCADE"), primary_key=True)
    permission: Mapped[str] = mapped_column(ForeignKey(PermissionModel.name, ondelete="CASCADE"), primary_key=True)
    state: Mapped[int] = mapped_column(Integer, nullable=False)


@dataclass(eq=True, unsafe_hash=True)
class Owner:
    name: str
    priority: Optional[int] = None
    nodes: dict[str, NodeState] = field(default_factory=dict, compare=False, hash=False)
    inherits: list = field(default_factory=list, compare=False, hash=False)
    wildcards: set[str] = field(default_factory=set, compare=False, hash=False)

    def dump(self):
        main_model = OwnerModel(
            name=self.name,
            priority=self.priority,
            wildcards=list(self.wildcards),
        )
        inherit_model = [
            OwnerInheritsModel(owner_name=self.name, inherits_name=inherit.name) for inherit in self.inherits
        ]
        permission_model = [
            OwnerPermissionModel(owner_name=self.name, permission=node, state=state.state)
            for node, state in self.nodes.items()
        ]
        return main_model, inherit_model, permission_model

    @classmethod
    def parse(cls, raw: OwnerModel):
        return cls(raw.name, raw.priority, wildcards=set(raw.wildcards))

    def __str__(self):
        return f"Owner({self.name})"
