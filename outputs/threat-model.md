# Universal Model Router：威脅模型

## 資產與信任邊界

- 使用者輸入與上傳資料。
- API tokens、MCP credentials 和本機檔案。
- Discovery 回傳的 Model Card、Skill、MCP Server Card、OpenAPI/Gradio Schema 和其他 metadata。
- 模型權重、套件、容器和執行程序。
- Hosted API 的輸入輸出、計費和執行日誌。
- Profile、評測證據和路由紀錄。

目錄、模型卡、工具描述、API 回應和模型輸出一律視為不可信資料；它們不能改寫系統安全政策，也不能直接提供可執行指令。

## 主要威脅與控制

| 威脅 | MVP 控制 |
|---|---|
| 發現結果包含惡意指令或 Prompt injection | 把描述當資料，不納入 system policy；工具參數由程式端 Schema 驗證；模型輸出不得直接變成命令或程式碼。 |
| SSRF 或惡意重新導向 | MVP 不接受任意 endpoint URL；Weather adapter 使用程式固定的 HTTPS host；HF connector 僅呼叫固定 HF API host；設 timeout 和結果大小上限。 |
| 下載模型或 Hub tool 時執行惡意程式 | MVP 不執行遠端 repo 程式或任意下載權重；後續要先固定 revision/digest、掃描、授權檢查和隔離執行。 |
| API token 洩露或過度權限 | credentials 由 adapter/runtime 管理，不傳給 LLM、不存入 Profile；採最小權限和可撤銷 token。 |
| 超額費用或服務資源耗盡 | Weather API adapter 設網路 timeout 和回應大小上限；Profile 可限制已知成本，且未知成本可設拒絕政策。SymPy 有 AST、輸入長度、變數數量及多項式次數限制，並在可終止的 spawn 子程序設 5 秒 timeout；尚無記憶體配額或完整 OS 沙箱。HTTP 服務也尚無併發／速率限制，不能視為可承受不受信任的公開流量。 |
| 不符授權的模型、權重或資料 | 將 code、weights、data license 分欄；未確認授權時視為不符合，而不是猜測可用。 |
| 偽造或不可比的 benchmark | 保存 dataset revision、任務設定、來源和 evidence level；Profile 的 `verified_by` 字串不構成信任，只有管理者另行核准的完整評測紀錄 SHA-256 digest 才能升級為 reproduced／independent；不同 benchmark 的數值不直接加權比較。 |
| API 失效或模型輸出格式變更 | runtime timeout、錯誤回報、Schema validation；不得把格式錯誤或過期資料當有效答案。 |
| 服務在線被誤認為品質可靠 | availability 與 quality evidence 分欄；健康檢查只代表端點可達，不作準確度證據。 |

## 後續擴展前提

加入 MCP Server、Hub weights 或本機容器執行前，需另外設計身分驗證、scope 管理、軟體供應鏈、網路隔離、硬體與時間配額、使用者資料政策和稽核流程。MCP 協定相容本身不能取代這些控制。
