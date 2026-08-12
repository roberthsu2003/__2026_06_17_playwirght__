# 📄 產品需求規格書 (PRD) - practice4.py
> **專案目標**：打造一個模組化、高健壯性且具備良好使用者體驗的台股股票查詢與歷史價格擷取 CLI 終端機應用程式 ([practice4.py](file:///Users/roberthsu2003/Documents/GitHub/2026_06_17_playwright/lesson17/practice4.py))。  
> **適用對象**：提供給 AI Coding Assistant (如 LLM Code Generator) 作為精確的實作開發依據。

---

## 📌 1. 專案概述 (Overview)

### 1.1 背景與目的
本專案需將 `twstock`（台股基本資訊與產業別查詢）與 `yfinance`（美國雅虎財經歷史價格下載）兩大套件整合至單一 Python 腳本 `practice4.py` 中。程式應以非 Notebook 的獨立 CLI (Command Line Interface) 腳本形式運作，提供清晰的選單導覽、強健的錯誤處理以及易讀的數據格式化輸出。

### 1.2 執行環境與依賴套件
- **執行工具/環境**：`uv` (Python 虛擬環境與套件管理工具)
- **依賴套件 (Dependencies)**：
  - `twstock` (用於查詢股票名稱、代碼、上市/上櫃與產業分類)
  - `yfinance` (用於下載歷史 K 線價格與成交量)
  - `pandas` (用於資料清理、計算與統計)
  - `typing` / `dataclasses` (Python 標準庫，用於型態標註與資料結構封裝)

---

## 🎯 2. 系統功能規格 (Functional Specifications)

### 2.1 股票資訊查詢模組 (`twstock` 整合)

1. **個股搜尋 (`search_stock_by_keyword`)**：
   - 支援「股票代碼」（如 `2330`）與「股票名稱」（如 `台積電` 或模糊匹配 `積`）。
   - 從 `twstock.codes` 字典檢索，需擷取以下欄位：
     - `code`: 股票代碼 (e.g., `'2330'`)
     - `name`: 股票名稱 (e.g., `'台積電'`)
     - `market`: 市場類別 (e.g., `'上市'`, `'上櫃'`, `'興櫃'`)
     - `group`: 產業類別 (e.g., `'半導體業'`)
2. **產業別篩選 (`filter_stocks_by_group`)**：
   - 輸入產業關鍵字（如 `半導體`、`金融`、`航運`、`電子`）。
   - 搜尋 `info.group` 中包含該關鍵字的所有股票，回傳清單並以格式化表格列出。
3. **市場類別字尾對應轉換 (`get_yfinance_ticker`)**：
   - 上市股票 (`market == "上市"`)：加上 `.TW`（例如：`2330.TW`）。
   - 上櫃股票 (`market == "上櫃"`)：加上 `.TWO`（例如：`8454.TWO`）。
   - 興櫃或其他預設情況：預設為 `.TW`，並於下載失敗時提示使用者。

---

### 2.2 歷史數據下載與統計模組 (`yfinance` 整合)

1. **數據下載 (`fetch_historical_data`)**：
   - 支援兩種時間選擇模式：
     - **模式 A：相對時間選單** (選擇 `1mo`, `3mo`, `6mo`, `1y`, `2y`, `5y`)
     - **模式 B：自訂日期範圍** (輸入起始日期 `YYYY-MM-DD` 與結束日期 `YYYY-MM-DD`)
   - 使用 `yf.Ticker(symbol).history(...)` 或 `yf.download(...)` 抓取資料。
2. **數據處理與統計計算 (`calculate_summary`)**：
   - 當抓取到 DataFrame 時，應進行以下統計計算：
     - **起始/結束日期** (Start / End Date)
     - **總交易日天數** (Total Trading Days)
     - **期間最高價** (Highest High Price) 及對應日期
     - **期間最低價** (Lowest Low Price) 及對應日期
     - **平均收盤價** (Average Close Price)
     - **最新收盤價** (Latest Close Price)
     - **總成交量 / 日平均成交量** (Total & Average Volume)
     - **期間漲跌幅 (%)**：`((最新收盤價 - 首日開盤價) / 首日開盤價) * 100`

---

### 2.3 CLI 選單與互動介面 (User Interface Workflow)

#### 主選單 (Main Menu) 結構：
```text
==================================================
  📈 台股股票查詢與歷史行情分析系統 (practice4.py)
==================================================
  [1] 搜尋股票代碼 / 名稱
  [2] 依產業別篩選股票
  [3] 抓取指定個股歷史價格
  [4] 一鍵式個股搜尋與行情分析 (整合流程)
  [0] 結束程式
==================================================
請輸入選項 [0-4]: 
```

#### 選項 [4] 一鍵整合流程規格：
1. 提示使用者輸入股票代號或名稱。
2. 顯示搜尋結果並確認個股。
3. 提示選擇時間範圍（快捷時間或自訂日期）。
4. 自動發送請求並下載 `yfinance` 行情。
5. 印出多欄位統計摘要說明與前/後 5 筆價格數據表格。
6. 詢問是否繼續查詢其他股票或返回主選單。

---

## 🛠️ 3. 詳細類別與函式規格 (Technical Architecture)

請執行模型嚴格遵循以下 dataclass 與函式簽名定義進行程式碼實作：

```python
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
    from_twstock(cls, code: str, info: Any) -> "StockInfo":
        """將 twstock code info 轉換為 StockInfo dataclass"""
        # 邏輯：上市 -> .TW, 上櫃 -> .TWO, 其餘 -> .TW
        suffix = ".TW"
        if hasattr(info, 'market'):
            if "上櫃" in info.market:
                suffix = ".TWO"
        yf_symbol = f"{code}{suffix}"
        return cls(
            code=code,
            name=getattr(info, 'name', '未知'),
            market=getattr(info, 'market', '未知'),
            group=getattr(info, 'group', '未知'),
            yf_symbol=yf_symbol
        )

def search_stock(keyword: str) -> List[StockInfo]:
    """
    搜尋股票名稱或代碼
    :param keyword: 使用者輸入之代碼或關鍵字
    :return: 匹配的 StockInfo 物件串列
    """
    pass

def filter_by_group(group_name: str) -> List[StockInfo]:
    """
    依產業類別關鍵字搜尋股票
    :param group_name: 產業關鍵字 (如 '半導體')
    :return: 匹配的 StockInfo 物件串列
    """
    pass

def fetch_stock_history(
    yf_symbol: str, 
    period: Optional[str] = "1mo", 
    start_date: Optional[str] = None, 
    end_date: Optional[str] = None
) -> Optional[pd.DataFrame]:
    """
    向 yfinance 抓取股票歷史行情 DataFrame
    :param yf_symbol: yfinance 代號 (如 '2330.TW')
    :param period: 相對時間 (1mo, 3mo, 6mo, 1y, 2y)
    :param start_date: 自訂起始日期 (YYYY-MM-DD)
    :param end_date: 自訂結束日期 (YYYY-MM-DD)
    :return: pandas DataFrame 或 None (失敗時)
    """
    pass

def calculate_summary(df: pd.DataFrame) -> Dict[str, Any]:
    """
    計算 DataFrame 的統計數據摘要
    :return: 包含 highest_price, lowest_price, avg_close, latest_close, pct_change 等欄位的字典
    """
    pass

def print_summary_report(stock: StockInfo, summary: Dict[str, Any], df: pd.DataFrame) -> None:
    """
    格式化印出終端機日報表格與前/後數據
    """
    pass

def main():
    """CLI 主選單互動迴圈"""
    pass
```

---

## 🛡️ 4. 邊界條件與例外處理 (Error Handling & Edge Cases)

實作 `practice4.py` 時必須包含以下容錯機制：

1. **查無股票關鍵字**：
   - 使用者輸入不存在的代碼或名稱時，顯示 `⚠️ 查無符合「{keyword}」的股票，請重新輸入。`。
2. **yfinance 下載失敗或資料為空**：
   - 當 `df.empty` 或網路請求異常時，不應讓程式 Crash。
   - 捕捉 `Exception`，並輸出 `❌ 數據下載失敗！請確認股票代號是否正確（例如興櫃股票可能無 Yahoo 數據）。`。
3. **日期格式輸入錯誤**：
   - 提示使用者輸入 `YYYY-MM-DD` 格式，若格式不符（如 `2026/01/01`），自動抓取 `ValueError` 並提示重新輸入。
4. **選單輸入無效選項**：
   - 當輸入非選單數字時（如字母或超出範圍的數字），提示 `⚠️ 無效選項，請輸入數字 0~4`。
5. **預防兩次字尾加疊**：
   - 當使用者手動輸入 `2330.TW` 時，自動識別並清除重複的 `.TW` / `.TWO` 避免產生 `2330.TW.TW` 錯誤。

---

## 🧪 5. 驗證與測試需求 (Verification & Acceptance Criteria)

負責撰寫 `practice4.py` 的模型需在編寫完成後，執行以下測試驗證：

1. **語法與執行測試**：
   使用 `uv run python lesson17/practice4.py` 無語法錯誤且能成功啟動 CLI 介面。
2. **個股搜尋測試**：
   - 搜尋 `2330` 能正確顯示「2330 | 台積電 | 上市 | 半導體業 | 2330.TW」。
   - 搜尋 `8454` 能正確顯示上櫃與 `.TWO` 標籤。
3. **數據抓取測試**：
   - 輸入 `2330.TW` 選擇近 1 個月，能成功印出統計報告與歷史價格 DataFrame。
4. **優雅退出**：
   - 在主選單輸入 `0` 時能順利結束程式並印出 `👋 感謝使用，再見！`。

---

## 📁 6. 產出檔案路徑
- **目標原始碼檔案**：[lesson17/practice4.py](file:///Users/roberthsu2003/Documents/GitHub/2026_06_17_playwright/lesson17/practice4.py)
- **PRD 規格檔案**：[lesson17/prd.md](file:///Users/roberthsu2003/Documents/GitHub/2026_06_17_playwright/lesson17/prd.md)
