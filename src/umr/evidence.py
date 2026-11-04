"""Version-bound benchmark evidence and conservative metric comparison."""

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
from typing import Any


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def contract_evaluation_digest(profile: dict[str, Any], evaluation: dict[str, Any]) -> str:
    """Bind approval to the full evidence record and the Profile artifact identity."""
    source = profile.get("source", {})
    identity = {
        "profile_id": profile.get("id"),
        "artifact_id": source.get("artifact_id"),
        "revision": source.get("revision"),
        "artifact_digest": source.get("artifact_digest"),
        "evaluation": evaluation,
    }
    return hashlib.sha256(canonical_json(identity)).hexdigest()


def capability_contract_digest(profile: dict[str, Any], task_id: str) -> str:
    capabilities = [cap for cap in profile.get("capabilities", []) if cap.get("task_id") == task_id]
    contracts = [{"task_id": task_id, "input_schema": cap.get("input_schema"), "output_schema": cap.get("output_schema")} for cap in capabilities]
    return "sha256:" + hashlib.sha256(canonical_json(sorted(contracts, key=canonical_json))).hexdigest()


def contract_errors(profile: dict[str, Any], evaluation: dict[str, Any]) -> list[str]:
    """Return evidence-contract errors. Legacy evidence is intentionally not comparable."""
    required = ("artifact", "task_id", "contract_digest", "dataset", "applicability", "metrics", "source", "evidence_level")
    errors = [f"missing {key}" for key in required if key not in evaluation]
    if errors:
        return errors
    if not isinstance(evaluation["task_id"], str) or not evaluation["task_id"]:
        errors.append("task_id must be a non-empty string")
    if not isinstance(evaluation["contract_digest"], str):
        errors.append("contract_digest must be a string")
    if not isinstance(evaluation["applicability"], dict):
        errors.append("applicability must be an object")
    if errors:
        return errors
    if evaluation["contract_digest"] != capability_contract_digest(profile, evaluation["task_id"]):
        errors.append("evaluation contract digest does not match Profile input/output schemas")
    artifact = evaluation["artifact"]
    source_artifact = profile.get("source", {})
    if not isinstance(artifact, dict) or not artifact.get("id") or not (artifact.get("revision") or artifact.get("digest")):
        errors.append("artifact identity requires id and revision or digest")
    elif artifact.get("id") != source_artifact.get("artifact_id"):
        errors.append("evaluation artifact id does not match Profile source")
    elif artifact.get("revision") != source_artifact.get("revision") or artifact.get("digest") != source_artifact.get("artifact_digest"):
        errors.append("evaluation artifact revision or digest does not match Profile source")
    dataset = evaluation["dataset"]
    if not isinstance(dataset, dict) or not all(dataset.get(key) for key in ("id", "revision", "split", "config_digest")):
        errors.append("dataset requires id, revision, split, and config_digest")
    source = evaluation["source"]
    if not isinstance(source, dict) or not source.get("url") or not source.get("evaluator"):
        errors.append("evaluation source requires url and evaluator")
    if not isinstance(evaluation["metrics"], list) or not evaluation["metrics"]:
        errors.append("evaluation requires at least one metric")
    return errors


@dataclass(frozen=True)
class ApprovalLedger:
    """Local, administrator-managed approvals kept outside imported Profiles."""
    approvals: dict[str, dict[str, Any]]
    revoked: frozenset[str] = frozenset()

    @classmethod
    def load(cls, path: str | Path) -> "ApprovalLedger":
        with Path(path).open("r", encoding="utf-8") as stream:
            document = json.load(stream)
        approvals = document.get("approvals", {})
        revoked = document.get("revoked", [])
        if not isinstance(approvals, dict) or not isinstance(revoked, list) or any(not isinstance(item, str) for item in revoked):
            raise ValueError("Approval ledger must contain an approvals object and revoked digest list")
        return cls(approvals=approvals, revoked=frozenset(revoked))

    def is_approved(self, digest: str) -> bool:
        record = self.approvals.get(digest)
        return digest not in self.revoked and isinstance(record, dict) and bool(record.get("approved_by")) and _valid_timestamp(record.get("approved_at"))


