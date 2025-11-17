import os
import asyncio
import json
from typing import Optional, List
from fastapi import (
    FastAPI, WebSocket, WebSocketDisconnect, Depends,
    HTTPException, status, Query
)
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv
from cryptography.fernet import Fernet

from db import (
    SessionLocal, init_db, User, Message, ChatGroups, ChatGroupUsers,
    UserRole, TherapistProfile, UserQuestionnaire, MailboxMessage,
    UserTherapist, UserTherapistChat
)
from auth import (
    get_password_hash, verify_password, create_access_token,
    get_current_user_token, verify_websocket_token
)
from websocket_manager import ConnectionManager
from llm import chat_completion

# ----------------------------------------------------
# Load environment & encryption
# ----------------------------------------------------

load_dotenv()

ENCRYPTION_KEY = os.environ.get("MY_APP_SECRET_KEY")
if not ENCRYPTION_KEY:
    raise ValueError("MY_APP_SECRET_KEY missing")
cipher_suite = Fernet(ENCRYPTION_KEY.encode())

APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))

app = FastAPI(title="Group Chat + Therapist System")

app.mount("/static", StaticFiles(directory="static"), name="static")
AVATAR_DIR = "static/avatars"

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


# ----------------------------------------------------
# Encryption utils
# ----------------------------------------------------
def encrypt(text: str):
    return cipher_suite.encrypt(text.encode()).decode()


def decrypt(token: str):
    return cipher_suite.decrypt(token.encode()).decode()


# ----------------------------------------------------
# WebSocket connection manager
# ----------------------------------------------------

class UserConnectionManager:
    def __init__(self):
        self.active_users: dict[int, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self.active_users[user_id] = websocket

    async def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self.active_users:
            del self.active_users[user_id]

    async def send_to_user(self, user_id: int, message: dict):
        ws = self.active_users.get(user_id)
        if ws:
            await ws.send_json(message)


manager = UserConnectionManager()


# ----------------------------------------------------
# Schemas
# ----------------------------------------------------

class TokenData(BaseModel):
    username: str
    role: str
    user_id: int


class AuthPayload(BaseModel):
    username: str
    password: str
    prefer_name: Optional[str] = None


class ChangePasswordPayload(BaseModel):
    old_password: str
    new_password: str


class AvatarUpdatePayload(BaseModel):
    avatar_url: str


class PreferNameUpdatePayload(BaseModel):
    prefer_name: str


class AssignTherapistPayload(BaseModel):
    therapist_id: int


class ChatSendPayload(BaseModel):
    target_id: int
    message: str


class TherapistProfileCreate(BaseModel):
    bio: Optional[str] = None
    expertise: Optional[str] = None
    years_experience: Optional[int] = None
    license_number: Optional[str] = None
    prefer_name: Optional[str] = None


class TherapistProfileUpdate(BaseModel):
    bio: Optional[str] = None
    expertise: Optional[str] = None
    years_experience: Optional[int] = None
    license_number: Optional[str] = None
    prefer_name: Optional[str] = None
    


class MessagePayload(BaseModel):
    content: str
    group_id: int


class MemberAdd(BaseModel):
    username: str


class ChatGroupCreate(BaseModel):
    group_name: Optional[str] = "new group"
    usernames: List[str]


class ChatGroupUpdate(BaseModel):
    group_name: str


class ChatGroupResponse(BaseModel):
    id: int
    group_name: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True


class QuestionnairePayload(BaseModel):
    content: dict


class MarkReadPayload(BaseModel):
    message_id: int


# ----------------------------------------------------
# DB Session Dependency
# ----------------------------------------------------
async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


# ----------------------------------------------------
# Broadcast helper
# ----------------------------------------------------

async def broadcast_message(session: AsyncSession, msg: Message, group_id: int):
    username = None
    if msg.user_id:
        u = await session.get(User, msg.user_id)
        username = u.username if u else "unknown"

    payload = {
        "type": "message",
        "message": {
            "id": msg.id,
            "username": "LLM Bot" if msg.is_bot else username,
            "group_id": group_id,
            "content": decrypt(msg.content),
            "is_bot": msg.is_bot,
            "created_at": str(msg.created_at)
        }
    }

    stmt = select(ChatGroupUsers.user_id).where(ChatGroupUsers.group_id == group_id)
    member_ids = (await session.execute(stmt)).scalars().all()

    for uid in member_ids:
        await manager.send_to_user(uid, payload)


# ----------------------------------------------------
# LLM Auto Response
# ----------------------------------------------------

async def maybe_answer_with_llm(session: AsyncSession, content: str, group_id: int):
    if "?" not in content:
        return

    system_prompt = (
        "You are a helpful assistant in a group chat. "
        "Answer concisely and clearly."
    )
    try:
        reply = await chat_completion([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content}
        ])
    except Exception as e:
        reply = f"(LLM error) {str(e)}"

    bot_msg = Message(
        user_id=None, content=encrypt(reply),
        is_bot=True, group_id=group_id
    )
    session.add(bot_msg)
    await session.commit()
    await session.refresh(bot_msg)

    await broadcast_message(session, bot_msg, group_id)


