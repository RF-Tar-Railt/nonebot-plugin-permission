"""repair_aclentry_resource_fk

Revision ID: 7cd5d9bc312d
Revises: d6d9c2bbb3a2
Create Date: 2026-07-09 01:20:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
import sqlalchemy.exc

revision: str = "7cd5d9bc312d"
down_revision: str | Sequence[str] | None = "d6d9c2bbb3a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACLENTRY_TABLE = "nonebot_plugin_permission_aclentrymodel"
RESOURCEMODEL_TABLE = "nonebot_plugin_permission_resourcemodel"
ACLENTRY_RESOURCE_FK = (
    "fk_nonebot_plugin_permission_aclentrymodel_resource_id_nonebot_plugin_permission_resourcemodel"
)


def _has_aclentry_resource_fk() -> bool:
    inspector = sa.inspect(op.get_bind())
    try:
        foreign_keys = inspector.get_foreign_keys(ACLENTRY_TABLE)
    except sqlalchemy.exc.NoSuchTableError:
        return False

    return any(
        fk.get("name") == ACLENTRY_RESOURCE_FK
        or (
            fk.get("constrained_columns") == ["resource_id"]
            and fk.get("referred_table") == RESOURCEMODEL_TABLE
        )
        for fk in foreign_keys
    )


def upgrade(name: str = "") -> None:
    if name:
        return

    if not _has_aclentry_resource_fk():
        return

    with op.batch_alter_table(
        ACLENTRY_TABLE,
        schema=None,
        reflect_kwargs={"resolve_fks": False},
    ) as batch_op:
        batch_op.drop_constraint(
            batch_op.f(ACLENTRY_RESOURCE_FK),
            type_="foreignkey",
        )


def downgrade(name: str = "") -> None:
    if name:
        return
