from typing import Dict
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from db import (
    Message, ChatGroups, ChatGroupUsers, User, UserRole, 
    UserProfile, MessageFlagLog, UserTherapist, MailboxMessage, 
    get_db, async_session_maker
)
from auth import get_current_user_token, verify_websocket_token
from websocket_manager import ConnectionManager
from llm import chat_completion
import time
import asyncio
from model.grouping import CentroidOps
from utils.security import encrypt, decrypt
from utils.task import get_chatbot
from model.red_flag_detector import LLMRedFlagJudge
from schemas import (
    TokenData, MessagePayload, GroupMessageListResponse, MessageResponse,
    ChatGroupCreate, ChatGroupListResponse, GroupMembersListResponse, SupportChatRequest, 
    ChatGroupUpdate, ChatGroupResponse, MemberAdd, ChatRequest, UserPublicDetail
)

# help functions
ALERT_TEMPLATE = """
    🔴 **CRITICAL SAFETY ALERT**
    **Source**: User {user_id} (Group {group_id})
    **Category**: {category} (Level {level})
    **Rationale**: {rationale}

    **Original Hidden Message**:
    "{content}"
"""

async def notify_therapist(user_id, group_id, alert_data, original_content):
    async with async_session_maker() as session:
        therapist_id = await session.execute(
                select(UserTherapist.therapist_id)
                .where(UserTherapist.user_id == user_id)
            ).scalar_one_or_none()
        
        alert_msg = ALERT_TEMPLATE.format(
            user_id=user_id,
            group_id=group_id,
            category=alert_data.get('category'),
            level=alert_data.get('level'),
            rationale=alert_data.get('rationale'),
            content=original_content
        )
        
        new_mail = MailboxMessage(
            from_user=None,
            to_user=therapist_id,
            is_read=False,
            content={
                "subject": "🔴 CRITICAL SAFETY ALERT",
                "body": alert_msg,
                "type": "alert",
                "level": alert_data.get('level')
            }
        )
        session.add(new_mail)
        await session.commit()

def update_group_centroids_safely(group_id: int, user_ids: list[int]):
    try:
        ops = CentroidOps(db_url="mysql+pymysql://chatuser:chatpass@localhost:3306/groupchat")
        
        for uid in user_ids:
            try:
                ops.update_centroid_incremental(group_id=group_id, user_id=uid)
            except RuntimeError as e:
                print(f"[Warning] User {uid} has no embedding, skipping centroid update. Error: {e}")
            except Exception as e:
                print(f"[Error] Failed to update centroid for user {uid}: {e}")
                
    except Exception as e:
        print(f"[Critical] CentroidOps initialization failed: {e}")

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
    chatbot = get_chatbot()
    async with SessionLocal() as session:
        req = ChatRequest(
            user_id=str(sender_id),
            message=content,
            history=[] # 历史记录为空
        )
        start_time = time.time()
        try:
            res = chatbot.handle_message(req)
            reply = res.reply
            
            duration = time.time() - start_time
            print(f"--- LLM Response Duration: {duration:.2f} seconds ---")
        except Exception as e:
            reply = f"(LLM error) Chatbot failed to generate reply. Error: {str(e)}"
        print(reply)
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
    background_tasks: BackgroundTasks,
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    if token_data.role != UserRole.therapist:
        raise HTTPException(403, "Only therapist can create group")

    if not payload.usernames:
        raise HTTPException(400, "Group members list cannot be empty.")

    target_usernames = list(set(payload.usernames))
    stmt = select(User).where(User.username.in_(target_usernames))
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

    user_ids = [u.id for u in users]
    background_tasks.add_task(update_group_centroids_safely, group.id, user_ids)

    return group.id


