# OpenCode Subagent 與 Git Worktree 協作方案

## 1. 文件目的

本文件規劃以 OpenCode subagent 為核心、以 Git worktree 隔離工作目錄的協作方案。目標是讓多個 agent 能平行處理互不重疊的任務，並讓主 agent 可以安全地審查、驗證與整合成果。

本文件以本 repository 為範例：使用 `uv` 管理 Python 3.12 以上的專案環境，依賴版本由 `pyproject.toml` 與 `uv.lock` 管理。OpenCode、Git、uv 的具體版本應在導入時記錄並在 CI 驗證。

## 2. 背景與問題

在同一個工作目錄中同時執行多個 subagent，常見問題包括：

- agent 修改到彼此尚未完成的檔案，造成衝突或遺失變更。
- 不同任務共用同一個分支，難以追蹤責任範圍與回退成果。
- 測試、`.venv`、暫存檔、服務與固定 port 互相影響，導致結果不穩定。
- 主 agent 不容易安全地審查、挑選與合併各 subagent 的成果。

因此，本方案採用「一個 subagent、一個唯一任務分支、一個獨立 worktree」作為基本隔離單位。必須注意：OpenCode 的 subagent 功能本身不會自動建立 Git worktree；worktree 必須由主 agent 或自動化腳本先建立，並從該目錄啟動 agent。

## 3. 目標與非目標

### 3.1 目標

- 定義 OpenCode project-level subagent 的設定與權限原則。
- 建立每個 subagent 對應唯一 branch 與 worktree 的標準流程。
- 讓主 agent 可以在任務可獨立時平行派工，逐一審查後依依賴順序整合。
- 以 `uv`、現有 lockfile 與專案實際測試能力提供可複製的驗證流程。
- 定義交付格式、衝突處理、失敗回復、清理與驗收標準。

### 3.2 非目標

- 不規範特定 CI/CD 平台、部署平台或雲端資源。
- 不取代 Git code review、測試、秘密管理與分支保護制度。
- 不要求所有任務都使用 subagent；簡單、連續或高度耦合的任務可由主 agent 直接完成。
- 不宣稱 worktree 能隔離共享的資料庫、Docker daemon、網路服務、port、外部 API 或 Git object database。

## 4. 名詞與責任

- **主 agent**：拆解需求、建立 worktree、派工、審查、解衝突、合併與最終決策者。
- **subagent**：在指定 worktree 中執行單一責任範圍任務，不得修改其他 worktree。
- **主工作目錄**：通常是 `main` 或 `develop` branch 所在的 repository 工作目錄。
- **worktree**：同一個 Git repository 的另一個工作目錄；它共享 Git 物件資料，但有獨立的 `HEAD`、index 與工作檔案。
- **任務分支**：單一 subagent 專用的 branch，例如 `agent/implementer-login`。
- **整合分支**：主 agent 最後合併成果的 branch，例如 `main`。
- **任務基準點**：建立 worktree 時使用的明確 commit，建議使用整合分支當下的 `origin/main` 或 `main`，避免各任務從不同版本開始。

## 5. 前置條件與規範

### 5.1 必要條件

在主工作目錄確認：

```bash
git rev-parse --show-toplevel
git status --short
git worktree list
uv --version
uv python find 3.12
opencode --version
```

執行建立、合併與清理流程的帳號必須對 repository 的 Git metadata（例如 `.git/refs` 與 worktree 管理資料）具有寫入權限；若只有讀取權限，只能進行文件、diff 與環境檢查，不能宣稱已完成 worktree 演練。

若 `git status --short` 有未提交變更，主 agent 必須先明確保留、提交或暫存；不得把主工作目錄的未提交變更誤帶入新任務。建立任務 branch 前，先更新遠端參照：

```bash
git fetch origin --prune
git switch main
git pull --ff-only origin main
```

