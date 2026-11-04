# Offline Router Evaluation

Cases: 50 total; 40 development; 10 holdout.

All profiles, evidence and labels are synthetic fixtures. This checks policy behavior only; it does not measure real model quality or predict performance on user queries. The holdout uses different input variants and reserved failure types, but remains a small, hand-authored fixture set.

## Fixed labels and metric definitions

Labels are assigned before running strategies. A qualified case has a non-empty acceptable candidate set; any candidate in that set is accepted and abstention is a miss. A must-abstain case has no admissible candidate; selecting any candidate is a wrong route. Positive cases accept multiple synthetic candidates, so they do not define a real ranking among eligible models.

- **Top-1 hit rate (qualified):** qualified cases selecting an acceptable candidate / all qualified cases; abstentions count as misses.
- **Wrong-route rate (all):** qualified cases that abstain or select an unacceptable candidate, plus must-abstain cases that select anything / all cases.
- **Abstain precision:** correct abstentions on must-abstain cases / all predicted abstentions; N/A if there are no predicted abstentions.
- **Abstain recall:** correct abstentions on must-abstain cases / all must-abstain cases; N/A if that denominator is empty.
- **Coverage (qualified):** qualified cases with any selected candidate / all qualified cases.

Ungated baselines show the effect of omitting capability/execution checks. Shared-eligibility rows use the same eligible candidate IDs returned by the router and therefore isolate ranking. All strategies receive the same underlying candidate pool for each case.

| Strategy | Top-1 hit (eligible) | Wrong route (all) | Abstain precision | Abstain recall | Coverage (eligible) |
|---|---:|---:|---:|---:|---:|
| Popularity (ungated) | 0.0% (25) | 100.0% (50) | N/A | 0.0% | 100.0% |
| Text relevance (ungated) | 0.0% (25) | 100.0% (50) | N/A | 0.0% | 100.0% |
| Popularity + shared eligibility | 100.0% (25) | 0.0% (50) | 100.0% | 100.0% | 100.0% |
| Text relevance + shared eligibility | 100.0% (25) | 0.0% (50) | 100.0% | 100.0% | 100.0% |
| Evidence router | 100.0% (25) | 0.0% (50) | 100.0% | 100.0% | 100.0% |

## Holdout subset

| Strategy | Top-1 hit (eligible) | Wrong route (all) | Abstain precision | Abstain recall | Coverage (eligible) |
|---|---:|---:|---:|---:|---:|
| Popularity (ungated) | 0.0% (5) | 100.0% (10) | N/A | 0.0% | 100.0% |
| Text relevance (ungated) | 0.0% (5) | 100.0% (10) | N/A | 0.0% | 100.0% |
| Popularity + shared eligibility | 100.0% (5) | 0.0% (10) | 100.0% | 100.0% | 100.0% |
| Text relevance + shared eligibility | 100.0% (5) | 0.0% (10) | 100.0% | 100.0% | 100.0% |
| Evidence router | 100.0% (5) | 0.0% (10) | 100.0% | 100.0% | 100.0% |

## Abstention cases by failure type

| Failure type | Cases | Router abstained | Popularity raw wrong routes | Text raw wrong routes |
|---|---:|---:|---:|---:|
| `cost-over-budget` | 1 | 1 | 1 | 1 |
| `data-license-unknown` | 4 | 4 | 4 | 4 |
| `horizon-out-of-range` | 4 | 4 | 4 | 4 |
| `independent-evidence-missing` | 4 | 4 | 4 | 4 |
| `invalid-input-schema` | 1 | 1 | 1 | 1 |
| `missing-input` | 4 | 4 | 4 | 4 |
| `region-mismatch` | 1 | 1 | 1 | 1 |
| `runtime-offline` | 1 | 1 | 1 | 1 |
| `unregistered-adapter` | 1 | 1 | 1 | 1 |
| `unsupported-task` | 4 | 4 | 4 | 4 |

## Interpretation

The gated baselines and router operate on a closed-world fixture where each eligible candidate has been pre-labelled as acceptable except in reserved policy cases. A perfect score means the implementation followed these labels; it does not establish that evidence-tier ranking selects more accurate real models. Because all eligible positive candidates are accepted, shared-eligibility ranking metrics cannot distinguish their relative quality. The raw popularity and text baselines are intentionally ungated and demonstrate why metadata relevance or downloads alone can select a non-executable candidate.

## Representative baseline failures

- `popularity_ungated` on `positive-01` selected `math.metadata`; expected math.primary, math.audited, math.regional. 具備本地 allowlisted adapter、輸入契約和適用條件的合成候選可執行；熱門 metadata-only 候選不合格。
- `text_relevance_ungated` on `positive-01` selected `math.metadata`; expected math.primary, math.audited, math.regional. 具備本地 allowlisted adapter、輸入契約和適用條件的合成候選可執行；熱門 metadata-only 候選不合格。

Re-run with `python tools/run_offline_evaluation.py`; complete case records and predictions are in `offline-evaluation.json`.
