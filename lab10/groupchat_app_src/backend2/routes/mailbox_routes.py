from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from db import MailboxMessage, User, get_db, UserRole
from auth import get_current_user_token
from schemas import (
    TokenData, MailboxListResponse,
    MailMarkReadPayload, MailApprovePayload
)
from datetime import datetime

router = APIRouter(prefix="/api/mailbox", tags=["Mailbox"])

@router.get("", response_model=MailboxListResponse)
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

    return {"messages": msgs}

@router.post("/read")
async def mark_mail_read(
    payload: MailMarkReadPayload, 
    token_data: TokenData = Depends(get_current_user_token), 
    session: AsyncSession = Depends(get_db)
):
    msg = await session.get(MailboxMessage, payload.mail_id)

    if not msg or msg.to_user != token_data.user_id:
        raise HTTPException(404)
    msg.is_read = True
    session.add(msg)
    await session.commit()
    return {"ok": True}

@router.post("/approve")
async def approve_user(
    payload: MailApprovePayload,
    token_data: TokenData = Depends(get_current_user_token), 
    session: AsyncSession = Depends(get_db)
):
    if token_data.role != UserRole.therapist:
        raise HTTPException(403)
    
    user = await session.get(User, payload.user_id)
    
    if not user:
        raise HTTPException(404)
    
    notice = MailboxMessage(
        from_user=token_data.user_id, 
        to_user=user.id, 
        content={"type": "approval", "message": "Your questionnaire has been approved!"}
    )
    session.add(notice)
    await session.commit()
    return {"ok": True}