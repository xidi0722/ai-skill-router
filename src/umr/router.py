"""Eligibility filtering and conservative, evidence-aware candidate ranking."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError

from .evidence import compare_profiles, contract_evaluation_digest, contract_errors
from .models import EVIDENCE_LEVELS, RoutePolicy, TaskRequest


def _profile_evidence_level(
    profile: dict[str, Any],
    task_id: str,
    request: TaskRequest,
    trusted_evaluation_digests: set[str],
    approved_evaluation_digests: set[str],
    revoked_evaluation_digests: set[str],
) -> str:
    evaluations = profile.get("evaluations", [])
    levels = ["none"]
    for evaluation in evaluations:
        if not isinstance(evaluation, dict) or evaluation.get("task_id") != task_id:
            continue
        applicability = evaluation.get("applicability") if isinstance(evaluation.get("applicability"), dict) else {}
        requested_region = request.constraints.get("region") or request.inputs.get("country_code")
        evidence_region = evaluation.get("region", applicability.get("region"))
        if requested_region and evidence_region not in (requested_region, "global"):
            continue
        requested_horizon = request.constraints.get("horizon_days")
        evidence_horizon = evaluation.get("horizon_days", applicability.get("horizon_days"))
        if requested_horizon is not None and evidence_horizon != requested_horizon:
            continue
        level = evaluation.get("evidence_level", "none")
        is_contract_record = "artifact" in evaluation
        contract_digest = None
        if not contract_errors(profile, evaluation):
            contract_digest = contract_evaluation_digest(profile, evaluation)
        legacy_approved = not is_contract_record and evaluation_digest(profile.get("id", ""), evaluation) in trusted_evaluation_digests
        contract_approved = is_contract_record and contract_digest in approved_evaluation_digests
        if level in ("reproduced", "independent") and not (legacy_approved or contract_approved):
            level = "publisher_claim"
        if contract_digest in revoked_evaluation_digests:
            level = "publisher_claim"
        levels.append(level)
    return max(levels, key=lambda level: EVIDENCE_LEVELS.get(level, 0))


def evaluation_digest(profile_id: str, evaluation: dict[str, Any]) -> str:
    """Stable identity for an evaluation explicitly approved by an administrator."""
    canonical = json.dumps(
        {"profile_id": profile_id, "evaluation": evaluation},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _runtime_health(profile: dict[str, Any], now: datetime | None = None) -> int:
    runtime = profile.get("runtime_status") or {}
    status = runtime.get("status", "unknown")
    if status == "offline":
        return -2
    if status not in ("ready", "degraded"):
        return 0
    last_probe = runtime.get("last_probe")
    if not isinstance(last_probe, str):
        return 0
    try:
        probed_at = datetime.fromisoformat(last_probe.replace("Z", "+00:00"))
    except ValueError:
        return 0
    if probed_at.tzinfo is None:
        return 0
    now = now or datetime.now(timezone.utc)
    probed_at = probed_at.astimezone(timezone.utc)
    if probed_at > now + timedelta(seconds=30) or now - probed_at > timedelta(minutes=5):
        return 0
    return 2 if status == "ready" else 1


def _required_input_names(capability: dict[str, Any]) -> set[str]:
    schema = capability.get("input_schema", {})
    required = schema.get("required", []) if isinstance(schema, dict) else []
    return set(required) if isinstance(required, list) else set()


def _check_applicability(
    capability: dict[str, Any],
    request: TaskRequest,
) -> list[str]:
    reasons: list[str] = []
    input_schema = capability.get("input_schema", {})
    try:
        Draft202012Validator.check_schema(input_schema)
        Draft202012Validator(input_schema, format_checker=FormatChecker()).validate(request.inputs)
    except SchemaError:
        reasons.append("input schema is invalid")
    except ValidationError as exc:
        reasons.append(f"inputs do not satisfy capability schema: {exc.message}")

    applicability = capability.get("applicability", {})
    constraints = request.constraints

    wanted_region = constraints.get("region") or request.inputs.get("country_code")
    supported_regions = applicability.get("regions")
    geography = applicability.get("geography")
    if geography not in (None, "global") and not wanted_region:
        reasons.append("region is required for this geographically limited capability")
    elif wanted_region and geography != "global":
        if supported_regions:
            if wanted_region not in supported_regions:
                reasons.append(f"region {wanted_region} is outside declared coverage")
        else:
            reasons.append("geographic applicability is unknown")

    horizon = constraints.get("horizon_days")
    if horizon is not None:
        maximum = applicability.get("max_horizon_days")
        minimum = applicability.get("min_horizon_days", 0)
        if maximum is None:
            reasons.append("maximum horizon is not declared")
        elif horizon > maximum or horizon < minimum:
            reasons.append(f"horizon {horizon} days is outside declared range")
    return reasons


def route(
    profiles: list[dict[str, Any]],
    request: TaskRequest,
    policy: RoutePolicy | None = None,
    available_adapters: set[str] | None = None,
    trusted_evaluation_digests: set[str] | None = None,
    approved_evaluation_digests: set[str] | None = None,
    revoked_evaluation_digests: set[str] | None = None,
) -> dict[str, Any]:
    policy = policy or RoutePolicy.from_constraints(request.constraints)
    trusted_evaluation_digests = trusted_evaluation_digests or set()
    approved_evaluation_digests = approved_evaluation_digests or set()
    revoked_evaluation_digests = revoked_evaluation_digests or set()
    minimum_evidence = EVIDENCE_LEVELS[policy.minimum_evidence_level]
    candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for profile in profiles:
        profile_id = profile.get("id", "<unknown>")
        matched = [
            capability
            for capability in profile.get("capabilities", [])
            if capability.get("task_id") == request.task_id
        ]
        if not matched:
            rejected.append({"profile_id": profile_id, "reasons": ["task_id does not match"]})
            continue

        failures: list[str] = []
        executable = [
            deployment
            for deployment in profile.get("deployments", [])
            if deployment.get("adapter")
            and available_adapters is not None
            and deployment.get("adapter") in available_adapters
            and deployment.get("status", "ready") in ("ready", "unknown")
        ]
        if not executable:
            failures.append("no executable deployment with a registered adapter; discovery metadata is not execution")

        applicable_capabilities = []
        capability_rejections = []
        for capability in matched:
            capability_failures = []
            missing = _required_input_names(capability) - request.inputs.keys()
            if missing:
                capability_failures.append("missing inputs: " + ", ".join(sorted(missing)))
            capability_failures.extend(_check_applicability(capability, request))
            if capability_failures:
                capability_rejections.append(capability_failures)
            else:
                applicable_capabilities.append(capability)
        if matched and not applicable_capabilities:
            failures.extend(
                reason
                for capability_failures in capability_rejections
                for reason in capability_failures
            )
            failures.append("no matching capability satisfies the request constraints")

        evidence_level = _profile_evidence_level(
            profile, request.task_id, request, trusted_evaluation_digests,
            approved_evaluation_digests, revoked_evaluation_digests,
        )
        if EVIDENCE_LEVELS[evidence_level] < minimum_evidence:
            failures.append(
                f"quality evidence {evidence_level} is below required {policy.minimum_evidence_level}"
            )
        runtime_health = _runtime_health(profile)
        if runtime_health == -2:
            failures.append("profile runtime status is offline")

        licenses = profile.get("source", {}).get("license", {})
        for field in policy.required_license_fields:
            if not licenses.get(field):
                failures.append(f"required {field} license is unknown")
        if policy.allowed_licenses:
            declared = [
                licenses.get(field)
                for field in ("code", "weights", "data")
                if licenses.get(field)
            ]
            if not declared:
                failures.append("no license is declared for the allowed_licenses policy")
            elif any(license_id not in policy.allowed_licenses for license_id in declared):
                failures.append("a declared license is outside allowed_licenses")

        eligible_deployments = []
        deployment_rejections = []
        for deployment in executable:
            cost = deployment.get("cost") or {}
            amount = cost.get("amount")
            currency = cost.get("currency")
            deployment_failures = []
            if policy.max_cost_usd is not None:
                if amount is None:
                    if policy.reject_unknown_costs:
                        deployment_failures.append(f"cost for {deployment['id']} is unknown")
                elif currency != "USD":
                    deployment_failures.append(f"cost currency for {deployment['id']} is not USD")
                elif amount > policy.max_cost_usd:
                    deployment_failures.append(f"deployment {deployment['id']} exceeds max_cost_usd")
            if deployment_failures:
                deployment_rejections.extend(deployment_failures)
            else:
                eligible_deployments.append(deployment)

        if executable and not eligible_deployments:
            failures.extend(deployment_rejections)

        if failures:
            rejected.append({"profile_id": profile_id, "reasons": sorted(set(failures))})
            continue

        # Metrics are deliberately not collapsed across benchmarks. Ranking first
        # uses evidence tier, then declared live health and deterministic ID order.
        health = runtime_health
        candidates.append({
            "profile": profile,
            "capability": applicable_capabilities[0],
            "deployment": sorted(eligible_deployments, key=lambda item: item["id"])[0],
            "evidence_level": evidence_level,
            "score": [EVIDENCE_LEVELS[evidence_level], health],
            "quality_note": (
                "No comparable quality evaluation is recorded."
                if evidence_level == "none"
                else "Evidence tier is shown; metric values are not compared across benchmarks."
            ),
        })

    candidates.sort(
        key=lambda item: (
            -item["score"][0],
            -item["score"][1],
            item["profile"]["id"],
        )
    )
    comparison = None
    if policy.require_quality_comparison and candidates:
        comparison = compare_profiles(
            [candidate["profile"] for candidate in candidates],
            policy.comparison_metric_id or "",
            approved_digests=approved_evaluation_digests,
            revoked_digests=revoked_evaluation_digests,
            minimum_difference=policy.minimum_metric_difference,
        )
        if comparison["status"] != "ordered":
            return {
                "status": "abstain",
                "selected": None,
                "candidates": [
                    {"profile_id": item["profile"]["id"], "deployment_id": item["deployment"]["id"], "evidence_level": item["evidence_level"]}
                    for item in candidates
                ],
                "comparison": comparison,
                "rejected": rejected,
                "reason": "Quality comparison is required but approved comparable evidence is insufficient.",
            }
        ranks = {item["profile_id"]: index for index, item in enumerate(comparison["ranked"])}
        candidates.sort(key=lambda item: ranks[item["profile"]["id"]])
    if not candidates:
        return {
            "status": "abstain",
            "selected": None,
            "candidates": [],
            "rejected": rejected,
            "reason": "No executable candidate passed the task and policy constraints.",
        }

    selected = candidates[0]
    return {
        "status": "selected",
        "selected": {
            "profile_id": selected["profile"]["id"],
            "display_name": selected["profile"].get("display_name"),
            "deployment_id": selected["deployment"]["id"],
            "adapter": selected["deployment"]["adapter"],
            "capability": selected["capability"],
            "evidence_level": selected["evidence_level"],
            "quality_note": selected["quality_note"],
        },
        "candidates": [
            {
                "profile_id": item["profile"]["id"],
                "deployment_id": item["deployment"]["id"],
                "evidence_level": item["evidence_level"],
                "score": item["score"],
                "quality_note": item["quality_note"],
            }
            for item in candidates
        ],
        "rejected": rejected,
        **({"comparison": comparison} if comparison is not None else {}),
    }
