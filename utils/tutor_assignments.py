"""Fill schedule tutor names using the bot's current group assignments."""
from utils.db_api.db import get_group_tutor_map


async def populate_tutors(lessons: list[dict]) -> None:
    if not lessons:
        return
    assignments = await get_group_tutor_map()
    for lesson in lessons:
        lesson['Tyutor'] = assignments.get(lesson.get('Guruh', ''), '')
