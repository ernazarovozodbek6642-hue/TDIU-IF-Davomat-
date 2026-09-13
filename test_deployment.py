import json
import os
import unittest
from unittest.mock import MagicMock, patch

from utils.google_credentials import load_google_credentials
from utils.scraper import get_driver


class DeploymentTests(unittest.TestCase):
    def test_google_credentials_json_secret_is_supported(self):
        payload = json.dumps({"type": "service_account", "client_email": "bot@example.test"})
        expected = MagicMock()
        with patch.dict(os.environ, {"GOOGLE_CREDENTIALS_JSON": payload}), \
             patch("utils.google_credentials.Credentials.from_service_account_info", return_value=expected) as loader:
            self.assertIs(load_google_credentials(["scope"]), expected)
        loader.assert_called_once_with(json.loads(payload), scopes=["scope"])

    def test_container_chromedriver_path_is_used_without_selenium_manager(self):
        driver = MagicMock()
        environment = {
            "CHROME_BIN": "/usr/bin/chromium",
            "CHROMEDRIVER_PATH": "/usr/bin/chromedriver",
            "SELENIUM_PAGE_LOAD_TIMEOUT": "45",
        }
        with patch.dict(os.environ, environment, clear=False), \
             patch("utils.scraper.os.path.exists", return_value=True), \
             patch("utils.scraper.os.path.isfile", return_value=True), \
             patch("utils.scraper.webdriver.Chrome", return_value=driver) as chrome:
            self.assertIs(get_driver(), driver)

        service = chrome.call_args.kwargs["service"]
        self.assertEqual(service.path, "/usr/bin/chromedriver")
        self.assertEqual(chrome.call_args.kwargs["options"].binary_location, "/usr/bin/chromium")
        driver.set_page_load_timeout.assert_called_once_with(45)
        driver.set_script_timeout.assert_called_once_with(45)


if __name__ == "__main__":
    unittest.main()
