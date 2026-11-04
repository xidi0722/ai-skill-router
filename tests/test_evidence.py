from copy import deepcopy
import json

from umr.evidence import ApprovalLedger, capability_contract_digest, compare_profiles, contract_evaluation_digest
from umr.models import TaskRequest
from umr.profile import validate_profile
from umr.router import evaluation_digest, route


def evidence_profile(base, profile_id, value, *, direction="lower", dataset_revision="v1", revision="r1", interval=None):
    profile = deepcopy(base)
    profile["id"] = profile_id
    profile["source"].update({"artifact_id": profile_id, "revision": revision, "artifact_digest": None})
    metric = {"id": "rmse.z500.day5", "value": value, "unit": "m2/s2", "direction": direction, "sample_count": 1200}
    if interval is not None:
        metric["confidence_interval"] = interval
    profile["evaluations"] = [{
        "task_id": "math.solve_equation",
        "evidence_level": "independent",
        "artifact": {"id": profile_id, "revision": revision, "digest": None},
        "contract_digest": capability_contract_digest(profile, "math.solve_equation"),
        "dataset": {"id": "fixture-bench", "revision": dataset_revision, "split": "test", "config_digest": "sha256:" + "b" * 64},
        "applicability": {"region": "global", "horizon_days": 5, "resolution": "240x121"},
        "metrics": [metric],
        "source": {"url": "https://example.org/report", "evaluator": "independent fixture reviewer"},
    }]
    return profile


def approvals(profiles):
    return {contract_evaluation_digest(p, p["evaluations"][0]) for p in profiles}


def test_contract_evidence_binds_artifact_revision_and_schema_validates(profiles):
    profile = evidence_profile(profiles[0], "candidate-a", 10)
    validate_profile(profile)
    digest = contract_evaluation_digest(profile, profile["evaluations"][0])
    profile["source"]["revision"] = "r2"
    assert contract_evaluation_digest(profile, profile["evaluations"][0]) != digest
    assert compare_profiles([profile], "rmse.z500.day5", approved_digests={digest})["status"] == "incomparable"

    profile = evidence_profile(profiles[0], "candidate-a", 10)
    metric_digest = contract_evaluation_digest(profile, profile["evaluations"][0])
    profile["evaluations"][0]["metrics"][0]["value"] = 9
    assert contract_evaluation_digest(profile, profile["evaluations"][0]) != metric_digest
    assert compare_profiles([profile], "rmse.z500.day5", approved_digests={metric_digest})["status"] == "incomparable"


def test_legacy_approval_cannot_bypass_new_contract_validation(profiles):
    profile = evidence_profile(profiles[0], "candidate-a", 10)
    profile["source"]["revision"] = "rev-changed"
    request = TaskRequest.from_dict({
        "task_id": "math.solve_equation", "inputs": {"equation": "x=1"},
        "constraints": {"require_independent_evidence": True},
    })
    old_style_digest = evaluation_digest(profile["id"], profile["evaluations"][0])
    result = route([profile], request, available_adapters={"sympy-equation"}, trusted_evaluation_digests={old_style_digest})
    assert result["status"] == "abstain"


def test_strict_evidence_must_match_region_and_horizon_scope(profiles):
    profile = evidence_profile(profiles[0], "candidate-a", 10)
    profile["evaluations"][0]["applicability"].update({"region": "US", "horizon_days": 3})
    request = TaskRequest.from_dict({
        "task_id": "math.solve_equation", "inputs": {"equation": "x=1"},
        "constraints": {"require_independent_evidence": True, "region": "TW", "horizon_days": 5},
    })
    digest = contract_evaluation_digest(profile, profile["evaluations"][0])
    result = route([profile], request, available_adapters={"sympy-equation"}, approved_evaluation_digests={digest})
    assert result["status"] == "abstain"
    assert "below required independent" in " ".join(result["rejected"][0]["reasons"])


