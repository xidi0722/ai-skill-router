# Universal Model Router：實作狀態

查核日期：2026-11-04。此文件區分目前程式碼與建議中的後續工作。

自訂工具階段：Python 應用可明確注入 `AdapterRegistry(additional_adapters=...)` 到 `RouterService`；不能覆蓋內建 adapter，且自訂程式在應用程式權限下執行，沒有沙箱。`examples/custom_tool.py` 示範 Fraction 和 SymPy、不同的合成資料、獨立帳本、版本變動與撤銷。Windows 11、Python 3.12.14 的新環境執行回歸測試 48 passed；資料集、示範版本與核准人均非真實 benchmark。自訂 adapter 不會從遠端 metadata 自動載入，CLI/HTTP 服務也不會自動載入。

本輪新增 Python 和 localhost HTTP 整合範例、實際路由結果驅動的合成候選比較表，以及 WeatherNext 部署缺少已核准降雨證據時的離線 abstain 範例；後者沒有匯入或比較 WeatherBench 分數。Windows 11／Python 3.12.14 新環境執行 46 個測試與四個範例成功，HTTP 需允許 localhost。真實模型排名品質仍未驗證。

前一階段查核時此目錄尚未初始化 Git；後續已建立 repository 並連接 `origin`。2026-11-04 本階段開始時，本機 `main` 和遠端為 `fe4c3e0`，工作目錄乾淨，未找到 `AGENTS.md`。

