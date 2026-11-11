# FCC Assistant — Master Vision, Product Strategy & Delivery Ledger

**Document owner:** Product / Engineering leadership  
**Version:** 1.0 | **Baseline date:** 2026-11-12  
**Repository:** `georgalaskostas-alt/fcc-assistant` | **Tracking branch:** `agent/workspace-v2`  
**Status:** Living product charter; **not** evidence of production readiness.

> **Mission:** Build an evidence-grounded Industrial Intelligence Platform that understands the physical plant, observes operating behavior through authorized data sources, investigates problems, supports engineering analysis, preserves institutional knowledge, trains personnel and informs management. FCC is the first proving ground; the architecture must generalize to other refinery units and industrial sites.

## 1. Product north star

A process engineer can open an unfamiliar P&ID, obtain correctly located and tagged symbols, inspect a validated connectivity graph, link those assets to historian signals and documents, ask technically meaningful questions, launch bounded investigations, and obtain traceable answers with explicit uncertainty. No unsupported claim may masquerade as verified engineering fact.

The system is an **engineering decision-support platform**, not an autonomous process controller. The ultimate market is industrial organizations, beginning with FCC/refining and extending to adjacent process industries after evidence-based validation.

### Non-negotiable principles
1. **Evidence before eloquence:** every engineering conclusion links to drawing region, revision, historian window, document citation, computation or human approval.
2. **Human authority:** engineering verification, safety-critical conclusions and operating changes remain under authorized personnel.
3. **OT boundary:** historian/DCS connectivity is initially read-only, explicitly authorized, segmented and audited. No automatic setpoint or actuator writes.
4. **Data governance:** company drawings, PI data, procedures and operating history may be confidential; no cloud uploads or model training without contractual and IT/OT approval.
5. **Measured quality:** test on held-out source drawings, distinct units and difficult cases; report precision, recall, exact-tag accuracy, graph edge accuracy, hallucination rate and human review time.
6. **Reproducible knowledge:** versions, source IDs, approvals, model versions, provenance, backup/restore, audit trail and regression tests.
7. **Model portability:** local VLM, hosted enterprise inference and specialized detectors behind replaceable interfaces; select by benchmarks and deployment constraints.
8. **No false progress:** a committed file, visible button, passing unit test, end-to-end demonstration and industrial acceptance are different maturity states.

## 2. Seven product pillars

| ID | Pillar | Intended user value | Target capability | Current evidence and gap |
|---|---|---|---|---|
| P1 | Engineering Intelligence | Turn P&ID/PFD into structured plant knowledge | Symbol detection, tag reading, line topology, off-page connectors, drawing revisions, graph query | Viewer, annotation/review, OCR, geometry and graph modules exist; demonstrated two approved tags and local restoration. Whole-drawing accuracy and graph correctness **not established**. |
| P2 | Live Process Intelligence | Understand present/historical behavior | Authorized PI/historian integration, tag-to-equipment mapping, trend/quality checks, process state | `pi_client.py`, `tag_registry.py`, `refinery_intelligence_api.py` exist. Production historian integration **not verified**. |
| P3 | Autonomous Investigation | Reduce time to credible diagnoses | Bounded hypothesis generation, evidence gathering, competing explanations, traceable report, resume | Investigation modules and tests exist. Accuracy on live engineering incidents **not verified**. |
| P4 | Process Engineering & Optimization | Quantify process behavior and opportunities | Balances, KPIs, soft sensors, constrained scenario evaluation, validated predictive models | Analytics/simulator/process modules exist. Real plant predictive performance **not verified**. |
| P5 | Technical Knowledge & Memory | Preserve approved engineering know-how | Versioned document archive, semantic asset links, provenance, approval and knowledge lifecycle | Archive/document/knowledge modules and local approved P&ID IndexedDB exist. Durable enterprise knowledge store and backup **not verified**. |
| P6 | Training & Operational Simulation | Teach operators and engineers using plant-specific context | Interactive circuits, grounded explanations, training scenarios, competency checks, validated simulation | Simulator and site-simulator modules exist. Training efficacy and simulation fidelity **not verified**. |
| P7 | Management & Decision Intelligence | Convert plant evidence into operational priorities | Cross-unit KPIs, reliability/energy views, executive briefs, opportunity tracking | Dashboard/management modules exist. Business KPI accuracy and executive pilot **not verified**. |