@router.post("/chat-groups/ai-1on1")
async def create_ai_group(
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    user = await session.get(User, token_data.user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    
    group = ChatGroups(
        group_name=f"{user.username} & WeMind AI",
        is_ai_1on1=True,
        max_size=1,
        current_size=1, 
        is_active=True
    )
    session.add(group)
    await session.flush()

    member = ChatGroupUsers(group_id=group.id, user_id=user.id, is_active=True)
    session.add(member)
    await session.commit()
    await session.refresh(group)

    return group.id

# add a member into a group
@router.post("/chat-groups/{group_id}/member")
async def add_member(
    group_id: int,
    payload: MemberAdd,
    background_tasks: BackgroundTasks,
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
    background_tasks.add_task(update_group_centroids_safely, group_id, [new_member.id])
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

# list group's user info
@router.get("/chat-groups/{group_id}/members", response_model=GroupMembersListResponse)
async def list_group_members(
    group_id: int,
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    group = await session.get(ChatGroups, group_id)
    if not group:
        raise HTTPException(404, "Group not found")

    stmt = (
        select(User, UserProfile)
        .join(ChatGroupUsers, User.id == ChatGroupUsers.user_id)
        .outerjoin(UserProfile, User.id == UserProfile.user_id)
        .where(ChatGroupUsers.group_id == group_id)
    )

    rows = (await session.execute(stmt)).all()

    members: list[UserPublicDetail] = []

    for user, profile in rows:
        avatar_url  = profile.avatar_url if profile and profile.avatar_url else None
        prefer_name = profile.prefer_name if profile and profile.prefer_name else ""
        bio         = profile.bio if profile and profile.bio else ""

        members.append(
            UserPublicDetail(
                user_id=user.id,
                username=user.username,
                avatar_url=avatar_url,
                prefer_name=prefer_name,
                bio=bio,
            )
        )

    if group.is_ai_1on1:
        members.append(
            UserPublicDetail(
                user_id=0,                    
                username="WeMind AI",
                avatar_url="/static/avatars/ai.png",
                prefer_name="WeMind AI",
                bio="AI assistant"
            )
        )

    return GroupMembersListResponse(ok=True, members=members)


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
            "is_visible": m.is_visible,
            "is_bot": m.is_bot,
            "created_at": str(m.created_at)
        })
    return {"messages": out}

@router.post("/messages", response_model=MessageResponse)
async def post_group_message(
    payload: MessagePayload,
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    group_id = payload.group_id
    # check membership
    stmt = select(ChatGroupUsers).where(
        ChatGroupUsers.group_id == group_id,
        ChatGroupUsers.user_id == token_data.user_id,
        ChatGroupUsers.is_active == True
    )
    if not (await session.execute(stmt)).scalar_one_or_none():
        raise HTTPException(403)

    # check proper language
    stmt = (
        select(Message)
        .where(Message.group_id == group_id)
        .order_by(Message.created_at.desc())
        .limit(10)
    )
    db_msgs = (await session.execute(stmt)).scalars().all()
    reversed_msgs = list(reversed(db_msgs))

    recent_context = []
    for msg in reversed_msgs:
        try:
            content = decrypt(msg.content)
            recent_context.append(content)
        except Exception:
            pass

    chatbot = get_chatbot()
    judge = LLMRedFlagJudge(llm=chatbot.llm)

    res = await judge.classify(
        payload.content, 
        recent=recent_context
    )
    level = res.get('level', 1)
    is_dangerous = level >= 2 or res.get('label') == 'alert'
    flag_type = res.get('category') if is_dangerous else None
    rationale = res.get('rationale')

    is_visible = not is_dangerous

    m = Message(
        user_id=token_data.user_id,
        content=encrypt(payload.content),
        is_visible=is_visible,
        is_bot=False,
        group_id=payload.group_id
    )
    session.add(m)
    await session.flush()

    flag_log = MessageFlagLog(
            message_id=m.id,
            level=res.get('level'),
            category=res.get('category'),
            rationale=res.get('rationale'),
            raw_response=res.get('raw')
        )
    session.add(flag_log)
    await session.commit()
    await session.refresh(m)

    if is_dangerous:
        
        opening_line = await chatbot.respond_to_flagged(
            tag = flag_type,
            message = payload.content,
            recent_messages=recent_context
        )

        if level >= 3:
            # sent a message to therapist
            # what should i write could be a good one
            asyncio.create_task(
                notify_therapist(
                    user_id=token_data.user_id,
                    group_id=payload.group_id,
                    alert_data=res,
                    original_content=payload.content
                )
            )
        return {
            "ok": False, 
            "id": m.id,
            "ai_opening_line": opening_line,
            "detail": flag_type,
            "rationale": rationale
        }
    else:
        await broadcast_message(session, m, payload.group_id)
        asyncio.create_task(maybe_answer_with_llm(token_data.user_id, payload.content, payload.group_id))
        return {"ok": True, "id": m.id}

@router.post("/support-chat/start", response_model=dict)
async def start_support_chat(
    payload: SupportChatRequest,
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    ai_msg = Message(
        user_id=None,
        group_id=payload.group_id,
        content=encrypt(payload.opening_message),
        is_bot=True,
        is_visible=True
    )
    session.add(ai_msg)
    await session.commit()
    return {"ok": True} 
    
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