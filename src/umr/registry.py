"""Profile catalog and metadata-only Hugging Face discovery connector."""

import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .profile import validate_profile


HF_API_BASE = "https://huggingface.co/api"
HF_TASK_MAP = {
    "vision.image_classification": "image-classification",
    "vision.object_detection": "object-detection",
    "audio.automatic_speech_recognition": "automatic-speech-recognition",
    "text.text_classification": "text-classification",
}


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


class LocalCatalogConnector:
    def __init__(self, directory: str | Path):
        self.directory = Path(directory)

    def discover(self) -> list[dict[str, Any]]:
        profiles: list[dict[str, Any]] = []
        if not self.directory.exists():
            return profiles
        for path in sorted(self.directory.glob("*.json")):
            with path.open("r", encoding="utf-8") as stream:
                profile = json.load(stream)
            validate_profile(profile)
            profiles.append(profile)
        return profiles


class HuggingFaceHubConnector:
    """Search public HF metadata; results are explicitly non-executable."""

    def __init__(self, timeout_seconds: float = 8.0):
        self.timeout_seconds = timeout_seconds

    def search_models(self, task_id: str, limit: int = 20) -> list[dict[str, Any]]:
        pipeline_tag = HF_TASK_MAP.get(task_id)
        if not pipeline_tag:
            return []
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")

        query = urlencode({
            "pipeline_tag": pipeline_tag,
            "sort": "downloads",
            "direction": "-1",
            "limit": limit,
        })
        request = Request(
            f"{HF_API_BASE}/models?{query}",
            headers={"Accept": "application/json", "User-Agent": "universal-model-router/0.1"},
        )
        try:
            with build_opener(_NoRedirectHandler).open(
                request, timeout=self.timeout_seconds
            ) as response:
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise RuntimeError("Hugging Face Hub response exceeded the size limit")
                payload = json.loads(raw)
        except HTTPError as exc:
            raise RuntimeError(f"Hugging Face Hub returned HTTP {exc.code}") from exc
        except (URLError, TimeoutError) as exc:
            raise RuntimeError(f"Hugging Face Hub discovery failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("Hugging Face Hub returned invalid JSON") from exc

        if not isinstance(payload, list):
            raise RuntimeError("Hugging Face Hub returned an unexpected response shape")

        profiles = []
        for item in payload[:limit]:
            model_id = item.get("modelId") or item.get("id")
            if not isinstance(model_id, str) or not model_id:
                continue
            task = item.get("pipeline_tag") or pipeline_tag
            profile = {
                "schema_version": "umr/v0.1",
                "id": f"urn:umr:huggingface.co:model:{model_id}",
                "kind": "model",
                "display_name": model_id,
                "description": "Hub metadata discovery result; not an executable deployment.",
                "source": {
                    "publisher": model_id.split("/", 1)[0] if "/" in model_id else "unknown",
                    "artifact_url": f"https://huggingface.co/{model_id}",
                    "revision": item.get("sha"),
                    "artifact_digest": None,
                    "license": {"code": None, "weights": None, "data": None},
                },
                "capabilities": [{
                    "task_id": task_id,
                    "input_schema": {"type": "object"},
                    "output_schema": {"type": "object"},
                    "applicability": {},
                    "data_requirements": [],
                }],
                "deployments": [],
                "evaluations": [],
                "quality_evidence_level": "none",
                "trust": {"metadata_status": "unverified-public-metadata"},
                "discovery_status": "metadata_only",
                "extensions": {
                    "downloads": item.get("downloads"),
                    "likes": item.get("likes"),
                    "pipeline_tag": task,
                },
            }
            validate_profile(profile)
            profiles.append(profile)
        return profiles
