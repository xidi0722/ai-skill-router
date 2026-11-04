# Evidence Contract 與路由比較評測

查核日期：2026-11-04。此階段加入版本綁定的 Evidence Contract、獨立 approval ledger、同條件比較器和 36 案排序 fixture。公開分數查核詳見 [evidence-source-audit.md](evidence-source-audit.md)。

## Evidence Contract

擴充 Capability Profile 的 `evaluations` 記錄。可比較記錄含 artifact ID 與 revision／digest、task ID、輸入／輸出 Capability schema digest、dataset ID／revision／split／設定 digest、地區／時距／解析度、帶單位與方向的 metrics，以及來源和 evaluator。舊版 evidence 仍可載入，但不視為數值可比較資料。

核准 digest 以 profile ID、Profile source 的 artifact ID／revision／digest 和完整評測記錄計算。比較器另外確認 Profile 的實際輸入／輸出 schema digest 與評測記錄一致。改動 artifact revision、分數、適用條件或契約會使原核准 digest 無法匹配。核准和撤銷列在獨立 JSON ledger，Profile 本身的 `verified_by` 不會核准證據。ledger 是本機管理的控制檔，尚未加入數位簽章、管理員身分驗證或不可竄改儲存；digest 只能辨識內容改動，不能證明評測真實。

比較前要求所有候選有已核准且未撤銷的記錄，且 task、contract digest、dataset revision、split、設定 digest、地區、時距、解析度、metric、unit 和方向一致。缺值、不可信、撤銷、版本不符或條件不同均回傳 incomparable。指標方向支援 lower／higher；同分、設定的最小差異未達門檻或信賴區間重疊時回傳 inconclusive。比較請求可用 `require_quality_comparison: true` 和 `comparison_metric_id`；不可比較時 Router abstain。一般路由維持舊行為。

approval ledger 格式：

```json
{
  "approvals": {
    "<sha256 digest>": {
      "approved_by": "local reviewer identity",
      "approved_at": "2026-11-04T12:00:00Z"
    }
  },
  "revoked": []
}
```

用 `umr route --approval-ledger evidence-approvals.json` 或 `umr serve --approval-ledger evidence-approvals.json` 載入。帳本必須由可信的本機管理者保護；此 MVP 沒有帳本簽章機制。

## 公開真實證據及其適用限制

WeatherBench 2 的公開分數清單可找到至少三個同條件全球預報結果：2020 年、240×121 grid、Z500 day 5、對 ERA5 的 RMSE 分別是 GenCast mean 262.4、GraphCast 274.3、Pangu-Weather 294.3 m²/s²，越低越好。紀錄標示 maintainer-run。官方頁面和資料限制、未固定 artifact revision 等細節見 [evidence-source-audit.md](evidence-source-audit.md)。

它們是全球大氣場評測，不能推論成台灣單點降水服務的品質；也沒有足夠 artifact 身分把分數綁定至目前的 Open-Meteo WeatherNext 2 adapter。因此它們尚未匯入 Profile 或 approval ledger，也沒有參與 Router 選擇。此處的公開證據能示範來源與適用邊界，不能證明現有 Hosted API 的排序品質。

## 36 案排序 fixture 結果

四種策略使用同一組兩個候選；評測把候選視為已通過前置資格篩選，只測排序邏輯，不測實際部署資格或執行。12 案有唯一手工標註優勝者，24 案因平手、資料集不符、未核准或 artifact 過期而必須 abstain。下載量、文字欄位與證據等級由固定 seed 獨立產生。所有分數和標籤都是合成資料。

| 策略 | Top-1 hit | 錯誤路由 | Abstain precision | Abstain recall | 合格覆蓋率 |
|---|---:|---:|---:|---:|---:|
| 熱門度 | 58.3% (7/12) | 80.6% (29/36) | N/A (0 predicted) | 0% (0/24) | 100% (12/12) |
| 文字相關性 | 66.7% (8/12) | 77.8% (28/36) | N/A (0 predicted) | 0% (0/24) | 100% (12/12) |
| 證據等級 | 50.0% (6/12) | 83.3% (30/36) | N/A (0 predicted) | 0% (0/24) | 100% (12/12) |
| 同條件數值證據 | 100% (12/12) | 0% (0/36) | 100% (24/24) | 100% (24/24) | 100% (12/12) |

這些分數只確認比較器遵循人工設定的 fixture；同條件數值策略的完美分數來自案例建構方式，不能當作真實排序能力證據。24 個必須 abstain 案分成 4 種情境，各 6 案：平手、資料集不符、未核准與 artifact revision 過期。Holdout 12 案只有 4 個合格案例，過小且仍為合成資料，只能當回歸檢查。

既有 50 案政策評測已保留於 `offline-evaluation.json` 和 `offline-evaluation.md`。它的正向標註讓多個候選同時可接受，所以不能評估合格候選間的排序品質。

## 重跑

```powershell
python -m pytest -q
python tools/run_offline_evaluation.py
python tools/run_evidence_ranking_evaluation.py
```

所有測試使用本機 fixture 或 mock；沒有呼叫即時天氣服務、下載公開 benchmark CSV、模型權重或資料集。公開來源結果目前只做人工查核，尚未有受控的原始資料檔和 SHA-256。下一步應先以固定 WeatherBench-X 設定和可追溯的結果檔重現公開分數，再建立能映射到可執行 artifact／deployment 的證據；否則系統只能證明證據比較邏輯，不能證明真實模型選擇品質。
