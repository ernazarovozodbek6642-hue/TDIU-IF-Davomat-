from datetime import datetime, date
import asyncio
import logging
from html import escape
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from filters.role_filter import IsAdmin
from states.states import AdminTutorState, AdminEditState, TutorAttendanceState, AddAdminState, SheetsSettingsState
from utils.db_api.db import (
    get_all_tutors, get_tutor_by_id, add_tutor, delete_tutor,
    get_tutor_groups, assign_group_to_tutor, remove_group_from_tutor,
    get_paras_for_date, get_groups_for_date_and_paras,
    get_students_by_group, get_absent_students, add_bot_admin,
    get_spreadsheet_id, set_spreadsheet_id, get_all_edupage_groups
)
from utils.sheet_settings import parse_spreadsheet_id
from utils.sheets import sheets_service_account_email, validate_spreadsheet_access
from keyboards.default.menu import admin_menu, cancel_menu
from keyboards.inline.admin import (
    get_tutors_list_keyboard, get_tutor_detail_keyboard,
    get_tutor_delete_confirm_keyboard, get_assignment_courses_keyboard,
    get_group_picker_keyboard
)
from keyboards.inline.attendance import (
    get_course_picker_keyboard, get_groups_keyboard,
    get_attendance_students_keyboard,
)
from utils.group_courses import groups_by_course

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.message(F.text == "⚙️ Sheets ID ni o'zgartirish")
async def start_change_sheets(message: Message, state: FSMContext):
    await state.clear()
    current_id = await get_spreadsheet_id()
    email = sheets_service_account_email()
    await state.set_state(SheetsSettingsState.entering_spreadsheet_id)
    await message.answer(
        f'📊 <b>Joriy Google Sheets:</b>\n<code>{escape(current_id)}</code>\n\n'
        'Yangi Google Sheets havolasini yoki ID’sini yuboring.\n\n'
        f'Faylni quyidagi manzilga <b>Editor</b> huquqi bilan ulashing:\n<code>{escape(email)}</code>\n\n'
        'Saqlangandan keyin jadval va davomat yangi fayl bilan ishlaydi.',
        parse_mode='HTML', reply_markup=cancel_menu()
    )


@router.message(SheetsSettingsState.entering_spreadsheet_id)
async def sheets_id_entered(message: Message, state: FSMContext):
    try:
        spreadsheet_id = parse_spreadsheet_id(message.text or '')
    except ValueError as exc:
        await message.answer(f'❌ {exc}')
        return
    status = await message.answer('⏳ Google Sheets fayli va tahrirlash ruxsati tekshirilmoqda...')
    try:
        title = await asyncio.to_thread(validate_spreadsheet_access, spreadsheet_id)
    except ValueError as exc:
        await status.edit_text(f'❌ {exc}\nID o‘zgartirilmadi. Ruxsatni tekshirib, qayta yuboring.')
        return
    except Exception:
        logging.exception('Yangi Google Sheets faylini tekshirishda xato')
        await status.edit_text('❌ Faylni tekshirib bo‘lmadi. Havola va botning Editor ruxsatini tekshiring. '
                               'ID o‘zgartirilmadi; qayta yuborishingiz mumkin.')
        return
    await set_spreadsheet_id(spreadsheet_id, updated_by=message.from_user.id)
    await state.clear()
    await status.edit_text('✅ Google Sheets ID yangilandi.')
    await message.answer(
        f'📊 <b>{escape(title)}</b>\n<code>{spreadsheet_id}</code>\n\n'
        f'<a href="https://docs.google.com/spreadsheets/d/{spreadsheet_id}">Google Sheets ni ochish</a>\n\n'
        'Keyingi jadval yuklash va davomat yangilash shu faylda bajariladi.',
        parse_mode='HTML', reply_markup=admin_menu()
    )


