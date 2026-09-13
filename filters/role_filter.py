from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from utils.db_api.db import get_tutor, is_admin


class IsAdmin(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user_id = event.from_user.id
        return await is_admin(user_id)


class IsTutor(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user_id = event.from_user.id
        if await is_admin(user_id):
            return True
        tutor = await get_tutor(user_id)
        return tutor is not None
