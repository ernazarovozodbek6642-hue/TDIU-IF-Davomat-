import threading
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from selenium.common.exceptions import TimeoutException, WebDriverException
from utils.scraper import scrape_timetable


class ScraperRecoveryTests(unittest.TestCase):
    def groups(self):
        return [SimpleNamespace(edupage_id=str(gid), group_name=str(gid),
                                kurs='1', num_param='94') for gid in (254, 255)]

    def test_retries_same_group_with_new_browser(self):
        old, fresh = MagicMock(), MagicMock()
        with patch('utils.scraper.get_driver', side_effect=[old, fresh]), patch(
            'utils.scraper.scrape_one_group_with_driver',
            side_effect=[TimeoutException('renderer timed out'), [], []],
        ) as scrape:
            self.assertEqual(scrape_timetable(datetime(2026, 9, 15),
                                             custom_edupage_groups=self.groups()), [])
        self.assertIs(scrape.call_args_list[0].args[0], old)
        self.assertIs(scrape.call_args_list[1].args[0], fresh)
        self.assertEqual([call.args[1]['id'] for call in scrape.call_args_list],
                         ['254', '254', '255'])
        old.quit.assert_called_once()
        fresh.quit.assert_called_once()

    def test_exhausted_retries_abort_instead_of_skipping_group(self):
        drivers = [MagicMock() for _ in range(3)]
        with patch('utils.scraper.get_driver', side_effect=drivers), patch(
            'utils.scraper.scrape_one_group_with_driver',
            side_effect=WebDriverException('tab crashed'),
        ) as scrape:
            with self.assertRaisesRegex(RuntimeError, 'Chala jadval yuklanmadi'):
                scrape_timetable(datetime(2026, 9, 15),
                                 custom_edupage_groups=self.groups())
        self.assertEqual(scrape.call_count, 3)
        self.assertTrue(all(call.args[1]['id'] == '254' for call in scrape.call_args_list))
        for driver in drivers:
            driver.quit.assert_called_once()

    def test_cancel_during_failure_does_not_start_another_browser(self):
        event = threading.Event()
        driver = MagicMock()
        def fail(*args):
            event.set()
            raise TimeoutException('timeout')
        with patch('utils.scraper.get_driver', return_value=driver) as factory, patch(
            'utils.scraper.scrape_one_group_with_driver', side_effect=fail,
        ):
            self.assertEqual(scrape_timetable(datetime(2026, 9, 15),
                                             custom_edupage_groups=self.groups(),
                                             cancel_event=event), [])
        factory.assert_called_once()
        driver.quit.assert_called_once()


if __name__ == '__main__':
    unittest.main()
