# Evidence Routing Ranking Evaluation

36 cases: 24 development, 12 holdout. All ranking cases are synthetic fixtures.

All strategies receive identical two-candidate pools treated as already eligible for ranking. The fixture does not exercise real capability/deployment eligibility or adapter execution; this measures ranking logic only.

| Strategy | Top-1 hit | Wrong route | Abstain precision | Abstain recall | Coverage |
|---|---:|---:|---:|---:|---:|
| 熱門度 | 58.3% (7/12) | 80.6% (29/36) | N/A (0 predicted) | 0.0% (0/24) | 100.0% (12/12) |
| 文字相關性 | 66.7% (8/12) | 77.8% (28/36) | N/A (0 predicted) | 0.0% (0/24) | 100.0% (12/12) |
| 證據等級 | 50.0% (6/12) | 83.3% (30/36) | N/A (0 predicted) | 0.0% (0/24) | 100.0% (12/12) |
| 同條件數值證據 | 100.0% (12/12) | 0.0% (0/36) | 100.0% (24/24) | 100.0% (24/24) | 100.0% (12/12) |

## Failure types

| Scenario | Cases | Numeric strategy abstained |
|---|---:|---:|
| `lower` | 6 | 0 |
| `higher` | 6 | 0 |
| `tie` | 6 | 6 |
| `dataset-mismatch` | 6 | 6 |
| `unapproved` | 6 | 6 |
| `stale-artifact` | 6 | 6 |

## Representative cases

| Case | Label | Numeric result | Reason |
|---|---|---|---|
| `rank-01` (lower) | candidate-a | candidate-a | hand-authored fixture declares candidate-a best under the stated comparable metric |
| `rank-02` (higher) | candidate-a | candidate-a | hand-authored fixture declares candidate-a best under the stated comparable metric |
| `rank-03` (tie) | abstain | abstain | tie makes metric evidence insufficient; abstain |
| `rank-04` (dataset-mismatch) | abstain | abstain | dataset-mismatch makes metric evidence insufficient; abstain |
| `rank-05` (unapproved) | abstain | abstain | unapproved makes metric evidence insufficient; abstain |
| `rank-06` (stale-artifact) | abstain | abstain | stale-artifact makes metric evidence insufficient; abstain |

## Interpretation

These results establish only that the comparator follows the hand-authored fixture labels. They do not establish real model quality, WeatherBench performance generalization, or end-to-end deployment selection. The synthetic scores are never copied into real Profiles.
