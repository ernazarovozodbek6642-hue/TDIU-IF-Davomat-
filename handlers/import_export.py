import io
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext

from filters.role_filter import IsAdmin
from states.states import ImportExportState
from keyboards.inline.import_export import get_import_export_menu
from keyboards.inline.attendance import get_course_picker_keyboard, get_groups_keyboard
from data.edupage_catalog import TIMETABLE_NUM
from utils.group_courses import groups_by_course
from utils.db_api.db import (
    get_all_students, bulk_import_students, replace_all_students, replace_group_students,
    get_all_tutors, get_tutor_groups, add_tutor, assign_group_to_tutor,
    get_all_subject_kafedras, bulk_import_subject_kafedras,
    get_all_edupage_groups, bulk_import_edupage_groups
)
from utils.excel_manager import (
    export_students_excel, export_tutors_excel, export_kafedra_map_excel, export_edupage_groups_excel,
    parse_students_excel, parse_single_group_students_excel,
    parse_tutors_excel, parse_kafedra_map_excel, parse_edupage_groups_excel,
    generate_student_template, generate_single_group_template,
    generate_tutor_template, generate_kafedra_template, generate_edupage_groups_template
)

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.message(F.text == "📥 Import / Export (Excel)")
async def import_export_main(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "📥 <b>Excel orqali Ma'lumotlarni Boshqarish:</b>\n\n"
        "Quyidagi amallardan birini tanlang:",
        parse_mode="HTML",
        reply_markup=get_import_export_menu()
    )


# ── Shablonlar ────────────────────────────────────────────

@router.callback_query(F.data == "ie_get_templates")
async def send_templates(callback: CallbackQuery):
    await callback.answer()
    stu_bytes = generate_student_template()
    grp_bytes = generate_single_group_template("I-50_24")
    tut_bytes = generate_tutor_template()
    kaf_bytes = generate_kafedra_template(await get_all_subject_kafedras())
    edu_bytes = generate_edupage_groups_template()

    await callback.message.answer_document(
        BufferedInputFile(stu_bytes, filename="Barcha_Talabalar_Shablon.xlsx"),
        caption="📄 <b>Barcha talabalarni yuklash shabloni</b> (Guruh + F.I.Sh)",
        parse_mode="HTML"
    )
    await callback.message.answer_document(
        BufferedInputFile(grp_bytes, filename="Bitta_Guruh_Shabloni.xlsx"),
        caption="📄 <b>Aynan bitta guruh talabalarini yangilash shabloni</b>",
        parse_mode="HTML"
    )
    await callback.message.answer_document(
        BufferedInputFile(tut_bytes, filename="Tyutorlar_Shablon.xlsx"),
        caption="📄 <b>Tyutorlar ro'yxatini yuklash shabloni</b>",
        parse_mode="HTML"
    )
    await callback.message.answer_document(
        BufferedInputFile(kaf_bytes, filename="Fanlar_va_Kafedralar_Shablon.xlsx"),
        caption="📄 <b>Fanlar va Kafedralar shabloni</b>\nFanlar ro‘yxati tayyor. Har bir fan yonidagi «Tegishli Kafedra» ustunini to‘ldiring.",
        parse_mode="HTML"
    )
    await callback.message.answer_document(
        BufferedInputFile(edu_bytes, filename="Edupage_Guruhlar_Shabloni.xlsx"),
        caption="📄 <b>EduPage Guruhlari xaritasi shabloni</b> (ID | Guruh | Kurs)",
        parse_mode="HTML"
    )


# ── Talabalarni Export Qilish ─────────────────────────────

@router.callback_query(F.data == "ie_export_students")
async def export_students_handler(callback: CallbackQuery):
    await callback.answer()
    students = await get_all_students()
    if not students:
        await callback.message.answer("📭 Bazada talabalar mavjud emas.")
        return

    excel_bytes = export_students_excel(students)
    await callback.message.answer_document(
        BufferedInputFile(excel_bytes, filename="Talabalar_Royxati.xlsx"),
        caption=f"📤 <b>Barcha talabalar ro'yxati</b>\nJami: <b>{len(students)}</b> nafar talaba",
        parse_mode="HTML"
    )


# ── Tyutorlarni Export Qilish ──────────────────────────────

