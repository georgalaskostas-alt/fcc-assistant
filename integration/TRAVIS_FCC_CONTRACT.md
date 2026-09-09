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

## Machine-readable bridge

### `GET /bridge/v1/capabilities`

Returns the bridge contract version, local/read-only security flags, advertised capability domains and the configured site/unit keys.

TRAVIS MUST verify:

- `mode == "local"`
- `read_only == true`
- `external_ai == false`
- `plant_write_access == false`

before enabling FCC process actions.

### `GET /bridge/v1/site`

Returns the semantic site catalog used by FCC Assistant, including configured process units and semantic variable/tag metadata. TRAVIS should use this endpoint instead of hardcoding PI tag names or assuming that only FCC exists.

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

Only endpoints explicitly documented here should be considered stable integration surface.

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

The local semantic catalog can contain one or many process units. Real refinery metadata is not committed to GitHub. FCC Assistant loads it from a local JSON file pointed to by:

`FCC_SITE_CONFIG=/local/path/site.json`

Example shape:

```json
{
  "name": "Refinery",
  "units": [
    {
      "key": "fcc",
      "name": "FCC",
      "tags": [
        {
          "key": "feed_flow",
          "label": "Feed Flow",
          "unit": "m3/h",
          "aliases": ["feed", "τροφοδοσία"]
        }
      ]
    }
  ]
}
```

The semantic catalog intentionally does not require real PI WebIds to be committed. PI identifiers/credentials remain local configuration.

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

TRAVIS should check `/health`, then `/bridge/v1/capabilities`, before exposing live FCC actions. Unknown contract versions or missing security guarantees must degrade to unavailable/read-only UI rather than fallback to an external service.

## Current implementation status

Available/foundation:

- standalone macOS FCC Assistant application
- bundled local backend
- local `/health` endpoint
- versioned `/bridge/v1/capabilities` endpoint
- semantic `/bridge/v1/site` endpoint
- local multi-unit site configuration loader
- FCC simulator/data foundation
- analytics/reporting foundation
- natural-language configurable workspace foundation
- dynamic trend/KPI/summary widget work

Planned/under development:

- embedded local AI runtime completion
- local speech-to-text
- production PI Web API configuration
- stabilized current/historical data bridge endpoints
- explicit API version negotiation beyond `1.0-draft`

## Change policy

Changes that break request/response compatibility require a contract version change. FCC Assistant owns this document. TRAVIS should implement against documented capabilities only and degrade gracefully when a capability is unavailable.