def _valid_timestamp(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def comparable_context(evaluation: dict[str, Any], metric: dict[str, Any]) -> tuple[Any, ...]:
    dataset = evaluation["dataset"]
    applicability = evaluation["applicability"]
    return (
        evaluation["task_id"], evaluation["contract_digest"], dataset["id"], dataset["revision"],
        dataset["split"], dataset["config_digest"], applicability.get("region"),
        applicability.get("horizon_days"), applicability.get("resolution"),
        metric["id"], metric["unit"], metric["direction"],
    )


def _metric(evaluation: dict[str, Any], metric_id: str) -> dict[str, Any] | None:
    for metric in evaluation.get("metrics", []):
        if isinstance(metric, dict) and metric.get("id") == metric_id:
            value = metric.get("value")
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                return None
            if metric.get("direction") not in ("lower", "higher") or not isinstance(metric.get("unit"), str) or not metric["unit"]:
                return None
            interval = metric.get("confidence_interval")
            if interval is not None and (
                not isinstance(interval, list) or len(interval) != 2
                or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in interval)
                or interval[0] > interval[1]
            ):
                return None
            return metric
    return None


def compare_profiles(
    profiles: list[dict[str, Any]], metric_id: str, *, approved_digests: set[str],
    revoked_digests: set[str] | None = None, minimum_difference: float = 0.0,
) -> dict[str, Any]:
    """Compare only approved, complete records measured under identical conditions."""
    if not metric_id or not math.isfinite(minimum_difference) or minimum_difference < 0:
        raise ValueError("metric_id and a non-negative finite minimum_difference are required")
    revoked = revoked_digests or set()
    options_by_profile = []
    reasons = []
    for profile in profiles:
        options = []
        for evaluation in profile.get("evaluations", []):
            errors = contract_errors(profile, evaluation)
            metric = _metric(evaluation, metric_id)
            digest = contract_evaluation_digest(profile, evaluation) if not errors else None
            if errors or metric is None:
                continue
            if digest in revoked:
                reasons.append({"profile_id": profile.get("id"), "reason": "evaluation approval was revoked"})
                continue
            if digest not in approved_digests:
                continue
            context = comparable_context(evaluation, metric)
            options.append({"profile_id": profile["id"], "value": float(metric["value"]), "direction": metric["direction"], "digest": digest, "context": context, "metric": metric})
        options_by_profile.append(options)
    if any(not options for options in options_by_profile):
        reasons.extend({"profile_id": profile.get("id"), "reason": "no complete approved metric evidence"} for profile, options in zip(profiles, options_by_profile) if not options)
        return {"status": "incomparable", "metric_id": metric_id, "ranked": [], "reasons": reasons or [{"reason": "one or more candidates lack complete approved metric evidence"}]}
    common_contexts = {option["context"] for option in options_by_profile[0]}
    for options in options_by_profile[1:]:
        common_contexts.intersection_update(option["context"] for option in options)
    if not common_contexts:
        return {"status": "incomparable", "metric_id": metric_id, "ranked": [], "reasons": [{"reason": "task, contract, dataset, split, conditions, unit, or metric direction differ"}]}
    chosen_context = sorted(common_contexts, key=repr)[0]
    observations = [
        sorted((option for option in options if option["context"] == chosen_context), key=lambda option: option["digest"])[0]
        for options in options_by_profile
    ]
    direction = observations[0]["direction"]
    reverse = direction == "higher"
    ranked = sorted(observations, key=lambda row: ((-row["value"] if reverse else row["value"]), row["profile_id"]))
    best, second = ranked[0], ranked[1] if len(ranked) > 1 else None
    if second is None:
        status = "ordered"
    else:
        gap = abs(best["value"] - second["value"])
        intervals = [row["metric"].get("confidence_interval") for row in (best, second)]
        overlaps = all(isinstance(interval, list) and len(interval) == 2 for interval in intervals) and max(intervals[0][0], intervals[1][0]) <= min(intervals[0][1], intervals[1][1])
        status = "inconclusive" if gap <= minimum_difference or overlaps else "ordered"
    return {
        "status": status,
        "metric_id": metric_id,
        "context": list(chosen_context),
        "ranked": [{"profile_id": row["profile_id"], "value": row["value"], "unit": row["metric"]["unit"], "direction": direction, "evidence_digest": row["digest"]} for row in ranked],
        "best_profile_ids": [row["profile_id"] for row in ranked if row["value"] == best["value"]],
        "reasons": ([{"reason": "scores are tied or uncertainty intervals overlap"}] if status == "inconclusive" else []),
    }
