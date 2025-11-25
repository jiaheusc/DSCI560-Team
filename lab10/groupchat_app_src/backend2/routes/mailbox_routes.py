from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from db import MailboxMessage, User, get_db, UserRole, UserTherapist,UserProfile,TherapistProfile
from auth import get_current_user_token
from schemas import (
    TokenData, MailboxListResponse, MailSendPayload, 
    MailMarkReadPayload, MailApprovePayload, 
    MailSendSuccessResponse, 
)
from datetime import datetime
from sqlalchemy.orm import aliased
import json

router = APIRouter(prefix="/api/mailbox", tags=["Mailbox"])

async def _fetch_and_format_mails(session: AsyncSession, is_sent_box: bool, user_id: int):

    Sender = aliased(User)
    SenderUP = aliased(UserProfile)
    SenderTP = aliased(TherapistProfile)
    Receiver = aliased(User)
    ReceiverUP = aliased(UserProfile)
    ReceiverTP = aliased(TherapistProfile)
    
    where_condition = MailboxMessage.from_user == user_id if is_sent_box else MailboxMessage.to_user == user_id

    stmt = (
        select(
            MailboxMessage,
            Sender, SenderUP, SenderTP,
            Receiver, ReceiverUP, ReceiverTP,
        )
        .select_from(MailboxMessage)
        .outerjoin(Sender, MailboxMessage.from_user == Sender.id)
        .outerjoin(SenderUP, SenderUP.user_id == Sender.id)
        .outerjoin(SenderTP, SenderTP.user_id == Sender.id)
        .join(Receiver, MailboxMessage.to_user == Receiver.id)
        .outerjoin(ReceiverUP, ReceiverUP.user_id == Receiver.id)
        .outerjoin(ReceiverTP, ReceiverTP.user_id == Receiver.id)

        .where(where_condition)
        .order_by(desc(MailboxMessage.created_at))
    )

    rows = (await session.execute(stmt)).all()
    out = []

    for m, sender, sup, stp, receiver, rup, rtp in rows:
        sender_name = (sup and sup.prefer_name) or (stp and stp.prefer_name) or sender.username if sender else "System"
        receiver_name = (rup and rup.prefer_name) or (rtp and rtp.prefer_name) or receiver.username

        content = m.content
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except:
                content = {"type": "unknown", "text": content}
        
        out.append({
            "id": m.id,
            "from_user": m.from_user,
            "from_name": sender_name,
            "to_user": m.to_user,
            "to_name": receiver_name,
            "content": content,
            "is_read": m.is_read,
            "created_at": m.created_at,
        })

    return out

@router.get("", response_model=MailboxListResponse)
async def get_mailbox(
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    out = await _fetch_and_format_mails(session, False, token_data.user_id)
    return {"messages": out}


@router.get("/sent", response_model=MailboxListResponse)
async def get_sent_mailbox(
    token_data: TokenData = Depends(get_current_user_token), 
    session: AsyncSession = Depends(get_db)
):
    out = await _fetch_and_format_mails(session, True, token_data.user_id)
    return {"messages": out}

@router.post("/send", response_model=MailSendSuccessResponse)
async def send_notification(
    payload: MailSendPayload,
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    sender_id = token_data.user_id
    target_id = payload.target_id

    target = await session.get(User, target_id)
    if not target:
        raise HTTPException(404, "Target not found")

    if token_data.role == UserRole.user:
        # user → therapist
        stmt = select(UserTherapist).where(
            (UserTherapist.user_id == sender_id) &
            (UserTherapist.therapist_id == target_id)
        )
    elif token_data.role == UserRole.therapist:
        # therapist → user
        stmt = select(UserTherapist).where(
            (UserTherapist.therapist_id == sender_id) &
            (UserTherapist.user_id == target_id)
        )
    else:
        raise HTTPException(403, "Invalid role")

    rel = (await session.execute(stmt)).scalar_one_or_none()
    if not rel:
        raise HTTPException(403, "No permission to message this user")

    mail = MailboxMessage(
        from_user=sender_id,
        to_user=target_id,
        content={
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
    # 应该加上 approve=true吗?
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
