from datetime import datetime
from playwright.sync_api import sync_playwright,Playwright,Browser,Page


def launch_browser(p:Playwright) -> Browser:
  """啟動 Chromium 瀏覽器實例"""
  return p.chromium.launch()


def search_wikipedia(page:Page, keyword:str) -> None:
  """在維基百科搜尋指定關鍵字"""
  page.goto("https://zh.wikipedia.org")
  page.locator("#searchInput").fill(keyword)
  page.screenshot(path=f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
  page.keyboard.press("Enter")
  page.wait_for_load_state("networkidle")


def get_search_result(page:Page) -> dict:
  """擷取搜尋結果頁面的標題與摘要"""
  heading:str = page.locator("#firstHeading").inner_text()
  elements = page.locator("#mw-content-text p")
  content:str = elements.first.inner_text() if elements.count() > 0 else ""
  return {"heading": heading, "content": content[:100]}


def crawl(p:Playwright) -> None:
  """爬蟲主流程：啟動瀏覽器、搜尋、擷取結果、返回首頁"""
  browser:Browser = launch_browser(p)
  try:
    page:Page = browser.new_page()
    search_wikipedia(page, "臺灣")

    result:dict = get_search_result(page)
    print(f"搜尋主題: {result['heading']}")
    print(f"摘要: {result['content']}")

    page.go_back()
    page.wait_for_load_state("networkidle")
    print(f"返回首頁: {page.title()}")
  except Exception as e:
    print(f"爬蟲執行失敗: {e}")
  finally:
    browser.close()


with sync_playwright() as p:
  crawl(p)
