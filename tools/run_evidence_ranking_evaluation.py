"""Compare ranking policies on a fixed, synthetic 36-case evidence fixture."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import random
import re
from typing import Any

from umr.evidence import capability_contract_digest, compare_profiles, contract_evaluation_digest, contract_errors


ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "outputs" / "evidence-ranking-evaluation.json"
OUT_MD = ROOT / "outputs" / "evidence-ranking-evaluation.md"
METRIC = "weather.z500.rmse.day5"
TASK_ID = "weather.global_field_forecast"
SCENARIOS = ("lower", "higher", "tie", "dataset-mismatch", "unapproved", "stale-artifact")


def build_cases() -> list[dict[str, Any]]:
    base = json.loads((ROOT / "profiles" / "open-meteo-weathernext2.json").read_text(encoding="utf-8"))
    rng = random.Random(20261104)
    cases = []
    for index in range(36):
        scenario = SCENARIOS[index % len(SCENARIOS)]
        winner = "candidate-a" if (index // 6) % 2 == 0 else "candidate-b"
        ids = ["candidate-a", "candidate-b"]
        values = {winner: 10.0 + (index // 6), ("candidate-b" if winner == "candidate-a" else "candidate-a"): 13.0 + (index // 6)}
        direction = "higher" if scenario == "higher" else "lower"
        if direction == "higher" and scenario == "higher":
            values = {winner: 0.9, ("candidate-b" if winner == "candidate-a" else "candidate-a"): 0.7}
        expected = winner if scenario in ("lower", "higher") else None
        profiles = []
        for candidate_id in ids:
            profile = deepcopy(base)
            profile["id"] = candidate_id
            profile["display_name"] = f"Synthetic ranking fixture {candidate_id}"
            profile["deployments"] = []
            profile["capabilities"] = [{
                "task_id": TASK_ID,
                "input_schema": {"type": "object", "required": ["variable", "region"], "properties": {"variable": {"type": "string"}, "region": {"type": "string"}}},
                "output_schema": {"type": "object", "required": ["forecast_field"], "properties": {"forecast_field": {"type": "array"}}},
                "applicability": {"geography": "global", "max_horizon_days": 14},
                "data_requirements": ["initial atmospheric state"],
            }]
            revision = "rev-1"
            profile["source"].update({"artifact_id": candidate_id, "revision": revision, "artifact_digest": None})
            quality = rng.choice(["publisher_claim", "reproduced", "independent"])
            evaluation = {
                "task_id": TASK_ID,
                "evidence_level": quality,
                "artifact": {"id": candidate_id, "revision": revision, "digest": None},
                "contract_digest": capability_contract_digest(profile, TASK_ID),
                "dataset": {"id": "weatherbench2", "revision": "fixture-v1", "split": "test-2020", "config_digest": "sha256:" + "c" * 64},
                "applicability": {"region": "global", "horizon_days": 5, "resolution": "240x121"},
                "metrics": [{"id": METRIC, "value": values[candidate_id], "unit": "m2/s2", "direction": direction, "sample_count": 100}],
                "source": {"url": "https://example.org/synthetic-ranking-fixture", "evaluator": "synthetic-fixture-author"},
            }
            profile["evaluations"] = [evaluation]
            # Ranking labels are written before policy predictions and are not inferred from them.
            profile["extensions"] = {
                "fixture_downloads": rng.randint(1, 10000),
                "fixture_description": " ".join(rng.sample(["global", "z500", "forecast", "day", "five", "weather", "model", "scientific"], k=4)),
                "fixture_evidence_level": quality,
            }
            if scenario == "tie":
                evaluation["metrics"][0]["value"] = 10.0
            elif scenario == "dataset-mismatch" and candidate_id == "candidate-b":
                evaluation["dataset"]["revision"] = "fixture-v2"
            elif scenario == "stale-artifact" and candidate_id == "candidate-b":
                evaluation["artifact"]["revision"] = "rev-old"
            profiles.append(profile)
        approved = {contract_evaluation_digest(p, p["evaluations"][0]) for p in profiles}
        if scenario == "unapproved":
            approved.remove(contract_evaluation_digest(profiles[0], profiles[0]["evaluations"][0]))
        cases.append({
            "case_id": f"rank-{index + 1:02d}",
            "split": "development" if index < 24 else "holdout",
            "scenario": scenario,
            "request": {"task_id": "weather.precipitation_forecast", "constraints": {"metric_id": METRIC}},
            "candidate_ids": ids,
            "expected_profile_id": expected,
            "profiles": profiles,
            "approved_digests": approved,
            "rationale": (f"hand-authored fixture declares {expected} best under the stated comparable metric" if expected else f"{scenario} makes metric evidence insufficient; abstain"),
        })
    return cases


def _text_pick(case: dict[str, Any]) -> str:
    query = set(re.findall(r"[a-z0-9]+", case["request"]["task_id"] + " global z500 forecast day five"))
    return max(case["profiles"], key=lambda p: (len(query & set(re.findall(r"[a-z0-9]+", p["extensions"]["fixture_description"]))), p["id"]))["id"]


def predictions(case: dict[str, Any]) -> dict[str, str | None]:
    popularity = max(case["profiles"], key=lambda p: (p["extensions"]["fixture_downloads"], p["id"]))["id"]
    text = _text_pick(case)
    levels = {"none": 0, "publisher_claim": 1, "reproduced": 2, "independent": 3}
    def effective_tier(profile):
        evaluation = profile["evaluations"][0]
        digest = contract_evaluation_digest(profile, evaluation)
        level = evaluation["evidence_level"]
        if contract_errors(profile, evaluation) or digest not in case["approved_digests"]:
            return min(levels.get(level, 0), levels["publisher_claim"])
        return levels.get(level, 0)
    tier = max(case["profiles"], key=lambda p: (effective_tier(p), p["id"]))["id"]
    comparison = compare_profiles(case["profiles"], METRIC, approved_digests=case["approved_digests"])
    numeric = comparison["ranked"][0]["profile_id"] if comparison["status"] == "ordered" else None
    return {"popularity": popularity, "text_relevance": text, "evidence_tier": tier, "numeric_evidence": numeric}


def metrics(cases: list[dict[str, Any]], name: str, results: dict[str, dict[str, str | None]]) -> dict[str, Any]:
    positive = [c for c in cases if c["expected_profile_id"] is not None]
    negative = [c for c in cases if c["expected_profile_id"] is None]
    correct_abstain = sum(results[c["case_id"]][name] is None for c in negative)
    predicted_abstain = sum(results[c["case_id"]][name] is None for c in cases)
    hit = sum(results[c["case_id"]][name] == c["expected_profile_id"] for c in positive)
    wrong = sum(
        (c["expected_profile_id"] is None and results[c["case_id"]][name] is not None)
        or (c["expected_profile_id"] is not None and results[c["case_id"]][name] != c["expected_profile_id"])
        for c in cases
    )
    return {
        "case_count": len(cases), "qualified_count": len(positive), "must_abstain_count": len(negative),
        "top1_hits": hit, "wrong_route_count": wrong,
        "correct_abstain_count": correct_abstain, "predicted_abstain_count": predicted_abstain,
        "qualified_selected_count": sum(results[c["case_id"]][name] is not None for c in positive),
        "top1_hit_rate": hit / len(positive) if positive else None,
        "wrong_route_rate": wrong / len(cases) if cases else None,
        "abstain_precision": correct_abstain / predicted_abstain if predicted_abstain else None,
        "abstain_recall": correct_abstain / len(negative) if negative else None,
        "coverage_on_qualified": sum(results[c["case_id"]][name] is not None for c in positive) / len(positive) if positive else None,
    }


def run() -> dict[str, Any]:
    cases = build_cases()
    names = ("popularity", "text_relevance", "evidence_tier", "numeric_evidence")
    result_map = {c["case_id"]: predictions(c) for c in cases}
    scored = []
    for case in cases:
        scored.append({
            **{k: v for k, v in case.items() if k not in ("profiles", "approved_digests")},
            "request": {"task_id": TASK_ID, "inputs": {"variable": "Z500", "region": "global"}, "constraints": {"lead_days": 5, "metric_id": METRIC}},
            "candidates": [{
                "profile_id": p["id"], "artifact": p["evaluations"][0]["artifact"],
                "dataset": p["evaluations"][0]["dataset"], "applicability": p["evaluations"][0]["applicability"],
                "metric": p["evaluations"][0]["metrics"][0], "evidence_level": p["evaluations"][0]["evidence_level"],
                "source": p["evaluations"][0]["source"],
                "approved": contract_evaluation_digest(p, p["evaluations"][0]) in case["approved_digests"],
                "fixture_downloads": p["extensions"]["fixture_downloads"],
                "fixture_description": p["extensions"]["fixture_description"],
            } for p in case["profiles"]],
            "predictions": result_map[case["case_id"]],
        })
    output = {
        "title": "Evidence routing ranking evaluation",
        "source_note": "All 36 ranking cases and their labels are artificial fixtures. Public WeatherBench 2 score listings are audited separately and are not treated as executable deployment evidence.",
        "metric_definitions": {
            "top1_hit_rate": "unique labelled best candidate selected / qualified cases; abstention is a miss",
            "wrong_route_rate": "qualified cases with abstention or wrong selection plus abstain-required cases with any selection / all cases",
            "abstain_precision": "correct abstentions / all predicted abstentions; N/A if no abstentions",
            "abstain_recall": "correct abstentions / all abstain-required cases; N/A if none",
            "coverage_on_qualified": "qualified cases with a selection / all qualified cases",
        },
        "comparability_note": "All strategies receive identical two-candidate pools treated as already eligible for ranking. The fixture does not exercise real capability/deployment eligibility or adapter execution; this measures ranking logic only.",
        "metrics": {name: {"all": metrics(cases, name, result_map), "development": metrics(cases[:24], name, result_map), "holdout": metrics(cases[24:], name, result_map)} for name in names},
        "scenario_counts": {scenario: sum(c["scenario"] == scenario for c in cases) for scenario in SCENARIOS},
        "cases": scored,
    }
    OUT_JSON.write_text(json.dumps(output, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    labels = {"popularity": "熱門度", "text_relevance": "文字相關性", "evidence_tier": "證據等級", "numeric_evidence": "同條件數值證據"}
    md = ["# Evidence Routing Ranking Evaluation", "", "36 cases: 24 development, 12 holdout. All ranking cases are synthetic fixtures.", "", output["comparability_note"], "", "| Strategy | Top-1 hit | Wrong route | Abstain precision | Abstain recall | Coverage |", "|---|---:|---:|---:|---:|---:|"]
    for name in names:
        m = output["metrics"][name]["all"]
        fmt = lambda x: "N/A" if x is None else f"{x:.1%}"
        precision = f"{fmt(m['abstain_precision'])} ({m['correct_abstain_count']}/{m['predicted_abstain_count']})" if m["predicted_abstain_count"] else "N/A (0 predicted)"
        recall = f"{fmt(m['abstain_recall'])} ({m['correct_abstain_count']}/{m['must_abstain_count']})"
        md.append(f"| {labels[name]} | {fmt(m['top1_hit_rate'])} ({m['top1_hits']}/{m['qualified_count']}) | {fmt(m['wrong_route_rate'])} ({m['wrong_route_count']}/{m['case_count']}) | {precision} | {recall} | {fmt(m['coverage_on_qualified'])} ({m['qualified_selected_count']}/{m['qualified_count']}) |")
    md.extend(["", "## Failure types", "", "| Scenario | Cases | Numeric strategy abstained |", "|---|---:|---:|"])
    for scenario, count in output["scenario_counts"].items():
        abstained = sum(c["scenario"] == scenario and c["predictions"]["numeric_evidence"] is None for c in scored)
        md.append(f"| `{scenario}` | {count} | {abstained} |")
    md.extend(["", "## Representative cases", "", "| Case | Label | Numeric result | Reason |", "|---|---|---|---|"])
    for case in (scored[0], scored[1], scored[2], scored[3], scored[4], scored[5]):
        label = case["expected_profile_id"] or "abstain"
        picked = case["predictions"]["numeric_evidence"] or "abstain"
        md.append(f"| `{case['case_id']}` ({case['scenario']}) | {label} | {picked} | {case['rationale']} |")
    md.extend(["", "## Interpretation", "", "These results establish only that the comparator follows the hand-authored fixture labels. They do not establish real model quality, WeatherBench performance generalization, or end-to-end deployment selection. The synthetic scores are never copied into real Profiles.", ""])
    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    return output


if __name__ == "__main__":
    result = run()
    print(json.dumps(result["metrics"], indent=2, ensure_ascii=False))
    print(f"Wrote {OUT_JSON} and {OUT_MD}")
