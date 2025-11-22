from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db import (
    get_db, UserProfile, UserRole, MailboxMessage, 
    User, UserQuestionnaire, UserTherapist, TherapistProfile
)
from auth import get_current_user_token
from schemas import (
    TokenData, UserProfileCreate, UserProfileUpdate, 
    AssignTherapistPayload, UserPublicDetail, 
    UserProfileWrappedResponse, UserTherapistRelationship
)
from model.grouping import GroupRecommender

router = APIRouter(prefix="/api/user", tags=["User"])

# create user profile
@router.post("/profile", response_model=UserProfileWrappedResponse)
async def create_profile(payload: UserProfileCreate, token_data=Depends(get_current_user_token), session: AsyncSession = Depends(get_db)):
    if token_data.role != UserRole.user:
        raise HTTPException(403)
    exists = (await session.execute(select(UserProfile).where(UserProfile.user_id == token_data.user_id))).scalar_one_or_none()
    if exists:
        raise HTTPException(400, "Profile already exists")
    
    profile = UserProfile(user_id=token_data.user_id, **payload.dict())
    session.add(profile)
    await session.commit()
    await session.refresh(profile)

    user = await session.get(User, token_data.user_id)

    return {
        "ok": True,
        "profile": {
            "user_id": user.id,
            "username": user.username,
            "avatar_url": profile.avatar_url,
            "prefer_name": profile.prefer_name,
            "bio": profile.bio,
        }
    }

# update user profile
@router.post("/profile/update", response_model=UserProfileWrappedResponse)
async def update_profile(payload: UserProfileUpdate, token_data=Depends(get_current_user_token), session: AsyncSession = Depends(get_db)):
    if token_data.role != UserRole.user:
        raise HTTPException(403)
    profile = (await session.execute(select(UserProfile).where(UserProfile.user_id == token_data.user_id))).scalar_one_or_none()
    if not profile:
        raise HTTPException(404, "Profile not found")
    for k, v in payload.dict(exclude_unset=True).items():
        setattr(profile, k, v)
    session.add(profile)
    await session.commit()
    await session.refresh(profile)

    user = await session.get(User, token_data.user_id)

    return {
        "ok": True,
        "profile": {
            "user_id": user.id,
            "username": user.username,
            "avatar_url": profile.avatar_url,
            "prefer_name": profile.prefer_name,
            "bio": profile.bio,
        }
    }

# get user profile (user used)
@router.get("/profile/me", response_model=UserPublicDetail)
async def get_profile_me(
    token_data=Depends(get_current_user_token), 
    session: AsyncSession = Depends(get_db)
):
    if token_data.role != UserRole.user:
        raise HTTPException(403)

    stmt = select(UserProfile).where(UserProfile.user_id == token_data.user_id)
    profile = (await session.execute(stmt)).scalar_one_or_none()

    if not profile:
        profile = UserProfile(
            user_id=token_data.user_id,
            avatar_url=None,
            prefer_name=None,
            bio=None
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
    }

@router.post("/me/assign-therapist")
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
    await session.refresh(rel)


    # Get user info
    user = await session.get(User, token_data.user_id)
    q_res = await session.execute(select(UserQuestionnaire).where(UserQuestionnaire.user_id == token_data.user_id))
    questionnaire = q_res.scalar_one_or_none()

    if not questionnaire:
        notice = MailboxMessage(
            from_user=user.id,
            to_user=rel.therapist_id,
            content={
                "type": "new_patient_assigned",
                "user": user.username,
                "user_id": user.id,
                "message": "This user has selected you as their therapist, but has not completed their questionnaire yet."
            }
        )
        session.add(notice)
        await session.commit()
        return {"ok": True, "detail": "Therapist assigned, questionnaire pending."}
    
    rec = GroupRecommender(db_url="mysql+pymysql://chatuser:chatpass@localhost:3307/groupchat")
    recommendation = rec.recommend(token_data.user_id)
    questionnaire.recommendation = recommendation

    # send to target therapist
    notice = MailboxMessage(
        from_user=user.id,
        to_user=rel.therapist_id,
        content={
            "type": "questionnaire",
            "user": user.username,
            "recommendation": recommendation,
            "answers": questionnaire.answers
        }
    )
    session.add(notice)

    await session.commit()
    return {"ok": True}

@router.get("/me/therapist", response_model=UserTherapistRelationship)
async def get_my_therapist(
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    stmt = select(UserTherapist).where(UserTherapist.user_id == token_data.user_id)
    rel = (await session.execute(stmt)).scalar_one_or_none()

    if not rel:
        return {"has_therapist": False, "therapist": None}

    therapist = await session.get(User, rel.therapist_id)
    profile = (await session.execute(
        select(TherapistProfile).where(TherapistProfile.user_id == rel.therapist_id)
    )).scalar_one_or_none()

    therapist_data = {
        "user_id": therapist.id,
        "avatar_url": profile.avatar_url if profile else None,
        "prefer_name": profile.prefer_name if profile else None,
        "bio": profile.bio if profile else None,
        "expertise": profile.expertise if profile else None,
        "years_experience": profile.years_experience if profile else None
    }
    
    return {
        "has_therapist": True,
        "therapist": therapist_data
    }

@router.get("/profile/status")
async def user_profile_status(
    token_data: TokenData = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    if token_data.role != UserRole.user:
        raise HTTPException(403)

    stmt = select(UserProfile).where(UserProfile.user_id == token_data.user_id)
    profile = (await session.execute(stmt)).scalar_one_or_none()

    if not profile or not profile.prefer_name:
        return {"ok": False}

    return {"ok": True}