@router.callback_query(F.data == "ie_export_tutors")
async def export_tutors_handler(callback: CallbackQuery):
    await callback.answer()
    tutors = await get_all_tutors()
    if not tutors:
        await callback.message.answer("📭 Bazada tyutorlar mavjud emas.")
        return

    tutors_with_groups = []
    for t in tutors:
        grps = await get_tutor_groups(t.id)
        tutors_with_groups.append((t, grps))

    excel_bytes = export_tutors_excel(tutors_with_groups)
    await callback.message.answer_document(
        BufferedInputFile(excel_bytes, filename="Tyutorlar_Royxati.xlsx"),
        caption=f"📤 <b>Barcha tyutorlar ro'yxati</b>\nJami: <b>{len(tutors)}</b> nafar tyutor",
        parse_mode="HTML"
    )


# ── Fanlar & Kafedralarni Export Qilish ────────────────────

@router.callback_query(F.data == "ie_export_kafedras")
async def export_kafedras_handler(callback: CallbackQuery):
    await callback.answer()
    items = await get_all_subject_kafedras()
    if not items:
        from data.constants import KAFEDRA_MAP
        from utils.db_api.models import SubjectKafedra
        items = [SubjectKafedra(subject_name=k, kafedra_name=v) for k, v in KAFEDRA_MAP.items()]

    excel_bytes = export_kafedra_map_excel(items)
    await callback.message.answer_document(
        BufferedInputFile(excel_bytes, filename="Fanlar_va_Kafedralar.xlsx"),
        caption=f"📤 <b>Fanlar va Kafedralar xaritasi</b>\nJami: <b>{len(items)}</b> ta fan biriktirilgan",
        parse_mode="HTML"
    )


# ── EduPage Guruhlarni Export Qilish ───────────────────────

@router.callback_query(F.data == "ie_export_edupage")
async def export_edupage_groups_handler(callback: CallbackQuery):
    await callback.answer()
    groups = await get_all_edupage_groups()
    if not groups:
        from data.constants import ID_TO_NAME, get_kurs
        from utils.db_api.models import EdupageGroup
        groups = []
        for gid, gname in ID_TO_NAME.items():
            kurs = get_kurs(gid) or "1-kurs"
            num_p = TIMETABLE_NUM
            groups.append(EdupageGroup(edupage_id=gid, group_name=gname, kurs=kurs, num_param=num_p))

    excel_bytes = export_edupage_groups_excel(groups)
    await callback.message.answer_document(
        BufferedInputFile(excel_bytes, filename="Edupage_Guruhlar_Xaritasi.xlsx"),
        caption=f"📤 <b>EduPage Guruhlari xaritasi</b>\nJami: <b>{len(groups)}</b> ta guruh",
        parse_mode="HTML"
    )


# ── Barcha Talabalarni Qo'shish (Smart Merge) ─────────────

@router.callback_query(F.data == "ie_import_students")
async def ask_student_file(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ImportExportState.waiting_student_file)
    await callback.message.answer(
        "📥 <b>Yangi talabalar ro'yxati yozilgan Excel (.xlsx) faylni yuboring:</b>\n\n"
        "<i>(Mavjud talabalar saqlanadi, faqat yangilari qo'shiladi)</i>\n"
        "Ustunlar: «Guruh» va «Talaba F.I.Sh.»",
        parse_mode="HTML"
    )


