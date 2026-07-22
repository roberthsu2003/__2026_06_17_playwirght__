from playwright.sync_api import sync_playwright,Playwright,Browser,Page
import time


def crawl(p:Playwright) -> None:
  browser:Browser = p.chromium.launch(headless=False)
  page:Page = browser.new_page()

  page.goto("https://zh.wikipedia.org")
  page.locator("input.cdx-text-input__input").fill("臺灣")
  page.wait_for_timeout(10000)
  time.sleep(10)



with sync_playwright() as p:
  crawl(p)
