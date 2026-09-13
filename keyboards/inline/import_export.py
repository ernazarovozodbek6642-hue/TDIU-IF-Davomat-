from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def nav_row(back_cb: str | None = None) -> list[InlineKeyboardButton]:
    row = []
    if back_cb:
        row.append(InlineKeyboardButton(text="↩️ Ortga", callback_data=back_cb))
    row.append(InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="go_home"))
    return row


def get_import_export_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📥 Yangi Talabalarni qo'shish (Smart)", callback_data="ie_import_students")
    builder.button(text="🔄 Guruh bo'yicha Talabalarni yangilash", callback_data="ie_import_single_group")
    builder.button(text="⚠️ Butun Fakultet Talabalarini To'liq Almashtirish", callback_data="ie_replace_all_students")
    builder.button(text="📤 Barcha Talabalarni Export qilish", callback_data="ie_export_students")
    builder.button(text="📥 Tyutorlarni Import qilish", callback_data="ie_import_tutors")
    builder.button(text="📤 Tyutorlarni Export qilish", callback_data="ie_export_tutors")
    builder.button(text="🏫 EduPage Guruhlarini Import qilish", callback_data="ie_import_edupage")
    builder.button(text="📤 EduPage Guruhlarini Export qilish", callback_data="ie_export_edupage")
    builder.button(text="📚 Fanlar & Kafedralarni Import qilish", callback_data="ie_import_kafedras")
    builder.button(text="📤 Fanlar & Kafedralarni Export qilish", callback_data="ie_export_kafedras")
    builder.button(text="📄 Namunaviy Shablonlarni yuklab olish", callback_data="ie_get_templates")
    builder.adjust(1)
    builder.row(*nav_row())
    return builder.as_markup()
