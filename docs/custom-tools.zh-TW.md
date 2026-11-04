# 接入可信任的本機工具

於 clone 後安裝 `python -m pip install -e .`，再執行 `python examples/custom_tool.py`。範例以 Python `fractions.Fraction` 與 SymPy 求解 `a*x+b=0`，建立兩份 Profile 和本機 deployment。測試資料、版本標籤及核准人均為教學 fixture；失敗數由實際執行計算，但兩份微型資料集不同，不能用於比較準確性。`example-v1` 不是固定的程式碼 digest。真正比較需要相同且具代表性的資料、切分、執行設定、版本、獨立審查與不確定性。

程式將 Profile 與分開管理、未簽章的核准帳本寫入暫存目錄；證據綁定 artifact 身分、任務契約、資料與指標，核准依 digest 記錄。撤銷時將 digest 加入 `revoked` 並重新載入服務；版本改動後應重新評估、審核並核准新的 digest。Digest 只能辨識紀錄是否變更，不能證明內容正確或審核者身分。

請參考 [English guide](custom-tools.md) 的程式碼：以 `AdapterRegistry(additional_adapters={"my-adapter": adapter})` 將可信任的物件明確傳給 `RouterService(adapter_registry=registry)`。物件須提供 `execute(inputs)`，回傳符合 Profile 輸出 Schema 的結果。程式以應用程式權限執行，沒有沙箱；不從下載的 metadata 自動載入程式。不能覆蓋內建 adapter，`umr serve` 亦不會自動載入這些自訂 adapter。

一般路由依現有排序規則選擇，不會自動比較數值。指定 `require_quality_comparison` 與 `comparison_metric_id` 後，範例因資料集不同而 abstain；版本變動與撤銷核准亦 abstain。輸入不合法及未註冊 adapter 在執行前被拒絕；`a=0` 則回傳結構化執行失敗。呼叫者應檢查 `decision.reason`、`rejected`、`comparison.reasons`、`provenance` 及 `execution`；HTTP 的 abstain 或 adapter 失敗通常仍回傳 200。詳見 `examples/http_integration.py` 與[證據說明](../outputs/evidence-routing-evaluation.md)。
