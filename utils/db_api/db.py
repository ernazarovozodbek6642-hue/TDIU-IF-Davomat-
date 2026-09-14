"""
db.py — PostgreSQL ulanish va async operatsiyalar
"""
from datetime import date
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, delete, func, distinct
from sqlalchemy.dialects.postgresql import insert
from utils.db_api.models import (
    Base, Tutor, TutorGroup, Student, Attendance,
    AttendanceSession, SubjectKafedra, EdupageGroup, BotAdmin, BotSetting
)
from data.config import DATABASE_URL, ADMINS, SPREADSHEET_ID
from utils.sheet_settings import parse_spreadsheet_id
from data.edupage_catalog import TIMETABLE_NUM, catalog_groups

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    connect_args={"timeout": 30, "command_timeout": 60},
)
Session = async_sessionmaker(engine, expire_on_commit=False)


async def init_db():
    """Jadvallarni yaratish"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def is_admin(telegram_id: int) -> bool:
    if telegram_id in ADMINS:
        return True
    async with Session() as s:
        return await s.get(BotAdmin, telegram_id) is not None


async def get_admin_ids() -> list[int]:
    async with Session() as s:
        result = await s.execute(select(BotAdmin.telegram_id))
        return sorted(set(ADMINS) | set(result.scalars().all()))


async def get_spreadsheet_id() -> str:
    async with Session() as s:
        setting = await s.get(BotSetting, 'spreadsheet_id')
        return setting.value if setting else SPREADSHEET_ID


async def set_spreadsheet_id(spreadsheet_id: str, updated_by: int) -> None:
    spreadsheet_id = parse_spreadsheet_id(spreadsheet_id)
    async with Session() as s:
        if updated_by not in ADMINS and await s.get(BotAdmin, updated_by) is None:
            raise PermissionError('Faqat admin Sheets ID ni o‘zgartira oladi')
        await s.execute(insert(BotSetting).values(
            key='spreadsheet_id', value=spreadsheet_id, updated_by=updated_by
        ).on_conflict_do_update(index_elements=[BotSetting.key], set_={
            'value': spreadsheet_id, 'updated_by': updated_by
        }))
        await s.commit()


ROOM_REFRESH_DEFAULT_MINUTES = 60


async def get_room_refresh_minutes() -> int:
    """Return the admin-selected room refresh interval; zero disables it."""
    async with Session() as s:
        setting = await s.get(BotSetting, 'room_refresh_minutes')
        if setting is None:
            return ROOM_REFRESH_DEFAULT_MINUTES
        try:
            value = int(setting.value)
        except (TypeError, ValueError):
            return ROOM_REFRESH_DEFAULT_MINUTES
        return value if value == 0 or 5 <= value <= 1440 else ROOM_REFRESH_DEFAULT_MINUTES


async def set_room_refresh_minutes(minutes: int, updated_by: int) -> None:
    """Persist an interval in minutes. Only admins may change this setting."""
    if minutes != 0 and not 5 <= minutes <= 1440:
        raise ValueError('Oraliq 5–1440 daqiqa bo‘lishi yoki o‘chirish uchun 0 bo‘lishi kerak')
    async with Session() as s:
        if updated_by not in ADMINS and await s.get(BotAdmin, updated_by) is None:
            raise PermissionError('Faqat admin xona yangilanish vaqtini o‘zgartira oladi')
        await s.execute(insert(BotSetting).values(
            key='room_refresh_minutes', value=str(minutes), updated_by=updated_by
        ).on_conflict_do_update(index_elements=[BotSetting.key], set_={
            'value': str(minutes), 'updated_by': updated_by
        }))
        await s.commit()


async def add_bot_admin(telegram_id: int, added_by: int) -> bool:
    """Only an existing admin may grant access. False means already an admin."""
    if not isinstance(telegram_id, int) or isinstance(telegram_id, bool) or not 0 < telegram_id < 2**52:
        raise ValueError('Noto‘g‘ri Telegram ID')
    async with Session() as s:
        if added_by not in ADMINS and await s.get(BotAdmin, added_by) is None:
            raise PermissionError('Faqat admin boshqa admin qo‘sha oladi')
        if telegram_id in ADMINS:
            return False
        result = await s.execute(
            insert(BotAdmin).values(telegram_id=telegram_id, added_by=added_by)
            .on_conflict_do_nothing(index_elements=[BotAdmin.telegram_id])
            .returning(BotAdmin.telegram_id)
        )
        added = result.scalar_one_or_none() is not None
        await s.commit()
        return added


# ── Tyutorlar ─────────────────────────────────────────────

async def get_tutor(telegram_id: int) -> Tutor | None:
    async with Session() as s:
        res = await s.execute(select(Tutor).where(Tutor.telegram_id == telegram_id))
        return res.scalar_one_or_none()


async def get_tutor_by_id(tutor_id: int) -> Tutor | None:
    async with Session() as s:
        res = await s.execute(select(Tutor).where(Tutor.id == tutor_id))
        return res.scalar_one_or_none()


async def get_all_tutors() -> list[Tutor]:
    async with Session() as s:
        res = await s.execute(select(Tutor).order_by(Tutor.name))
        return list(res.scalars().all())


async def add_tutor(telegram_id: int, name: str) -> Tutor:
    async with Session() as s:
        res = await s.execute(select(Tutor).where(Tutor.telegram_id == telegram_id))
        tutor = res.scalar_one_or_none()
        if tutor:
            tutor.name = name
        else:
            tutor = Tutor(telegram_id=telegram_id, name=name)
            s.add(tutor)
        await s.commit()
        await s.refresh(tutor)
        return tutor


async def delete_tutor(tutor_id: int) -> bool:
    async with Session() as s:
        res = await s.execute(delete(Tutor).where(Tutor.id == tutor_id))
        await s.commit()
        return res.rowcount > 0


async def get_tutor_groups(tutor_id: int) -> list[str]:
    async with Session() as s:
        res = await s.execute(
            select(TutorGroup.group_name)
            .where(TutorGroup.tutor_id == tutor_id)
            .order_by(TutorGroup.group_name)
        )
        return [r[0] for r in res.all()]


async def get_group_tutor_map() -> dict[str, str]:
    """Current group assignments; retain every tutor if a group has several."""
    async with Session() as s:
        result = await s.execute(
            select(TutorGroup.group_name, Tutor.name)
            .join(Tutor, Tutor.id == TutorGroup.tutor_id)
            .order_by(TutorGroup.group_name, Tutor.name)
        )
        assignments = {}
        for group_name, tutor_name in result.all():
            names = assignments.setdefault(group_name, [])
            if tutor_name not in names:
                names.append(tutor_name)
        return {group: ', '.join(names) for group, names in assignments.items()}


async def assign_group_to_tutor(tutor_id: int, group_name: str):
    async with Session() as s:
        ex = (await s.execute(
            select(TutorGroup).where(
                TutorGroup.tutor_id == tutor_id,
                TutorGroup.group_name == group_name
            )
        )).scalar_one_or_none()
        if not ex:
            s.add(TutorGroup(tutor_id=tutor_id, group_name=group_name))
            await s.commit()


async def remove_group_from_tutor(tutor_id: int, group_name: str):
    async with Session() as s:
        await s.execute(
            delete(TutorGroup).where(
                TutorGroup.tutor_id == tutor_id,
                TutorGroup.group_name == group_name
            )
        )
        await s.commit()


# ── Talabalar (Students) ──────────────────────────────────

async def get_students_by_group(group_name: str) -> list[str]:
    async with Session() as s:
        res = await s.execute(
            select(Student.full_name)
            .where(Student.group_name == group_name)
            .order_by(Student.full_name)
        )
        return [r[0] for r in res.all()]


async def get_all_students() -> list[Student]:
    async with Session() as s:
        res = await s.execute(
            select(Student).order_by(Student.group_name, Student.full_name)
        )
        return list(res.scalars().all())


async def bulk_import_students(students_data: list[tuple[str, str]]) -> int:
    """Yangi talabalarni qo'shadi (borlarini saqlaydi)"""
    if not students_data:
        return 0
    async with Session() as s:
        count = 0
        for group_name, full_name in students_data:
            g_name = group_name.strip()
            f_name = full_name.strip()
            if not g_name or not f_name:
                continue
            ex = (await s.execute(
                select(Student).where(
                    Student.group_name == g_name,
                    Student.full_name == f_name
                )
            )).scalar_one_or_none()
            if not ex:
                s.add(Student(group_name=g_name, full_name=f_name))
                count += 1
        await s.commit()
        return count


