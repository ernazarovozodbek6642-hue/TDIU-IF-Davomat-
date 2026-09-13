from datetime import date
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from filters.role_filter import IsAdmin
from states.states import AdminHistState
from keyboards.inline.history import (
    get_history_dates_keyboard, get_history_paras_keyboard, get_history_groups_keyboard
)
from keyboards.inline.attendance import get_course_picker_keyboard
from utils.db_api.db import (
    Session as DbSession, get_attendance_dates, get_paras_for_date,
    get_groups_for_date_and_paras, get_students_by_group
)
from utils.db_api.models import Attendance, AttendanceSession
from utils.excel_manager import generate_attendance_history_excel
from utils.group_courses import groups_by_course

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.message(F.text == "📊 Yoqlamalar tarixi")
async def history_start(message: Message, state: FSMContext):
    await state.clear()
    dates = await get_attendance_dates(limit=14)
    if not dates:
        await message.answer("📭 Hali hech qanday yoqlama yozuvi mavjud emas.")
        return

    await message.answer(
        "📅 <b>Qaysi sanadagi yoqlamani ko'rmoqchisiz?</b>",
        parse_mode="HTML",
        reply_markup=get_history_dates_keyboard(dates)
    )


@router.callback_query(F.data.startswith("hdate:"))
async def history_pick_date(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    date_str = callback.data.replace("hdate:", "")
    d = date.fromisoformat(date_str)

    paras = await get_paras_for_date(d)
    if not paras:
        await callback.message.edit_text(f"📭 {d.strftime('%d.%m.%Y')} da yoqlama topilmadi.")
        await state.clear()
        return

    await state.update_data(hist_date=date_str, hist_all_paras=paras, hist_paras=[])
    await state.set_state(AdminHistState.picking_paras)

    await callback.message.edit_text(
        f"📅 <b>{d.strftime('%d.%m.%Y')}</b>\n"
        f"⏰ <b>Qaysi paralarni hisobotga kiritmoqchisiz?</b>\n"
        f"<i>(Bir yoki bir nechtasini tanlang):</i>",
        parse_mode="HTML",
        reply_markup=get_history_paras_keyboard(paras, [])
    )


@router.callback_query(AdminHistState.picking_paras, F.data.startswith("hpara:"))
async def history_toggle_para(callback: CallbackQuery, state: FSMContext):
    val = callback.data.replace("hpara:", "")
    data = await state.get_data()
    all_paras = data.get("hist_all_paras", [])
    selected = list(data.get("hist_paras", []))

    if val == "all":
        selected = list(all_paras) if len(selected) != len(all_paras) else []
    else:
        p_int = int(val)
        if p_int in selected:
            selected.remove(p_int)
        else:
            selected.append(p_int)

    await state.update_data(hist_paras=selected)
    await callback.answer()
    try:
        await callback.message.edit_reply_markup(
            reply_markup=get_history_paras_keyboard(all_paras, selected)
        )
    except Exception:
        pass


@router.callback_query(AdminHistState.picking_paras, F.data == "hpara_back")
async def history_back_to_dates(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    dates = await get_attendance_dates(limit=14)
    await callback.message.edit_text(
        "📅 <b>Sanani tanlang:</b>",
        parse_mode="HTML",
        reply_markup=get_history_dates_keyboard(dates)
    )


@router.callback_query(AdminHistState.picking_paras, F.data == "hpara_done")
async def history_paras_done(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    selected_paras = data.get("hist_paras", [])
    if not selected_paras:
        await callback.answer("⚠️ Iltimos, kamida 1 ta parani tanlang!", show_alert=True)
        return

    date_str = data.get("hist_date")
    d = date.fromisoformat(date_str)
    groups = await get_groups_for_date_and_paras(d, selected_paras)

    if not groups:
        await callback.message.edit_text("📭 Tanlangan paralarda guruhlar topilmadi.")
        await state.clear()
        return

    await state.update_data(hist_all_groups=groups, hist_groups=[])
    await state.set_state(AdminHistState.picking_groups)
    courses = groups_by_course(groups)
    await callback.message.edit_text(
        "📚 <b>Qaysi kurs guruhlari hisoboti kerak?</b>\n"
        "<i>Avval kursni tanlang:</i>",
        parse_mode="HTML",
        reply_markup=get_course_picker_keyboard(
            {course: len(items) for course, items in courses.items()},
            prefix="hcourse",
            back_cb="hgrp_back",
            action_cb="h_export_excel",
            action_text="📥 Excel hisobotni yuklash",
        ),
    )


@router.callback_query(AdminHistState.picking_groups, F.data.startswith("hcourse:"))
async def history_pick_course(callback: CallbackQuery, state: FSMContext):
    course = callback.data.replace("hcourse:", "")
    data = await state.get_data()
    courses = groups_by_course(data.get("hist_all_groups", []))
    await state.update_data(hist_course=course)
    await callback.message.edit_text(
        f"👥 <b>{course}-kurs guruhlarini tanlang:</b>" if course != "other"
        else "👥 <b>Guruhlarni tanlang:</b>",
        parse_mode="HTML",
        reply_markup=get_history_groups_keyboard(
            courses.get(course, []),
            data.get("hist_groups", []),
            back_cb="hgrp_courses",
        ),
    )
    await callback.answer()


@router.callback_query(AdminHistState.picking_groups, F.data == "hgrp_courses")
async def history_back_to_courses(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    courses = groups_by_course(data.get("hist_all_groups", []))
    selected_count = len(data.get("hist_groups", []))
    action_text = "📥 Excel hisobotni yuklash"
    if selected_count:
        action_text += f" ({selected_count})"
    await callback.message.edit_text(
        "📚 <b>Kursni tanlang:</b>",
        parse_mode="HTML",
        reply_markup=get_course_picker_keyboard(
            {course: len(items) for course, items in courses.items()},
            prefix="hcourse",
            back_cb="hgrp_back",
            action_cb="h_export_excel",
            action_text=action_text,
        ),
    )
    await callback.answer()


@router.callback_query(AdminHistState.picking_groups, F.data.startswith("hgrp:"))
async def history_toggle_group(callback: CallbackQuery, state: FSMContext):
    val = callback.data.replace("hgrp:", "").replace("|", "/")
    data = await state.get_data()
    all_groups = data.get("hist_all_groups", [])
    selected = list(data.get("hist_groups", []))
    course = data.get("hist_course", "1")
    courses = groups_by_course(all_groups)
    visible_groups = courses.get(course, [])

    if val == "all":
        if visible_groups and set(visible_groups).issubset(selected):
            selected = [group for group in selected if group not in visible_groups]
        else:
            selected = list(dict.fromkeys(selected + visible_groups))
    else:
        if val in selected:
            selected.remove(val)
        else:
            selected.append(val)

    await state.update_data(hist_groups=selected)
    await callback.answer()
    try:
        await callback.message.edit_reply_markup(
            reply_markup=get_history_groups_keyboard(
                visible_groups, selected, back_cb="hgrp_courses"
            )
        )
    except Exception:
        pass


@router.callback_query(AdminHistState.picking_groups, F.data == "hgrp_back")
async def history_back_to_paras(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    all_paras = data.get("hist_all_paras", [])
    selected_paras = data.get("hist_paras", [])
    d = date.fromisoformat(data.get("hist_date"))

    await state.set_state(AdminHistState.picking_paras)
    await callback.message.edit_text(
        f"📅 <b>{d.strftime('%d.%m.%Y')}</b>\n⏰ <b>Paralarni tanlang:</b>",
        parse_mode="HTML",
        reply_markup=get_history_paras_keyboard(all_paras, selected_paras)
    )


@router.callback_query(AdminHistState.picking_groups, F.data == "h_export_excel")
async def export_history_excel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    d = date.fromisoformat(data.get("hist_date"))
    selected_paras = data.get("hist_paras", [])
    selected_groups = data.get("hist_groups", [])
    if not selected_groups:
        selected_groups = data.get("hist_all_groups", [])

    msg_wait = await callback.message.answer("⏳ Excel hisobot tayyorlanmoqda...")

    async with DbSession() as s:
        # Kelmaganlar
        res = await s.execute(
            select(Attendance).where(
                Attendance.date == d,
                Attendance.para.in_(selected_paras),
                Attendance.group_name.in_(selected_groups)
            ).order_by(Attendance.group_name, Attendance.para, Attendance.student_name)
        )
        records = list(res.scalars().all())

        # 100% sessiyalar
        res_sess = await s.execute(
            select(AttendanceSession).where(
                AttendanceSession.date == d,
                AttendanceSession.para.in_(selected_paras),
                AttendanceSession.group_name.in_(selected_groups),
                AttendanceSession.all_present == True
            )
        )
        all_present_sessions = {(row.group_name, row.para) for row in res_sess.scalars().all()}

    # Har bir guruh talabalar soni
    group_student_counts = {}
    for g in selected_groups:
        stus = await get_students_by_group(g)
        group_student_counts[g] = len(stus)

    excel_bytes = generate_attendance_history_excel(
        att_date=d,
        paras=selected_paras,
        records=records,
        all_present_sessions=all_present_sessions,
        group_student_counts=group_student_counts
    )

    fname = f"yoqlama_{d.strftime('%d.%m.%Y')}.xlsx"
    await callback.message.answer_document(
        BufferedInputFile(excel_bytes, filename=fname),
        caption=(
            f"📊 <b>{d.strftime('%d.%m.%Y')} kunlik yoqlama hisoboti</b>\n\n"
            f"⏰ Paralar: <b>{', '.join(f'{p}-para' for p in sorted(selected_paras))}</b>\n"
            f"👥 Guruhlar soni: <b>{len(selected_groups)}</b> ta\n"
            f"❌ Jami kelmaganlar yozuvi: <b>{len(records)}</b> ta"
        ),
        parse_mode="HTML"
    )
    await msg_wait.delete()
    await state.clear()
