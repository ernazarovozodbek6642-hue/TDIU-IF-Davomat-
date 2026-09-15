import unittest
from datetime import datetime
from unittest.mock import patch, AsyncMock, MagicMock
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.base import StorageKey

from test_admin_access import AsyncSessionAdapter, AdminAccessTests
from utils.db_api import db
from utils.db_api.models import BotSetting, BotAdmin
from utils.sheet_settings import parse_spreadsheet_id
from utils.sheets import (
    validate_spreadsheet_access, update_sheets_attendance, update_room_column,
    daily_sheet_group_names,
)
from handlers.admin import sheets_id_entered, router
from states.states import SheetsSettingsState
from data.constants import HEADERS

OLD = 'old_spreadsheet_1234567890'
NEW = 'new_spreadsheet_1234567890'


class SheetSettingsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_engine('sqlite://')
        BotAdmin.__table__.create(self.engine)
        BotSetting.__table__.create(self.engine)
        self.sessions = patch.object(db, 'Session', side_effect=lambda: AsyncSessionAdapter(self.engine))
        self.admins = patch.object(db, 'ADMINS', [111])
        self.fallback = patch.object(db, 'SPREADSHEET_ID', OLD)
        self.sessions.start()
        self.admins.start()
        self.fallback.start()
        self.state = FSMContext(MemoryStorage(), StorageKey(bot_id=1, chat_id=111, user_id=111))

    async def asyncTearDown(self):
        for mock in (self.sessions, self.admins, self.fallback):
            mock.stop()
        await self.state.storage.close()
        self.engine.dispose()

    def message(self, text=NEW, uid=111):
        return AdminAccessTests().message(uid=uid, text=text)

    async def test_fallback_and_persistence_after_new_session(self):
        self.assertEqual(await db.get_spreadsheet_id(), OLD)
        await db.set_spreadsheet_id(NEW, updated_by=111)
        self.assertEqual(await db.get_spreadsheet_id(), NEW)
        await db.add_bot_admin(222, added_by=111)
        await db.set_spreadsheet_id(OLD, updated_by=222)
        self.assertEqual(await db.get_spreadsheet_id(), OLD)
        with Session(self.engine) as s:
            self.assertEqual(s.get(BotSetting, 'spreadsheet_id').updated_by, 222)

    async def test_room_refresh_interval_is_admin_controlled_and_persistent(self):
        self.assertEqual(await db.get_room_refresh_minutes(), 60)
        await db.set_room_refresh_minutes(90, updated_by=111)
        self.assertEqual(await db.get_room_refresh_minutes(), 90)
        await db.add_bot_admin(222, added_by=111)
        await db.set_room_refresh_minutes(0, updated_by=222)
        self.assertEqual(await db.get_room_refresh_minutes(), 0)
        with self.assertRaises(PermissionError):
            await db.set_room_refresh_minutes(30, updated_by=999)
        for invalid in (-1, 1, 1441):
            with self.assertRaises(ValueError):
                await db.set_room_refresh_minutes(invalid, updated_by=111)

    async def test_non_admin_cannot_change_setting_or_open_flow(self):
        with self.assertRaises(PermissionError):
            await db.set_spreadsheet_id(NEW, updated_by=999)
        self.assertEqual(await db.get_spreadsheet_id(), OLD)
        with patch.object(Message, 'answer', new=AsyncMock()) as answer:
            await router.propagate_event('message', self.message("⚙️ Sheets ID ni o'zgartirish", 999), state=self.state)
            answer.assert_not_awaited()

    async def test_validation_failure_preserves_old_setting_and_state(self):
        await self.state.set_state(SheetsSettingsState.entering_spreadsheet_id)
        for error in (ValueError('Editor ruxsati yo‘q'), RuntimeError('Network unavailable')):
            status = SimpleNamespace(edit_text=AsyncMock())
            with patch.object(Message, 'answer', new=AsyncMock(return_value=status)), \
                 patch('handlers.admin.validate_spreadsheet_access', side_effect=error):
                await sheets_id_entered(self.message(), self.state)
            self.assertEqual(await db.get_spreadsheet_id(), OLD)
            self.assertEqual(await self.state.get_state(), SheetsSettingsState.entering_spreadsheet_id.state)

    async def test_valid_link_saves_only_after_access_check(self):
        await self.state.set_state(SheetsSettingsState.entering_spreadsheet_id)
        status = SimpleNamespace(edit_text=AsyncMock())
        with patch.object(Message, 'answer', new=AsyncMock(return_value=status)), \
             patch('handlers.admin.validate_spreadsheet_access', return_value='New <Schedule>') as validate:
            await sheets_id_entered(self.message(f'https://docs.google.com/spreadsheets/d/{NEW}/edit#gid=0'), self.state)
        validate.assert_called_once_with(NEW)
        self.assertEqual(await db.get_spreadsheet_id(), NEW)
        self.assertIsNone(await self.state.get_state())


