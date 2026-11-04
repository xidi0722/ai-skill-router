"""Reproducible router policy evaluation over explicitly synthetic fixtures."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from umr.models import TaskRequest  # noqa: E402
from umr.router import evaluation_digest, route  # noqa: E402


TRUSTED_REVIEWERS = {"fixture-reviewer:math", "fixture-reviewer:weather"}
POSITIVE_QUERIES = {
    "math.solve_equation": "solve polynomial equation algebra symbolic math",
    "weather.precipitation_forecast": "Taiwan weather rain precipitation forecast tomorrow",
}
MATH_EQUATIONS = [
    "x**2-4=0", "x+3=7", "2*x=10", "x**2=9", "x-8=0",
    "3*x+2=11", "x**2-1=0", "4*x=20", "x+12=15", "x**2-16=0",
]


def _load_profile(name: str) -> dict[str, Any]:
    with (ROOT / "profiles" / name).open(encoding="utf-8") as stream:
        return json.load(stream)


def _candidate_pool(task_id: str, horizon: int = 1) -> list[dict[str, Any]]:
    is_math = task_id == "math.solve_equation"
    base = _load_profile("sympy-equation.json" if is_math else "open-meteo-weathernext2.json")
    prefix = "math" if is_math else "weather"
    evaluator = "fixture-reviewer:math" if is_math else "fixture-reviewer:weather"
    high_popularity_description = (
        "Solve polynomial equation algebra symbolically with a math model"
        if is_math else
        "Taiwan weather rain precipitation forecast tomorrow with a weather model"
    )
    profiles = []
    for suffix, downloads, level, verifier, executable in (
        ("primary", 100, "publisher_claim", None, True),
        ("audited", 20, "independent", evaluator, True),
        ("metadata", 1_000_000, "none", None, False),
        ("regional", 50, "publisher_claim", None, True),
    ):
        profile = copy.deepcopy(base)
        profile["id"] = f"{prefix}.{suffix}"
        profile["display_name"] = (
            high_popularity_description if suffix == "metadata" else f"{prefix} {suffix} fixture"
        )
        profile["description"] = high_popularity_description if suffix == "metadata" else "Curated candidate fixture."
        profile["extensions"] = {"downloads": downloads}
        profile["runtime_status"] = {"status": "unknown", "last_probe": None}
        profile["evaluations"] = [] if suffix == "metadata" else [{
            "task_id": task_id,
            "evidence_level": level,
            "verified_by": verifier,
            "region": "global",
            "horizon_days": horizon,
        }]
        if not executable:
            profile["deployments"] = []
        if suffix == "regional":
            profile["capabilities"][0]["applicability"] = {
                "geography": "regional",
                "regions": ["TW"],
                "max_horizon_days": 14,
            }
        profiles.append(profile)
    return profiles


def build_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    task_ids = list(POSITIVE_QUERIES)
    for index in range(25):
        task_id = task_ids[index % 2]
        horizon = index % 14 + 1
        inputs = (
            {"equation": MATH_EQUATIONS[index % len(MATH_EQUATIONS)]}
            if task_id == "math.solve_equation" else
            {"latitude": 24.1477, "longitude": 120.6736, "target_date": "2026-11-05", "timezone": "Asia/Taipei"}
        )
        constraints: dict[str, Any] = {"region": "TW"}
        if task_id == "weather.precipitation_forecast":
            constraints["horizon_days"] = horizon
        cases.append({
            "case_id": f"positive-{index + 1:02d}",
            "split": "development" if index < 20 else "holdout",
            "query_text": POSITIVE_QUERIES[task_id],
            "request": {"task_id": task_id, "inputs": inputs, "constraints": constraints},
            "candidate_ids": [f"{'math' if task_id.startswith('math') else 'weather'}.{suffix}" for suffix in ("primary", "audited", "metadata", "regional")],
            "acceptable_profile_ids": [f"{'math' if task_id.startswith('math') else 'weather'}.{suffix}" for suffix in ("primary", "audited", "regional")],
            "must_abstain": False,
            "rationale": "具備本地 allowlisted adapter、輸入契約和適用條件的合成候選可執行；熱門 metadata-only 候選不合格。",
            "fixture_origin": "人工合成 Profile，任務與 adapter 契約取自本 repo profiles；不是模型效能資料。",
            "scenario": "eligible",
        })

    negative_scenarios = [
        ("unsupported-task", "science.unregistered", {}, {}, "任務目錄沒有候選 Capability，必須 abstain。"),
        ("missing-input", "math.solve_equation", {}, {}, "方程輸入缺失，不能路由到求解器。"),
        ("horizon-out-of-range", "weather.precipitation_forecast", {"latitude": 24, "longitude": 121, "target_date": "2026-11-05"}, {"region": "TW", "horizon_days": 20}, "請求時距超出所有天氣候選的宣告範圍。"),
        ("independent-evidence-missing", "weather.precipitation_forecast", {"latitude": 24, "longitude": 121, "target_date": "2026-11-05"}, {"region": "TW", "horizon_days": 2, "require_independent_evidence": True}, "獨立證據的 verified_by 不在信任清單，strict policy 必須 abstain。"),
        ("data-license-unknown", "weather.precipitation_forecast", {"latitude": 24, "longitude": 121, "target_date": "2026-11-05"}, {"region": "TW", "required_license_fields": ["data"]}, "天氣 Profile 未知資料授權，政策要求 data license，必須 abstain。"),
    ]
    for scenario_index, (scenario, task_id, inputs, extra_constraints, rationale) in enumerate(negative_scenarios):
        for variant in range(4):
            candidate_prefix = "math" if task_id.startswith("math") or task_id == "science.unregistered" else "weather"
            constraints = dict(extra_constraints)
            if task_id == "weather.precipitation_forecast":
                constraints.setdefault("horizon_days", 2)
            if scenario == "independent-evidence-missing":
                constraints["horizon_days"] = 2
            cases.append({
                "case_id": f"negative-{scenario_index + 1}-{variant + 1}",
                "split": "development",
                "query_text": POSITIVE_QUERIES.get(task_id, "find a science tool for an unsupported task"),
                "request": {"task_id": task_id, "inputs": inputs, "constraints": constraints},
                "candidate_ids": [f"{candidate_prefix}.{suffix}" for suffix in ("primary", "audited", "metadata", "regional")],
                "acceptable_profile_ids": [],
                "must_abstain": True,
                "rationale": rationale,
                "fixture_origin": "人工合成 Profile 與政策反例；不代表線上服務或真實模型品質。",
                "scenario": scenario,
            })
    holdout_scenarios = [
        ("region-mismatch", "weather.precipitation_forecast", {"latitude": 24, "longitude": 121, "target_date": "2026-11-05"}, {"region": "US", "horizon_days": 2}, "地域限制不涵蓋請求地區。"),
        ("runtime-offline", "math.solve_equation", {"equation": "x=2"}, {}, "所有可執行候選都標記離線。"),
        ("cost-over-budget", "weather.precipitation_forecast", {"latitude": 24, "longitude": 121, "target_date": "2026-11-05"}, {"region": "TW", "max_cost_usd": 1}, "全部部署成本都超出預算。"),
        ("unregistered-adapter", "math.solve_equation", {"equation": "x=2"}, {}, "Profile 的 adapter 未在本機註冊清單。"),
        ("invalid-input-schema", "math.solve_equation", {"equation": 4}, {}, "輸入值不符合 Capability JSON Schema。"),
    ]
    for index, (scenario, task_id, inputs, constraints, rationale) in enumerate(holdout_scenarios):
        if task_id.startswith("weather"):
            constraints = {**constraints, "horizon_days": 2}
        cases.append({
            "case_id": f"holdout-negative-{index + 1}",
            "split": "holdout",
            "query_text": POSITIVE_QUERIES[task_id],
            "request": {"task_id": task_id, "inputs": inputs, "constraints": constraints},
            "candidate_ids": [f"{'math' if task_id.startswith('math') else 'weather'}.{suffix}" for suffix in ("primary", "audited", "metadata", "regional")],
            "acceptable_profile_ids": [],
            "must_abstain": True,
            "rationale": rationale,
            "fixture_origin": "人工合成 Profile 與未用於 development 負例模板的保留政策條件。",
            "scenario": scenario,
        })
    return cases


def _popularity(profiles: list[dict[str, Any]]) -> str:
    return max(profiles, key=lambda profile: (profile.get("extensions", {}).get("downloads", 0), profile["id"]))["id"]


def _text_relevance(query: str, profiles: list[dict[str, Any]]) -> str:
    tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
    def score(profile):
        text = " ".join([
            profile.get("display_name", ""),
            profile.get("description", ""),
            " ".join(capability.get("task_id", "") for capability in profile.get("capabilities", [])),
        ]).lower()
        resource_tokens = set(re.findall(r"[a-z0-9]+", text))
        return (len(tokens & resource_tokens), profile["id"])
    return max(profiles, key=score)["id"]


def _metrics(cases, predictions):
    eligible = [case for case in cases if not case["must_abstain"]]
    must_abstain = [case for case in cases if case["must_abstain"]]
    selected = [case for case in cases if predictions[case["case_id"]] is not None]
    hits = sum(predictions[case["case_id"]] in case["acceptable_profile_ids"] for case in eligible)
    wrong = sum(
        predictions[case["case_id"]] is not None
        and (case["must_abstain"] or predictions[case["case_id"]] not in case["acceptable_profile_ids"])
        for case in cases
    )
    correct_abstain = sum(predictions[case["case_id"]] is None for case in must_abstain)
    predicted_abstain = [case for case in cases if predictions[case["case_id"]] is None]
    return {
        "case_count": len(cases),
        "qualified_count": len(eligible),
        "must_abstain_count": len(must_abstain),
        "top1_hit_rate_on_qualified": hits / len(eligible) if eligible else None,
        "wrong_route_rate_all_cases": wrong / len(cases) if cases else None,
        "abstain_precision": correct_abstain / len(predicted_abstain) if predicted_abstain else None,
        "abstain_recall": correct_abstain / len(must_abstain) if must_abstain else None,
        "coverage_on_qualified": sum(predictions[case["case_id"]] is not None for case in eligible) / len(eligible) if eligible else None,
        "abstained_count": len(predicted_abstain),
    }


def run() -> dict[str, Any]:
    cases = build_cases()
    outputs: dict[str, dict[str, str | None]] = {
        "popularity_ungated": {},
        "text_relevance_ungated": {},
        "popularity_shared_eligibility": {},
        "text_relevance_shared_eligibility": {},
        "evidence_router": {},
    }
    annotated_cases = []
    for case in cases:
        task_id = case["request"]["task_id"]
        candidate_task = task_id if task_id in POSITIVE_QUERIES else "math.solve_equation"
        horizon = case["request"]["constraints"].get("horizon_days", 1)
        profiles = _candidate_pool(candidate_task, horizon)
        if case["scenario"] == "independent-evidence-missing":
            for profile in profiles:
                for evaluation in profile.get("evaluations", []):
                    evaluation["verified_by"] = "untrusted-profile-author"
        if case["scenario"] == "region-mismatch":
            for profile in profiles:
                profile["capabilities"][0]["applicability"] = {
                    "geography": "regional", "regions": ["TW"], "max_horizon_days": 14
                }
        elif case["scenario"] == "runtime-offline":
            for profile in profiles:
                profile["runtime_status"]["status"] = "offline"
        elif case["scenario"] == "cost-over-budget":
            for profile in profiles:
                for deployment in profile["deployments"]:
                    deployment["cost"] = {
                        "amount": 10, "currency": "USD", "unit": "request", "status": "fixture"
                    }
        elif case["scenario"] == "unregistered-adapter":
            for profile in profiles:
                for deployment in profile["deployments"]:
                    deployment["adapter"] = "unregistered-fixture-adapter"
        ids = set(case["candidate_ids"])
        profiles = [profile for profile in profiles if profile["id"] in ids]
        request = TaskRequest.from_dict(case["request"])
        trusted_digests = {
            evaluation_digest(profile["id"], evaluation)
            for profile in profiles
            for evaluation in profile.get("evaluations", [])
            if evaluation.get("verified_by") in TRUSTED_REVIEWERS
        }
        decision = route(
            profiles, request, available_adapters={"sympy-equation", "open-meteo-weathernext2"},
            trusted_evaluation_digests=trusted_digests,
        )
        outputs["evidence_router"][case["case_id"]] = (
            decision["selected"]["profile_id"] if decision["selected"] else None
        )
        eligible_ids = {candidate["profile_id"] for candidate in decision["candidates"]}
        eligible_profiles = [profile for profile in profiles if profile["id"] in eligible_ids]
        outputs["popularity_ungated"][case["case_id"]] = _popularity(profiles) if profiles else None
        outputs["text_relevance_ungated"][case["case_id"]] = _text_relevance(case["query_text"], profiles) if profiles else None
        outputs["popularity_shared_eligibility"][case["case_id"]] = _popularity(eligible_profiles) if eligible_profiles else None
        outputs["text_relevance_shared_eligibility"][case["case_id"]] = _text_relevance(case["query_text"], eligible_profiles) if eligible_profiles else None
        annotated_cases.append({
            **case,
            "candidates": [{
                "profile_id": profile["id"],
                "kind": profile["kind"],
                "execution_available": bool(profile["deployments"]),
                "downloads_fixture": profile["extensions"]["downloads"],
                "description": profile["description"],
            } for profile in profiles],
            "predictions": {name: prediction[case["case_id"]] for name, prediction in outputs.items()},
        })

    summary = {}
    for strategy, predictions in outputs.items():
        summary[strategy] = {
            "all": _metrics(cases, predictions),
            "development": _metrics([c for c in cases if c["split"] == "development"], predictions),
            "holdout": _metrics([c for c in cases if c["split"] == "holdout"], predictions),
        }
    failures = {
        strategy: [case for case in annotated_cases if (
            (case["must_abstain"] and case["predictions"][strategy] is not None)
            or (not case["must_abstain"] and case["predictions"][strategy] not in case["acceptable_profile_ids"])
        )][:3]
        for strategy in outputs
    }
    failure_type_summary = {}
    for scenario in sorted({case["scenario"] for case in cases if case["must_abstain"]}):
        group = [case for case in cases if case["scenario"] == scenario]
        failure_type_summary[scenario] = {
            "case_count": len(group),
            "router_abstained_count": sum(outputs["evidence_router"][case["case_id"]] is None for case in group),
            "popularity_ungated_wrong_count": sum(outputs["popularity_ungated"][case["case_id"]] is not None for case in group),
            "text_relevance_ungated_wrong_count": sum(outputs["text_relevance_ungated"][case["case_id"]] is not None for case in group),
        }
    return {
        "title": "Universal Model Router offline policy evaluation",
        "dataset": {
            "case_count": len(cases),
            "development_count": sum(c["split"] == "development" for c in cases),
            "holdout_count": sum(c["split"] == "holdout" for c in cases),
            "source_note": "All candidates and evaluation labels are synthetic policy fixtures derived from checked-in profiles. They are not real model performance evidence.",
            "labeling_rules": {
                "qualified": "A case is qualified only when it has at least one candidate pre-labelled acceptable; any selected candidate in that set is a hit, and abstention is a miss.",
                "must_abstain": "A case must abstain when its task/policy fixture has no admissible candidate. Any selected candidate is a wrong route.",
                "multiple_acceptable_candidates": "Positive cases intentionally accept multiple synthetic candidates; labels do not encode a real quality ordering among them.",
                "splits": "Forty hand-authored development cases cover the policy matrix. Ten holdout cases use altered input variants and reserved negative-case variants; both splits remain small synthetic fixtures.",
            },
            "metric_definitions": {
                "top1_hit_rate_on_qualified": "Qualified cases selecting any profile in acceptable_profile_ids divided by all qualified cases; abstention is a miss.",
                "wrong_route_rate_all_cases": "Qualified cases that abstain or select outside acceptable_profile_ids plus must_abstain cases that select any profile, divided by all cases.",
                "abstain_precision": "Correct abstentions on must_abstain cases divided by all predicted abstentions; N/A when no strategy output abstains.",
                "abstain_recall": "Correct abstentions on must_abstain cases divided by all must_abstain cases; N/A when there are no must-abstain cases.",
                "coverage_on_qualified": "Qualified cases with any selected profile divided by all qualified cases.",
            },
            "methods": {
                "popularity_ungated": "Select highest fixture downloads; ignores eligibility and execution status.",
                "text_relevance_ungated": "Select maximum token overlap between query and candidate metadata; ignores eligibility and execution status.",
                "popularity_shared_eligibility": "Same hard eligibility decision as the router, then select highest downloads from eligible candidates.",
                "text_relevance_shared_eligibility": "Same hard eligibility decision as the router, then select maximum token overlap from eligible candidates.",
                "evidence_router": "Current router with registered adapters and out-of-band approved fixture evaluation digests.",
                "comparison_note": "The ungated rows measure eligibility-gate value. The shared-eligibility rows isolate ranking. These synthetic cases cannot establish live model quality.",
            },
        },
        "metrics": summary,
        "failure_type_summary": failure_type_summary,
        "representative_failures": failures,
        "cases": annotated_cases,
    }


def render_markdown(result: dict[str, Any]) -> str:
    strategies = [
        ("Popularity (ungated)", "popularity_ungated"),
        ("Text relevance (ungated)", "text_relevance_ungated"),
        ("Popularity + shared eligibility", "popularity_shared_eligibility"),
        ("Text relevance + shared eligibility", "text_relevance_shared_eligibility"),
        ("Evidence router", "evidence_router"),
    ]
    lines = [
        "# Offline Router Evaluation",
        "",
        f"Cases: {result['dataset']['case_count']} total; {result['dataset']['development_count']} development; {result['dataset']['holdout_count']} holdout.",
        "",
        "All profiles, evidence and labels are synthetic fixtures. This checks policy behavior only; it does not measure real model quality or predict performance on user queries. The holdout uses different input variants and reserved failure types, but remains a small, hand-authored fixture set.",
        "",
        "## Fixed labels and metric definitions",
        "",
        "Labels are assigned before running strategies. A qualified case has a non-empty acceptable candidate set; any candidate in that set is accepted and abstention is a miss. A must-abstain case has no admissible candidate; selecting any candidate is a wrong route. Positive cases accept multiple synthetic candidates, so they do not define a real ranking among eligible models.",
        "",
        "- **Top-1 hit rate (qualified):** qualified cases selecting an acceptable candidate / all qualified cases; abstentions count as misses.",
        "- **Wrong-route rate (all):** qualified cases that abstain or select an unacceptable candidate, plus must-abstain cases that select anything / all cases.",
        "- **Abstain precision:** correct abstentions on must-abstain cases / all predicted abstentions; N/A if there are no predicted abstentions.",
        "- **Abstain recall:** correct abstentions on must-abstain cases / all must-abstain cases; N/A if that denominator is empty.",
        "- **Coverage (qualified):** qualified cases with any selected candidate / all qualified cases.",
        "",
        "Ungated baselines show the effect of omitting capability/execution checks. Shared-eligibility rows use the same eligible candidate IDs returned by the router and therefore isolate ranking. All strategies receive the same underlying candidate pool for each case.",
        "",
        "| Strategy | Top-1 hit (eligible) | Wrong route (all) | Abstain precision | Abstain recall | Coverage (eligible) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    def percent(value):
        return "N/A" if value is None else f"{value * 100:.1f}%"
    for label, key in strategies:
        metrics = result["metrics"][key]["all"]
        lines.append(
            f"| {label} | {percent(metrics['top1_hit_rate_on_qualified'])} ({metrics['qualified_count']}) | "
            f"{percent(metrics['wrong_route_rate_all_cases'])} ({metrics['case_count']}) | "
            f"{percent(metrics['abstain_precision'])} | {percent(metrics['abstain_recall'])} | "
            f"{percent(metrics['coverage_on_qualified'])} |"
        )
    lines.extend(["", "## Holdout subset", "", "| Strategy | Top-1 hit (eligible) | Wrong route (all) | Abstain precision | Abstain recall | Coverage (eligible) |", "|---|---:|---:|---:|---:|---:|"])
    for label, key in strategies:
        metrics = result["metrics"][key]["holdout"]
        lines.append(
            f"| {label} | {percent(metrics['top1_hit_rate_on_qualified'])} ({metrics['qualified_count']}) | "
            f"{percent(metrics['wrong_route_rate_all_cases'])} ({metrics['case_count']}) | "
            f"{percent(metrics['abstain_precision'])} | {percent(metrics['abstain_recall'])} | "
            f"{percent(metrics['coverage_on_qualified'])} |"
        )
    lines.extend(["", "## Abstention cases by failure type", "", "| Failure type | Cases | Router abstained | Popularity raw wrong routes | Text raw wrong routes |", "|---|---:|---:|---:|---:|"])
    for scenario, metrics in result["failure_type_summary"].items():
        lines.append(
            f"| `{scenario}` | {metrics['case_count']} | {metrics['router_abstained_count']} | "
            f"{metrics['popularity_ungated_wrong_count']} | {metrics['text_relevance_ungated_wrong_count']} |"
        )
    lines.extend(["", "## Interpretation", "", "The gated baselines and router operate on a closed-world fixture where each eligible candidate has been pre-labelled as acceptable except in reserved policy cases. A perfect score means the implementation followed these labels; it does not establish that evidence-tier ranking selects more accurate real models. Because all eligible positive candidates are accepted, shared-eligibility ranking metrics cannot distinguish their relative quality. The raw popularity and text baselines are intentionally ungated and demonstrate why metadata relevance or downloads alone can select a non-executable candidate.", "", "## Representative baseline failures", ""])
    for strategy in ("popularity_ungated", "text_relevance_ungated"):
        failures = result["representative_failures"][strategy]
        if failures:
            case = failures[0]
            lines.append(
                f"- `{strategy}` on `{case['case_id']}` selected `{case['predictions'][strategy]}`; "
                f"expected {'abstain' if case['must_abstain'] else ', '.join(case['acceptable_profile_ids'])}. {case['rationale']}"
            )
    lines.extend(["", "Re-run with `python tools/run_offline_evaluation.py`; complete case records and predictions are in `offline-evaluation.json`.", ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "outputs" / "offline-evaluation.json")
    args = parser.parse_args()
    result = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path = args.output.with_suffix(".md")
    markdown_path.write_text(render_markdown(result), encoding="utf-8")
    print(json.dumps(result["metrics"], ensure_ascii=False, indent=2))
    print(f"Detailed cases and results: {args.output}")
    print(f"Readable summary: {markdown_path}")


if __name__ == "__main__":
    main()
