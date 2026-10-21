"""Base class and small helpers shared by all 13 models (spec section 10)."""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import CheckConstraint, DateTime, MetaData, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def uuid_pk(default_in_db: bool = True) -> Mapped[uuid.UUID]:
    """Primary key uuid. The database generates it with gen_random_uuid()."""
    return mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()") if default_in_db else None,
    )


def created_at_col() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


def updated_at_col() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


def enum_check(column: str, enum_cls: type[Enum], name: str, nullable: bool = False) -> CheckConstraint:
    """CHECK (column IN ('A','B',...)) built from a shared enum, so values never drift."""
    values = ", ".join(f"'{member.value}'" for member in enum_cls)
    sql = f"{column} IN ({values})"
    if nullable:
        sql = f"{column} IS NULL OR {column} IN ({values})"
    return CheckConstraint(sql, name=name)
