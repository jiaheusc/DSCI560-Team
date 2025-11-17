import os
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Boolean, ForeignKey, DateTime, func, UniqueConstraint, Enum, Integer
from dotenv import load_dotenv
from sqlalchemy import JSON
import enum

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+asyncmy://chatuser:chatpass@localhost:3306/groupchat")

class UserRole(str, enum.Enum):
    user = "user"
    therapist = "therapist"
    operator = "operator"

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    user_role: Mapped[UserRole] = mapped_column(
        Enum(UserRole),
        nullable=False,
        default=UserRole.user
    )
    prefer_name: Mapped[str | None] = mapped_column(String(50))
    avatar_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    basic_info: Mapped[str | None] = mapped_column(Text(), nullable=True, default=None)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())
    messages: Mapped[list["Message"]] = relationship("Message", back_populates="user")
    memberships: Mapped[list["ChatGroupUsers"]] = relationship("ChatGroupUsers", back_populates="user")

class ChatGroups(Base):
    __tablename__ = "chat_groups"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    group_name: Mapped[str] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean(), default=False)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())
    memberships: Mapped[list["ChatGroupUsers"]] = relationship("ChatGroupUsers", back_populates="group", cascade="all, delete-orphan")
    messages: Mapped[list["Message"]] = relationship("Message", back_populates="group", cascade="all, delete-orphan")

class ChatGroupUsers(Base):
    __tablename__ = "chat_group_users"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("chat_groups.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    is_active: Mapped[bool] = mapped_column(Boolean(), default=False)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())
    group: Mapped["ChatGroups"] = relationship("ChatGroups", back_populates="memberships")
    user: Mapped["User"] = relationship("User", back_populates="memberships")
    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uk_group_user"),
    )

class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("chat_groups.id", ondelete="CASCADE"), nullable=False)
    content: Mapped[str] = mapped_column(Text())
    is_bot: Mapped[bool] = mapped_column(Boolean(), default=False)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="messages")
    group: Mapped["ChatGroups"] = relationship("ChatGroups", back_populates="messages")

class Questionnaires(Base):
    __tablename__ = "questionnaires"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    content: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class TherapistProfile(Base):
    __tablename__ = "therapist_profiles"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    expertise: Mapped[str | None] = mapped_column(String(255), nullable=True)
    years_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    license_number: Mapped[str | None] = mapped_column(String(100), nullable=True)

class UserQuestionnaire(Base):
    __tablename__ = "user_questionnaires"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    answers: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class UserTherapist(Base):
    __tablename__ = "user_therapists"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    therapist_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())

class UserTherapistChat(Base):
    __tablename__ = "user_therapist_chats"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    therapist_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)