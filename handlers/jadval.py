import asyncio
import logging
import queue
import threading
from dataclasses import dataclass
from functools import partial
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from filters.role_filter import IsAdmin
from keyboards.inline.jadval import (
    get_dates_keyboard, get_kurs_keyboard,
    get_upload_cancel_keyboard, get_upload_cancel_confirm_keyboard,
)
from utils.scraper import scrape_timetable, scrape_week_timetable
from utils.sheets import upload_to_sheets, existing_daily_sheet_names
from utils.db_api.db import (
    get_kafedra_map_dict, get_edupage_groups_by_kurs, get_edupage_id_to_name_dict,
    get_all_edupage_groups, get_spreadsheet_id
)
from data.constants import DAYS_UZ

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@dataclass
class UploadJob:
    cancel_event: threading.Event
    progress_text: str = ""
    confirming: bool = False


ACTIVE_UPLOADS: dict[int, UploadJob] = {}


def _home_kb() -> InlineKeyboardMarkup:
    """Yakuniy xabarlardagi faqat Bosh menyu tugmasi"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 Bosh menyu", callback_data="go_home")
    return builder.as_markup()


@router.message(F.text == "📅 Jadval yuklash")
async def cmd_jadval(message: Message):
    await message.answer(
        "📅 <b>Qaysi kun uchun jadval kerak?</b>",
        parse_mode="HTML",
        reply_markup=get_dates_keyboard()
    )


@router.callback_query(F.data.startswith("date_"))
@router.callback_query(F.data.startswith("week_"))
async def handle_date(callback: CallbackQuery):
    await callback.answer()
    mode, date_str = callback.data.split('_', 1)
    target_date = datetime.strptime(date_str, "%Y-%m-%d")
    if mode == 'week':
        day_label = f"Butun hafta: {target_date:%d.%m}–{target_date + timedelta(days=5):%d.%m.%Y}"
        date_str = f'week:{date_str}'
    else:
        day_label = f"{target_date.strftime('%d.%m.%Y')} {DAYS_UZ[target_date.weekday()]}"

    await callback.message.edit_text(
        f"📅 <b>{day_label}</b>\n\nQaysi kurs dars jadvali yuklansin?",
        parse_mode="HTML",
        reply_markup=get_kurs_keyboard(date_str)
    )


@router.callback_query(F.data.startswith("kurs_"))
async def handle_kurs(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id in ACTIVE_UPLOADS:
        await callback.answer("Sizda jadval yuklash jarayoni allaqachon ishlayapti.", show_alert=True)
        return
    await callback.answer()
    parts = callback.data.split("_", 2)
    kurs = parts[1]
    kurs_label = "Barcha kurslar" if kurs == "all" else f"{kurs}-kurs"
    date_str = parts[2]
    whole_week = date_str.startswith('week:')
    date_str = date_str.removeprefix('week:')
    target_date = datetime.strptime(date_str, "%Y-%m-%d")
    day_label = (f"Butun hafta: {target_date:%d.%m}–{target_date + timedelta(days=5):%d.%m.%Y}"
                 if whole_week else f"{target_date:%d.%m.%Y} {DAYS_UZ[target_date.weekday()]}")

    msg = callback.message
    loop = asyncio.get_running_loop()
    try:
        spreadsheet_id = await get_spreadsheet_id()
        target_dates = (
            [target_date + timedelta(days=offset) for offset in range(6)]
            if whole_week else [target_date]
        )
        existing_sheets = await loop.run_in_executor(
            None, partial(existing_daily_sheet_names, target_dates, spreadsheet_id)
        )
    except Exception as exc:
        await msg.edit_text(
            f"❌ <b>Google Sheets tekshiruvida xato:</b>\n<code>{exc}</code>",
            parse_mode="HTML", reply_markup=_home_kb(),
        )
        return

    if not whole_week and existing_sheets:
        await msg.edit_text(
            f"⚠️ <b>{day_label}</b> jadvali oldindan yuklangan.\n\n"
            "Mavjud varaq va undagi qo‘lda kiritilgan ma’lumotlar saqlandi.",
            parse_mode="HTML", reply_markup=_home_kb(),
        )
        return
    if whole_week and len(existing_sheets) == len(target_dates):
        await msg.edit_text(
            f"⚠️ <b>{day_label}</b> varaqlari oldindan yuklangan.\n\n"
            "Qayta yuklash bajarilmadi.",
            parse_mode="HTML", reply_markup=_home_kb(),
        )
        return

    initial_text = (
        f"🕐 <b>{kurs_label} | {day_label}</b> uchun dars jadvali yuklanmoqda...\n\n"
        f"<b>Jarayon:</b> [░░░░░░░░░░░░░░░░░░░░] 0%\n"
        f"⏳ Tayyorlanmoqda, kuting..."
    )
    job = UploadJob(cancel_event=threading.Event(), progress_text=initial_text)
    ACTIVE_UPLOADS[user_id] = job
    uploaded_days = []
    try:
        await msg.edit_text(
            initial_text, parse_mode="HTML", reply_markup=get_upload_cancel_keyboard()
        )
        progress_queue = queue.Queue()

        def progress_callback(text):
            progress_queue.put(text)

        kafedra_map = await get_kafedra_map_dict()
        custom_groups = (await get_all_edupage_groups() if kurs == "all"
                         else await get_edupage_groups_by_kurs(kurs))
        id_to_name = await get_edupage_id_to_name_dict()

        future = loop.run_in_executor(
            None, partial(
                scrape_week_timetable if whole_week else scrape_timetable, target_date, progress_callback,
                kurs, kafedra_map, custom_groups, id_to_name, cancel_event=job.cancel_event,
            )
        )

        last_text = ""
        while not future.done():
            await asyncio.sleep(2)
            latest = None
            while not progress_queue.empty():
                try:
                    latest = progress_queue.get_nowait()
                except queue.Empty:
                    break
            if latest:
                job.progress_text = latest
            if latest and latest != last_text and not job.confirming and not job.cancel_event.is_set():
                last_text = latest
                try:
                    await msg.edit_text(
                        latest, parse_mode="HTML", reply_markup=get_upload_cancel_keyboard()
                    )
                except Exception:
                    pass

        result = await future
        if job.cancel_event.is_set():
            await msg.edit_text(
                "⛔ <b>Jadval yuklash to‘xtatildi.</b>",
                parse_mode="HTML", reply_markup=_home_kb(),
            )
            return
        daily_lessons = result if whole_week else {target_date: result}
        lesson_count = sum(len(items) for items in daily_lessons.values())

        if not lesson_count:
            await msg.edit_text(
                f"📭 <b>{day_label}</b> — {kurs_label}: dars topilmadi.",
                reply_markup=_home_kb()
            )
            return

        await msg.edit_text(
            f"📤 <b>Google Sheets ga yuklanmoqda...</b>\n\n"
            f"✅ Edupage dan <b>{lesson_count}</b> ta dars muvaffaqiyatli olindi.\n"
            f"⏳ Jadval shakllantirilmoqda, biroz kuting...",
            parse_mode="HTML",
            reply_markup=get_upload_cancel_keyboard(),
        )

        empty_days = []
        skipped_days = []
        uploaded_lesson_count = 0
        sheets_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
        for day, lessons in daily_lessons.items():
            if job.cancel_event.is_set():
                await msg.edit_text(
                    "⛔ <b>Jadval yuklash to‘xtatildi.</b>",
                    parse_mode="HTML", reply_markup=_home_kb(),
                )
                return
            if not lessons:
                empty_days.append(day.strftime('%d.%m'))
                continue
            day_sheet_name = f"{day.strftime('%d.%m')} {DAYS_UZ[day.weekday()]}"
            if day_sheet_name in existing_sheets:
                skipped_days.append(day_sheet_name)
                continue
            sheets_url, sheet_name = await loop.run_in_executor(
                None, partial(upload_to_sheets, lessons, day, spreadsheet_id)
            )
            uploaded_days.append(f'{sheet_name}: {len(lessons)} ta dars')
            uploaded_lesson_count += len(lessons)
            if job.cancel_event.is_set():
                completed = '\n'.join(uploaded_days)
                await msg.edit_text(
                    "⛔ <b>Jadval yuklash to‘xtatildi.</b>\n\n"
                    "Boshlangan Google Sheets amali xavfsiz tugatildi.\n"
                    f"Yuklangan varaqlar:\n{completed}",
                    parse_mode="HTML", reply_markup=_home_kb(),
                )
                return
        if not uploaded_days:
            skipped_summary = ', '.join(skipped_days)
            await msg.edit_text(
                "⚠️ <b>Yangi jadval yuklanmadi.</b>\n\n"
                f"Oldindan mavjud varaqlar: {skipped_summary}",
                parse_mode="HTML", reply_markup=_home_kb(),
            )
            return
        sheet_summary = '\n'.join(uploaded_days)
        empty_summary = ('\nDars yo‘q kunlar: ' + ', '.join(empty_days)) if empty_days else ''
        skipped_summary = ('\nOldindan mavjud: ' + ', '.join(skipped_days)) if skipped_days else ''

        await msg.edit_text(
            f"✅ <b>{kurs_label} | {day_label}</b> dars jadvali Google Sheets ga muvaffaqiyatli yuklandi!\n\n"
            f"📊 Yuklangan darslar: <b>{uploaded_lesson_count}</b> ta\n"
            f"📋 {sheet_summary}{empty_summary}{skipped_summary}\n\n"
            f"🔗 <a href='{sheets_url}'>Google Sheets jadvalini ochish</a>",
            parse_mode="HTML",
            reply_markup=_home_kb()
        )

    except Exception as e:
        logging.error(f"Jadval yuklashda xato: {e}")
        completed = ('\n\nYuklangan varaqlar:\n' + '\n'.join(uploaded_days)) if uploaded_days else ''
        try:
            await msg.edit_text(
                f"❌ <b>Xatolik yuz berdi:</b>\n<code>{str(e)}</code>{completed}",
                parse_mode="HTML",
                reply_markup=_home_kb()
            )
        except Exception:
            pass
    finally:
        if ACTIVE_UPLOADS.get(user_id) is job:
            ACTIVE_UPLOADS.pop(user_id, None)


@router.callback_query(F.data == "upload_cancel_request")
async def request_upload_cancel(callback: CallbackQuery):
    job = ACTIVE_UPLOADS.get(callback.from_user.id)
    if job is None:
        await callback.answer("Faol yuklash jarayoni topilmadi.", show_alert=True)
        return
    job.confirming = True
    await callback.answer()
    await callback.message.edit_text(
        f"{job.progress_text}\n\n⚠️ <b>Yuklashni rostdan ham to‘xtatasizmi?</b>",
        parse_mode="HTML", reply_markup=get_upload_cancel_confirm_keyboard(),
    )


@router.callback_query(F.data == "upload_cancel_continue")
async def continue_upload(callback: CallbackQuery):
    job = ACTIVE_UPLOADS.get(callback.from_user.id)
    if job is None:
        await callback.answer("Faol yuklash jarayoni topilmadi.", show_alert=True)
        return
    job.confirming = False
    await callback.answer("Yuklash davom etmoqda.")
    await callback.message.edit_text(
        job.progress_text, parse_mode="HTML", reply_markup=get_upload_cancel_keyboard(),
    )


@router.callback_query(F.data == "upload_cancel_confirm")
async def confirm_upload_cancel(callback: CallbackQuery):
    job = ACTIVE_UPLOADS.get(callback.from_user.id)
    if job is None:
        await callback.answer("Faol yuklash jarayoni topilmadi.", show_alert=True)
        return
    job.cancel_event.set()
    job.confirming = False
    await callback.answer("Yuklash to‘xtatilmoqda.")
    await callback.message.edit_text(
        "⏹ <b>Yuklash to‘xtatilmoqda...</b>\n\n"
        "Joriy EduPage so‘rovi tugashi bilan jarayon xavfsiz yopiladi.",
        parse_mode="HTML",
    )