**Integration rule:** these are seven views of **one shared plant identity and evidence model**, not seven isolated chatbots.

## 3. Shared industrial intelligence core

**Canonical entities:** Site, Unit, Equipment, Nozzle/Port, Instrument, ControlLoop, Valve, PipeSegment, LineNumber, Junction, OffPageConnector, Document, DrawingRevision, HistorianTag, TimeSeriesWindow, OperatingEvent, Investigation, Hypothesis, Evidence, Calculation, Approval, ModelVersion.

**Required relations:** `connected_to`, `located_on`, `measures`, `controls`, `belongs_to`, `documented_by`, `supersedes`, `observed_in`, `supports`, `contradicts`, `approved_by`.

**Evidence contract:** every extracted entity or inferred edge carries source drawing/revision/page, bounding box or line geometry, extraction method/model version, confidence or uncertainty, review state, timestamp and provenance. **Confidence is not a substitute for verification.**

**Engineering knowledge tiers:** (1) raw source; (2) machine proposal; (3) human-verified plant fact; (4) analytical hypothesis; (5) approved engineering conclusion. Never silently promote one tier to another.

**Deployment:** existing Tauri/React desktop and FastAPI service retained initially; later add governed identity, durable database, searchable documents, graph store (PostgreSQL relational graph acceptable initially), object storage, model registry, monitoring and RBAC. IndexedDB is a local cache, not an enterprise system of record.

## 4. P&ID Intelligence Engine — technical execution

1. **Input & quality:** source PDF/vector extraction when available; raster images; image rectification, tiling, orientation and resolution metadata.
2. **Vision proposals:** benchmark multiple vision-language models on held-out drawings. VLM output is an unverified semantic hypothesis.
3. **Specialized symbol detection:** detect instruments, valves, equipment, line breaks, connectors, junctions and ports with a trained detector; return precise boxes/masks.
4. **OCR and semantic parsing:** technical tag grammar, instrument/line number distinction, symbol-to-text assignment, multilingual/rotated text, confidence calibration.
5. **Geometry and topology:** vector tracing where possible, raster line segmentation otherwise, distinguish crossings from connections, route through valves and equipment ports, resolve off-page continuation.
6. **Graph reconstruction:** typed nodes/edges, topology validation, source evidence and revision awareness. No unverified isolation claim.
7. **Review by exception:** visual overlay with transparent boxes, uncertainty queues, bulk inspection, human approval, change log.
8. **Learning loop:** engineer-approved annotations → versioned dataset → training → held-out evaluation → controlled model release and rollback.
9. **Engineering questions:** graph-grounded retrieval and LLM reasoning; always point back to diagram evidence.

**Critical test cases:** dashed signal lines, process pipes, crossing without junction, branch junction, valve at elbow, overlapping text, PRV and instrument bubbles, tiny symbols, rotated tags, page seams, repeated tags, multiple drawings of one source.

## 5. Product roadmap and acceptance gates

| Phase | Scope | Exit gate | Status |
|---|---|---|---|
| G0 — Baseline & audit | Inventory repo, runnable build, tests, dependency/security review, current demo recordings | Signed-off feature inventory with evidence and known failures | **In progress / incomplete** |
| G1 — Engineering benchmark | Representative permissioned P&IDs; gold-standard symbols, tags, edges; VLM/OCR/detector comparison | Reproducible benchmark with held-out drawings, failure taxonomy | **Not demonstrated** |
| G2 — Symbol & tag engine | Detection, OCR, association, review, export | Targets: ≥95% instrument precision/recall and exact tag accuracy on defined pilot set; measured, not assumed | **Prototype components only** |
| G3 — Connectivity graph | Typed edges, crossings, junctions, off-page links, versioning | Target ≥98% edge precision on defined test set; all safety-sensitive paths require review | **Prototype components only** |
| G4 — Engineering Copilot | Graph/document-grounded Q&A, citations, abstention | No unsupported critical claims in pilot acceptance suite; audited answer provenance | **Not demonstrated** |
| G5 — Live intelligence | Authorized read-only PI integration, asset-tag binding, quality checks | Secure integration and accurate, replayable trend analysis | **Not demonstrated** |
| G6 — Investigations & analytics | Bounded investigations, process calculations, model validation | Reproducible real-case evaluations and engineer sign-off | **Prototype components only** |
| G7 — Training and management | Training content, simulation validation, KPIs, dashboards | User studies, measured utility and data reconciliation | **Prototype components only** |
| G8 — Industrial pilot | Security, RBAC, backups, monitoring, IP/data agreements, user training | Written acceptance by authorized customer stakeholders | **Not started** |

