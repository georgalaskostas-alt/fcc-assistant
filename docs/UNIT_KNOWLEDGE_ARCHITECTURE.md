# Unit Knowledge Architecture

Status: design foundation for Workspace v2

## Goal

FCC Assistant must understand each configured process unit using more than live PI data. It must also use local engineering documentation, unit manuals, approved operating knowledge, revamp history and current unit-specific practices.

The system is advisory and read-only. It must never write PI/DCS values, controller outputs, setpoints or process commands.

## Core principle

The original manual is immutable source material. Site-specific changes are stored as a separate versioned knowledge layer rather than editing the source document.

Effective knowledge for a unit is derived from:

1. Original/manual source documents
2. Extracted structured knowledge and summaries
3. Revamp / modification records
4. Engineer-approved operational overrides
5. Time validity (`effective_from`, optional `effective_to`)
6. Provenance and approval metadata

This allows the system to preserve what the source manual states while also understanding what is currently true for the physical unit.

## Example

Manual statement:

> Valve FV-123 normal operating limit: 65%.

Current approved unit practice after revamp:

> For current FCC configuration, operate FV-123 up to 60% under normal service.

The system must retain both statements and answer using the current effective value while explicitly retaining the original source and the engineering override as provenance.

## Per-unit knowledge package

Each process unit owns a knowledge package:

```text
UnitKnowledgePackage
├── unit_key
├── documents[]
├── manual_summary
├── sections[]
├── equipment[]
├── operating_limits[]
├── procedures[]
├── constraints[]
├── chemistry / lab context[]
├── revamps[]
├── overrides[]
└── revision metadata
```

## Document ingestion

Supported target flow:

```text
Upload manual / procedure / engineering note
        ↓
Local document extraction
        ↓
Section-aware chunking
        ↓
Local embeddings / local retrieval index
        ↓
Structured extraction
        ↓
Generated manual summary
        ↓
Engineer review / approval
        ↓
Active unit knowledge package
```

All document processing should remain local for plant documents.

## Required source metadata

Every ingested document must store at minimum:

- document id
- unit key
- document type
- title
- revision number/date when available
- file hash
- ingestion timestamp
- source file path/reference
- page/section provenance for extracted knowledge
- active/superseded state

## Engineer overrides

Overrides are first-class records, not free-text edits to the manual.

Suggested model:

```json
{
  "id": "override-id",
  "unit_key": "fcc",
  "subject": "FV-123 normal operating upper limit",
  "manual_value": "65%",
  "effective_value": "60%",
  "reason": "Post-revamp operating practice",
  "effective_from": "2025-06-01",
  "effective_to": null,
  "source_document_id": "manual-001",
  "source_section": "6.4.2",
  "approved_by": "engineer identity",
  "approved_at": "timestamp",
  "status": "active"
}
```

Important properties:

- preserve original manual value
- record current effective value
- require reason/context
- support revocation/supersession
- support historical queries
- show provenance to the user

## Revamp model

A revamp or permanent process modification should be represented separately from an ad-hoc note.

```text
UnitRevamp
├── id
├── unit_key
├── title
├── description
├── effective_from
├── affected_equipment[]
├── affected_constraints[]
├── supporting_documents[]
└── approved knowledge changes[]
```

This allows questions to be interpreted against the correct historical configuration of the unit.

Example:

- “What happened in HCU yesterday?” → current configuration and current effective knowledge.
- “How was FCC operating in March 2023?” → knowledge and constraints effective in March 2023 where available.

## Retrieval policy for AI answers

For a unit-specific question, the local AI context should be assembled from:

1. selected unit and time range
2. relevant PI / lab / report evidence
3. current or historically-effective operational knowledge
4. relevant manual excerpts
5. active engineering overrides
6. revamp/modification context

Priority when statements conflict:

1. active engineer-approved override / approved revamp knowledge
2. active approved site procedure
3. latest applicable manual revision
4. older/superseded source only for historical explanation

The answer must not silently hide conflicts. If an override changes a manual value, the system should be able to state that the current effective value differs from the source manual.

## Shift and event analysis

Questions such as:

- “How did the units perform on night shift?”
- “What important happened in Hydrocracker this afternoon?”
- “Was FCC operation normal?”

should combine process evidence with unit knowledge rather than using generic thresholds.

Target reasoning context:

```text
Observed PI trends
+ Lab results
+ Unit operating envelope
+ Current approved overrides
+ Known equipment constraints
+ Revamp state
+ Shift/time context
= evidence-backed operational summary
```

The result should distinguish:

- observed facts
- inferred significance
- applicable operating knowledge
- missing evidence / uncertainty

## Knowledge maturity state

Each unit should expose a readiness state:

- `empty` — no manuals ingested
- `indexed` — documents locally indexed
- `review_needed` — extracted summary/knowledge awaiting engineer review
- `approved` — active approved unit knowledge
- `stale` — later revamp/change suggests review is required

## UI direction

Settings / Knowledge should eventually include:

```text
Unit Knowledge
├── FCC
│   ├── Manuals
│   ├── Current summary
│   ├── Approved overrides
│   ├── Revamps
│   └── Knowledge readiness
├── HCU
└── CDU
```

Engineer actions:

- add document
- inspect generated summary
- approve/reject extracted knowledge
- add current operating difference
- set effective date
- supersede an old override
- view source page/section
- compare manual vs current practice

## Safety and auditability

This knowledge system is decision support, not process control.

Required guarantees:

- local storage and local AI for plant documents
- no external AI upload of plant manuals/data by default
- no PI/DCS write path
- every override auditable
- source provenance preserved
- no silent mutation of source manuals
- historical revisions retained
- AI answers should cite the local source/override records used

## Implementation phases

### Phase 1
- local unit knowledge store
- document metadata
- manual summary record
- engineer overrides
- revamp records
- effective-date resolution
- API endpoints for knowledge status and effective knowledge

### Phase 2
- PDF/manual local ingestion
- local parsing/chunking
- local embeddings and retrieval
- generated section/manual summaries
- engineer approval workflow

### Phase 3
- connect knowledge retrieval to shift/event analysis
- PI + lab + knowledge evidence assembly
- provenance shown in answers
- historical configuration-aware analysis

### Phase 4
- richer equipment relationships
- procedure/constraint graph
- cross-unit refinery reasoning
- knowledge freshness detection after revamps/document updates
