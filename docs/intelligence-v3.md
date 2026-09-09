# Intelligence v3

Intelligence v3 develops the FCC Assistant from a dashboard command interface into a safer conversational operations copilot.

## Principles

- Process access remains read-only.
- The current user turn is authoritative; older dialogue context may help resolve references but may not override an explicit current request.
- Compound commands must be executed completely or rejected before dashboard mutation.
- Conversation context sent to the local planner is bounded and sanitized.
- The planner must not invent process units, measurements, widget IDs, or plant facts.
- Ambiguous changes are clarified instead of guessed.

## Implemented foundation

- Case-insensitive multi-action current-turn detection for Greek and English dashboard commands without classifying ordinary or empty questions as dashboard mutations.
- Greek (accented/unaccented) and English restore/add disambiguation, including compound restore + add requests.
- Common add/remove/replace synonyms are normalized into action families (`πρόσθεσε`, `βγάλε`, `διέγραψε`, `swap`, etc.).
- Complete-or-reject validation for compound remove/add and restore/remove requests.
- Action-family validation for add, remove, replace and restore execution plans, including cross-action mismatches and update mismatches.
- Restore is allowed only through its internal add-widgets execution representation; incompatible remove/update execution is rejected.
- Validation that explicit unit-scoped mutations resolve to concrete unit targets; unknown target IDs are rejected.
- Valid multi-unit requests can target combinations inside the units explicitly named by the user; targets outside that set are rejected.
- Protection against stale context redirecting an explicit current command to another unit.
- Context-based unit resolution remains allowed when the current turn intentionally omits the unit (`αφαίρεσε αυτό`).
- Explicit contextual references are allowed when they resolve to the unit named in the current turn (`αφαίρεσε αυτό από το FCC`).
- Bounded multilingual recent-turn context for the local planner with explicit field allowlists.
- Pending intent lists and removed-widget references are capped to prevent unbounded planner context.
- Safe scalar values are normalized to bounded text while nested/malformed values are dropped.
- Sanitized malformed action context, container shapes, and empty-state handling.
- Regression coverage for Greek/English compound commands, accented/unaccented restore phrases, action synonyms, read-only questions, empty commands, missing targets, wrong units, multi-unit targets, partial plans, action mismatches, and bounded context.

## Acceptance examples

- `Αφαίρεσε το feed από το FCC και βάλε feed στο HCU` -> both actions must be present before anything changes.
- `Ξαναβάλε το FCC feed και πρόσθεσε feed στο HCU` -> restore plus the separate add request must both be understood.
- `Bring back the FCC feed and add the HCU feed` -> restore and separate add are both preserved.
- `Βάλε τα πάλι πίσω και αφαίρεσε το HCU feed` -> restore and remove must both execute, otherwise reject.
- `Βάλε τα πάλι πίσω` / `Επανέφερε το FCC feed` / `Επαναφερε το FCC feed` / `Bring back the FCC feed` -> restore only, not a false new add request.
- `Τι βλέπω τώρα στο FCC;` / `Ποιο είναι το feed του FCC;` -> read-only questions are not treated as edit commands.
- A current FCC command whose plan targets HCU -> reject before dashboard mutation, even if old dialogue context mentioned HCU.
- `Αφαίρεσε αυτό` -> may use the last safe widget reference because the current turn does not contradict it.
- `Αφαίρεσε αυτό από το FCC` -> context may resolve `αυτό`, but the resolved target must actually belong to FCC.
- Explicit add/remove/replace requests cannot silently turn into a different dashboard action.
- `Επανέφερε ...` may compile to `add_widgets`, but cannot compile to remove/update.
- An explicit unit mutation cannot act on a widget ID that is absent from the current workspace.

## Next development scope

1. Conversation reference resolution across multiple turns (`αυτό`, `εκείνο`, `και στο HCU`, corrections).
2. Deterministic handling of common operator follow-ups before local-AI fallback.
3. Engineering question memory separated from dashboard-edit memory.
4. Evidence-backed engineering answers with explicit provenance and uncertainty.
5. Read-only PI Web API adapter configuration and health checks without process writes.
6. Scenario/diagnostic reasoning that distinguishes observation, correlation, hypothesis, and approved engineering knowledge.