class SheetValidationTests(unittest.TestCase):
    def test_daily_sheet_groups_are_read_only_from_column_c(self):
        client = MagicMock()
        sheet = client.open_by_key.return_value.worksheet.return_value
        sheet.get.return_value = [['I-900/26'], [''], ['I-901/26'], ['I-900/26']]
        with patch('utils.sheets._get_gspread_client', return_value=(client, MagicMock())):
            groups = daily_sheet_group_names(datetime(2026, 9, 14), NEW)
        self.assertEqual(groups, {'I-900/26', 'I-901/26'})
        sheet.get.assert_called_once_with('C3:C')
        sheet.batch_update.assert_not_called()

    def test_id_and_urls(self):
        for value in (NEW, f'https://docs.google.com/spreadsheets/d/{NEW}/edit?usp=sharing#gid=0',
                      f'https://docs.google.com/spreadsheets/u/0/d/{NEW}/edit'):
            self.assertEqual(parse_spreadsheet_id(value), NEW)
        for value in ('', '123', '@test', f'https://evil.example/spreadsheets/d/{NEW}',
                      f'https://docs.google.com/document/d/{NEW}/edit', 'bad id with spaces___'):
            with self.assertRaises(ValueError):
                parse_spreadsheet_id(value)

    def test_readonly_and_non_spreadsheet_rejected(self):
        for mime, can_edit, succeeds in [('application/vnd.google-apps.spreadsheet', True, True),
                                       ('application/vnd.google-apps.spreadsheet', False, False),
                                       ('application/pdf', True, False)]:
            service = MagicMock()
            service.files().get().execute.return_value = {
                'name': 'Schedule', 'mimeType': mime, 'capabilities': {'canEdit': can_edit}}
            with patch('utils.sheets.load_google_credentials'), patch('utils.sheets.build', return_value=service):
                if succeeds:
                    self.assertEqual(validate_spreadsheet_access(NEW), 'Schedule')
                else:
                    with self.assertRaises(ValueError):
                        validate_spreadsheet_access(NEW)

    def test_attendance_uses_selected_spreadsheet(self):
        client = MagicMock()
        sheet = client.open_by_key.return_value.worksheet.return_value
        row = [''] * len(HEADERS)
        row[HEADERS.index('Guruh')] = 'I-900/26'
        row[HEADERS.index('Juft-lik')] = '6'
        sheet.get_all_values.return_value = [['Title'], HEADERS, row]
        with patch('utils.sheets._get_gspread_client', return_value=(client, MagicMock())):
            self.assertTrue(update_sheets_attendance('I-900/26', 6, [], datetime(2026, 9, 15), 25, NEW))
        client.open_by_key.assert_called_once_with(NEW)
        sheet.batch_update.assert_called_once()
        updates = sheet.batch_update.call_args.args[0]
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0]['range'], 'M3')

    def test_room_refresh_updates_only_g_when_group_and_period_match(self):
        client = MagicMock()
        sheet = client.open_by_key.return_value.worksheet.return_value
        sheet.get.return_value = [
            ['I-900/26', 'Teacher', 'Fan', 'Kafedra', '1/101', '1'],
            ['I-901/26', 'Teacher', 'Fan', 'Kafedra', '2/202', '1'],
            ['I-900/26', 'Teacher', 'Fan', 'Kafedra', '3/303', '2'],
        ]
        lessons = [
            {'Guruh': 'I-900/26', 'Juft-lik': '1', 'Xona': '4/404',
             "Professor-o'qituvchining F.I.Sh": 'Teacher', 'Fan nomi': 'Fan'},
            {'Guruh': 'I-902/26', 'Juft-lik': '1', 'Xona': '5/505',
             "Professor-o'qituvchining F.I.Sh": 'Teacher', 'Fan nomi': 'Fan'},
        ]
        with patch('utils.sheets._get_gspread_client', return_value=(client, MagicMock())):
            result = update_room_column(lessons, datetime(2026, 9, 14), NEW)

        sheet.get.assert_called_once_with('C3:H')
        sheet.batch_update.assert_called_once_with(
            [{'range': 'G3', 'values': [['4/404']]}], value_input_option='RAW'
        )
        self.assertEqual(result['changed'], 1)
        self.assertEqual(result['matched'], 1)
        self.assertEqual(result['unmatched'], 2)


if __name__ == '__main__':
    unittest.main()
