"""Application service joining discovery, routing, execution, and provenance."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError

from .evidence import ApprovalLedger
from .execution import AdapterRegistry, ExecutionError
from .models import RoutePolicy, TaskRequest
from .profile import validate_profile
from .registry import HuggingFaceHubConnector, LocalCatalogConnector
from .router import route


class RouterService:
    def __init__(
        self,
        profile_directory: str | Path = "profiles",
        trusted_evaluation_digests: set[str] | None = None,
        approved_evaluation_digests: set[str] | None = None,
        revoked_evaluation_digests: set[str] | None = None,
        approval_ledger_path: str | Path | None = None,
        adapter_registry: AdapterRegistry | None = None,
    ):
        self.profile_directory = Path(profile_directory)
        self.local_connector = LocalCatalogConnector(self.profile_directory)
        self.hf_connector = HuggingFaceHubConnector()
        self.adapters = adapter_registry if adapter_registry is not None else AdapterRegistry()
        self.trusted_evaluation_digests = trusted_evaluation_digests or set()
        self.approved_evaluation_digests = approved_evaluation_digests or set()
        self.revoked_evaluation_digests = revoked_evaluation_digests or set()
        if approval_ledger_path is not None:
            ledger = ApprovalLedger.load(approval_ledger_path)
            self.approved_evaluation_digests.update(
                digest for digest in ledger.approvals if ledger.is_approved(digest)
            )
            self.revoked_evaluation_digests.update(ledger.revoked)

    def profiles(self) -> list[dict[str, Any]]:
        return self.local_connector.discover()

    def handle(self, body: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(body.get("execute", False), bool):
            raise ValueError("execute must be a boolean")
        request = TaskRequest.from_dict(body)
        constraints = request.constraints
        if not isinstance(constraints.get("discover_huggingface", False), bool):
            raise ValueError("discover_huggingface must be a boolean")
        policy = RoutePolicy.from_constraints(constraints)
        profiles = self.profiles()
        if constraints.get("discover_huggingface", False):
            limit = constraints.get("discovery_limit", 10)
            if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
                raise ValueError("discovery_limit must be an integer between 1 and 100")
            discovered = self.hf_connector.search_models(request.task_id, limit=limit)
            known = {profile["id"] for profile in profiles}
            profiles.extend(profile for profile in discovered if profile["id"] not in known)
        for profile in profiles:
            validate_profile(profile)

        decision = route(
            profiles,
            request,
            policy,
            self.adapters.adapter_ids,
            self.trusted_evaluation_digests,
            self.approved_evaluation_digests,
            self.revoked_evaluation_digests,
        )
        response: dict[str, Any] = {
            "request": {
                "task_id": request.task_id,
                "constraints": constraints,
            },
            "decision": decision,
            "provenance": {
                "router_version": "0.1.0",
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "input_digest_sha256": hashlib.sha256(
                    json.dumps(request.inputs, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
                ).hexdigest(),
            },
        }
        if decision["selected"] is None:
            return response

        selected_id = decision["selected"]["profile_id"]
        profile = next(item for item in profiles if item["id"] == selected_id)
        deployment = next(
            item
            for item in profile["deployments"]
            if item["id"] == decision["selected"]["deployment_id"]
        )
        response["provenance"].update({
            "profile_id": selected_id,
            "source": profile["source"],
            "deployment_id": deployment["id"],
            "adapter": deployment["adapter"],
            "quality_evidence_level": decision["selected"]["evidence_level"],
        })

        if body.get("execute", False):
            capability = decision["selected"]["capability"]
            input_schema = capability.get("input_schema", {})
            output_schema = capability.get("output_schema", {})
            started_at = datetime.now(timezone.utc).isoformat()
            result: Any = None
            adapter_returned = False
            try:
                Draft202012Validator.check_schema(input_schema)
                Draft202012Validator.check_schema(output_schema)
                Draft202012Validator(input_schema, format_checker=FormatChecker()).validate(request.inputs)
                result = self.adapters.execute(deployment["adapter"], request.inputs)
                adapter_returned = True
                Draft202012Validator(output_schema, format_checker=FormatChecker()).validate(result)
            except SchemaError:
                return self._execution_failure(
                    response, started_at, "capability_schema_invalid",
                    "The selected capability has an invalid input or output schema.",
                )
            except ValidationError:
                if not adapter_returned:
                    return self._execution_failure(
                        response, started_at, "input_schema_validation_failed",
                        "The request inputs do not satisfy the selected capability schema.",
                    )
                return self._execution_failure(
                    response, started_at, "output_schema_validation_failed",
                    "The adapter output does not satisfy the selected capability schema.",
                )
            except ExecutionError as exc:
                # Do not return adapter exception text: provider errors can contain request URLs
                # and user-supplied query values. Preserve only a stable error category.
                messages = {
                    "timeout": "The adapter exceeded its execution time limit.",
                    "provider_timeout": "The model provider request timed out.",
                    "provider_http_error": "The model provider returned an HTTP error.",
                    "provider_redirect_blocked": "The model provider attempted a redirect.",
                    "provider_connection_failed": "The model provider could not be reached.",
                    "response_too_large": "The model provider response exceeded the size limit.",
                    "invalid_json": "The model provider returned invalid JSON.",
                }
                return self._execution_failure(
                    response,
                    started_at,
                    exc.code,
                    messages.get(exc.code, "The selected adapter could not complete the request."),
                )
            response["execution"] = {
                "status": "completed",
                "started_at": started_at,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "result": result,
            }
        else:
            response["execution"] = {"status": "not_requested"}
        return response

    @staticmethod
    def _execution_failure(
        response: dict[str, Any], started_at: str, code: str, message: str
    ) -> dict[str, Any]:
        response["execution"] = {
            "status": "failed",
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "error": {"code": code, "message": message},
        }
        return response
