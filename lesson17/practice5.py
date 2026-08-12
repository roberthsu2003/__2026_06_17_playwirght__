"""
practice5.py (PRD3 終極整合版)
----------------------------------------
📈 台股雙引擎行情分析與批次爬蟲桌面系統
- Tab 1: 單股歷史折線分析 (yfinance + Qt Graphics View Framework)
- Tab 2: 批次即時爬蟲 (Async Playwright + QThread + asyncio)
- Tab 3: 資料庫與檔案匯出 (CSV / JSON)
"""

import sys
import asyncio
import datetime
import pandas as pd
from typing import List, Dict, Any

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLineEdit, QComboBox, QPushButton, QLabel, QTableWidget,
    QTableWidgetItem, QGraphicsView, QGraphicsScene,
    QGraphicsRectItem, QGraphicsLineItem, QGraphicsPathItem, QGraphicsEllipseItem,
    QGraphicsTextItem, QMessageBox, QProgressBar, QHeaderView, QSlider,
    QTabWidget, QGroupBox, QSpinBox, QListWidget, QListWidgetItem,
    QTextEdit, QFileDialog, QGridLayout
)
from PySide6.QtCore import (
    Qt, QThread, Signal, QTimer
)
from PySide6.QtGui import (
    QColor, QPen, QBrush, QPainter, QFont, QPainterPath, QLinearGradient
)

from practice4 import StockInfo, search_stock, fetch_stock_history, calculate_summary
from stock_batch_scraper import export_to_csv, export_to_json


# ======================================================================
# Phase 1: 歷史數據工作器 (Tab 1)
# ======================================================================
class FetchDataWorker(QThread):
    """背景資料下載工作器，避免 UI 凍結"""
    data_loaded = Signal(StockInfo, dict, pd.DataFrame)
    error_occurred = Signal(str)

    def __init__(self, query: str, period: str):
        super().__init__()
        self.query = query
        self.period = period

    def run(self):
        try:
            clean_query = self.query.strip().replace(".TW", "").replace(".TWO", "")
            results = search_stock(clean_query)

            if not results:
                raise ValueError(f"查無符合「{self.query}」的股票代碼或名稱。")

            stock = results[0]
            df = fetch_stock_history(stock.yf_symbol, period=self.period)

            if df is None or df.empty:
                alt_symbol = f"{stock.code}.TWO" if stock.yf_symbol.endswith(".TW") else f"{stock.code}.TW"
                df = fetch_stock_history(alt_symbol, period=self.period)
                if df is not None and not df.empty:
                    stock.yf_symbol = alt_symbol

            if df is None or df.empty:
                raise ValueError(f"無法取得「{stock.name} ({stock.yf_symbol})」的歷史行情數據。")

            summary = calculate_summary(df)
            self.data_loaded.emit(stock, summary, df)
        except Exception as e:
            self.error_occurred.emit(str(e))


# ======================================================================
# Phase 2: Playwright 異步執行緒背景工作器 (Tab 2)
# ======================================================================
class PlaywrightWorker(QThread):
    """Playwright 批次爬蟲工作器 (QThread + asyncio)"""
    single_stock_done = Signal(dict)     # 每完成一支股票發送一次 (即時更新表格)
    batch_finished = Signal(list)        # 批次全部完成，回傳完整 list[dict]
    progress_signal = Signal(int, int)   # completed_count, total_count
    log_signal = Signal(str)             # 日誌訊息
    error_signal = Signal(str)

    def __init__(self, stock_codes: List[str], max_concurrency: int = 3):
        super().__init__()
        self.stock_codes = stock_codes
        self.max_concurrency = max_concurrency
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        # 於獨立執行緒中建立新的 asyncio 事件迴圈執行 Playwright
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            results = loop.run_until_complete(self._async_batch_fetch())
            if not self._is_cancelled:
                self.batch_finished.emit(results)
            else:
                self.log_signal.emit("⏹️ 爬蟲作業已中止")
        except Exception as e:
            self.error_signal.emit(str(e))
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            loop.close()

    async def _async_batch_fetch(self) -> List[Dict]:
        from stock_batch_scraper import fetch_single_stock
        from playwright.async_api import async_playwright

        results: List[Dict] = []
        semaphore = asyncio.Semaphore(self.max_concurrency)
        total = len(self.stock_codes)
        completed = 0

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )

            async def worker(code: str):
                nonlocal completed
                async with semaphore:
                    if self._is_cancelled:
                        return None
                    self.log_signal.emit(f"⏳ [併行爬取中] 股票代碼: {code} ...")
                    data = await fetch_single_stock(context, code)
                    completed += 1
                    self.progress_signal.emit(completed, total)
                    self.single_stock_done.emit(data)
                    name = data.get("股票名稱", code)
                    price = data.get("即時價格", "N/A")
                    self.log_signal.emit(f"✅ [爬取成功] {name} ({code}): NT$ {price}")
                    await asyncio.sleep(0.5)
                    return data

            tasks = [asyncio.create_task(worker(c)) for c in self.stock_codes]

            # 持續等待全部完成，或被 cancel() 中止
            while True:
                done, pending = await asyncio.wait(tasks, timeout=0.2)
                if self._is_cancelled or not pending:
                    break

            if self._is_cancelled and pending:
                for t in pending:
                    t.cancel()
                await asyncio.gather(*pending, return_exceptions=True)

            for t in tasks:
                if t.cancelled():
                    continue
                try:
                    r = t.result()
                except asyncio.CancelledError:
                    continue
                if r is not None:
                    results.append(r)

            await browser.close()

        return results


