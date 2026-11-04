"""Run from the project root: python examples/offline_demo.py (no network)."""
from copy import deepcopy
from pathlib import Path
import json

from umr.evidence import capability_contract_digest, contract_evaluation_digest
from umr.models import TaskRequest
from umr.router import route
from umr.service import RouterService


def main():
    root = Path(__file__).resolve().parents[1]
    print("AI Skill Router | offline demo")
    print("All comparison candidates, scores and approvals below are synthetic fixtures.")
    result = RouterService(root / "profiles").handle({
        "task_id": "math.solve_equation", "inputs": {"equation": "x**2 - 4 = 0"}, "execute": True,
    })
    if result.get("execution", {}).get("status") != "completed":
        raise RuntimeError("Math execution failed")
    solutions = result["execution"]["result"]["solutions"]
    if {row.get("x") for row in solutions} != {"-2", "2"} or not all(row["verified"] for row in solutions):
        raise RuntimeError("Solution verification failed")
    print("1. Math route: SymPy -> solutions " + ", ".join(row["x"] for row in solutions) + " (substitution verified)")
    print("   Verification checks returned solutions, not completeness of the solution set.")

    base = json.loads((root / "profiles" / "sympy-equation.json").read_text(encoding="utf-8"))
    candidates = []
    for name, score in (("fixture-a", 2.0), ("fixture-b", 4.0)):
        profile = deepcopy(base)
        profile["id"] = name
        profile["source"].update({"artifact_id": name, "revision": "v1", "artifact_digest": None})
        profile["evaluations"] = [{
            "task_id": "math.solve_equation", "evidence_level": "reproduced",
            "artifact": {"id": name, "revision": "v1", "digest": None},
            "contract_digest": capability_contract_digest(profile, "math.solve_equation"),
            "dataset": {"id": "synthetic-demo", "revision": "v1", "split": "test", "config_digest": "sha256:" + "b" * 64},
            "applicability": {"region": "global", "horizon_days": None, "resolution": None},
            "metrics": [{"id": "fixture-error", "value": score, "unit": "points", "direction": "lower"}],
            "source": {"url": "https://example.org/synthetic-demo", "evaluator": "synthetic fixture"},
        }]
        candidates.append(profile)
    approved = {contract_evaluation_digest(p, p["evaluations"][0]) for p in candidates}
    request = TaskRequest.from_dict({"task_id": "math.solve_equation", "inputs": {"equation": "x=1"}, "constraints": {"require_quality_comparison": True, "comparison_metric_id": "fixture-error"}})
    decision = route(candidates, request, available_adapters={"sympy-equation"}, approved_evaluation_digests=approved)
    if decision["status"] != "selected" or decision["selected"]["profile_id"] != "fixture-a":
        raise RuntimeError("Fixture comparison failed")
    print("2. Synthetic comparison (scores and approvals are fixtures):")
    print("   Candidate | revision | executable | dataset/split | metric | approved | decision")
    eligible = {item["profile_id"] for item in decision["candidates"]}
    for profile in candidates:
        evaluation = profile["evaluations"][0]
        metric = evaluation["metrics"][0]
        digest = contract_evaluation_digest(profile, evaluation)
        chosen = profile["id"] == decision["selected"]["profile_id"]
        print(f"   {profile['id']} | {profile['source']['revision']} | {profile['id'] in eligible} | "
              f"{evaluation['dataset']['id']}/{evaluation['dataset']['split']} | "
              f"{metric['value']} {metric['unit']} ({metric['direction']} better) | "
              f"{digest in approved} | {'selected' if chosen else 'eligible'}")
    print("   Same synthetic task, dataset and metric; approvals supplied locally.")
    selected = next(p for p in candidates if p['id'] == decision['selected']['profile_id'])
    print("   Source: " + selected['evaluations'][0]['source']['url'] + "; evidence digest: " + decision["comparison"]["ranked"][0]["evidence_digest"][:16] + "...")
    candidates[0]["source"]["revision"] = "v2"
    decision = route(candidates, request, available_adapters={"sympy-equation"}, approved_evaluation_digests=approved)
    if decision["status"] != "abstain":
        raise RuntimeError("Stale evidence did not cause abstention")
    print(f"3. Revision changed v1 -> v2: {decision['status'].upper()} (approved evidence no longer matches)")
    print("   Reason: " + decision["comparison"]["reasons"][0]["reason"])
    print("Demo complete. Synthetic scores are not real benchmark evidence.")


if __name__ == "__main__":
    main()
