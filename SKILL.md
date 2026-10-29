---
name: scientific-keyword-expansion
description: Expand a scientific research topic into categorized, deduplicated bilingual search keywords, academic search queries, and optionally evidence-checked terms. Use for literature-search planning and research direction exploration; do not use for ordinary web keyword SEO.
---

# Scientific Keyword Expansion

Help a researcher build a defensible academic search vocabulary. The host Agent supplies domain reasoning and candidate concepts; the bundled Python package validates, filters, ranks, builds queries, verifies, and exports them. Python alone cannot infer a field from a topic string.

## Interpret the request

Extract `topic` (required), `focus`, `exclude`, `count` (default 50), `language` (default bilingual), `mode` (default quick), `depth` (default balanced), `cross_domain` (default true), and `search_queries` (default true) from ordinary language. Ask only if the core research problem is genuinely ambiguous. A request for literature verification selects research mode. Do not call research mode if the user or environment rules prohibit network access. Read [the candidate contract](references/candidate-contract.md) before generating input.

## Quick mode

1. Choose a `task_strategy`: `field_overview`, `research_problem`, `method_exploration`, or `literature_search`. Analyze the object, scientific problem, inputs and outputs, optimization variables when applicable, physical or mathematical constraints, methods, evaluation criteria, and feasible experimental checks. Build an object → constraint → subproblem → method → metric map. Read [research analysis guidelines](references/research-analysis-guidelines.md). Choose categories from this map; do not reuse a parent-field taxonomy for a narrow problem.
2. Decompose the user's topic into separate `search_concepts` for research object, problem, method, context, and relevant theory. Give each concept useful synonymous search terms. A compound topic sentence is not automatically a standard exact phrase. Check that no two groups represent the same concept.
3. Generate a surplus of distinct candidates when justified. Cover direct concepts, theory, methods, subproblems, metrics, adjacent work, and plausible transfers. For narrow topics favor direct problem terms; reduce broad background terms. Read [keyword quality and scoring](references/keyword-quality-guidelines.md). Reassess each candidate for `topic_relevance`, `search_utility`, and `exploration_value` separately. Keep the legacy five numeric dimensions for compatibility; they are estimates, not evidence of literature importance. Classify terminology independently as `established_term`, `general_academic_term`, `descriptive_phrase`, or `exploratory_term`; a Quick Mode established-term label is preliminary and still unverified.
4. Give each candidate a specific 1–3 sentence `reason` and concise `score_reason` in the requested language. Explain the scientific link and likely literature value; for transfers name the proposed mechanism and mark target adoption unverified. Keep abbreviations and synonyms with their canonical concept. Use `concept_id` only for expressions judged identical, never merely related.
5. Supply important relationships with an explanation and direction. `A uses_method B` means A uses B; `A part_of B` means A is a component of B. Use `related_to` when direction is unclear, and `semantic_status: uncertain` when the proposed meaning needs review. Read [relationship rules](references/relationship-rules.md). Expand excluded directions to known synonyms when preparing candidates and search concepts.
6. Save a JSON request conforming to [the contract](references/candidate-contract.md), then run `python -m scientific_keyword_expansion.cli --input INPUT.json --out OUTPUT_DIR`. Add `--formats markdown json csv` when all exports are needed. With source checkout, set `PYTHONPATH=src` or install using `pip install -e .` from this folder. For a traceable run add `--debug-log PATH --skill-loaded` only after actually reading this SKILL.md; the log calls this an Agent attestation, not independent proof.
7. Inspect `quality_checks`, warnings, query groups, focus coverage, the Research Search Brief, and count. Resolve error-level issues and review semantic warnings. Inspect abbreviation ambiguity and query breadth before searching. If credible concepts run short, report the shortfall; never pad. Present the generated Markdown and link to JSON/CSV when useful.

The legacy `relevance_score` is a weighted Agent estimate. `coverage_potential` is a prediction, never a literature count. If the three new levels are omitted for legacy input, Python derives them from the five scores and marks `assessment_basis: derived_from_legacy_scores`; provide independent levels when possible. Read [terminology rules](references/terminology-rules.md) for ambiguous terms and [query rules](references/search-query-rules.md) when adapting search syntax.

## Revise a previous report

When the user supplies a previous report and feedback, read the previous JSON and keep its sound candidates as a starting set. Apply preserve/remove requests explicitly; interpret focus changes in the analysis, scores, and search concepts. Reassess retained terms, add justified candidates, and run the full review again. Supply `previous_report` and `revision_reason` in the new input so Python records added, removed, and retained keywords. Keep the earlier file. The Agent interprets free-text feedback; Python does not convert it into scientific judgments.

## Research mode

Use the same candidate process with `mode: "research"`; call the CLI after confirming network access. `--providers openalex` can limit a run. It samples metadata from OpenAlex, Semantic Scholar, Crossref, and arXiv. `term_found` only means a phrase or synonym occurs in sampled title/abstract; `context_supported` and `expert_reviewed` require an explicit review citing a retrieved record. Failed search, no phrase match, and not checked have distinct states. Read [verification rules](references/verification-guidelines.md) before interpreting evidence. Research Mode also probes up to three representative queries through OpenAlex plain-text `search`; it records actual parameters and counts, but this is not Boolean-equivalent validation and cannot yield precision without relevance labels. Zero-hit queries may be relaxed at most twice (`query_revision_rounds` 0–2); before/after probes are retained. For many candidates, budget API traffic and time; narrow the input or use quick mode first.
Before a live run, use `scientific-keywords doctor` (or `python -m scientific_keyword_expansion.cli doctor` with `PYTHONPATH=src`) to test fresh DNS and HTTPS metadata responses from OpenAlex and Crossref. The command reports proxy environment, urllib's detected proxy, Windows Internet Settings, and categorized failures. If it fails inside Codex's network sandbox, compare the same command in the local terminal before attributing failure to the Skill. CLI options `--proxy-url`, `--timeout`, and `--retries` also apply to Research Mode; environment alternatives are `SKE_PROXY_URL`, `SKE_HTTP_TIMEOUT`, and `SKE_HTTP_RETRIES`. An explicit proxy URL must name an HTTP(S) proxy endpoint, typically `http://host:port` for a Clash HTTP/mixed port; SOCKS URLs are unsupported. Never disable SSL certificate verification. See [README diagnostics](README.md#api-连通性与代理诊断).
If the researcher supplies DOI/URL-keyed human relevance judgments, place them in `query_relevance_labels` with `query_label_source: human_review`; the report may then show only a labelled-sample fraction and its sample size. Never invent relevance labels or call this corpus-wide precision.

## Output and failures

By default `report.md` is written to the requested output directory. Select `output_format: "all"` or `--formats markdown json csv` to also write `report.json` and `keywords.csv`. CSV has a UTF-8 BOM for Excel. The JSON report follows [the report schema](schemas/keyword-report.schema.json). Platform query rendering is optional with `--platform generic_boolean|google_scholar|web_of_science|scopus|openalex`. OpenAlex output is a plain search string, not Boolean syntax. On invalid input, fix the specific validation error. On missing network evidence, report the failure plainly; do not convert an API search hit into exact-term proof. If fewer concepts qualify than requested, return the actual number and reason.

## Example requests

- “请围绕计算成像生成 30 个中英文科研关键词，并给出检索式。”
- “针对 DMD 无掩膜光刻中的二值图案优化，排除 EUV，优先考虑可迁移的优化方法。”
- “对 photonic devices 生成研究方向关键词，使用文献验证模式。”