# ======================================================================
# 收盤價折線圖畫布 (Qt Graphics View Framework)
# ======================================================================
class ClosePriceLineGraphicsView(QGraphicsView):
    """收盤價折線圖與動態互動畫布 (Qt Graphics View Framework)"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setMouseTracking(True)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

        self.df = None
        self.points_data = []
        self._anim_index = 0
        self._timer = None

        self.line_path_item = None
        self.gradient_path_item = None
        self.crosshair_line = None
        self.hover_circle = None
        self.tooltip_rect = None
        self.tooltip_text = None
        self.chart_mode = "line"
        self.on_point_selected_callback = None

    def clear_and_setup(self):
        if self._timer and self._timer.isActive():
            self._timer.stop()
        self.scene.clear()
        self.points_data.clear()
        self.crosshair_line = None
        self.hover_circle = None
        self.tooltip_rect = None
        self.tooltip_text = None

    def draw_chart(self, df: pd.DataFrame, chart_mode: str = "line"):
        self.df = df
        self.chart_mode = chart_mode
        self.clear_and_setup()

        if df.empty:
            return

        count = len(df)
        margin_left = 65
        margin_right = 35
        margin_top = 40
        margin_bottom = 50

        view_w = max(self.width(), 650)
        view_h = max(self.height(), 450)

        chart_w = view_w - margin_left - margin_right
        chart_h = view_h - margin_top - margin_bottom

        x_step = chart_w / max(count - 1, 1)

        if self.chart_mode == "line":
            y_min = df['Close'].min()
            y_max = df['Close'].max()
        else:
            y_min = df['Low'].min()
            y_max = df['High'].max()

        price_range = y_max - y_min if y_max != y_min else 1.0

        def map_y(val):
            return view_h - margin_bottom - ((val - y_min) / price_range * chart_h)

        # 1. 繪製背景參考網格與 Y 軸標籤
        grid_pen = QPen(QColor("#E9ECEF"), 1, Qt.PenStyle.DashLine)
        text_font = QFont("Arial", 9)

        for k in range(5):
            ratio = k / 4.0
            price_val = y_min + ratio * price_range
            y_pos = map_y(price_val)

            self.scene.addLine(margin_left, y_pos, view_w - margin_right, y_pos, grid_pen)

            txt = QGraphicsTextItem(f"{price_val:.1f}")
            txt.setFont(text_font)
            txt.setDefaultTextColor(QColor("#6C757D"))
            txt.setPos(5, y_pos - 10)
            self.scene.addItem(txt)

        # 2. 收集各交易日點位數據
        first_close = df['Close'].iloc[0]
        for i, (idx, row) in enumerate(df.iterrows()):
            x_pos = margin_left + i * x_step
            close_p = row['Close']
            y_pos = map_y(close_p)
            date_str = idx.strftime('%Y-%m-%d')
            chg = ((close_p - first_close) / first_close) * 100

            self.points_data.append({
                'index': i,
                'x': x_pos,
                'y': y_pos,
                'open': row['Open'],
                'close': close_p,
                'high': row['High'],
                'low': row['Low'],
                'y_open': map_y(row['Open']),
                'y_high': map_y(row['High']),
                'y_low': map_y(row['Low']),
                'date': date_str,
                'chg': chg,
                'volume': int(row['Volume'])
            })

        self.scene.setSceneRect(0, 0, view_w, view_h)

        if self.chart_mode == "line":
            # --- 📈 收盤價折線圖與漸層渲染 ---
            self.gradient_path_item = QGraphicsPathItem()
            self.line_path_item = QGraphicsPathItem()

            is_overall_up = df['Close'].iloc[-1] >= df['Close'].iloc[0]
            line_color = QColor("#E74C3C") if is_overall_up else QColor("#2ECC71")

            # 底層漸層畫筆
            grad = QLinearGradient(0, margin_top, 0, view_h - margin_bottom)
            grad_top = QColor(line_color)
            grad_top.setAlpha(70)
            grad_bottom = QColor(line_color)
            grad_bottom.setAlpha(5)
            grad.setColorAt(0.0, grad_top)
            grad.setColorAt(1.0, grad_bottom)

            self.gradient_path_item.setBrush(QBrush(grad))
            self.gradient_path_item.setPen(QPen(Qt.PenStyle.NoPen))

            line_pen = QPen(line_color, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            self.line_path_item.setPen(line_pen)

            self.scene.addItem(self.gradient_path_item)
            self.scene.addItem(self.line_path_item)

            # 開啟漸進登場動畫
            self._anim_index = 1
            self._timer = QTimer()
            self._timer.timeout.connect(self._run_line_anim)
            self._timer.start(16)
        else:
            # --- 📊 K 線圖模式 ---
            for p in self.points_data:
                is_up = p['close'] >= p['open']
                color = QColor("#E74C3C") if is_up else QColor("#2ECC71")
                self.scene.addLine(p['x'], p['y_high'], p['x'], p['y_low'], QPen(color, 1))
                w = max(x_step * 0.6, 3.0)
                top = min(p['y_open'], p['y'])
                h = max(abs(p['y_open'] - p['y']), 1.0)
                rect = QGraphicsRectItem(p['x'] - w/2, top, w, h)
                rect.setBrush(QBrush(color))
                rect.setPen(QPen(color, 1))
                self.scene.addItem(rect)

        # 3. 建立動態懸浮十字線、高亮焦點圓點與 Tooltip 卡片
        self.crosshair_line = QGraphicsLineItem()
        self.crosshair_line.setPen(QPen(QColor("#7F8C8D"), 1, Qt.PenStyle.DashLine))
        self.crosshair_line.setZValue(9)
        self.crosshair_line.setVisible(False)
        self.scene.addItem(self.crosshair_line)

        self.hover_circle = QGraphicsEllipseItem()
        self.hover_circle.setBrush(QBrush(QColor("#E74C3C")))
        self.hover_circle.setPen(QPen(QColor("#FFFFFF"), 2))
        self.hover_circle.setZValue(12)
        self.hover_circle.setVisible(False)
        self.scene.addItem(self.hover_circle)

        self.tooltip_rect = QGraphicsRectItem()
        self.tooltip_rect.setBrush(QBrush(QColor(33, 37, 41, 230)))
        self.tooltip_rect.setPen(QPen(Qt.PenStyle.NoPen))
        self.tooltip_rect.setZValue(10)
        self.tooltip_rect.setVisible(False)
        self.scene.addItem(self.tooltip_rect)

        self.tooltip_text = QGraphicsTextItem()
        self.tooltip_text.setDefaultTextColor(QColor("#FFFFFF"))
        self.tooltip_text.setFont(QFont("Arial", 9))
        self.tooltip_text.setZValue(11)
        self.tooltip_text.setVisible(False)
        self.scene.addItem(self.tooltip_text)

    def _run_line_anim(self):
        if not self.points_data or self._anim_index > len(self.points_data):
            if self._timer:
                self._timer.stop()
            return

        pts = self.points_data[:self._anim_index]
        self._anim_index += 3
        if self._anim_index > len(self.points_data):
            pts = self.points_data

        line_path = QPainterPath()
        line_path.moveTo(pts[0]['x'], pts[0]['y'])
        for p in pts[1:]:
            line_path.lineTo(p['x'], p['y'])

        base_y = self.height() - 50
        grad_path = QPainterPath(line_path)
        grad_path.lineTo(pts[-1]['x'], base_y)
        grad_path.lineTo(pts[0]['x'], base_y)
        grad_path.closeSubpath()

        self.line_path_item.setPath(line_path)
        self.gradient_path_item.setPath(grad_path)

    def update_cursor_at_index(self, index: int):
        if not self.points_data or index < 0 or index >= len(self.points_data):
            return
        p = self.points_data[index]
        self._update_highlight(p)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        if not self.points_data:
            return

        # 修正 PySide6 / Qt6 DeprecationWarning: 使用 event.position().toPoint() 替代 event.pos()
        pos = event.position().toPoint()
        mouse_x = self.mapToScene(pos).x()

        idx_closest, closest_p = min(enumerate(self.points_data), key=lambda item: abs(item[1]['x'] - mouse_x))
        self._update_highlight(closest_p)

        if self.on_point_selected_callback:
            self.on_point_selected_callback(idx_closest)

    def _update_highlight(self, p: dict):
        # 1. 十字垂直線
        self.crosshair_line.setLine(p['x'], 20, p['x'], self.height() - 40)
        self.crosshair_line.setVisible(True)

        # 2. 高亮焦點圓圓點
        self.hover_circle.setRect(p['x'] - 6, p['y'] - 6, 12, 12)
        color = QColor("#E74C3C") if p['close'] >= p['open'] else QColor("#2ECC71")
        self.hover_circle.setBrush(QBrush(color))
        self.hover_circle.setVisible(True)

        # 3. 資訊卡片內容
        info_text = (
            f"📅 日期: {p['date']}\n"
            f"💰 收盤價: NT$ {p['close']:.2f}\n"
            f"📈 開盤/最高/最低: {p['open']:.2f} / {p['high']:.2f} / {p['low']:.2f}\n"
            f"📊 成交量: {p['volume']:,} 股"
        )
        self.tooltip_text.setPlainText(info_text)

        rect_b = self.tooltip_text.boundingRect()
        tx = p['x'] + 15
        ty = p['y'] - 30

        if tx + rect_b.width() > self.width() - 20:
            tx = p['x'] - rect_b.width() - 15
        if ty < 20:
            ty = 20

        self.tooltip_rect.setRect(tx - 5, ty - 5, rect_b.width() + 10, rect_b.height() + 10)
        self.tooltip_text.setPos(tx, ty)

        self.tooltip_rect.setVisible(True)
        self.tooltip_text.setVisible(True)

    def wheelEvent(self, event):
        scale_factor = 1.25
        if event.angleDelta().y() > 0:
            self.scale(scale_factor, scale_factor)
        else:
            self.scale(1/scale_factor, 1/scale_factor)


# ======================================================================
# Tab 2 容器 (帶批次完成訊號，供 Tab 3 接收)
# ======================================================================
class BatchScraperTab(QWidget):
    batch_completed = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)


# ======================================================================
# 主視窗 (QTabWidget 三分頁)
# ======================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("📈 台股雙引擎行情分析與批次爬蟲系統 (practice5.py)")
        self.resize(1360, 850)
        self.worker = None
        self.playwright_worker = None
        self.current_df = None
        self._init_ui()

    # ------------------------------------------------------------------
    # 主 UI：QTabWidget 三分頁
    # ------------------------------------------------------------------
    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.tabs = QTabWidget()
        self.tab1 = self._build_tab1()
        self.tab2 = self._build_tab2()
        self.tab3 = self._build_tab3()
        self.tabs.addTab(self.tab1, "📊 Tab 1: 單股歷史折線分析")
        self.tabs.addTab(self.tab2, "🚀 Tab 2: 批次即時爬蟲")
        self.tabs.addTab(self.tab3, "💾 Tab 3: 資料庫與檔案匯出")
        layout.addWidget(self.tabs)

        # 批次完成 -> 更新 Tab3
        self.tab2.batch_completed.connect(self._on_batch_completed)

    # ==================================================================
    # Tab 1: 單股歷史行情與折線圖分析
    # ==================================================================
    def _build_tab1(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # --- 頂部搜尋控制列 ---
        cb = QHBoxLayout()
        self.input_code = QLineEdit()
        self.input_code.setText("2330")
        self.input_code.setPlaceholderText("輸入股票代碼或名稱 (如 2330 或 台積電)")
        self.input_code.setFixedWidth(260)
        self.input_code.returnPressed.connect(self._on_search)

        self.combo_period = QComboBox()
        self.combo_period.addItems(["1mo", "3mo", "6mo", "1y", "2y", "5y"])

        self.combo_chart_type = QComboBox()
        self.combo_chart_type.addItems(["📉 收盤價折線圖", "📊 走勢K線圖"])
        self.combo_chart_type.currentIndexChanged.connect(self._on_chart_type_changed)

        self.btn_search = QPushButton("🚀 查詢行情")
        self.btn_search.clicked.connect(self._on_search)

        cb.addWidget(QLabel("股票搜尋:"))
        cb.addWidget(self.input_code)
        cb.addWidget(QLabel("時間範圍:"))
        cb.addWidget(self.combo_period)
        cb.addWidget(QLabel("圖表類型:"))
        cb.addWidget(self.combo_chart_type)
        cb.addStretch()
        cb.addWidget(self.btn_search)
        layout.addLayout(cb)

        # --- 中央區域 QSplitter 左右分欄 ---
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(self.splitter)

        # 左側: 折線圖 + 日期滑桿
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        self.view = ClosePriceLineGraphicsView()
        self.view.on_point_selected_callback = self._on_view_point_selected
        left_layout.addWidget(self.view)

        slider_box = QHBoxLayout()
        slider_box.addWidget(QLabel("📅 日期滑桿選取:"))
        self.date_slider = QSlider(Qt.Orientation.Horizontal)
        self.date_slider.setEnabled(False)
        self.date_slider.valueChanged.connect(self._on_slider_value_changed)
        slider_box.addWidget(self.date_slider)

        self.lbl_slider_info = QLabel("提示: 亦可用滑桿或鍵盤左右鍵精確移動交易日點位")
        self.lbl_slider_info.setStyleSheet("color: #6C757D; font-size: 11px;")
        slider_box.addWidget(self.lbl_slider_info)
        left_layout.addLayout(slider_box)

        self.splitter.addWidget(left_widget)

        # 右側: 統計卡片 + 歷史價格明細表格
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        self.stats_card = QWidget()
        self.stats_card.setStyleSheet("background-color: #F8F9FA; border: 1px solid #DEE2E6; border-radius: 6px; padding: 8px;")
        sc_lay = QVBoxLayout(self.stats_card)
        self.lbl_title = QLabel("🔍 請搜尋股票進行分析")
        self.lbl_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #212529;")
        self.lbl_price = QLabel("最新收盤: --")
        self.lbl_change = QLabel("漲跌幅: --")
        sc_lay.addWidget(self.lbl_title)
        sc_lay.addWidget(self.lbl_price)
        sc_lay.addWidget(self.lbl_change)
        right_layout.addWidget(self.stats_card)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["日期", "開盤", "最高", "最低", "收盤", "成交量"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.cellClicked.connect(self._on_table_cell_clicked)
        right_layout.addWidget(self.table)

        self.splitter.setSizes([800, 480])
        self.splitter.addWidget(right_widget)

        # 進度列
        self.pbar = QProgressBar()
        self.pbar.setVisible(False)
        layout.addWidget(self.pbar)

        return tab

    # ==================================================================
    # Tab 2: 多股批次即時爬蟲
    # ==================================================================
    def _build_tab2(self) -> QWidget:
        tab = BatchScraperTab()
        layout = QVBoxLayout(tab)

        # --- 爬蟲模式與搜尋設定 ---
        cfg_box = QGroupBox("⚙️ 爬蟲模式與搜尋設定")
        cfg_lay = QVBoxLayout(cfg_box)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("模式選單:"))
        self.combo_mode = QComboBox()
        self.combo_mode.addItems([
            "1. 預設熱門股 (2330, 2317, 2454, 2308, 3008)",
            "2. 關鍵字搜尋複選 (twstock)",
            "3. 自訂股票代碼清單"
        ])
        self.combo_mode.currentIndexChanged.connect(self._on_mode_changed)
        row1.addWidget(self.combo_mode)
        row1.addStretch()
        row1.addWidget(QLabel("併行數:"))
        self.spin_concurrency = QSpinBox()
        self.spin_concurrency.setRange(1, 5)
        self.spin_concurrency.setValue(3)
        self.spin_concurrency.setSuffix(" (1~5)")
        row1.addWidget(self.spin_concurrency)

        self.btn_start = QPushButton("⚡ 開始批次爬取")
        self.btn_start.clicked.connect(self._on_start_batch)
        row1.addWidget(self.btn_start)

        self.btn_stop = QPushButton("⏹️ 中止爬蟲")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._on_stop_batch)
        row1.addWidget(self.btn_stop)
        cfg_lay.addLayout(row1)

        self.edit_custom_codes = QLineEdit()
        self.edit_custom_codes.setPlaceholderText("請輸入股票代碼清單，以逗號分隔 (例: 2330, 2317, 3008)")
        self.edit_custom_codes.setVisible(False)
        cfg_lay.addWidget(self.edit_custom_codes)
        layout.addWidget(cfg_box)

        # --- 關鍵字搜尋與股票選擇區 (模式 2) ---
        self.search_group = QGroupBox("🔍 關鍵字搜尋與股票選擇區")
        sg_lay = QVBoxLayout(self.search_group)
        kw_row = QHBoxLayout()
        self.edit_keyword = QLineEdit()
        self.edit_keyword.setPlaceholderText("輸入股票代碼或名稱關鍵字 (如 23 或 晶圓)")
        self.edit_keyword.returnPressed.connect(self._on_keyword_search)
        kw_row.addWidget(self.edit_keyword)
        self.btn_keyword_search = QPushButton("🔎 搜尋")
        self.btn_keyword_search.clicked.connect(self._on_keyword_search)
        kw_row.addWidget(self.btn_keyword_search)
        sg_lay.addLayout(kw_row)
        self.list_stocks = QListWidget()
        self.list_stocks.setMaximumHeight(160)
        sg_lay.addWidget(self.list_stocks)
        self.search_group.setVisible(False)
        layout.addWidget(self.search_group)

        # --- 批次爬取即時結果明細表 ---
        table_group = QGroupBox("📊 批次爬取即時結果明細表")
        tg_lay = QVBoxLayout(table_group)
        self.batch_table = QTableWidget()
        self.batch_table.setColumnCount(10)
        self.batch_table.setHorizontalHeaderLabels(["代碼", "名稱", "即時價格", "漲跌資訊", "資料時間", "開盤", "最高", "最低", "昨收", "狀態"])
        self.batch_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.batch_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.batch_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        tg_lay.addWidget(self.batch_table)
        layout.addWidget(table_group, stretch=3)

        # --- 爬蟲即時日誌與進度 ---
        log_group = QGroupBox("📜 爬蟲即時日誌與進度")
        lg_lay = QVBoxLayout(log_group)
        self.batch_progress = QProgressBar()
        self.batch_progress.setRange(0, 1)
        self.batch_progress.setValue(0)
        lg_lay.addWidget(self.batch_progress)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(180)
        lg_lay.addWidget(self.log_text)
        layout.addWidget(log_group)

        return tab

    # ==================================================================
    # Tab 3: 資料庫與檔案匯出
    # ==================================================================
    def _build_tab3(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # --- 匯出設定面板 ---
        cfg_box = QGroupBox("💾 匯出設定面板")
        cfg_lay = QVBoxLayout(cfg_box)
        form = QGridLayout()
        form.addWidget(QLabel("檔案格式:"), 0, 0)
        self.combo_export_format = QComboBox()
        self.combo_export_format.addItems(["CSV (.csv)", "JSON (.json)", "兩者皆匯出"])
        self.combo_export_format.currentIndexChanged.connect(self._on_export_format_changed)
        form.addWidget(self.combo_export_format, 0, 1, 1, 2)

        form.addWidget(QLabel("儲存路徑:"), 1, 0)
        today = datetime.date.today().strftime("%Y%m%d")
        self.edit_export_path = QLineEdit()
        self.edit_export_path.setText(f"output/stocks_batch_{today}.csv")
        form.addWidget(self.edit_export_path, 1, 1)

        self.btn_browse = QPushButton("📂 選擇路徑")
        self.btn_browse.clicked.connect(self._on_browse_path)
        form.addWidget(self.btn_browse, 1, 2)

        self.btn_export = QPushButton("💾 一鍵匯出")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._on_export)
        form.addWidget(self.btn_export, 2, 1)

        cfg_lay.addLayout(form)
        layout.addWidget(cfg_box)

        # --- 數據預覽與歷史記錄 ---
        info_box = QGroupBox("📋 數據預覽與歷史記錄")
        info_lay = QVBoxLayout(info_box)
        self.lbl_export_summary = QLabel("目前尚未有批次爬取結果，請先至 Tab 2 執行爬取。")
        self.lbl_export_summary.setStyleSheet("color: #495057; font-size: 12px;")
        info_lay.addWidget(self.lbl_export_summary)
        self.preview_table = QTableWidget()
        self.preview_table.setColumnCount(10)
        self.preview_table.setHorizontalHeaderLabels(["代碼", "名稱", "即時價格", "漲跌資訊", "資料時間", "開盤", "最高", "最低", "昨收", "狀態"])
        self.preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.preview_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        info_lay.addWidget(self.preview_table)
        layout.addWidget(info_box)

        self.last_results: List[Dict] = []
        return tab

    # ==================================================================
    # Tab 1 訊號槽
    # ==================================================================
    def _on_search(self):
        query = self.input_code.text().strip()
        if not query:
            query = "2330"
            self.input_code.setText("2330")

        self.pbar.setVisible(True)
        self.pbar.setRange(0, 0)
        self.btn_search.setEnabled(False)

        self.worker = FetchDataWorker(query, self.combo_period.currentText())
        self.worker.data_loaded.connect(self._on_data_done)
        self.worker.error_occurred.connect(self._on_err)
        self.worker.start()

    def _on_data_done(self, stock: StockInfo, summary: dict, df: pd.DataFrame):
        self.pbar.setVisible(False)
        self.btn_search.setEnabled(True)
        self.current_df = df

        self.lbl_title.setText(f"📉 {stock.name} ({stock.code}) - {stock.market} | {stock.group}")
        self.lbl_price.setText(f"最新收盤: NT$ {summary['latest_close']:.2f} (最高: {summary['high_price']:.2f} / 最低: {summary['low_price']:.2f})")

        color_str = "#E74C3C" if summary['pct_change'] >= 0 else "#2ECC71"
        self.lbl_change.setText(f"期間漲跌幅: <font color='{color_str}'><b>{summary['pct_change']:.2f}%</b></font> | 均量: {summary['avg_volume']:,.0f}")

        # 填寫 Table
        self.table.setRowCount(len(df))
        for i, (idx, row) in enumerate(df.iterrows()):
            self.table.setItem(i, 0, QTableWidgetItem(idx.strftime('%Y-%m-%d')))
            self.table.setItem(i, 1, QTableWidgetItem(f"{row['Open']:.2f}"))
            self.table.setItem(i, 2, QTableWidgetItem(f"{row['High']:.2f}"))
            self.table.setItem(i, 3, QTableWidgetItem(f"{row['Low']:.2f}"))
            self.table.setItem(i, 4, QTableWidgetItem(f"{row['Close']:.2f}"))
            self.table.setItem(i, 5, QTableWidgetItem(f"{int(row['Volume']):,}"))

        # 設定 Date Slider 範圍
        self.date_slider.blockSignals(True)
        self.date_slider.setRange(0, len(df) - 1)
        self.date_slider.setValue(len(df) - 1)
        self.date_slider.setEnabled(True)
        self.date_slider.blockSignals(False)

        mode = "line" if self.combo_chart_type.currentIndex() == 0 else "kline"
        self.view.draw_chart(df, mode)

    def _on_slider_value_changed(self, val: int):
        self.view.update_cursor_at_index(val)
        self.table.selectRow(val)

    def _on_view_point_selected(self, index: int):
        self.date_slider.blockSignals(True)
        self.date_slider.setValue(index)
        self.date_slider.blockSignals(False)
        self.table.selectRow(index)

    def _on_table_cell_clicked(self, row: int, col: int):
        self.date_slider.setValue(row)
        self.view.update_cursor_at_index(row)

    def _on_chart_type_changed(self, idx: int):
        if self.current_df is not None and not self.current_df.empty:
            mode = "line" if idx == 0 else "kline"
            self.view.draw_chart(self.current_df, mode)

    def _on_err(self, msg: str):
        self.pbar.setVisible(False)
        self.btn_search.setEnabled(True)
        QMessageBox.critical(self, "查詢錯誤", msg)

    # ==================================================================
    # Tab 2 訊號槽
    # ==================================================================
    def _twstock_search(self, keyword: str) -> List[Dict]:
        import twstock
        query = keyword.strip().lower()
        results = []
        for code, info in twstock.codes.items():
            if len(code) == 4 and (info.type == '股票' or getattr(info, 'market', '') in ['上市', '上櫃']):
                if query in code.lower() or query in getattr(info, 'name', '').lower():
                    results.append({
                        "code": code,
                        "name": getattr(info, 'name', '未知'),
                        "market": getattr(info, 'market', '台股'),
                        "group": getattr(info, 'group', '')
                    })
        return results

    def _on_mode_changed(self, idx: int):
        self.search_group.setVisible(idx == 1)
        self.edit_custom_codes.setVisible(idx == 2)

    def _on_keyword_search(self):
        keyword = self.edit_keyword.text().strip()
        if not keyword:
            QMessageBox.warning(self, "搜尋", "請先輸入搜尋關鍵字！")
            return
        self.list_stocks.clear()
        matches = self._twstock_search(keyword)[:20]
        if not matches:
            QMessageBox.information(self, "搜尋結果", f"查無符合「{keyword}」的股票。")
            return
        for m in matches:
            item = QListWidgetItem(f"{m['code']} - {m['name']} ({m['market']})")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, m['code'])
            self.list_stocks.addItem(item)
        self._log(f"🔍 找到 {len(matches)} 筆符合「{keyword}」的股票，請勾選欲爬取的項目。")

    def _collect_codes(self) -> List[str]:
        mode = self.combo_mode.currentIndex()
        if mode == 0:
            codes = ["2330", "2317", "2454", "2308", "3008"]
        elif mode == 1:
            codes = []
            for i in range(self.list_stocks.count()):
                item = self.list_stocks.item(i)
                if item.checkState() == Qt.CheckState.Checked:
                    codes.append(item.data(Qt.ItemDataRole.UserRole))
        else:
            raw = self.edit_custom_codes.text().strip()
            codes = [c.strip() for c in raw.split(",") if c.strip()]
        return list(dict.fromkeys(codes))

    def _on_start_batch(self):
        if self.playwright_worker is not None and self.playwright_worker.isRunning():
            return
        codes = self._collect_codes()
        if not codes:
            QMessageBox.warning(self, "提示", "請先選擇或輸入至少一支股票代碼！")
            return

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.batch_table.setRowCount(0)
        self.batch_table.setRowCount(len(codes))
        self.batch_row_map = {}
        for i, c in enumerate(codes):
            self.batch_row_map[c] = i
            self.batch_table.setItem(i, 0, QTableWidgetItem(c))
            self.batch_table.setItem(i, 9, QTableWidgetItem("⏳ 爬取中"))

        self.batch_progress.setRange(0, len(codes))
        self.batch_progress.setValue(0)
        self.batch_progress.setFormat(f"爬取進度: 0/{len(codes)}")
        self._log(f"🚀 開始批次爬取 {len(codes)} 支股票: {', '.join(codes)}")

        self.playwright_worker = PlaywrightWorker(codes, self.spin_concurrency.value())
        self.playwright_worker.single_stock_done.connect(self._on_single_stock_done)
        self.playwright_worker.progress_signal.connect(self._on_batch_progress)
        self.playwright_worker.log_signal.connect(self._log)
        self.playwright_worker.batch_finished.connect(self._on_batch_finished)
        self.playwright_worker.error_signal.connect(self._on_batch_error)
        self.playwright_worker.start()

    def _on_stop_batch(self):
        self._log("⏹️ 正在中止爬蟲作業...")
        self.btn_stop.setEnabled(False)
        if self.playwright_worker:
            self.playwright_worker.cancel()

    def _on_single_stock_done(self, data: dict):
        code = str(data.get("股票代碼", ""))
        row = self.batch_row_map.get(code)
        if row is None:
            return
        if "錯誤訊息" in data:
            self.batch_table.setItem(row, 1, QTableWidgetItem("❌ 抓取失敗"))
            self.batch_table.setItem(row, 9, QTableWidgetItem("❌ 失敗"))
        else:
            values = [
                data.get("股票名稱", ""),
                data.get("即時價格", ""),
                data.get("漲跌資訊", ""),
                data.get("資料時間", ""),
                data.get("開盤價", ""),
                data.get("最高價", ""),
                data.get("最低價", ""),
                data.get("昨收價", "")
            ]
            for col, v in enumerate(values, start=1):
                self.batch_table.setItem(row, col, QTableWidgetItem(str(v)))
            self.batch_table.setItem(row, 9, QTableWidgetItem("✅ 成功"))

    def _on_batch_progress(self, completed: int, total: int):
        self.batch_progress.setValue(completed)
        self.batch_progress.setFormat(f"爬取進度: {completed}/{total}")

    def _on_batch_finished(self, results: List[Dict]):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        success = sum(1 for r in results if "錯誤訊息" not in r)
        self._log(f"✨ 批次爬取完成！成功 {success}/{len(results)} 支股票")
        self.tab2.batch_completed.emit(results)
        if success:
            QMessageBox.information(self, "批次完成", f"✅ 批次爬取完成！成功取得 {success}/{len(results)} 支股票資料")
        else:
            QMessageBox.warning(self, "批次完成", f"⚠️ 批次結束，但 0/{len(results)} 支股票成功 (可能為暫停或全部失敗)。")

    def _on_batch_error(self, msg: str):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self._log(f"❌ 爬蟲錯誤: {msg}")
        if "executable doesn't exist" in str(msg).lower() or "playwright install" in str(msg).lower():
            QMessageBox.critical(
                self, "Playwright 錯誤",
                "偵測不到 Playwright Chromium 瀏覽器，請先執行:\n\nuv run playwright install chromium"
            )
        else:
            QMessageBox.critical(self, "爬蟲錯誤", str(msg))

    def _log(self, msg: str):
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_text.append(f"[{ts}] {msg}")
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    # ==================================================================
    # Tab 3 訊號槽
    # ==================================================================
    def _on_export_format_changed(self, idx: int):
        path = self.edit_export_path.text().strip()
        if idx == 1:
            if not path.endswith(".json"):
                base = path[:-4] if path.endswith(".csv") else path
                self.edit_export_path.setText(base + ".json")
        elif idx == 0:
            if not path.endswith(".csv"):
                base = path[:-5] if path.endswith(".json") else path
                self.edit_export_path.setText(base + ".csv")

    def _on_browse_path(self):
        today = datetime.date.today().strftime("%Y%m%d")
        default = self.edit_export_path.text().strip() or f"output/stocks_batch_{today}.csv"
        fmt = self.combo_export_format.currentIndex()
        if fmt == 1:
            fname, _ = QFileDialog.getSaveFileName(self, "選擇匯出路徑", default, "JSON 檔案 (*.json)")
        else:
            fname, _ = QFileDialog.getSaveFileName(self, "選擇匯出路徑", default, "CSV 檔案 (*.csv)")
        if fname:
            self.edit_export_path.setText(fname)

    def _on_batch_completed(self, results: List[Dict]):
        """接收 Tab2 完成訊號後更新 Tab3"""
        self.last_results = results
        success = [r for r in results if "錯誤訊息" not in r]
        total = len(results)
        rate = (len(success) / total * 100) if total else 0.0
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.lbl_export_summary.setText(
            f"📦 最新批次: 共 {total} 筆資料 | ✅ 成功率: {rate:.1f}% | 🕐 最後更新時間: {ts}"
        )

        self.preview_table.setRowCount(total)
        for i, r in enumerate(results):
            self.preview_table.setItem(i, 0, QTableWidgetItem(str(r.get("股票代碼", ""))))
            self.preview_table.setItem(i, 1, QTableWidgetItem(str(r.get("股票名稱", ""))))
            self.preview_table.setItem(i, 2, QTableWidgetItem(str(r.get("即時價格", ""))))
            self.preview_table.setItem(i, 3, QTableWidgetItem(str(r.get("漲跌資訊", ""))))
            self.preview_table.setItem(i, 4, QTableWidgetItem(str(r.get("資料時間", ""))))
            self.preview_table.setItem(i, 5, QTableWidgetItem(str(r.get("開盤價", ""))))
            self.preview_table.setItem(i, 6, QTableWidgetItem(str(r.get("最高價", ""))))
            self.preview_table.setItem(i, 7, QTableWidgetItem(str(r.get("最低價", ""))))
            self.preview_table.setItem(i, 8, QTableWidgetItem(str(r.get("昨收價", ""))))
            if "錯誤訊息" in r:
                self.preview_table.setItem(i, 1, QTableWidgetItem(f"❌ 失敗: {r.get('錯誤訊息', '')}"))
                self.preview_table.setItem(i, 9, QTableWidgetItem("❌ 失敗"))
            else:
                self.preview_table.setItem(i, 9, QTableWidgetItem("✅ 成功"))

        self.btn_export.setEnabled(bool(success))

    def _on_export(self):
        data = [r for r in self.last_results if "錯誤訊息" not in r]
        if not data:
            QMessageBox.warning(self, "匯出", "目前無成功資料可供匯出！")
            return

        path = self.edit_export_path.text().strip()
        if not path:
            QMessageBox.warning(self, "匯出", "請先設定儲存路徑！")
            return

        try:
            fmt = self.combo_export_format.currentIndex()
            if fmt == 0:
                p = path if path.endswith(".csv") else path + ".csv"
                export_to_csv(data, p)
                saved = p
            elif fmt == 1:
                p = path if path.endswith(".json") else path + ".json"
                export_to_json(data, p)
                saved = p
            else:
                base = path
                if base.endswith(".csv"):
                    base = base[:-4]
                elif base.endswith(".json"):
                    base = base[:-5]
                export_to_csv(data, base + ".csv")
                export_to_json(data, base + ".json")
                saved = f"{base}.csv / {base}.json"
            self._log(f"💾 資料已匯出: {saved}")
            QMessageBox.information(self, "匯出成功", f"✅ 資料匯出成功！\n\n路徑: {saved}")
        except Exception as e:
            QMessageBox.critical(self, "匯出失敗", str(e))


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