Targets above are **aspirational acceptance criteria**, not current measurements. Sequence and durations must be estimated after G0/G1; a 20-week pilot is a planning scenario, not a commitment.

## 6. Current verified baseline — 2026-11-12

### Directly observed in collaboration
- Dataset Manager paired `IMG_5397.JPG` and `IMG_5446.JPG` with YOLO label files: **2 valid pairs, 7 total annotations, 0 structural errors/warnings** in the displayed validation screen. This validates label structure only, **not** annotation correctness.
- P&ID `IMG_5397.JPG`: `TI-544` and `TI-545` were engineer-approved. UI displayed **“Restored previously approved drawing from local engineer memory.”** Local persistence/restore demonstrated on user's installation.
- Local OCR scan generated irrelevant candidate tags (`NOTE8`, `RV-505`, `A3`, `A8`, `M10`) and failed to produce comprehensive instrument recognition. **This is a known failed approach for whole-P&ID understanding.**
- A local VLM integration (`backend/app/pid_vision.py` and desktop action) was committed. **No successful local build, model inference, accuracy benchmark or end-to-end validation has been provided.**

### Repository presence (not runtime verification)
- Backend contains `pid_intelligence.py`, `pid_geometry.py`, `pid_graph.py`, `pid_topology.py`, `pid_vision.py`, `pi_client.py`, `autonomous_investigation.py`, `process_analytics.py`, `simulator.py`, `technical_archive.py`, `unit_knowledge.py`, `management_brief.py` and numerous investigation/dashboard modules.
- Tests exist in `backend/tests/`; presence alone does **not** establish they pass on the current branch.
- CI workflow exists at `.github/workflows/ci.yml`; current run status **not checked**.
- Current project maturity: **multi-module prototype / engineering workbench**. No defensible overall percentage complete until G0 inventory and a weighted, evidence-based scorecard.

### Known immediate risks
- P&ID OCR confuses text labels with instruments.
- A generic VLM can hallucinate topology or tags; must not be trusted as a connectivity authority.
- Existing knowledge is partly local IndexedDB, without confirmed enterprise backup/restore.
- Drawing rights, customer IP, security boundaries and authorization for actual refinery data must be resolved.
- End-to-end builds, runtime integration, benchmarks, OT security and industrial reliability are not yet demonstrated.
- Prior code changes were sometimes committed without local build/test evidence; this must change.

## 7. Immediate execution backlog — prioritized

| ID | Priority | Work package | Deliverable | Evidence required |
|---|---|---|---|---|
| A-001 | P0 | Full repository technical audit | Modules/endpoints/UI/test matrix; dead code, duplicate paths, build blockers | File-level inventory and actual build/test logs |
| A-002 | P0 | Verify current VLM integration | Working Mac local inference and safe API transport; error handling | End-to-end run on permitted sample image |
| A-003 | P0 | Define gold benchmark | Permissioned images, independently reviewed symbol/tag/edge ground truth, source-drawing split | Dataset manifest, annotation quality review |
| A-004 | P0 | Canonical engineering schema | Versioned entities, typed connections, evidence, revision, review state | Schema tests and migration design |
| A-005 | P0 | Secure knowledge backup | Export/import of approved annotations and source provenance | Round-trip restore test |
| A-006 | P1 | Benchmark VLM/OCR/detector | Error analysis and selected architecture | Precision/recall/latency/cost report |
| A-007 | P1 | Specialized symbol detector | Multi-class instrument/valve/equipment/connector inference | Held-out evaluation |
| A-008 | P1 | Circuit geometry engine | Junction/crossing/port/off-page detection | Edge-level validation suite |
| A-009 | P1 | Graph-grounded copilot | Question → graph traversal → cited answer | No unsupported answer on acceptance set |
| A-010 | P1 | PI historian read-only connector | Asset-tag mapping, timestamps, quality and security | Authorized integration replay |
| A-011 | P1 | Investigation evaluation | Competing hypotheses, evidence trace, bounded execution | Engineer-reviewed case studies |
| A-012 | P2 | Process models and simulator | Verified balances and constrained what-if | Validation against plant or approved reference |
| A-013 | P2 | Training/management products | Role-specific workflows and KPIs | User study, reconciled metrics |
| A-014 | P0 before external pilot | Security, IP and data governance | Agreements, threat model, audit, RBAC | Customer IT/OT/legal approval |

