import asyncio
import os
from datetime import datetime
from typing import List

from playwright.async_api import async_playwright, Browser, BrowserContext
from models.data_models import CategoryScan, ProductScan, StoreInfo
from platforms.pchome_platform import PChomePlatform
from platforms.momo_platform import MomoPlatform
from platforms.yahoo_platform import YahooPlatform

from utils.io_helper import load_config, save_json_report
from utils.reporter import format_console_report, format_markdown_report

# Constants
CONFIG_FILE = "products_config.json"
REPORT_JSON = "price_report.json"
REPORT_MD = "price_report.md"

async def fetch_item_across_platforms(context: BrowserContext, brand: str, name: str, keyword: str) -> ProductScan:
    # 使用具體的平台實作物件 (這裡可以用 Factory Pattern 來生成，現在直接建立)
    pchome = PChomePlatform()
    momo = MomoPlatform()
    yahoo = YahooPlatform()

    # 將任務放入列表
    tasks = [
        pchome.fetch(context, keyword),
        momo.fetch(context, keyword),
        yahoo.fetch(context, keyword)
    ]
    
    store_results = await asyncio.gather(*tasks, return_exceptions=True)
    # 過濾掉 Exception
    valid_results = [r for r in store_results if isinstance(r, StoreInfo)]

    return ProductScan(brand=brand, name=name, keyword=keyword, stores=valid_results)

async def monitor_category_async(context: BrowserContext, category_item: dict) -> CategoryScan:
    category_name = category_item["category"]
    maobao_cfg = category_item["maobao_product"]
    competitors_cfg = category_item["competitors"]

    print(f"🚀 開始平行併發查詢品類：【{category_name}】跨賣場數據...")

    # 建立任務列表
    tasks = [
        fetch_item_across_platforms(context, "毛寶", maobao_cfg["name"], maobao_cfg["keyword"])
    ]

    for comp in competitors_cfg:
        tasks.append(fetch_item_across_platforms(context, comp["brand"], comp["name"], comp["keyword"]))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    valid_results = [r for r in results if isinstance(r, ProductScan)]

    return CategoryScan(
        category=category_name,
        maobao_product=valid_results[0],
        competitors=valid_results[1:]
    )

async def main():
    print("=" * 80)
    print("毛寶企業 (Maobao) 多賣場產品與競品價格每日監控系統 [Playwright Async 重構版]")
    print("=" * 80)

    # 1. 載入組態
    try:
        config_data = load_config(CONFIG_FILE)
    except Exception as e:
        print(f"❌ {e}")
        return

    categories = config_data.get("monitor_products", [])
    platforms_info = config_data.get("platforms", [])
    platform_names = [p["name"] for p in platforms_info]
    print(f"📦 載入設定完成！監控 {len(categories)} 大品類，跨賣場：{', '.join(platform_names)}...\n")

    start_time = datetime.now()

    # 2. 執行抓取流程
    async with async_playwright() as p:
        browser: Browser = await p.firefox.launch(headless=True)
        context: BrowserContext = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
        )

        cat_tasks = [monitor_category_async(context, cat) for cat in categories]
        all_results_raw = await asyncio.gather(*cat_tasks, return_exceptions=True)
        # 將結果轉為 CategoryScan 物件列表
        all_results: List[CategoryScan] = []
        for r in all_results_raw:
            if isinstance(r, CategoryScan):
                all_results.append(r)
        
        await context.close()
        await browser.close()

    elapsed = (datetime.now() - start_time).total_seconds()
    print("\n" + "=" * 80)
    print(f"✓ 所有品類跨賣場抓取完成！總耗時僅：{elapsed:.2f} 秒 (非同步併發加速)")
    print("=" * 80)

    # 3. Console Output 報表
    format_console_report(all_results)

    # 4. JSON Export
    report_json_data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_seconds": round(elapsed, 2),
        "platforms": platform_names,
        "note": "單位與包裝規格不同，無輸出價差比較與優勢分析",
        "data": [
            {
                "category": c.category,
                "maobao_product": {
                    "brand": c.maobao_product.brand,
                    "name": c.maobao_product.name,
                    "keyword": c.maobao_product.keyword,
                    "stores": [
                        {"platform": s.platform, "title": s.title, "price": s.price, "url": s.url, "status": s.status} 
                        for s in c.maobao_product.stores
                    ]
                },
                "competitors": [
                    {
                        "brand": comp.brand,
                        "name": comp.name,
                        "keyword": comp.keyword,
                        "stores": [
                            {"platform": s.platform, "title": s.title, "price": s.price, "url": s.url, "status": s.status} 
                            for s in comp.stores
                        ]
                    } for comp in c.competitors
                ]
            } for c in all_results
        ]
    }
    save_json_report(REPORT_JSON, report_json_data)
    print(f"\n✓ 已匯出 JSON 詳細數據：{REPORT_JSON}")

    # 5. Markdown Export
    md_content = format_markdown_report(all_results, platform_names, elapsed)
    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"✓ 已匯出 Markdown 分析報告：{REPORT_MD}")

if __name__ == "__main__":
    asyncio.run(main())
