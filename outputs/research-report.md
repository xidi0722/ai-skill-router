# Universal Model Router：先行研究

查核日期：2026-11-04。研究範圍為可公開檢視的 GitHub 原始碼、官方文件與原始論文；不代表已搜尋或排除所有私有及商業系統。

### 查核版本快照

版本資訊以本次查核時官方文件／GitHub Releases 可見內容為準；`main` 文件會變動，未標明版本的項目不推測版本號。

| 項目 | 查核快照 |
|---|---|
| HuggingGPT / JARVIS | 檢視 `main` README；最後一筆明確日期更新為 2023-07-28，README 表示規劃評估和重建，未以新版實作為已驗證前提。 |
| ARD | `ard-spec` README 標示 v0.91、開放演進中；規格狀態 Proposal。 |
| hf-discover | GitHub Release v1.3.7，commit `02c41aa`；README／變更紀錄仍提到 ARD v0.5 envelope。這是與 ARD v0.91 並存的版本互通落差。 |
| MCP | 穩定規格 `2026-07-28`，官方 repo release commit `5f5440b`。舊版 `2025-11-25` 仍需考慮相容性。 |
| smolagents | GitHub Release v1.26.0，commit `12c1bc8`。 |
| LiteLLM | GitHub Releases 查核到 v1.106.7；比較範圍限於 Auto Router 的已設定模型池路由功能。 |
| inference.sh | 使用官方線上 MCP connector 文件；該文件未提供本次可固定的版本／commit，故只將它列為文件描述的託管目錄能力。 |

