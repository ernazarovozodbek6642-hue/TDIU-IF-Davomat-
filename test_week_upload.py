import unittest
import threading
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock, MagicMock

from test_edupage_update import CachedDriver
from utils.scraper import scrape_timetable, scrape_week_timetable
from keyboards.inline.jadval import get_dates_keyboard
from handlers import jadval


class WeekScrapeTests(unittest.TestCase):
    def test_cancelled_scrape_closes_driver_without_fetching_groups(self):
        cancel_event = threading.Event()
        cancel_event.set()
        driver = CachedDriver()
        driver.get = MagicMock(wraps=driver.get)
        driver.quit = MagicMock()
        with patch('utils.scraper.get_driver', return_value=driver):
            lessons = scrape_timetable(
                datetime(2026, 9, 8), kurs='1', cancel_event=cancel_event
            )
        self.assertEqual(lessons, [])
        driver.get.assert_not_called()
        driver.quit.assert_called_once()

    def test_week_dates_and_one_fetch_per_group(self):
        driver = CachedDriver()
        driver.get = MagicMock(wraps=driver.get)
        with patch('utils.scraper.get_driver', return_value=driver):
            week = scrape_week_timetable(datetime(2026, 9, 8), kurs='all')
        self.assertEqual([d.strftime('%Y-%m-%d') for d in week],
                         [f'2026-09-{i:02d}' for i in range(7, 13)])
        self.assertEqual(driver.get.call_count, 132)
        self.assertEqual({r['Filtr uchun'] for rows in week.values() for r in rows},
                         {'1-kurs', '2-kurs', '3-kurs', '4-kurs'})
        for day, rows in week.items():
            self.assertTrue(all(r['_day'] == jadval.DAYS_UZ[day.weekday()] for r in rows))
            self.assertEqual([r['t/r'] for r in rows], list(range(1, len(rows) + 1)))

    def test_button_keeps_week_start_across_month_boundary(self):
        with patch('keyboards.inline.jadval.datetime') as clock:
            clock.now.return_value = datetime(2026, 9, 1)
            buttons = [b for row in get_dates_keyboard().inline_keyboard for b in row]
        week = next(b for b in buttons if b.callback_data.startswith('week_'))
        self.assertEqual(week.callback_data, 'week_2026-08-31')
        self.assertIn('31.08–05.09', week.text)