若專案整合分支不是 `main`，必須將以下範例中的 `main` 統一替換為實際分支。若不能執行 `pull`（例如離線），應使用已確認的本地 commit，並在交付紀錄中標註基準點。

### 5.2 共通規範

- 每個 worktree 使用唯一路徑與 branch；不可使用 `git worktree add --force` 來繞過 branch 已被 checkout 的保護。
- `WORKTREE_ROOT` 必須是已確認可寫入、且不會被清理程序意外刪除的目錄；預設可用 repository sibling 目錄，受限環境可覆寫為暫存或專用目錄。
- 任務範圍應盡量避免修改相同檔案；若必須重疊，改為依序處理並明確定義依賴。
- agent 只可在主 agent 指定的 worktree 中讀寫與執行命令，不可使用相對路徑猜測其他 worktree。
- 每個 worktree 都要在自己的目錄執行 `uv sync`；`.venv` 不應提交到 Git。
- 不得提交 `.env`、token、cookie、私鑰或其他秘密；測試資料也不得包含真實敏感資料。
- 未經主 agent 明確授權，subagent 不得 `git push`、修改遠端分支保護設定、合併分支或刪除其他 worktree。
- 平行 agent 若共用資料庫、服務或 port，必須先分配獨立 schema、測試資料、port 或 mock；worktree 不會自動提供這些隔離。

## 6. OpenCode Subagent 設定

### 6.1 官方支援的設定位置與格式

專案級 agent 放在 `.opencode/agents/`，每個 Markdown 檔案的檔名就是 agent 名稱，例如 `.opencode/agents/implementer.md` 會建立 `implementer` agent。使用 YAML front matter 設定 `description`、`mode` 與 `permission`；`mode: subagent` 表示它是可被主 agent 委派的 subagent。

也可在 `opencode.json` 的 `agent` 區段設定 agent。以下是可作為版本控管範本的 JSON 設定；實際模型名稱須依組織可用的 provider 與 OpenCode 版本調整：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "agent": {
    "implementer": {
      "description": "在指定 worktree 實作單一功能並補充測試",
      "mode": "subagent",
      "permission": {
        "edit": "allow",
        "bash": "ask",
        "external_directory": "deny"
      }
    },
    "reviewer": {
      "description": "只讀審查指定 worktree 的差異與測試結果",
      "mode": "subagent",
      "permission": {
        "edit": "deny",
        "bash": {
          "*": "ask",
          "git diff *": "allow",
          "git log *": "allow",
          "git status *": "allow"
        },
        "external_directory": "deny"
      }
    }
  }
}
```

`permission` 的值是 `allow`、`ask` 或 `deny`。目前應優先使用 `permission`，不要把舊式 `tools` 設定當成新方案的主要範例。權限是安全護欄，不是 worktree 隔離的替代品；尤其 `bash` 若獲准，agent 仍可能透過 shell 執行檔案操作，因此應搭配工作目錄、秘密管理與人工審查。

若採用 Markdown agent，最小範例如下：

```markdown
---
description: 在指定 worktree 實作單一功能並執行驗證
mode: subagent
permission:
  edit: allow
  bash: ask
  external_directory: deny
---

