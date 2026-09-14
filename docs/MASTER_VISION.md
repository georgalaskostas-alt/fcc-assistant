# Refinery AI Assistant — Master Vision & Guardrails

*Canonical project goal for architecture, development, and future reviews*

**Status:** Canonical reference for project direction

## 1. Mission

- Create a secure, highly autonomous AI assistant for the refinery environment, available on the workstation of each authorized user — from engineer to refinery manager.
- The assistant is not limited to FCC monitoring. FCC is the first proving ground. The long-term product is a refinery-wide AI work platform combining operational data, technical knowledge, engineering workflows, document intelligence, analysis, reporting, and autonomous multi-step task execution.

## 2. Primary users

- Process engineers, operations engineers, maintenance and reliability engineers, shift supervisors, area/unit managers, technical managers, and refinery management.
- The same platform must adapt its workspace, level of detail, permissions, tools, and summaries to the user’s role.

## 3. Core product pillars

- Operations Intelligence: read and analyze historian/PI/DCS-derived information, trends, KPIs, alarms/events, laboratory and production data where available.
- Technical Knowledge: search and understand P&IDs, PFDs, manuals, datasheets, procedures, studies, incident reports, inspection documents, HAZOP/MOC material, vendor documents, and other approved technical archive content.
- Engineering Work Assistant: perform investigations, comparisons, calculations, reporting, technical drafting, retrieval of related documents, historical case search, and multi-step engineering workflows.
- Controlled Engineering Editing: identify inconsistencies, create proposed corrections/redlines, support revision workflows, and prepare controlled document changes after engineer review and approval.
- Management Intelligence: refinery/unit summaries, production vs plan, major deviations, losses, constraints, open issues, and drill-down from management level to unit/equipment/tag level.
- Personal Workspace & Memory: preserve the user’s active investigations, dashboards, context, tasks, documents, and prior work so the assistant can continue work rather than restart from zero.

## 4. Assistant autonomy

- The target is an agentic assistant: the user gives a goal and the assistant can plan and execute a sequence of permitted actions using tools.
- Examples include selecting relevant tags, retrieving history, comparing periods, searching the technical archive, finding related incidents, generating trends, building a hypothesis, and drafting a report.
- The LLM is the reasoning/orchestration layer. Deterministic tools execute concrete actions. Permissions, validation, audit, and approval gates control what can actually happen.

## 5. Operational data and safety boundary

- Operational/process interfaces are read-only by default. The assistant may retrieve, analyze, compare, visualize, and explain process data.
- The assistant must not autonomously write to DCS/PLC/SIS, change setpoints, move valves, alter controller parameters, or perform closed-loop process control.
- Any future capability that affects the physical process would require a separate safety architecture, governance, approvals, and validation; it is outside the current product target.

## 6. Technical archive and document intelligence

- The assistant must understand the technical archive as structured engineering knowledge, not as a folder of PDFs.
- Documents should retain provenance and metadata such as document number, revision, date, unit, equipment, document type, page/source location, and approval status.
- Answers based on documents should be grounded in source material and, where practical, point the engineer to the exact document/revision/page.

## 7. P&ID and engineering-document correction workflow

- The assistant may detect potential errors or receive an explicit correction instruction from an engineer.
- Default controlled workflow: Approved Master → AI understanding → Proposed change / redline → Engineer review → Engineer approval → Controlled revision/output → Audit trail.
- The assistant must not silently overwrite an approved master engineering document.
- Initial implementation should prioritize redline/markup generation and revision comparison. Native CAD/DWG/DXF editing can be added later through suitable CAD integrations.
- The same controlled-editing concept may later cover PFDs, datasheets, line lists, instrument lists, procedures, control narratives, cause-and-effect documents, and technical notes.

## 8. Refinery semantic model

- The system must not depend only on raw tag names. It needs a semantic model of the refinery: site → unit → section → equipment → stream → measurement → relationships.
- This semantic layer should map real historian tags, equipment identifiers, documents, incidents, and engineering concepts so the assistant can reason about the plant rather than merely search strings.

## 9. Tools the AI should be able to use

