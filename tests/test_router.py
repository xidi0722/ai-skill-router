from copy import deepcopy
from datetime import datetime, timezone

from umr.models import RoutePolicy, TaskRequest
from umr.router import _runtime_health, evaluation_digest, route


MATH_REQUEST = TaskRequest.from_dict({
    "task_id": "math.solve_equation",
    "inputs": {"equation": "x**2 - 4 = 0"},
    "constraints": {},
})


def test_profile_with_alternative_capabilities_survives_one_inapplicable(profiles):
    profile = deepcopy(profiles[0])
    profile["capabilities"].insert(0, {
        "task_id": "math.solve_equation",
        "input_schema": {"type": "object", "required": ["equation", "domain"]},
        "output_schema": {"type": "object"},
    })
    decision = route([profile], MATH_REQUEST, available_adapters={"sympy-equation"})
    assert decision["status"] == "selected"
    assert decision["selected"]["capability"]["input_schema"]["required"] == ["equation"]


def test_cost_budget_filters_deployments_individually(profiles):
    profile = deepcopy(profiles[0])
    profile["deployments"][0]["cost"] = {
        "amount": 5, "currency": "USD", "unit": "request", "status": "listed"
    }
    profile["deployments"].append({
        "id": "math-cheaper",
        "kind": "local",
        "adapter": "sympy-equation",
        "status": "ready",
        "cost": {"amount": 0.01, "currency": "USD", "unit": "request", "status": "listed"},
    })
    request = TaskRequest.from_dict({
        "task_id": "math.solve_equation",
        "inputs": {"equation": "x=1"},
        "constraints": {"max_cost_usd": 0.1},
    })
    decision = route([profile], request, available_adapters={"sympy-equation"})
    assert decision["status"] == "selected"
    assert decision["selected"]["deployment_id"] == "math-cheaper"


def test_untrusted_independent_label_does_not_satisfy_strict_policy(profiles):
    profile = deepcopy(profiles[0])
    profile["quality_evidence_level"] = "independent"
    profile["evaluations"] = [{
        "task_id": "math.solve_equation",
        "evidence_level": "independent",
        "verified_by": "untrusted-author-claim",
    }]
    decision = route(
        [profile], MATH_REQUEST,
        RoutePolicy.from_constraints({"require_independent_evidence": True}),
        {"sympy-equation"},
    )
    assert decision["status"] == "abstain"
    assert "publisher_claim" in " ".join(decision["rejected"][0]["reasons"])


def test_admin_approved_evaluation_digest_can_supply_task_evidence(profiles):
    profile = deepcopy(profiles[0])
    evaluation = {
        "task_id": "math.solve_equation",
        "evidence_level": "independent",
        "verified_by": "trusted-lab",
    }
    profile["evaluations"] = [evaluation]
    decision = route(
        [profile], MATH_REQUEST,
        RoutePolicy.from_constraints({"require_independent_evidence": True}),
        {"sympy-equation"},
        {evaluation_digest(profile["id"], evaluation)},
    )
    assert decision["status"] == "selected"
    assert decision["selected"]["evidence_level"] == "independent"


def test_evidence_must_match_task_region_and_horizon(profiles):
    profile = deepcopy(profiles[1])
    profile["evaluations"] = [{
        "task_id": "weather.precipitation_forecast",
        "evidence_level": "independent",
        "verified_by": "trusted-lab",
        "region": "TW",
        "horizon_days": 2,
    }]
    digest = evaluation_digest(profile["id"], profile["evaluations"][0])
    request = TaskRequest.from_dict({
        "task_id": "weather.precipitation_forecast",
        "inputs": {"latitude": 24, "longitude": 121, "target_date": "2026-11-05"},
        "constraints": {
            "require_independent_evidence": True,
            "region": "US",
            "horizon_days": 2,
        },
    })
    decision = route([profile], request, available_adapters={"open-meteo-weathernext2"}, trusted_evaluation_digests={digest})
    assert decision["status"] == "abstain"
    request2 = TaskRequest.from_dict({
        "task_id": "weather.precipitation_forecast",
        "inputs": {"latitude": 24, "longitude": 121, "target_date": "2026-11-05"},
        "constraints": {"require_independent_evidence": True, "region": "TW", "horizon_days": 3},
    })
    assert route([profile], request2, available_adapters={"open-meteo-weathernext2"}, trusted_evaluation_digests={digest})["status"] == "abstain"


