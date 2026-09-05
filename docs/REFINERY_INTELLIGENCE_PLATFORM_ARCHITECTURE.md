# Refinery Intelligence Platform Architecture

## Product objective

Evolve FCC Assistant from a unit dashboard into an on-premise, refinery-wide operations intelligence and decision-support platform for engineers, unit supervisors, complex managers, refinery management and other authorized roles.

The product must scale without redesign from one unit to a whole refinery.

## Hierarchy

```text
Refinery
├── Complex / Department
│   ├── Unit
│   ├── Unit
│   └── Unit
├── Utilities / Energy
├── Laboratory
├── Tank Farm / Inventories
├── Movements / Blending
├── Reliability / Maintenance context
├── Production Planning
└── Economics / Margins
```

Example complex:

```text
Conversion Complex
├── FCC
├── Hydrocracker
└── Vacuum Distillation
```

## Role-oriented experience

### Unit / process engineer
Needs deep process intelligence:
- live and historical process trends
- laboratory results and quality context
- shift/event analysis
- manual and procedure knowledge
- revamp-aware unit knowledge
- operating-envelope context
- learned process behavior and comparable historical episodes
- equipment/process constraints
- engineer review of learned patterns
- reporting and investigation workspaces

### Unit supervisor / foreman
Needs operational prioritization:
- current unit state
- significant deviations
- shift handover intelligence
- active constraints
- quality risks
- important equipment/process events
- comparison with recent operation
- concise AI-generated operational brief with evidence

### Complex / department manager
Needs cross-unit understanding:
- health/status of all assigned units
- throughput and production vs plan
- cross-unit constraints and dependencies
- quality and lab exceptions
- energy / utilities performance
- significant events by shift/day
- bottlenecks
- reliability context
- production losses and recoveries
- drill-down from complex -> unit -> equipment/tag/evidence

### Refinery management
Needs refinery-level decision support:
- production and plan attainment
- refinery and complex constraints
- major quality deviations
- energy and utility intensity
- inventories
- movements / transfer constraints
- blending context where available
- reliability events affecting production
- economics / margin indicators where authorized
- concise refinery brief with explainable drill-down

## Data domains

The architecture treats data sources as separate governed domains.

### Process
PI Web API / historian values, calculated variables, operating states and events.

### Laboratory
Product/feed/intermediate analyses, timestamps, sample context, specification and quality state.

### Knowledge
Manuals, procedures, revamps, approved engineering overrides, unit-specific practices and learned approved relationships.

### Production
Rates, yields, daily/monthly production, plan/target, losses, constraint accounting.

### Energy and utilities
Fuel, steam, electricity, hydrogen, cooling, water and other material utility indicators where available.

### Reliability
Equipment availability, production-impacting maintenance context, trips, bad actors and active constraints. Integration remains read-only.

### Inventory
Tank levels/volumes, usable inventory, days of cover, high/low constraints and feed/product availability where authorized.

### Movements and blending
Transfers, receipts, shipments, routing constraints, blend status and movement exceptions where systems expose governed read-only data.

### Economics
Authorized economic indicators such as feed/product values, variable operating costs, energy costs, hydrogen cost, contribution/margin and plan/forecast variance. Economics is a separate permission domain.

## Economic/process attribution

The platform should not stop at displaying a margin number. Where trusted source data and approved calculations exist, it should attribute performance changes to operational drivers such as:

- throughput loss
- feed slate/value change
- yield shift
- product quality / downgrade / off-spec impact
- energy penalty
- hydrogen consumption
- catalyst/chemical consumption where available
- equipment constraint
- downstream bottleneck
- inventory or movement limitation

Attribution must distinguish calculated contribution from causal proof and must expose its source/calculation lineage.

## Progressive drill-down

The UI should avoid one enormous dashboard. It should support progressive hierarchy:

```text
Refinery -> Complex -> Unit -> Section/Equipment -> Variable/Lab/Event -> Evidence
```

A refinery manager sees exceptions and business/process significance first. A process engineer can drill to detailed evidence and history.

## Natural-language examples

- "How did the conversion complex run on night shift?"
- "What important happened in Hydrocracker this afternoon?"
- "Which units are limiting refinery throughput right now?"
- "Where did we lose production versus plan today?"
- "What changed in FCC yield versus comparable feed campaigns?"
- "Show inventory constraints that can affect tomorrow's plan."
- "Explain today's margin variance, using only data I am authorized to see."

Answers must respect role permissions and source provenance.

## Role-based access control

Authorization must be enforced in backend services, not only hidden in the UI.

Conceptual roles/scopes:
- process engineer: assigned units, engineering/process domains
- supervisor: assigned operational units
- complex manager: assigned complex and approved cross-unit domains
- refinery manager: refinery-level operational domains
- economics-authorized: explicit economics permission
- knowledge approver: approve unit knowledge / engineering overrides
- administrator: configuration and identity management, not automatic access to all sensitive business data

The exact enterprise mapping should be compatible with future SSO / Active Directory integration.

## Audit and provenance

Every consequential answer should be traceable to evidence. The platform should retain:
- data source and timestamp
- calculation version
- manual section/page/chunk where applicable
- active engineering override and effective date
- learned-pattern evidence and confidence
- user-approved knowledge revision
- AI query/audit metadata appropriate to enterprise policy

## Data quality

Every analytical domain should carry quality/freshness state. The AI must distinguish:
- live/trusted
- delayed/stale
- simulated/development
- missing
- bad/questionable
- manually entered / approved

The system must not silently substitute simulated or stale data for live plant data.

## Enterprise deployment principles

- on-premise/local deployment first
- no external AI required for plant intelligence
- no plant/process data sent to external AI by default
- encrypted persistent storage
- configurable retention
- backup/restore strategy
- future high-availability deployment profile
- SSO/AD-ready identity architecture
- role-based authorization
- audit trail
- versioned schemas/calculations/models
- observability and health monitoring

## Safety boundary

The platform is decision support and read-only toward plant control/historian interfaces.

It must not:
- write DCS/PI values
- change controller modes or setpoints
- actuate valves/equipment
- execute process commands
- present learned statistical association as proven causality

Optimization recommendations, if added later, require a separately governed advisory architecture and explicit safety review.

## Product modules

1. Operations Workspace
2. Shift Intelligence
3. Unit Knowledge
4. Process Behavior Learning
5. Laboratory Intelligence
6. Production & Plan
7. Energy & Utilities
8. Reliability Context
9. Inventory Intelligence
10. Movements & Blending
11. Economics & Margin (permission-gated)
12. Reporting / Briefing
13. Administration / Data Sources / RBAC / Audit
14. Local AI & Search
15. TRAVIS local bridge

## Delivery strategy

Do not attempt all enterprise connectors at once. Build one coherent vertical slice and keep every schema scalable to refinery scope.

### Phase A — current vertical slice
FCC + Hydrocracker simulator/site model, dynamic multi-unit workspace, local knowledge, process behavior learning foundation.

### Phase B — engineering intelligence
Manual ingestion, approved overrides/revamps, lab model, operational episodes, shift intelligence and evidence-backed local AI.

### Phase C — complex management
Complex hierarchy, production vs plan, cross-unit constraints, energy/utilities and management briefing.

### Phase D — refinery operations
Inventory, movements/blending, reliability integrations and refinery-wide exception/constraint intelligence.

### Phase E — economics and enterprise hardening
Permission-gated margins/economic attribution, SSO/AD, hardened audit/security, backup/HA/retention, deployment validation and enterprise administration.
