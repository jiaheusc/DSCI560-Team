import os
import asyncio
from typing import Optional, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Request, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select, desc, Enum, func
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv

from cryptography.fernet import Fernet

from db import SessionLocal, init_db, User, Message, ChatGroups, ChatGroupUsers, UserRole, TherapistProfile, UserQuestionnaire, UserTherapist, UserTherapistChat
from auth import get_password_hash, verify_password, create_access_token, get_current_user_token, verify_websocket_token
from websocket_manager import ConnectionManager
from llm import chat_completion
import enum

ENCRYPTION_KEY = os.environ.get("MY_APP_SECRET_KEY")
if not ENCRYPTION_KEY:
    raise ValueError("not setting key")

cipher_suite = Fernet(ENCRYPTION_KEY.encode())

load_dotenv()

APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))

app = FastAPI(title="Group Chat with LLM Bot")

app.mount("/static", StaticFiles(directory="static"), name="static")
AVATAR_DIR = "static/avatars"


# Allow same-origin and dev origins by default
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- encrypt ---
def encrypt(text):
    return cipher_suite.encrypt(text.encode()).decode()

# --- decrypt ---
def decrypt(token):
    return cipher_suite.decrypt(token.encode()).decode()


class UserConnectionManager:

    def __init__(self):

        self.active_users: dict[int, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()

        self.active_users[user_id] = websocket

    def disconnect(self, websocket: WebSocket, user_id: int):

        if user_id in self.active_users:
            del self.active_users[user_id]

    async def send_to_user(self, user_id: int, message: dict):

        websocket = self.active_users.get(user_id)
        if websocket:
            await websocket.send_json(message)

manager = UserConnectionManager()

# --------- Schemas ---------
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

    class Config:
        from_attributes = True

class TherapistProfileUpdate(BaseModel):
    bio: Optional[str] = None
    expertise: Optional[str] = None
    years_experience: Optional[int] = None
    license_number: Optional[str] = None

class MessagePayload(BaseModel):
    content: str
    group_id: int

class MarkReadPayload(BaseModel):
    message_id: int

class ChatGroupCreate(BaseModel):
    group_name: Optional[str] = "new group"
    usernames: List[str]

class ChatGroupUpdate(BaseModel):
    group_name: str

class MemberAdd(BaseModel):
    username: str
  
class ChatGroupResponse(BaseModel):
    id: int
    group_name: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True

class QuestionnairePayload(BaseModel):
    content: dict


# --------- Dependencies ---------
async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session

# --------- Utilities ---------
async def broadcast_message(session: AsyncSession, msg: Message, group_id: int):
    # Load username
    username = None
    if msg.user_id:
        u = await session.get(User, msg.user_id)
        username = u.username if u else "unknown"
    payload = {
        "type": "message",
        "message": {
            "id": msg.id,
            "username": username if not msg.is_bot else "LLM Bot",
            "group_id": group_id,
            "content": decrypt(msg.content),
            "is_bot": msg.is_bot,
            "created_at": str(msg.created_at)
        }
    }

    # find all the group members
    stmt = select(ChatGroupUsers.user_id).where(ChatGroupUsers.group_id == group_id)
    result = await session.execute(stmt)
    member_ids = result.scalars().all()
    for user_id in member_ids:
        await manager.send_to_user(user_id, payload)

# llm answer question
async def maybe_answer_with_llm(session: AsyncSession, content: str, group_id: int):
    # naive heuristic: reply if the message contains a question mark
    if "?" not in content:
        return
    system_prompt = (
        "You are a helpful assistant participating in a small group chat. "
        "Provide concise, accurate answers suitable for a shared chat context. "
        "Cite facts succinctly when helpful and avoid extremely long messages."
    )
    try:
        reply_text = await chat_completion([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content}
        ])
    except Exception as e:
        reply_text = f"(LLM error) {e}"
    bot_msg = Message(user_id=None, content=encrypt(reply_text), is_bot=True, group_id=group_id)
    session.add(bot_msg)
    await session.commit()
    await session.refresh(bot_msg)
    await broadcast_message(session, bot_msg, group_id)
    return