- Operational tools: search tags, retrieve history, calculate averages/deltas, compare periods, trend data, detect deviations/anomalies, find correlations, and retrieve alarms/events where authorized.
- Knowledge tools: search documents, open a specific source, locate equipment documentation, compare revisions, find similar incidents, and retrieve approved procedures.
- Workspace tools: create/update dashboards, trends, KPIs, tables, reports, investigations, and saved workspaces.
- Engineering-document tools: create redlines, compare revisions, propose changes, generate change logs, and prepare approval packages.

## 10. Role-aware experience and permissions

- Each user sees only data, documents, functions, and organizational scope they are authorized to access.
- A process engineer may need detailed historian and technical-analysis tools; a maintenance engineer may need equipment history and vendor documentation; a manager may need high-level refinery KPIs with drill-down.
- Role-based access control, source permissions, approval rights, and audit logging are part of the product architecture, not optional add-ons.

## 11. Local / enterprise deployment principle

- Sensitive refinery data and technical documents should remain inside the approved enterprise environment.
- The intended architecture supports local/on-premises inference, local databases/indexes, local technical-archive retrieval, and controlled enterprise integrations.
- Public-cloud AI must not receive refinery process payloads or protected technical documents unless explicitly approved by the organization under a defined security model.

## 12. User experience

- The product is more than a chat window. It should combine conversational interaction with a dynamic workspace.
- The AI should be able to open and organize trends, KPIs, tables, documents, P&IDs, reports, sources, tasks, and investigations in response to the user’s goal.
- Natural language and, later, local speech-to-text should both be supported.

## 13. Current FCC implementation

- FCC Assistant is Phase 1 and the proving ground for the larger platform.
- Current work on conversational dashboard control, persistent context, deterministic actions, local AI, unit/tag semantics, and restart-safe state is foundational infrastructure for the refinery-wide product.
- Implementation choices made now should avoid assumptions that only work for one user, one unit, or one small tag set.

## 14. Roadmap

- Phase 1 — FCC Workspace: reliable desktop app, local backend/AI, dynamic workspace, conversational control, persistent context, semantic unit/tag model.
- Phase 2 — Real operational data: PI/historian connectivity, real tags, caching, statistics, permissions, auditability.
- Phase 3 — Technical Archive: ingestion, metadata, semantic retrieval, citations, equipment/document linking, revision awareness.
- Phase 4 — Autonomous Engineering Investigations: anomaly/deviation analysis, historical similarity, correlations, event reconstruction, report generation.
- Phase 5 — Controlled Engineering Editing: P&ID/PFD redlines, revision comparison, proposed corrections, approval workflow, audit trail, later CAD integration.
- Phase 6 — Refinery-wide rollout: more units, more roles, broader enterprise data sources, management intelligence, organization-scale deployment.

## 15. Non-negotiable design guardrails

- Do not reduce the project to an FCC chatbot or a fixed dashboard.
- Do not design around a single user, single unit, or hard-coded set of tags.
- Do not let the AI invent operational facts when data or sources are unavailable; uncertainty and missing evidence must be explicit.
- Do not permit silent destructive edits to approved engineering documents.
- Do not permit autonomous process-control writes under the current product scope.
- Every important AI action should be traceable to tools, data, documents, or explicit user instruction.
- Human approval is mandatory for controlled engineering-document revisions.

## 16. Canonical project statement

- Build a secure, highly autonomous, role-aware Refinery AI Assistant that runs in the approved enterprise environment and helps every authorized user — from engineer to refinery manager — monitor and understand operations, search and reason over the technical archive, conduct multi-step engineering investigations, create reports and workspaces, and propose controlled corrections to engineering documents, while maintaining strict permissions, provenance, auditability, human approval for controlled revisions, and a read-only boundary toward process control systems.

## 17. Review checklist — use this before major features

- Does this feature move us toward a refinery-wide assistant rather than only an FCC dashboard?
- Can it scale to many users, many units, large tag sets, and a large technical archive?
- Is the assistant sufficiently autonomous to reduce manual engineering work?
- Is the result grounded in real data/documents and traceable to sources?
- Are permissions, audit, and approval requirements explicit?
- Does it preserve the read-only process-control boundary?
- For engineering documents, does it use proposal/redline → review → approval → controlled revision?
- Does it strengthen the common platform rather than create a one-off implementation?
- Can both an engineer and a manager benefit from the same underlying architecture at different levels of detail?

---

**Review rule:** Re-read this document before major architectural or product decisions.
