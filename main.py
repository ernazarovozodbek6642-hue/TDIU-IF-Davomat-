"""
main.py — TDIU Iqtisodiyot Fakulteti Davomat va Jadval Boti
Aiogram 3.x Modular Arxitekturasi
"""
import asyncio
import logging
from datetime import datetime, timedelta
from functools import partial

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from data.config import BOT_TOKEN, ADMINS, validate_runtime_config
from data.constants import DAYS_UZ
from handlers import setup_message_routers
from utils.db_api.db import (
    init_db, get_kafedra_map_dict, get_all_edupage_groups, get_edupage_id_to_name_dict,
    get_admin_ids, get_spreadsheet_id, get_room_refresh_minutes, engine
)
from utils.scraper import scrape_timetable
from utils.sheets import (
    upload_to_sheets, daily_sheet_exists, daily_sheet_group_names, update_room_column,
)

# Logging sozlamalari
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

validate_runtime_config()
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
_last_room_refresh_attempt: datetime | None = None
_last_room_refresh_interval: int | None = None
_room_refresh_task: asyncio.Task | None = None


async def auto_upload_today():
    """Har kuni ertalab 07:00 da dars jadvalini avtomatik yuklash"""
    today = datetime.now()
    if today.weekday() == 6:  # Yakshanba
        return

    logging.info(f"⏰ Avtomatik jadval yuklash boshlandi: {today.strftime('%d.%m.%Y')}")
    admin_ids = list(ADMINS)
    try:
        admin_ids = await get_admin_ids()
        loop = asyncio.get_running_loop()
        spreadsheet_id = await get_spreadsheet_id()
        sheet_name = f"{today.strftime('%d.%m')} {DAYS_UZ[today.weekday()]}"
        already_exists = await loop.run_in_executor(
            None, partial(daily_sheet_exists, today, spreadsheet_id)
        )
        if already_exists:
            logging.info("Avtomatik yuklash o'tkazib yuborildi: %s varag'i mavjud", sheet_name)
            for admin_id in admin_ids:
                try:
                    await bot.send_message(
                        admin_id,
                        f"ℹ️ <b>{sheet_name}</b> varag‘i oldindan mavjud. "
                        "Avtomatik yuklash uni qayta yozmadi.",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass
            return

        kafedra_map = await get_kafedra_map_dict()
        id_to_name = await get_edupage_id_to_name_dict()

        groups = await get_all_edupage_groups()
        all_lessons = await loop.run_in_executor(
            None, scrape_timetable, today, None, "all", kafedra_map, groups, id_to_name
        )

        if not all_lessons:
            for admin_id in admin_ids:
                try:
                    await bot.send_message(
                        admin_id,
                        f"⚠️ <b>{today.strftime('%d.%m.%Y')}</b> — Edupage da dars jadvali topilmadi.",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
            return

        sheets_url, sheet_name = await loop.run_in_executor(
            None, partial(upload_to_sheets, all_lessons, today, spreadsheet_id)
        )

        for admin_id in admin_ids:
            try:
                await bot.send_message(
                    admin_id,
                    f"✅ <b>{today.strftime('%d.%m.%Y')} {DAYS_UZ[today.weekday()]}</b> dars jadvali avtomatik yuklandi!\n\n"
                    f"📊 Jami darslar: <b>{len(all_lessons)}</b> ta\n"
                    f"📋 Varaq: <b>{sheet_name}</b>\n\n"
                    f"🔗 <a href='{sheets_url}'>Google Sheets ni ochish</a>",
                    parse_mode="HTML"
                )
            except Exception:
                pass

    except Exception as e:
        logging.error(f"Avtomatik jadval yuklashda xato: {e}")
        for admin_id in admin_ids:
            try:
                await bot.send_message(
                    admin_id,
                    f"❌ <b>Avtomatik yuklashda xatolik yuz berdi:</b>\n<code>{e}</code>",
                    parse_mode="HTML"
                )
            except Exception:
                pass


async def _perform_room_refresh(now: datetime):
    """Run the longer EduPage and Sheets work outside the scheduler callback."""
    global _last_room_refresh_attempt
    try:
        loop = asyncio.get_running_loop()
        spreadsheet_id = await get_spreadsheet_id()
        sheet_groups = await loop.run_in_executor(
            None, partial(daily_sheet_group_names, now, spreadsheet_id)
        )
        if not sheet_groups:
            _last_room_refresh_attempt = None
            return
        kafedra_map = await get_kafedra_map_dict()
        id_to_name = await get_edupage_id_to_name_dict()
        wanted_groups = {name.casefold() for name in sheet_groups}
        groups = [
            group for group in await get_all_edupage_groups()
            if group.group_name.strip().casefold() in wanted_groups
        ]
        if not groups:
            logging.warning("Xona yangilash uchun C ustuniga mos EduPage guruhi topilmadi")
            return
        logging.info("Xona yangilash: C ustunidagi %s ta guruh tekshirilmoqda", len(groups))
        lessons = await loop.run_in_executor(
            None, scrape_timetable, now, None, 'all', kafedra_map, groups, id_to_name
        )
        result = await loop.run_in_executor(
            None, partial(update_room_column, lessons, now, spreadsheet_id)
        )
        logging.info(
            "Xonalar yangilandi: %s ta o‘zgardi, %s ta mos keldi, %s ta noaniq",
            result['changed'], result['matched'], result['ambiguous'],
        )
    except Exception:
        logging.exception("Xonalarni avtomatik yangilashda xato")
        for admin_id in await get_admin_ids():
            try:
                await bot.send_message(admin_id, "❌ Xonalarni avtomatik yangilashda xatolik yuz berdi.")
            except Exception:
                pass


async def auto_refresh_today_rooms():
    """Start a room-only refresh when the configured interval is due."""
    global _last_room_refresh_attempt, _last_room_refresh_interval, _room_refresh_task
    now = datetime.now()
    if now.weekday() == 6:
        return
    minutes = await get_room_refresh_minutes()
    if minutes == 0:
        _last_room_refresh_interval = 0
        _last_room_refresh_attempt = None
        return
    if _room_refresh_task is not None and not _room_refresh_task.done():
        return
    if minutes != _last_room_refresh_interval:
        _last_room_refresh_interval = minutes
        _last_room_refresh_attempt = None
    if (_last_room_refresh_attempt is not None
            and now - _last_room_refresh_attempt < timedelta(minutes=minutes)):
        return

    _last_room_refresh_attempt = now
    _room_refresh_task = asyncio.create_task(
        _perform_room_refresh(now), name='room-column-refresh'
    )

async def _init_db_with_retry(attempts: int = 5):
    for attempt in range(1, attempts + 1):
        try:
            await init_db()
            return
        except Exception:
            if attempt == attempts:
                raise
            delay = min(2 ** attempt, 30)
            logging.exception(
                "Database ulanishi muvaffaqiyatsiz (%s/%s). %s soniyadan keyin qayta uriniladi.",
                attempt, attempts, delay,
            )
            await asyncio.sleep(delay)


async def on_startup(dispatcher: Dispatcher):
    # Server uyg'onganda Neon/DNS bir necha soniya kechiksa ham qayta urinish.
    await _init_db_with_retry()
    logging.info("Ma'lumotlar bazasi jadvallari muvaffaqiyatli ishga tushirildi.")

    # Adminlarga bildirishnoma
    for admin_id in await get_admin_ids():
        try:
            await bot.send_message(
                chat_id=admin_id,
                text="🚀 <b>TDIU-IF Davomat Boti muvaffaqiyatli ishga tushdi!</b>",
                parse_mode="HTML"
            )
        except Exception as e:
            logging.warning(f"Adminga ({admin_id}) xabar yuborishda xato: {e}")


async def on_shutdown(dispatcher: Dispatcher):
    await engine.dispose()
    logging.info("Database ulanish havzasi yopildi.")


async def main():
    main_router = setup_message_routers()
    dp.include_router(main_router)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # APScheduler sozlash (Har kuni Toshkent vaqti bilan 07:00 da)
    scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")
    scheduler.add_job(
        auto_upload_today, "cron", hour=7, minute=0,
        id="daily_timetable_upload", replace_existing=True,
        coalesce=True, misfire_grace_time=3600, max_instances=1,
    )
    scheduler.add_job(
        auto_refresh_today_rooms, "interval", minutes=1,
        id="room_column_refresh_check", replace_existing=True,
        coalesce=True, misfire_grace_time=60, max_instances=1,
    )
    scheduler.start()
    logging.info("⏰ APScheduler ishga tushdi (Har kuni 07:00 da avto yuklash)")

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logging.info("Bot polling rejimi boshlandi...")
        await dp.start_polling(bot)
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot to'xtatildi.")
