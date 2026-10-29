"""Strict input contract shared by the agent workflow and deterministic pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

TERM_TYPES = {"standard", "related", "exploratory"}
RELATIONS = {"is_a", "part_of", "uses_method", "models", "evaluated_by", "related_to", "potential_transfer",
             "broader_than", "narrower_than", "applied_to"}  # legacy input remains readable
LEVELS = {"high", "medium", "low"}
TERM_CLASSES = {"established_term", "general_academic_term", "descriptive_phrase", "exploratory_term"}
STRATEGIES = {"field_overview", "research_problem", "method_exploration", "literature_search"}
MODES = {"quick", "research"}
LANGUAGES = {"bilingual", "english", "chinese"}
DEPTHS = {"narrow", "balanced", "broad"}
SCORE_KEYS = {"direct_relevance", "term_accuracy", "coverage_potential", "cross_domain_value", "distinctiveness"}
LAYERS = {"core_concept", "theory", "method", "subproblem", "metric", "adjacent", "transfer"}
SEARCH_ROLES = {"research_object", "research_problem", "method", "application_context", "theory", "adjacent_domain"}


def _string(value: Any, name: str, *, required: bool = True) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    value = " ".join(value.split())
    if required and not value:
        raise ValueError(f"{name} cannot be empty")
    return value


def _strings(value: Any, name: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list")
    return [_string(item, f"{name} item") for item in value]


@dataclass
class Candidate:
    keyword: str
    chinese: str
    category: str
    term_type: str
    reason: str
    scores: dict[str, int]
    abbreviation: str = ""
    synonyms: list[str] = field(default_factory=list)
    concept_id: str = ""
    scope: str = "core"
    query_role: str = "problem"
    layer: str = "core_concept"
    focus_tags: list[str] = field(default_factory=list)
    score_reason: str = ""
    topic_relevance: str = ""
    search_utility: str = ""
    exploration_value: str = ""
    term_class: str = ""
    translation_note: str = ""
    verification_review: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Candidate":
        if not isinstance(raw, dict):
            raise ValueError("candidate must be an object")
        scores = raw.get("scores")
        if not isinstance(scores, dict) or set(scores) != SCORE_KEYS:
            raise ValueError(f"scores must contain exactly {sorted(SCORE_KEYS)}")
        if any(type(value) is not int or not 0 <= value <= 100 for value in scores.values()):
            raise ValueError("each score must be an integer from 0 to 100")
        term_type = _string(raw.get("term_type"), "term_type").lower()
        if term_type not in TERM_TYPES:
            raise ValueError(f"invalid term_type: {term_type}")
        scope = _string(raw.get("scope", "core"), "scope").lower()
        if scope not in {"core", "adjacent", "transfer"}:
            raise ValueError(f"invalid scope: {scope}")
        query_role = _string(raw.get("query_role", "problem"), "query_role").lower()
        if query_role not in {"problem", "method", "application"}:
            raise ValueError(f"invalid query_role: {query_role}")
        default_layer = "transfer" if scope == "transfer" else "adjacent" if scope == "adjacent" else "method" if query_role == "method" else "core_concept"
        layer = _string(raw.get("layer", default_layer), "layer").lower()
        if layer not in LAYERS:
            raise ValueError(f"invalid layer: {layer}")
        if scope == "transfer" and layer != "transfer":
            raise ValueError("transfer scope requires transfer layer")
        if layer == "transfer" and scope != "transfer":
            raise ValueError("transfer layer requires transfer scope")
        reason = _string(raw.get("reason"), "reason")
        assessments = {}
        for key in ("topic_relevance", "search_utility", "exploration_value"):
            value = _string(raw.get(key, ""), key, required=False).lower()
            if value and value not in LEVELS:
                raise ValueError(f"invalid {key}: {value}")
            assessments[key] = value
        term_class = _string(raw.get("term_class", ""), "term_class", required=False).lower()
        if term_class and term_class not in TERM_CLASSES:
            raise ValueError(f"invalid term_class: {term_class}")
        review = raw.get("verification_review", {})
        if not isinstance(review, dict):
            raise ValueError("verification_review must be an object")
        if review:
            if review.get("status") not in {"context_supported", "expert_reviewed"}:
                raise ValueError("verification_review status is invalid")
            _string(review.get("reason"), "verification_review reason")
            _string(review.get("evidence_url"), "verification_review evidence_url")
            if review["status"] == "expert_reviewed":
                _string(review.get("reviewer"), "verification_review reviewer")
        return cls(
            keyword=_string(raw.get("keyword"), "keyword"),
            chinese=_string(raw.get("chinese", ""), "chinese", required=False),
            category=_string(raw.get("category"), "category"),
            term_type=term_type,
            reason=reason,
            scores=dict(scores),
            abbreviation=_string(raw.get("abbreviation", ""), "abbreviation", required=False),
            synonyms=_strings(raw.get("synonyms", []), "synonyms"),
            concept_id=_string(raw.get("concept_id", ""), "concept_id", required=False),
            scope=scope,
            query_role=query_role,
            layer=layer,
            focus_tags=_strings(raw.get("focus_tags", []), "focus_tags"),
            score_reason=_string(raw.get("score_reason", reason), "score_reason"),
            term_class=term_class,
            translation_note=_string(raw.get("translation_note", ""), "translation_note", required=False),
            verification_review=review,
            **assessments,
        )


@dataclass
class Request:
    topic: str
    candidates: list[Candidate]
    focus: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    count: int = 50
    language: str = "bilingual"
    mode: str = "quick"
    depth: str = "balanced"
    cross_domain: bool = True
    search_queries: bool = True
    verify_terms: bool = False
    output_format: str = "markdown"
    domain_analysis: dict[str, Any] = field(default_factory=dict)
    relationships: list[dict[str, str]] = field(default_factory=list)
    search_concepts: list[dict[str, Any]] = field(default_factory=list)
    report_date: str = ""
    task_strategy: str = ""
    evaluate_queries: bool = True
    query_revision_rounds: int = 2
    previous_report: dict[str, Any] = field(default_factory=dict)
    revision_reason: str = ""
    query_relevance_labels: dict[str, bool] = field(default_factory=dict)
    query_label_source: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Request":
        if not isinstance(raw, dict):
            raise ValueError("input must be a JSON object")
        topic = _string(raw.get("topic"), "topic")
        count = raw.get("count", 50)
        if type(count) is not int or not 1 <= count <= 200:
            raise ValueError("count must be an integer from 1 to 200")
        language = _string(raw.get("language", "bilingual"), "language").lower()
        mode = _string(raw.get("mode", "quick"), "mode").lower()
        depth = _string(raw.get("depth", "balanced"), "depth").lower()
        output_format = _string(raw.get("output_format", "markdown"), "output_format").lower()
        if language not in LANGUAGES or mode not in MODES or depth not in DEPTHS:
            raise ValueError("invalid language, mode, or depth")
        if output_format not in {"markdown", "json", "csv", "all"}:
            raise ValueError("invalid output_format")
        for key in ("cross_domain", "search_queries", "verify_terms", "evaluate_queries"):
            if type(raw.get(key, key != "verify_terms")) is not bool:
                raise ValueError(f"{key} must be a boolean")
        if mode == "quick" and raw.get("verify_terms", False):
            raise ValueError("verify_terms requires research mode")
        candidates = raw.get("candidates")
        if not isinstance(candidates, list):
            raise ValueError("candidates must be a list generated by the host agent")
        domain_analysis = raw.get("domain_analysis", {})
        if not isinstance(domain_analysis, dict):
            raise ValueError("domain_analysis must be an object")
        relationships = raw.get("relationships", [])
        if not isinstance(relationships, list):
            raise ValueError("relationships must be a list")
        for edge in relationships:
            if not isinstance(edge, dict) or edge.get("relation") not in RELATIONS:
                raise ValueError("invalid relationship")
            _string(edge.get("source"), "relationship source")
            _string(edge.get("target"), "relationship target")
            if "explanation" in edge:
                _string(edge["explanation"], "relationship explanation")
            if edge.get("semantic_status", "unreviewed") not in {"unreviewed", "agent_reviewed", "uncertain"}:
                raise ValueError("invalid relationship semantic_status")
        search_concepts = raw.get("search_concepts", [])
        if not isinstance(search_concepts, list):
            raise ValueError("search_concepts must be a list")
        ids: set[str] = set()
        for concept in search_concepts:
            if not isinstance(concept, dict):
                raise ValueError("search concept must be an object")
            identity = _string(concept.get("id"), "search concept id")
            if identity.casefold() in ids:
                raise ValueError(f"duplicate search concept id: {identity}")
            ids.add(identity.casefold())
            if concept.get("role") not in SEARCH_ROLES:
                raise ValueError(f"invalid search concept role: {concept.get('role')}")
            terms = _strings(concept.get("terms"), "search concept terms")
            if not 1 <= len(terms) <= 6:
                raise ValueError("search concept needs 1–6 terms")
        report_date = _string(raw.get("report_date", ""), "report_date", required=False)
        if report_date:
            from datetime import date
            try:
                date.fromisoformat(report_date)
            except ValueError as error:
                raise ValueError("report_date must be YYYY-MM-DD") from error
        strategy = _string(raw.get("task_strategy", ""), "task_strategy", required=False).lower()
        if strategy and strategy not in STRATEGIES:
            raise ValueError("invalid task_strategy")
        rounds = raw.get("query_revision_rounds", 2)
        if type(rounds) is not int or not 0 <= rounds <= 2:
            raise ValueError("query_revision_rounds must be 0–2")
        previous = raw.get("previous_report", {})
        if not isinstance(previous, dict):
            raise ValueError("previous_report must be an object")
        labels = raw.get("query_relevance_labels", {})
        if not isinstance(labels, dict) or any(not isinstance(key, str) or type(value) is not bool
                                               for key, value in labels.items()):
            raise ValueError("query_relevance_labels must map DOI/URL strings to booleans")
        label_source = _string(raw.get("query_label_source", ""), "query_label_source", required=False)
        if label_source and label_source not in {"human_review", "agent_review"}:
            raise ValueError("invalid query_label_source")
        if labels and not label_source:
            raise ValueError("query_label_source is required when relevance labels are supplied")
        return cls(topic=topic, candidates=[Candidate.from_dict(item) for item in candidates],
                   focus=_strings(raw.get("focus", []), "focus"),
                   exclude=_strings(raw.get("exclude", []), "exclude"),
                   count=count, language=language, mode=mode, depth=depth,
                   cross_domain=raw.get("cross_domain", True),
                   search_queries=raw.get("search_queries", True),
                   verify_terms=raw.get("verify_terms", False),
                   output_format=output_format, domain_analysis=domain_analysis,
                   relationships=relationships, search_concepts=search_concepts,
                   report_date=report_date, task_strategy=strategy,
                   evaluate_queries=raw.get("evaluate_queries", True), query_revision_rounds=rounds,
                   previous_report=previous,
                   revision_reason=_string(raw.get("revision_reason", ""), "revision_reason", required=False),
                   query_relevance_labels=labels, query_label_source=label_source)


def to_dict(value: Any) -> dict[str, Any]:
    return asdict(value)
