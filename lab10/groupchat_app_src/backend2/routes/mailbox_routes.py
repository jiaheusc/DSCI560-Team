from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from db import MailboxMessage, User, get_db, UserRole, UserTherapist
from auth import get_current_user_token
from schemas import (
    TokenData, MailboxListResponse, MailSendPayload, 
    MailMarkReadPayload, MailApprovePayload, MailSendSuccessResponse
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

@router.post("/send", response_model=MailSendSuccessResponse)
async def send_notification(
    payload: MailSendPayload,
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    sender_id = token_data.user_id
    target_id = payload.target_id

    stmt = select(UserTherapist).where(
        (UserTherapist.user_id == token_data.user_id) |
        (UserTherapist.therapist_id == token_data.user_id)
    )
    rel = (await session.execute(stmt)).scalar_one_or_none()
    if not rel:
        raise HTTPException(403)

    if sender_id == rel.user_id:
        if target_id != rel.therapist_id:
            raise HTTPException(403)
    elif sender_id == rel.therapist_id:
        if target_id != rel.user_id:
            raise HTTPException(403)
    else:
        raise HTTPException(403)
    
    mail = MailboxMessage(
        from_user = sender_id,
        to_user = target_id,
        content = {
            "type": "direct_message", 
            "message": payload.message
        }
    )
    session.add(mail)
    await session.commit()
    await session.refresh(mail)

    return {"ok": True, "mail_id": mail.id}

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
    # 应该加上 approve=true
    notice = MailboxMessage(
        from_user=token_data.user_id, 
        to_user=user.id, 
        content={"type": "approval", "message": "Your questionnaire has been approved!"}
    )
    session.add(notice)
    await session.commit()
    return {"ok": True}

@router.get("/partner")
async def get_mail_partner(
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    """
    Automatically find the 'partner' in the UserTherapist relationship.
    - If current user is USER → partner is their THERAPIST
    - If current user is THERAPIST → partner is a USER? (ambiguous, skip auto)
    """
    # USER ONLY: auto get therapist
    if token_data.role == UserRole.user:
        stmt = select(UserTherapist).where(UserTherapist.user_id == token_data.user_id)
        rel = (await session.execute(stmt)).scalar_one_or_none()

        if not rel:
            return {"ok": False, "partner_id": None, "name": None}

        therapist = await session.get(User, rel.therapist_id)
        name = therapist.username

        # if therapist has profile with prefer_name
        from db import TherapistProfile  # import inside
        prof = (
            await session.execute(
                select(TherapistProfile).where(TherapistProfile.user_id == therapist.id)
            )
        ).scalar_one_or_none()

        if prof and prof.prefer_name:
            name = prof.prefer_name

        return {"ok": True, "partner_id": therapist.id, "name": name}

    # THERAPIST: cannot auto determine (multiple users)
    return {"ok": False, "partner_id": None, "name": None}
