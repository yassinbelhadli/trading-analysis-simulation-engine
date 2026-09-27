from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: str) -> Optional[User]:
        return await self.session.get(User, user_id)

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create_by_telegram(
        self,
        telegram_id: int,
        telegram_username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        language: str = "EN",
    ) -> User:
        user = await self.get_by_telegram_id(telegram_id)
        if user:
            user.last_login = datetime.now(timezone.utc)
            if telegram_username is not None:
                user.telegram_username = telegram_username
            if first_name is not None:
                user.first_name = first_name
            if last_name is not None:
                user.last_name = last_name
            return user

        user = User(
            telegram_id=telegram_id,
            telegram_username=telegram_username,
            first_name=first_name,
            last_name=last_name,
            language=language,
            last_login=datetime.now(timezone.utc),
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def update_language(self, user_id: str, language: str) -> Optional[User]:
        user = await self.get_by_id(user_id)
        if user:
            user.language = language
        return user

    async def update_timezone(self, user_id: str, timezone: str) -> Optional[User]:
        user = await self.get_by_id(user_id)
        if user:
            user.timezone = timezone
        return user

    async def set_status(self, user_id: str, status: str) -> Optional[User]:
        user = await self.get_by_id(user_id)
        if user:
            user.status = status
        return user
