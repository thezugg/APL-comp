from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


def utc_now():
    return datetime.now(timezone.utc)


class Admin(Base):
    __tablename__ = "admins"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="admin")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Division(Base):
    __tablename__ = "divisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (UniqueConstraint("name", "division_id", name="uq_team_div"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    division_id: Mapped[int] = mapped_column(ForeignKey("divisions.id"), index=True)


class Player(Base):
    __tablename__ = "players"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    division_id: Mapped[int] = mapped_column(ForeignKey("divisions.id"), index=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    member_number: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Competition(Base):
    __tablename__ = "competitions"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(180))
    kind: Mapped[str] = mapped_column(String(20))
    division_id: Mapped[int | None] = mapped_column(ForeignKey("divisions.id"), nullable=True)
    enforce_same_division: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Entry(Base):
    __tablename__ = "entries"
    __table_args__ = (UniqueConstraint("competition_id", "label", name="uq_entry_label"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(400))
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True)


class EntryPlayer(Base):
    __tablename__ = "entry_players"
    __table_args__ = (UniqueConstraint("competition_id", "player_id", name="uq_comp_player"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id", ondelete="CASCADE"), index=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("entries.id", ondelete="CASCADE"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    name_snapshot: Mapped[str] = mapped_column(String(120))
    division_snapshot: Mapped[str] = mapped_column(String(80))
    team_snapshot: Mapped[str] = mapped_column(String(120), default="")


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (UniqueConstraint("competition_id", "round_num", "position", name="uq_match_round_pos"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id", ondelete="CASCADE"), index=True)
    round_num: Mapped[int] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer)
    a: Mapped[int | None] = mapped_column(ForeignKey("entries.id"), nullable=True)
    b: Mapped[int | None] = mapped_column(ForeignKey("entries.id"), nullable=True)
    bye: Mapped[bool] = mapped_column(Boolean, default=False)
    score_a: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_b: Mapped[int | None] = mapped_column(Integer, nullable=True)
    winner: Mapped[int | None] = mapped_column(ForeignKey("entries.id"), nullable=True)


class Audit(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    admin_id: Mapped[int | None] = mapped_column(ForeignKey("admins.id"), nullable=True)
    event: Mapped[str] = mapped_column(String(80))
    detail: Mapped[str] = mapped_column(String(600))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
