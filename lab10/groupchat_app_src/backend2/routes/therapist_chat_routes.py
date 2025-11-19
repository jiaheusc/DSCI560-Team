from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db import get_db, UserTherapist, UserTherapistChat, User, UserRole
from auth import get_current_user_token
from utils.security import encrypt, decrypt
from schemas import (
    TokenData, ChatSendPayload, MarkReadPayload, ChatMessageListResponse
)

router = APIRouter(prefix="/api/therapist-chat", tags=["Therapist Chat"])

@router.post("/send")
async def send_user_therapist_message(
    payload: ChatSendPayload,
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    sender_id = token_data.user_id
    target_id = payload.target_id

    stmt = select(UserTherapist).where(
        (UserTherapist.user_id == sender_id) |
        (UserTherapist.therapist_id == sender_id)
    )
    rel = (await session.execute(stmt)).scalar_one_or_none()
    if not rel:
        raise HTTPException(403, "No relationship found")

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


@router.post("/mark-read")
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


@router.get("/messages", response_model=ChatMessageListResponse)
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

    out = [
        {
            "id": m.id,
            "sender_id": m.sender_id,
            "message": decrypt(m.message),
            "is_read": m.is_read,
            "created_at": m.created_at
        }
        for m in messages
    ]

    return {"messages": out}

# @router.get("/messages/{user_id}")
# async def therapist_chat_with_user(
#     user_id: int,
#     token_data: TokenData = Depends(get_current_user_token),
#     session: AsyncSession = Depends(get_db)
# ):
#     if token_data.role != UserRole.therapist:
#         raise HTTPException(403)

#     stmt = select(UserTherapist).where(
#         (UserTherapist.user_id == user_id) &
#         (UserTherapist.therapist_id == token_data.user_id)
#     )
#     rel = (await session.execute(stmt)).scalar_one_or_none()
#     if not rel:
#         raise HTTPException(403, "Not assigned")

#     stmt = (
#         select(UserTherapistChat)
#         .where(
#             (UserTherapistChat.user_id == user_id) &
#             (UserTherapistChat.therapist_id == token_data.user_id)
#         )
#         .order_by(UserTherapistChat.created_at)
#     )
#     msgs = (await session.execute(stmt)).scalars().all()

#     return {
#         "messages": [
#             {
#                 "id": m.id,
#                 "sender_id": m.sender_id,
#                 "message": decrypt(m.message),
#                 "is_read": m.is_read,
#                 "created_at": m.created_at
#             }
#             for m in msgs
#         ]
#     }