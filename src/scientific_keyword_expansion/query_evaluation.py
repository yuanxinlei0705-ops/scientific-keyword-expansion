"""Static query checks and bounded, explicitly approximate OpenAlex retrieval probes."""

from __future__ import annotations

import re
import os
from datetime import datetime, timezone
from typing import Any

from .queries import valid_query_expression


def static_validation(query: dict[str, Any]) -> dict[str, Any]:
    groups = query.get("groups", [])
    issues: list[str] = []
    if not valid_query_expression(query["expression"], groups):
        issues.append("invalid_boolean_structure")
    if len(groups) > 3:
        issues.append("too_many_concepts")
    if any(len(term.split()) > 7 for group in groups for term in group["terms"]):
        issues.append("long_exact_phrase")
    acronyms = sorted({term for group in groups for term in group["terms"]
                       if re.fullmatch(r"[A-Z]{2,4}", term)})
    if acronyms:
        issues.append("acronym_ambiguity_review")
    if len(groups) == 3 and query["kind"] not in {"focused", "review"}:
        issues.append("check_restrictiveness")
    return {"passed": not any(issue in {"invalid_boolean_structure", "too_many_concepts", "long_exact_phrase"}
                               for issue in issues), "issues": issues, "ambiguous_acronyms": acronyms,
            "platform_notes": {"generic_boolean": "canonical", "scopus": "field wrapper only; test in Scopus",
                               "web_of_science": "topic wrapper only; test in Web of Science",
                               "google_scholar": "approximate; AND omitted", "openalex": "plain-text approximation"}}


def _plain_search(groups: list[dict[str, Any]]) -> str:
    # OpenAlex `search` receives text, not this report's Boolean expression.
    return " ".join(group["terms"][0] for group in groups)


def _boolean_expression(groups: list[dict[str, Any]]) -> str:
    return " AND ".join(("(" + " OR ".join(f'"{term}"' for term in group["terms"]) + ")")
                        if len(group["terms"]) > 1 else f'"{group["terms"][0]}"' for group in groups)


def _abstract(index: dict[str, list[int]] | None) -> str:
    if not index:
        return ""
    return " ".join(word for _, word in sorted((position, word) for word, positions in index.items()
                                                 for position in positions))


def _probe(query: dict[str, Any], client: Any, groups: list[dict[str, Any]], sample_limit: int,
           labels: dict[str, bool], label_source: str) -> dict[str, Any]:
    params: dict[str, Any] = {"search": _plain_search(groups), "per_page": sample_limit}
    request_params = dict(params)
    if os.environ.get("OPENALEX_API_KEY"):
        request_params["api_key"] = os.environ["OPENALEX_API_KEY"]
    result: dict[str, Any] = {"platform": "openalex", "queried_at": datetime.now(timezone.utc).isoformat(),
                              "executed_params": {**params, **({"api_key": "[redacted]"} if "api_key" in request_params else {})},
                              "execution_equivalence": "plain_text_approximation",
                              "boolean_expression": _boolean_expression(groups),
                              "request_status": "failed", "retrieval_count": None, "sample_size": 0,
                              "query_coverage": None, "estimated_precision": None, "labelled_sample_size": 0,
                              "evaluation_method": "unlabelled_metadata_lexical_overlap", "sample": [], "error": ""}
    try:
        data = client.get("openalex", "https://api.openalex.org/works", request_params)
        rows = data.get("results", [])
        count = data.get("meta", {}).get("count")
        result["request_status"] = "success"
        result["retrieval_count"] = count if type(count) is int else None
        result["sample_size"] = len(rows)
        covered: set[int] = set()
        for row in rows:
            title = row.get("display_name") or ""
            abstract = _abstract(row.get("abstract_inverted_index"))
            corpus = f" {title} {abstract} ".casefold()
            matched = [index for index, group in enumerate(groups) if any(term.casefold() in corpus for term in group["terms"])]
            covered.update(matched)
            label_key = next((key for key in (row.get("doi"), row.get("id")) if key in labels), None)
            relevance_label = labels[label_key] if label_key else None
            result["sample"].append({"title": title, "doi": row.get("doi"), "url": row.get("id") or "",
                                     "publication_year": row.get("publication_year"),
                                     "matched_concept_ids": [groups[index]["id"] for index in matched],
                                     "relevance_label": relevance_label})
        result["query_coverage"] = round(len(covered) / len(groups), 3) if groups and rows else None
        human_labels = [item["relevance_label"] for item in result["sample"]
                        if item["relevance_label"] is not None]
        result["labelled_sample_size"] = len(human_labels)
        if label_source == "human_review" and human_labels:
            result["estimated_precision"] = round(sum(human_labels) / len(human_labels), 3)
            result["evaluation_method"] = "human_labelled_sample_fraction; not corpus precision"
        elif label_source == "agent_review" and human_labels:
            result["evaluation_method"] = "agent_labels_recorded; precision_not_estimated"
    except Exception as error:
        result["error"] = str(error)
    return result


def evaluate_live(query: dict[str, Any], client: Any, *, max_revisions: int = 2,
                  sample_limit: int = 5, context_groups: list[dict[str, Any]] | None = None,
                  relevance_labels: dict[str, bool] | None = None, label_source: str = "") -> dict[str, Any]:
    """Probe a query and relax one AND group at a time only when the API reports zero hits.

    No strict precision claim is possible without human relevance labels. The
    executed OpenAlex text is recorded because it is not Boolean-equivalent.
    """
    groups = list(query["groups"])
    labels = relevance_labels or {}
    history = [_probe(query, client, groups, sample_limit, labels, label_source)]
    for _ in range(max_revisions):
        previous = history[-1]
        if previous["request_status"] != "success":
            break
        if previous["retrieval_count"] == 0 and len(groups) > 1:
            groups = groups[:-1]
            reason = "Zero returned results; removed one AND concept group."
        elif previous["sample_size"] and previous["query_coverage"] == 0:
            context = next((group for group in (context_groups or [])
                            if group["role"] == "application_context" and group["id"] not in {item["id"] for item in groups}), None)
            if context is None or len(groups) >= 3:
                break
            groups = [*groups, context]
            reason = "Zero sampled lexical concept overlap; added one application-context group for review."
        else:
            break
        revised = _probe(query, client, groups, sample_limit, labels, label_source)
        revised["revision_reason"] = reason
        history.append(revised)
    return {"status": history[-1]["request_status"], "platform": "openalex",
            "query_history": history, "revision_count": len(history) - 1,
            "retrieval_count": history[-1]["retrieval_count"],
            "sample_size": history[-1]["sample_size"], "query_coverage": history[-1]["query_coverage"],
            "estimated_precision": history[-1]["estimated_precision"],
            "labelled_sample_size": history[-1]["labelled_sample_size"],
            "ambiguity_warning": bool(query["static_validation"]["ambiguous_acronyms"]),
            "review_warning": "Sampled metadata has zero lexical concept overlap; assess topical relevance manually."
                              if history[-1]["sample_size"] and history[-1]["query_coverage"] == 0 else "",
            "evaluation_method": history[-1]["evaluation_method"]}


def representative_indices(queries: list[dict[str, Any]], limit: int = 3) -> list[int]:
    chosen: list[int] = []
    for kind in ("focused", "method", "overview"):
        found = next((index for index, query in enumerate(queries)
                      if query["kind"] == kind and index not in chosen), None)
        if found is not None:
            chosen.append(found)
    return chosen[:limit]