**Next decision:** perform A-001, then execute A-002 and A-003 in parallel. Do not spend further cycles on cosmetic OCR heuristics as the main AI strategy.

## 8. Progress scorecard — how to answer “where are we?”

**Never fabricate an overall completion %.** Each pillar and gate receives:
- **Maturity 0:** concept only.
- **Maturity 1:** source implementation present.
- **Maturity 2:** tests/build pass with reproducible logs.
- **Maturity 3:** end-to-end user workflow demonstrated.
- **Maturity 4:** measured against independent benchmark/acceptance criteria.
- **Maturity 5:** authorized industrial pilot accepted.

For every status report provide:
1. Date, branch, commit and what was actually inspected.
2. Executive summary: target vs current reality.
3. Seven-pillar maturity table and gate status.
4. Changes since previous report, with commits and test evidence.
5. Quantified quality metrics **only when measured**; otherwise “unknown”.
6. Bugs, technical debt, security/IP blockers, dependencies.
7. Next 3–5 prioritized deliverables, owners, acceptance tests.
8. Pilot readiness assessment and remaining risks.
9. Updated change log entry.

**Completion percentages** may be introduced only after a scoped work breakdown and explicit weighting; code presence is not business readiness.

## 9. Operating cadence and update protocol

At **every meaningful implementation milestone**:
1. Read this file before making architectural/product decisions.
2. Verify the latest repository state and any supplied test evidence.
3. Update the relevant pillar, phase gate, backlog row and evidence.
4. Append a dated entry to the change log with commit(s), outcome, tests, blockers and next step.
5. Commit documentation changes alongside or immediately after code changes.
6. On a user request for a status report, re-read this file **and** inspect current repo/CI evidence; report discrepancies explicitly.

**Automation limitation:** this file will not update itself when development happens elsewhere. Updates occur when an agent/developer runs the protocol; continuous unattended tracking requires a separately configured workflow.

## 10. Commercial and organizational plan

**Initial customer hypothesis:** refinery engineering/operations teams; validate measurable reduction in drawing interpretation and investigation time before enterprise-wide claims.

**Commercial stages:** Engineering Edition → Operations Edition → Enterprise Industrial Intelligence. Expand beyond FCC only after repeatable cross-unit validation.

**Pilot requirements:** defined scope, access to permitted sample drawings and data, nominated process/instrument engineers, IT/OT oversight, acceptance metrics, procurement/commercial terms, IP and confidentiality agreements. The founder's existing employment relationship requires explicit conflict-of-interest/IP review.

**Indicative staffing:** process/product lead; computer vision/ML; backend/graph/data; frontend/product engineering; security and domain reviewers as needed. Staffing and cost are hypotheses until resourced and quoted.

## 11. Decision log

| Date | Decision | Rationale |
|---|---|---|
| 2026-11-12 | Make Industrial Intelligence Platform the north star, not OCR-only P&ID software | Shared plant knowledge unlocks engineering, operations, investigations, training and management |
| 2026-11-12 | Retain existing codebase, audit before large refactor | Preserve useful modules while separating prototypes from validated capability |
| 2026-11-12 | Use hybrid vision + specialized detection + OCR + geometry + verified graph | Generic OCR/VLM alone is not reliable topology reconstruction |
| 2026-11-12 | Keep AI read-only and engineering decisions human-authorized | Industrial safety, traceability and trust |
| 2026-11-12 | Track progress by evidence-based maturity gates | Avoid misleading “done” labels and invented completion percentages |