async def replace_all_students(students_data: list[tuple[str, str]]) -> int:
    """Butun fakultet talabalar bazasini yangi ro'yxatga to'liq almashtirish"""
    if not students_data:
        return 0
    async with Session() as s:
        # Barcha mavjud talabalarni tozalaymiz
        await s.execute(delete(Student))
        await s.flush()

        seen = set()
        count = 0
        for group_name, full_name in students_data:
            g_name = group_name.strip()
            f_name = full_name.strip()
            if not g_name or not f_name or (g_name, f_name) in seen:
                continue
            seen.add((g_name, f_name))
            s.add(Student(group_name=g_name, full_name=f_name))
            count += 1

        await s.commit()
        return count


async def replace_group_students(group_name: str, full_names: list[str]) -> int:
    g_name = group_name.strip()
    if not g_name:
        return 0
    async with Session() as s:
        await s.execute(delete(Student).where(Student.group_name == g_name))
        await s.flush()

        seen = set()
        count = 0
        for name in full_names:
            f_name = name.strip()
            if not f_name or f_name in seen:
                continue
            seen.add(f_name)
            s.add(Student(group_name=g_name, full_name=f_name))
            count += 1

        await s.commit()
        return count


async def get_all_groups_from_db() -> list[str]:
    async with Session() as s:
        res = await s.execute(select(distinct(Student.group_name)).order_by(Student.group_name))
        return [r[0] for r in res.all()]


