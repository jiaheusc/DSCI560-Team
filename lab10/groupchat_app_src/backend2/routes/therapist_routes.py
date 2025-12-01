from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import date, datetime, time
from utils.security import encrypt, decrypt
from db import (
    User, TherapistProfile, UserRole, UserTherapist, UserProfile, 
    UserTherapistChat, DailyUserSummary, ChatGroups, ChatGroupUsers, get_db
)
from auth import get_current_user_token
from schemas import (
    TokenData, TherapistPublicDetail, TherapistPrivateDetail, TherapistListResponse,
    TherapistProfileCreate, TherapistProfileUpdate, DailySummaryListResponse, 
    TherapistProfileWrappedResponse, PatientListResponse, UserPrivateDetail, 
    ChatGroupListResponse
)

router = APIRouter(prefix="/api/therapist", tags=["Therapist"])

@router.get("/profile/status")
async def has_therapist_profile(
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    if token_data.role != UserRole.therapist:
        raise HTTPException(403)

    profile = (await session.execute(
        select(TherapistProfile).where(TherapistProfile.user_id == token_data.user_id)
    )).scalar_one_or_none()
    if not profile or not profile.prefer_name:
        return {"ok": False}
    
    return {"ok": True}
    
@router.get("/therapists", response_model=TherapistListResponse)
async def list_therapists(
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    stmt = (
        select(User, TherapistProfile)
        .outerjoin(TherapistProfile, User.id == TherapistProfile.user_id)
        .where(User.user_role == UserRole.therapist)
    )

    rows = (await session.execute(stmt)).all()

    out = []
    for user, profile in rows:
        out.append({
            "user_id": user.id,
            "prefer_name": profile.prefer_name if profile else None,
            "bio": profile.bio if profile else None,
            "expertise": profile.expertise if profile else None,
            "years_experience": profile.years_experience if profile else None,
            "avatar_url": profile.avatar_url if profile else None,
        })

    return {"therapists": out}

# create therapist profile
@router.post("/profile", response_model=TherapistProfileWrappedResponse)
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

    profile = TherapistProfile(
        user_id=token_data.user_id,
        avatar_url=payload.avatar_url,
        prefer_name=payload.prefer_name,
        bio=payload.bio,
        expertise=payload.expertise,
        years_experience=payload.years_experience,
        license_number=payload.license_number,
    )
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    user = await session.get(User, token_data.user_id)

    profile = {
        "user_id": user.id,
        "username": user.username,
        "avatar_url": profile.avatar_url,
        "prefer_name": profile.prefer_name,
        "bio": profile.bio,
        "expertise": profile.expertise,
        "years_experience": profile.years_experience,
        "license_number": profile.license_number,
    }
    return {"ok": True, "profile": profile}


@router.post("/profile/update", response_model=TherapistProfileWrappedResponse)
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

    user = await session.get(User, token_data.user_id)

    profile = {
        "user_id": user.id,
        "username": user.username,
        "avatar_url": profile.avatar_url,
        "prefer_name": profile.prefer_name,
        "bio": profile.bio,
        "expertise": profile.expertise,
        "years_experience": profile.years_experience,
        "license_number": profile.license_number,
    }

    return {"ok": True, "profile": profile}

@router.get("/profile/me", response_model=TherapistPrivateDetail)
async def get_my_therapist_profile(
    token_data:TokenData = Depends(get_current_user_token), 
    session: AsyncSession = Depends(get_db)
):
    if token_data.role != UserRole.therapist:
        raise HTTPException(403)

    stmt = select(TherapistProfile).where(TherapistProfile.user_id == token_data.user_id)
    profile = (await session.execute(stmt)).scalar_one_or_none()

    if not profile:
        profile = TherapistProfile(
            user_id=token_data.user_id,
            avatar_url="",
            prefer_name="",
            bio="",
            expertise="",
            years_experience=0,
            license_number=""
        )
        session.add(profile)
        await session.commit()
        await session.refresh(profile)

    user = await session.get(User, token_data.user_id)

    return {
        "user_id": user.id,
        "username": user.username,
        "avatar_url": profile.avatar_url,
        "prefer_name": profile.prefer_name,
        "bio": profile.bio,
        "expertise": profile.expertise,
        "years_experience": profile.years_experience,
        "license_number": profile.license_number,
    }

@router.get("/profile/{therapist_id}", response_model=TherapistPublicDetail)
async def get_public_therapist_profile(
    therapist_id: int, 
    session: AsyncSession = Depends(get_db)
):
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
        "user_id": user.id,
        "avatar_url": profile.avatar_url,
        "prefer_name": profile.prefer_name if profile else "",
        "bio": profile.bio if profile else "",
        "expertise": profile.expertise if profile else "",
        "years_experience": profile.years_experience if profile else 0
    }

###
#   therapist's users apis
###
@router.get("/my-users", response_model=PatientListResponse)
async def therapist_list_users(
    token_data:TokenData = Depends(get_current_user_token), 
    session: AsyncSession = Depends(get_db)
):
    if token_data.role != UserRole.therapist:
        raise HTTPException(403)
    
    stmt = select(UserTherapist).where(UserTherapist.therapist_id == token_data.user_id)
    relations = (await session.execute(stmt)).scalars().all()
    out = []
    
    for r in relations:
        user = await session.get(User, r.user_id)
        profile = (await session.execute(select(UserProfile).where(UserProfile.user_id == user.id))).scalar_one_or_none()
        unread_stmt = select(func.count(UserTherapistChat.id)).where(
            (UserTherapistChat.user_id == user.id) &
            (UserTherapistChat.therapist_id == token_data.user_id) &
            (UserTherapistChat.sender_id == user.id) &
            (UserTherapistChat.is_read == False)
        )
        unread = (await session.execute(unread_stmt)).scalar()
        out.append({
            "id": user.id, 
            "username": user.username,
            "prefer_name": profile.prefer_name if profile else None,
            "avatar_url": profile.avatar_url if profile else None,
            "unread": unread
        })
    return {"users": out}

@router.get("/user/{user_id}", response_model=UserPrivateDetail)
async def get_user_profile_for_therapist(
    user_id: int,
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):  
    if token_data.role != UserRole.therapist:
        raise HTTPException(403)
    
    user_therapist = (await session.execute(
        select(UserTherapist).
        where((UserTherapist.therapist_id == token_data.user_id) & (UserTherapist.user_id == user_id))
    )).scalar_one_or_none()

    if not user_therapist:
        raise HTTPException(404)

    profile = (await session.execute(
        select(UserProfile).
        where(UserProfile.user_id == user_id)
    )).scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail="User profile not found")
    return profile

