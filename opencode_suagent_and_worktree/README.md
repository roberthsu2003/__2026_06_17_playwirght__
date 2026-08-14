# OpenCode Subagent 與 Git Worktree

本文件說明如何讓 OpenCode 的 subagent 各自使用獨立 Git worktree，安全地平行處理任務。完整規劃請參閱 repository 根目錄的 PRD.md。

## 核心原則

採用「一個 subagent、一個唯一任務分支、一個獨立 worktree」：

- 主 agent 負責拆解任務、建立 worktree、審查與合併。
- 每個 subagent 只在指定 worktree 中工作。
- 每個 worktree 使用唯一 branch，不共用同一個 checkout。
- 合併前必須完成 review 與專案實際測試。
- worktree 不會隔離共享資料庫、服務、port、外部 API 或秘密。

## OpenCode Subagent 設定

專案級 agent 可放在 .opencode/agents/，例如 .opencode/agents/implementer.md：

~~~markdown
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
~~~

也可以在 opencode.json 的 agent 區段定義 implementer、reviewer 等角色。設定欄位可能隨 OpenCode 版本變動；正式使用前請以 opencode --help 與該版本官方文件確認。權限設定是安全護欄，不能取代 worktree 隔離與人工審查。

## 建立 Worktree

先在主工作目錄確認 Git 狀態與工具版本：

~~~bash
git status --short
git worktree list
uv --version
opencode --version
~~~

若主工作目錄有未提交變更，先明確提交、暫存或保留，避免誤帶到新任務。建立一個實作任務用的 worktree：

~~~bash
git worktree add -b agent/implementer ../worktrees/agent-implementer main
~~~

Git 會自動建立 `../worktrees/agent-implementer` 資料夾，並將 `main` 分支的專案檔案放入其中。執行後可用 `git worktree list` 確認。

每個 branch 與 worktree 路徑都必須唯一。不要使用 -B 或 --force 覆蓋既有成果。若要從遠端最新版本開始，先執行 git fetch origin --prune，確認基準後再建立 worktree。

## 初始化與啟動 Subagent

每個 worktree 都要使用自己的 uv 環境：

~~~bash
cd ../worktrees/agent-implementer
uv sync --locked
uv run python --version
opencode
~~~

若本專案需要 Playwright 瀏覽器，另外執行：

~~~bash
uv run playwright install
~~~

啟動後提供完整任務資訊：

~~~text
任務 ID：T-001
工作目錄：/絕對路徑/../worktrees/agent-implementer
分支：agent/implementer
基準 commit：<建立 worktree 時記錄的 commit>
可修改範圍：<指定目錄或檔案>
不可修改範圍：其他 worktree、遠端設定、秘密檔案
驗收：完成指定功能並執行專案實際測試
交付：列出修改檔案、commit、驗證結果與剩餘風險；不得 push 或合併
~~~

## 交付、審查與合併

subagent 完成後：

~~~bash
git status --short
git diff --check
# 依專案實際設定執行測試，不要假設一定有 pytest
uv run <專案測試命令>
git add <明確列出的檔案>
git commit -m "feat: implement requested change"
~~~

主 agent 審查並合併：

~~~bash
git log --oneline --decorate -1 agent/implementer
git diff main...agent/implementer
git switch main
git merge --no-ff agent/implementer
~~~

若發生衝突，依任務依賴順序處理；不要以 git reset --hard 或 git checkout -- 直接丟棄變更。

## 清理

確認 branch 已整合、worktree 沒有未提交變更後：

~~~bash
git -C ../worktrees/agent-implementer status --short
git worktree remove ../worktrees/agent-implementer
git branch -d agent/implementer
git worktree prune
~~~

清理前若仍需保留成果，請先 commit、建立 patch 或保留 worktree。

## 優點

- **隔離性**：降低 agent 互相覆寫檔案與污染未完成變更的風險。
- **平行處理**：研究、實作、測試與文件可在任務獨立時同時進行。
- **可追蹤**：每項成果都有清楚的 branch、commit 與 diff。
- **容易審查與回復**：主 agent 能逐一檢視小型變更，必要時可單獨重做或回退。
- **環境干擾較少**：各 worktree 可各自執行 uv sync 與測試。

## 注意事項

- worktree 不能自動解決相同檔案或相同程式區段的合併衝突。
- 每個 worktree 可能需要獨立同步依賴，會增加磁碟與初始化時間。
- 不要提交 .env、token、cookie、私鑰或真實敏感測試資料。
- 若 agent 共用資料庫、服務或 port，請分配獨立資源或使用 mock。
- uv sync --locked 適合可重現初始化；依賴變更時應同步檢查 pyproject.toml 與 uv.lock。

## 快速驗收

~~~bash
git diff --check
uv sync --locked
uv run python --version
git worktree list
~~~

實際 worktree 建立演練需要 repository 的 Git metadata（例如 .git/refs）具備寫入權限。完整驗收條件與風險請參閱 PRD.md。

## 參考資料

- [OpenCode Agents](https://opencode.ai/docs/agents/)
- [OpenCode Permissions](https://opencode.ai/docs/permissions/)
- [OpenCode Rules（AGENTS.md）](https://opencode.ai/docs/rules/)
- [Git git-worktree](https://git-scm.com/docs/git-worktree)
- [uv sync](https://docs.astral.sh/uv/reference/cli/)
