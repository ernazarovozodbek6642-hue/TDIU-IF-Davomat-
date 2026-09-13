from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.db_api.models import Tutor


def nav_row(back_cb: str | None = None) -> list[InlineKeyboardButton]:
    row = []
    if back_cb:
        row.append(InlineKeyboardButton(text="↩️ Ortga", callback_data=back_cb))
    row.append(InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="go_home"))
    return row


def get_tutors_list_keyboard(tutors: list[Tutor]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for t in tutors:
        builder.button(text=f"👤 {t.name}", callback_data=f"adm_tutor:{t.id}")
    builder.button(text="➕ Yangi tyutor qo'shish", callback_data="adm_add_tutor")
    builder.adjust(1)
    builder.row(*nav_row())
    return builder.as_markup()


def get_tutor_detail_keyboard(tutor_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📎 Guruhlarni biriktirish / o'chirish", callback_data=f"adm_assign:{tutor_id}")
    builder.button(text="❌ Tyutorni o'chirish", callback_data=f"adm_del_tutor:{tutor_id}")
    builder.adjust(1)
    builder.row(*nav_row(back_cb="adm_back_tutors"))
    return builder.as_markup()


def get_tutor_delete_confirm_keyboard(tutor_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Ha, o'chirilsin", callback_data=f"adm_del_ok:{tutor_id}")
    builder.button(text="❌ Bekor qilish", callback_data=f"adm_tutor:{tutor_id}")
    builder.adjust(2)
    builder.row(*nav_row(back_cb=f"adm_tutor:{tutor_id}"))
    return builder.as_markup()


def get_assignment_courses_keyboard(
    tutor_id: int,
    course_counts: dict[str, int],
    pending_changes: int = 0,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    course_icons = {"1": "1️⃣", "2": "2️⃣", "3": "3️⃣", "4": "4️⃣"}
    for course in ("1", "2", "3", "4"):
        count = course_counts.get(course, 0)
        builder.button(
            text=f"{course_icons[course]} {course}-kurs ({count})",
            callback_data=f"adm_grp_course:{tutor_id}:{course}",
        )
    builder.adjust(2)
    save_text = "💾 Saqlash"
    if pending_changes:
        save_text += f" ({pending_changes})"
    builder.row(
        InlineKeyboardButton(text=save_text, callback_data=f"adm_grp_save:{tutor_id}")
    )
    builder.row(*nav_row(back_cb=f"adm_tutor:{tutor_id}"))
    return builder.as_markup()


def get_group_picker_keyboard(
    tutor_id: int,
    all_groups: list[str],
    already_assigned: set[str],
    selected_new: set[str],
    removed_old: set[str],
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for g in sorted(all_groups):
        if g in already_assigned and g not in removed_old:
            icon = "✅"
        elif g in selected_new:
            icon = "☑️"
        else:
            icon = "⬜"

        safe_g = g.replace("/", "|")
        builder.button(text=f"{icon} {g}", callback_data=f"adm_grp_tog:{tutor_id}:{safe_g}")

    builder.adjust(3)
    builder.row(
        InlineKeyboardButton(text="💾 Saqlash", callback_data=f"adm_grp_save:{tutor_id}"),
    )
    builder.row(*nav_row(back_cb=f"adm_grp_courses:{tutor_id}"))
    return builder.as_markup()