你只能在主 agent 指定的 worktree 工作。先閱讀需求、AGENTS.md、
pyproject.toml 與相關程式，再實作指定範圍。不要修改其他 worktree、
不要 push 或合併。完成後回報修改檔案、commit、驗證命令、結果與剩餘風險。
```

### 6.2 建議角色

- `researcher`：調查需求、現有程式與限制；預設禁止編輯，產出分析與建議。
- `implementer`：負責單一功能或模組的實作與測試；可編輯指定 worktree。
- `tester`：補充或執行測試，分析失敗原因；是否可編輯須依任務決定。
- `reviewer`：檢查 diff、設計、安全性、可維護性與測試覆蓋率；預設唯讀。
- `docs`：維護文件與操作說明；只修改明確列出的文件範圍。

每次派工必須提供：任務 ID、worktree 絕對路徑、branch 名稱、基準 commit、可修改範圍、不可修改範圍、前置依賴、驗收條件、測試命令、是否允許 commit，以及交付回報格式。

## 7. 建立與啟動 Worktree

### 7.1 建立多個任務

以下指令在主工作目錄執行，假設目前已在乾淨的 `main`，並以 `main` 作為每個任務的同一基準：

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
WORKTREE_ROOT="${WORKTREE_ROOT:-$REPO_ROOT/../worktrees}"
git status --short
git rev-parse --verify main
git worktree list
mkdir -p "$WORKTREE_ROOT"
git worktree add -b agent/implementer "$WORKTREE_ROOT/agent-implementer" main
git worktree add -b agent/tester "$WORKTREE_ROOT/agent-tester" main
git worktree list
```

`-b` 只會建立不存在的 branch；若 branch 已存在，指令會失敗，這是預期的安全行為。不要以 `-B` 或 `--force` 隨意覆蓋既有成果。若任務需從最新遠端開始，先完成 `git fetch`，再使用已確認的 `origin/main` 作為基準，例如：

```bash
git worktree add -b agent/docs "$WORKTREE_ROOT/agent-docs" origin/main
```

### 7.2 初始化 uv 環境

延續 7.1 的 shell session，或先重新設定 `REPO_ROOT` 與 `WORKTREE_ROOT`。每個 worktree 都包含相同的 `pyproject.toml` 與 `uv.lock`，在各自目錄執行：

```bash
cd "$WORKTREE_ROOT/agent-implementer"
uv sync --locked
uv run python --version
uv run python -c "import playwright; print(playwright.__version__)"
```

`uv sync --locked` 會驗證 lockfile 必須已是最新且不修改 `uv.lock`；適合可重現的任務初始化與 CI。`uv sync --frozen` 只使用現有 lockfile、不檢查 `pyproject.toml` 是否需要更新，應只在已明確接受該行為時使用。若依賴定義有意變更，先由負責 agent 執行 `uv lock`，檢查並提交 `pyproject.toml` 與 `uv.lock` 的一致變更，再讓其他 worktree 重新同步。

本 repository 沒有在 `pyproject.toml` 宣告 pytest，因此不能把 `uv run pytest` 當成無條件通用命令。實際測試命令必須以專案現有測試檔、`README.md`、CI 設定或任務規格為準。若需要 Playwright 瀏覽器，另執行：

```bash
uv run playwright install
```

在 CI 或已知瀏覽器已安裝的環境，可用 `uv run --no-sync ...` 避免每次命令重新同步；只有在先完成 `uv sync --locked` 且環境未被改動時才可這樣做。

### 7.3 啟動 subagent

OpenCode 必須從目標 worktree 啟動，才能讓它把該目錄視為專案根目錄並讀取該 worktree 版本的 `AGENTS.md` 與 `.opencode/` 設定：

```bash
cd "$WORKTREE_ROOT/agent-implementer"
opencode
```

啟動後提供類似以下任務訊息：

```text
任務 ID：T-001
工作目錄：/絕對路徑/../worktrees/agent-implementer
分支：agent/implementer
基準 commit：<建立 worktree 時記錄的 commit>
可修改範圍：src/、tests/
不可修改範圍：其他 worktree、遠端設定、秘密檔案
驗收：完成指定功能，並執行 <專案實際測試命令>
交付：列出修改檔案、commit、驗證結果與剩餘風險；不得 push 或合併。
```

若由主 agent 透過 OpenCode 的 task 工具委派，仍必須確認被委派 agent 的工作目錄是該 worktree；單純在同一個主工作目錄中呼叫多個 subagent，並不符合本方案。

## 8. 完成、審查與合併

### 8.1 Subagent 交付

subagent 完成後，在自己的 worktree 執行：