本階段新增離線 Demo、雙語入口、貢獻文件、CI workflow 與推廣材料。乾淨隔離環境安裝和 Demo 已於 Windows 11／Python 3.12.14 驗證，既有測試 46 passed。[遠端 CI](https://github.com/xidi0722/ai-skill-router/actions/runs/41841204321) 在提交 `2b0b14c` 的 Windows 與 Ubuntu、Python 3.11 和 3.12 四種組合通過；macOS 與實際終端截圖尚未驗證或製作。詳見 [launch-verification.md](launch-verification.md)。

## 已實作

- Capability Profile JSON Schema 2020-12，並載入本機 curated profile。
- Hugging Face Hub 只讀 metadata connector；已發現的模型不會自動取得部署或執行資格。
- Router 對 task ID、JSON Schema 輸入、適用條件、相同任務及指定地區／時距的評測證據、管理者核准的完整評測紀錄 digest、授權政策、逐部署成本政策、過期 runtime 探測及已註冊 adapter 做資格篩選；不合格時 abstain。只填 `verified_by` 不會取得 independent 等級。
- Evidence Contract 現支援綁定 artifact ID/revision/digest、Capability input/output schema digest、dataset revision/split/config digest、適用條件、metric 數值／單位／方向和評測來源。新評測 digest 綁定完整 Profile artifact identity；Profile schema 或 artifact revision 改動會讓契約檢查或 digest 比對失敗。
- 外部 approval ledger 與匯入 Profile 分離，支援核准及撤銷。檔案由呼叫者指定，CLI/HTTP 都可載入。它目前是本機管理 JSON，未簽章、未驗證管理者身分，也沒有不可竄改儲存。
- 僅在 `require_quality_comparison` 啟用時，Router 比較同 task、schema contract、dataset/split/config、地區、時距、解析度、metric、單位及方向的已核准紀錄；缺值、撤銷、條件不同、平手或信賴區間重疊時 strict 路由 abstain。一般路由保留既有相容行為。
- SymPy 受限 AST 方程求解器，限制運算語法、輸入大小、變數數量、非負指數與多項式次數；除法僅允許除以非零常數，並把求得的解代回原式。
- Open-Meteo WeatherNext 2 固定端點 adapter，驗證座標、時區、日期、回應結構、欄位型別和非負值，並明確標示尚未由本專案回測。
- Python service、CLI、只綁定 localhost 的 HTTP API；路由回應帶有 profile、部署、adapter、證據等級、輸入 SHA-256 digest 與執行時間戳。Digest 不保留原始輸入，且不等同可重播的完整執行紀錄。
- 執行失敗及輸出契約失敗會回傳結構化 execution 狀態、穩定錯誤碼、時間戳和已選部署 provenance；對外錯誤訊息不包含 Adapter 的原始例外文字或請求 URL。Abstain 保留逐候選拒絕理由。
- 威脅模型與先行研究報告。
- 離線合成路由評測工具與 50 個可重現案例，分 development 與 holdout 子集，比較熱門度、文字相關性及 evidence router；數字只驗證政策 fixture 行為。
- 36 案同條件比較 fixture，包含熱門度、文字相關性、證據等級與數值證據四種策略，固定 seed 生成 metadata；全部是人工合成資料，不代表實際模型品質。

## 尚未實作／尚未驗收

- 沒有 ARD Registry、MCP Registry、MCP Server Card 或 MCP client connector；HF connector 也未把結果匯入執行清單。
- 沒有自然語言 Task Request parser；呼叫者需先提供正規化 task ID 和輸入欄位。
- 一般路由仍以證據等級、服務狀態和穩定 ID 排序；只有明確要求數值品質比較時使用新比較器。沒有真實來源證據能映射至目前可執行的 WeatherNext deployment，也沒有天氣歷史回測或校準度評估。
- 天氣服務端模型 revision 未固定，且目前沒有計算集合 spread／機率校準；輸入 digest 和時間戳只能協助追蹤，不能重現供應商當時的模型權重或資料快照。
- 沒有通用第三方 hosted API、Gradio、MCP 或可下載模型執行器；目前只有兩個明確 allowlist adapter。
- 沒有安全沙箱執行外部程式、容器隔離、模型權重 digest 驗證、認證密鑰管理或完整費用追蹤。
- SymPy 已移到可終止的 spawn 子程序並設 5 秒 wall-clock timeout；仍沒有記憶體配額或完整 OS 沙箱。localhost HTTP API 沒有併發或速率限制，不應直接公開到網路。
- WeatherBench 2 公開列表可讀取 2020 Z500 day 5 同條件的 GenCast mean、GraphCast、Pangu-Weather 三個 maintainer-run RMSE 值；來源轉錄與不確定性見 `outputs/evidence-source-audit.md`。列表無權重 digest／精確 revision、樣本數和信賴區間，任務是全球 Z500 而非本專案的單點降水；故未匯入 Profile／approval ledger，不能支撐現有 WeatherNext API 的選擇。
- 既有 50 案政策評測與新增 36 案排序評測都屬合成 fixture。正向政策案例接受多個候選；排序案例唯一最佳候選由人工標籤配合人工分數情境建立，數值比較器在這些案例上的 100% 只驗證實作遵循 fixture，不是實際模型品質證據。
- wheel 已建置並安裝到專案隔離目錄，安裝後 CLI 解出 `x**2 - 4 = 0` 得到 -2、2，兩解代回成功。最新版原始碼測試在 Python 3.12.14、jsonschema 4.26.0、SymPy 1.14.0、pytest 9.2.0 上 **46/46 通過**，含 localhost TCP smoke test、Evidence Contract、revision/tamper/revocation、數值比較及原有回歸測試。兩套離線評測均重跑，沒有呼叫即時外部 API或部署服務。
- 此 Codex Windows 執行環境的系統 `python` 命令是不可用的 WindowsApps placeholder；隨附 Python 3.12.14 runtime 建立的 `.venv` 沒有 `ensurepip`，因此本次以 bundled runtime 建置 wheel 並用 `pip --prefix .venv` 安裝。此環境可用 `.\.venv\Scripts\python.exe -m pytest -q` 執行（46 passed），新建的標準 Python 環境則照 README 的 venv 命令即可。

## 解讀限制

SymPy 的代回檢查是單次執行的數學一致性檢查，不是通用的模型品質 benchmark。WeatherNext adapter 回傳供應商預報及格式／單位檢查，不代表本專案驗證了預測準確性。兩者不可比較成共同分數。