## 12. Change log

### 2026-11-12 — v1.0 master baseline
- **Change:** Established unified product vision, seven pillars, architecture, maturity gates, prioritized backlog, reporting standard, security principles and initial evidence-based status.
- **Source of baseline:** user/assistant project planning discussions plus repository tree inspected on `agent/workspace-v2`; selected observed screenshots and previously reported commits.
- **Tests executed for this document:** none; **not** a completed technical audit.
- **Current blockers:** unvalidated whole-drawing AI, unverified VLM runtime, no gold benchmark, incomplete durable knowledge governance.
- **Next:** A-001 repository audit and A-002 local VLM end-to-end verification.

### 2026-11-12 — A-001 technical audit, first evidence pass
- **Scope inspected:** GitHub repository tree (264 paths), backend/desktop entrypoints, package/dependency scripts, existing `docs/ARCHITECTURE_AUDIT.md` and `docs/MASTER_VISION.md`, GitHub Actions run 43113635879 and desktop failure logs.
- **Key discovery:** a pre-existing broader refinery vision and architecture audit already cover controlled engineering editing, personal workspace/memory, and agent/tool contracts. These remain first-class requirements; do not narrow scope to P&ID.
- **CI evidence:** run 43113635879 on commit `bc9c04a` had backend **success**, desktop-web **failure**. Desktop errors were TS2367 (candidate category), TS2345 (shadow review state) and TS2322 (ZIP BlobPart typing).
- **Remediation committed:** `66309fd` (review type unions) and `311b238` (ZIP BlobPart conversion). **New CI result not yet verified** at time of this entry.
- **Important discrepancy:** frontend uses `http://127.0.0.1:18765`, while `scripts/dev-backend.sh` runs port **8000**. Determine whether Tauri's embedded sidecar bridges 18765 before treating this as a defect; document both runtime modes and test each.
- **Additional audit tasks:** enumerate route contracts, examine identity/RBAC enforcement, inspect data provenance and persistent storage, verify build and sidecar packaging, evaluate model installation/runtime path, confirm PI integration mode.
- **Next:** confirm fresh CI after fixes, audit desktop sidecar port wiring, then perform controlled VLM end-to-end benchmark.

### 2026-11-12 — CI verification after A-001 remediation
- GitHub Actions run **43114495612**, commit **311b238**, completed with **success** (both required CI jobs according to workflow conclusion). This validates the backend test job and desktop web TypeScript/Vite build for that commit; **it does not validate macOS Tauri packaging, Ollama inference or industrial functionality**.
- Subsequent documentation-only runs were still in progress when checked. Baseline source build is green at 311b238.

### 2026-11-12 — A-001 runtime/CSP audit continuation
- Confirmed **two intentional backend modes**: `scripts/dev-backend.sh` starts manual Uvicorn at **8000**; `desktop/src-tauri/src/main.rs` launches/reuses a Tauri `fcc-backend` sidecar at **18765**; `desktop/src/api.ts` and P&ID Vision UI target **18765**. Port mismatch is a mode distinction, **not by itself a bug**.
- Found actual Tauri **Content Security Policy** mismatch: `tauri.conf.json` allowed `8765` but not `18765` in `connect-src`. Fixed by explicitly permitting local 18765 while retaining legacy 8765 entries; commit **52a607c**. A real macOS Tauri run remains required to confirm behavior.
- Tauri sidecar checks `/health` before reusing an existing process on 18765; the check validates service-like response but is **not authentication**. Desktop backend has CORS allowlist, also **not authentication**. Multi-user access and privileged data actions still require backend-enforced authorization review.
- Next verification: GitHub CI, macOS Tauri runtime, CSP connectivity and end-to-end Ollama P&ID inference. Update CI status only after results are available.