來源：[JARVIS README](https://github.com/microsoft/JARVIS/blob/main/hugginggpt/README.md)、[ARD spec repository](https://github.com/ards-project/ard-spec)、[hf-discover releases](https://github.com/huggingface/hf-discover/releases)、[MCP releases](https://github.com/modelcontextprotocol/modelcontextprotocol/releases)、[smolagents releases](https://github.com/huggingface/smolagents/releases)、[LiteLLM releases](https://github.com/BerriAI/litellm/releases)。

## 結論

本次查核沒有找到一個公開專案能證明已完整實作「跨目錄自主發現、按領域證據選擇、跨型態執行、領域驗證、安全治理」全部能力。最接近的開源研究系統是 HuggingGPT；目前也有目錄協定、通用 MCP 應用目錄和模型平台分別涵蓋流程中的部分環節。

因此，不宜把「LLM 搜尋模型並呼叫工具」當成主要創新。值得研發的缺口是：用統一的執行契約和適用條件描述資源，讓路由結果可由同類評測證據支持，並在證據不足時降低信心或拒絕執行。

## 方案比較

| 方案 | 查核到的實際能力 | 未解決的需求 |
|---|---|---|
| HuggingGPT / Microsoft JARVIS | 論文及 README 描述任務規劃、模型選擇、執行和回覆整理。論文將模型按任務篩選，再按 Hub 下載量選前 K 名。 | 下載量不是適用性或準確度的可靠證據；未提供跨領域統一執行描述、可比較的驗證證據與完整的安全模型。README 最新列出的日期更新是 2023-07，並提到規劃重建。參考：[原始碼 README](https://github.com/microsoft/JARVIS/blob/main/hugginggpt/README.md)、[論文](https://openreview.net/pdf?id=yHdTscY6Ci)。 |
| ARD | 規格描述 Agentic Resource 的目錄、搜尋和聯邦導覽；最新查核版本標示 v0.91、Proposal，並以 JSON-LD 擴充描述欄位。 | ARD 是發現層，不是推論協定、領域評測標準或可信度背書。參考：[ARD 規格](https://github.com/ards-project/ard-spec/blob/main/spec/ard.md)。 |
| Hugging Face hf-discover | 開源 Client/Server 可搜尋 Skills、MCP Servers 和 Spaces，並導覽 ARD 目錄。README 說搜尋 Spaces 僅返回目前 runtime 為 RUNNING 的項目。 | 「Space 正在執行」不是「模型適用」或「品質已驗證」。README 說它目前使用 ARD v0.5 envelope，而上游規格頁為 v0.91 Proposal；整合時須處理版本差異。參考：[hf-discover README](https://github.com/huggingface/hf-discover)。 |
| MCP 與 MCP Registry | MCP 定義 Client/Server 通訊和工具、資源等介面；官方 Registry 是 MCP Server 目錄。MCP Server Card 用於取得單一 Server 的身分與連線資訊，執行時工具仍需經 MCP 查詢。參考：[MCP 2026-07-28 server/discover](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/server/discover.mdx)、[Server Card discovery](https://github.com/modelcontextprotocol/ext-server-card/blob/main/docs/discovery.md)、[Official MCP Registry](https://registry.modelcontextprotocol.io/)。 | MCP 不決定某項科學任務該使用哪個模型，也不提供模型品質基準或輸出正確性保證。 |
| Hugging Face Hub、MCP、Inference Providers 和 Spaces | Hub 提供模型、資料集、Space、文件和評測結果；HF MCP 支援 Hub 搜尋、Jobs，以及在啟用 Dynamic Spaces 時探索並呼叫 MCP 相容 Spaces。Gradio Space 可提供 API。參考：[HF MCP](https://huggingface.co/docs/hub/en/agents-mcp)、[Spaces as API endpoints](https://huggingface.co/docs/hub/en/spaces-api-endpoints)、[Inference Providers](https://huggingface.co/docs/inference-providers/index)。 | 這些功能支援 HF 生態系搜尋與執行，不等於跨來源的能力比較或領域品質驗證。Hub Model Card 是 Markdown 加 metadata；結構化評測功能目前仍標示為進行中。參考：[Model Cards](https://huggingface.co/docs/hub/en/model-cards)、[Evaluation Results](https://huggingface.co/docs/hub/en/eval-results)。 |
| smolagents | Agent 執行框架，可接 MCP、HF InferenceClient 和 Gradio Space。從 Hub 載入工具涉及執行遠端程式碼，文件要求信任來源。參考：[工具文件](https://github.com/huggingface/smolagents/blob/main/docs/source/en/tutorials/tools.md)。 | 可提供執行框架，不會自動提供通用資源目錄或證據式路由。 |
| LiteLLM Auto Router | 在使用者已設定的模型池和 tiers 中，按請求選擇模型。參考：[Auto Router 文件](https://docs.litellm.ai/docs/auto_router/)。 | 主要是已部署 LLM 間的選擇，不是跨領域模型與科學工具的全球探索。 |
| inference.sh | 官方文件描述應用目錄、app_list/app_get/app_run/task_get 等工具，也能透過 MCP proxy 連接其他 MCP Server。這是接近「目錄＋執行」的託管服務。參考：[MCP Server 文件](https://inference.sh/docs/connectors/mcp-server)。 | 查閱的文件沒有顯示獨立科學基準驗證、跨領域評測比較或完整開源的通用能力路由器。不能把應用清單與 Agent 呼叫視為已完成證據式模型路由。 |

## 重要例子：天氣預報

Google DeepMind 的 WeatherNext repository 將 GraphCast 和 GenCast 列為較早的模型家族，並列出直接取得預報資料的服務平台。Open-Meteo 提供 WeatherNext 2 API。其文件指出，WeatherNext 原生總降水是六小時累積資料；API 對部分雨量欄位進行衍生處理，也會按本地時區彙總日資料。這顯示任務路由需要知道資料來源、時間解析度和衍生欄位，不能只看模型名稱。

參考：[Google DeepMind WeatherNext repository](https://github.com/google-deepmind/weathernext)、[Open-Meteo WeatherNext 2 API](https://open-meteo.com/en/docs/google-weathernext-api)。

## 研發判斷

建議整合既有目錄和執行協定；自行研發的部分集中在：

1. Model Artifact、Capability、Deployment、Evidence 和 Runtime Status 的分層資料模型。
2. 跨來源的 Profile 正規化與適用性硬篩選。
3. 僅比較相同任務與相同評測條件的證據式路由。
4. 分領域的輸出驗證與不確定性說明。
5. 具最小權限和來源驗證的執行治理。

跨領域不存在通用單一準確度。天氣應按變數、預測時距、區域、回測資料與機率校準比較；數學可做符號化或殘差驗算；影像應用相符資料集的任務指標；生物模型需使用領域基準或實驗觀測。當證據不可比時，路由器應 abstain 或清楚標示為未驗證結果。
