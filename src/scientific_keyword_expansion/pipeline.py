"""Deterministic selection, cautious deduplication, ranking, and query design."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import asdict
from datetime import date, datetime, timezone
from typing import Any

from .models import Candidate, Request
from .quality import review_quality
from .query_evaluation import evaluate_live, representative_indices, static_validation
from .queries import adapt_query, build_queries, prepare_search_concepts
from .relationships import review_relationships

WEIGHTS = {"direct_relevance": .35, "term_accuracy": .25, "coverage_potential": .20,
           "cross_domain_value": .15, "distinctiveness": .05}
TYPE_ORDER = {"standard": 0, "related": 1, "exploratory": 2}


def normalize(value: str) -> str:
    """Normalize typography without erasing meaningful scientific modifiers."""
    value = unicodedata.normalize("NFKC", value).casefold()
    value = re.sub(r"[‐‑‒–—−]", "-", value)
    value = re.sub(r"\s*([-/])\s*", r"\1", value)
    value = re.sub(r"[^\w\u3400-\u9fff/-]+", " ", value)
    return " ".join(value.split())


def score(candidate: Candidate) -> int:
    return round(sum(candidate.scores[key] * weight for key, weight in WEIGHTS.items()))


def _level(value: int) -> str:
    return "high" if value >= 88 else "medium" if value >= 65 else "low"


def _assessments(item: Candidate) -> dict[str, str]:
    values = {
        "topic_relevance": _level(item.scores["direct_relevance"]),
        "search_utility": _level(round((item.scores["term_accuracy"] + item.scores["coverage_potential"]) / 2)),
        "exploration_value": _level(round((item.scores["cross_domain_value"] + item.scores["distinctiveness"]) / 2)),
    }
    supplied = {key: getattr(item, key) for key in values}
    return {**{key: supplied[key] or value for key, value in values.items()},
            "assessment_basis": "agent_explicit" if all(supplied.values()) else "derived_from_legacy_scores"}


def _rank(item: Candidate, strategy: str) -> int:
    assessments = _assessments(item)
    levels = {"low": 1, "medium": 2, "high": 3}
    topic = levels[assessments["topic_relevance"]]
    utility = levels[assessments["search_utility"]]
    exploration = levels[assessments["exploration_value"]]
    if strategy == "literature_search":
        return 4 * utility + 2 * topic + exploration
    if strategy == "method_exploration":
        return 3 * exploration + 2 * topic + utility
    if strategy == "field_overview":
        return 3 * topic + 2 * utility + (2 if item.layer in {"core_concept", "theory"} else 0)
    return 4 * topic + utility + exploration


def _aliases(candidate: Candidate) -> set[str]:
    return {normalize(term) for term in [candidate.keyword, candidate.abbreviation, *candidate.synonyms] if term}


def deduplicate(candidates: list[Candidate]) -> tuple[list[Candidate], list[str]]:
    """Merge explicit same-concept IDs or exact canonical duplicates only.

    Alias collisions alone are flagged for review: related scientific concepts can
    share short names, so a similarity score is never authority to merge them.
    """
    groups: dict[str, Candidate] = {}
    canonical_keys: dict[str, str] = {}
    warnings: list[str] = []
    for candidate in candidates:
        canonical = normalize(candidate.keyword)
        key = canonical_keys.get(canonical) or (f"concept:{normalize(candidate.concept_id)}" if candidate.concept_id else f"name:{canonical}")
        if key not in groups:
            groups[key] = candidate
            canonical_keys[canonical] = key
            continue
        old = groups[key]
        winner, loser = sorted((old, candidate), key=lambda item: (TYPE_ORDER[item.term_type], -score(item), len(item.keyword)) )
        winner.synonyms = list(dict.fromkeys([*winner.synonyms, loser.keyword, loser.abbreviation, *loser.synonyms]))
        winner.synonyms = [item for item in winner.synonyms if item and normalize(item) != normalize(winner.keyword)]
        if not winner.chinese and loser.chinese:
            winner.chinese = loser.chinese
        groups[key] = winner
        canonical_keys[canonical] = key
        canonical_keys[normalize(winner.keyword)] = key
        if old.concept_id and normalize(old.keyword) != normalize(candidate.keyword):
            warnings.append(f"Agent-declared equivalent concepts merged: {old.keyword} / {candidate.keyword}")
    result = list(groups.values())
    for index, left in enumerate(result):
        for right in result[index + 1:]:
            if _aliases(left) & _aliases(right):
                warnings.append(f"Shared alias needs semantic review: {left.keyword} / {right.keyword}")
    return result, warnings


def _excluded(candidate: Candidate, exclusions: list[str]) -> bool:
    haystack = [candidate.keyword, candidate.category, candidate.chinese, *candidate.synonyms]
    def matches(term: str, item: str) -> bool:
        needle, corpus = normalize(term), normalize(item)
        if not needle:
            return False
        if re.search(r"[\u3400-\u9fff]", needle):
            return needle in corpus
        return f" {needle} " in f" {corpus} "
    return any(matches(term, item) for term in exclusions for item in haystack)


def _selection(candidates: list[Candidate], count: int, focus: list[str], depth: str,
               strategy: str) -> list[Candidate]:
    focus_terms = [normalize(item) for item in focus]

    def priority(item: Candidate) -> tuple[int, int, str]:
        signals = [normalize(item.keyword), *(normalize(tag) for tag in item.focus_tags)]
        focus_match = any(term == signal or (len(signal) >= 3 and f" {signal} " in f" {term} ")
                          for term in focus_terms for signal in signals)
        layer_bonus = {"core_concept": 5, "subproblem": 7, "theory": 2, "method": 3,
                       "metric": 2, "adjacent": -6, "transfer": -8}[item.layer]
        if depth == "narrow" and item.scope == "adjacent":
            layer_bonus -= 8
        adjusted = score(item) + _rank(item, strategy) + (14 if focus_match else 0) + layer_bonus
        return (-adjusted, TYPE_ORDER[item.term_type], item.keyword.casefold())

    by_category: dict[str, list[Candidate]] = defaultdict(list)
    for item in candidates:
        by_category[item.category].append(item)
    for values in by_category.values():
        values.sort(key=priority)
    categories = sorted(by_category, key=lambda category: priority(by_category[category][0]))
    selected: list[Candidate] = []
    # Narrow requests should not inherit every broad-field category.
    coverage_categories = categories[:5] if depth == "narrow" else categories
    for category in coverage_categories:
        if len(selected) < count:
            selected.append(by_category[category].pop(0))
    remaining = sorted((item for values in by_category.values() for item in values), key=priority)
    transfer_floor = 1 if depth == "narrow" else max(1, count // 15)
    for item in remaining:
        if len(selected) >= count or sum(x.scope == "transfer" for x in selected) >= transfer_floor:
            break
        if item.scope == "transfer":
            selected.append(item)
    adjacent_floor = 1 if depth == "narrow" else max(1, count // 12)
    for item in remaining:
        if len(selected) >= count or sum(x.scope == "adjacent" for x in selected) >= adjacent_floor:
            break
        if item.scope == "adjacent" and item not in selected:
            selected.append(item)
    transfer_limit = max(1, round(count * (.15 if depth == "narrow" else .2)))
    adjacent_limit = max(1, round(count * (.2 if depth == "narrow" else .3)))
    for item in remaining:
        if len(selected) >= count:
            break
        if item in selected:
            continue
        if item.scope == "transfer" and sum(x.scope == "transfer" for x in selected) >= transfer_limit:
            continue
        if item.scope == "adjacent" and sum(x.scope == "adjacent" for x in selected) >= adjacent_limit:
            continue
        selected.append(item)
    if len(selected) < count:
        for item in remaining:
            if len(selected) >= count:
                break
            if item not in selected:
                selected.append(item)
    return sorted(selected, key=lambda item: (-_rank(item, strategy), -score(item), item.keyword.casefold()))


def build_report(raw: dict[str, Any], verifier: Any = None) -> dict[str, Any]:
    request = Request.from_dict(raw)
    warnings: list[str] = []
    if not request.candidates:
        warnings.append("No agent-generated candidates supplied; topic-only inference is unavailable in the Python pipeline.")
    eligible = [item for item in request.candidates if not _excluded(item, request.exclude)]
    if not request.cross_domain:
        eligible = [item for item in eligible if item.scope != "transfer"]
    unique, dedup_warnings = deduplicate(eligible)
    warnings.extend(dedup_warnings)
    strategy = request.task_strategy or ("research_problem" if request.depth == "narrow" else "field_overview")
    selected = _selection(unique, request.count, request.focus, request.depth, strategy)
    if len(selected) < request.count:
        warnings.append(f"Only {len(selected)} distinct eligible concepts for requested {request.count}; no filler terms added.")
    keywords: list[dict[str, Any]] = []
    for index, item in enumerate(selected, 1):
        entry = asdict(item)
        value = score(item)
        assessments = _assessments(item)
        level = assessments["topic_relevance"]
        term_class = item.term_class or ("exploratory_term" if item.term_type == "exploratory" else
                                         "descriptive_phrase" if item.term_type == "related" else "general_academic_term")
        entry.update(id=index, relevance_score=value, relevance_level=level,
                     score_basis="agent_estimate", priority=level,
                     term_class=term_class, term_class_basis="agent_estimate" if item.term_class else "legacy_mapping",
                     **assessments,
                     verification_status="not_checked", verification_checked_at=None,
                     verification_sources=[], verification_attempts=[], research_status="unverified", evidence=[])
        keywords.append(entry)
    if request.mode == "research":
        if verifier is None:
            from .verification import Verifier
            verifier = Verifier()
        for entry in keywords:
            try:
                evidence, errors = verifier.verify(entry["keyword"], [entry["abbreviation"], *entry["synonyms"]])
                entry["evidence"] = evidence
                entry["verification_checked_at"] = datetime.now(timezone.utc).isoformat()
                attempts = getattr(verifier, "last_attempts", [])
                entry["verification_attempts"] = attempts
                entry["verification_sources"] = sorted({source for item in evidence for source in item.get("sources", [item["source"]])})
                entry["verification_status"] = ("term_found" if any(x["match_type"] in ("exact_phrase", "synonym") for x in evidence)
                                                else "search_failed" if (attempts and all(x["status"] == "failed" for x in attempts)) or (not attempts and errors and not evidence)
                                                else "searched_no_match")
                review = entry.get("verification_review") or {}
                if review and entry["verification_status"] == "term_found":
                    cited = next((paper for paper in evidence if review["evidence_url"] in {paper.get("url"), paper.get("doi")}), None)
                    if cited:
                        entry["verification_status"] = review["status"]
                        entry["verification_review_reason"] = review["reason"]
                        cited["context_assessment"] = review["status"]
                        cited["relevance_reason"] = review["reason"]
                        if review.get("reviewer"):
                            cited["reviewer"] = review["reviewer"]
                    else:
                        warnings.append(f"Verification review for {entry['keyword']} did not cite a retrieved record.")
                # A few metadata hits cannot establish the maturity of a research direction.
                entry["research_status"] = "unverified"
                warnings.extend(errors)
            except Exception as error:
                entry["verification_checked_at"] = datetime.now(timezone.utc).isoformat()
                entry["verification_status"] = "search_failed"
                warnings.append(f"Verification failed for {entry['keyword']}: {error}")
        if not any(item["evidence"] for item in keywords):
            warnings.append("Research mode found no usable evidence; all terms remain unverified.")
    relationships, relationship_issues = review_relationships(request.relationships, keywords, normalize)
    concepts, concept_warnings = (prepare_search_concepts(request.topic, keywords,
                                                          request.search_concepts, request.exclude)
                                  if request.search_queries or request.search_concepts else ([], []))
    warnings.extend(concept_warnings)
    queries = build_queries(concepts, keywords) if request.search_queries else []
    priority_map = {"focused": 1, "core_problem": 1, "overview": 1,
                    "method": 2, "review": 2, "application": 2, "cross_domain": 3}
    expected_map = {"focused": "papers on the specific research problem",
                    "core_problem": "problem formulations and constraints",
                    "overview": "field overviews and representative studies",
                    "method": "method and algorithm papers",
                    "review": "review and survey papers",
                    "application": "application studies", "cross_domain": "transferable ideas from adjacent fields"}
    for query in queries:
        query["static_validation"] = static_validation(query)
        query["priority"] = priority_map[query["kind"]]
        query["expected_papers"] = expected_map[query["kind"]]
        query["recommendation_reason"] = ("Combines distinct concepts for the stated search objective; "
                                          "review actual results before treating it as effective.")
        query["live_evaluation"] = None
    if request.mode == "research" and request.evaluate_queries and queries:
        provider_names = {provider.name for provider in getattr(verifier, "providers", [])}
        if "openalex" in provider_names:
            for index in representative_indices(queries):
                queries[index]["live_evaluation"] = evaluate_live(
                    queries[index], verifier.client, max_revisions=request.query_revision_rounds,
                    context_groups=concepts, relevance_labels=request.query_relevance_labels,
                    label_source=request.query_label_source)
                if queries[index]["live_evaluation"]["status"] == "failed":
                    error = queries[index]["live_evaluation"]["query_history"][-1]["error"]
                    warnings.append(f"Live query probe failed for {queries[index]['kind']}: {error}")
        else:
            warnings.append("Live query evaluation requires an OpenAlex provider; no query was executed.")
    quality = review_quality(keywords, queries, relationships, request.count, request.language,
                             extra_issues=relationship_issues)
    warnings.extend(f"{item['code']}: {item['message']}" for item in quality["issues"])
    best_queries = []
    for kind in ("focused", "method", "overview", "cross_domain", "review"):
        choice = next((item for item in queries if item["kind"] == kind and item not in best_queries), None)
        if choice:
            best_queries.append(choice)
    best_queries = best_queries[:5]
    verify_order = sorted(keywords, key=lambda item: (item["term_class"] not in {"descriptive_phrase", "exploratory_term"},
                                                     item["verification_status"] not in {"search_failed", "searched_no_match"},
                                                     item["id"]))
    layer_order = {"core_concept": 0, "subproblem": 1, "theory": 2, "metric": 3,
                   "method": 4, "adjacent": 5, "transfer": 6}
    brief_order = sorted(keywords, key=lambda item: ({"high": 0, "medium": 1, "low": 2}[item["topic_relevance"]],
                                                     layer_order.get(item["layer"], 7),
                                                     {"high": 0, "medium": 1, "low": 2}[item["search_utility"]],
                                                     -item["relevance_score"]))
    brief = {"research_problem": request.domain_analysis.get("research_problem", request.topic),
             "priority_keywords": [item["keyword"] for item in brief_order[:10]],
             "priority_queries": [item["expression"] for item in best_queries],
             "main_directions": list(dict.fromkeys(item["category"] for item in keywords))[:5],
             "terms_needing_verification": [item["keyword"] for item in verify_order
                                          if item["verification_status"] in {"not_checked", "searched_no_match", "search_failed"}
                                          or item["term_class"] in {"descriptive_phrase", "exploratory_term"}][:10],
             "transfer_opportunities": [item["keyword"] for item in keywords if item["scope"] == "transfer"][:5]}
    previous_names = {normalize(item["keyword"]): item["keyword"] for item in request.previous_report.get("keywords", [])
                      if isinstance(item, dict) and item.get("keyword")}
    current_names = {normalize(item["keyword"]): item["keyword"] for item in keywords}
    revision = ({"added_keywords": [name for key, name in current_names.items() if key not in previous_names],
                 "removed_keywords": [name for key, name in previous_names.items() if key not in current_names],
                 "retained_keywords": [name for key, name in current_names.items() if key in previous_names],
                 "revision_reason": request.revision_reason}
                if request.previous_report else None)
    return {"topic": request.topic, "focus": request.focus, "exclude": request.exclude,
            "requested_count": request.count, "generated_count": len(keywords), "mode": request.mode,
            "task_strategy": strategy,
            "language": request.language, "generated_at": request.report_date or date.today().isoformat(),
            "domain_analysis": request.domain_analysis, "keywords": keywords,
            "search_concepts": concepts, "search_queries": queries,
            "relationships": relationships, "quality_checks": quality,
            "research_search_brief": brief, "revision": revision,
            "warnings": list(dict.fromkeys(warnings))}
