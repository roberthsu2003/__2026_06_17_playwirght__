# PRD：Herdr 終端機多工環境使用規範與教學文件

- **文件版本**：v1.1（已依主人審核意見調整）
- **建立日期**：2026-08-17
- **撰寫者**：Claude（主控 agent，本專案 workspace）
- **實作者**：`agent-implementer`（另一個 herdr workspace）
- **驗收者**：主控 agent → 主人（roberthsu2003）
- **適用專案**：`2026_06_17_playwright`（華梵 Playwright 課程教材庫）
- **環境現況**：herdr 0.8.0（Homebrew 安裝於 `/opt/homebrew/bin/herdr`），macOS Darwin 25.6.0，zsh

> **v1.1 變更摘要**（依主人審核決定）
> 1. 交付物從 `docs/herdr/` 六個檔案，改為 **專案根目錄單一檔案 `HERDR.md`**。
> 2. 場景手冊從 8 個精簡為 **核心 4 個**（跑測試、派工子 agent、workspace 隔離、具名 session）。
> 3. 實作者 **不得執行 git commit**，成果留在 working tree 由主人自行檢視。

---

## 1. 背景與問題

本專案是一個課程教材庫（`lesson1` ~ `lesson17`），日常工作型態包含：

1. 執行 Playwright / Python 腳本並觀察輸出
2. 同時開啟 dev server、測試、爬蟲腳本
3. 讓多個 AI coding agent（Claude Code、Codex、opencode 等）平行處理不同的 lesson 或分支

目前的痛點：

| 痛點 | 說明 |
| --- | --- |
| 終端機視窗散亂 | 每個任務各開一個分頁，無法一眼看出誰在跑什麼 |
| Agent 狀態不透明 | 不知道背景的 agent 是在「工作中」「等待輸入」還是「已完成」 |
| 缺乏協作規範 | 沒有一套「主控 agent 如何派工給另一個 agent」的標準流程 |
| 知識未沉澱 | herdr 的指令用法散落在 `--help`，團隊／學生無從學起 |

**Herdr** 正是解決這些問題的工具：它把終端機組織成 workspace / tab / pane 三層結構，能辨識 pane 中執行的 coding agent，並透過 `herdr` CLI 對外開放整個 session 的控制權。

---

## 2. 目標與非目標

### 2.1 目標（Goals）

- **G1**：產出一份可直接照做的 Herdr 安裝與設定說明（macOS 為主，附其他平台說明）。
- **G2**：以本專案的真實工作情境，整理出 **4 個核心場景** 的操作手冊（含可複製指令）。
- **G3**：建立「主控 agent ↔ 子 agent」的派工與驗收 SOP，讓多 agent 協作有規則可循。
- **G4**：提供一份 **指令速查表**，涵蓋 workspace / tab / pane / agent / worktree / session 六大命令群。
- **G5**：文件全程使用 **繁體中文**，符合本專案 `AGENTS.md` 的規範。
- **G6**：全部內容集中在 **單一檔案 `HERDR.md`**，一頁到底、不需跳轉。

### 2.2 非目標（Non-Goals）

- 不修改本專案任何既有的 lesson 程式碼。
- 不安裝或設定 herdr 以外的新工具。
- 不撰寫 herdr 原始碼層級的原理分析，只聚焦「怎麼用」。
- 不涵蓋 Windows 原生環境（可註明 WSL 可行性即可）。
- 不建立 `docs/` 目錄，不拆分多檔。

---

## 3. 目標讀者

| 讀者 | 需求 |
| --- | --- |
| 專案主人（roberthsu2003） | 快速回顧指令、建立自己的多 agent 工作流 |
| 課程學生 | 從零安裝 herdr，理解 workspace/tab/pane 的心智模型 |
| AI coding agent | 作為 context 讀取，知道如何正確驅動 herdr（含安全規則） |

---

## 4. 交付物（Deliverables）

實作者（`agent-implementer`）只需產出／修改 **兩個檔案**：

- **D1**：專案根目錄新增 `HERDR.md`
- **D2**：專案根目錄 `README.md` 增補一節連結

### D1. `HERDR.md`（單一檔案，依下列章節順序撰寫）

文件開頭需有：標題、「適用版本：herdr 0.8.0」標註、完整目錄（TOC，以錨點連結指向各章節）。

#### 第 1 章：Herdr 是什麼
- 3 段以內說明 Herdr 解決什麼問題、跟一般 tmux / iTerm 分頁的差異（重點：**能辨識 pane 內的 coding agent 並回報其生命週期狀態**）。
- workspace / tab / pane / agent 四層概念，用表格或 mermaid 圖呈現。