@router.message(ImportExportState.waiting_student_file, F.document)
async def process_student_file(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    if not doc.file_name.endswith((".xlsx", ".xls")):
        await message.answer("❌ Faqat Excel (.xlsx yoki .xls) formatdagi fayl yuboring!")
        return

    msg_wait = await message.answer("⏳ Fayl yuklanmoqda va qayta ishlanmoqda...")
    try:
        file_io = io.BytesIO()
        await bot.download(doc, destination=file_io)
        file_bytes = file_io.getvalue()

        parsed = parse_students_excel(file_bytes)
        if not parsed:
            await msg_wait.edit_text("❌ Fayldan talaba ma'lumotlari topilmadi. Shablon formatini tekshiring.")
            return

        added_count = await bulk_import_students(parsed)
        await state.clear()
        await msg_wait.edit_text(
            f"✅ <b>Yangi talabalar muvaffaqiyatli qo'shildi!</b>\n\n"
            f"📄 Fayldan o'qildi: <b>{len(parsed)}</b> ta talaba\n"
            f"📥 Bazaga yangi qo'shilgan: <b>{added_count}</b> ta",
            parse_mode="HTML"
        )
    except Exception as e:
        await msg_wait.edit_text(f"❌ Faylni o'qishda xatolik yuz berdi:\n<code>{e}</code>", parse_mode="HTML")


# ── Butun Fakultet Talabalarini To'liq Almashtirish ───────

@router.callback_query(F.data == "ie_replace_all_students")
async def ask_replace_all_students_file(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ImportExportState.waiting_replace_all_students_file)
    await callback.message.answer(
        "⚠️ <b>DIQQAT: Butun fakultet talabalar bazasini to'liq almashtirish!</b>\n\n"
        "Ushbu amal barcha guruhlardagi mavjud talabalar ro'yxatini tozalab, "
        "yuborilgan yangi Excel fayldagi talabalar bilan 100% almashtiradi.\n"
        "<i>(O'tgan kunlardagi davomat tarixiga tegilmaydi)</i>\n\n"
        "📥 <b>Barcha guruhlarning to'liq yangi ro'yxati yozilgan Excel (.xlsx) faylini yuboring:</b>",
        parse_mode="HTML"
    )


@router.message(ImportExportState.waiting_replace_all_students_file, F.document)
async def process_replace_all_students_file(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    if not doc.file_name.endswith((".xlsx", ".xls")):
        await message.answer("❌ Faqat Excel (.xlsx yoki .xls) formatdagi fayl yuboring!")
        return

    msg_wait = await message.answer("⏳ Butun fakultet talabalar bazasi yangilanmoqda...")
    try:
        file_io = io.BytesIO()
        await bot.download(doc, destination=file_io)
        file_bytes = file_io.getvalue()

        parsed = parse_students_excel(file_bytes)
        if not parsed:
            await msg_wait.edit_text("❌ Fayldan talaba ma'lumotlari topilmadi. Shablon formatini tekshiring.")
            return

        total_count = await replace_all_students(parsed)
        await state.clear()
        await msg_wait.edit_text(
            f"✅ <b>Fakultet talabalar bazasi to'liq yangilandi!</b>\n\n"
            f"👥 Bazadagi jami yangi talabalar soni: <b>{total_count}</b> nafar",
            parse_mode="HTML"
        )
    except Exception as e:
        await msg_wait.edit_text(f"❌ Xatolik yuz berdi:\n<code>{e}</code>", parse_mode="HTML")


# ── Guruh bo'yicha Talabalarni Yangilash ───────────────────

@router.callback_query(F.data == "ie_import_single_group")
async def start_single_group_import(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    groups = [group.group_name for group in await get_all_edupage_groups()]
    courses = groups_by_course(groups)
    await state.update_data(single_import_groups=groups)
    await state.set_state(ImportExportState.waiting_single_group_select)
    await callback.message.edit_text(
        "🔄 <b>Qaysi guruh talabalarini yangilamoqchisiz?</b>\n\n"
        "<i>Avval kursni tanlang:</i>",
        parse_mode="HTML",
        reply_markup=get_course_picker_keyboard(
            {course: len(items) for course, items in courses.items()},
            prefix="ie_course",
        ),
    )


@router.callback_query(
    ImportExportState.waiting_single_group_select,
    F.data.startswith("ie_course:"),
)
async def pick_course_for_single_group_import(callback: CallbackQuery, state: FSMContext):
    course = callback.data.replace("ie_course:", "")
    data = await state.get_data()
    courses = groups_by_course(data.get("single_import_groups", []))
    await callback.message.edit_text(
        f"👥 <b>{course}-kurs guruhini tanlang:</b>" if course != "other"
        else "👥 <b>Guruhni tanlang:</b>",
        parse_mode="HTML",
        reply_markup=get_groups_keyboard(
            courses.get(course, []), prefix="ie_grp", back_cb="ie_courses"
        ),
    )
    await callback.answer()


@router.callback_query(
    ImportExportState.waiting_single_group_select,
    F.data == "ie_courses",
)
async def back_to_single_import_courses(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    courses = groups_by_course(data.get("single_import_groups", []))
    await callback.message.edit_text(
        "📚 <b>Kursni tanlang:</b>",
        parse_mode="HTML",
        reply_markup=get_course_picker_keyboard(
            {course: len(items) for course, items in courses.items()},
            prefix="ie_course",
        ),
    )
    await callback.answer()


@router.callback_query(ImportExportState.waiting_single_group_select, F.data.startswith("ie_grp:"))
async def pick_group_for_import(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    group_name = callback.data.replace("ie_grp:", "").replace("|", "/")
    await state.update_data(target_group_import=group_name)
    await state.set_state(ImportExportState.waiting_single_group_file)

    await callback.message.edit_text(
        f"👥 Guruh: <b>{group_name}</b>\n\n"
        f"📥 Endi ushbu guruhning talabalar ro'yxati yozilgan Excel (.xlsx) faylini yuboring.\n"
        f"<i>(Ushbu guruhning eski talabalari o'rniga yangi yuborilgan talabalar yoziladi)</i>",
        parse_mode="HTML"
    )


@router.message(ImportExportState.waiting_single_group_file, F.document)
async def process_single_group_file(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    if not doc.file_name.endswith((".xlsx", ".xls")):
        await message.answer("❌ Faqat Excel (.xlsx yoki .xls) formatdagi fayl yuboring!")
        return

    data = await state.get_data()
    group_name = data.get("target_group_import")
    msg_wait = await message.answer(f"⏳ <b>{group_name}</b> guruhi talabalari yangilanmoqda...")

    try:
        file_io = io.BytesIO()
        await bot.download(doc, destination=file_io)
        file_bytes = file_io.getvalue()

        names = parse_single_group_students_excel(file_bytes, group_name)
        if not names:
            await msg_wait.edit_text("❌ Fayldan talabalar ismi topilmadi. Shablon formatini tekshiring.")
            return

        updated_count = await replace_group_students(group_name, names)
        await state.clear()
        await msg_wait.edit_text(
            f"✅ <b>{group_name}</b> guruhi talabalar ro'yxati muvaffaqiyatli yangilandi!\n\n"
            f"👥 Jami yangi talabalar soni: <b>{updated_count}</b> nafar",
            parse_mode="HTML"
        )
    except Exception as e:
        await msg_wait.edit_text(f"❌ Xatolik yuz berdi:\n<code>{e}</code>", parse_mode="HTML")


# ── Tyutorlarni Import Qilish ──────────────────────────────

@router.callback_query(F.data == "ie_import_tutors")
async def ask_tutor_file(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ImportExportState.waiting_tutor_file)
    await callback.message.answer(
        "📥 <b>Tyutorlar ro'yxati yozilgan Excel (.xlsx) faylni yuboring:</b>\n\n"
        "<i>Eslatma: Faylda [Telegram ID | Tyutor F.I.Sh. | Guruhlar] ustunlari bo'lishi kerak.</i>",
        parse_mode="HTML"
    )


@router.message(ImportExportState.waiting_tutor_file, F.document)
async def process_tutor_file(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    if not doc.file_name.endswith((".xlsx", ".xls")):
        await message.answer("❌ Faqat Excel (.xlsx yoki .xls) formatdagi fayl yuboring!")
        return

    msg_wait = await message.answer("⏳ Fayl yuklanmoqda va qayta ishlanmoqda...")
    try:
        file_io = io.BytesIO()
        await bot.download(doc, destination=file_io)
        file_bytes = file_io.getvalue()

        parsed = parse_tutors_excel(file_bytes)
        if not parsed:
            await msg_wait.edit_text("❌ Fayldan tyutor ma'lumotlari topilmadi. Shablon formatini tekshiring.")
            return

        added_tutors = 0
        assigned_groups = 0
        for tg_id, name, grps in parsed:
            tutor = await add_tutor(tg_id, name)
            added_tutors += 1
            for g in grps:
                await assign_group_to_tutor(tutor.id, g)
                assigned_groups += 1

        await state.clear()
        await msg_wait.edit_text(
            f"✅ <b>Tyutorlar importi muvaffaqiyatli yakunlandi!</b>\n\n"
            f"👤 Qo'shilgan/yangilangan tyutorlar: <b>{added_tutors}</b> nafar\n"
            f"📚 Biriktirilgan guruhlar: <b>{assigned_groups}</b> ta",
            parse_mode="HTML"
        )
    except Exception as e:
        await msg_wait.edit_text(f"❌ Faylni o'qishda xatolik yuz berdi:\n<code>{e}</code>", parse_mode="HTML")


# ── EduPage Guruhlarni Import Qilish ───────────────────────

@router.callback_query(F.data == "ie_import_edupage")
async def ask_edupage_group_file(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ImportExportState.waiting_edupage_group_file)
    await callback.message.answer(
        "📥 <b>EduPage Guruhlari ro'yxati yozilgan Excel (.xlsx) faylni yuboring:</b>\n\n"
        "<i>Eslatma: Faylda [EduPage ID | Guruh nomi | Kursi] ustunlari bo'lishi kerak.</i>",
        parse_mode="HTML"
    )


@router.message(ImportExportState.waiting_edupage_group_file, F.document)
async def process_edupage_group_file(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    if not doc.file_name.endswith((".xlsx", ".xls")):
        await message.answer("❌ Faqat Excel (.xlsx yoki .xls) formatdagi fayl yuboring!")
        return

    msg_wait = await message.answer("⏳ EduPage guruhlar xaritasi yangilanmoqda...")
    try:
        file_io = io.BytesIO()
        await bot.download(doc, destination=file_io)
        file_bytes = file_io.getvalue()

        parsed = parse_edupage_groups_excel(file_bytes)
        if not parsed:
            await msg_wait.edit_text("❌ Fayldan guruh ma'lumotlari topilmadi. Shablon formatini tekshiring.")
            return

        count = await bulk_import_edupage_groups(parsed)
        await state.clear()
        await msg_wait.edit_text(
            f"✅ <b>EduPage Guruhlari xaritasi muvaffaqiyatli saqlandi!</b>\n\n"
            f"🏫 Jami saqlangan/yangilangan guruhlar: <b>{count}</b> ta",
            parse_mode="HTML"
        )
    except Exception as e:
        await msg_wait.edit_text(f"❌ Faylni o'qishda xatolik yuz berdi:\n<code>{e}</code>", parse_mode="HTML")


# ── Fanlar & Kafedralarni Import Qilish ────────────────────

@router.callback_query(F.data == "ie_import_kafedras")
async def ask_kafedra_file(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ImportExportState.waiting_kafedra_file)
    template = generate_kafedra_template(await get_all_subject_kafedras())
    await callback.message.answer_document(
        BufferedInputFile(template, filename='Fanlar_va_Kafedralar_Shablon.xlsx'),
        caption="📥 <b>Fanlar ro‘yxati shablonda tayyor.</b>\n\n"
        "«Tegishli Kafedra» ustunini to‘ldirib, shu Excel faylni qayta yuboring. "
        "Kafedrasi bo‘sh qoldirilgan qatorlar import qilinmaydi.",
        parse_mode="HTML"
    )


@router.message(ImportExportState.waiting_kafedra_file, F.document)
async def process_kafedra_file(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    if not doc.file_name.endswith((".xlsx", ".xls")):
        await message.answer("❌ Faqat Excel (.xlsx yoki .xls) formatdagi fayl yuboring!")
        return

    msg_wait = await message.answer("⏳ Fanlar va Kafedralar xaritasi yangilanmoqda...")
    try:
        file_io = io.BytesIO()
        await bot.download(doc, destination=file_io)
        file_bytes = file_io.getvalue()

        parsed = parse_kafedra_map_excel(file_bytes)
        if not parsed:
            await msg_wait.edit_text("❌ Fayldan fan va kafedra ma'lumotlari topilmadi. Shablon formatini tekshiring.")
            return

        count = await bulk_import_subject_kafedras(parsed)
        await state.clear()
        await msg_wait.edit_text(
            f"✅ <b>Fanlar va Kafedralar muvaffaqiyatli saqlandi!</b>\n\n"
            f"📚 Jami saqlangan/yangilangan fanlar: <b>{count}</b> ta",
            parse_mode="HTML"
        )
    except Exception as e:
        await msg_wait.edit_text(f"❌ Faylni o'qishda xatolik yuz berdi:\n<code>{e}</code>", parse_mode="HTML")
