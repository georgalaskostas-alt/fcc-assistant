# TRAVIS ↔ FCC Assistant Integration Contract

Contract version: `1.0-draft`

## Ownership

FCC Assistant owns process-data access, PI Web API integration, unit/tag metadata, analytics, reports, configurable operations workspaces, local AI and local speech-to-text.

TRAVIS owns its UI, runtime, permissions, task execution, workspace/window system and the client side of this integration.

TRAVIS MUST consume FCC capabilities through this local contract rather than duplicating FCC backend or process-intelligence logic.

## Security boundary

- Integration is local-first and read-only.
- Plant/process data MUST NOT be sent to external AI/cloud services by this bridge.
- No PI/DCS writes are permitted.
- No setpoint, controller-output or process-command writes are permitted.
- Any future write capability requires a new contract version and explicit architecture/security approval.

## Transport

Current FCC backend base URL:

`http://127.0.0.1:8000`

The service binds to loopback for local desktop use.

## Core status

### `GET /health`

Expected response shape:

```json
{
  "status": "ok",
  "service": "fcc-assistant-backend",
  "mode": "local"
}
```

TRAVIS should treat failure to reach this endpoint as FCC Assistant unavailable and degrade gracefully.

## Capability domains

The bridge is intended to expose versioned operations for:

1. health/status
2. sites and units
3. tag/variable metadata
4. current snapshots
5. historical trends
6. statistics and averages
7. shift/unit summaries
8. reports
9. configurable dashboard/workspace definitions
10. natural-language process queries through the FCC local AI runtime

Endpoints beyond `/health` are not frozen by this draft until their current backend routes and schemas are promoted into this contract.

## Multi-unit model

The logical hierarchy is:

```text
Site
 ├─ Unit
 │   ├─ Variable / PI tag mapping
 │   ├─ analytics
 │   ├─ reports
 │   └─ workspace widgets
 └─ Unit ...
```

TRAVIS should address units and semantic variables through FCC metadata rather than hardcoding refinery PI tag names.

## Dashboard/workspace semantics

FCC Assistant owns translation of user intent such as:

- “show FCC feed as an 8-hour trend”
- “show average regenerator O2 for this shift”
- “give me a unit summary”
- “build an overview for all units I supervise”

into validated FCC workspace configuration.

TRAVIS may present or launch these capabilities, but should not independently implement a second natural-language-to-PI dashboard engine.

## Local AI and speech

FCC process queries are intended to run through the FCC Assistant local AI runtime. Speech-to-text for FCC commands is also intended to remain local. TRAVIS must not silently reroute process content to an external model.

## Compatibility

TRAVIS should check bridge availability before exposing live FCC actions. Future revisions will add a machine-readable contract/capabilities endpoint and explicit API version negotiation.

## Current implementation status

Available/foundation:

- standalone macOS FCC Assistant application
- bundled local backend
- local `/health` endpoint
- FCC simulator/data foundation
- analytics/reporting foundation
- multi-unit model foundation
- natural-language configurable workspace foundation
- dynamic trend/KPI/summary widget work

Planned/under development:

- embedded local AI runtime
- local speech-to-text
- production PI Web API configuration
- stabilized multi-unit metadata endpoints
- versioned TRAVIS bridge endpoints and schemas

## Change policy

Changes that break request/response compatibility require a contract version change. FCC Assistant owns this document. TRAVIS should implement against documented capabilities only and degrade gracefully when a capability is unavailable.