#### 第 2 章：安裝與初始設定
必須包含：
- macOS：`brew install herdr`（本機現況：homebrew-core formula，v0.8.0）
- 其他平台安裝方式與升級管道：`herdr update`、`herdr channel set <stable|preview>`
- zsh 補完：`herdr completion zsh`
- 設定檔位置：`~/.config/herdr/config.toml`；記錄檔：`~/.config/herdr/herdr.log`（另有 `herdr-client.log`、`herdr-server.log`）
- 環境變數 `HERDR_CONFIG_PATH` 的用途
- Agent 整合安裝：`herdr integration install claude|codex|opencode|copilot|...`（說明「整合」的好處：狀態辨識更準確）
- **驗證安裝成功的檢查清單**：`herdr --version`、`herdr status`、進入 session 後 `echo $HERDR_ENV` 應為 `1`

#### 第 3 章：核心概念
必須說明：
- 三層結構與 ID 規則：workspace `w1`、tab `w1:t1`、pane `w1:p1`；ID 為**不可重用**的穩定 handle
- pane 搬移後會取得新的 workspace-qualified pane ID（`pane move` 之後要改用新 ID）
- 注入到每個 pane 的環境變數：`HERDR_ENV`、`HERDR_WORKSPACE_ID`、`HERDR_TAB_ID`、`HERDR_PANE_ID`
- Agent 生命週期狀態：`idle` / `working` / `blocked` / `done` / `unknown` 各自的意義
  - 特別說明 `done` = 未被看見的背景工作完成後的 idle；CLI 讀取**不會**標記為已看見
  - `unknown` **不等於**完成
- pane 與 agent 的差別：`agent start` 只能在「已存在且處於互動提示符」的 shell pane 上啟動，**不會**自行建立或分割版面
- 讀取來源 `--source` 四種模式的差別：`visible` / `recent` / `recent-unwrapped` / `detection`，並說明日誌與逐字稿優先用 `recent-unwrapped`

#### 第 4 章：核心場景手冊（本文件重點）

每個場景都要有四段：**情境描述 → 完整可複製指令 → 預期輸出 → 注意事項**。

必須涵蓋以下 **4 個場景**（不多不少）：

| # | 場景 | 重點指令 |
| --- | --- | --- |
| S1 | 開一個旁邊的 pane 跑測試／腳本，焦點不離開目前視窗 | `herdr pane split --current --direction right --cwd "$PWD" --no-focus` → 從 `.result.pane.pane_id` 取 ID → `herdr pane run` → `herdr pane wait-output --match ... --timeout ...` → `herdr pane read --source recent-unwrapped` |
| S2 | 在新 pane 啟動另一個 coding agent 並派工、等待、讀取結果 | `herdr pane split` → `herdr agent start <name> --kind <kind> --pane <pane-id>` → `herdr agent prompt <name> "..." --wait --timeout 120000` → `herdr agent get` / `herdr agent read` |
| S3 | 用 workspace 隔離不同任務（例：一個跑課程教材、一個跑重構分支） | `herdr workspace list` / `create` / `get` / `focus` / `rename`；並說明何時該開新 workspace、何時只需在同 tab 分割 pane |
| S4 | 長時間跑 Playwright 或 dev server，離線後再回來 | 具名 session：`herdr --session <name>`、`herdr session list` / `attach` / `stop` / `delete` |

**S2 需額外補充兩個實務要點：**
- 若 agent 已處於 `blocked`，`agent prompt` 會回傳 `agent_blocked` 而不送出輸入；此時要先 `agent get` / `agent read` 看清對話框，再用 `agent send-keys <name> esc`（或其他鍵）刻意回應。
- 若因 agent 在 alternate screen 上執行，加大 `--lines` 也讀不到完整回覆時，改請該 agent 把完整回覆寫成暫存目錄的 Markdown 檔、只回傳檔案路徑，再直接讀檔。（此為備援手法，初次 prompt 時不要主動要求寫檔）

