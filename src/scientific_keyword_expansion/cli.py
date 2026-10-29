"""Command-line entrypoint for validated, agent-generated candidate data."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .exporters import write_outputs
from .pipeline import adapt_query, build_report


def _http_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--proxy-url", help="HTTP(S) proxy URL; overrides SKE_PROXY_URL and urllib system/environment detection")
    parser.add_argument("--timeout", type=float, help="Seconds per request; default SKE_HTTP_TIMEOUT or 12")
    parser.add_argument("--retries", type=int, help="Retries per request; default SKE_HTTP_RETRIES or 2")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "doctor":
        from .diagnostic import run_doctor
        doctor_parser = argparse.ArgumentParser(prog="scientific-keywords doctor", description="Probe academic API DNS, proxy, and HTTPS")
        _http_arguments(doctor_parser)
        return run_doctor(doctor_parser.parse_args(argv[1:]))
    parser = argparse.ArgumentParser(description="Process agent-generated scientific keyword candidates")
    parser.add_argument("--input", type=Path, required=True, help="JSON request containing topic and candidate concepts")
    parser.add_argument("--out", type=Path, required=True, help="Output directory")
    parser.add_argument("--formats", nargs="+", choices=["markdown", "json", "csv"],
                        help="Override input output_format; default is Markdown")
    parser.add_argument("--platform", choices=["generic_boolean", "google_scholar", "web_of_science", "scopus", "openalex"])
    parser.add_argument("--providers", nargs="+", choices=["openalex", "semantic_scholar", "crossref", "arxiv"],
                        help="Research mode: query only the selected academic metadata sources")
    parser.add_argument("--debug-log", type=Path, help="Write a compact execution-stage JSON log")
    parser.add_argument("--skill-loaded", action="store_true", help="Agent attests it read SKILL.md; recorded as agent-reported")
    _http_arguments(parser)
    args = parser.parse_args(argv)
    events: list[dict] = []
    def event(stage: str, status: str, **details) -> None:
        events.append({"stage": stage, "status": status, "at": datetime.now(timezone.utc).isoformat(), **details})
    event("skill_loaded", "agent_reported" if args.skill_loaded else "not_observed")
    try:
        raw = json.loads(args.input.read_text(encoding="utf-8-sig"))
        event("topic_analyzed", "input_supplied" if raw.get("domain_analysis") else "not_observed")
        event("candidates_generated", "input_supplied", count=len(raw.get("candidates", [])))
        verifier = None
        if raw.get("mode", "quick").lower() == "research":
            from .verification import HttpClient, Verifier
            verifier = Verifier(client=HttpClient(proxy_url=args.proxy_url, timeout=args.timeout, retries=args.retries))
        if args.providers:
            if raw.get("mode", "quick").lower() != "research":
                raise ValueError("--providers requires research mode")
            from .verification import Arxiv, Crossref, OpenAlex, SemanticScholar, Verifier
            registry = {"openalex": OpenAlex, "semantic_scholar": SemanticScholar,
                        "crossref": Crossref, "arxiv": Arxiv}
            verifier = Verifier([registry[name]() for name in dict.fromkeys(args.providers)], verifier.client)
        report = build_report(raw, verifier=verifier)
        event("candidates_validated", "success", selected=report["generated_count"],
              quality_passed=report["quality_checks"]["passed"])
        event("queries_generated", "success", count=len(report["search_queries"]))
        event("literature_checked", "completed" if report["mode"] == "research" else "not_requested",
              verified_terms=sum(bool(item["evidence"]) for item in report["keywords"]),
              live_queries=sum(query.get("live_evaluation") is not None for query in report["search_queries"]),
              revised_queries=sum(bool(query.get("live_evaluation") and query["live_evaluation"]["revision_count"])
                                  for query in report["search_queries"]))
        requested_format = raw.get("output_format", "markdown").lower()
        selected_formats = args.formats or (["markdown", "json", "csv"] if requested_format == "all" else [requested_format])
        paths = write_outputs(report, args.out, tuple(selected_formats))
        if args.platform:
            target = args.out / f"queries-{args.platform}.txt"
            target.write_text("\n\n".join(adapt_query(query, args.platform) for query in report["search_queries"]) + "\n", encoding="utf-8")
            paths.append(target)
        for path in paths:
            print(path)
        event("report_exported", "success", paths=[str(path) for path in paths])
        if args.debug_log:
            args.debug_log.parent.mkdir(parents=True, exist_ok=True)
            args.debug_log.write_text(json.dumps({"stages": events}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for warning in report["warnings"]:
            print(f"warning: {warning}", file=sys.stderr)
        return 0
    except (ValueError, OSError, json.JSONDecodeError) as error:
        event("pipeline_failed", "failed", error=str(error))
        if args.debug_log:
            try:
                args.debug_log.parent.mkdir(parents=True, exist_ok=True)
                args.debug_log.write_text(json.dumps({"stages": events}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            except OSError:
                pass
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