@router.message(F.text == "➕ Admin qo'shish")
async def start_add_admin(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(AddAdminState.entering_telegram_id)
    await message.answer(
        "🆔 <b>Yangi adminning Telegram ID raqamini yuboring.</b>\n\n"
        "U siz kabi barcha bo‘limlardan foydalanishi va boshqa adminlarni ham qo‘shishi mumkin.\n"
        "Telegram ID raqamini @userinfobot orqali bilish mumkin.",
        parse_mode='HTML', reply_markup=cancel_menu()
    )


@router.message(AddAdminState.entering_telegram_id)
async def admin_id_entered(message: Message, state: FSMContext):
    value = (message.text or '').strip()
    if not value.isascii() or not value.isdigit() or len(value) > 16 or not 0 < int(value) < 2**52:
        await message.answer('❌ To‘g‘ri Telegram ID raqamini yuboring (masalan: 123456789).')
        return
    telegram_id = int(value)
    added = await add_bot_admin(telegram_id, added_by=message.from_user.id)
    await state.clear()
    text = (f'✅ <code>{telegram_id}</code> admin sifatida qo‘shildi.\n\n'
            'U botga /start yuborsa, barcha admin bo‘limlari ochiladi.' if added else
            f'ℹ️ <code>{telegram_id}</code> allaqachon admin.')
    await message.answer(text, parse_mode='HTML', reply_markup=admin_menu())


# ── Tyutorlar Ro'yxati ────────────────────────────────────

@router.message(F.text == "👥 Tyutorlar")
async def list_tutors(message: Message, state: FSMContext):
    await state.clear()
    tutors = await get_all_tutors()
    if not tutors:
        builder = InlineKeyboardBuilder()
        builder.button(text="➕ Tyutor qo'shish", callback_data="adm_add_tutor")
        await message.answer("👥 Hozircha tyutorlar qo'shilmagan.", reply_markup=builder.as_markup())
        return

    await message.answer(
        "👥 <b>Fakultet Tyutorlari:</b>\n<i>Tyutor ustiga bosib guruhlarini boshqaring:</i>",
        parse_mode="HTML",
        reply_markup=get_tutors_list_keyboard(tutors)
    )


@router.callback_query(F.data == "adm_back_tutors")
async def back_to_tutors_list(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    tutors = await get_all_tutors()
    await callback.message.edit_text(
        "👥 <b>Fakultet Tyutorlari:</b>",
        parse_mode="HTML",
        reply_markup=get_tutors_list_keyboard(tutors)
    )


@router.callback_query(F.data.startswith("adm_tutor:"))
async def view_tutor(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    tutor_id = int(callback.data.split(":")[1])
    tutor = await get_tutor_by_id(tutor_id)
    if not tutor:
        await callback.answer("Tyutor topilmadi!", show_alert=True)
        return

    groups = await get_tutor_groups(tutor_id)
    groups_str = ", ".join(groups) if groups else "<i>Biriktirilmagan</i>"

    text = (
        f"👤 <b>Tyutor:</b> {tutor.name}\n"
        f"🆔 <b>Telegram ID:</b> <code>{tutor.telegram_id}</code>\n"
        f"📚 <b>Guruhlari:</b> {groups_str}\n"
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_tutor_detail_keyboard(tutor_id)
    )


# ── Tyutor Qo'shish ───────────────────────────────────────

@router.message(F.text == "➕ Tyutor qo'shish")
@router.callback_query(F.data == "adm_add_tutor")
async def start_add_tutor(event: Message | CallbackQuery, state: FSMContext):
    await state.set_state(AdminTutorState.entering_tutor_name)
    msg = event if isinstance(event, Message) else event.message
    if isinstance(event, CallbackQuery):
        await event.answer()
    await msg.answer("✏️ <b>Tyutorning to'liq F.I.Sh. kiriting:</b>", parse_mode="HTML", reply_markup=ReplyKeyboardRemove())


@router.message(AdminTutorState.entering_tutor_name)
async def tutor_name_entered(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 3:
        await message.answer("❌ Iltimos, to'g'ri ism-familiya kiriting:")
        return
    await state.update_data(tutor_name=name)
    await state.set_state(AdminTutorState.entering_tutor_id)
    await message.answer(
        f"🆔 <b>{name}</b> ning Telegram ID raqamini kiriting:\n\n"
        f"<i>(Tyutor @userinfobot orqali o'z ID sini bilib olishi mumkin)</i>",
        parse_mode="HTML"
    )


@router.message(AdminTutorState.entering_tutor_id)
async def tutor_id_entered(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("❌ Telegram ID faqat raqamlardan iborat bo'lishi kerak! Qayta kiriting:")
        return

    tg_id = int(text)
    data = await state.get_data()
    name = data["tutor_name"]

    tutor = await add_tutor(tg_id, name)
    await state.clear()

    await message.answer(
        f"✅ <b>{name}</b> muvaffaqiyatli tyutor sifatida qo'shildi!\n"
        f"🆔 <code>{tg_id}</code>\n\n"
        f"Endi «👥 Tyutorlar» bo'limidan unga guruh biriktirishingiz mumkin.",
        parse_mode="HTML",
        reply_markup=admin_menu()
    )


# ── Guruh Biriktirish (Toggle) ────────────────────────────

async def _assignment_groups_by_course() -> dict[str, list[str]]:
    courses = {course: [] for course in ("1", "2", "3", "4")}
    for group in await get_all_edupage_groups():
        course = str(group.kurs).removesuffix("-kurs")
        if course in courses and group.group_name not in courses[course]:
            courses[course].append(group.group_name)
    for groups in courses.values():
        groups.sort(key=str.casefold)
    return courses


async def _render_assignment_courses(
    callback: CallbackQuery,
    tutor_id: int,
    selected_new: set,
    removed_old: set,
):
    courses = await _assignment_groups_by_course()
    kb = get_assignment_courses_keyboard(
        tutor_id,
        {course: len(groups) for course, groups in courses.items()},
        len(selected_new) + len(removed_old),
    )
    await callback.message.edit_text(
        "📚 <b>Kursni tanlang:</b>\n\n"
        "Tanlangan kurs ichidan tyutorga biriktiriladigan guruhlarni belgilang.",
        parse_mode="HTML",
        reply_markup=kb,
    )


async def _render_group_picker(
    callback: CallbackQuery,
    tutor_id: int,
    course: str,
    selected_new: set,
    removed_old: set,
):
    already = set(await get_tutor_groups(tutor_id))
    courses = await _assignment_groups_by_course()
    kb = get_group_picker_keyboard(
        tutor_id=tutor_id,
        all_groups=courses.get(course, []),
        already_assigned=already,
        selected_new=selected_new,
        removed_old=removed_old
    )
    await callback.message.edit_text(
        f"📎 <b>{course}-kurs guruhlarini tanlang:</b>\n"
        "✅ = biriktirilgan | ☑️ = yangi | ⬜ = biriktirilmagan\n\n"
        "<i>Guruh nomini bosing va oxirida «💾 Saqlash» tugmasini bosing:</i>",
        parse_mode="HTML",
        reply_markup=kb
    )


@router.callback_query(F.data.startswith("adm_assign:"))
async def open_group_picker(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    tutor_id = int(callback.data.split(":")[1])
    await state.update_data(assign_tutor_id=tutor_id, assign_selected=[], assign_removed=[])
    await state.set_state(AdminTutorState.picking_group)
    await _render_assignment_courses(callback, tutor_id, set(), set())


@router.callback_query(AdminTutorState.picking_group, F.data.startswith("adm_grp_courses:"))
async def back_to_assignment_courses(callback: CallbackQuery, state: FSMContext):
    tutor_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    await _render_assignment_courses(
        callback,
        tutor_id,
        set(data.get("assign_selected", [])),
        set(data.get("assign_removed", [])),
    )
    await callback.answer()


@router.callback_query(AdminTutorState.picking_group, F.data.startswith("adm_grp_course:"))
async def open_course_groups(callback: CallbackQuery, state: FSMContext):
    _, tutor_id_raw, course = callback.data.split(":")
    tutor_id = int(tutor_id_raw)
    data = await state.get_data()
    await state.update_data(assign_course=course)
    await _render_group_picker(
        callback,
        tutor_id,
        course,
        set(data.get("assign_selected", [])),
        set(data.get("assign_removed", [])),
    )
    await callback.answer()


@router.callback_query(AdminTutorState.picking_group, F.data.startswith("adm_grp_tog:"))
async def toggle_group_assignment(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    tutor_id = int(parts[1])
    group_name = ":".join(parts[2:]).replace("|", "/")

    data = await state.get_data()
    selected_new = set(data.get("assign_selected", []))
    removed_old = set(data.get("assign_removed", []))
    course = data.get("assign_course", "1")
    already = set(await get_tutor_groups(tutor_id))

    if group_name in already:
        if group_name in removed_old:
            removed_old.discard(group_name)
        else:
            removed_old.add(group_name)
    else:
        if group_name in selected_new:
            selected_new.discard(group_name)
        else:
            selected_new.add(group_name)

    await state.update_data(assign_selected=list(selected_new), assign_removed=list(removed_old))
    await _render_group_picker(callback, tutor_id, course, selected_new, removed_old)
    await callback.answer()


@router.callback_query(AdminTutorState.picking_group, F.data.startswith("adm_grp_save:"))
async def save_group_assignments(callback: CallbackQuery, state: FSMContext):
    tutor_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    selected_new = set(data.get("assign_selected", []))
    removed_old = set(data.get("assign_removed", []))

    for g in selected_new:
        await assign_group_to_tutor(tutor_id, g)
    for g in removed_old:
        await remove_group_from_tutor(tutor_id, g)

    await state.clear()
    await callback.answer("✅ Guruhlar muvaffaqiyatli saqlandi!", show_alert=True)
    await view_tutor(callback, state)


# ── Tyutorni O'chirish ────────────────────────────────────

@router.callback_query(F.data.startswith("adm_del_tutor:"))
async def confirm_delete_tutor(callback: CallbackQuery):
    await callback.answer()
    tutor_id = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        "⚠️ <b>Haqiqatan ham ushbu tyutorni o'chirmoqchimisiz?</b>",
        parse_mode="HTML",
        reply_markup=get_tutor_delete_confirm_keyboard(tutor_id)
    )


@router.callback_query(F.data.startswith("adm_del_ok:"))
async def do_delete_tutor(callback: CallbackQuery, state: FSMContext):
    tutor_id = int(callback.data.split(":")[1])
    await delete_tutor(tutor_id)
    await callback.answer("✅ Tyutor o'chirildi!", show_alert=True)
    await back_to_tutors_list(callback, state)


# ── Yoqlamani Tahrirlash ──────────────────────────────────

@router.message(F.text == "✏️ Yoqlamani tahrirlash")
async def start_edit_attendance(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(AdminEditState.picking_date)
    await message.answer(
        "📅 <b>Qaysi sanadagi yoqlamani tahrirlamoqchisiz?</b>\n\n"
        "Formatda yozing: <code>25.03.2026</code>",
        parse_mode="HTML"
    )


@router.message(AdminEditState.picking_date)
async def process_edit_date(message: Message, state: FSMContext):
    text = message.text.strip()
    try:
        dt = datetime.strptime(text, "%d.%m.%Y")
    except ValueError:
        await message.answer("❌ Noto'g'ri sana formati! Masalan: <code>25.03.2026</code>", parse_mode="HTML")
        return

    paras = await get_paras_for_date(dt.date())
    if not paras:
        await message.answer(f"📭 <b>{text}</b> sanasida hech qanday yoqlama yozuvi topilmadi.", parse_mode="HTML")
        await state.clear()
        return

    await state.update_data(edit_date=dt.date().isoformat(), edit_date_str=text)

    builder = InlineKeyboardBuilder()
    for p in paras:
        builder.button(text=f"⏰ {p}-para", callback_data=f"admedit_p:{p}")
    builder.adjust(4)

    await state.set_state(AdminEditState.picking_para)
    await message.answer(f"📅 <b>{text}</b>\n⏰ Parani tanlang:", parse_mode="HTML", reply_markup=builder.as_markup())


@router.callback_query(AdminEditState.picking_para, F.data.startswith("admedit_p:"))
async def process_edit_para(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    para = int(callback.data.replace("admedit_p:", ""))
    data = await state.get_data()
    att_date = date.fromisoformat(data["edit_date"])

    groups = await get_groups_for_date_and_paras(att_date, [para])
    if not groups:
        await callback.message.edit_text("📭 Bu parada yoqlama qilingan guruhlar topilmadi.")
        await state.clear()
        return

    courses = groups_by_course(groups)
    await state.update_data(edit_para=para, edit_all_groups=groups)

    await state.set_state(AdminEditState.picking_groups)
    await callback.message.edit_text(
        "📚 <b>Tahrirlash uchun avval kursni tanlang:</b>",
        parse_mode="HTML",
        reply_markup=get_course_picker_keyboard(
            {course: len(items) for course, items in courses.items()},
            prefix="admedit_course",
        ),
    )


@router.callback_query(AdminEditState.picking_groups, F.data.startswith("admedit_course:"))
async def process_edit_course(callback: CallbackQuery, state: FSMContext):
    course = callback.data.replace("admedit_course:", "")
    data = await state.get_data()
    courses = groups_by_course(data.get("edit_all_groups", []))
    await callback.message.edit_text(
        f"👥 <b>{course}-kurs guruhini tanlang:</b>" if course != "other"
        else "👥 <b>Guruhni tanlang:</b>",
        parse_mode="HTML",
        reply_markup=get_groups_keyboard(
            courses.get(course, []), prefix="admedit_g", back_cb="admedit_courses"
        ),
    )
    await callback.answer()


@router.callback_query(AdminEditState.picking_groups, F.data == "admedit_courses")
async def back_to_edit_courses(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    courses = groups_by_course(data.get("edit_all_groups", []))
    await callback.message.edit_text(
        "📚 <b>Kursni tanlang:</b>",
        parse_mode="HTML",
        reply_markup=get_course_picker_keyboard(
            {course: len(items) for course, items in courses.items()},
            prefix="admedit_course",
        ),
    )
    await callback.answer()


@router.callback_query(AdminEditState.picking_groups, F.data.startswith("admedit_g:"))
async def process_edit_group(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    group_name = callback.data.replace("admedit_g:", "").replace("|", "/")
    data = await state.get_data()
    att_date = date.fromisoformat(data["edit_date"])
    para = data["edit_para"]

    students = await get_students_by_group(group_name)
    db_absent = await get_absent_students(group_name, para, att_date=att_date)

    await state.update_data(
        group=group_name,
        para=para,
        students=students,
        db_absent=[],
        new_absent=list(db_absent),
        edit_mode=True,
        page=0
    )
    await state.set_state(TutorAttendanceState.marking_absent)

    # Attendance interfeysini ko'rsatamiz
    keldi = max(0, len(students) - len(db_absent))
    kelmadi = len(db_absent)
    kb = get_attendance_students_keyboard(
        students=students,
        absent_set=set(db_absent),
        db_absent_set=set(),
        new_absent_set=set(db_absent),
        page=0,
        per_page=20,
        is_edit_mode=True
    )
    await callback.message.edit_text(
        f"👥 Guruh: <b>{group_name}</b> | ⏰ Para: <b>{para}</b>\n"
        f"📅 Sana: <b>{data.get('edit_date_str')}</b> <i>(Tahrirlash)</i>\n\n"
        f"✅ Kelgan: {keldi} | ❌ Kelmagan: {kelmadi}\n\n"
        f"<i>Kelmagan talabani bosing (❌ holatga keladi) va «💾 Saqlash» tugmasini bosing:</i>",
        parse_mode="HTML",
        reply_markup=kb
    )
