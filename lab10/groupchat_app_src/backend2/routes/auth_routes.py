from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db import User, UserRole, get_db
from schemas import AuthPayload, ChangePasswordPayload, TokenData
from auth import get_password_hash, verify_password, create_access_token, get_current_user_token
import os

router = APIRouter(prefix="/api", tags=["Auth"])
AVATAR_DIR = "static/avatars"


@router.post("/signup")
async def signup(
    payload: AuthPayload,
    session: AsyncSession = Depends(get_db)
):
    exists = await session.execute(select(User).where(User.username == payload.username))
    if exists.scalar_one_or_none():
        raise HTTPException(400, "Username already taken")

    u = User(username=payload.username, password_hash=get_password_hash(payload.password), user_role=UserRole.user)
    session.add(u)
    await session.commit()
    await session.refresh(u)

    token = create_access_token({"username": u.username, "role": u.user_role.value, "user_id": u.id})
    return {"ok": True, "token": token}

@router.post("/therapist/signup")
async def signup_therapist(
    payload: AuthPayload,
    token_data: TokenData =Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    if token_data.role != UserRole.operator:
        raise HTTPException(403, "Only operator can create therapist accounts")
    
    exists = await session.execute(select(User).where(User.username == payload.username))
    if exists.scalar_one_or_none():
        raise HTTPException(400, "Username already taken")

    u = User(username=payload.username, password_hash=get_password_hash(payload.password), user_role=UserRole.therapist)
    session.add(u)
    await session.commit()
    await session.refresh(u)

    token = create_access_token({"username": u.username, "role": u.user_role.value, "user_id": u.id})
    return {"ok": True, "token": token}

@router.post("/operator/signup")
async def signup_operator(
    payload: AuthPayload,
    token_data: TokenData =Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    
    exists = await session.execute(select(User).where(User.username == payload.username))
    if exists.scalar_one_or_none():
        raise HTTPException(400, "Username already taken")

    u = User(username=payload.username, password_hash=get_password_hash(payload.password), user_role=UserRole.operator)
    session.add(u)
    await session.commit()
    await session.refresh(u)

    token = create_access_token({"username": u.username, "role": u.user_role.value, "user_id": u.id})
    return {"ok": True, "token": token}

@router.post("/login")
async def login(
    payload: AuthPayload,
    session: AsyncSession = Depends(get_db)
):
    print(">>> LOGIN ENTERED")  
    res = await session.execute(select(User).where(User.username == payload.username))
    u = res.scalar_one_or_none()
    if not u or not verify_password(payload.password, u.password_hash):
        raise HTTPException(401, "Invalid credentials")

    token = create_access_token({"username": u.username, "role": u.user_role.value, "user_id": u.id})
    return {"ok": True, "token": token}

@router.get("/avatars")
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

@router.post("/auth/change-password")
async def change_password(
    payload: ChangePasswordPayload,
    token_data: TokenData =Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db)
):
    user = (await session.execute(select(User).where(User.username == token_data.username))).scalar_one_or_none()
    if not verify_password(payload.old_password, user.password_hash):
        raise HTTPException(400, "Incorrect current password")
    
    user.password_hash = get_password_hash(payload.new_password)
    session.add(user)
    await session.commit()
    return {"ok": True}