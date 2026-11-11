# Refinery AI Assistant — Architecture Audit

> Review baseline: `docs/MASTER_VISION.md`
> Current implementation: FCC Assistant / `agent/workspace-v2`

## Purpose

This audit keeps implementation aligned with the long-term Refinery AI Assistant rather than optimizing only for the current FCC dashboard prototype.

## Executive assessment

The current FCC Assistant is a useful Phase-1 foundation, especially its local desktop/backend split, persistent dashboard state, conversational workspace actions, deterministic execution for concrete UI commands, and early unit/tag semantics. These components should be preserved.

The main architectural risk is allowing FCC-specific command handling and dashboard-specific dialogue state to become the central architecture. The refinery-wide product needs a generic agent/tool layer, refinery semantic model, source/permission model, knowledge/document subsystem, task/investigation model, and controlled engineering-document workflow.

## Keep and strengthen

### Local desktop + backend boundary
Keep the Tauri desktop client and local Python/FastAPI backend separation. It provides a practical base for workstation deployment and local/enterprise processing.

### Dynamic workspace
Keep the AI-controlled workspace concept. Trends, KPIs, tables, documents, reports and future investigation artifacts should become generic workspace resources rather than FCC-only widgets.

### Deterministic execution
Keep deterministic executors for concrete actions. The LLM should plan and orchestrate; validated tools should perform state-changing application actions.

### Persistent context
Keep restart-safe state, but evolve it from `last_widget` / `last_action_context` into user, session, task and investigation state.

### Read-only process boundary
Preserve read-only access toward historian/PI/DCS-derived operational data under the current product scope.

## Generalize now

### Unit model
Avoid hard-coding FCC/HCU behavior in conversational logic. Unit identity, equipment, streams, variables and relationships should come from a refinery semantic model.

### Widget/action vocabulary
Move toward generic tool contracts such as `create_trend`, `update_workspace_item`, `retrieve_history`, `search_documents`, `compare_periods`, and `create_report`. Natural-language variants should not require one-off application code indefinitely.

### State ownership
Current dashboard/dialogue JSON persistence is acceptable for the prototype, but refinery-wide deployment requires explicit identities for user, role, workspace, task/investigation and site scope.

### Agent orchestration
The agent should receive goals and select permitted tools. Fast deterministic parsing remains useful for trivial commands, but it must not become the only path for product intelligence.

## Missing platform capabilities

### Refinery Semantic Model
Create a canonical model for:

`site → area → unit → section → equipment → stream → measurement/tag`

It must support aliases, relationships, tag mappings, document links and source provenance.

### Source Registry
Every external source should have a registered connector, capability set, security classification and read/write policy. Initial examples: PI/historian, technical archive, alarm/event historian, LIMS and maintenance systems.

### Identity, RBAC and authorization
Introduce role-aware permissions before broad enterprise integrations. Authorization must be enforced by tools/backend, not merely by the LLM prompt.

### Technical Knowledge subsystem
Add document ingestion, metadata, revision/provenance tracking, semantic retrieval and citations. P&IDs and controlled engineering documents require first-class document identities and revision status.

### Investigation/Task model
Create durable multi-step tasks so an engineer can start an investigation, close the app, return later and continue. Tasks should record goal, evidence, tool calls, artifacts, hypotheses, conclusions and status.

### Audit/Event ledger
Important AI actions should be auditable: user instruction, plan, tool invocation, data/document source, generated artifact, approval and resulting change.

### Controlled Engineering Editing
Implement as a separate bounded subsystem:

`Approved Master → Proposed Change/Redline → Review → Approval → Controlled Revision → Audit`

Start with non-destructive redline/markup generation and revision comparison. Do not overwrite approved masters automatically.

## Target logical architecture

```text
Desktop / User Experience
        |
        v
Assistant / Agent Orchestrator
        |
        +---- Context & Task Memory
        +---- Refinery Semantic Model
        +---- Authorization / Policy
        |
        v
Validated Tool Layer
   |        |          |          |
   v        v          v          v
Operational Knowledge  Workspace  Engineering Docs
Data        Archive    & Reports  / Redlines
   |        |          |          |
PI/etc.   Documents   Local UI   Approval Workflow
```

