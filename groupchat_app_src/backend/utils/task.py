import asyncio
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from sqlalchemy import select
from db import SessionLocal, ChatGroups, Message, DailyUserSummary
from utils.security import encrypt, decrypt
from model.chatbot import MentalHealthChatbot

_chatbot: MentalHealthChatbot | None = None

def get_chatbot() -> MentalHealthChatbot:
    global _chatbot
    if _chatbot is None:
        _chatbot = MentalHealthChatbot()
    return _chatbot


async def generate_daily_summaries():
    bot = get_chatbot()
    async with SessionLocal() as session:
        stmt = select(ChatGroups).where(ChatGroups.is_active == True)
        groups = (await session.execute(stmt)).scalars().all()

        now = datetime.now(timezone.utc)
        yesterday_date = (now - timedelta(days=1)).date()
        day_start = datetime(
            year=yesterday_date.year,
            month=yesterday_date.month,
            day=yesterday_date.day,
            tzinfo=timezone.utc,
        )
        day_end = day_start + timedelta(days=1)

        for group in groups:
            
            stmt_msgs = (
                select(Message)
                .where(
                    Message.group_id == group.id,
                    Message.created_at >= day_start,
                    Message.created_at < day_end,
                    Message.is_bot == False,
                )
            )
            msgs = (await session.execute(stmt_msgs)).scalars().all()

            if not msgs:
                continue

            user_conversations = defaultdict(list)
            for m in msgs:
                if m.user_id:
                    try:
                        text = decrypt(m.content)
                        user_conversations[str(m.user_id)].append(text)
                    except Exception:
                        pass
            
            if not user_conversations:
                continue

            try:
                summary_data = await bot.summarize_group(dict(user_conversations))

                for uid_key, info in summary_data.items():
                    try:
                        u_id = int(uid_key)
                        print(info.get("summary", ""))
                        print(info.get("mood", "neutral"))
                        summary_text = encrypt(info.get("summary", ""))
                        mood = encrypt(info.get("mood", "neutral"))
                        exists_stmt = select(DailyUserSummary).where(
                            DailyUserSummary.group_id == group.id,
                            DailyUserSummary.user_id == u_id,
                            DailyUserSummary.summary_date == yesterday_date,
                        )
                        existed = (await session.execute(exists_stmt)).scalar_one_or_none()
                        if existed:
                            existed.summary_text = summary_text
                            existed.mood = mood
                            session.add(existed)
                        else:
                            record = DailyUserSummary(
                                group_id=group.id,
                                user_id=u_id,
                                summary_date=yesterday_date,
                                summary_text=summary_text,
                                mood=mood,
                            )
                            session.add(record)

                    except ValueError:
                        continue
                await session.commit()
                
            except Exception as e:
                print(f"  - group {group.id} failed: {e}")
    print(f"[{datetime.now()}] daily summary finished.")