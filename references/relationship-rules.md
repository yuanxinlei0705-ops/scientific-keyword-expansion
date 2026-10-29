# Keyword relationship directions

Use only relationships that help a researcher understand the topic or choose a search route. Both endpoints must be selected keyword nodes. Give a one-sentence scientific explanation and `semantic_status` (`agent_reviewed`, `uncertain`, or `unreviewed`). `agent_reviewed` describes a semantic Agent check, not literature verification.

| Relation | Direction of `source → target` |
|---|---|
| `is_a` | Source is a kind of target. |
| `part_of` | Source is a component of target. |
| `uses_method` | Source task or approach uses target method. |
| `models` | Source model describes target process or object. |
| `evaluated_by` | Source task or output is evaluated using target metric. |
| `related_to` | The concepts are connected, with no stronger directed claim. |
| `potential_transfer` | Source idea might transfer to target problem; target use remains unverified. |

Do not label a component as a subtype. For example, a waveguide may be `part_of` a photonic integrated circuit. An inverse-design task can `uses_method` an adjoint method; the reverse arrow would change the claim. Use `uncertain` if a domain specialist needs to check the connection. Python flags self-links, duplicate links, missing nodes, contradictory reverse directed links, and some layer-based direction suspicions. These are structural warnings, not a semantic proof.

Legacy `broader_than`, `narrower_than`, and `applied_to` remain readable for old input; revise them to the new vocabulary or `related_to` after reviewing their meaning.
