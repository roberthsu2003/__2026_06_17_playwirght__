# Playwright 網站健康檢查 App

這是一個繁體中文的 Tkinter 桌面工具，可使用 Chromium、Firefox 或 WebKit
檢查網站的 HTTP 狀態、回應時間、頁面標題、`h1` 主標題與最終 URL，並儲存完整頁面截圖。

## 功能

- Playwright 在背景 worker thread 執行，不會阻塞 Tkinter 主迴圈。
- 所有 UI 更新經由 thread-safe queue 回到主執行緒。
- 支援 headless 模式與 100～300000 毫秒 timeout。
- 依 HTTP 結果顯示成功、警告或失敗狀態。
- 截圖儲存在 `lesson10/output/`，並可直接從 App 開啟資料夾。
- URL、timeout 與常見 Playwright 錯誤均提供繁體中文提示。

本專案不使用資料庫，也不建立歷史監測資料。

## 使用 uv 安裝

需要 Python 3.12 以上與 [uv](https://docs.astral.sh/uv/)。在專案根目錄執行：

```bash
uv sync
uv run playwright install
```

若只想依照 `requirements.txt` 建立環境：

```bash
uv venv
uv pip install -r requirements.txt
uv run playwright install
```

## 啟動桌面 App

```bash
uv run python lesson10/gui.py
```

操作方式：

1. 輸入以 `http://` 或 `https://` 開頭的 URL。
2. 選擇瀏覽器，設定 headless 與 timeout。
3. 按下「開始檢查」，結果與截圖預覽會顯示在右側。

## 保留的 CLI 執行方式

原本的 CLI 預設行為保持不變，會檢查 `https://example.com/`：

```bash
uv run python lesson10/practice5.py
uv run python lesson10/practice5.py --browser firefox
uv run python lesson10/practice5.py --browser webkit
```

## 執行測試

```bash
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q lesson10 tests
```

測試以假的 Playwright 物件驗證核心函式，因此不需要連線到外部網站。
