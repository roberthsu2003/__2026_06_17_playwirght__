from playwright.sync_api import sync_playwright,Playwright,Browser,Page


def crawl(p:Playwright) -> None:
  browser:Browser = p.chromium.launch()
  page:Page = browser.new_page()
  page.goto("https://zh.wikipedia.org")
  page.locator("#searchInput").fill("臺灣")
  page.screenshot(path="screenshot.png")
  page.keyboard.press("Enter")
  page.wait_for_load_state("networkidle")
  first_heading:str = page.locator("#firstHeading").inner_text()
  print(f"搜尋主題:{first_heading}")

  content:str = page.locator("#mw-content-text p").first.inner_text()
  print(f"摘要: {content[:100]}")
  page.go_back()
  page.wait_for_load_state("networkidle")
  print(f"返品首頁:{page.title()}")
  browser.close()


with sync_playwright() as p:
  crawl(p)