def test_numeric_comparison_uses_direction_and_is_deterministic(profiles):
    a = evidence_profile(profiles[0], "a", 10)
    b = evidence_profile(profiles[0], "b", 12)
    result = compare_profiles([a, b], "rmse.z500.day5", approved_digests=approvals([a, b]))
    assert result["status"] == "ordered"
    assert result["best_profile_ids"] == ["a"]
    a_higher = evidence_profile(profiles[0], "a", 0.8, direction="higher")
    b_higher = evidence_profile(profiles[0], "b", 0.7, direction="higher")
    assert compare_profiles([a_higher, b_higher], "rmse.z500.day5", approved_digests=approvals([a_higher, b_higher]))["best_profile_ids"] == ["a"]


def test_incompatible_dataset_or_direction_abstains(profiles):
    a = evidence_profile(profiles[0], "a", 10)
    b = evidence_profile(profiles[0], "b", 12, dataset_revision="v2")
    assert compare_profiles([a, b], "rmse.z500.day5", approved_digests=approvals([a, b]))["status"] == "incomparable"
    b = evidence_profile(profiles[0], "b", 12, direction="higher")
    assert compare_profiles([a, b], "rmse.z500.day5", approved_digests=approvals([a, b]))["status"] == "incomparable"


def test_unapproved_revoked_missing_unknown_and_close_scores_are_inconclusive(profiles):
    a = evidence_profile(profiles[0], "a", 10, interval=[9, 11])
    b = evidence_profile(profiles[0], "b", 10.5, interval=[10, 12])
    a_digest = contract_evaluation_digest(a, a["evaluations"][0])
    b_digest = contract_evaluation_digest(b, b["evaluations"][0])
    result = compare_profiles([a, b], "rmse.z500.day5", approved_digests={a_digest, b_digest})
    assert result["status"] == "inconclusive"
    assert compare_profiles([a, b], "rmse.z500.day5", approved_digests={a_digest}, revoked_digests={b_digest})["status"] == "incomparable"
    assert compare_profiles([a, b], "rmse.z500.day5", approved_digests={a_digest})["status"] == "incomparable"
    b["evaluations"][0]["metrics"][0]["value"] = None
    assert compare_profiles([a, b], "rmse.z500.day5", approved_digests={a_digest, contract_evaluation_digest(b, b["evaluations"][0])})["status"] == "incomparable"


def test_strict_quality_request_abstains_without_comparable_evidence(profiles):
    profiles = [deepcopy(profiles[0]), deepcopy(profiles[0])]
    profiles[1]["id"] = "other"
    request = TaskRequest.from_dict({
        "task_id": "math.solve_equation", "inputs": {"equation": "x=1"},
        "constraints": {"require_quality_comparison": True, "comparison_metric_id": "rmse.z500.day5"},
    })
    result = route(profiles, request, available_adapters={"sympy-equation"})
    assert result["status"] == "abstain"
    assert result["comparison"]["status"] == "incomparable"


def test_router_selects_numerically_best_approved_candidate_and_respects_revocation(profiles):
    a = evidence_profile(profiles[0], "a", 10)
    b = evidence_profile(profiles[0], "b", 12)
    request = TaskRequest.from_dict({
        "task_id": "math.solve_equation", "inputs": {"equation": "x=1"},
        "constraints": {"require_quality_comparison": True, "comparison_metric_id": "rmse.z500.day5"},
    })
    approved = approvals([a, b])
    result = route([a, b], request, available_adapters={"sympy-equation"}, approved_evaluation_digests=approved)
    assert result["status"] == "selected"
    assert result["selected"]["profile_id"] == "a"
    revoked = route([a, b], request, available_adapters={"sympy-equation"}, approved_evaluation_digests=approved, revoked_evaluation_digests={next(iter(approved))})
    assert revoked["status"] == "abstain"


def test_approval_ledger_keeps_approval_outside_profile_and_revocation_wins(tmp_path):
    path = tmp_path / "approvals.json"
    path.write_text(json.dumps({
        "approvals": {"digest-a": {"approved_by": "local-admin", "approved_at": "2026-11-04T12:00:00Z"}},
        "revoked": ["digest-a"],
    }), encoding="utf-8")
    ledger = ApprovalLedger.load(path)
    assert not ledger.is_approved("digest-a")
    assert not ledger.is_approved("digest-b")