### 2026-11-12 — A-001 macOS desktop launch confirmation (user-observed)
- **Local pull:** user fetched branch updates through `9215dec` on MacBook Air.
- **Observed local command:** `./scripts/dev-desktop.sh` ran `npm install`, Vite v7.3.6 reported ready at `localhost:1420`, Rust/Cargo reported `Finished dev profile`, and launched `target/debug/fcc-assistant`. **User explicitly confirmed the application window opened normally.**
- **Verified level:** macOS Tauri development build and desktop window startup. **Not verified:** backend identity/health endpoint 18765, UI API requests, Ollama model installation/inference, full P&ID semantics, production packaging.
- **Security finding (new):** `npm install` reported **2 high severity vulnerabilities** affecting the local dependency graph, but exact package/advisory IDs remain unknown pending `npm audit --json` (sanitized report). Do not run indiscriminate `npm audit fix --force`.
- **GitHub CI:** commits `52a607c`, `64a8858`, `9215dec` all have completed successful GitHub Actions runs; CI still does not execute macOS Tauri packaging.
- **Next check:** while desktop is running, `curl -fsS http://127.0.0.1:18765/health` and `curl -fsS http://127.0.0.1:18765/api/v1/system/capabilities`. Capture `cd desktop && npm audit --omit=dev` and `npm audit` to identify advisories; differentiate production and development vulnerabilities.

### 2026-11-12 — A-001 backend health and dependency security verification
- **User-confirmed Mac runtime checks:** `GET http://127.0.0.1:18765/health` returned `{"status":"ok","service":"fcc-assistant-backend","mode":"local"}`. `GET /api/v1/system/capabilities` returned `pi_web_api=not_configured`, `local_ai=ready`, `local_ai_runtime=llama.cpp`, `external_ai=false`, `plant_write_access=false` and advertised feature flags. This **verifies the backend HTTP endpoints** and advertised configuration, **not** a successful LLM answer, a functioning PI connector or effectiveness of each listed feature.
- **Security audit evidence:** `npm audit --omit=dev` found **0** vulnerabilities. `npm audit` flagged **2 high-severity development dependency packages**: `source-map-js` through 1.2.1 (GHSA-68fv-2mgg-jv7q, event-loop DoS) and `vite` through 7.3.6 (multiple advisories including GHSA-9jrq-w75r-8gcw and Windows launch-editor issues).
- **Remediation committed:** `2b6d46d` updates the Vite minimum to `^7.3.7` (patched within v7) and adds an npm override `source-map-js: ^1.2.2` (patched). The repository does **not** track a `desktop/package-lock.json`; local npm install must regenerate/reconcile packages. **Do not claim vulnerabilities are cleared until both `npm audit` and desktop CI confirm.**
- **Security nuance:** `npm audit --omit=dev` = 0 identified issues in production dependency graph, not a security certification; dev-server vulnerabilities still matter during development, especially if visiting untrusted websites.
- **Next:** validate dependency update through GitHub CI and local npm audit, then test local model inference, P&ID Vision endpoint and scoped PI integration.

### 2026-11-12 — A-001 dependency remediation validated on user's macOS
- User ran `git pull origin agent/workspace-v2`, `npm install`, `npm audit` and `npm run build` under `desktop/` after commit `2b6d46d`.
- **Results:** npm changed 2 packages; `npm install` reported **0 vulnerabilities**, `npm audit` reported **0 vulnerabilities**, and `tsc && vite build` **passed** with **Vite 7.3.8** (1615 transformed modules, built in 1.12 seconds). These are user-supplied runtime/build logs, not a local execution by the assistant.
- **A-001 dependency security issue CLOSED for observed dependency versions**. Continue to rescan future versions; npm audit measures known advisories, not total security assurance.
- **A-002 architecture discovery:** current `local_ai=ready` in `/api/v1/system/capabilities` refers to embedded **llama.cpp** model/binary presence (text analysis). P&ID Vision endpoint `/api/v1/pid/vision/analyze` is a **separate Ollama-only multimodal pipeline** defaulting to `qwen2.5vl:7b` on loopback port 11434. **Embedded llama.cpp readiness does not mean Vision AI is installed or operational.**
- **A-002 next checks:** read-only `GET /api/v1/ai/status`, `GET /api/v1/ai/runtime` and `GET http://127.0.0.1:11434/api/tags` to distinguish text-model runtime from Ollama Vision availability; verify inference against permissioned test image separately. The Vision prompt and model-output parsing are unbenchmarked proposals, not verified circuit reconstruction.