# ----------------------------------------------------
# Startup: init DB
# ----------------------------------------------------
@app.on_event("startup")
async def on_startup():
    await init_db()


# ----------------------------------------------------
# USER SIGNUP / LOGIN / PASSWORD
# ----------------------------------------------------

@app.post("/api/signup")
async def signup(payload: AuthPayload, session: AsyncSession = Depends(get_db)):
    exists = await session.execute(select(User).where(User.username == payload.username))
    if exists.scalar_one_or_none():
        raise HTTPException(400, "Username already taken")

    u = User(
        username=payload.username,
        password_hash=get_password_hash(payload.password),
        prefer_name=payload.prefer_name,
        user_role=UserRole.user,
        basic_info=None
    )
    session.add(u)
    await session.commit()
    await session.refresh(u)

    token = create_access_token({
        "username": u.username,
        "role": u.user_role.value,
        "user_id": u.id
    })
    return {"ok": True, "token": token}


@app.post("/api/login")
async def login(payload: AuthPayload, session: AsyncSession = Depends(get_db)):
    res = await session.execute(select(User).where(User.username == payload.username))
    u = res.scalar_one_or_none()
    if not u or not verify_password(payload.password, u.password_hash):
        raise HTTPException(401, "Invalid credentials")

    token = create_access_token({
        "username": u.username,
        "role": u.user_role.value,
        "user_id": u.id
    })
    return {"ok": True, "token": token}


