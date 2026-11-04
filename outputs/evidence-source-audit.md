# 公開評測證據查核

查核日期：2026-11-04。以下為公開證據盤點，不會匯入目前可執行的 WeatherNext deployment，也不會授予路由核准。

## 找到的同條件分數

WeatherBench 2 分數表的 2020、240×121 grid、Z500、day 5 分組列出：GenCast mean 對 ERA5 的 RMSE 為 262.4 m²/s²；GraphCast 對 ERA5 為 274.3 m²/s²；Pangu-Weather 對 ERA5 為 294.3 m²/s²。三列都標為 maintainer-run。三者同屬該榜單所列 deterministic Z500 day-5 結果，但目前可查到的呈現資料未提供權重 digest、精確模型版本、起報樣本數、信賴區間或完整結果設定 digest。

分數數值由 [Project AURION 的 WeatherBench 2 分數頁](https://aurion.semai.id/benchmarks/weatherbench-2/)讀取；該頁逐筆列出設定、執行者和來源，並連回 [WeatherBench 2 官方分數頁](https://sites.research.google/gr/weatherbench/)和官方互動圖表。AURION 將目前列出的 106 筆結果標成 maintainer-run、0 筆 independent。這是次級資料整理，不能視為獨立重算。官方 [WeatherBench 2 FAQ](https://sites.research.google/gr/weatherbench/faq/)確認 Pangu-Weather 的 2020 評測使用 ERA5、GraphCast 頁面列出其訓練資料年份；官方論文說明不同模型可能使用不同 ground truth 與初始化條件，需檢視每一筆設定，不可只按數字排序。

此分數表有兩項明確限制。首先，benchmark 的受評資源是全球大氣場模型，不是本專案現有的單點降水 API；Z500 RMSE 不能代表台中降雨量預報品質。其次，基準列未提供可與本專案 Profile `source.revision` 或 `artifact_digest` 對應的權重身分。因此，這些是有來源的歷史 benchmark 記錄，但尚非本 Router 可核准、可套用到 WeatherNext API 的路由證據。

| 資源 | 指標與值 | 條件 | 執行者／來源身分 | 版本與不確定性 |
|---|---:|---|---|---|
| GenCast mean | RMSE 262.4 m²/s²，越低越好 | Z500、day 5、2020、240×121、vs ERA5 | WeatherBench maintainer-run；AURION 逐筆來源連官方 scoreboard | 權重 revision/digest、樣本數與信賴區間未列 |
| GraphCast | RMSE 274.3 m²/s²，越低越好 | 同上 | 同上 | 同上 |
| Pangu-Weather | RMSE 294.3 m²/s²，越低越好 | 同上 | 同上 | 同上 |

已查核來源：

- [WeatherBench 2 官方 GitHub repository](https://github.com/google-research/weatherbench2)，Apache-2.0 授權適用於 repository 程式碼；本次未下載或複製模型權重或資料。
- [WeatherBench 2 官方 benchmark paper](https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2023MS004019)，記錄評測原則和 ground-truth 差異。
- [WeatherBench 2 官方 FAQ](https://sites.research.google/gr/weatherbench/faq/)，記錄參評模型、訓練／初始化資訊與指標定義。
- [AURION benchmark table](https://aurion.semai.id/benchmarks/weatherbench-2/)，本次數字的可讀逐筆轉錄來源；頁面日期顯示 2026-10-10，頁面提供 CSV 連結。本次只查閱網頁，沒有下載 CSV，所以沒有本地檔案 SHA-256。AURION 表格的獨立再利用授權未在本次查核中確認。
- [WeatherBench 2 dataset guide](https://weatherbench2.readthedocs.io/en/latest/data-guide.html) 指出各資料 bucket 各有授權，部分限研究用途。本次未取得 benchmark 資料集、也未假設它可商用。

本次沒有找到足以把上述全球大氣場分數綁定到本專案單點降水 API 的證據。因而沒有把這些實際分數寫入 Profile、approval ledger 或離線排序測試；排序測試資料均明確標為人工合成。
