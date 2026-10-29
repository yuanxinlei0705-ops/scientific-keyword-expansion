# Terminology and selection rules

- Prefer phrases actually used by researchers. Do not form a novel phrase by joining appealing nouns and call it standard.
- Distinguish the term's legitimacy in its source field from evidence that it has been used in the target field.
- Keep abbreviations with the canonical phrase; do not count them separately.
- Treat synonyms as alternate searches, not extra concepts. Check whether apparent synonyms differ in objective, model, scale, or application before sharing a `concept_id`.
- Agent scores are estimates. Evaluate direct relation, likely terminological accuracy, likely retrieval coverage, cross-field value, and distinctiveness independently; include a concrete reason.
- Use a narrow scope for narrow requests and a wider, explicitly labeled adjacent set only when useful. If count cannot be met without padding, report a shortfall.
- When a translation is uncertain, leave `chinese` blank and describe the uncertainty in `reason`.
- Use `term_class` independently of relevance: `established_term` requires an evidence basis, `general_academic_term` is a recognizable wider-field expression, `descriptive_phrase` composes the present problem, and `exploratory_term` probes a hypothesis. In Quick Mode all classes remain unverified.
- Short uppercase abbreviations may be ambiguous across fields. Prefer a full name first in each search group and review actual hits before using an abbreviation alone. A static warning is a prompt to check, not proof of ambiguity.
