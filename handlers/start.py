from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from utils.db_api.db import get_tutor, is_admin
from keyboards.default.menu import admin_menu, tutor_menu
from keyboards.inline.jadval import get_dates_keyboard

router = Router()


async def _send_home(target, state: FSMContext, uid: int):
    """Bosh menyuga qaytish uchun umumiy yordamchi"""
    await state.clear()
    if await is_admin(uid):
        text = (
            "🏠 <b>Bosh menyu</b>\n\n"
            "Quyidagi bo'limlardan birini tanlang:"
        )
        kb = admin_menu()
    else:
        tutor = await get_tutor(uid)
        if tutor:
            text = (
                f"🏠 <b>Bosh menyu</b>\n\n"
                f"Salom, <b>{tutor.name}</b>!\n"
                f"Davomat kiritish uchun tugmani bosing."
            )
            kb = tutor_menu()
        else:
            text = (
                "Assalomu alaykum!\n\n"
                f"🆔 Sizning Telegram ID raqamingiz: <code>{uid}</code>\n\n"
                "Botdan foydalanish uchun dekanatga murojaat qiling "
                "va yuqoridagi ID raqamingizni taqdim eting."
            )
            kb = ReplyKeyboardRemove()

    if isinstance(target, Message):
        await target.answer(text, parse_mode="HTML", reply_markup=kb)
    elif isinstance(target, CallbackQuery):
        await target.message.answer(text, parse_mode="HTML", reply_markup=kb)
        try:
            await target.message.delete()
        except Exception:
            pass


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    await _send_home(message, state, uid)


@router.message(F.text.in_(["❌ Bekor qilish", "🏠 Bosh menyu"]))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    await _send_home(message, state, uid)


# ── Global inline callback handlerlar ─────────────────────

@router.callback_query(F.data == "go_home")
async def go_home_callback(callback: CallbackQuery, state: FSMContext):
    """Istalgan inline menyudan Bosh menyuga qaytish"""
    await callback.answer()
    await _send_home(callback, state, callback.from_user.id)


@router.callback_query(F.data == "jadval_back")
async def jadval_back_callback(callback: CallbackQuery):
    """Kurs tanlash sahifasidan sana tanlash sahifasiga qaytish"""
    await callback.answer()
    await callback.message.edit_text(
        "📅 <b>Qaysi kun uchun jadval kerak?</b>",
        parse_mode="HTML",
        reply_markup=get_dates_keyboard()
    )


@router.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery):
    """Sahifa raqami tugmasi — hech narsa qilmaydi"""
    await callback.answer()
