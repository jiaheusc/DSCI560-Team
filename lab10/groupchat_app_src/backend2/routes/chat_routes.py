from typing import Dict
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from db import Message, ChatGroups, ChatGroupUsers, User, UserRole, get_db
from auth import get_current_user_token, verify_websocket_token
from websocket_manager import ConnectionManager
from llm import chat_completion
import time
import asyncio
from utils.security import encrypt, decrypt
from model.red_flag_detector import check_both, batch_check_both
from model.chatbot import MentalHealthChatbot
from schemas import (
    TokenData, MessagePayload, GroupMessageListResponse, 
    ChatGroupCreate, ChatGroupListResponse, ChatGroupUpdate, 
    ChatGroupResponse, MemberAdd, ChatRequest
)
router = APIRouter(prefix="/api", tags=["Group Chat"])

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
global_chatbot_instance = MentalHealthChatbot()

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

    stmt = select(ChatGroupUsers.user_id).where(
        ChatGroupUsers.group_id == group_id,
        ChatGroupUsers.is_active == True
    )
    member_ids = (await session.execute(stmt)).scalars().all()

    for uid in member_ids:
        await manager.send_to_user(uid, payload)

async def maybe_answer_with_llm(sender_id: int, content: str, group_id: int):
    if "?" not in content:
        return
    
    from db import SessionLocal, Message

    async with SessionLocal() as session:
        req = ChatRequest(
            user_id=str(sender_id),  # 使用实际发送者的 ID (需要转换为 str)
            message=content,
            history=[] # 历史记录仍为空，见第二点解释
        )
        start_time = time.time()
        try:
            # 调用 MentalHealthChatbot 实例
            res = global_chatbot_instance.handle_message(req)
            reply = res.reply
            
            duration = time.time() - start_time
            print(f"--- LLM Response Duration: {duration:.2f} seconds ---")
        except Exception as e:
            reply = f"(LLM error) Chatbot failed to generate reply. Error: {str(e)}"

        bot_msg = Message(
            user_id=None, content=encrypt(reply),
            is_bot=True, group_id=group_id
        )
        session.add(bot_msg)
        await session.commit()
        await session.refresh(bot_msg)

        await broadcast_message(session, bot_msg, group_id)

###
    # routers
###
MAX_SIZE = 10

# create a new group
@router.post("/chat-groups")
async def create_group(
    payload: ChatGroupCreate,
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    if token_data.role != UserRole.therapist:
        raise HTTPException(403, "Only therapist can create group")

    if not payload.usernames:
        raise HTTPException(400, "Group members list cannot be empty.")

    stmt = select(User).where(User.username.in_(payload.usernames))
    users = (await session.execute(stmt)).scalars().all()

    if len(users) != len(payload.usernames):
        found = {u.username for u in users}
        missing = [n for n in payload.usernames if n not in found]
        raise HTTPException(404, f"Users not found: {missing}")

    initial_member_count = len(users)

    if initial_member_count >= MAX_SIZE:
        raise HTTPException(400, f"Group is full. Max size is {MAX_SIZE}")
    
    group = ChatGroups(
        group_name=payload.group_name, 
        current_size=initial_member_count, 
        is_active=True
    )
    session.add(group)
    await session.flush()

    members = [
        ChatGroupUsers(group_id=group.id, user_id=u.id, is_active=True)
        for u in users
    ]
    session.add_all(members)
    await session.commit()
    await session.refresh(group)

    return group.id

# add a member into a group
@router.post("/chat-groups/{group_id}/member")
async def add_member(
    group_id: int,
    payload: MemberAdd,
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    if token_data.role != UserRole.therapist:
        raise HTTPException(403)
    
    target_group = await session.get(ChatGroups, group_id)
    if not target_group:
        raise HTTPException(404)

    if target_group.current_size >= target_group.max_size:
        raise HTTPException(400, f"Group is full. Max size is {target_group.max_size}")
    
    new_member = (await session.execute(
        select(User).where(User.username == payload.username)
    )).scalar_one_or_none()

    if not new_member:
        raise HTTPException(404, "User not found")

    exists = (await session.execute(
        select(ChatGroupUsers).where(
            ChatGroupUsers.group_id == group_id,
            ChatGroupUsers.user_id == new_member.id
        )
    )).scalar_one_or_none()

    if exists:
        raise HTTPException(400, "Already in group")

    m = ChatGroupUsers(group_id=group_id, user_id=new_member.id, is_active=True)
    session.add(m)
    
    
    target_group.current_size += 1
    session.add(target_group)
    await session.commit()

    return {"ok": True}

# list user' groups
@router.get("/chat-groups", response_model=ChatGroupListResponse)
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
    return {"groups": groups}

# change group name
@router.post("/chat-groups/{group_id}", response_model=ChatGroupResponse)
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


@router.get("/messages", response_model=GroupMessageListResponse)
async def get_group_messages(
    group_id: int,
    limit: int = 50,
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    stmt = select(ChatGroupUsers).where(
        ChatGroupUsers.group_id == group_id,
        ChatGroupUsers.user_id == token_data.user_id,
        ChatGroupUsers.is_active == True
    )
    if not (await session.execute(stmt)).scalar_one_or_none():
        raise HTTPException(403)
    
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

@router.post("/messages")
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

    # check proper language
    result: Dict[str, str] = check_both(payload.content)
    
    print(f"content: {payload.content}")
    print(result)
    if result.get("self_harm") == "FAIL":
        return {"ok": False, "detail": "self_harm"}
    if result.get("hate") == "FAIL":
        return {"ok": False, "detail": "hate"}
    
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

    asyncio.create_task(maybe_answer_with_llm(token_data.user_id, payload.content, payload.group_id))

    return {"ok": True, "id": m.id}
    # return {"ok": True}


@router.websocket("/ws")
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