#### 第 5 章：多 Agent 協作 SOP
必須定義：
- **派工流程**：主控 agent 建立 pane → 啟動子 agent → 下 prompt → `--wait` 等待 → 讀取結果 → 驗收 → 不通過則附具體缺失清單退回重做（**本 PRD 的執行過程本身就是這個流程的示範，請把它寫成範例**）
- **驗收檢查清單範本**（子 agent 交回時，主控 agent 要逐項確認什麼）
- **安全與禮儀規則**（必須逐條列出）：
  - 背景工作一律加 `--no-focus`，除非主人要求切換畫面
  - 一律使用 `--current`、明確 pane ID 或唯一 agent 名稱，**不要**依賴其他 client 的焦點 pane
  - ID 必須從 JSON 回應解析，不可從側邊欄順序或範例推測
  - 不關閉自己沒有建立的 workspace / tab / pane / session
  - 絕不在活動 session 中執行 `herdr server stop`，絕不 kill 主 herdr 行程
  - 探索指令請執行 `herdr <group>`（不帶子命令）；**不要**執行裸 `herdr`（會啟動 TUI），也不要用「省略參數」的方式試探會造成變更的巢狀命令（例如 `herdr workspace create` 有預設值，會真的執行）
  - 版面禮儀：寬的 pane 往右切、窄或高的 pane 往下切，避免連續同方向分割產生出無法使用的細長欄位（可先用 `herdr pane layout` 判斷）
- agent 命名規則：符合 `[a-z][a-z0-9_-]{0,31}`，且在存活 agent 中唯一；agent 結束／被釋放／被取代時名稱會被清除

#### 第 6 章：指令速查表
- 依 workspace / tab / pane / agent / worktree / session / notification / integration 分組
- 每列格式：`指令` ｜ 用途 ｜ 常用選項 ｜ **唯讀或會變更**
- 附「JSON 回應中該取哪個欄位」對照表，至少包含：
  - `workspace create` → `.result.workspace` / `.result.tab` / `.result.root_pane`
  - `tab create` → `.result.tab` / `.result.root_pane`
  - `pane split` → `.result.pane.pane_id`
  - `pane move` → `.result.move_result.pane.pane_id`（舊 ID 為 `.result.move_result.previous_pane_id`）

### D2. 專案根目錄 `README.md` 更新
- 在既有內容之後新增一節「開發環境 / Herdr 終端機工作流」，一句話說明並連結到 `./HERDR.md`。
- **不得刪除或改寫既有的課程連結內容。**

---

## 5. 內容撰寫規範（Content Requirements）

| 編號 | 規範 |
| --- | --- |
| C1 | 全文使用**繁體中文**；技術名詞（workspace、pane、agent、worktree）保留英文原字，不硬翻 |
| C2 | 所有指令必須放在 ` ```bash ` 區塊中，可直接複製執行 |
| C3 | 指令中出現的 ID 一律用 `<pane-id>`、`$HERDR_PANE_ID` 這類佔位符，**不得**寫死本機當下的實際 ID（`wB`、`wC` 等） |
| C4 | 速查表中每個指令都必須標註「**唯讀 / 會變更狀態**」 |
| C5 | 文件中所有指令與選項，都必須能對應到 herdr 0.8.0 實際的 `--help` 輸出；**嚴禁杜撰不存在的指令或參數**（可比對本 PRD 第 9 節附錄） |
| C6 | 文件開頭需有 TOC 與「適用版本：herdr 0.8.0」標註 |
| C7 | 危險操作（`workspace close`、`tab close`、`pane close`、`session stop/delete`、`server stop`、`worktree remove --force`）必須以 `> ⚠️` 引言區塊警告 |
| C8 | 章節層級：`HERDR.md` 使用 `#` 為文件標題、`##` 為六大章、`###` 以下為細節，維持一致 |

---

## 6. 驗收標準（Acceptance Criteria）

主控 agent 收到 `agent-implementer` 的回報後，逐項檢查；**任一項不通過即退回重做**。

| 編號 | 驗收項目 | 判定方式 |
| --- | --- | --- |
| A1 | 專案根目錄存在 `HERDR.md`，且包含第 1~6 全部六章 | `ls HERDR.md` + 閱讀章節標題 |
| A2 | 專案 `README.md` 已新增 Herdr 章節並連結 `./HERDR.md`，原有課程連結內容完好 | `git diff README.md` |
| A3 | 文件中出現的每一個 herdr 子命令與選項都真實存在 | 逐一比對 `herdr <group>` 的 help 輸出 |
| A4 | 第 4 章涵蓋 S1~S4 四個場景，且每個場景都有「情境／指令／預期輸出／注意事項」四段 | 人工閱讀 |
| A5 | 第 5 章已完整列出本 PRD 4.1 D1 第 5 章所列的**所有**安全規則 | 逐條核對 |
| A6 | 全文為繁體中文，無簡體字、無整段英文 | 抽查 + `grep` 常見簡體字 |
| A7 | 未修改任何 `lesson*/` 目錄下的檔案；變更檔案只有 `HERDR.md` 與 `README.md` | `git status --short` |
| A8 | 所有 Markdown 表格、程式碼區塊格式正確，無斷版；TOC 錨點可用 | 人工閱讀 |
| A9 | 未寫死本機實際 workspace/pane ID | `grep -nE '\bw[A-Z](:t[0-9]+\|:p[0-9]+)?\b' HERDR.md` 應無違規結果 |
| A10 | 危險指令皆有 ⚠️ 警告（C7） | 人工核對 |
| A11 | **未執行任何 git commit / push**，成果留在 working tree | `git log -1` 應與派工前相同 |
| A12 | 未建立 `docs/` 目錄或其他額外檔案 | `git status --short` |