@router.get("/users/{user_id}/groups", response_model=ChatGroupListResponse)
async def get_user_groups(
    user_id: int,
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    if token_data.role != UserRole.therapist:
        raise HTTPException(403)
    
    user_therapist = (await session.execute(
        select(UserTherapist).
        where(UserTherapist.therapist_id == token_data.user_id, UserTherapist.user_id == user_id)
    )).scalar_one_or_none()

    if not user_therapist:
        raise HTTPException(404)
    
    stmt = (
        select(ChatGroups) 
        .join(ChatGroupUsers, ChatGroups.id == ChatGroupUsers.group_id)
        .where(ChatGroupUsers.user_id == user_id)
    )
    groups = (await session.execute(stmt)).scalars().all()
    return ChatGroupListResponse(groups=groups)


@router.get("/users/{user_id}/groups/{group_id}/summaries", response_model=DailySummaryListResponse)
async def get_user_summaries(
    user_id: int,
    group_id: int,
    start_date: date = Query(...),
    end_date: date = Query(...),
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    if token_data.role != UserRole.therapist:
        raise HTTPException(403)
    
    user_therapist = (await session.execute(
        select(UserTherapist).
        where(UserTherapist.therapist_id == token_data.user_id, UserTherapist.user_id == user_id)
    )).scalar_one_or_none()

    if not user_therapist:
        raise HTTPException(404)

    start_datetime = datetime.combine(start_date, time.min)
    end_datetime = datetime.combine(end_date, time.max)

    stmt = (
        select(DailyUserSummary)
        .where(
            and_(
                DailyUserSummary.group_id == group_id,
                DailyUserSummary.user_id == user_id,
                DailyUserSummary.summary_date >= start_datetime,
                DailyUserSummary.summary_date <= end_datetime
            )
        )
        .order_by(DailyUserSummary.summary_date.asc())
    )

    summaries = (await session.execute(stmt)).scalars().all()

    if not summaries:
        return DailySummaryListResponse(summaries=[])
    
    results = []
    for item in summaries:
        text = None
        if item.summary_text:
            try:
                text = decrypt(item.summary_text)
            except Exception:
                text = "[Decryption Error]"

        mood = None
        if item.mood:
            try:
                mood = decrypt(item.mood)
            except Exception:
                mood = None

        results.append({
            "summary_date": item.summary_date,
            "summary_text": text,
            "mood": mood
        })
    
    return DailySummaryListResponse(summaries=results)