from datetime import datetime, timedelta
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from data.constants import DAYS_UZ


def nav_row(back_cb: str | None = None) -> list[InlineKeyboardButton]:
    """Har bir sahifaning pastida 'Ortga' va 'Bosh menyu' tugmalari"""
    row = []
    if back_cb:
        row.append(InlineKeyboardButton(text="↩️ Ortga", callback_data=back_cb))
    row.append(InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="go_home"))
    return row


def get_dates_keyboard() -> InlineKeyboardMarkup:
    today = datetime.now()
    builder = InlineKeyboardBuilder()
    for i in range(7):
        date = today + timedelta(days=i)
        if date.weekday() == 6:  # Yakshanba
            continue
        label = f"{date.strftime('%d.%m')} {DAYS_UZ[date.weekday()]}"
        if i == 0:
            label = f"📅 Bugun {label}"
        builder.button(text=label, callback_data=f"date_{date.strftime('%Y-%m-%d')}")
    builder.adjust(2)
    monday = today - timedelta(days=today.weekday())
    saturday = monday + timedelta(days=5)
    builder.row(InlineKeyboardButton(
        text=f"🗓 Butun hafta ({monday:%d.%m}–{saturday:%d.%m})",
        callback_data=f"week_{monday:%Y-%m-%d}"
    ))
    builder.row(*nav_row())
    return builder.as_markup()


def get_kurs_keyboard(date_str: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="1️⃣ 1-kurs", callback_data=f"kurs_1_{date_str}")
    builder.button(text="2️⃣ 2-kurs", callback_data=f"kurs_2_{date_str}")
    builder.button(text="3️⃣ 3-kurs", callback_data=f"kurs_3_{date_str}")
    builder.button(text="4️⃣ 4-kurs", callback_data=f"kurs_4_{date_str}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="📚 Barcha kurslarni yuklash", callback_data=f"kurs_all_{date_str}"))
    builder.row(*nav_row(back_cb="jadval_back"))
    return builder.as_markup()


def get_upload_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⛔ Yuklashni to‘xtatish", callback_data="upload_cancel_request")
    ]])


def get_upload_cancel_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Ha, to‘xtatilsin", callback_data="upload_cancel_confirm"),
        InlineKeyboardButton(text="↩️ Yo‘q, davom etsin", callback_data="upload_cancel_continue"),
    ]])