@app.post("/api/auth/change-password")
async def change_password(
    payload: ChangePasswordPayload,
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    user = (await session.execute(
        select(User).where(User.username == token_data.username)
    )).scalar_one_or_none()

    if not verify_password(payload.old_password, user.password_hash):
        raise HTTPException(400, "Incorrect current password")

    user.password_hash = get_password_hash(payload.new_password)
    session.add(user)
    await session.commit()

    return {"ok": True}


# ----------------------------------------------------
# AVATAR + PROFILE
# ----------------------------------------------------

@app.get("/api/avatars")
async def list_avatars(token_data: TokenData = Depends(get_current_user_token)):
    try:
        files = sorted(os.listdir(AVATAR_DIR))
    except:
        return {"avatars": []}

    valid_exts = (".png", ".jpg", ".jpeg", ".avif", ".webp")
    return {
        "avatars": [
            f"/static/avatars/{f}"
            for f in files if f.lower().endswith(valid_exts)
        ]
    }


@app.post("/api/users/avatar")
async def update_avatar(
    payload: AvatarUpdatePayload,
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    user = (await session.execute(
        select(User).where(User.username == token_data.username)
    )).scalar_one_or_none()

    user.avatar_url = payload.avatar_url
    session.add(user)
    await session.commit()

    return {"ok": True}


@app.post("/api/users/prefer_name")
async def update_prefer_name(
    payload: PreferNameUpdatePayload,
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    user = (await session.execute(
        select(User).where(User.username == token_data.username)
    )).scalar_one_or_none()

    user.prefer_name = payload.prefer_name
    session.add(user)
    await session.commit()

    return {"ok": True}


# ----------------------------------------------------
# THERAPIST LIST / PROFILE
# ----------------------------------------------------

@app.get("/api/therapists")
async def list_therapists(
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    stmt = (
        select(User, TherapistProfile)
        .outerjoin(TherapistProfile)
        .where(User.user_role == UserRole.therapist)
    )

    rows = (await session.execute(stmt)).all()

    out = []
    for user, profile in rows:
        out.append({
            "id": user.id,
            "username": user.username,
            "prefer_name": user.prefer_name,
            "bio": profile.bio if profile else None,
            "expertise": profile.expertise if profile else None,
            "years_experience": profile.years_experience if profile else None
        })

    return {"therapists": out}


@app.post("/api/therapist/profile")
async def create_therapist_profile(
    payload: TherapistProfileCreate,
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    if token_data.role != UserRole.therapist:
        raise HTTPException(403)

    exists = (await session.execute(
        select(TherapistProfile).where(TherapistProfile.user_id == token_data.user_id)
    )).scalar_one_or_none()

    if exists:
        raise HTTPException(400, "Profile already exists")

    p = TherapistProfile(
        user_id=token_data.user_id,
        bio=payload.bio,
        expertise=payload.expertise,
        years_experience=payload.years_experience,
        license_number=payload.license_number,
        prefer_name=payload.prefer_name
    )
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return {"ok": True, "profile": p}


@app.post("/api/therapist/profile/update")
async def update_therapist_profile(
    payload: TherapistProfileUpdate,
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    if token_data.role != UserRole.therapist:
        raise HTTPException(403)

    profile = (await session.execute(
        select(TherapistProfile).where(TherapistProfile.user_id == token_data.user_id)
    )).scalar_one_or_none()

    if not profile:
        raise HTTPException(404)

    data = payload.dict(exclude_unset=True)
    for k, v in data.items():
        setattr(profile, k, v)

    session.add(profile)
    await session.commit()
    await session.refresh(profile)

    return {"ok": True, "profile": profile}


@app.get("/api/therapist/profile/me")
async def get_my_therapist_profile(
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    if token_data.role != UserRole.therapist:
        raise HTTPException(403)

    stmt = (
        select(User, TherapistProfile)
        .outerjoin(TherapistProfile)
        .where(User.id == token_data.user_id)
    )
    user, profile = (await session.execute(stmt)).one_or_none()

    if not profile:
        profile = TherapistProfile(
            user_id=user.id, bio="", expertise="",
            years_experience=0, license_number="", prefer_name=user.prefer_name
        )
        session.add(profile)
        await session.commit()
        await session.refresh(profile)

    return {
        "username": user.username,
        "prefer_name": user.prefer_name,
        "avatar_url": user.avatar_url,
        "bio": profile.bio,
        "expertise": profile.expertise,
        "years_experience": profile.years_experience,
        "license_number": profile.license_number,
        "prefer_name": profile.prefer_name
    }


# ----------------------------------------------------
# ASSIGN THERAPIST (User → Therapist)
# ----------------------------------------------------

@app.post("/api/users/me/assign-therapist")
async def assign_my_therapist(
    payload: AssignTherapistPayload,
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    if token_data.role != UserRole.user:
        raise HTTPException(403)

    therapist = await session.get(User, payload.therapist_id)
    if not therapist or therapist.user_role != UserRole.therapist:
        raise HTTPException(400, "Invalid therapist")

    stmt = select(UserTherapist).where(UserTherapist.user_id == token_data.user_id)
    rel = (await session.execute(stmt)).scalar_one_or_none()

    if rel:
        rel.therapist_id = payload.therapist_id
    else:
        rel = UserTherapist(
            user_id=token_data.user_id,
            therapist_id=payload.therapist_id
        )
        session.add(rel)

    await session.commit()
    return {"ok": True}


@app.get("/api/users/me/therapist")
async def get_my_therapist(
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    stmt = select(UserTherapist).where(UserTherapist.user_id == token_data.user_id)
    rel = (await session.execute(stmt)).scalar_one_or_none()

    if not rel:
        return {"has_therapist": False}

    therapist = await session.get(User, rel.therapist_id)
    profile = (await session.execute(
        select(TherapistProfile).where(TherapistProfile.user_id == rel.therapist_id)
    )).scalar_one_or_none()

    return {
        "has_therapist": True,
        "therapist": {
            "id": therapist.id,
            "username": therapist.username,
            "avatar_url": therapist.avatar_url,
            "bio": profile.bio if profile else None,
            "expertise": profile.expertise if profile else None,
            "years_experience": profile.years_experience if profile else None,  
            "prefer_name": profile.prefer_name if profile else None
        }
    }


# ----------------------------------------------------
# USER–THERAPIST PRIVATE CHAT
# ----------------------------------------------------

@app.post("/api/therapist-chat/send")
async def send_user_therapist_message(
    payload: ChatSendPayload,
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    sender_id = token_data.user_id
    target_id = payload.target_id

    # find relation
    stmt = select(UserTherapist).where(
        (UserTherapist.user_id == sender_id) |
        (UserTherapist.therapist_id == sender_id)
    )
    rel = (await session.execute(stmt)).scalar_one_or_none()

    if not rel:
        raise HTTPException(403, "No relationship found")

    # validate
    if sender_id == rel.user_id:
        if target_id != rel.therapist_id:
            raise HTTPException(403)
    elif sender_id == rel.therapist_id:
        if target_id != rel.user_id:
            raise HTTPException(403)
    else:
        raise HTTPException(403)

    chat = UserTherapistChat(
        user_id=rel.user_id,
        therapist_id=rel.therapist_id,
        sender_id=sender_id,
        message=encrypt(payload.message),
        is_read=False
    )
    session.add(chat)
    await session.commit()
    await session.refresh(chat)

    return {"ok": True, "chat_id": chat.id}


@app.post("/api/therapist-chat/mark-read")
async def mark_read(
    payload: MarkReadPayload,
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    msg = await session.get(UserTherapistChat, payload.message_id)
    if not msg:
        raise HTTPException(404)

    if token_data.user_id not in (msg.user_id, msg.therapist_id):
        raise HTTPException(403)

    if msg.sender_id == token_data.user_id:
        raise HTTPException(400, "Cannot mark your own message")

    msg.is_read = True
    session.add(msg)
    await session.commit()

    return {"ok": True}


@app.get("/api/therapist-chat/messages")
async def list_messages(
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    stmt = select(UserTherapist).where(
        (UserTherapist.user_id == token_data.user_id) |
        (UserTherapist.therapist_id == token_data.user_id)
    )
    rel = (await session.execute(stmt)).scalar_one_or_none()
    if not rel:
        raise HTTPException(403)

    stmt = (
        select(UserTherapistChat)
        .where(
            (UserTherapistChat.user_id == rel.user_id) &
            (UserTherapistChat.therapist_id == rel.therapist_id)
        )
        .order_by(UserTherapistChat.created_at)
    )
    messages = (await session.execute(stmt)).scalars().all()

    return {
        "messages": [
            {
                "id": m.id,
                "sender_id": m.sender_id,
                "message": decrypt(m.message),
                "is_read": m.is_read,
                "created_at": m.created_at
            }
            for m in messages
        ]
    }


# ----------------------------------------------------
# THERAPIST: list users
# ----------------------------------------------------

@app.get("/api/therapist/my-users")
async def therapist_list_users(
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    if token_data.role != UserRole.therapist:
        raise HTTPException(403)

    stmt = select(UserTherapist).where(UserTherapist.therapist_id == token_data.user_id)
    relations = (await session.execute(stmt)).scalars().all()

    out = []
    for r in relations:
        user = await session.get(User, r.user_id)

        unread_stmt = select(func.count(UserTherapistChat.id)).where(
            (UserTherapistChat.user_id == user.id) &
            (UserTherapistChat.therapist_id == token_data.user_id) &
            (UserTherapistChat.sender_id == user.id) &
            (UserTherapistChat.is_read == False)
        )
        unread_count = (await session.execute(unread_stmt)).scalar()

        out.append({
            "id": user.id,
            "username": user.username,
            "prefer_name": user.prefer_name,
            "avatar_url": user.avatar_url,
            "unread": unread_count
        })

    return {"users": out}


@app.get("/api/therapist-chat/messages/{user_id}")
async def therapist_chat_with_user(
    user_id: int,
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    if token_data.role != UserRole.therapist:
        raise HTTPException(403)

    stmt = select(UserTherapist).where(
        (UserTherapist.user_id == user_id) &
        (UserTherapist.therapist_id == token_data.user_id)
    )
    rel = (await session.execute(stmt)).scalar_one_or_none()
    if not rel:
        raise HTTPException(403, "Not assigned")

    stmt = (
        select(UserTherapistChat)
        .where(
            (UserTherapistChat.user_id == user_id) &
            (UserTherapistChat.therapist_id == token_data.user_id)
        )
        .order_by(UserTherapistChat.created_at)
    )
    msgs = (await session.execute(stmt)).scalars().all()

    return {
        "messages": [
            {
                "id": m.id,
                "sender_id": m.sender_id,
                "message": decrypt(m.message),
                "is_read": m.is_read,
                "created_at": m.created_at
            }
            for m in msgs
        ]
    }


# ----------------------------------------------------
# GROUPCHAT
# ----------------------------------------------------

@app.get("/api/messages")
async def get_group_messages(
    group_id: int,
    limit: int = 50,
    session: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Message)
        .where(Message.group_id == group_id)
        .order_by(desc(Message.created_at), desc(Message.id))
        .limit(limit)
    )
    msgs = list(reversed((await session.execute(stmt)).scalars().all()))

    out = []
    for m in msgs:
        username = None
        if not m.is_bot and m.user_id:
            u = await session.get(User, m.user_id)
            username = u.username if u else "unknown"

        out.append({
            "id": m.id,
            "username": "LLM Bot" if m.is_bot else username,
            "content": decrypt(m.content),
            "is_bot": m.is_bot,
            "created_at": str(m.created_at)
        })
    return {"messages": out}


@app.post("/api/messages")
async def post_group_message(
    payload: MessagePayload,
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    # check membership
    stmt = select(ChatGroupUsers).where(
        ChatGroupUsers.group_id == payload.group_id,
        ChatGroupUsers.user_id == token_data.user_id,
        ChatGroupUsers.is_active == True
    )
    if not (await session.execute(stmt)).scalar_one_or_none():
        raise HTTPException(403)

    m = Message(
        user_id=token_data.user_id,
        content=encrypt(payload.content),
        is_bot=False,
        group_id=payload.group_id
    )
    session.add(m)
    await session.commit()
    await session.refresh(m)

    await broadcast_message(session, m, payload.group_id)

    asyncio.create_task(maybe_answer_with_llm(session, payload.content, payload.group_id))

    return {"ok": True, "id": m.id}


# -------------------------------
# GROUP CRUD
# -------------------------------

@app.post("/api/chat-groups")
async def create_group(
    payload: ChatGroupCreate,
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    if token_data.role != UserRole.therapist:
        raise HTTPException(403, "Only therapist")

    if not payload.usernames:
        raise HTTPException(400, "Empty group")

    stmt = select(User).where(User.username.in_(payload.usernames))
    users = (await session.execute(stmt)).scalars().all()

    if len(users) != len(payload.usernames):
        found = {u.username for u in users}
        missing = [n for n in payload.usernames if n not in found]
        raise HTTPException(404, f"Users not found: {missing}")

    group = ChatGroups(group_name=payload.group_name, is_active=True)
    session.add(group)
    await session.flush()

    members = [
        ChatGroupUsers(group_id=group.id, user_id=u.id, is_active=True)
        for u in users
    ]
    session.add_all(members)
    await session.commit()
    await session.refresh(group)

    return group


@app.get("/api/chat-groups", response_model=List[ChatGroupResponse])
async def list_my_groups(
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    stmt = (
        select(ChatGroups)
        .join(ChatGroupUsers)
        .where(ChatGroupUsers.user_id == token_data.user_id)
        .order_by(ChatGroups.group_name)
    )
    groups = (await session.execute(stmt)).scalars().all()
    return groups


@app.post("/api/chat-groups/{group_id}")
async def rename_group(
    group_id: int,
    payload: ChatGroupUpdate,
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    group = await session.get(ChatGroups, group_id)
    if not group:
        raise HTTPException(404)

    stmt = select(ChatGroupUsers).where(
        ChatGroupUsers.group_id == group_id,
        ChatGroupUsers.user_id == token_data.user_id
    )
    if not (await session.execute(stmt)).scalar_one_or_none():
        raise HTTPException(403)

    group.group_name = payload.group_name
    session.add(group)
    await session.commit()
    await session.refresh(group)

    return group


@app.post("/api/chat-groups/{group_id}/members")
async def add_member(
    group_id: int,
    payload: MemberAdd,
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    # Must be in the group
    stmt = select(ChatGroupUsers).where(
        ChatGroupUsers.group_id == group_id,
        ChatGroupUsers.user_id == token_data.user_id
    )
    if not (await session.execute(stmt)).scalar_one_or_none():
        raise HTTPException(403)

    new_user = (await session.execute(
        select(User).where(User.username == payload.username)
    )).scalar_one_or_none()

    if not new_user:
        raise HTTPException(404, "User not found")

    exists = (await session.execute(
        select(ChatGroupUsers).where(
            ChatGroupUsers.group_id == group_id,
            ChatGroupUsers.user_id == new_user.id
        )
    )).scalar_one_or_none()

    if exists:
        raise HTTPException(400, "Already in group")

    m = ChatGroupUsers(group_id=group_id, user_id=new_user.id, is_active=True)
    session.add(m)
    await session.commit()

    return {"ok": True}


# ----------------------------------------------------
# QUESTIONNAIRE + MAILBOX
# ----------------------------------------------------
@app.get("/api/user/questionnaire")
async def save_questionnaire(
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    if token_data.role != UserRole.user:
        raise HTTPException(403)
    
    res = await session.execute(select(UserQuestionnaire).where(UserQuestionnaire.user_id == token_data.user_id))
    existing = res.scalar_one_or_none()

    if existing:
        return {"ok": True}
    
    return {"ok": False}
    
@app.post("/api/user/questionnaire")
async def save_questionnaire(payload: QuestionnairePayload, token_data: TokenData = Depends(get_current_user_token), session: AsyncSession = Depends(get_db)):
    # Save questionnaire
    res = await session.execute(select(UserQuestionnaire).where(UserQuestionnaire.user_id == token_data.user_id))
    existing = res.scalar_one_or_none()

    if existing:
        existing.answers = payload.content
        session.add(existing)
    else:
        new_q = UserQuestionnaire(
            user_id = token_data.user_id,
            answers = payload.content
        )
        session.add(new_q)

    # Get user info
    user = await session.get(User, token_data.user_id)

    # look for chosen therapist
    rel = await session.execute(select(UserTherapist).where(UserTherapist.user_id == token_data.user_id))
    rel = rel.scalar_one_or_none()

    if rel:
        therapist_id = rel.therapist_id

        # send to target therapist
        notice = MailboxMessage(
            from_user=user.id,
            to_user=therapist_id,
            content={
                "type": "questionnaire",
                "user": user.username,
                "answers": payload.content
            }
        )
        session.add(notice)

    await session.commit()
    return {"ok": True}

# Public therapist profile
@app.get("/api/therapist/profile/{therapist_id}")
async def get_public_therapist_profile(therapist_id: int, session: AsyncSession = Depends(get_db)):
    # look for therapist
    stmt = (
        select(User, TherapistProfile)
        .outerjoin(TherapistProfile, TherapistProfile.user_id == User.id)
        .where(User.id == therapist_id, User.user_role == UserRole.therapist)
    )
    result = await session.execute(stmt)
    row = result.one_or_none()

    if not row:
        raise HTTPException(404, "Therapist not found")

    user, profile = row

    return {
        "id": user.id,
        "username": user.username,
        "avatar_url": user.avatar_url,
        "bio": profile.bio if profile else "",
        "expertise": profile.expertise if profile else "",
        "years_experience": profile.years_experience if profile else 0,
        "license_number": profile.license_number if profile else "",
        "prefer_name": profile.prefer_name if profile else user.prefer_name
    }

@app.get("/api/mailbox")
async def get_mailbox(
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    stmt = (
        select(MailboxMessage)
        .where(MailboxMessage.to_user == token_data.user_id)
        .order_by(desc(MailboxMessage.created_at))
    )
    msgs = (await session.execute(stmt)).scalars().all()

    out = []
    for m in msgs:
        c = m.content or {}
        if c.get("type") == "questionnaire":
            out.append({
                "id": m.id,
                "from_user": m.from_user,
                "to_user": m.to_user,
                "content": {
                    "type": "questionnaire",
                    "user": c.get("user"),
                    "answers": c.get("answers")
                },
                "is_read": m.is_read,
                "created_at": m.created_at
            })
        else:
            out.append({
                "id": m.id,
                "from_user": m.from_user,
                "to_user": m.to_user,
                "content": {"type": "text", "text": str(c)},
                "is_read": m.is_read,
                "created_at": m.created_at
            })
    return out


@app.post("/api/mailbox/read")
async def mark_mail_read(
    payload: dict,
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    mail_id = payload.get("mail_id")
    msg = await session.get(MailboxMessage, mail_id)

    if not msg or msg.to_user != token_data.user_id:
        raise HTTPException(404)

    msg.is_read = True
    session.add(msg)
    await session.commit()

    return {"ok": True}


@app.post("/api/mailbox/approve")
async def approve_user(
    payload: dict,
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    if token_data.role != UserRole.therapist:
        raise HTTPException(403)

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(400)

    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(404)

    notice = MailboxMessage(
        from_user=token_data.user_id,
        to_user=user_id,
        content="Your questionnaire has been approved!"
    )
    session.add(notice)
    await session.commit()

    return {"ok": True}


# ----------------------------------------------------
# WEBSOCKET
# ----------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    session: AsyncSession = Depends(get_db)
):
    try:
        token_data = verify_websocket_token(token)
        if not token_data:
            await websocket.accept()
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    except:
        await websocket.accept()
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    uid = token_data.user_id
    await manager.connect(websocket, uid)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket, uid)
    except Exception:
        await manager.disconnect(websocket, uid)


# ----------------------------------------------------
# SERVE FRONTEND
# ----------------------------------------------------
app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")