class WeekHandlerTests(unittest.IsolatedAsyncioTestCase):
    def callback(self, data):
        return SimpleNamespace(data=data, answer=AsyncMock(),
                               from_user=SimpleNamespace(id=1001),
                               message=SimpleNamespace(edit_text=AsyncMock()))

    async def asyncSetUp(self):
        jadval.ACTIVE_UPLOADS.clear()

    async def asyncTearDown(self):
        jadval.ACTIVE_UPLOADS.clear()

    async def test_week_button_offers_all_courses(self):
        callback = self.callback('week_2026-09-07')
        await jadval.handle_date(callback)
        kb = callback.message.edit_text.call_args.kwargs['reply_markup']
        data = [b.callback_data for row in kb.inline_keyboard for b in row]
        self.assertIn('kurs_all_week:2026-09-07', data)
        for course in range(1, 5):
            self.assertIn(f'kurs_{course}_week:2026-09-07', data)

    async def test_upload_cancel_requires_confirmation(self):
        callback = self.callback('upload_cancel_request')
        job = jadval.UploadJob(threading.Event(), progress_text='Jarayon 40%')
        jadval.ACTIVE_UPLOADS[1001] = job

        await jadval.request_upload_cancel(callback)
        self.assertTrue(job.confirming)
        keyboard = callback.message.edit_text.call_args.kwargs['reply_markup']
        actions = [button.callback_data for row in keyboard.inline_keyboard for button in row]
        self.assertEqual(actions, ['upload_cancel_confirm', 'upload_cancel_continue'])

        await jadval.confirm_upload_cancel(callback)
        self.assertTrue(job.cancel_event.is_set())
        self.assertIn('to‘xtatilmoqda', callback.message.edit_text.call_args.args[0])

    async def test_upload_can_continue_after_declining_confirmation(self):
        callback = self.callback('upload_cancel_continue')
        job = jadval.UploadJob(threading.Event(), progress_text='Jarayon 55%', confirming=True)
        jadval.ACTIVE_UPLOADS[1001] = job

        await jadval.continue_upload(callback)
        self.assertFalse(job.confirming)
        self.assertFalse(job.cancel_event.is_set())
        self.assertEqual(callback.message.edit_text.call_args.args[0], 'Jarayon 55%')

    async def run_upload(self, weekly_result, upload_effect=None):
        callback = self.callback('kurs_all_week:2026-09-07')
        with patch.object(jadval, 'get_kafedra_map_dict', new=AsyncMock(return_value={})), \
             patch.object(jadval, 'get_all_edupage_groups', new=AsyncMock(return_value=[])), \
             patch.object(jadval, 'get_edupage_id_to_name_dict', new=AsyncMock(return_value={})), \
             patch.object(jadval, 'get_spreadsheet_id', new=AsyncMock(return_value='new-sheet-id')), \
             patch.object(jadval, 'existing_daily_sheet_names', return_value=set()), \
             patch.object(jadval, 'scrape_week_timetable', return_value=weekly_result), \
             patch.object(jadval, 'upload_to_sheets', side_effect=upload_effect or
                          (lambda rows, day, sheet_id: ('https://example.com/sheets', day.strftime('%d.%m')))) as upload:
            await jadval.handle_kurs(callback)
        return callback, upload

    async def test_manual_daily_upload_refuses_existing_sheet(self):
        callback = self.callback('kurs_all_2026-09-07')
        with patch.object(jadval, 'get_spreadsheet_id', new=AsyncMock(return_value='new-sheet-id')), \
             patch.object(jadval, 'existing_daily_sheet_names', return_value={'07.09 Dushanba'}), \
             patch.object(jadval, 'scrape_timetable') as scrape, \
             patch.object(jadval, 'upload_to_sheets') as upload:
            await jadval.handle_kurs(callback)
        scrape.assert_not_called()
        upload.assert_not_called()
        self.assertIn('oldindan yuklangan', callback.message.edit_text.call_args.args[0])

    async def test_upload_skips_empty_days_and_uses_separate_dates(self):
        first, second, third = (datetime(2026, 9, n) for n in (7, 8, 9))
        callback, upload = await self.run_upload({first: [{'Guruh': 'A'}], second: [], third: [{'Guruh': 'B'}]})
        self.assertEqual([call.args[1] for call in upload.call_args_list], [first, third])
        self.assertTrue(all(call.args[2] == 'new-sheet-id' for call in upload.call_args_list))
        final = callback.message.edit_text.call_args.args[0]
        self.assertIn('Dars yo‘q kunlar: 08.09', final)
        self.assertIn('07.09: 1 ta dars', final)
        self.assertIn('09.09: 1 ta dars', final)

    async def test_empty_week_does_not_upload(self):
        callback, upload = await self.run_upload({datetime(2026, 9, 7): []})
        upload.assert_not_called()
        self.assertIn('dars topilmadi', callback.message.edit_text.call_args.args[0])

    async def test_partial_failure_reports_completed_days(self):
        callback, upload = await self.run_upload(
            {datetime(2026, 9, 7): [{}], datetime(2026, 9, 8): [{}]},
            [('https://example.com', '07.09'), RuntimeError('Upload failed')])
        self.assertEqual(upload.call_count, 2)
        final = callback.message.edit_text.call_args.args[0]
        self.assertIn('Yuklangan varaqlar', final)
        self.assertIn('07.09', final)
        self.assertIn('Xatolik', final)


if __name__ == '__main__':
    unittest.main()
