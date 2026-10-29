# Research problem analysis

Build a field-specific problem map before proposing keywords. Record the map in `domain_analysis`; do not substitute a generic discipline taxonomy for the actual research question.

1. **Research object:** What system, material, dataset, device, process, or phenomenon is studied? Name the parts whose behavior matters.
2. **Scientific problem:** What outcome is being predicted, explained, designed, optimized, or measured? State it as a concrete question and identify the target output.
   Where applicable, identify inputs, controllable variables, loss functions, and a feasible experimental check; do not force an optimization formulation onto descriptive research.
3. **Constraints and mechanisms:** Identify governing physical laws, mathematical conditions, experimental limits, data limitations, and implementation constraints. Separate known facts from assumptions.
4. **Technical routes:** Map relevant theory, forward models, simulation, inverse/optimization methods, learning methods, experimental techniques, and evaluation metrics. Include only routes that genuinely address the problem.
5. **Field boundary:** For each nearby area, explain what it shares with the target problem and what differs. Reduce broad parent-field terms when the request is narrow.
6. **Transfer opportunities:** Explain the source field, the transferable mechanism, and the target constraint it might address. Label an unverified transfer as a hypothesis. Do not infer adoption from conceptual fit alone.

Use a compact knowledge structure: object → mechanism/constraint → subproblem → method → metric. A keyword should have a traceable place in this structure. The structure is dynamic: an experimental materials question and a machine-learning question will use different categories.

## Search concept decomposition

Create `search_concepts` as small groups before asking Python to generate queries. Each group has a stable `id`, one `role` (`research_object`, `research_problem`, `method`, `application_context`, `theory`, `adjacent_domain`), and 1–6 alternate `terms` that refer to the same search concept. The first term is preferred. Use separate groups for different concepts, even when they appear in the same user sentence. Do not place a compositional long topic in one quoted term. Treat a term used in two groups as a duplicate concept and consolidate it.

For a narrow project, identify the actual object, problem, and context first. Include a method group only if it is central to the research or to a deliberate exploratory query. Record the limits of the decomposition if the user's description is ambiguous.

Separate a method that shares an inverse-problem structure from one already shown to work on the target hardware or material. Similar equations do not imply identical physical constraints. Record this boundary in `domain_analysis` and mark an untested method link as `potential_transfer`.