---

## 7. 執行流程（Workflow）

```
[主控 agent] 撰寫 PRD.md
        ↓
[主人] 審核 PRD.md ── 不通過 → 主控 agent 修改 PRD（已完成一輪，產出 v1.1）
        ↓ 通過
[主控 agent] 透過 herdr 將 PRD 派工給 workspace「agent-implementer」的 agent
        ↓
[agent-implementer] 依 PRD 產出 HERDR.md 與 README.md 增補（不 commit）
        ↓
[agent-implementer] 回報完成
        ↓
[主控 agent] 依第 6 節 A1~A12 逐項驗收
        ↓
   不通過 → 附上「具體缺失清單 + 對應驗收編號」，退回 agent-implementer 修改（可重複多輪）
        ↓ 通過
[主控 agent] 向主人回報，工作完成
```

---

## 8. 風險與對策

| 風險 | 對策 |
| --- | --- |
| 實作者杜撰不存在的 herdr 指令 | 驗收項 A3 強制比對 `--help`；C5 明文禁止；第 9 節附錄提供完整命令清單供比對 |
| 實作者誤動 lesson 教材 | 驗收項 A7 以 `git status --short` 把關 |
| 實作者擅自 commit | 驗收項 A11 以 `git log -1` 把關；派工 prompt 中明確禁止 |
| 實作者執行破壞性 herdr 指令（關閉別人的 pane、停掉 server） | 第 5 章安全規則 + 派工 prompt 中重申「herdr 只做唯讀探索，不得執行變更型指令」 |
| agent 回覆過長讀不完整 | 採用第 4 章 S2 的備援手法：請其寫入暫存 Markdown 後讀檔 |
| 多輪往返造成內容漂移 | 每次退回都附「具體缺失清單 + 對應驗收編號」，不做模糊指示 |

---

## 9. 附錄：herdr 0.8.0 命令群一覽（供實作者比對，禁止超出此範圍）

```
herdr workspace   list | create | get | focus | rename | report-metadata | close
herdr tab         list | create | get | focus | rename | close
herdr pane        list | current | get | layout | process-info | neighbor | edges | focus |
                  resize | zoom | rename | read | split | swap | move | close |
                  send-text | send-keys | wait-output | run |
                  report-agent | report-agent-session | release-agent | report-metadata
herdr agent       list | get | read | send-keys | prompt | rename | focus | wait |
                  attach | start | explain
herdr worktree    list | create | open | remove
herdr session     list | attach | stop | delete
herdr notification show
herdr integration install | uninstall
herdr config      reset-keys
herdr channel     set <stable|preview>
herdr api         <subcommand>
herdr status | update | completion <shell> | server stop | server reload-config
```

支援的 agent kinds（`herdr agent start --kind`）：

```
pi | claude | codex | gemini | cursor | devin | agy | cline | omp | mastracode |
opencode | copilot | kimi | kiro | droid | amp | grok | hermes | kilo | qodercli | maki
```

`herdr integration install/uninstall` 支援的整合：

```
pi | omp | claude | codex | copilot | devin | droid | kimi | opencode |
kilo | hermes | qodercli | cursor | mastracode | antigravity-cli | grok
```

---

## 10. 主人審核結果（已確認）

| 項目 | 決定 |
| --- | --- |
| 文件位置 | 根目錄單一 `HERDR.md`（不建 `docs/`） |
| 場景範圍 | 精簡為核心 4 個：S1 跑測試、S2 派工子 agent、S3 workspace 隔離、S4 具名 session |
| Commit 策略 | 實作者**不 commit**，成果留在 working tree 由主人自行檢視後決定 |

**PRD 狀態：已定案，可進入派工階段。**