async def get_user_therapist_relation(session, user_id_or_therapist_id: int):
    stmt = select(UserTherapist).where(
        (UserTherapist.user_id == user_id_or_therapist_id) |
        (UserTherapist.therapist_id == user_id_or_therapist_id)
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none()

# --------- Routes ---------
@app.on_event("startup")
async def on_startup():
    await init_db()

# normal user signup
@app.post("/api/signup")
async def signup(payload: AuthPayload, session: AsyncSession = Depends(get_db)):
    # check unique username
    existing = await session.execute(select(User).where(User.username == payload.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already taken")
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
    print(f"user role: {u.user_role.value}")
    token = create_access_token({"username": u.username, "role": u.user_role.value, "user_id": u.id})
    return {"ok": True, "token": token}

# therapist signup
# only operator can create therapist account
@app.post("/api/create_therapist")
async def create_therapist(payload: AuthPayload, token_data: TokenData = Depends(get_current_user_token), session: AsyncSession = Depends(get_db)):
    
    # check is operator
    res = await session.execute(select(User).where(User.username == token_data.username))
    u = res.scalar_one_or_none()
    if u.user_role != UserRole.operator:
        raise HTTPException(status_code=403, detail="Only operator can create therapist accounts")

    # create therapist account
    existing = await session.execute(select(User).where(User.username == payload.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already taken")

    therapist = User(
        username=payload.username,
        password_hash=get_password_hash(payload.password),
        prefer_name=payload.prefer_name,
        user_role=UserRole.therapist,
        basic_info=None
    )
    session.add(therapist)
    await session.commit()
    await session.refresh(therapist)
    token = create_access_token({"username": therapist.username, "role": therapist.user_role.value, "user_id": therapist.id})
    return {"ok": True, "token": token}

# only for inside use
# @app.post("/api/operator/signup")
# async def signup(payload: AuthPayload, session: AsyncSession = Depends(get_db)):
#     # check unique username
#     existing = await session.execute(select(User).where(User.username == payload.username))
#     if existing.scalar_one_or_none():
#         raise HTTPException(status_code=400, detail="Username already taken")
#     operator = User(
#         username=payload.username, 
#         password_hash=get_password_hash(payload.password),
#         user_role=UserRole.operator,
#         prefer_name=payload.prefer_name,
#         basic_info=None
#     )
#     session.add(operator)
#     await session.commit()
#     await session.refresh(operator)
#     token = create_access_token({"username": operator.username, "role": operator.user_role.value, "user_id": operator.id})
#     return {"ok": True, "token": token}

# all user login
@app.post("/api/login")
async def login(payload: AuthPayload, session: AsyncSession = Depends(get_db)):
    res = await session.execute(select(User).where(User.username == payload.username))
    u = res.scalar_one_or_none()
    if not u or not verify_password(payload.password, u.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"username": u.username, "role": u.user_role.value, "user_id": u.id})
    return {"ok": True, "token": token}

# change password
@app.post("/api/auth/change-password")
async def change_password(payload: ChangePasswordPayload, token_data: TokenData = Depends(get_current_user_token), session: AsyncSession = Depends(get_db)):
    res = await session.execute(select(User).where(User.username == token_data.username))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid user")
    
    if not verify_password(payload.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect current password")

    user.password_hash = get_password_hash(payload.new_password)
    session.add(user)
    await session.commit()

    return {"ok": True, "msg": "Password updated successfully"}

# get all avatars
@app.get("/api/avatars")
async def list_avatars(token_data: TokenData = Depends(get_current_user_token)):
    try:
        files = sorted(os.listdir(AVATAR_DIR))
    except FileNotFoundError:
        return JSONResponse(status_code=500, content={"error": "Avatar directory not found"})

    valid_exts = (".png", ".jpg", ".jpeg", ".avif", ".webp")
    avatars = [
        f"/static/avatars/{f}"
        for f in files
        if f.lower().endswith(valid_exts)
    ]

    return {"avatars": avatars}

# add or modify avatars
@app.post("/api/users/avatar")
async def update_avatar(payload: AvatarUpdatePayload, token_data: TokenData = Depends(get_current_user_token), session: AsyncSession = Depends(get_db)):

    res = await session.execute(select(User).where(User.username == token_data.username))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid user")

    user.avatar_url = payload.avatar_url
    session.add(user)
    await session.commit()

    return {"ok": True}

# add or modify prefer_name
@app.post("/api/users/prefer_name")
async def update_prefer_name(payload: PreferNameUpdatePayload, token_data: TokenData = Depends(get_current_user_token), session: AsyncSession = Depends(get_db)):

    res = await session.execute(select(User).where(User.username == token_data.username))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid user")

    user.prefer_name = payload.prefer_name
    session.add(user)
    await session.commit()

    return {"ok": True}

# list all therapist with profile (bio & expertise)
@app.get("/api/therapists")
async def list_therapists(token_data: TokenData = Depends(get_current_user_token), session: AsyncSession = Depends(get_db)):
    stmt = (
        select(User, TherapistProfile)
        .outerjoin(TherapistProfile, TherapistProfile.user_id == User.id)
        .where(User.user_role == UserRole.therapist)
    )

    result = await session.execute(stmt)
    rows = result.all()

    therapists = []
    for user, profile in rows:
        therapists.append({
            "id": user.id, 
            "username": user.username,
            "prefer_name": user.prefer_name,
            "bio": profile.bio if profile else None,
            "expertise": profile.expertise if profile else None,
            "has_profile": profile is not None
        })

    return {"therapists": therapists}
    
# user choose a therapist
@app.post("/api/users/me/assign-therapist")
async def assign_my_therapist(payload: AssignTherapistPayload, token_data: TokenData = Depends(get_current_user_token), session: AsyncSession = Depends(get_db)):
    if token_data.role != UserRole.user:
        raise HTTPException(status_code=403, detail="Only users can assign a therapist")

    user_id = token_data.user_id

    res = await session.execute(select(User).where(User.id == payload.therapist_id))
    therapist = res.scalar_one_or_none()

    if not therapist or therapist.user_role != UserRole.therapist:
        raise HTTPException(status_code=400, detail="Invalid therapist")

    res = await session.execute(select(UserTherapist).where(UserTherapist.user_id == user_id))
    relation = res.scalar_one_or_none()

    if relation:
        relation.therapist_id = payload.therapist_id
        session.add(relation)
    else:
        new_rel = UserTherapist(
            user_id=user_id,
            therapist_id=payload.therapist_id
        )
        session.add(new_rel)

    await session.commit()

    return {"ok": True, "therapist_id": payload.therapist_id}

# user get their therapist profile
@app.get("/api/users/me/therapist")
async def get_my_therapist(token_data: TokenData = Depends(get_current_user_token), session: AsyncSession = Depends(get_db)):
    if token_data.role != UserRole.user:
        raise HTTPException(status_code=403, detail="Only users can check therapist profile")

    user_id = token_data.user_id

    res = await session.execute(select(UserTherapist).where(UserTherapist.user_id == user_id))
    link = res.scalar_one_or_none()

    if not link:
        return {"has_therapist": False}

    therapist_id = link.therapist_id

    res = await session.execute(select(User).where(User.id == therapist_id))
    therapist = res.scalar_one()

    res = await session.execute(select(TherapistProfile).where(TherapistProfile.user_id == therapist_id))
    profile = res.scalar_one_or_none()

    return {
        "has_therapist": True,
        "therapist": {
            "id": therapist.id,
            "username": therapist.username, # 需要吗？
            "prefer_name": therapist.prefer_name,
            "avatar_url": therapist.avatar_url,
            "bio": profile.bio if profile else None,
            "expertise": profile.expertise if profile else None,
            "years_experience": profile.years_experience if profile else None,
        }
    }

# send message (chat between user and therapist)
# parameter: target_id, message
@app.post("/api/therapist-chat/send")
async def send_user_therapist_message(payload: ChatSendPayload, token_data: TokenData = Depends(get_current_user_token), session: AsyncSession = Depends(get_db)):
    sender_id = token_data.user_id
    target_id = payload.target_id

    rel = await get_user_therapist_relation(session, sender_id)
    if not rel:
        raise HTTPException(status_code=403, detail="No therapist-user relationship found")

    if sender_id == rel.user_id:
        if target_id != rel.therapist_id:
            raise HTTPException(status_code=403, detail="You are not assigned to this therapist")
        
        user_id = rel.user_id
        therapist_id = rel.therapist_id
    
    elif sender_id == rel.therapist_id:
        if target_id != rel.user_id:
            raise HTTPException(status_code=403, detail="Cannot message this user")
        
        user_id = rel.user_id
        therapist_id = rel.therapist_id

    else:
        raise HTTPException(status_code=403, detail="Invalid sender")

    chat = UserTherapistChat(
        user_id=user_id,
        therapist_id=therapist_id,
        sender_id=sender_id,
        message=encrypt(payload.message),
        is_read=False,
    )
    session.add(chat)
    await session.commit()
    await session.refresh(chat)

    return {"ok": True, "chat_id": chat.id, "created_at": chat.created_at}

# mark unread message to read
# parameter: message_id
@app.post("/api/therapist-chat/mark-read")
async def mark_message_as_read(payload: MarkReadPayload,token_data: TokenData = Depends(get_current_user_token),session: AsyncSession = Depends(get_db)):
    my_id = token_data.user_id

    stmt = select(UserTherapistChat).where(UserTherapistChat.id == payload.message_id)
    res = await session.execute(stmt)
    msg = res.scalar_one_or_none()

    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if my_id not in (msg.user_id, msg.therapist_id):
        raise HTTPException(status_code=403, detail="Not allowed")

    if msg.sender_id == my_id:
        raise HTTPException(status_code=400, detail="Cannot mark your own message as read")

    msg.is_read = True
    session.add(msg)
    await session.commit()
    await session.refresh(msg)

    return {"ok": True, "message_id": msg.id}

# list all message between therapist and user (for user)
@app.get("/api/therapist-chat/messages")
async def get_chat_messages(token_data: TokenData = Depends(get_current_user_token), session: AsyncSession = Depends(get_db)):
    my_id = token_data.user_id

    rel = await get_user_therapist_relation(session, my_id)
    if not rel:
        raise HTTPException(status_code=403, detail="No therapist-user relationship found")

    user_id = rel.user_id
    therapist_id = rel.therapist_id

    stmt = (
        select(UserTherapistChat)
        .where(
            (UserTherapistChat.user_id == user_id) &
            (UserTherapistChat.therapist_id == therapist_id)
        )
        .order_by(UserTherapistChat.created_at)
    )
    res = await session.execute(stmt)
    messages = res.scalars().all()

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

# list all users of the therapist
@app.get("/api/therapist/my-users")
async def get_my_users(token_data: TokenData = Depends(get_current_user_token), session: AsyncSession = Depends(get_db)):
    if token_data.role != UserRole.therapist:
        raise HTTPException(status_code=403, detail="Only therapists can access this")

    therapist_id = token_data.user_id
    res = await session.execute(select(UserTherapist).where(UserTherapist.therapist_id == therapist_id))
    relations = res.scalars().all()

    if not relations:
        return {"users": []}

    users = []

    for rel in relations:
        user_res = await session.execute(select(User).where(User.id == rel.user_id))
        user = user_res.scalar_one_or_none()

        unread_stmt = select(func.count(UserTherapistChat.id)).where(
            (UserTherapistChat.user_id == user.id) &
            (UserTherapistChat.therapist_id == therapist_id) &
            (UserTherapistChat.sender_id == user.id) &  # user 发给 therapist
            (UserTherapistChat.is_read == False)
        )
        unread_res = await session.execute(unread_stmt)
        unread_count = unread_res.scalar()

        users.append({
            "id": user.id,
            "username": user.username,
            "prefer_name": user.prefer_name,
            "avatar_url": user.avatar_url,
            "unread": unread_count
        })

    return {"users": users}

# therapist get all message with one user
@app.get("/api/therapist-chat/messages/{user_id}")
async def get_chat_messages_with_user(user_id: int, token_data: TokenData = Depends(get_current_user_token), session: AsyncSession = Depends(get_db)):
    if token_data.role != UserRole.therapist:
        raise HTTPException(status_code=403, detail="Only therapists can view this")

    therapist_id = token_data.user_id

    stmt = select(UserTherapist).where((UserTherapist.user_id == user_id) & (UserTherapist.therapist_id == therapist_id))
    res = await session.execute(stmt)
    rel = res.scalar_one_or_none()

    if not rel:
        raise HTTPException(status_code=403, detail="This user is not assigned to you")

    msg_stmt = (
        select(UserTherapistChat)
        .where(
            (UserTherapistChat.user_id == user_id) &
            (UserTherapistChat.therapist_id == therapist_id)
        )
        .order_by(UserTherapistChat.created_at)
    )
    msg_res = await session.execute(msg_stmt)
    messages = msg_res.scalars().all()

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

# create therapist profiles
@app.post("/api/therapist/profile")
async def create_therapist_profile(payload: TherapistProfileCreate, token_data: TokenData = Depends(get_current_user_token), session: AsyncSession = Depends(get_db)):
    if token_data.role != UserRole.therapist:
        raise HTTPException(status_code=403, detail="Only therapists can create profiles")

    res = await session.execute(select(TherapistProfile).where(TherapistProfile.user_id == token_data.user_id))
    existing_profile = res.scalar_one_or_none()
    if existing_profile:
        raise HTTPException(status_code=400, detail="Profile already exists")

    new_profile = TherapistProfile(
        user_id=token_data.user_id,
        bio=payload.bio,
        expertise=payload.expertise,
        years_experience=payload.years_experience,
        license_number=payload.license_number,
    )

    session.add(new_profile)
    await session.commit()
    await session.refresh(new_profile)
    return {"ok": True, "profile": new_profile}

# therapist update their profile
@app.post("/api/therapist/profile/update")
async def update_therapist_profile(payload: TherapistProfileUpdate, token_data: TokenData = Depends(get_current_user_token), session: AsyncSession = Depends(get_db)):
    if token_data.role != UserRole.therapist:
        raise HTTPException(status_code=403, detail="Only therapists can modify profiles")

    res = await session.execute(select(TherapistProfile).where(TherapistProfile.user_id == token_data.user_id))
    profile = res.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    update_data = payload.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(profile, key, value)

    session.add(profile)
    await session.commit()
    await session.refresh(profile)

    return {"ok": True, "profile": profile}

# for user get their profile
@app.get("/api/user/profile/me")
async def get_my_user_profile(token_data: TokenData = Depends(get_current_user_token), session: AsyncSession = Depends(get_db)):
    if token_data.role != UserRole.user:
        raise HTTPException(status_code=403, detail="Only user can view profile")

    res = await session.execute(select(User).where(User.id == token_data.user_id))
    user = res.scalar_one_or_none()

    return {
        "username": user.username,
        "prefer_name": user.prefer_name,
        "avatar_url": user.avatar_url
    }

# for therapist get their profile
@app.get("/api/therapist/profile/me")
async def get_my_therapist_profile(token_data: TokenData = Depends(get_current_user_token), session: AsyncSession = Depends(get_db)):
    if token_data.role != UserRole.therapist:
        raise HTTPException(status_code=403, detail="Only therapists can view profile")

    stmt = (
        select(User, TherapistProfile)
        .outerjoin(TherapistProfile, TherapistProfile.user_id == User.id)
        .where(User.id == token_data.user_id)
    )

    result = await session.execute(stmt)
    row = result.one_or_none()

    if not row:
        raise HTTPException(status_code=404, detail="Profile not found")

    user, profile = row

    return {
        "username": user.username,
        "prefer_name": user.prefer_name,
        "avatar_url": user.avatar_url,
        "bio": profile.bio if profile else None,
        "expertise": profile.expertise if profile else None,
        "years_experience": profile.years_experience if profile else None,
        "license_number": profile.license_number if profile else None
    }

# get all message in a group
# /api/messages?group_id=***
@app.get("/api/messages")
async def get_messages(group_id: int, limit: int = 50, session: AsyncSession = Depends(get_db)):
    res = await session.execute(select(Message)
                                .where(Message.group_id == group_id)
                                .order_by(desc(Message.created_at), desc(Message.id))
                                .limit(limit))
    items = list(reversed(res.scalars().all()))
    out = []
    
    for m in items:
        username = None

        content_to_send = decrypt(m.content)
        if not m.is_bot and m.user_id:
            u = await session.get(User, m.user_id)
            username = u.username if u else "unknown"
        out.append({
            "id": m.id,
            "username": "LLM Bot" if m.is_bot else (username or "unknown"),
            "content": content_to_send,
            "is_bot": m.is_bot,
            "created_at": str(m.created_at)
        })
    return {"messages": out}

# user post a message in the group
@app.post("/api/messages")
async def post_message(payload: MessagePayload, token_data: TokenData = Depends(get_current_user_token), session: AsyncSession = Depends(get_db)):
    # res = await session.execute(select(User).where(User.username == token_data.username))
    # u = res.scalar_one_or_none()
    # if not u:
    #     raise HTTPException(status_code=401, detail="Invalid user")

    # check if group member
    group_id = payload.group_id
    check_stmt = select(ChatGroupUsers).where(
        ChatGroupUsers.group_id == group_id,
        ChatGroupUsers.user_id == token_data.user_id,
        ChatGroupUsers.is_active == True
    )
    if not (await session.execute(check_stmt)).scalar_one_or_none():
        raise HTTPException(status_code=403, detail="You are not a member of this group")
    

    content_to_save = encrypt(payload.content)
    m = Message(user_id=token_data.user_id, content=content_to_save, is_bot=False, group_id=group_id)
    session.add(m)
    await session.commit()
    await session.refresh(m)
    await broadcast_message(session, m, group_id)
    # fire-and-forget LLM answer
    asyncio.create_task(maybe_answer_with_llm(session, payload.content, group_id))
    return {"ok": True, "id": m.id}


# create chat group
@app.post("/api/chat-groups")
async def create_chat_group(payload: ChatGroupCreate, token_data: TokenData = Depends(get_current_user_token), session: AsyncSession = Depends(get_db)):
    if token_data.role != UserRole.therapist:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    
    if not payload.usernames:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot create a group with no members")
    
    stmt = select(User).where(User.username.in_(payload.usernames))
    res = await session.execute(stmt)
    users_to_add = res.scalars().all()

    if len(users_to_add) != len(payload.usernames):
        found_usernames = {u.username for u in users_to_add}
        missing = [name for name in payload.usernames if name not in found_usernames]
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Users not found: {', '.join(missing)}")
    
    # create new group
    new_group = ChatGroups(
        group_name=payload.group_name,
        is_active=True
    )
    session.add(new_group)
    await session.flush()

    # 是否把therapist也加进组里？

    # add member into the group
    members_to_add = []
    for user in users_to_add:
        member = ChatGroupUsers(
            group_id=new_group.id,
            user_id=user.id,
            is_active=True
        )
        members_to_add.append(member)

    session.add_all(members_to_add)
    await session.commit()
    await session.refresh(new_group)

    return new_group

# list all groups with group name
@app.get("/api/chat-groups", response_model=List[ChatGroupResponse])
async def get_user_groups(token_data: TokenData = Depends(get_current_user_token), session: AsyncSession = Depends(get_db)):
    
    stmt = (
        select(ChatGroups)
        .join(ChatGroupUsers, ChatGroupUsers.group_id == ChatGroups.id)
        .where(ChatGroupUsers.user_id == token_data.user_id, ChatGroupUsers.is_active == True)
        .order_by(ChatGroups.group_name)
    )
    # might need to change to order by last modified time
    result = await session.execute(stmt)
    groups = result.scalars().all()
    return groups

# add a user into a exist group
# 加新人是therapist加还是用户加？
@app.post("/api/chat-groups/{group_id}/members")
async def add_member_to_group(group_id: int, payload: MemberAdd, token_data: TokenData = Depends(get_current_user_token), session: AsyncSession = Depends(get_db)):
    res = await session.execute(select(User).where(User.username == token_data.username))
    current_user = res.scalar_one_or_none()
    if not current_user:
        raise HTTPException(status_code=401, detail="Invalid operator")
    
    # if are therapist check the role
    check_stmt = select(ChatGroupUsers).where(
        ChatGroupUsers.group_id == group_id,
        ChatGroupUsers.user_id == token_data.user_id
    )
    if not (await session.execute(check_stmt)).scalar_one_or_none():
        raise HTTPException(status_code=403, detail="You are not a member of this group")
    
    # find if added user in users db
    res_add = await session.execute(select(User).where(User.username == payload.username))
    user_to_add = res_add.scalar_one_or_none()
    if not user_to_add:
        raise HTTPException(status_code=404, detail=f"User '{payload.username}' not found")

    check_exists_stmt = select(ChatGroupUsers).where(
        ChatGroupUsers.group_id == group_id,
        ChatGroupUsers.user_id == user_to_add.id
    )
    if (await session.execute(check_exists_stmt)).scalar_one_or_none():
        raise HTTPException(status_code=4.0, detail="User is already in this group")
    
    new_membership = ChatGroupUsers(
        group_id=group_id,
        user_id=user_to_add.id,
        is_active=True
    )
    session.add(new_membership)
    await session.commit()
    return {"ok": True, "message": f"User {payload.username} added to group {group_id}"}

# modify group name
@app.post("/api/chat-groups/{group_id}")
async def update_group_name(group_id: int, payload: ChatGroupUpdate, token_data: TokenData = Depends(get_current_user_token), session: AsyncSession = Depends(get_db)):
    group = await session.get(ChatGroups, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    check_stmt = select(ChatGroupUsers).where(
        ChatGroupUsers.group_id == group_id,
        ChatGroupUsers.user_id == token_data.user_id
    )
    if not (await session.execute(check_stmt)).scalar_one_or_none():
        raise HTTPException(status_code=403, detail="You are not a member of this group")


    group.group_name = payload.group_name
    session.add(group)
    await session.commit()
    await session.refresh(group)
    
    return group

# create a questionnaire
# @app.post("/api/questionnaire")
# async def post_questionnaire(data: dict, token_data: TokenData = Depends(get_current_user_token), session: AsyncSession = Depends(get_db)):
#     if token_data.role != UserRole.operator:
#         raise HTTPException(status_code=403, detail="Only operator able to create questionnaire")

#     q = Questionnaires(content=data["content"])
#     session.add(q)
#     await session.commit()
#     return {"ok": True}

# get questionnaire
# @app.get("/api/questionnaire")
# async def post_questionnaire(token_data: TokenData = Depends(get_current_user_token), session: AsyncSession = Depends(get_db)):
#     res = await session.execute(select(Questionnaires).order_by(Questionnaires.updated_at.desc()).limit(1))
#     latest_questionnaire = res.scalar_one_or_none()
#     if not latest_questionnaire:
#         raise HTTPException(status_code=404, detail="No questionnaire found")
#     return latest_questionnaire


# save user questionnaire into db
@app.post("/api/user/questionnaire")
async def save_questionnaire(payload: QuestionnairePayload, token_data: TokenData = Depends(get_current_user_token), session: AsyncSession = Depends(get_db)):
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

    await session.commit()
    return {"ok": True}
    

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...), session: AsyncSession = Depends(get_db)):
    user_id = None
    
    try:
        token_data = verify_websocket_token(token)
        
        if not token_data:
            await websocket.accept() 
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
            return

        user_id = token_data.user_id

    except Exception as e:
        print(f"WS auth failed during token check: {e}")
        await websocket.accept() 
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Auth error")
        return
    
    await manager.connect(websocket, user_id) 

    try:
        while True:
            data = await websocket.receive_text()

    except WebSocketDisconnect:
        print(f"User {user_id} disconnected")
        await manager.disconnect(websocket, user_id) 
    except Exception as e:
        print(f"WS Error for {user_id}: {e}")
        await manager.disconnect(websocket, user_id)

# Serve frontend
app.mount("/", StaticFiles(directory="../frontend", html=True), name="static")
