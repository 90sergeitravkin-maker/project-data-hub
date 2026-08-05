# src/back/app_data_registry/models.py
"""SQLAlchemy модели Data Registry (Python-типы в Mapped[])."""
from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, Boolean, ForeignKey, UniqueConstraint, DateTime, Index, Text
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

from src.database.base import Base


SCHEMA_NAME = "app_data_registry"
TABLE_ARGS = {"schema": SCHEMA_NAME}


class DataSource(Base):
    __tablename__ = "data_sources"
    __table_args__ = TABLE_ARGS

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    version_links: Mapped[list["ServiceVersionDataSource"]] = relationship(
        "ServiceVersionDataSource", back_populates="source", cascade="all, delete-orphan", lazy="selectin"
    )


class Service(Base):
    __tablename__ = "services"
    __table_args__ = TABLE_ARGS

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    versions: Mapped[list["ServiceVersion"]] = relationship(
        "ServiceVersion", back_populates="service", cascade="all, delete-orphan", lazy="selectin"
    )


class ServiceVersion(Base):
    __tablename__ = "service_versions"
    __table_args__ = (
        UniqueConstraint("service_id", "version_number", name="uq_service_version"),
        Index("idx_service_version_active", "service_id", "is_active"),
        {"schema": SCHEMA_NAME},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(f"{SCHEMA_NAME}.services.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    service: Mapped["Service"] = relationship("Service", back_populates="versions")
    sources: Mapped[list["ServiceVersionDataSource"]] = relationship(
        "ServiceVersionDataSource", back_populates="version", cascade="all, delete-orphan", lazy="selectin"
    )


class ServiceVersionDataSource(Base):
    __tablename__ = "version_sources"
    __table_args__ = (
        UniqueConstraint("version_id", "source_id", name="uq_version_source"),
        Index("idx_source_versions", "source_id"),
        {"schema": SCHEMA_NAME},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(f"{SCHEMA_NAME}.service_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(f"{SCHEMA_NAME}.data_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    version: Mapped["ServiceVersion"] = relationship("ServiceVersion", back_populates="sources")
    source: Mapped["DataSource"] = relationship("DataSource", back_populates="version_links")