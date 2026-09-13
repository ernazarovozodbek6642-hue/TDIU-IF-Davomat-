import asyncio
import logging
from datetime import datetime, date
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from data.config import GOOGLE_CREDENTIALS
from data.constants import DAYS_UZ, ALL_GROUPS
from filters.role_filter import IsTutor
from states.states import TutorAttendanceState
from utils.db_api.db import (
    get_tutor, get_tutor_groups, get_students_by_group,
    get_absent_students, save_attendance, is_admin, get_spreadsheet_id,
)
from utils.group_courses import groups_by_course
from utils.sheets import update_sheets_attendance
from keyboards.inline.attendance import (
    get_course_picker_keyboard, get_groups_keyboard, get_paras_keyboard,
    get_attendance_students_keyboard
)

router = Router()
router.message.filter(IsTutor())
router.callback_query.filter(IsTutor())


async def _get_students_list(group_name: str) -> list[str]:
    """Bazadan talabalarni oladi"""
    students = await get_students_by_group(group_name)
    return sorted(students)


async def _show_attendance_interface(
    message: Message,
    state: FSMContext,
    edit: bool = False,
    page: int = 0
):
    data = await state.get_data()
    students = data.get("students", [])
    group = data.get("group", "")
    para = data.get("para", 1)
    is_edit_mode = data.get("edit_mode", False)
    edit_date_str = data.get("edit_date_str", "")

    db_absent = set(data.get("db_absent", []))
    new_absent = set(data.get("new_absent", []))
    all_absent = db_absent | new_absent

    keldi = max(0, len(students) - len(all_absent))
    kelmadi = len(all_absent)

    kb = get_attendance_students_keyboard(
        students=students,
        absent_set=all_absent,
        db_absent_set=db_absent,
        new_absent_set=new_absent,
        page=page,
        per_page=20,
        is_edit_mode=is_edit_mode
    )

    date_display = edit_date_str if is_edit_mode else datetime.now().strftime('%d.%m.%Y')
    edit_notice = "\n⚠️ <i>(Tahrirlash rejimi)</i>" if is_edit_mode else ""

    text = (
        f"👥 Guruh: <b>{group}</b> | ⏰ Para: <b>{para}</b>{edit_notice}\n"
        f"📅 Sana: <b>{date_display}</b>\n\n"
        f"✅ <b>Kelgan:</b> {keldi} nafar  |  ❌ <b>Kelmagan:</b> {kelmadi} nafar\n\n"
        f"<i>Kelmagan talabaning ustiga bosing (❌ belgilanadi):</i>"
    )

    if edit:
        try:
            await message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            pass
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.message(F.text == "📋 Yoqlama qilish")
async def start_attendance(message: Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id

    if await is_admin(uid):
        groups = ALL_GROUPS
        courses = groups_by_course(groups)
        await state.update_data(att_allowed_groups=groups)
        await state.set_state(TutorAttendanceState.picking_group)
        await message.answer(
            f"👋 <b>Admin yoqlama bo'limi</b>\n"
            f"📅 Sana: <b>{datetime.now().strftime('%d.%m.%Y')}</b>\n\n"
            f"📚 Avval kursni tanlang:",
            parse_mode="HTML",
            reply_markup=get_course_picker_keyboard(
                {course: len(items) for course, items in courses.items()},
                prefix="att_course",
            ),
        )
    else:
        tutor = await get_tutor(uid)
        if not tutor:
            await message.answer("❌ Siz tyutor sifatida ro'yxatdan o'tmagansiz!")
            return

        groups = await get_tutor_groups(tutor.id)
        if not groups:
            await message.answer(
                f"👋 Salom, <b>{tutor.name}</b>!\n\n"
                f"⚠️ Sizga hali guruh biriktirilmagan. Iltimos, adminga murojaat qiling.",
                parse_mode="HTML"
            )
            return

        courses = groups_by_course(groups)
        await state.update_data(att_allowed_groups=groups)
        await state.set_state(TutorAttendanceState.picking_group)
        await message.answer(
            f"👋 Salom, <b>{tutor.name}</b>!\n"
            f"📅 Sana: <b>{datetime.now().strftime('%d.%m.%Y')}</b>\n\n"
            f"📚 Avval kursni tanlang:",
            parse_mode="HTML",
            reply_markup=get_course_picker_keyboard(
                {course: len(items) for course, items in courses.items()},
                prefix="att_course",
            ),
        )


@router.callback_query(TutorAttendanceState.picking_group, F.data.startswith("att_course:"))
async def pick_attendance_course(callback: CallbackQuery, state: FSMContext):
    course = callback.data.replace("att_course:", "")
    data = await state.get_data()
    courses = groups_by_course(data.get("att_allowed_groups", []))
    await state.update_data(att_course=course)
    await callback.message.edit_text(
        f"👥 <b>{course}-kurs guruhini tanlang:</b>" if course != "other"
        else "👥 <b>Guruhni tanlang:</b>",
        parse_mode="HTML",
        reply_markup=get_groups_keyboard(
            courses.get(course, []), prefix="att_grp", back_cb="att_courses"
        ),
    )
    await callback.answer()


@router.callback_query(TutorAttendanceState.picking_group, F.data == "att_courses")
async def back_to_attendance_courses(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    courses = groups_by_course(data.get("att_allowed_groups", []))
    await callback.message.edit_text(
        "📚 <b>Kursni tanlang:</b>",
        parse_mode="HTML",
        reply_markup=get_course_picker_keyboard(
            {course: len(items) for course, items in courses.items()},
            prefix="att_course",
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("att_grp:"))
async def pick_group(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    group_name = callback.data.replace("att_grp:", "").replace("|", "/")
    uid = callback.from_user.id

    tutor_id = None
    if not await is_admin(uid):
        tutor = await get_tutor(uid)
        if tutor:
            tutor_id = tutor.id

    await state.update_data(group=group_name, tutor_id=tutor_id)

    # Bugungi Sheets dan faol paralarni olishga harakat qilamiz
    today = datetime.now()
    active_paras = ["1", "2", "3", "4", "5", "6", "7", "8"]

    try:
        import gspread
        from google.oauth2.service_account import Credentials
        creds = Credentials.from_service_account_file(
            GOOGLE_CREDENTIALS,
            scopes=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        )
        client = gspread.authorize(creds)
        sheet_name = f"{today.strftime('%d.%m')} {DAYS_UZ[today.weekday()]}"
        spreadsheet_id = await get_spreadsheet_id()
        sheet = client.open_by_key(spreadsheet_id).worksheet(sheet_name)
        vals = sheet.get_all_values()
        if len(vals) >= 2:
            headers = vals[1]
            g_idx = headers.index('Guruh')
            p_idx = headers.index('Juft-lik')
            found_paras = []
            for row in vals[2:]:
                if len(row) > g_idx and row[g_idx] == group_name:
                    p = row[p_idx].strip()
                    if p and p not in found_paras:
                        found_paras.append(p)
            if found_paras:
                active_paras = found_paras
    except Exception as e:
        logging.info(f"Sheets dan para olishda eslatma (standart paralar ishlatiladi): {e}")

    await callback.message.edit_text(
        f"👥 Guruh: <b>{group_name}</b>\n"
        f"📅 Sana: <b>{today.strftime('%d.%m.%Y')}</b>\n\n"
        f"⏰ <b>Dars juftligini (parani) tanlang:</b>",
        parse_mode="HTML",
        reply_markup=get_paras_keyboard(active_paras, prefix="att_para", back_cb="att_back_to_groups")
    )


@router.callback_query(F.data == "att_back_to_groups")
async def back_to_groups(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    groups = data.get("att_allowed_groups", [])
    course = data.get("att_course")
    if not groups:
        uid = callback.from_user.id
        if await is_admin(uid):
            groups = ALL_GROUPS
        else:
            tutor = await get_tutor(uid)
            groups = await get_tutor_groups(tutor.id) if tutor else []
        await state.update_data(att_allowed_groups=groups)
    courses = groups_by_course(groups)
    if not course:
        await callback.message.edit_text(
            "📚 <b>Kursni tanlang:</b>",
            parse_mode="HTML",
            reply_markup=get_course_picker_keyboard(
                {key: len(items) for key, items in courses.items()}, prefix="att_course"
            ),
        )
        return

    await callback.message.edit_text(
        f"👥 <b>{course}-kurs guruhini tanlang:</b>" if course != "other"
        else "👥 <b>Guruhni tanlang:</b>",
        parse_mode="HTML",
        reply_markup=get_groups_keyboard(
            courses.get(course, []), prefix="att_grp", back_cb="att_courses"
        ),
    )


@router.callback_query(F.data.startswith("att_para:"))
async def pick_para(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    para = int(callback.data.replace("att_para:", ""))
    data = await state.get_data()
    group_name = data.get("group")

    students = await _get_students_list(group_name)
    if not students:
        await callback.message.edit_text(
            f"⚠️ <b>{group_name}</b> guruhi uchun talabalar ro'yxati topilmadi.\n\n"
            f"Admin panel orqali talabalar ro'yxatini Excel formatda yuklang.",
            parse_mode="HTML"
        )
        return

    # Bugungi kunga DB da avval saqlangan kelmaganlar
    db_absent = await get_absent_students(group_name, para)

    await state.update_data(
        para=para,
        students=students,
        db_absent=list(db_absent),
        new_absent=[],
        page=0
    )
    await state.set_state(TutorAttendanceState.marking_absent)
    await _show_attendance_interface(callback.message, state, edit=True, page=0)


@router.callback_query(TutorAttendanceState.marking_absent, F.data.startswith("att_tog:"))
async def toggle_student(callback: CallbackQuery, state: FSMContext):
    student_short = callback.data.replace("att_tog:", "")
    data = await state.get_data()
    students = data.get("students", [])
    db_absent = set(data.get("db_absent", []))
    new_absent = set(data.get("new_absent", []))
    is_edit_mode = data.get("edit_mode", False)

    full_name = next((s for s in students if s[:30] == student_short), student_short)

    if not is_edit_mode and full_name in db_absent:
        await callback.answer("🔒 Bu talaba avval belgilangan va saqlangan!", show_alert=True)
        return

    if is_edit_mode:
        if full_name in new_absent:
            new_absent.discard(full_name)
        else:
            new_absent.add(full_name)
    else:
        if full_name in new_absent:
            new_absent.discard(full_name)
        else:
            new_absent.add(full_name)

    page = data.get("page", 0)
    await state.update_data(new_absent=list(new_absent))
    await callback.answer()
    await _show_attendance_interface(callback.message, state, edit=True, page=page)


@router.callback_query(TutorAttendanceState.marking_absent, F.data.startswith("att_page:"))
async def change_page(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    page = int(callback.data.replace("att_page:", ""))
    await state.update_data(page=page)
    await _show_attendance_interface(callback.message, state, edit=True, page=page)


@router.callback_query(F.data == "noop")
async def handle_noop(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(TutorAttendanceState.marking_absent, F.data == "att_all_present")
async def mark_all_present(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    group = data.get("group")
    para = data.get("para")
    tutor_id = data.get("tutor_id")
    students = data.get("students", [])
    is_edit_mode = data.get("edit_mode", False)

    att_date = None
    if is_edit_mode and data.get("edit_date"):
        att_date = date.fromisoformat(data["edit_date"])

    target_dt = datetime.combine(att_date, datetime.min.time()) if att_date else datetime.now()

    # DB ga bo'sh kelmaganlar bilan saqlaymiz (100% kelgan)
    await save_attendance(
        group_name=group,
        para=para,
        absent_students=[],
        tutor_id=tutor_id,
        att_date=att_date
    )

    # Google Sheets ga ham yangilaymiz
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None, update_sheets_attendance,
        group, para, [], target_dt, len(students), await get_spreadsheet_id()
    )

    await state.clear()
    await callback.message.edit_text(
        f"✅ <b>{group}</b> — {para}-para yoqlama muvaffaqiyatli saqlandi!\n\n"
        f"🎉 <b>100% to'liq qatnashish! Barcha talabalar darsda.</b>",
        parse_mode="HTML"
    )


@router.callback_query(TutorAttendanceState.marking_absent, F.data == "att_save")
async def save_attendance_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    group = data.get("group")
    para = data.get("para")
    tutor_id = data.get("tutor_id")
    students = data.get("students", [])
    is_edit_mode = data.get("edit_mode", False)

    db_absent = set(data.get("db_absent", []))
    new_absent = set(data.get("new_absent", []))
    all_absent = list(db_absent | new_absent) if not is_edit_mode else list(new_absent)

    att_date = None
    if is_edit_mode and data.get("edit_date"):
        att_date = date.fromisoformat(data["edit_date"])

    target_dt = datetime.combine(att_date, datetime.min.time()) if att_date else datetime.now()

    # DB ga saqlash
    await save_attendance(
        group_name=group,
        para=para,
        absent_students=all_absent,
        tutor_id=tutor_id,
        att_date=att_date
    )

    # Google Sheets ga saqlash
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None, update_sheets_attendance,
        group, para, all_absent, target_dt, len(students), await get_spreadsheet_id()
    )

    absent_text = "\n".join(f"  • {s}" for s in all_absent) if all_absent else "Barcha talabalar kelgan! 🎉"

    await state.clear()
    await callback.message.edit_text(
        f"✅ <b>{group}</b> — {para}-para yoqlama muvaffaqiyatli saqlandi!\n\n"
        f"👥 Jami talabalar: <b>{len(students)}</b> nafar\n"
        f"✅ Kelgan: <b>{len(students) - len(all_absent)}</b> nafar\n"
        f"❌ Kelmagan: <b>{len(all_absent)}</b> nafar\n\n"
        f"<b>Kelmaganlar ro'yxati:</b>\n{absent_text}",
        parse_mode="HTML"
    )


@router.callback_query(TutorAttendanceState.marking_absent, F.data == "att_back")
async def attendance_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await back_to_groups(callback, state)
