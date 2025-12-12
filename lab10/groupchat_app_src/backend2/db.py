import os
import enum
from dotenv import load_dotenv

from sqlalchemy import (
    String, Text, Boolean, ForeignKey, DateTime, func,
    UniqueConstraint, Enum, Integer, JSON
)
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, relationship
)

# ---------------------------------------------------------
# LOAD ENV
# ---------------------------------------------------------
load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+asyncmy://chatuser:chatpass@localhost:3306/groupchat"
)

# ---------------------------------------------------------
# ENUMS
# ---------------------------------------------------------

class UserRole(str, enum.Enum):
    user = "user"
    therapist = "therapist"
    operator = "operator"

# ---------------------------------------------------------
# BASE CLASS
# ---------------------------------------------------------

class Base(DeclarativeBase):
    pass

# ---------------------------------------------------------
# USER TABLE
# ---------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    user_role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False, default=UserRole.user)

    password_hash: Mapped[str] = mapped_column(String(255))

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    # relations
    messages: Mapped[list["Message"]] = relationship("Message", back_populates="user")
    memberships: Mapped[list["ChatGroupUsers"]] = relationship("ChatGroupUsers", back_populates="user")

# ---------------------------------------------------------
# GROUP TABLES
# ---------------------------------------------------------

class ChatGroups(Base):
    __tablename__ = "chat_groups"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    group_name: Mapped[str] = mapped_column(String(50))
    is_ai_1on1: Mapped[bool] = mapped_column(Boolean(), default=False)
    current_size: Mapped[int] = mapped_column(nullable=False, default=0) 
    max_size: Mapped[int] = mapped_column(nullable=False, default=10)
    
    is_active: Mapped[bool] = mapped_column(Boolean(), default=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    memberships: Mapped[list["ChatGroupUsers"]] = relationship(
        "ChatGroupUsers", back_populates="group", cascade="all, delete-orphan"
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="group", cascade="all, delete-orphan"
    )


class ChatGroupUsers(Base):
    __tablename__ = "chat_group_users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("chat_groups.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    is_active: Mapped[bool] = mapped_column(Boolean(), default=False)

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    group: Mapped["ChatGroups"] = relationship("ChatGroups", back_populates="memberships")
    user: Mapped["User"] = relationship("User", back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uk_group_user"),
    )

# ---------------------------------------------------------
# GROUP MESSAGE TABLE
# ---------------------------------------------------------

class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    group_id: Mapped[int] = mapped_column(
        ForeignKey("chat_groups.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text)
    is_visible: Mapped[bool] = mapped_column(Boolean(), default=True)
    is_bot: Mapped[bool] = mapped_column(Boolean(), default=False)

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="messages")
    group: Mapped["ChatGroups"] = relationship("ChatGroups", back_populates="messages")
    flag_log: Mapped["MessageFlagLog"] = relationship(
        "MessageFlagLog", 
        back_populates="message", 
        uselist=False, 
        cascade="all, delete-orphan"
    )

class MessageFlagLog(Base):
    __tablename__ = "message_flag_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), unique=True
        )
    level: Mapped[int] = mapped_column(default=1)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    message: Mapped["Message"] = relationship("Message", back_populates="flag_log")
    
# ---------------------------------------------------------
# USER DAILY SUMMARY TABLE
# ---------------------------------------------------------
class DailyUserSummary(Base):
    __tablename__ = "daily_user_summaries"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("chat_groups.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    summary_date: Mapped["DateTime"] = mapped_column(DateTime(timezone=True))
    summary_text: Mapped[str | None] = mapped_column(Text(), nullable=True)
    mood: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())

    group: Mapped["ChatGroups"] = relationship("ChatGroups")
    user: Mapped["User"] = relationship("User")

# ---------------------------------------------------------
# OLD QUESTIONNAIRE (SYSTEM DEFAULT) — OPTIONAL
# ---------------------------------------------------------

class Questionnaires(Base):
    __tablename__ = "questionnaires"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    content: Mapped[dict] = mapped_column(JSON)

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now(),
                                                 onupdate=func.now())

# ---------------------------------------------------------
# THERAPIST PROFILE
# ---------------------------------------------------------

class TherapistProfile(Base):
    __tablename__ = "therapist_profiles"
    __table_args__ = {'extend_existing': True}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)

    avatar_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prefer_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    expertise: Mapped[str | None] = mapped_column(String(255), nullable=True)
    years_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    license_number: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now(),
                                                 onupdate=func.now())



# ---------------------------------------------------------
# USER PROFILE
# ---------------------------------------------------------
class UserProfile(Base):
    __tablename__ = "user_profiles"
    __table_args__ = {'extend_existing': True}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)

    avatar_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prefer_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)

    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    mood_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now(),
                                                 onupdate=func.now())


# ---------------------------------------------------------
# USER QUESTIONNAIRE ANSWERS (USER SUBMISSIONS)
# ---------------------------------------------------------

class UserQuestionnaire(Base):
    __tablename__ = "user_questionnaires"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    answers: Mapped[dict] = mapped_column(JSON, nullable=False)
    recommendation: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now(),
                                                 onupdate=func.now())

# ---------------------------------------------------------
# USER <-> THERAPIST RELATIONSHIP
# ---------------------------------------------------------

class UserTherapist(Base):
    __tablename__ = "user_therapists"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    therapist_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

# ---------------------------------------------------------
# USER ↔ THERAPIST CHAT
# ---------------------------------------------------------

class UserTherapistChat(Base):
    __tablename__ = "user_therapist_chats"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    therapist_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")
    message: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

# ---------------------------------------------------------
# MAILBOX (Your app.py uses this — must include)
# ---------------------------------------------------------

class MailboxMessage(Base):
    __tablename__ = "mailbox_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    from_user: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=True 
    )
    to_user: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    content: Mapped[dict] = mapped_column(JSON, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

# ---------------------------------------------------------
# ENGINE & SESSION
# ---------------------------------------------------------

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True
)
async_session_maker = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# ---------------------------------------------------------
# INIT DB
# ---------------------------------------------------------

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session