def test_editing_approved_evaluation_invalidates_its_digest(profiles):
    profile = deepcopy(profiles[0])
    evaluation = {"task_id": "math.solve_equation", "evidence_level": "independent"}
    profile["evaluations"] = [evaluation]
    digest = evaluation_digest(profile["id"], evaluation)
    profile["evaluations"][0]["value"] = 0.99
    decision = route(
        [profile], MATH_REQUEST,
        RoutePolicy.from_constraints({"require_independent_evidence": True}),
        {"sympy-equation"},
        {digest},
    )
    assert decision["status"] == "abstain"


def test_unknown_adapter_metadata_and_offline_profiles_abstain(profiles):
    metadata = deepcopy(profiles[0])
    metadata["deployments"] = []
    unknown = deepcopy(profiles[0])
    unknown["deployments"][0]["adapter"] = "arbitrary-python"
    offline = deepcopy(profiles[0])
    offline["runtime_status"]["status"] = "offline"
    for profile in (metadata, unknown, offline):
        assert route([profile], MATH_REQUEST, available_adapters={"sympy-equation"})["status"] == "abstain"


def test_unknown_and_stale_runtime_are_not_healthy():
    now = datetime(2026, 11, 4, tzinfo=timezone.utc)
    assert _runtime_health({"runtime_status": {"status": "unknown"}}, now) == 0
    assert _runtime_health({"runtime_status": {"status": "ready"}}, now) == 0
    assert _runtime_health({"runtime_status": {"status": "ready", "last_probe": "2020-01-01T00:00:00Z"}}, now) == 0
    assert _runtime_health({"runtime_status": {"status": "ready", "last_probe": "2026-11-03T23:58:00Z"}}, now) == 2
    assert _runtime_health({"runtime_status": {"status": "ready", "last_probe": "2026-11-05T00:00:00Z"}}, now) == 0


def test_geography_horizon_inputs_and_licenses_fail_closed(profiles):
    profile = deepcopy(profiles[1])
    profile["capabilities"][0]["applicability"] = {
        "geography": "regional", "regions": ["TW"], "max_horizon_days": 3
    }
    request = TaskRequest.from_dict({
        "task_id": "weather.precipitation_forecast",
        "inputs": {"latitude": 24, "longitude": 121, "target_date": "bad"},
        "constraints": {"region": "US", "horizon_days": 5, "required_license_fields": ["data"]},
    })
    decision = route([profile], request, available_adapters={"open-meteo-weathernext2"})
    assert decision["status"] == "abstain"
    reasons = " ".join(decision["rejected"][0]["reasons"])
    assert "region" in reasons and "horizon" in reasons and "data license" in reasons


def test_unknown_cost_can_be_rejected(profiles):
    request = TaskRequest.from_dict({
        "task_id": "weather.precipitation_forecast",
        "inputs": {"latitude": 24, "longitude": 121, "target_date": "2026-11-05"},
        "constraints": {"max_cost_usd": 1, "reject_unknown_costs": True},
    })
    decision = route([profiles[1]], request, available_adapters={"open-meteo-weathernext2"})
    assert decision["status"] == "abstain"


def test_cost_over_budget_rejected_but_unrelated_deployment_does_not_poison_profile(profiles):
    profile = deepcopy(profiles[0])
    profile["deployments"][0]["cost"] = {
        "amount": 10, "currency": "USD", "unit": "request", "status": "listed"
    }
    request = TaskRequest.from_dict({
        "task_id": "math.solve_equation",
        "inputs": {"equation": "x=1"},
        "constraints": {"max_cost_usd": 1},
    })
    assert route([profile], request, available_adapters={"sympy-equation"})["status"] == "abstain"

    profile["deployments"].append({
        "id": "cheap", "kind": "local", "adapter": "sympy-equation", "status": "ready",
        "cost": {"amount": 0, "currency": "USD", "unit": "request", "status": "listed"},
    })
    result = route([profile], request, available_adapters={"sympy-equation"})
    assert result["status"] == "selected"
    assert result["selected"]["deployment_id"] == "cheap"