### 2026-11-12 — A-002 AI runtime discovery on user's Mac
- User re-confirmed desktop `npm audit` **0 vulnerabilities** and `tsc && vite build` **success** (Vite **7.3.8**, 1615 modules).
- `curl 127.0.0.1:18765/api/v1/ai/status` and `/api/v1/ai/runtime` both returned **connection refused**. **Interpretation:** desktop backend was not listening at test time; do not infer a regression without restarting `./scripts/dev-desktop.sh` and repeating health checks.
- `ollama list` returned no model rows; `GET 127.0.0.1:11434/api/tags` returned `{"models":[]}`. **Ollama daemon is reachable but no models are installed.** P&ID Vision inference cannot currently work via Ollama.
- **Action:** restart desktop in its own persistent terminal, verify `/health` and AI status from a second terminal, then install a tested multimodal Ollama model under explicit disk/RAM constraints. Do not mistake llama.cpp text model for the separate Ollama vision model.
- **Status:** A-002 in progress; no vision inference test performed, no accuracy claim.

### 2026-11-12 — A-002 hardware and backend availability
- User-reported `system_profiler` identifies **MacBook Air Apple M2, 8 GB unified memory**. Favor memory-constrained vision-model evaluation, not a default 7B VLM alongside desktop and embedded text LLM; benchmark actual peak RAM and latency before selection.
- User again received `curl: (7) Failed to connect` for `/health` and `/api/v1/ai/status` at `127.0.0.1:18765`. This shows **no listening desktop backend at the moment of the check**, not a demonstrated crash or backend regression. Need contemporaneous `./scripts/dev-desktop.sh` terminal output and process/port checks before diagnosing.
- Next: restart desktop in a persistent terminal, then verify port 18765 in parallel from another terminal; collect sidecar diagnostics if port remains unavailable. Do not download a large vision model yet.

### 2026-11-12 — A-002 desktop sidecar verified live
- User restarted the desktop and checked in a second terminal. `lsof -nP -iTCP:18765 -sTCP:LISTEN` showed `fcc-backe` PID **9472** listening on `127.0.0.1:18765`.
- `curl -v http://127.0.0.1:18765/health` connected successfully, received **HTTP 200 OK**, `server: uvicorn`, and JSON `{"status":"ok","service":"fcc-assistant-backend","mode":"local"}`.
- Process listing showed executable `desktop/src-tauri/target/debug/fcc-backend` (PIDs 9471 and 9472). Thus the desktop's own sidecar is confirmed running; earlier connection-refused observations were time-specific availability, not evidence of a permanent launch failure.
- **Remaining A-002 gate:** request local AI status and runtime readiness while desktop remains open; distinguish llama.cpp text model from the empty Ollama Vision model inventory, then select a memory-appropriate multimodal model for Apple M2 8 GB and run controlled P&ID inference.

### 2026-11-12 — A-002 embedded llama.cpp runtime confirmed live
- User supplied successful `GET /api/v1/ai/status`: `configured=true`, `connected=true`, `runtime=llama.cpp`, `provider=embedded-local`, model `Qwen3-4B-Q4_K_M`, `local_only=true`, with loaded model path under `~/.fcc-assistant/models/`.
- User supplied `GET /api/v1/ai/runtime`: binary and GGUF model both present, `endpoint_ready=true`, `port_open=true`, `identity_verified=true`, state `running=true`, `ready=true`, process PID **9525**, endpoint `127.0.0.1:18081`, macOS arm64.
- `ollama list` is still empty; the Ollama-based `/api/v1/pid/vision/analyze` multimodal path is not yet ready. These are **distinct runtimes**. No completed inference request yet; readiness does not prove answer quality or P&ID recognition.
- Next gate: run safe text-only chat-completions inference against the local llama.cpp endpoint; then design a memory-budgeted VLM approach for Apple M2 8GB and engineer-reviewed P&ID benchmark. Avoid concurrently loading a large 7B VLM with the resident 4B model.
