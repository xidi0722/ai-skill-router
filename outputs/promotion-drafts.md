# Publication drafts — review before posting

Repository: https://github.com/xidi0722/ai-skill-router
Offline demo: https://github.com/xidi0722/ai-skill-router/blob/main/examples/offline_demo.py
Releases: https://github.com/xidi0722/ai-skill-router/releases

## Technical article (English)

### When should an agent refuse to call a tool?

A tool can exist in a catalogue and still be unsuitable for a request. A benchmark can describe a different dataset, forecast horizon or model revision. What should an agent do when it cannot establish that the evidence applies?

AI Skill Router is an early Python prototype for exploring that question. It checks candidate eligibility, keeps task and artifact identities with evidence, and can abstain when a required comparison is missing or incompatible. Its approval ledger is local and unsigned; an approved digest identifies a record, not a guarantee that the evidence is true.

Try the offline example from the repository root:

```sh
python -m pip install -e .
python examples/offline_demo.py
```

The first step solves an equation with SymPy and checks returned solutions by substitution. The next two steps use explicitly synthetic candidates: compare their scores, then change an artifact revision and observe abstention. These numbers are fixtures, not model benchmarks. The project does not yet establish real-world selection quality; the weather adapter has not been independently backtested.

I would value feedback on the decision contract: what evidence would you require before allowing an agent to compare tools, and where should it abstain?

### 技術文章繁體中文

**Agent 何時應拒絕呼叫工具？** 工具存在於目錄中，仍可能不適用於目前問題；benchmark 也可能對應不同資料集、時距或模型版本。AI Skill Router 是一個早期 Python 原型，檢查候選資格、保留版本綁定證據，並在必要比較無法成立時拒答。核准帳本是未簽章的本機檔案，digest 只辨識紀錄，不保證評測真實。

從 repository 執行 `python -m pip install -e .` 與 `python examples/offline_demo.py`：先由 SymPy 求解並代回，再使用合成候選比較，最後因 revision 變動而 abstain。合成分數不是實際 benchmark；天氣 adapter 尚未獨立回測。想請教：你會要求哪些證據後才讓 Agent 比較工具？

## Show HN draft (English)

Title: Show HN: AI Skill Router – a prototype that can abstain when tool evidence is stale

I built an early Python prototype for routing scientific tools using explicit eligibility and version-bound evidence. The offline demo solves an equation, compares synthetic candidates, then abstains after a revision change. Install with `python -m pip install -e .`, then run `python examples/offline_demo.py`. The comparisons are fixtures; real model selection quality and weather forecasts are not independently validated. Where would this contract fail in an agent you maintain?

繁體中文：我做了一個早期 Python 工具路由原型，用資格與版本綁定證據來決定是否 abstain。Demo 可離線求解方程、比較合成候選並展示版本變更後拒答；真實模型選擇品質尚未驗證。你維護的 Agent 會在哪些情況下需要不同契約？

## Developer community draft (English)

How do you prevent an agent from selecting a tool using benchmark evidence for an older artifact? AI Skill Router explores this with profile checks and a local approval ledger. Run `python -m pip install -e . && python examples/offline_demo.py`. The comparison data are synthetic and the ledger is unsigned. What fields would you add to the compatibility check? https://github.com/xidi0722/ai-skill-router

繁體中文：如何避免 Agent 使用舊版本 artifact 的 benchmark 選工具？此原型透過 Profile 與本機核准帳本探索這個問題。上述安裝與 Demo 命令可重現；比較資料為合成且帳本未簽章。你會增加哪些相容性欄位？

## Scientific-tool community draft (English)

We are exploring a small router that records why a scientific tool was eligible and can abstain when comparable evidence is missing. The offline example uses SymPy and synthetic comparison records: `python -m pip install -e . && python examples/offline_demo.py`. No forecast accuracy claim is made. What dataset/version or unit checks should be mandatory? https://github.com/xidi0722/ai-skill-router

繁體中文：此小型原型記錄科學工具為何合格，並在缺少可比較證據時拒答。離線例子使用 SymPy 與合成比較紀錄，不宣稱預報準確。你認為資料版本及單位應強制檢查哪些條件？

## Release notes draft (English)

Early prototype: local profiles, SymPy and fixed-host WeatherNext adapters, optional evidence comparison, abstention, CLI and localhost HTTP API. Offline demo and synthetic policy/ranking fixtures are included. Evidence ledger is unsigned; live weather accuracy and real model ranking remain unvalidated. Run `python examples/offline_demo.py` after installation. Feedback: which eligibility failure should be clearer?

繁體中文：早期原型包含本機 Profile、SymPy、固定主機 WeatherNext adapter、可選證據比較與拒答、CLI 和 localhost HTTP API。離線 Demo 與評測使用合成 fixture；帳本未簽章，實際天氣預報及模型排序品質尚未驗證。歡迎回饋需要更清楚呈現的資格失敗原因。