# ── Edupage Guruhlar Xaritasi (EdupageGroup) ──────────────

async def get_all_edupage_groups() -> list[EdupageGroup]:
    async with Session() as s:
        res = await s.execute(select(EdupageGroup).where(EdupageGroup.num_param == TIMETABLE_NUM))
        overrides = list(res.scalars().all())
    return merge_edupage_groups(overrides)


def merge_edupage_groups(overrides: list[EdupageGroup]) -> list[EdupageGroup]:
    """Use the verified current catalog; Excel imports can override its entries.

    Older timetable versions stay stored but do not replace the current catalog.
    """
    groups = {g['id']: EdupageGroup(edupage_id=g['id'], group_name=g['name'],
              kurs=g['kurs'], num_param=TIMETABLE_NUM) for g in catalog_groups()}
    for group in overrides:
        if group.num_param == TIMETABLE_NUM:
            groups[group.edupage_id] = group
    return sorted(groups.values(), key=lambda g: (g.kurs, g.group_name))


async def get_edupage_groups_by_kurs(kurs: str) -> list[EdupageGroup]:
    course = str(kurs).removesuffix('-kurs')
    return [g for g in await get_all_edupage_groups() if g.kurs.removesuffix('-kurs') == course]


async def bulk_import_edupage_groups(items: list[tuple[str, str, str, str]]) -> int:
    if not items:
        return 0
    async with Session() as s:
        count = 0
        for gid, gname, kurs, num_param in items:
            gid = str(gid).strip()
            gname = gname.strip()
            kurs = kurs.strip()
            num_p = str(num_param).strip() if num_param else TIMETABLE_NUM
            if not gid or not gname:
                continue
            ex = (await s.execute(
                select(EdupageGroup).where(EdupageGroup.edupage_id == gid)
            )).scalar_one_or_none()
            if ex:
                ex.group_name = gname
                ex.kurs = kurs
                ex.num_param = num_p
            else:
                s.add(EdupageGroup(edupage_id=gid, group_name=gname, kurs=kurs, num_param=num_p))
            count += 1
        await s.commit()
        return count


async def get_edupage_id_to_name_dict() -> dict[str, str]:
    return {g.edupage_id: g.group_name for g in await get_all_edupage_groups()}


# ── Fanlar va Kafedralar Xaritasi ─────────────────────────

