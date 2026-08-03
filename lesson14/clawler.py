import asyncio
import os
import json
from pprint import pprint

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
          pprint(config_data)


if __name__ == "__main__":
  # 使用 asyncio.run() 啟動 Python Event Loop
  asyncio.run(main())
