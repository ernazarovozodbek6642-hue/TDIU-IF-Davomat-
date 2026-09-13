from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def admin_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Jadval yuklash"), KeyboardButton(text="📋 Yoqlama qilish")],
            [KeyboardButton(text="👥 Tyutorlar"), KeyboardButton(text="➕ Tyutor qo'shish")],
            [KeyboardButton(text="📊 Yoqlamalar tarixi"), KeyboardButton(text="✏️ Yoqlamani tahrirlash")],
            [KeyboardButton(text="📥 Import / Export (Excel)")],
            [KeyboardButton(text="➕ Admin qo'shish")],
            [KeyboardButton(text="⚙️ Sheets ID ni o'zgartirish")],
        ],
        resize_keyboard=True
    )


def tutor_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Yoqlama qilish")],
        ],
        resize_keyboard=True
    )


def cancel_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏠 Bosh menyu"), KeyboardButton(text="❌ Bekor qilish")],
        ],
        resize_keyboard=True
    )
