import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from bs4 import BeautifulSoup

from utils.scraper import (
    scrape_timetable, scrape_week_timetable, _period_numbers_for_rect,
    _normalize_room,
)
from utils.timetable_weeks import active_week_slot, day_bounds, cell_week_slot


class Live254Fixture:
    def get(self, url):
        self.page_source = Path('data/inspect_254_live.html').read_text(encoding='utf-8')

    def find_elements(self, *args):
        return [True]

    def quit(self):
        pass


class AlternatingWeeksTests(unittest.TestCase):
    def setUp(self):
        self.group = SimpleNamespace(edupage_id='254', group_name='I-900/26', kurs='1-kurs', num_param='94')

    def daily(self, day):
        with patch('utils.scraper.get_driver', return_value=Live254Fixture()):
            return scrape_timetable(day, kurs='1', custom_edupage_groups=[self.group])

    def test_tuesday_sixth_period_alternates_for_consecutive_weeks(self):
        upper, lower = "Iqtisodiy ta'limotlar tarixi", 'Amaliy matematika 1'
        for week, expected in enumerate([upper, lower, upper, lower]):
            rows = self.daily(datetime(2026, 9, 15) + timedelta(weeks=week))
            sixth = [r for r in rows if r['Juft-lik'] == '6']
            self.assertEqual(len(sixth), 1)
            self.assertEqual(sixth[0]['Fan nomi'], expected)
            self.assertEqual(sixth[0]['Xona'], '4/1')
            self.assertTrue(any(r['Juft-lik'] == '5' for r in rows))

    def test_monday_double_width_lesson_covers_first_and_second_periods(self):
        rows = self.daily(datetime(2026, 9, 14))
        sport = [r for r in rows if r['Fan nomi'] == 'Jismoniy madaniyat va Sport']
        self.assertEqual([r['Juft-lik'] for r in sport], ['1', '2'])
        self.assertTrue(all(r['Xona'] == 'Sport kompleksi' for r in sport))
        self.assertTrue(all(r["Mashg'ulot turi"] == 'Seminar' for r in sport))
        self.assertEqual(_period_numbers_for_rect(172.005, 684.49875), ['1', '2'])

    def test_visible_teacher_and_room_without_capacity(self):
        rows = self.daily(datetime(2026, 9, 14))
        history = next(
            row for row in rows
            if row['Fan nomi'] == "Iqtisodiy ta'limotlar tarixi"
        )
        self.assertEqual(history["Professor-o'qituvchining F.I.Sh"], 'Tashmatov Sh')
        self.assertEqual(history['Xona'], '4/1')
        self.assertEqual(_normalize_room('5/122-12 lab / 5/123-12 lab'), '5/122 / 5/123')
        self.assertEqual(_normalize_room('3/105-30 YAK'), '3/105')

    def test_weekly_upload_uses_same_rule_and_resets_daily_numbers(self):
        for monday, expected in [(datetime(2026, 9, 14), "Iqtisodiy ta'limotlar tarixi"),
                                 (datetime(2026, 9, 21), 'Amaliy matematika 1')]:
            with patch('utils.scraper.get_driver', return_value=Live254Fixture()):
                week = scrape_week_timetable(monday, kurs='all', custom_edupage_groups=[self.group])
            rows = week[monday + timedelta(days=1)]
            self.assertEqual([r['Fan nomi'] for r in rows if r['Juft-lik'] == '6'], [expected])
            self.assertEqual([r['t/r'] for r in rows], list(range(1, len(rows) + 1)))
            self.assertTrue(any(r['Fan nomi'] == 'Amaliy matematika 1' for r in week[monday + timedelta(days=3)]))

    def test_full_height_or_horizontal_split_is_not_alternating(self):
        soup = BeautifulSoup('<svg><rect x="0" y="100" width="50" height="200"/> '
                             '<rect x="0" y="100" width="100" height="100"/> '
                             '<rect x="0" y="200" width="100" height="100"/></svg>', 'html.parser')
        rects = soup.find_all('rect')
        self.assertIsNone(cell_week_slot(rects[0], (100, 300)))
        self.assertEqual(cell_week_slot(rects[1], (100, 300)), 0)
        self.assertEqual(cell_week_slot(rects[2], (100, 300)), 1)

    def test_parity_is_continuous_across_year_and_before_anchor(self):
        monday = datetime(2026, 9, 14)
        for index in (-2, -1, 0, 1, 2, 15, 16, 17, 52, 53):
            self.assertEqual(active_week_slot(monday + timedelta(weeks=index)), index % 2)
            self.assertEqual(active_week_slot(monday + timedelta(weeks=index, days=5)), index % 2)


if __name__ == '__main__':
    unittest.main()
