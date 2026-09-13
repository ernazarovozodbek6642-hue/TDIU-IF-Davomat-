import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SyncSession
from aiogram.types import Message, Chat, User
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.base import StorageKey

from utils.db_api import db
from utils.db_api.models import BotAdmin
from filters.role_filter import IsAdmin, IsTutor
from handlers.admin import router, admin_id_entered
from handlers.start import _send_home
from handlers.attendance import start_attendance
from states.states import AddAdminState


class AsyncSessionAdapter:
    """Exercise actual SQL and persistence with an isolated in-memory database."""
    def __init__(self, engine):
        self.session = SyncSession(engine)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self.session.close()

    async def get(self, *args):
        return self.session.get(*args)

    async def execute(self, *args):
        return self.session.execute(*args)

    async def commit(self):
        self.session.commit()


class AdminAccessTests(unittest.IsolatedAsyncioTestCase):
    async def test_unknown_user_gets_own_id_and_dekanat_notice(self):
        from aiogram.types import ReplyKeyboardRemove
        with patch('handlers.start.get_tutor', new=AsyncMock(return_value=None)), \
             patch.object(Message, 'answer', new=AsyncMock()) as answer:
            await _send_home(self.message(999), self.state, 999)
        text = answer.call_args.args[0]
        self.assertIn('<code>999</code>', text)
        self.assertIn('dekanatga murojaat qiling', text)
        self.assertIsInstance(answer.call_args.kwargs['reply_markup'], ReplyKeyboardRemove)

    async def test_registered_tutor_still_gets_attendance_menu(self):
        with patch('handlers.start.get_tutor', new=AsyncMock(return_value=SimpleNamespace(name='Tyutor'))), \
             patch.object(Message, 'answer', new=AsyncMock()) as answer:
            await _send_home(self.message(999), self.state, 999)
        self.assertNotIn('dekanatga', answer.call_args.args[0])
        keyboard = answer.call_args.kwargs['reply_markup']
        self.assertEqual(keyboard.keyboard[0][0].text, '📋 Yoqlama qilish')

    async def asyncSetUp(self):
        self.engine = create_engine('sqlite://')
        BotAdmin.__table__.create(self.engine)
        self.sessions = patch.object(db, 'Session', side_effect=lambda: AsyncSessionAdapter(self.engine))
        self.admins = patch.object(db, 'ADMINS', [111])
        self.sessions.start()
        self.admins.start()
        self.state = FSMContext(MemoryStorage(), StorageKey(bot_id=1, chat_id=111, user_id=111))

    async def asyncTearDown(self):
        self.sessions.stop()
        self.admins.stop()
        await self.state.storage.close()
        self.engine.dispose()

    def message(self, uid=111, text="➕ Admin qo'shish"):
        return Message(message_id=1, date=datetime.now(), chat=Chat(id=uid, type='private'),
                       from_user=User(id=uid, is_bot=False, first_name='Test'), text=text)

    async def test_permissions_persist_and_new_admin_can_grant(self):
        self.assertTrue(await db.add_bot_admin(222, added_by=111))
        self.assertTrue(await db.is_admin(222))
        self.assertTrue(await db.add_bot_admin(333, added_by=222))
        self.assertEqual(await db.get_admin_ids(), [111, 222, 333])
        self.assertFalse(await db.add_bot_admin(222, added_by=111))
        self.assertFalse(await db.add_bot_admin(111, added_by=222))
        with SyncSession(self.engine) as session:
            self.assertEqual(session.get(BotAdmin, 333).added_by, 222)

    async def test_unauthorized_cannot_grant(self):
        with self.assertRaises(PermissionError):
            await db.add_bot_admin(222, added_by=999)
        self.assertFalse(await db.is_admin(222))

    async def test_both_role_filters_accept_new_admin(self):
        await db.add_bot_admin(222, added_by=111)
        event = SimpleNamespace(from_user=SimpleNamespace(id=222))
        self.assertTrue(await IsAdmin()(event))
        with patch('filters.role_filter.get_tutor', new=AsyncMock()) as tutor:
            self.assertTrue(await IsTutor()(event))
            tutor.assert_not_awaited()

    async def test_non_admin_cannot_open_admin_flow(self):
        with patch.object(Message, 'answer', new=AsyncMock()) as answer:
            await router.propagate_event('message', self.message(999), state=self.state)
            answer.assert_not_awaited()
        self.assertIsNone(await self.state.get_state())

    async def test_dynamic_admin_can_open_add_flow(self):
        await db.add_bot_admin(222, added_by=111)
        with patch.object(Message, 'answer', new=AsyncMock()):
            await router.propagate_event('message', self.message(222), state=self.state)
        self.assertEqual(await self.state.get_state(), AddAdminState.entering_telegram_id.state)

    async def test_input_validation_and_success(self):
        await self.state.set_state(AddAdminState.entering_telegram_id)
        with patch.object(Message, 'answer', new=AsyncMock()):
            for value in ('', '-123', '0', '@username', '1.2', '9' * 40, '²'):
                await admin_id_entered(self.message(text=value), self.state)
                self.assertEqual(await self.state.get_state(), AddAdminState.entering_telegram_id.state)
            await admin_id_entered(self.message(text='222'), self.state)
        self.assertTrue(await db.is_admin(222))
        self.assertIsNone(await self.state.get_state())

    async def test_new_admin_gets_full_home_and_all_attendance_groups(self):
        await db.add_bot_admin(222, added_by=111)
        with patch.object(Message, 'answer', new=AsyncMock()) as answer:
            await _send_home(self.message(222), self.state, 222)
            menu = answer.call_args.kwargs['reply_markup']
            self.assertIn("➕ Admin qo'shish", [b.text for row in menu.keyboard for b in row])
        with patch.object(Message, 'answer', new=AsyncMock()), \
             patch('handlers.attendance.get_course_picker_keyboard') as keyboard:
            await start_attendance(self.message(222), self.state)
            course_counts = keyboard.call_args.args[0]
            self.assertEqual(sum(course_counts.values()), 132)
            self.assertEqual(keyboard.call_args.kwargs['prefix'], 'att_course')


if __name__ == '__main__':
    unittest.main()
