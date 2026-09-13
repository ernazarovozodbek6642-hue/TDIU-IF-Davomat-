import unittest
from unittest.mock import patch
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from test_admin_access import AsyncSessionAdapter
from utils.db_api import db
from utils.db_api.models import Tutor, TutorGroup
from utils.tutor_assignments import populate_tutors


class TutorAssignmentTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_engine('sqlite://')
        Tutor.__table__.create(self.engine)
        TutorGroup.__table__.create(self.engine)
        with Session(self.engine) as s:
            s.add_all([Tutor(id=1, telegram_id=111, name='Ali Valiyev'),
                       Tutor(id=2, telegram_id=222, name='Zafar Karimov')])
            s.add(TutorGroup(tutor_id=1, group_name='I-80/25'))
            s.commit()
        self.sessions = patch.object(db, 'Session', side_effect=lambda: AsyncSessionAdapter(self.engine))
        self.sessions.start()

    async def asyncTearDown(self):
        self.sessions.stop()
        self.engine.dispose()

    async def test_current_assignment_replaces_static_name(self):
        lessons = [{'Guruh': 'I-80/25', 'Tyutor': 'Old name'},
                   {'Guruh': 'I-81/25', 'Tyutor': 'Old name'}]
        await populate_tutors(lessons)
        self.assertEqual([r['Tyutor'] for r in lessons], ['Ali Valiyev', ''])

    async def test_reassignment_and_removal_are_visible_on_next_upload(self):
        lessons = [{'Guruh': 'I-80/25'}]
        await populate_tutors(lessons)
        with Session(self.engine) as s:
            s.execute(delete(TutorGroup))
            s.add(TutorGroup(tutor_id=2, group_name='I-80/25'))
            s.commit()
        await populate_tutors(lessons)
        self.assertEqual(lessons[0]['Tyutor'], 'Zafar Karimov')
        with Session(self.engine) as s:
            s.execute(delete(TutorGroup))
            s.commit()
        await populate_tutors(lessons)
        self.assertEqual(lessons[0]['Tyutor'], '')

    async def test_multiple_tutors_are_not_silently_dropped(self):
        with Session(self.engine) as s:
            s.add(TutorGroup(tutor_id=2, group_name='I-80/25'))
            s.commit()
        self.assertEqual(await db.get_group_tutor_map(), {'I-80/25': 'Ali Valiyev, Zafar Karimov'})


if __name__ == '__main__':
    unittest.main()
