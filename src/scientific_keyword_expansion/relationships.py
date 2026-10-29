"""Check relation structure; semantic direction remains an Agent judgment."""

from __future__ import annotations

from typing import Any


LEGACY = {"broader_than", "narrower_than", "applied_to"}
DIRECTED = {"is_a", "part_of", "uses_method", "models", "evaluated_by", "potential_transfer"}


def review_relationships(edges: list[dict[str, Any]], keywords: list[dict[str, Any]],
                         normalize) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    nodes = {normalize(item["keyword"]): item for item in keywords}
    result: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    def flag(code: str, severity: str, message: str) -> None:
        issues.append({"code": code, "severity": severity, "message": message})

    for edge in edges:
        source, target, relation = normalize(edge["source"]), normalize(edge["target"]), edge["relation"]
        if source == target:
            flag("relationship_self_reference", "error", f"Self-reference: {edge['source']}")
            continue
        if source not in nodes or target not in nodes:
            flag("relationship_missing_node", "warning", f"Relationship endpoint not selected: {edge['source']} → {edge['target']}")
            continue
        key = (source, target, relation)
        if relation == "related_to":
            key = (min(source, target), max(source, target), relation)
        if key in seen:
            flag("relationship_duplicate", "warning", f"Duplicate relationship: {edge['source']} → {edge['target']} ({relation})")
            continue
        if relation in DIRECTED and (target, source, relation) in seen:
            flag("relationship_contradiction", "warning", f"Opposite directed relations need review: {edge['source']} ↔ {edge['target']}")
        if relation in LEGACY:
            flag("legacy_relationship", "warning", f"Legacy relation {relation} needs semantic migration: {edge['source']} → {edge['target']}")
        source_layer = nodes[source].get("layer")
        target_layer = nodes[target].get("layer")
        if relation == "uses_method" and source_layer == "method" and target_layer in {"subproblem", "core_concept"}:
            flag("possible_relation_reversal", "warning", f"Check uses_method direction: {edge['source']} → {edge['target']}")
        seen.add(key)
        result.append({"source": nodes[source]["keyword"], "target": nodes[target]["keyword"],
                       "relation": relation, "explanation": edge.get("explanation", ""),
                       "semantic_status": edge.get("semantic_status", "unreviewed"),
                       "verification_status": "unverified"})
    return result, issues
