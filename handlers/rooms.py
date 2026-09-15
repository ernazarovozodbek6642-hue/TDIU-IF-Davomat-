import asyncio
import logging
from datetime import datetime, timedelta
from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from data.constants import DAYS_UZ
from filters.role_filter import IsAdmin
from utils.db_api.db import (
    get_spreadsheet_id, get_all_edupage_groups,
    get_kafedra_map_dict, get_edupage_id_to_name_dict,
)
from utils.scraper import scrape_timetable
from utils.sheets import daily_sheet_group_names, update_room_column

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())
_refresh_lock = asyncio.Lock()


def room_dates_keyboard(start=None):
    start = start or datetime.now()
    builder = InlineKeyboardBuilder()
    for offset in range(7):
        day = start + timedelta(days=offset)
        if day.weekday() != 6:
            builder.button(text=f'{day:%d.%m.%Y} {DAYS_UZ[day.weekday()]}',
                           callback_data=f'rooms_date_{day:%Y-%m-%d}')
    builder.adjust(2)
    builder.button(text='⬅️ Oldingi hafta', callback_data=f'rooms_page_{start - timedelta(days=7):%Y-%m-%d}')
    builder.button(text='Keyingi hafta ➡️', callback_data=f'rooms_page_{start + timedelta(days=7):%Y-%m-%d}')
    builder.adjust(2)
    builder.row(*InlineKeyboardBuilder().button(text='🏠 Bosh menyu', callback_data='go_home').buttons)
    return builder.as_markup()


@router.message(F.text == '🏫 Xonalarni yangilash')
async def open_room_dates(message: Message, state: FSMContext):
    await state.clear()
    await message.answer('🏫 Xonalar qaysi sana uchun yangilansin?\n'
                         'Tanlangan kunda oldindan yuklangan jadval bo‘lishi kerak.',
                         reply_markup=room_dates_keyboard())


@router.callback_query(F.data.startswith('rooms_page_'))
async def room_page(callback: CallbackQuery):
    await callback.answer()
    day = datetime.strptime(callback.data.removeprefix('rooms_page_'), '%Y-%m-%d')
    await callback.message.edit_reply_markup(reply_markup=room_dates_keyboard(day))


@router.callback_query(F.data.startswith('rooms_date_'))
async def refresh_rooms(callback: CallbackQuery):
    if _refresh_lock.locked():
        await callback.answer('Xonalar yangilanmoqda. Jarayon tugashini kuting.', show_alert=True)
        return
    day = datetime.strptime(callback.data.removeprefix('rooms_date_'), '%Y-%m-%d')
    await callback.answer()
    if _refresh_lock.locked():
        await callback.message.answer('Xonalar yangilanmoqda. Jarayon tugashini kuting.')
        return
    async with _refresh_lock:
        try:
            await callback.message.edit_text(f'⏳ {day:%d.%m.%Y} uchun xonalar tekshirilmoqda...')
            sheet_id = await get_spreadsheet_id()
            names = await asyncio.to_thread(daily_sheet_group_names, day, sheet_id)
            if not names:
                await callback.message.edit_text('Bu sanada jadval yoki guruhlar topilmadi. Avval jadvalni yuklang.',
                                                 reply_markup=room_dates_keyboard(day))
                return
            wanted = {name.strip().casefold() for name in names}
            groups = [group for group in await get_all_edupage_groups()
                      if group.group_name.strip().casefold() in wanted]
            if not groups:
                await callback.message.edit_text('Jadvaldagi guruhlarga mos EduPage guruhlari topilmadi.',
                                                 reply_markup=room_dates_keyboard(day))
                return
            lessons = await asyncio.to_thread(
                scrape_timetable, day, None, 'all', await get_kafedra_map_dict(),
                groups, await get_edupage_id_to_name_dict(),
            )
            if not lessons:
                await callback.message.edit_text('Bu sana uchun EduPage’da dars topilmadi. Xonalar o‘zgartirilmadi.',
                                                 reply_markup=room_dates_keyboard(day))
                return
            result = await asyncio.to_thread(update_room_column, lessons, day, sheet_id)
            await callback.message.edit_text(
                f'✅ {day:%d.%m.%Y}: xonalarni yangilash tugadi.\n'
                f'O‘zgartirilgan: {result["changed"]} ta.\n'
                f'O‘zgarishsiz: {result["unchanged"]} ta.\n'
                f'Mos kelmagan: {result["unmatched"]} ta.\n'
                f'Aniqlashtirish kerak: {result["ambiguous"]} ta.\n\n'
                'Faqat xona ustuni yangilandi. Davomat ma’lumotlari saqlandi.',
                reply_markup=room_dates_keyboard(day),
            )
        except Exception as exc:
            logging.exception('Xonalarni qo‘lda yangilashda xato')
            await callback.message.edit_text(f'❌ Xonalarni yangilashda xato:\n{escape(str(exc))}',
                                             parse_mode='HTML', reply_markup=room_dates_keyboard(day))
