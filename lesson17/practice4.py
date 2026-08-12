from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import pandas as pd
import twstock
import yfinance as yf

@dataclass
class StockInfo:
    """股票基本資訊資料模型"""
    code: str
    name: str
    market: str
    group: str
    yf_symbol: str

    @classmethod
    def from_twstock(cls, code: str, info: Any) -> "StockInfo":
        """將 twstock 資料轉換為 StockInfo dataclass"""
        # 邏輯：上市 -> .TW, 上櫃 -> .TWO, 其餘預設 -> .TW
        market_val = getattr(info, 'market', '') if not isinstance(info, dict) else info.get('market', '')
        name_val = getattr(info, 'name', '未知') if not isinstance(info, dict) else info.get('name', '未知')
        group_val = getattr(info, 'group', '未知') if not isinstance(info, dict) else info.get('group', '未知')
        
        suffix = ".TW"
        if "上櫃" in market_val:
            suffix = ".TWO"
        
        yf_symbol = f"{code}{suffix}"
        return cls(
            code=code,
            name=name_val,
            market=market_val if market_val else '未知',
            group=group_val if group_val else '未知',
            yf_symbol=yf_symbol
        )

def search_stock(keyword: str) -> List[StockInfo]:
    """
    搜尋股票名稱或代碼
    :param keyword: 使用者輸入之代碼或關鍵字
    :return: 匹配的 StockInfo 物件串列
    """
    stocks_dict = twstock.codes
    results = []
    
    for code, info in stocks_dict.items():
        name = getattr(info, 'name', '') if not isinstance(info, dict) else info.get('name', '')
        if keyword == code or keyword in name:
            results.append(StockInfo.from_twstock(code, info))
    return results

def filter_by_group(group_name: str) -> List[StockInfo]:
    """
    依產業類別關鍵字搜尋股票
    :param group_name: 產業關鍵字 (如 '半導體')
    :return: 匹配的 StockInfo 物件串列
    """
    stocks_dict = twstock.codes
    results = []
    for code, info in stocks_dict.items():
        group = getattr(info, 'group', '') if not isinstance(info, dict) else info.get('group', '')
        if group_name in group:
            results.append(StockInfo.from_twstock(code, info))
    return results

def fetch_stock_history(
    yf_symbol: str, 
    period: Optional[str] = "1mo", 
    start_date: Optional[str] = None, 
    end_date: Optional[str] = None
) -> Optional[pd.DataFrame]:
    """
    向 yfinance 抓取股票歷史行情 DataFrame
    """
    # 先清除可能重複的字尾
    clean_symbol = yf_symbol.replace(".TW.TW", ".TW").replace(".TWO.TWO", ".TWO")
    
    try:
        ticker = yf.Ticker(clean_symbol)
        if start_date and end_date:
            df = ticker.history(start=start_date, end=end_date)
        else:
            df = ticker.history(period=period)

        if df.empty:
            return None
        return df
    except Exception:
        return None

def calculate_summary(df: pd.DataFrame) -> Dict[str, Any]:
    """
    計算 DataFrame 的統計數據摘要
    """
    if df.empty:
        return {}

    # 取得首日開盤價用來計算漲跌幅
    first_open = df['Open'].iloc[0]
    latest_close = df['Close'].iloc[-1]
    
    summary = {
        "start_date": df.index[0].strftime('%Y-%m-%d'),
        "end_date": df.index[-1].strftime('%Y-%m-%d'),
        "total_days": len(df),
        "high_price": df['High'].max(),
        "high_date": df.loc[df['High'].idxmax()].name.strftime('%Y-%m-%d'),
        "low_price": df['Low'].min(),
        "low_date": df.loc[df['Low'].idxmin()].name.strftime('%Y-%m-%d'),
        "avg_close": df['Close'].mean(),
        "latest_close": latest_close,
        "total_volume": df['Volume'].sum(),
        "avg_volume": df['Volume'].mean(),
        "pct_change": ((latest_close - first_open) / first_open) * 100
    }
    return summary

def print_summary_report(stock: StockInfo, summary: Dict[str, Any], df: pd.DataFrame) -> None:
    """
    格式化印出終端機日報表格與前/後數據
    """
    print(f"\n📊 📈 {stock.name} ({stock.code}) 歷史行情統計摘要")
    print(f"📅 時間範圍: {summary['start_date']} ~ {summary['end_date']}")
    print("-" * 50)
    print(f"🔹 總交易日數    : {summary['total_days']} 日")
    print(f"🔹 最高價        : {summary['high_price']:.2f} (日期: {summary['high_date']})")
    print(f"🔹 最低價        : {summary['low_price']:.2f} (日期: {summary['low_date']})")
    print(f"🔹 平均收盤價    : {summary['avg_close']:.2f}")
    print(f"🔹 最新收盤價    : {summary['latest_close']:.2f}")
    print(f"🔹 總成交量      : {summary['total_volume']:,.0f}")
    print(f"🔹 日平均成交量  : {summary['avg_volume']:,.0f}")
    print(f"🔹 期間漲跌幅    : {summary['pct_change']:.2f}%")
    print("-" * 50)
    print("📝 價格數據預覽 (前 5 筆):")
    print(df.head().to_string())
    print("\n📝 價格數據預覽 (後 5 筆):")
    print(df.tail().to_string())
    print("-" * 50)

def get_valid_date(prompt: str) -> str:
    """確保使用者輸入符合 YYYY-MM-DD 格式的日期"""
    while True:
        date_str = input(prompt).strip()
        try:
            pd.to_datetime(date_str, format='%Y-%m-%d')
            return date_str
        except ValueError:
            print("⚠️ 日期格式錯誤，請使用 YYYY-MM-DD 格式 (例如: 2023-01-01)")

