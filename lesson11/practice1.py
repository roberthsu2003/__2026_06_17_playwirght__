from playwright.sync_api import sync_playwright,Playwright,Browser,Page


def crawl(p:Playwright) -> None:
  browser:Browser = p.chromium.launch(headless=False)
  page:Page = browser.new_page()

  page.goto("https://zh.wikipedia.org")
  page.get_by_placeholder("搜尋維基百科").first.fill("臺灣")
  page.screenshot(path="screenshot.png")
  page.keyboard.press("Enter")
  page.wait_for_load_state("networkidle")
  page.wait_for_timeout(10000)
  browser.close()


with sync_playwright() as p:
  crawl(p)