```bash
git status --short
git diff --check
uv sync --locked
uv run <專案實際驗證命令>
git add -- <明確列出的檔案>
git commit -m "feat: implement requested change"
git status --short
```

若驗證命令失敗，不得只回報「完成」；必須列出失敗命令、可重現步驟、是否為環境問題，以及尚未修正的風險。commit 前應排除 `.env`、`.venv`、瀏覽器快取、報告輸出與其他產物。

### 8.2 主 agent 審查

主 agent 在主工作目錄執行：

```bash
git worktree list
git status --short
git log --oneline --decorate -1 agent/implementer
git diff --check main...agent/implementer
git diff --stat main...agent/implementer
git diff main...agent/implementer -- <預期檔案>
```

審查至少確認：變更沒有超出範圍、沒有秘密、沒有不必要的 lockfile 漂移、測試結果可重現、commit 位於正確分支，且不存在未提交變更。需要修改時，讓同一個 subagent 在同一個 worktree 修正並重新驗證；不要讓另一個 agent 同時修改同一分支。

### 8.3 合併與整體驗證

依任務依賴順序，在主工作目錄合併：

```bash
git switch main
git status --short
git merge --no-ff agent/implementer
uv sync --locked
uv run <完整測試或驗證命令>
```

發生衝突時，主 agent 應停止平行合併，檢查 `git status`，逐一解決衝突並執行 `git diff --check` 與完整驗證。若衝突涉及設計決策，不應默認採用任一方；應回到任務規格或請負責人決策。合併完成前不可清理仍需要的 branch 或 worktree。

## 9. 清理與回復