async def get_all_subject_kafedras() -> list[SubjectKafedra]:
    async with Session() as s:
        res = await s.execute(select(SubjectKafedra).order_by(SubjectKafedra.subject_name))
        return list(res.scalars().all())


async def get_kafedra_map_dict() -> dict[str, str]:
    async with Session() as s:
        res = await s.execute(select(SubjectKafedra))
        return {r.subject_name: r.kafedra_name for r in res.scalars().all()}


async def bulk_import_subject_kafedras(items: list[tuple[str, str]]) -> int:
    if not items:
        return 0
    async with Session() as s:
        count = 0
        for subj, kaf in items:
            s_name = subj.strip()
            k_name = kaf.strip()
            if not s_name or not k_name:
                continue
            ex = (await s.execute(
                select(SubjectKafedra).where(SubjectKafedra.subject_name == s_name)
            )).scalar_one_or_none()
            if ex:
                ex.kafedra_name = k_name
            else:
                s.add(SubjectKafedra(subject_name=s_name, kafedra_name=k_name))
            count += 1
        await s.commit()
        return count


# ── Attendance (Yoqlama) ──────────────────────────────────

async def save_attendance(
    group_name: str,
    para: int,
    absent_students: list[str],
    tutor_id: int | None = None,
    att_date: date | None = None
):
    if att_date is None:
        att_date = date.today()

    async with Session() as s:
        await s.execute(
            delete(Attendance).where(
                Attendance.date == att_date,
                Attendance.group_name == group_name,
                Attendance.para == para,
            )
        )
        await s.flush()

        all_present = len(absent_students) == 0

        seen = set()
        for student_name in absent_students:
            s_name = student_name.strip()
            if not s_name or s_name in seen:
                continue
            seen.add(s_name)
            s.add(Attendance(
                date=att_date,
                group_name=group_name,
                para=para,
                student_name=s_name,
                tutor_id=tutor_id
            ))

        ex_sess = (await s.execute(
            select(AttendanceSession).where(
                AttendanceSession.date == att_date,
                AttendanceSession.group_name == group_name,
                AttendanceSession.para == para,
            )
        )).scalar_one_or_none()

        if ex_sess:
            ex_sess.all_present = all_present
            if tutor_id is not None:
                ex_sess.tutor_id = tutor_id
        else:
            s.add(AttendanceSession(
                date=att_date,
                group_name=group_name,
                para=para,
                all_present=all_present,
                tutor_id=tutor_id
            ))

        await s.commit()


async def get_absent_students(
    group_name: str,
    para: int,
    att_date: date | None = None
) -> list[str]:
    if att_date is None:
        att_date = date.today()

    async with Session() as s:
        res = await s.execute(
            select(Attendance.student_name).where(
                Attendance.date == att_date,
                Attendance.group_name == group_name,
                Attendance.para == para
            ).order_by(Attendance.student_name)
        )
        return [r[0] for r in res.all()]


async def get_attendance_dates(limit: int = 14) -> list[date]:
    async with Session() as s:
        res1 = await s.execute(select(distinct(Attendance.date)))
        res2 = await s.execute(select(distinct(AttendanceSession.date)))
        all_d = sorted({r[0] for r in res1.all()} | {r[0] for r in res2.all()}, reverse=True)
        return all_d[:limit]


async def get_paras_for_date(att_date: date) -> list[int]:
    async with Session() as s:
        res1 = await s.execute(select(distinct(Attendance.para)).where(Attendance.date == att_date))
        res2 = await s.execute(select(distinct(AttendanceSession.para)).where(AttendanceSession.date == att_date))
        paras = sorted({r[0] for r in res1.all()} | {r[0] for r in res2.all()})
        return paras


async def get_groups_for_date_and_paras(att_date: date, paras: list[int]) -> list[str]:
    async with Session() as s:
        res1 = await s.execute(
            select(distinct(Attendance.group_name))
            .where(Attendance.date == att_date, Attendance.para.in_(paras))
        )
        res2 = await s.execute(
            select(distinct(AttendanceSession.group_name))
            .where(AttendanceSession.date == att_date, AttendanceSession.para.in_(paras))
        )
        groups = sorted({r[0] for r in res1.all()} | {r[0] for r in res2.all()})
        return groups
