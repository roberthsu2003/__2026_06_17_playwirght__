from playwright.sync_api import sync_playwright,Playwright,Browser,Page
import os

def  element_location_demo(p:Playwright):
  browser:Browser = p.chromium.launch(headless=False)
  page:Page = browser.new_page()

  # 取得當前檔案的絕對路徑
  current_dir:str = os.path.dirname(os.path.abspath(__file__))
  html_file = os.path.join(current_dir, "login_demo.html")

  # 開啟本地 HTML 檔案
  page.goto(f"file://{html_file}")
  print("✓ 已開啟登入頁面")

  browser.close()

if __name__ == "__main__":
  print("=" * 60)
  print("Playwright 元素定位示範")
  print("=" * 60)
  with sync_playwright() as p:
    element_location_demo(p)
  print("\n" + "=" * 60)
  print("示範完成")
  print("=" * 60)
