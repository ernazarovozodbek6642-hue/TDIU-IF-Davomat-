from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def nav_row(back_cb: str | None = None) -> list[InlineKeyboardButton]:
    """Har bir sahifaning pastida 'Ortga' va 'Bosh menyu' tugmalari"""
    row = []
    if back_cb:
        row.append(InlineKeyboardButton(text="↩️ Ortga", callback_data=back_cb))
    row.append(InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="go_home"))
    return row


def get_course_picker_keyboard(
    course_counts: dict[str, int],
    prefix: str,
    back_cb: str | None = None,
    action_cb: str | None = None,
    action_text: str | None = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    icons = {"1": "1️⃣", "2": "2️⃣", "3": "3️⃣", "4": "4️⃣", "other": "📁"}
    labels = {"other": "Boshqa"}
    for course in ("1", "2", "3", "4", "other"):
        count = course_counts.get(course, 0)
        if not count:
            continue
        label = labels.get(course, f"{course}-kurs")
        builder.button(
            text=f"{icons[course]} {label} ({count})",
            callback_data=f"{prefix}:{course}",
        )
    builder.adjust(2)
    if action_cb and action_text:
        builder.row(InlineKeyboardButton(text=action_text, callback_data=action_cb))
    builder.row(*nav_row(back_cb=back_cb))
    return builder.as_markup()


def get_groups_keyboard(groups: list[str], prefix: str = "tutor_grp", back_cb: str | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for g in sorted(groups):
        safe_g = g.replace("/", "|")
        builder.button(text=f"👥 {g}", callback_data=f"{prefix}:{safe_g}")
    builder.adjust(3 if len(groups) > 6 else 2)
    builder.row(*nav_row(back_cb=back_cb))
    return builder.as_markup()


def get_paras_keyboard(paras: list[str], prefix: str = "tutor_para", back_cb: str = "tutor_back") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for p in sorted(paras, key=lambda x: int(x)):
        builder.button(text=f"⏰ {p}-para", callback_data=f"{prefix}:{p}")
    builder.adjust(4)
    builder.row(*nav_row(back_cb=back_cb))
    return builder.as_markup()


def get_attendance_students_keyboard(
    students: list[str],
    absent_set: set[str],
    db_absent_set: set[str],
    new_absent_set: set[str],
    page: int = 0,
    per_page: int = 20,
    is_edit_mode: bool = False
) -> InlineKeyboardMarkup:
    total_pages = max(1, (len(students) - 1) // per_page + 1)
    chunk = students[page * per_page: (page + 1) * per_page]

    builder = InlineKeyboardBuilder()
    for student in chunk:
        if is_edit_mode:
            icon = "❌" if student in absent_set else "✅"
        else:
            if student in db_absent_set:
                icon = "❌"
            elif student in new_absent_set:
                icon = "❌"
            else:
                icon = "✅"

        builder.button(
            text=f"{icon} {student}",
            callback_data=f"att_tog:{student[:30]}"
        )
    builder.adjust(1)

    # Sahifa navigatsiyasi
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"att_page:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if (page + 1) * per_page < len(students):
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"att_page:{page + 1}"))
    if nav:
        builder.row(*nav)

    # Hammasi kelgan
    if not absent_set:
        builder.row(InlineKeyboardButton(text="💯 Hammasi kelgan", callback_data="att_all_present"))

    # Saqlash + Ortga + Bosh menyu
    builder.row(InlineKeyboardButton(text="💾 Saqlash", callback_data="att_save"))
    builder.row(*nav_row(back_cb="att_back"))
    return builder.as_markup()
