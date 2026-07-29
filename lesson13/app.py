import argparse
from playwright.sync_api import sync_playwright
import crawler

STATIONS = {
    "南港": "NanGang", "台北": "TaiPei", "板橋": "BanQiao",
    "桃園": "TaoYuan", "新竹": "XinZhu", "苗栗": "MiaoLi",
    "台中": "TaiZhong", "彰化": "ZhangHua", "雲林": "YunLin",
    "嘉義": "JiaYi", "台南": "TaiNan", "左營": "ZuoYing",
}

COOKIES_FILE = "thsrc_cookies.json"

if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="高鐵時刻表查詢")
  parser.add_argument("departure", nargs="?", default="台北",
                      help="出發站 (預設: 台北)")
  parser.add_argument("arrival", nargs="?", default="台中",
                      help="到達站 (預設: 台中)")
  args = parser.parse_args()

  if args.departure not in STATIONS:
    print(f"錯誤：不支援的出發站「{args.departure}」")
    print(f"可用車站：{'、'.join(STATIONS)}")
    exit(1)
  if args.arrival not in STATIONS:
    print(f"錯誤：不支援的到達站「{args.arrival}」")
    print(f"可用車站：{'、'.join(STATIONS)}")
    exit(1)
  if args.departure == args.arrival:
    print("錯誤：出發站與到達站不能相同")
    exit(1)

  with sync_playwright() as p:
    crawler.crawl(p=p, cookies_file=COOKIES_FILE, headless=False,
                  departure_station=args.departure,
                  arrival_station=args.arrival)