只有在成果已合併、已備份或明確放棄，且 worktree 沒有未提交變更時才清理：

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
WORKTREE_ROOT="${WORKTREE_ROOT:-$REPO_ROOT/../worktrees}"
cd "$REPO_ROOT"
git -C "$WORKTREE_ROOT/agent-implementer" status --short
git worktree remove "$WORKTREE_ROOT/agent-implementer"
git branch -d agent/implementer
git worktree prune --dry-run
git worktree prune
```

`git worktree remove` 是可逆性較低的操作；若仍需保留未提交成果，先 commit、建立 patch 或保留整個 worktree。若 worktree 已被手動刪除，才使用 `git worktree prune` 清理遺留的 metadata；不要把 prune 當成一般刪除流程的替代品。若 branch 尚未合併，`git branch -d` 會拒絕刪除；不得直接改用 `-D`，除非已明確確認成果不再需要。

回復未合併任務的優先順序：保留 worktree → commit 或建立 patch → 重新審查 → 決定合併或放棄。不要用 `git reset --hard`、`git clean -fd` 或 `git branch -D` 取代審查與備份。

## 10. 建議協作流程

1. 主 agent 讀取需求、`AGENTS.md`、`pyproject.toml`、`uv.lock` 與現有測試，建立任務清單。
2. 標出檔案重疊與任務依賴；只有互不重疊且共用資源已隔離的任務才平行執行。
3. 固定整合分支與基準 commit，為每個任務建立唯一 branch 與 worktree。
4. 在各 worktree 執行 `uv sync --locked`，必要時安裝 Playwright 瀏覽器。
5. 從各自 worktree 啟動 OpenCode subagent，提供完整任務契約與驗收條件。
6. Subagent 完成實作、驗證並提交；主 agent 審查 commit、diff、秘密與測試證據。
7. 按依賴順序逐一合併；每次重要合併後執行適當驗證，全部完成後執行完整驗證。
8. 確認成果可回復且沒有未提交變更後，再移除 worktree 與已合併 branch。

## 11. 優點、限制與風險

### 11.1 優點

- 每個 agent 有獨立的工作檔案、index、HEAD 與 branch，降低互相覆寫的機率。
- 研究、實作、測試與文件在可獨立時能平行進行。
- 變更可透過 branch、commit 與小型 diff 追蹤、審查與回退。
- 各 worktree 可建立自己的 `.venv`，降低 Python 環境互相污染。

### 11.2 仍需管理的風險

- 同一檔案或相依 API 的平行修改仍會在合併時衝突。
- worktree 共享 Git object database；若 repository metadata 或 Git 操作被不當修改，不能視為完全安全邊界。
- 每個 worktree 的 `.venv` 會增加初始化時間與磁碟使用量；大型依賴還可能造成下載或快取競爭。
- Python 依賴、Playwright 瀏覽器、OS 套件、GPU、外部 API、資料庫與固定 port 不是由 worktree 自動隔離。
- OpenCode permission 與 prompt 不能取代 sandbox、秘密管理、最小權限、人工審查與分支保護。
- `uv.lock` 若由不同 agent 同時修改，容易造成不必要衝突；依賴更新應指定單一負責 agent。
- 版本、模型、OpenCode 設定欄位與權限行為可能變更；導入前應使用實際版本執行 `opencode --help`、設定驗證與最小試跑。

## 12. 驗收條件

- [ ] 文件使用目前 OpenCode 支援的 `.opencode/agents/*.md` 或 `opencode.json` agent 設定，而非未驗證的 `agents.yaml` 範例。
- [ ] 每個 subagent 都有唯一 branch、唯一 worktree、明確基準 commit 與明確工作目錄。
- [ ] 文件包含建立、初始化、啟動、交付、審查、合併、衝突處理、回復與清理流程。
- [ ] 每個工作目錄都使用 `uv sync --locked`；不把不存在的 pytest 命令當作本 repository 的固定前提。
- [ ] 文件說明 Playwright 瀏覽器安裝、`.venv`、lockfile 與外部共享資源的限制。
- [ ] 文件要求主 agent 在合併前驗證 diff、秘密、未提交變更與測試結果。
- [ ] 文件以繁體中文撰寫，術語、命令、路徑與程式碼區塊一致。
- [ ] 可依本文件建立專案級 OpenCode agent，並由新加入的開發者重現最小流程。

## 13. 實施前檢查清單

在正式啟用前，應以實際環境完成一次最小演練：

```bash
git status --short
REPO_ROOT="$(git rev-parse --show-toplevel)"
WORKTREE_ROOT="${WORKTREE_ROOT:-$REPO_ROOT/../worktrees}"
mkdir -p "$WORKTREE_ROOT"
git worktree add -b agent/smoke "$WORKTREE_ROOT/agent-smoke" main
cd "$WORKTREE_ROOT/agent-smoke"
uv sync --locked
uv run python --version
git diff --check
git status --short
cd "$REPO_ROOT"
git worktree remove "$WORKTREE_ROOT/agent-smoke"
git branch -d agent/smoke
git worktree prune --dry-run
```

若實際 agent 設定、測試命令或 Playwright 瀏覽器需求與上述不同，必須先更新本文件與 `AGENTS.md`，再讓其他人依文件操作。

## 14. 後續工作與參考資料

1. 鎖定實際 OpenCode 版本、可用 model provider 與權限政策，並以 `opencode --help` 及設定驗證確認。
2. 將建立、檢查與清理流程包裝成經審查的腳本；腳本必須驗證 branch、path 與 dirty state，不可默認使用破壞性選項。
3. 在 CI 中執行 `uv sync --locked`、專案完整測試與必要的 Playwright browser setup。
4. 針對大型專案建立任務命名、依賴圖、共享服務隔離與衝突處理規範。

參考官方文件：

- [OpenCode Agents](https://opencode.ai/docs/agents/)
- [OpenCode Permissions](https://opencode.ai/docs/permissions/)
- [OpenCode Rules（AGENTS.md）](https://opencode.ai/docs/rules/)
- [Git git-worktree](https://git-scm.com/docs/git-worktree)
- [uv sync](https://docs.astral.sh/uv/reference/cli/)
