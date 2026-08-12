import sys
import pandas as pd
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLineEdit, QComboBox, QPushButton, QLabel, QTableWidget,
    QTableWidgetItem, QGraphicsView, QGraphicsScene, QGraphicsItem,
    QGraphicsRectItem, QGraphicsLineItem, QGraphicsPathItem, QGraphicsEllipseItem,
    QGraphicsTextItem, QMessageBox, QProgressBar, QHeaderView, QSlider
)
from PySide6.QtCore import (
    Qt, QThread, Signal, QRectF, QPointF, QTimer
)
from PySide6.QtGui import (
    QColor, QPen, QBrush, QPainter, QFont, QPainterPath, QLinearGradient
)

# 繼承 practice4.py 的數據模型與核心運算 logic
from practice4 import StockInfo, search_stock, filter_by_group, fetch_stock_history, calculate_summary

class FetchDataWorker(QThread):
    """背景資料下載工作器，避免 UI 凍結"""
    data_loaded = Signal(StockInfo, dict, pd.DataFrame)
    error_occurred = Signal(str)

    def __init__(self, query: str, period: str, start_date: str = None, end_date: str = None):
        super().__init__()
        self.query = query
        self.period = period
        self.start_date = start_date
        self.end_date = end_date

    def run(self):
        try:
            clean_query = self.query.strip().replace(".TW", "").replace(".TWO", "")
            results = search_stock(clean_query)
            
            if not results:
                raise ValueError(f"查無符合「{self.query}」的股票代碼或名稱。")
            
            stock = results[0]
            
            if self.start_date and self.end_date:
                df = fetch_stock_history(stock.yf_symbol, start_date=self.start_date, end_date=self.end_date)
            else:
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
            if self._timer: self._timer.stop()
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

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("📈 台股收盤價折線圖與行情分析系統 (PySide6 Graphics View)")
        self.resize(1280, 800)
        self.worker = None
        self.current_df = None
        self._init_ui()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Control Bar ---
        cb = QHBoxLayout()
        self.input_code = QLineEdit()
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

        # --- Splitter ---
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(self.splitter)

        # Left: View (收盤價折線圖) + Slider Navigation Bar
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        self.view = ClosePriceLineGraphicsView()
        self.view.on_point_selected_callback = self._on_view_point_selected
        left_layout.addWidget(self.view)

        # 輔助滑桿控制器 (了解滑鼠控制不好操控時可滑動或用鍵盤微調)
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

        # Right: Stats + Table
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

        # Progress Bar
        self.pbar = QProgressBar()
        self.pbar.setVisible(False)
        layout.addWidget(self.pbar)

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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
