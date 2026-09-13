"""Server/Docker deployment diagnostics without printing any secrets."""
import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from aiogram import Bot
from bs4 import BeautifulSoup
from sqlalchemy import text
from selenium.webdriver.support.ui import WebDriverWait

from data.config import BOT_TOKEN, validate_runtime_config
from data.edupage_catalog import TIMETABLE_NUM
from utils.google_credentials import load_google_credentials
from utils.scraper import find_chrome_binary, get_driver
from utils.sheets import SCOPES, _get_gspread_client, validate_spreadsheet_access


def check_local() -> list[str]:
    validate_runtime_config()
    credentials = load_google_credentials(SCOPES)
    if not credentials.service_account_email:
        raise RuntimeError("Google service-account client_email topilmadi")

    chrome = find_chrome_binary()
    if not chrome:
        raise RuntimeError("Chrome/Chromium topilmadi")
    driver_path = os.getenv("CHROMEDRIVER_PATH", "").strip()
    if driver_path and not Path(driver_path).is_file():
        raise RuntimeError(f"CHROMEDRIVER_PATH topilmadi: {driver_path}")
    return [f"Chrome: {chrome}", "Google credentials: OK", "Muhit o‘zgaruvchilari: OK"]


async def check_database() -> tuple[str, str]:
    from utils.db_api.db import engine, get_spreadsheet_id

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return "Neon/PostgreSQL", await get_spreadsheet_id()
    finally:
        await engine.dispose()


async def check_telegram() -> str:
    bot = Bot(token=BOT_TOKEN)
    try:
        identity = await bot.get_me()
        return f"Telegram: @{identity.username}"
    finally:
        await bot.session.close()


def check_google(spreadsheet_id: str, write_test: bool) -> list[str]:
    title = validate_spreadsheet_access(spreadsheet_id)
    messages = [f"Google Sheets: {title} (edit ruxsati bor)"]
    if not write_test:
        return messages

    client, _ = _get_gspread_client()
    spreadsheet = client.open_by_key(spreadsheet_id)
    worksheet = None
    test_name = "__bot_deploy_check_" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    try:
        worksheet = spreadsheet.add_worksheet(title=test_name, rows=2, cols=3)
        worksheet.update(range_name="A1:C1", values=[[1, 2, "=SUM(A1:B1)"]], value_input_option="USER_ENTERED")
        if worksheet.acell("C1").value != "3":
            raise RuntimeError("Google Sheets formula tekshiruvi kutilgan natijani bermadi")
        messages.append("Google Sheets vaqtinchalik yozish/formula testi: OK")
    finally:
        if worksheet is not None:
            spreadsheet.del_worksheet(worksheet)
    return messages


def check_edupage() -> str:
    driver = get_driver()
    try:
        url = f"https://tsue.edupage.org/timetable/view.php?num={TIMETABLE_NUM}&class=*254"
        driver.get(url)
        WebDriverWait(driver, 45).until(lambda d: d.find_elements("css selector", "svg g > text"))
        svg = BeautifulSoup(driver.page_source, "html.parser").find("svg")
        if svg is None or not svg.select_one("g > text"):
            raise RuntimeError("EduPage jadval SVG elementi topilmadi")
        return "Chromium + ChromeDriver + EduPage: OK"
    finally:
        driver.quit()


async def run_full(write_test: bool) -> list[str]:
    messages = check_local()
    database_message, spreadsheet_id = await check_database()
    messages.append(database_message + ": OK")
    messages.extend(await asyncio.to_thread(check_google, spreadsheet_id, write_test))
    messages.append(await check_telegram())
    messages.append(await asyncio.to_thread(check_edupage))
    return messages


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Bot deployment diagnostikasi")
    parser.add_argument("--local", action="store_true", help="Faqat image ichidagi fayl va dasturlarni tekshiradi")
    parser.add_argument("--google-write", action="store_true", help="Vaqtinchalik varaq yaratib-o‘chirib yozishni tekshiradi")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    try:
        messages = check_local() if args.local else asyncio.run(run_full(args.google_write))
    except Exception as exc:
        print(f"DEPLOYMENT CHECK FAILED: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 1

    if not args.quiet:
        for message in messages:
            print(f"OK - {message}")
        print("DEPLOYMENT CHECK PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
