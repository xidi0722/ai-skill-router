# Universal Model Router

Universal Model Router is an early, evidence-aware capability layer for discovering, selecting, executing, and checking existing models and scientific tools. The first MVP supports curated local profiles, metadata-only Hugging Face Hub discovery, exact equation solving with SymPy, and a fixed-host Open-Meteo WeatherNext 2 forecast adapter.

This project is not a general model marketplace and does not execute arbitrary model repositories, downloaded code, or MCP servers. Discovering a repository does not make it executable.

## Install

Python 3.11 or later is required.

    python -m pip install -e .

## Develop and verify locally

    python -m pip install -e ".[test]" -c constraints-dev.txt
    python -m pytest -q
    python tools/run_offline_evaluation.py
    python tools/run_evidence_ranking_evaluation.py

The first offline evaluation writes 50 policy cases to `outputs/offline-evaluation.json` and `.md`. The evidence ranking evaluation writes 36 comparison cases to `outputs/evidence-ranking-evaluation.json` and `.md`. Both are synthetic fixtures and are not evidence about real model quality. See [Evidence Contract and public source audit](outputs/evidence-routing-evaluation.md) and [public score source audit](outputs/evidence-source-audit.md).

On Windows with a standard Python installation, create an isolated environment and run the same checks from PowerShell:

    py -3 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -e ".[test]" -c constraints-dev.txt
    .\.venv\Scripts\python.exe -m pytest -q
    .\.venv\Scripts\python.exe tools\run_offline_evaluation.py
    .\.venv\Scripts\python.exe tools\run_evidence_ranking_evaluation.py
    .\.venv\Scripts\umr.exe route --request examples\solve.json --execute

## Try the local equation solver

    umr route --request examples/solve.json --execute

The request format is:

    {
      "task_id": "math.solve_equation",
      "inputs": {"equation": "x**2 - 4 = 0"},
      "constraints": {}
    }

The solver accepts numeric constants, variable names, parentheses, +, -, *, division by a non-zero numeric constant, and non-negative integer powers up to 10. It rejects calls, attributes, indexing, symbolic denominators, and all other Python syntax.

## Try the WeatherNext adapter

    umr route --request examples/weather.json --execute

The request must include latitude, longitude, target date, and timezone. The adapter calls a fixed Open-Meteo HTTPS host; callers cannot supply a URL. The response includes the forecast source and marks forecast quality as unvalidated by this project. The CLI and HTTP service do not configure trusted benchmark digests, so `require_independent_evidence: true` abstains by default. A Python integration may inject administrator-approved full-record digests into `RouterService`; a profile's `verified_by` string alone is not trusted. The example date is fixed; update it to a local date in the current forecast window before use.

External API terms, availability, and current pricing should be checked before production use. No external API is called during installation.

## Discover Hugging Face models

    umr discover --task-id vision.image_classification

This connector returns public Hub metadata only. It does not infer a runnable endpoint from model weights or a model card. Such results are marked metadata_only and cannot be selected for execution.

Supported task IDs map to Hub pipeline tags:

- vision.image_classification
- vision.object_detection
- audio.automatic_speech_recognition
- text.text_classification

## Local HTTP API

    umr serve

The server binds to 127.0.0.1:8765 only.

- GET /health
- GET /profiles
- GET /schema
- POST /route

POST a Task Request to /route. Add "execute": true to the request to run the selected allowlisted adapter. The route decision is returned with candidate exclusions, evidence level, reasons, and provenance. Execution failures return `execution.status: "failed"` with a stable error code and the selected profile/deployment/adapter provenance; provider exception text and request URLs are redacted.

For a strict numeric quality comparison, add `require_quality_comparison: true` and `comparison_metric_id` to constraints. Pass a separately maintained approval ledger with `--approval-ledger`; the router abstains when records are unapproved, revoked, stale, or incomparable. The ledger is a local administrative file and has no signature or identity verification in this MVP.

## Research and design

- [Prior art research](outputs/research-report.md)
- [Architecture and MVP](outputs/architecture.md)
- [Threat model](outputs/threat-model.md)
- [Implementation status](outputs/implementation-status.md)
- [Capability Profile schema](src/umr/schemas/capability-profile.schema.json)

## Current limits

- There is no historical forecast backtest bundled with the MVP. WeatherNext results are operational API outputs, not independently verified predictions.
- HF discovery is not an execution adapter.
- Costs and service terms can change; unknown costs remain unknown and strict cost policies reject them.
- The MVP exposes HTTP and Python interfaces, but does not yet implement an MCP server, ARD registry client, local model sandbox, or domain-specific biology/vision evaluators.
- The localhost API is not hardened for public traffic. SymPy runs in a terminable child process with a wall-clock timeout, but has no memory quota or full OS sandbox.
