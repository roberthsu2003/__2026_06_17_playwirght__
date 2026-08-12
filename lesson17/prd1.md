# 🎨 產品需求規格書 (PRD) - practice5.py
> **專案目標**：將 [practice4.py](file:///Users/roberthsu2003/Documents/GitHub/2026_06_17_playwright/lesson17/practice4.py) 的 CLI 功能升級為現代化桌面 GUI 應用程式 ([practice5.py](file:///Users/roberthsu2003/Documents/GitHub/2026_06_17_playwright/lesson17/practice4.py))。  
> **核心技術**：Python 3.10+, **PySide6** (`QtWidgets`, `QtGui`, `QtCore`), **Qt Graphics View Framework** (`QGraphicsView`, `QGraphicsScene`, `QGraphicsItem`, `QPropertyAnimation`), `twstock`, `yfinance`, `pandas`。  
> **適用對象**：提供給 AI Coding Assistant 作為極為嚴謹且具體的 PySide6 GUI 與動態繪圖開發依據。

---

## 📌 1. 專案概述 (Overview)

### 1.1 背景與目的
本專案需延伸 `practice4.py` 的台股資訊查詢與歷史價格抓取邏輯，建構一個具有高視覺吸引力與流暢互動體驗的桌面端 GUI 軟體 `practice5.py`。
為了提供超越傳統靜態圖表的互動體驗，核心 K 線圖與成交量圖表必須採用 **Qt 的 Graphics View Framework (`QGraphicsView` / `QGraphicsScene`)** 自行繪製，並加入 **漸變渲染與流暢的展演動畫 (`QPropertyAnimation` / 動畫組)**。

### 1.2 執行環境與套件需求
- **環境**：`uv` 虛擬環境
- **必備套件**：
  - `PySide6` (Qt 官方 Python 綁定)
  - `twstock` (台股股票搜尋與產業別分類)
  - `yfinance` (歷史行情 K 線與成交量抓取)
  - `pandas` / `numpy` (數據處理與幾何座標計算)

---

## 🎯 2. GUI 畫面佈局與控制元件 (GUI Layout Specification)

整體視窗採用 `QMainWindow`，尺寸預設為 `1280x800`，結構分為三大區塊：

```text
+-----------------------------------------------------------------------------------+
| 🔍 控制面板 (Top Control Bar)                                                      |
| 關鍵字: [  2330  ] 產業: [半導體▼] 時間: [1個月▼] [ 🚀 查詢行情 ]  狀態: [ 準備就緒 ] |
+---------------------------------------------------+-------------------------------+
| 📊 繪圖區域 (Qt Graphics View)                    | 📈 統計卡片與數據表格           |
| (QGraphicsView & QGraphicsScene)                  | [ 數據摘要面板 ]               |
| - 自訂繪製 K 線 (Candlestick Item)                | - 最高價 / 最低價 / 最新價    |
| - 包含成長/登場動態動畫                             | - 漲跌幅 / 日均成交量          |
| - 十字准星游標與動態 Hover Tooltip 浮動卡片          +-------------------------------+
|                                                   | 📝 歷史價格明細 (QTableWidget) |
|                                                   | 日期 | 開盤 | 最高 | 最低 | 收盤 | Volume|
+---------------------------------------------------+-------------------------------+
```

---

## 🎨 3. Qt Graphics View Framework 與動畫繪製規格 (Graphics & Animation Spec)

本專案的最重要亮點為使用 **Qt Graphics View Framework** 進行高自由度的 custom item 繪製與動畫控制，細節如下：

### 3.1 座標系與畫布設置 (`QGraphicsScene` / `QGraphicsView`)
- **圖形視圖 (`StockGraphicsView`)**：
  - 繼承自 `QGraphicsView`，開啟平滑抗鋸齒渲染 (`QPainter.RenderHint.Antialiasing`)。
  - 支援滑鼠滾輪縮放 (Zoom In/Out) 與按住拖曳 (Pan/Scroll)。
  - 支援滑鼠移動監聽，實作動態十字準星線 (`QGraphicsLineItem`) 與懸浮資訊卡片 (`TooltipItem`)。

### 3.2 自訂 K 線與成交量圖形項目 (`CandlestickGraphicsItem`)
- **台股顏色規範**：
  - 上漲 (`Close > Open`)：標誌性紅色 (`#E74C3C`)，實心或高亮填滿。
  - 下跌 (`Close < Open`)：標誌性綠色或藍色 (`#2ECC71`)，實心填滿。
  - 平盤 (`Close == Open`)：灰色 (`#95A5A6`)。
- **繪圖邏輯**：
  - 上下影線 (`QGraphicsLineItem`)：連接 最高價 (High) 與 最低價 (Low)。
  - 實體柱狀體 (`QGraphicsRectItem`)：開盤價 (Open) 與 收盤價 (Close) 形成之矩形。
  - 下方成交量柱 (Volume Bar)：對應當天成交量，垂直對齊於 K 線下方。

### 3.3 動畫效果規格 (Animation Requirements)
載入或切換股票歷史數據時，必須觸發以下動畫：
1. **K 線柱狀圖登場成長動畫 (`QPropertyAnimation`)**：
   - 每個 K 線與成交量柱狀體在繪製完成後，其高度從 `0` 經由 `QEasingCurve.Type.OutCubic` 緩動效果延伸成長至實際目標高度（動畫時間：約 `600ms`）。
2. **動態淡入效果 (Fade-in / Opacity Animation)**：
   - Scene 上的 Item 初始透明度為 `0.0`，在 `300ms` 內平滑漸變至 `1.0`。
3. **懸浮提示卡片 (Tooltip) 平滑跟隨**：
   - 滑鼠移動至某日 K 線上時，彈出氣泡卡片並以平滑移動顯示當日 Open, High, Low, Close, Volume。

---

## ⚡ 4. 多執行緒與效能架構 (Multithreading & Responsiveness)

為避免 API 網路請求（`yfinance` / `twstock`）導致 GUI 視窗「無回應 (Not Responding)」或畫面凍結，必須採用 `QThread` / `QObject` 異步處理機制：

1. **背景資料下載工作器 (`StockDataWorker`)**：
   - 繼承自 `QThread` 或使用 `QRunnable` + `QThreadPool`。
   - 負責執行 `search_stock()`、`filter_by_group()` 及 `fetch_stock_history()`。
2. **Signal / Slot 信號槽機制**：
   - `started_signal`: 觸發主視窗進度條 `QProgressBar` 開始轉動。
   - `finished_signal(stock_info, summary_dict, df)`: 將抓取好的資料安全傳回主 UI 執行緒進行 UI 更新與動畫播送。
   - `error_signal(err_msg)`: 當網路失敗或股票代號無效時，傳回錯誤訊息並跳出 QMessageBox 提示。

---

## 🛠️ 5. 程式碼結構與類別設計 (Architecture & Code Design)

請執行模型嚴格遵循以下架構構建 [practice5.py](file:///Users/roberthsu2003/Documents/GitHub/2026_06_17_playwright/lesson17/practice5.py)：

```python
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLineEdit, QComboBox, QPushButton, QLabel, QTableWidget,
    QTableWidgetItem, QGraphicsView, QGraphicsScene, QGraphicsItem,
    QGraphicsRectItem, QGraphicsLineItem, QGraphicsTextItem, QMessageBox, QProgressBar
)
from PySide6.QtCore import Qt, QThread, Signal, QRectF, QPointF, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor, QPen, QBrush, QPainter, QFont

# 1. 繼承 practice4.py 的數據模型與核心運算 logic
from practice4 import StockInfo, search_stock, filter_by_group, fetch_stock_history, calculate_summary

# 2. 背景工作線程
class FetchDataWorker(QThread):
    data_loaded = Signal(object, dict, object) # stock, summary, df
    error_occurred = Signal(str)

    def __init__(self, yf_symbol: str, period: str, start: str = None, end: str = None):
        super().__init__()
        # 儲存查詢參數...

    def run(self):
        # 執行背景 API 呼叫，完成後發送 data_loaded 信號

# 3. Qt Graphics View 自訂繪圖類別
class CandlestickGraphicsView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)

    def draw_chart_with_animation(self, df: pd.DataFrame):
        """清除舊圖形，重新計算幾何座標並播送 K 線登場動畫"""
        pass

# 4. 主視窗
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("📈 台股行情分析與繪圖系統 (PySide6 Graphics View)")
        self.resize(1280, 800)
        self.init_ui()

    def init_ui(self):
        # 建立操控列、Splitter、QGraphicsView 與 QTableWidget
        pass
```

---

## 🛡️ 6. 邊界條件與體驗要求 (User Experience & Edge Cases)

1. **查無資料防禦**：
   - 下載數據失敗時，`QGraphicsView` 畫面應繪製提示文字 `「⚠️ 無法取得行情資料」`，且表格清空，非程式崩潰。
2. **圖表縮放與邊界限制**：
   - 繪製 K 線時，需根據畫畫的高寬度自動做坐標縮放（Scale Y 軸為最高/最低價區間，X 軸依交易日平分）。
3. **記憶體管理**：
   - 每次載入新股票時，呼叫 `self.scene.clear()` 釋放舊有的 `QGraphicsItem` 與動畫記憶體，避免記憶體洩漏。

---

## 🧪 7. 驗收標準與測試執行指令 (Acceptance Criteria)

實作模型編寫完 `practice5.py` 後，需通過以下測試：

1. **GUI 成功啟動**：
   執行 `uv run python lesson17/practice5.py` 成功跳出 1280x800 視窗，且無 Console 報錯。
2. **多執行緒防凍結驗證**：
   按下「查詢」時，主 UI 保持可點擊/移動狀態，進度條正常運作。
3. **Graphics View 動畫驗證**：
   K 線圖繪製時具備動態伸展登場動畫，滑鼠移動於圖形上有十字線與資訊 Tooltip。

---

## 📁 8. 產出檔案路徑
- **目標 GUI 程式**：[lesson17/practice5.py](file:///Users/roberthsu2003/Documents/GitHub/2026_06_17_playwright/lesson17/practice5.py)
- **PRD 規格檔案**：[lesson17/prd1.md](file:///Users/roberthsu2003/Documents/GitHub/2026_06_17_playwright/lesson17/prd1.md)
