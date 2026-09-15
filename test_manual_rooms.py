import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from contextlib import ExitStack

from handlers import rooms


class ManualRoomTests(unittest.IsolatedAsyncioTestCase):
    async def run_refresh(self, names, lessons=None, error=None):
        callback = SimpleNamespace(data='rooms_date_2026-09-16', answer=AsyncMock(),
                                   message=SimpleNamespace(edit_text=AsyncMock(), answer=AsyncMock()))
        group = SimpleNamespace(group_name='I-900/26')
        with ExitStack() as stack:
            for name, result in [('get_spreadsheet_id', 'sheet'), ('get_all_edupage_groups', [group]),
                                 ('get_kafedra_map_dict', {}), ('get_edupage_id_to_name_dict', {})]:
                stack.enter_context(patch.object(rooms, name, new=AsyncMock(return_value=result)))
            stack.enter_context(patch.object(rooms, 'daily_sheet_group_names', return_value=names))
            scrape = stack.enter_context(patch.object(rooms, 'scrape_timetable',
                                                       return_value=lessons or [], side_effect=error))
            update = stack.enter_context(patch.object(rooms, 'update_room_column', return_value={
                'changed': 2, 'unchanged': 3, 'unmatched': 0, 'ambiguous': 0,
            }))
            await rooms.refresh_rooms(callback)
            return callback, scrape, update

    async def test_selected_date_and_sheet_used_for_room_update(self):
        lessons = [{'Guruh': 'I-900/26', 'Xona': '4/404'}]
        cb, scrape, update = await self.run_refresh(['I-900/26'], lessons)
        self.assertEqual(scrape.call_args.args[0], datetime(2026, 9, 16))
        update.assert_called_once_with(lessons, datetime(2026, 9, 16), 'sheet')
        self.assertIn('O‘zgartirilgan: 2', cb.message.edit_text.call_args.args[0])

    async def test_missing_sheet_does_not_scrape_or_write(self):
        _, scrape, update = await self.run_refresh([])
        scrape.assert_not_called()
        update.assert_not_called()

    async def test_edupage_failure_does_not_write_and_unlocks(self):
        _, _, update = await self.run_refresh(['I-900/26'], error=RuntimeError('unavailable'))
        update.assert_not_called()
        self.assertFalse(rooms._refresh_lock.locked())

    def test_calendar_has_dates_and_week_navigation(self):
        data = [b.callback_data for row in rooms.room_dates_keyboard(datetime(2026, 9, 15)).inline_keyboard for b in row]
        self.assertIn('rooms_date_2026-09-15', data)
        self.assertIn('rooms_page_2026-09-08', data)
        self.assertIn('rooms_page_2026-09-22', data)
        self.assertNotIn('rooms_date_2026-09-20', data)

    async def test_only_daily_upload_is_scheduled(self):
        import main
        with patch.object(main, 'AsyncIOScheduler') as scheduler, \
             patch.object(main, 'setup_message_routers'), \
             patch.object(main, 'dp') as dp, \
             patch.object(main.bot, 'delete_webhook', new=AsyncMock()):
            dp.start_polling = AsyncMock()
            await main.main()
        jobs = scheduler.return_value.add_job.call_args_list
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].args, (main.auto_upload_today, 'cron'))


if __name__ == '__main__':
    unittest.main()
