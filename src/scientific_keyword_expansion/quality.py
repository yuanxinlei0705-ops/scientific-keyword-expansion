"""Deterministic quality checks; scientific judgments remain with the host Agent."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from .queries import valid_query_expression


def _norm(value: str) -> str:
    return " ".join(value.casefold().split())


def review_quality(keywords: list[dict[str, Any]], queries: list[dict[str, Any]],
                   relationships: list[dict[str, Any]], requested_count: int,
                   language: str, extra_issues: list[dict[str, str]] | None = None) -> dict[str, Any]:
    issues: list[dict[str, str]] = list(extra_issues or [])

    def flag(code: str, severity: str, message: str) -> None:
        issues.append({"code": code, "severity": severity, "message": message})

    if len(keywords) > requested_count:
        flag("count_exceeded", "error", "Selected keyword count exceeds the request.")
    names = [_norm(item["keyword"]) for item in keywords]
    if len(names) != len(set(names)):
        flag("duplicate_keyword", "error", "Canonical keyword strings repeat after normalization.")
    reasons = Counter(_norm(item["reason"]) for item in keywords)
    repeated = {reason for reason, count in reasons.items() if count > 1}
    for item in keywords:
        reason = item["reason"]
        if _norm(reason) in repeated:
            flag("repeated_explanation", "error", f"Explanation is reused: {item['keyword']}")
        if re.search(r"\b(a core concept for|an adjacent concept useful for|is relevant to|related to this research|a standard method in its source field)\b", reason, re.I):
            flag("boilerplate_explanation", "error", f"Explanation is generic: {item['keyword']}")
        if len(reason.strip()) < (18 if re.search(r"[\u3400-\u9fff]", reason) else 45):
            flag("short_explanation", "warning", f"Explanation may lack research detail: {item['keyword']}")
        if not item.get("score_reason", "").strip():
            flag("missing_score_reason", "error", f"Score reason is missing: {item['keyword']}")
        if item["scope"] == "core" and item["scores"]["direct_relevance"] < 55:
            flag("weak_core_relevance", "warning", f"Core scope has a low direct-relevance estimate: {item['keyword']}")
        if language != "english" and not item.get("chinese"):
            flag("translation_review", "warning", f"Chinese translation needs review: {item['keyword']}")
        if item.get("term_class") == "established_term" and item.get("verification_status") == "not_checked":
            flag("established_term_unverified", "warning", f"Established-term classification lacks a live citation: {item['keyword']}")
    if len(keywords) >= 10:
        unique_scores = len({item["relevance_score"] for item in keywords})
        if unique_scores < max(5, len(keywords) // 8):
            flag("score_clustering", "warning", "Relevance scores cluster heavily; review per-concept dimensions.")
        vectors = Counter(tuple(item["scores"].values()) for item in keywords)
        if vectors and max(vectors.values()) >= max(6, len(keywords) // 4):
            flag("repeated_score_vector", "warning", "Many keywords share an identical five-dimensional score vector.")
    expressions = [_norm(query["expression"]) for query in queries]
    if len(expressions) != len(set(expressions)):
        flag("duplicate_query", "error", "Search expressions repeat.")
    for query in queries:
        if not valid_query_expression(query["expression"], query.get("groups", [])):
            flag("invalid_query", "error", f"Invalid search query: {query['expression']}")
        if not query.get("static_validation", {}).get("passed", True):
            flag("query_static_validation", "error", f"Static query validation failed: {query['expression']}")
    for relation in relationships:
        if not relation.get("explanation"):
            flag("relationship_explanation", "warning", f"Relationship lacks an explanation: {relation['source']} → {relation['target']}")
        if relation["relation"] == "potential_transfer" and relation["verification_status"] != "unverified":
            flag("unverified_transfer", "error", "Potential transfer was marked as verified.")
    return {"passed": not any(item["severity"] == "error" for item in issues),
            "issues": issues, "keyword_count": len(keywords), "query_count": len(queries)}
