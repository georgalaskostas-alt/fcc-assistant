# Process Behavior Learning Architecture

## Goal

FCC Assistant must learn how each process unit behaves as an integrated chemical process, not merely memorize typical tag values.

The target is a unit-specific operational behavior model that can connect:

- feed and feed quality
- operating severity and operating regime
- temperatures and pressure profiles
- flows, ratios and recycle structure
- catalyst / hydrogen / steam / utility conditions where applicable
- equipment constraints
- laboratory results
- product yields and product quality
- energy use and major utilities
- disturbances and transitions
- approved operating practices and revamp state
- resulting process outcomes

The intended reasoning style is chemical-engineering process reasoning: inputs -> regime -> interactions -> outputs -> quality -> constraints -> observed consequences.

## What the system must NOT learn as its primary model

It must not reduce learning to statements such as:

- valve FV-123 is usually 43% open
- tray temperature T-204 is usually 183 C
- compressor suction pressure is usually X bar

Those values may be useful contextual features, but they are not the learned process knowledge itself.

## Operational episodes

Continuous history should be segmented into operational episodes. Each episode represents a coherent period such as:

- stable operation
- feed transition
- severity change
- rate change
- catalyst-condition change
- product-quality correction
- startup / shutdown / partial shutdown
- equipment limitation
- disturbance and recovery
- post-revamp operating mode

Each episode stores a structured context and outcome.

Example conceptual record:

```text
Unit: FCC
Period: 2026-08-21 07:00-11:30
Regime: stable high-rate operation
Inputs:
  feed rate
  feed quality / density / relevant assay
  catalyst circulation context
  steam / air / utility context
Operating state:
  reactor severity
  regenerator state
  fractionation state
Constraints:
  active engineering limits
  equipment constraints
Outputs:
  naphtha rate
  LCCO rate
  slurry rate
  fuel gas
Quality:
  lab results
Observed result:
  stable conversion and acceptable product quality
```

## Learned relationships

The system should learn repeated process relationships such as:

- under feed family A and severity range B, higher reactor temperature is repeatedly associated with a change in conversion / gas make / product distribution
- at similar throughput, a different feed quality produces a different regenerator or fractionator response
- this hydrogen/feed regime in HCU repeatedly corresponds to a certain product quality envelope
- after a specific revamp, the same feed rate produces a different pressure-drop or energy profile
- certain combinations of operating variables precede quality deterioration or recovery

These are learned operational patterns, not automatic causal claims.

## Evidence levels

Every learned statement must carry an evidence class.

### 1. Observed
Directly measured or calculated from trusted local data.

### 2. Repeated association
A statistically repeated relationship across comparable operating episodes.

### 3. Engineering hypothesis
A plausible chemical-engineering interpretation requiring engineer review.

### 4. Approved unit knowledge
A relationship or interpretation explicitly reviewed and approved by an engineer.

The AI must never present a repeated association as proven causality.

## Context normalization

The model must compare like with like. Similarity should account for variables such as:

- unit configuration / revamp version
- feed family and feed quality
- throughput
- operating mode
- catalyst age / activity where relevant
- hydrogen availability / recycle conditions where relevant
- ambient or utility constraints when material
- equipment availability
- product target / campaign

A historical episode from a materially different unit configuration must not silently define normal behavior for the current configuration.

## Revamp awareness

Learning is version-aware.

Operational data should be tagged with the configuration state that was effective at that time. A post-revamp behavior model should not automatically inherit pre-revamp relationships.

Where useful, the system may compare pre- and post-revamp behavior explicitly.

## Outcome-oriented learning

The principal learned object should be an input/regime/outcome relationship rather than a tag baseline.

Example:

```text
Context:
  HCU feed family = X
  throughput = 92-96%
  reactor inlet temperature regime = Y
  H2/oil ratio regime = Z

Repeated outcome:
  diesel sulfur = lower range
  conversion = higher range
  hydrogen consumption = higher range
  reactor delta-T = stable

Confidence:
  high repeated association
Comparable episodes:
  37
```

## Shift intelligence

For questions such as:

- "How did the units run on night shift?"
- "What important happened in Hydrocracker this afternoon?"
- "Why was FCC product quality different today?"

The analysis pipeline should combine:

1. actual PI process history
2. laboratory results
3. current approved unit knowledge
4. manual / revamp context
5. operational episode classification
6. learned comparable historical episodes
7. deviations from the expected outcome envelope

The answer should focus on process significance, not merely list tag movements.

## Chemical-engineering interpretation

The local AI may use general chemical-engineering knowledge to interpret observed patterns, but site-specific statements must be grounded in local evidence.

Priority order:

1. actual measured data
2. approved current unit knowledge
3. approved revamp / engineering context
4. manual knowledge
5. learned repeated unit-specific relationships
6. generic chemical-engineering knowledge

Generic engineering knowledge must never override an approved site-specific fact.

## Human review loop

The system may surface candidate learned relationships for engineer review.

Example:

```text
Candidate pattern:
At comparable feed quality and throughput, FCC operation with reactor temperature 3-5 C higher has repeatedly coincided with higher fuel-gas make and lower LCCO yield.

Evidence:
31 comparable operating episodes
Confidence: medium
Status: candidate
```

The engineer may:

- approve
- reject
- refine the context
- add an explanation
- mark a known confounder

Approved relationships become part of unit knowledge.

## Safety boundary

This subsystem is analytical and read-only.

It may:

- learn process behavior
- identify patterns
- compare operating regimes
- explain deviations
- generate engineering hypotheses

It must not:

- write to PI / DCS
- change setpoints
- execute control actions
- autonomously prescribe control moves as authoritative instructions

Any future optimization or advisory-control capability requires a separate explicitly approved architecture and safety review.

## Planned implementation components

1. Operational Episode Store
2. Regime Classifier
3. Context Similarity Engine
4. Outcome Feature Builder
5. Repeated-Pattern Miner
6. Evidence / Confidence Scoring
7. Engineer Review Queue
8. Approved Learned Knowledge Store
9. Shift Intelligence Retrieval
10. Local AI reasoning layer over actual data + approved knowledge + learned behavior