def main():
    """CLI 主選單互動迴圈"""
    print("⏳ 正在載入股票清單，請稍候...")
    try:
        stocks_dict = twstock.codes
        print("✅ 載入完成！\n")
    except Exception as e:
        print(f"❌ 讀取資料失敗: {e}")
        return

    while True:
        print("\n==================================================")
        print("  📈 台股股票查詢與歷史行情分析系統 (practice4.py)")
        print("==================================================")
        print("  [1] 搜尋股票代碼 / 名稱")
        print("  [2] 依產業別篩選股票")
        print("  [3] 抓取指定個股歷史價格")
        print("  [4] 一鍵式個股搜尋與行情分析 (整合流程)")
        print("  [0] 結束程式")
        print("==================================================")
        
        choice = input("請輸入選項 [0-4]: ").strip()

        if choice == '1':
            keyword = input("請輸入代號或名稱關鍵字: ").strip()
            results = search_stock(keyword)
            if not results:
                print(f"⚠️ 查無符合「{keyword}」的股票，請重新輸入。")
            else:
                for s in results:
                    print(f"🔍 {s.code} | {s.name} | {s.market} | {s.group} | {s.yf_symbol}")

        elif choice == '2':
            group_kw = input("請輸入產業關鍵字 (例如: 半導體): ").strip()
            results = filter_by_group(group_kw)
            if not results:
                print(f"⚠️ 查無符合「{group_kw}」的產業資訊。")
            else:
                print(f"\n✅ '{group_kw}' 產業下的股票清單：")
                for s in results:
                    print(f"- {s.code} | {s.name} ({s.market})")

        elif choice == '3':
            code = input("請輸入股票代號 (例如: 2330): ").strip()
            # 清除可能重複的字尾 (.TW) 以避免之後加上倍增
            code = code.replace(".TW", "").replace(".TWO", "")
            
            stocks_dict = twstock.codes
            if code not in stocks_dict:
                print(f"⚠️ 查無符合「{code}」的股票，請重新輸入。")
                continue
            
            stock = StockInfo.from_twstock(code, stocks_dict[code])
            
            print(f"\n確認個股: {stock.name} ({stock.yf_symbol})")
            print("選擇時間範圍:")
            print("  [1] 過去 1 個月 (1mo)")
            print("  [2] 過去 3 個月 (3mo)")
            print("  [3] 過去 6 個月 (6mo)")
            print("  [4] 過去 1 年 (1y)")
            print("  [5] 自訂日期範圍")
            time_choice = input("請選擇 [1-5]: ").strip()

            df = None
            if time_choice == '1':
                df = fetch_stock_history(stock.yf_symbol, period="1mo")
            elif time_choice == '2':
                df = fetch_stock_history(stock.yf_symbol, period="3mo")
            elif time_choice == '3':
                df = fetch_stock_history(stock.yf_symbol, period="6mo")
            elif time_choice == '4':
                df = fetch_stock_history(stock.yf_symbol, period="1y")
            elif time_choice == '5':
                start = get_valid_date("請輸入起始日期 (YYYY-MM-DD): ")
                end = get_valid_date("請輸入結束日期 (YYYY-MM-DD): ")
                df = fetch_stock_history(stock.yf_symbol, start_date=start, end_date=end)
            else:
                print("⚠️ 無效選項")

            if df is not None and not df.empty:
                summary = calculate_summary(df)
                print_summary_report(stock, summary, df)
            else:
                print(f"❌ 數據下載失敗！請確認股票代號是否正確（例如興櫃股票可能無 Yahoo 數據）。")

        elif choice == '4':
            keyword = input("請輸入股票代號或名稱: ").strip()
            results = search_stock(keyword)
            if not results:
                print(f"⚠️ 查無符合「{keyword}」的股票，請重新輸入。")
                continue
            
            # 取第一個搜尋結果作為確認對象
            target_stock = results[0]
            print(f"\n✅ 已找到: {target_stock.name} ({target_stock.code})")
            print("請選擇時間範圍:")
            print("  [1] 過去 1 個月 (1mo)")
            print("  [2] 過去 3 個月 (3mo)")
            print("  [3] 過去 6 個月 (6mo)")
            print("  [4] 過去 1 年 (1y)")
            print("  [5] 自訂日期範圍")
            time_choice = input("請選擇 [1-5]: ").strip()

            df = None
            if time_choice == '1':
                df = fetch_stock_history(target_stock.yf_symbol, period="1mo")
            elif time_choice == '2':
                df = fetch_stock_history(target_stock.yf_symbol, period="3mo")
            elif time_choice == '3':
                df = fetch_stock_history(target_stock.yf_symbol, period="6mo")
            elif time_choice == '4':
                df = fetch_stock_history(target_stock.yf_symbol, period="1y")
            elif time_choice == '5':
                start = get_valid_date("請輸入起始日期 (YYYY-MM-DD): ")
                end = get_valid_date("請輸入結束日期 (YYYY-MM-DD): ")
                df = fetch_stock_history(target_stock.yf_symbol, start_date=start, end_date=end)

            if df is not None and not df.empty:
                summary = calculate_summary(df)
                print_summary_report(target_stock, summary, df)
            else:
                print(f"❌ 數據下載失敗！請確認股票代號是否正確。")

            cont = input("\n是否繼續查詢其他股票? (y/n): ").lower()
            if cont != 'y':
                print("👋 感謝使用，再見！")
                break

        elif choice == '0':
            print("👋 感謝使用，再見！")
            break
        else:
            print("⚠️ 無效選項，請輸入數字 0~4")

if __name__ == "__main__":
    main()
