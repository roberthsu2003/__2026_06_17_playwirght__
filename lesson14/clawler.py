import asyncio
import os
import json,datetime
from pprint import pprint
from playwright.async_api import async_playwright,Browser,BrowserContext

# ==============================================================================
# 0. 專案全域變數設定 (Global Configurations)
# ==============================================================================
CONFIG_FILE = "products_config.json" # 商品與賣場組態設定檔

async def main():
  print("=" * 80)
  print("毛寶企業 (Maobao) 多賣場產品與競品價格每日監控系統 [Playwright Async版]")
  print("=" * 80)

  # 1. 檢查並讀取 JSON 組態檔 (展現組態驅動設計 Configuration-Driven)
  if not os.path.exists(CONFIG_FILE):
      print(f"❌ 找不到設定檔：{CONFIG_FILE}")
      return

  with open(CONFIG_FILE, "r", encoding="utf-8") as f:
      config_data = json.load(f)
      #pprint(config_data)

      categories:list[dict] = config_data.get("monitor_products", [])
      #pprint(categories)
      platforms:list[dict] = config_data.get("platforms", [])
      platform_names = [p["name"] for p in platforms]
      #print(platform_names)
      print(f"📦 載入設定完成！監控 {len(categories)} 大品類，跨賣場：{', '.join(platform_names)}...\n")

      start_time = datetime.now()

      # 2. 啟動 Playwright Async 引擎與 BrowserContext (瀏覽器上下文)
      async with async_playwright() as p:
        # headless=True 以背景模式執行（可設定 headless=False 觀察瀏覽器自動化操作過程）
        browser:Browser = await p.firefox.launch(headless=True)

        # 建立全局 Context，注入通用 User-Agent 與 Viewport
        context:BrowserContext = await browser.new_context(
          viewport={"width": 1280, "height": 720},
          user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
        )



if __name__ == "__main__":
  # 使用 asyncio.run() 啟動 Python Event Loop
  asyncio.run(main())
