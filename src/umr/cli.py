"""Command-line interface."""

import argparse
import json
from pathlib import Path
from typing import Any

from .profile import load_schema
from .registry import HuggingFaceHubConnector
from .service import RouterService


def _print(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(prog="umr")
    subparsers = parser.add_subparsers(dest="command", required=True)

    route_parser = subparsers.add_parser("route", help="route a normalized Task Request")
    route_parser.add_argument("--request", required=True, type=Path)
    route_parser.add_argument("--execute", action="store_true")
    route_parser.add_argument("--profiles", default="profiles", type=Path)
    route_parser.add_argument("--approval-ledger", type=Path)

    discover_parser = subparsers.add_parser("discover", help="search Hugging Face metadata")
    discover_parser.add_argument("--task-id", required=True)
    discover_parser.add_argument("--limit", default=10, type=int)

    subparsers.add_parser("schema", help="print the Capability Profile JSON Schema")

    serve_parser = subparsers.add_parser("serve", help="run a localhost HTTP API")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", default=8765, type=int)
    serve_parser.add_argument("--profiles", default="profiles", type=Path)
    serve_parser.add_argument("--approval-ledger", type=Path)

    args = parser.parse_args()
    if args.command == "route":
        with args.request.open("r", encoding="utf-8") as stream:
            body = json.load(stream)
        if not isinstance(body, dict):
            parser.error("request file must contain a JSON object")
        body["execute"] = bool(args.execute)
        _print(RouterService(args.profiles, approval_ledger_path=args.approval_ledger).handle(body))
    elif args.command == "discover":
        _print(HuggingFaceHubConnector().search_models(args.task_id, args.limit))
    elif args.command == "schema":
        _print(load_schema())
    elif args.command == "serve":
        if args.host not in ("127.0.0.1", "localhost", "::1"):
            parser.error("The MVP HTTP API may only bind to localhost.")
        from .http_api import serve

        serve(host=args.host, port=args.port, profile_directory=args.profiles, approval_ledger_path=args.approval_ledger)


if __name__ == "__main__":
    main()
