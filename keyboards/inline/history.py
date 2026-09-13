from datetime import date
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def nav_row(back_cb: str | None = None) -> list[InlineKeyboardButton]:
    row = []
    if back_cb:
        row.append(InlineKeyboardButton(text="↩️ Ortga", callback_data=back_cb))
    row.append(InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="go_home"))
    return row


def get_history_dates_keyboard(dates: list[date]) -> InlineKeyboardMarkup:
    today = date.today()
    builder = InlineKeyboardBuilder()
    for d in dates:
        label = d.strftime("%d.%m.%Y")
        if d == today:
            label = f"📅 Bugun {label}"
        builder.button(text=label, callback_data=f"hdate:{d.isoformat()}")
    builder.adjust(2)
    builder.row(*nav_row())
    return builder.as_markup()


def get_history_paras_keyboard(all_paras: list[int], selected_paras: list[int]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for p in all_paras:
        icon = "✅" if p in selected_paras else "⬜"
        builder.button(text=f"{icon} {p}-para", callback_data=f"hpara:{p}")
    builder.adjust(4)

    all_icon = "✅" if len(selected_paras) == len(all_paras) and all_paras else "⬜"
    builder.row(InlineKeyboardButton(text=f"{all_icon} Barchasi", callback_data="hpara:all"))
    builder.row(InlineKeyboardButton(text="➡️ Davom etish", callback_data="hpara_done"))
    builder.row(*nav_row(back_cb="hpara_back"))
    return builder.as_markup()


def get_history_groups_keyboard(
    all_groups: list[str],
    selected_groups: list[str],
    back_cb: str = "hgrp_back",
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for g in all_groups:
        icon = "✅" if g in selected_groups else "⬜"
        safe_g = g.replace("/", "|")
        builder.button(text=f"{icon} {g}", callback_data=f"hgrp:{safe_g}")
    builder.adjust(3)

    all_icon = "✅" if all_groups and set(all_groups).issubset(selected_groups) else "⬜"
    builder.button(text=f"{all_icon} Barchasi", callback_data="hgrp:all")
    builder.row(InlineKeyboardButton(text="📥 Excel hisobotni yuklash", callback_data="h_export_excel"))
    builder.row(*nav_row(back_cb=back_cb))
    return builder.as_markup()
