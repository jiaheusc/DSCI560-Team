from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db import UserQuestionnaire, get_db, UserRole
from auth import get_current_user_token
from schemas import TokenData, QuestionnairePayload

router = APIRouter(prefix="/api/user", tags=["Questionnaire"])


@router.get("/questionnaire")
async def get_questionnaire(
    token_data: TokenData = Depends(get_current_user_token), 
    session: AsyncSession = Depends(get_db)
):
    if token_data.role != UserRole.user:
        raise HTTPException(403)
    res = await session.execute(select(UserQuestionnaire).where(UserQuestionnaire.user_id == token_data.user_id))
    existing = res.scalar_one_or_none()
    return {"ok": bool(existing)}


@router.post("/questionnaire")
async def save_questionnaire(
    payload: QuestionnairePayload, 
    token_data: TokenData = Depends(get_current_user_token), 
    session: AsyncSession = Depends(get_db)
):
    res = await session.execute(select(UserQuestionnaire).where(UserQuestionnaire.user_id == token_data.user_id))
    questionnaire = res.scalar_one_or_none()
    
    if questionnaire:
        questionnaire.answers = payload.content
        session.add(questionnaire)
    else:
        questionnaire = UserQuestionnaire(user_id=token_data.user_id, answers=payload.content)
        session.add(questionnaire)
    await session.commit()
    return {"ok": True}