"""Build short, concept-level search strategies from an Agent's decomposition."""

from __future__ import annotations

import re
from typing import Any


def _norm(value: str) -> str:
    return " ".join(value.casefold().replace("–", "-").replace("—", "-").split())


def _compound(value: str) -> bool:
    words = value.split()
    return len(words) > 7 or (len(words) > 5 and bool(re.search(r"\b(and|for|using|with|via)\b", value, re.I)))


def _terms(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        value = " ".join(value.replace('"', "").split())
        key = _norm(value)
        if key and key not in seen and not _compound(value):
            seen.add(key)
            result.append(value)
    return result[:6]


def prepare_search_concepts(topic: str, keywords: list[dict[str, Any]],
                            supplied: list[dict[str, Any]] | None = None,
                            exclude: list[str] | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    """Use an explicit Agent decomposition; derive a conservative fallback for old input."""
    warnings: list[str] = []
    groups: list[dict[str, Any]] = []
    excluded = {_norm(item) for item in (exclude or [])}
    if supplied:
        source = supplied
    else:
        source = []
        # A simple, known field name can seed a broad search. Never quote a long
        # compositional user sentence merely because it was supplied as `topic`.
        if not _compound(topic) and any(_norm(topic) == _norm(item["keyword"]) for item in keywords):
            source.append({"id": "topic", "role": "application_context", "terms": [topic]})
        ranked = sorted(keywords, key=lambda item: -item["relevance_score"])
        for item in ranked:
            role = ("method" if item.get("query_role") == "method" or item.get("layer") == "transfer" else
                    "application_context" if item.get("query_role") == "application" else
                    "research_problem" if item.get("layer") == "subproblem" else "theory" if item.get("layer") == "theory" else "research_object")
            source.append({"id": f"keyword-{item['id']}", "role": role,
                           "terms": [item["keyword"], item.get("abbreviation", ""), *item.get("synonyms", [])]})
        warnings.append("Search concepts were inferred from candidate metadata; Agent review of topic decomposition is recommended.")

    seen_terms: set[str] = set()
    for item in source:
        terms = _terms(item["terms"])
        terms = [term for term in terms if not any(ex and (ex == _norm(term) or f" {ex} " in f" {_norm(term)} ") for ex in excluded)]
        if not terms:
            warnings.append(f"Search concept {item['id']} was omitted because its terms were compound or excluded.")
            continue
        fresh = [term for term in terms if _norm(term) not in seen_terms]
        if not fresh:
            warnings.append(f"Duplicate search concept omitted: {item['id']}")
            continue
        if len(fresh) != len(terms):
            warnings.append(f"Overlapping search variants removed from: {item['id']}")
        group = {"id": item["id"], "role": item["role"], "terms": fresh}
        groups.append(group)
        seen_terms.update(_norm(term) for term in fresh)
        if len(groups) >= 18:
            break
    return groups, warnings


def _expression(group: dict[str, Any]) -> str:
    terms = ['"' + term + '"' for term in group["terms"][:4]]
    return "(" + " OR ".join(terms) + ")" if len(terms) > 1 else terms[0]


def build_queries(groups: list[dict[str, Any]], keywords: list[dict[str, Any]],
                  limit: int = 16) -> list[dict[str, Any]]:
    if not groups:
        return []
    by_role: dict[str, list[dict[str, Any]]] = {}
    for group in groups:
        by_role.setdefault(group["role"], []).append(group)
    objects = by_role.get("research_object", [])
    contexts = by_role.get("application_context", [])
    problems = by_role.get("research_problem", [])
    methods = by_role.get("method", [])
    theories = by_role.get("theory", [])
    adjacent = by_role.get("adjacent_domain", [])
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()

    def add(kind: str, objective: str, proposed: list[dict[str, Any]]) -> None:
        if len(result) >= limit:
            return
        chosen: list[dict[str, Any]] = []
        terms_seen: set[str] = set()
        for group in proposed:
            if group["id"] in {item["id"] for item in chosen}:
                continue
            if any(_norm(term) in terms_seen for term in group["terms"]):
                continue
            chosen.append(group)
            terms_seen.update(_norm(term) for term in group["terms"])
            if len(chosen) == 3:
                break
        if not chosen:
            return
        signature = tuple(sorted(item["id"] for item in chosen))
        if signature in seen:
            return
        expression = " AND ".join(_expression(item) for item in chosen)
        if not valid_query_expression(expression, chosen):
            return
        seen.add(signature)
        result.append({"kind": kind, "objective": objective,
                       "concepts": [item["terms"][0] for item in chosen],
                       "groups": chosen, "logic": "OR within a concept; AND between distinct concepts",
                       "platform": "generic_boolean", "expression": expression})

    first = lambda values: values[:1]
    overview = first(objects) + first(contexts)
    if not overview:
        overview = first(problems) + first(theories)
    if not overview:
        overview = groups[:1]
    add("overview", "Broad field overview", overview)
    review_group = {"id": "review-literature", "role": "review", "terms": ["review", "survey"]}
    add("review", "Review literature", overview + [review_group])
    if problems:
        add("focused", "Research object, context and problem", first(objects) + first(contexts) + first(problems))
        add("core_problem", "Core research problem", first(contexts) + first(problems))
    add("application", "Application context", first(contexts))
    add("application", "Application and problem", first(contexts) + first(problems))
    for problem in problems[:3]:
        add("focused", "Specific research problem", first(objects) + [problem] + first(contexts))
    for method in methods[:4]:
        add("method", "Method for the research problem", first(problems or contexts or objects) + [method])
        add("method", "Method under application constraints", first(contexts or objects) + [method])
    for theory in theories[:2]:
        add("core_problem", "Physical or mathematical mechanism", first(objects or contexts) + [theory])
    transfer_names = {_norm(item["keyword"]) for item in keywords if item.get("scope") == "transfer"}
    for method in methods:
        if _norm(method["terms"][0]) in transfer_names:
            add("cross_domain", "Explore a potentially transferable method", first(adjacent or contexts or problems) + [method])
    for domain in adjacent[:2]:
        add("cross_domain", "Compare an adjacent domain", first(problems or objects) + [domain])
    return result[:limit]


def valid_query_expression(expression: str, groups: list[dict[str, Any]]) -> bool:
    """Validate our generated Boolean syntax and distinct concept groups."""
    if not 1 <= len(groups) <= 3:
        return False
    ids = [group["id"] for group in groups]
    if len(ids) != len(set(ids)):
        return False
    terms = [_norm(term) for group in groups for term in group["terms"]]
    if len(terms) != len(set(terms)):
        return False
    depth = 0
    for character in expression:
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth < 0:
                return False
    if depth != 0 or expression.count('"') % 2:
        return False
    if len(groups) == 1 and " AND " in expression:
        return False
    return expression.count(" AND ") == len(groups) - 1


def adapt_query(query: dict[str, Any], platform: str) -> str:
    expression = query["expression"]
    if platform == "generic_boolean":
        return expression
    if platform == "web_of_science":
        return f"TS=({expression})"
    if platform == "scopus":
        return f"TITLE-ABS-KEY({expression})"
    if platform == "google_scholar":
        return re.sub(r"\s+AND\s+", " ", expression)
    if platform == "openalex":
        return " ".join(group["terms"][0] for group in query.get("groups", [])[:2]) or " ".join(query["concepts"][:2])
    raise ValueError(f"unsupported platform: {platform}")
