# Keyword quality and scoring

## Candidate distribution

Use seven flexible layers: `core_concept`, `theory`, `method`, `subproblem`, `metric`, `adjacent`, `transfer`. For a narrow problem, start around 40–50% direct concepts/subproblems, 25–35% mechanisms and methods, 10–20% adjacent topics, and 5–15% possible transfers. Adjust for the user's goal and the number of defensible terms. A broad survey can be wider; precision searching should be tighter. These are reasoning prompts, not quotas or permission to fill weak slots.

Create roughly 1.5–2 times the target count only when the field supports that many credible, distinct concepts. Reassess `scope`, `layer`, `scores`, and explanations for each narrower or broader request. A candidate that was core in a parent field may be adjacent in a focused problem. Do not copy scores or rationales across topics.

## Individual explanation

Write 1–3 sentences in the requested language that make the link to the research problem concrete: what the term means here, what object or constraint it addresses, and what type of literature it should find. For transfer methods, name the source mechanism and the target constraint while stating that adoption is unverified. Avoid repeating a sentence with the category name swapped in. The `reason` should stand on its own; `score_reason` should identify which evidence or relevance judgment most influenced its rating.

## Five-dimensional estimate

Rate each concept separately on a 0–100 scale:

- `direct_relevance` (35%): how directly this term addresses the stated object, problem, or constraint, not merely its parent discipline.
- `term_accuracy` (25%): confidence that the name represents the intended academic concept; uncertain coined phrases score lower and remain exploratory.
- `coverage_potential` (20%): estimated ability to retrieve a useful and distinct literature set. This is a prediction unless a database was queried.
- `cross_domain_value` (15%): value for connecting methods or explanations across fields; high value does not prove target-field adoption.
- `distinctiveness` (5%): whether the term adds a distinct search axis rather than rephrasing another candidate.

The weighted total is an Agent estimate, never a citation count. Use `relevance_level` and `score_reason` to keep the number in context. Do not assign one vector to an entire category. If the rationale is weak, lower confidence and flag review rather than inventing precision.

## Three distinct assessments

Provide `topic_relevance`, `search_utility`, and `exploration_value` separately as `high|medium|low` when possible. Topic relevance concerns the user's precise scientific question. Search utility concerns whether the wording is an effective, unambiguous literature handle. Exploration value concerns the benefit of adjacent methods or new hypotheses. A transferable algorithm may be high in exploration value but medium or low in topic relevance. Explain that difference in `score_reason`. The old weighted `relevance_score` remains for compatibility and is not a fourth literature metric. Missing new levels are derived from the old scores and marked as such.

For legacy candidates without explicit levels, the deterministic fallback uses `high` for a derived component at least 88, `medium` for 65–87, and `low` below 65. The thresholds prevent a broad weighted total from silently determining all three meanings; they do not constitute empirical calibration. For a field overview, favor established core concepts and theories; for a specific problem, favor direct variables, constraints, and metrics; for method exploration, give plausible transfers room; for literature preparation, favor accurate, searchable terminology. This changes selection priority, not the scientific meaning of a category.

## Review before export

Check field boundaries, missing mechanisms or metrics, terms with no clear search purpose, synonyms counted twice, template explanations, identical score vectors, inferred adoption claims, and questionable translations. Python detects mechanical errors and some warning signs; the Agent must resolve scientific meaning. If `quality_checks.passed` is false, revise candidates before presenting the report as final.
