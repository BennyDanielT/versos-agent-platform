"""SQLAlchemy ORM models — mirror sql/schema.sql.

The DDL in sql/schema.sql is the source of truth (it runs in Postgres on boot,
including indexes). These ORM classes are how the app reads/writes those tables.
In a real project Alembic would generate the DDL from these models; here we keep
both so the schema file stays a clean, reviewable artifact for the interview.
"""
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    customer_id: Mapped[str] = mapped_column(Text)
    complaint_text: Mapped[str] = mapped_column(Text)

    issue_category: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str | None] = mapped_column(Text)
    ai_summary: Mapped[str | None] = mapped_column(Text)
    ai_remediation: Mapped[str | None] = mapped_column(Text)
    ai_confidence: Mapped[float | None] = mapped_column(Float)

    status: Mapped[str] = mapped_column(Text, default="new")
    triage_mode: Mapped[str] = mapped_column(Text, default="suggest")
    approved_by: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    customer_id: Mapped[str] = mapped_column(Text)
    s3_uri: Mapped[str] = mapped_column(Text)
    filename: Mapped[str] = mapped_column(Text)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    language: Mapped[str | None] = mapped_column(Text)
    keywords: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    processing_status: Mapped[str] = mapped_column(Text, default="uploaded")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    transcripts: Mapped[list["Transcript"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )
    findings: Mapped[list["AuditFinding"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("media_assets.id", ondelete="CASCADE"))
    transcript_text: Mapped[str] = mapped_column(Text)
    confidence_score: Mapped[float | None] = mapped_column(Float)
    speaker_count: Mapped[int | None] = mapped_column(Integer)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    asset: Mapped["MediaAsset"] = relationship(back_populates="transcripts")


class AuditFinding(Base):
    __tablename__ = "audit_findings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("media_assets.id", ondelete="CASCADE"))
    finding_type: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    detected_by: Mapped[str] = mapped_column(Text, default="rules")
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    asset: Mapped["MediaAsset"] = relationship(back_populates="findings")