The LLM reasons and orchestrates. Tools enforce schemas, permissions, source boundaries and deterministic execution.

## Recommended implementation sequence

### Foundation A — Architecture contracts
Define generic domain contracts for `UserContext`, `RefineryEntity`, `DataSource`, `ToolDefinition`, `Task/Investigation`, `Evidence`, `WorkspaceArtifact`, `DocumentReference`, `ProposedDocumentChange` and `Approval`.

### Foundation B — Semantic model
Move FCC/HCU definitions behind a generic refinery/site registry and keep current behavior working through adapters.

### Foundation C — Tool registry
Expose existing dashboard operations as validated tools and create a common tool execution/audit envelope.

### Foundation D — Durable task memory
Add durable investigations/tasks instead of relying only on conversational last-action state.

### Foundation E — Technical archive
Add document ingestion/retrieval with provenance and revision metadata.

### Foundation F — Redline workflow
Implement proposed redline artifacts, engineer approval and audit before considering native CAD modification.

### Foundation G — Enterprise scale
Add identity/RBAC, centralized policy, deployment/configuration, telemetry and multi-user/multi-unit scale controls.

## Immediate rule for current development

Do not stop fixing `workspace-v2`; reliable conversational workspace control remains necessary. But new features should be implemented behind generic contracts whenever practical, rather than adding more FCC-specific phrase branches.

## Architecture review gate

Before merging a major feature, answer:

1. Does it support the refinery-wide master vision?
2. Is domain knowledge represented as data/semantics rather than hard-coded phrases?
3. Can the capability be exposed as a validated tool to the agent?
4. Is source provenance retained?
5. Are authorization and read/write boundaries enforceable outside the LLM?
6. Is persistent task/context ownership clear?
7. Is the action auditable?
8. If an approved engineering document changes, is human approval mandatory?
9. Will the design still make sense with many users, units, tags and documents?

If several answers are no, redesign before extending the implementation.


## Evidence-based audit continuation — 2026-11-12 (A-001)

This section supplements the earlier architecture audit; the original strategic findings remain valid.

### Inventory and existing product vision
- Repository tree: **264 paths** at the inspected branch, including 78 backend test files, desktop React/Tauri, backend FastAPI, model/investigation/dashboard/knowledge/P&ID modules and CI.
- Existing `docs/MASTER_VISION.md` explicitly includes **Controlled Engineering Editing** and **Personal Workspace & Memory** in addition to engineering, operations, knowledge, investigations and management. These must be mapped into the seven-pillar product architecture as cross-cutting capabilities.
- Current source code is broad but presence does not prove end-to-end behavior or production maturity.

### CI finding — confirmed failure and code remediation
- GitHub Actions run **43113635879**, SHA `bc9c04a`: backend job **success**; desktop-web job **failure** at `npm run build`.
- TypeScript diagnostics: `PidIntelligenceView.tsx` invalid `unknown` category comparisons and missing `pending` in shadow review type; `pidDatasetZip.ts` `Uint8Array<ArrayBufferLike>` rejected as `BlobPart`.
- Fixes committed: `66309fd` and `311b238`. **Re-run status pending**; do not claim green build until GitHub CI confirms it.

### Runtime integration risk requiring verification
- `desktop/src/api.ts` points to port **18765**, whereas `scripts/dev-backend.sh` launches Uvicorn on **8000**. This may be intentional because Tauri uses an embedded backend on 18765. Inspect Tauri launch and sidecar implementation, then document supported developer modes; verify the VLM request uses the correct runtime route.
- `backend/app/main.py` registers the new P&ID vision router and `desktop_server.py` includes the desktop APIs. Ollama inference is **not verified**.

### Remaining A-001 work
1. Confirm current CI and local Tauri build, including packaging.
2. Trace startup paths, port/sidecar lifecycle and CORS.
3. Inspect actual API authorization and read-only enforcement.
4. Audit persistence, migrations, backup and data provenance.
5. Produce endpoint-to-UI-to-test traceability matrix and maturity rating per product pillar.
6. Validate one full, permissioned P&ID end-to-end.
