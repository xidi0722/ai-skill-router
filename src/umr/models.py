"""Small, framework-independent request and routing policy types."""

from dataclasses import dataclass, field
import math
from typing import Any


EVIDENCE_LEVELS = {
    "none": 0,
    "publisher_claim": 1,
    "reproduced": 2,
    "independent": 3,
}


@dataclass(frozen=True)
class TaskRequest:
    task_id: str
    inputs: dict[str, Any]
    constraints: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TaskRequest":
        task_id = value.get("task_id")
        inputs = value.get("inputs", {})
        constraints = value.get("constraints", {})
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task_id must be a non-empty string")
        if not isinstance(inputs, dict):
            raise ValueError("inputs must be a JSON object")
        if not isinstance(constraints, dict):
            raise ValueError("constraints must be a JSON object")
        if "country_code" in inputs and not isinstance(inputs["country_code"], str):
            raise ValueError("inputs.country_code must be a string")
        return cls(task_id=task_id.strip(), inputs=inputs, constraints=constraints)


@dataclass(frozen=True)
class RoutePolicy:
    require_independent_evidence: bool = False
    minimum_evidence_level: str = "none"
    max_cost_usd: float | None = None
    reject_unknown_costs: bool = False
    required_license_fields: tuple[str, ...] = ()
    allowed_licenses: tuple[str, ...] = ()
    require_quality_comparison: bool = False
    comparison_metric_id: str | None = None
    minimum_metric_difference: float = 0.0

    @classmethod
    def from_constraints(cls, constraints: dict[str, Any]) -> "RoutePolicy":
        require_independent = constraints.get("require_independent_evidence", False)
        reject_unknown_costs = constraints.get("reject_unknown_costs", False)
        if not isinstance(require_independent, bool):
            raise ValueError("require_independent_evidence must be a boolean")
        if not isinstance(reject_unknown_costs, bool):
            raise ValueError("reject_unknown_costs must be a boolean")
        require_quality_comparison = constraints.get("require_quality_comparison", False)
        if not isinstance(require_quality_comparison, bool):
            raise ValueError("require_quality_comparison must be a boolean")
        comparison_metric_id = constraints.get("comparison_metric_id")
        if comparison_metric_id is not None and (not isinstance(comparison_metric_id, str) or not comparison_metric_id.strip()):
            raise ValueError("comparison_metric_id must be a non-empty string")
        if require_quality_comparison and comparison_metric_id is None:
            raise ValueError("comparison_metric_id is required when quality comparison is required")
        minimum_metric_difference = constraints.get("minimum_metric_difference", 0.0)
        if isinstance(minimum_metric_difference, bool) or not isinstance(minimum_metric_difference, (int, float)) or not math.isfinite(minimum_metric_difference) or minimum_metric_difference < 0:
            raise ValueError("minimum_metric_difference must be a non-negative finite number")
        level = constraints.get("minimum_evidence_level", "none")
        if require_independent:
            level = "independent"
        if level not in EVIDENCE_LEVELS:
            raise ValueError(f"Unsupported minimum_evidence_level: {level}")

        max_cost = constraints.get("max_cost_usd")
        if max_cost is not None:
            if (
                isinstance(max_cost, bool)
                or not isinstance(max_cost, (int, float))
                or not math.isfinite(max_cost)
                or max_cost < 0
            ):
                raise ValueError("max_cost_usd must be a non-negative number")
            max_cost = float(max_cost)

        horizon = constraints.get("horizon_days")
        if horizon is not None and (
            isinstance(horizon, bool)
            or not isinstance(horizon, (int, float))
            or not math.isfinite(horizon)
            or horizon < 0
        ):
            raise ValueError("horizon_days must be a non-negative number")
        region = constraints.get("region")
        if region is not None and not isinstance(region, str):
            raise ValueError("region must be a string")

        required_license_fields = constraints.get("required_license_fields", [])
        allowed_licenses = constraints.get("allowed_licenses", [])
        valid_license_fields = {"code", "weights", "data"}
        if (
            not isinstance(required_license_fields, list)
            or any(field not in valid_license_fields for field in required_license_fields)
        ):
            raise ValueError("required_license_fields must contain code, weights, and/or data")
        if not isinstance(allowed_licenses, list) or any(
            not isinstance(license_id, str) for license_id in allowed_licenses
        ):
            raise ValueError("allowed_licenses must be a list of strings")

        return cls(
            require_independent_evidence=level == "independent",
            minimum_evidence_level=level,
            max_cost_usd=max_cost,
            reject_unknown_costs=reject_unknown_costs,
            required_license_fields=tuple(required_license_fields),
            allowed_licenses=tuple(allowed_licenses),
            require_quality_comparison=require_quality_comparison,
            comparison_metric_id=comparison_metric_id,
            minimum_metric_difference=float(minimum_metric_difference),
        )
