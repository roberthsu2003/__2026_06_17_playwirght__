"""登入頁面表單驗證的 Playwright 自動化測試。"""

import unittest
from pathlib import Path
from typing import ClassVar, override

from playwright.sync_api import Browser, Dialog, Page, Playwright, sync_playwright


LOGIN_PAGE = Path(__file__).with_name("login_demo.html").resolve().as_uri()


class LoginPageTest(unittest.TestCase):
    """驗證登入頁面的成功、欄位錯誤與登入錯誤流程。"""

    playwright: ClassVar[Playwright]
    browser: ClassVar[Browser]
    _page: Page | None = None

    @property
    def page(self) -> Page:
        """取得目前測試用的頁面。"""
        assert self._page is not None
        return self._page

    @classmethod
    @override
    def setUpClass(cls) -> None:
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    @override
    def tearDownClass(cls) -> None:
        cls.browser.close()
        cls.playwright.stop()

    @override
    def setUp(self) -> None:
        self._page = self.browser.new_page()
        _ = self.page.goto(LOGIN_PAGE)

    @override
    def tearDown(self) -> None:
        self.page.close()

    def test_successful_submission_shows_welcome_message(self) -> None:
        self.page.get_by_label("用戶名").fill("admin")
        self.page.get_by_label("密碼").fill("password")
        self.page.get_by_role("button", name="登入").click()

        self.assertTrue(self.page.locator("#success-message").is_visible())
        self.assertEqual(self.page.locator("#welcome-user").inner_text(), "admin")

    def test_required_fields_show_errors_and_block_submission(self) -> None:
        self.page.get_by_role("button", name="登入").click()

        self.assertEqual(
            self.page.locator("#username-error").inner_text(), "請輸入用戶名。"
        )
        self.assertEqual(
            self.page.locator("#password-error").inner_text(), "請輸入密碼。"
        )
        self.assertEqual(
            self.page.locator("#username").get_attribute("aria-invalid"), "true"
        )
        self.assertEqual(
            self.page.locator("#password").get_attribute("aria-invalid"), "true"
        )
        self.assertFalse(self.page.locator("#success-message").is_visible())

    def test_whitespace_username_shows_validation_error(self) -> None:
        self.page.get_by_label("用戶名").fill("   ")
        self.page.get_by_label("密碼").fill("password")
        self.page.get_by_role("button", name="登入").click()

        self.assertEqual(
            self.page.locator("#username-error").inner_text(), "請輸入用戶名。"
        )
        self.assertFalse(self.page.locator("#success-message").is_visible())

    def test_invalid_credentials_show_login_error(self) -> None:
        dialog_messages: list[str] = []

        def accept_login_error(dialog: Dialog) -> None:
            dialog_messages.append(dialog.message)
            dialog.accept()

        self.page.on("dialog", accept_login_error)
        self.page.get_by_label("用戶名").fill("admin")
        self.page.get_by_label("密碼").fill("wrong-password")
        self.page.get_by_role("button", name="登入").click()

        self.assertEqual(len(dialog_messages), 1)
        self.assertIn("用戶名或密碼錯誤", dialog_messages[0])
        self.assertFalse(self.page.locator("#success-message").is_visible())


if __name__ == "__main__":
    _ = unittest.main()
