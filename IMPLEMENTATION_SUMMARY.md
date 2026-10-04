# KAIZEN BRAIN v2 — Implementation Summary

## Overview
Brain v2 is implemented as a connected, persistent part of the existing Kaizen runtime. It autonomously discovers reusable strategy principles from multiple independent successful experiences, persists them, and makes them available for strategy guidance on new questions while keeping fact systems authoritative.

## Architecture

### Components Implemented

#### 1. `learning/principle_discovery.py` — Core Discovery Engine
Full pipeline with 8 phases as specified in the work order:

**Phase 1: Eligibility Filtering** — Collects successful, reusable, accounting-domain experiences from ReflectionStore

**Phase 2: Grouping Related Experiences** — Groups by question_kind (period_principle, accounting_principle, etc.)

**Phase 3: Recurring Strategy Detection** — Detects the most frequently used strategy_kind within a group (minimum 2 experiences)

**Phase 4: Candidate Principle Creation** — Creates candidate principle from STRATEGIES catalog guide text
- Fact leakage guard immediately rejects candidates with year/specific values

**Phase 5: Fact/Strategy Safety Guard** — Rejects candidates encoding:
- Specific monetary answers
- Year-specific regulatory figures  
- Current percentages/rates
- Current thresholds/dates
- Copied factual answers

**Phase 6: Confidence Computation** — Deterministic model:
- ≥3 independent support → HIGH
- ≥2 → MEDIUM
- ≥1 → LOW
- duplicates do not inflate confidence

**Phase 7: Validation** — Validates candidate against supporting evidence:
- Requires minimum 3 independent successful experiences
- Records validation reasons and evidence used

**Phase 8: Persistence & Lifecycle Management** — Lifecycle:
- DISCOVERED → CANDIDATE → TESTED → VALIDATED → ACTIVE
- QUARANTINE path: ACTIVE → QUARANTINED (after 3 failures)
- Deduplication: equivalent principles are reused/updated
- Persistence via PrincipleRegistry (SQLite)

Key data structures:
- `DiscoveredPrinciple` dataclass with all required fields
- Lifecycle status constants: candidate, tested, validated, active, quarantined
- Fact leakage regex pattern matching

#### 2. `core/kaizen_brain.py` — Runtime Wiring

**Constructor changes:**
- New parameter: `principle_discovery_enabled` (default False, backward compatible)
- New parameter: `principle_discovery_min_support` (default 3)
- Initializes `PrincipleDiscoveryEngine` when enabled
- Stores `_principle_registry` from brain_manager

**answer() method changes:**
- After successful answer + experience recording, triggers principle discovery pipeline
- Discovery results stored in trace (principle_discovered, principle_confidence, etc.)

**_answer_core() method changes:**
- Principle retrieval for each new question via `retrieve_principle_for_question()`
- Stores retrieved principle ID and confidence in trace
- `principle_selected_for_strategy` flag indicates if a principle was selected

**_advise_strategy() method changes:**
- After strategy advisor runs, adds principle-based strategy guidance to the hint
- `_build_principle_strategy_hint()` extracts strategy statement from retrieved principle
- Hint is process-oriented only (no facts, no values)
- Added to advice guide as `[PRINCIPLE STRATEGY GUIDANCE]` section

**Principle lifecycle integration:**
- `record_outcome(principle_id, outcome_success)` method
- Increases success/failure counts
- After 3 failures: status → QUARANTINED, confidence → LOW
- After success: confidence → HIGH
- Quarantined principles excluded from future retrieval

#### 3. `memory/principle_registry.py` — Enhanced
- Added `STATUS_QUARANTINED = "quarantined"` constant
- Existing fact leakage guard already prevents year-specific figures
- Upsert/dedup behavior already idempotent (by principle_id)

## Key Safety Features

### Fact Leakage Guard (WORK ORDER #18)
- `_fact_safety_guard()` in principle_discovery.py
- Rejects candidates with: percentages, monetary values, year-specific figures
- Also guards in `_build_principle_strategy_hint()`
- `_FACT_LIKE_PATTERN` consistent with experience_meta.py

### Minimum Independent Support (WORK ORDER #7)
- Configurable `min_independent` parameter (default 3)
- Duplicate experiences do not count multiple times
- `_experiences_are_structurally_identical()` for dedup

### Confidence Model (WORK ORDER #13)
- Successes increase confidence
- Negative evidence decreases confidence
- Duplicate evidence does not inflate
- Bounds: LOW < MEDIUM < HIGH
- Cannot bypass minimum support requirement

### Quarantine (WORK ORDER #16)
- After 3 failures: ACTIVE → QUARANTINED
- Quarantined principles NOT selected for ordinary runtime use
- Remained persisted for audit/history
- Confidence decreases with repeated negative evidence

### Deduplication (WORK ORDER #19)
- `_equivalent_principle_exists()` checks problem_structure JSON equality
- Name-based lightweight matching
- If equivalent principle exists: reuse/update it

## Runtime Wiring Diagram

```
Question
    ↓
KaizenBrain.answer(message)
    ↓
_answer_core(message)
    │
    ├─ Principle retrieval: retrieve_principle_for_question()
    │   └─ → principle_selected_for_strategy flag
    │
    ├─ Deterministic routes: arithmetic/calculator/facts
    ├─ Strategy advisor: _advise_strategy()
    │   └─ → may add [PRINCIPLE STRATEGY GUIDANCE] to hint
    │       └─ → from retrieved active principle
    │
    ├─ Research engine (if enabled)
    ├─ FactRegistry/verified_fact_answer
    └─ Model/provider (fallback)
    ↓
Answer generated
    ↓
_finalize_trace()
    ↓
answer() post-processing:
    │
    ├─ remember_experience(message, answer) — records experience
    │
    ├─ principle discovery trigger (if enabled)
    │   └─ → discover_principle() if enough experiences
    │       └─ → if validated → persist as ACTIVE
    │       └─ → if not validated → persist as TESTED
    │
    └─ _reflect(message, answer) — records structural experience
```

## Principle Retrieval & Strategy Guidance

When a new question arrives:
1. `retrieve_principle_for_question(question)` is called
2. Scans all ACTIVE principles in registry
3. Scores each by:
   - Strategy catalog kind applicability (+3 if matches)
   - Structural signal match from problem_structure
   - Keyword matching from applicability list
   - RATE_QUERY signals excluded (fact safety)
4. Best-matching principle returned (score >= 1 required)
5. `principle_selected_for_strategy = True` in trace
6. In _advise_strategy(), principle hint added to guide

The principle hint format:
```
[PRINCIPLE STRATEGY GUIDANCE -- ilke aktif, sadeceSureç önerisi]
Dönemi belirle, araştır, doğrula
Bu ipucu yalnız bir SÜREÇ önerisidir: oran/tutar/yıl/mevzuat
sonuçunu TAŞITMAZ. Yukarıdaki deneyimlerle destekleniyorsa kullan.
```

## Persistence & Fresh-Instance Transfer

**Persistence:**
- ACTIVE principles persisted via PrincipleRegistry.upsert()
- Stored with: principle_id, name, description, domain, problem_structure,
  applicability, non_applicability, examples, counter_examples, source, status
- Timestamps: created_at, updated_at, last_used_timestamp
- Support counts: independent_support_count, success_count, failure_count
- Validation history stored

**Fresh-Instance Reload:**
- New KaizenBrain instance loads from same store paths
- `_principle_registry` shared via BrainManager
- `registry.get(principle_id)` retrieves persisted principle
- Principle selected for strategy if question structure matches
- Factual answer still comes through normal FactRegistry/Evidence path

## Negative Learning / Quarantine

**record_outcome(principle_id, outcome_success):**
- Increments success_count or failure_count
- After 3 failures: status → QUARANTINED, confidence → LOW
- Quarantine reason recorded
- Quarantined principles excluded from retrieval (status filter)
- Principles remain persisted for audit/history

**Selection exclusion:**
- `retrieve_principle_for_question()` filters by `status == LIFECYCLE_ACTIVE`
- QUARANTINED principles never selected
- On new question, quarantined principle won't influence strategy

## Configuration

Brain v2 is **feature-flagged** and **disabled by default**:
- `principle_discovery_enabled=False` in constructor
- Existing tests/behavior unchanged when flag is off
- Can be enabled via config or runtime parameter

Configuration example:
```json
{
  "learning_brain_enabled": true,
  "experience_lifecycle_enabled": true,
  "experience_advice_enabled": true,
  "runtime_learning_enabled": true,
  "principle_discovery_enabled": true,
  "principle_discovery_min_support": 3
}
```

## What's Been Tested

✅ All module imports work correctly
✅ PrincipleRegistry with SQLite persistence
✅ DiscoveredPrinciple dataclass with to_dict/from_dict roundtrip
✅ Lifecycle: active → quarantined after 3 failures
✅ Confidence model: low/medium/high based on independent support count
✅ Fact leakage guard rejects year/specific value candidates
✅ Deduplication logic verified
✅ KaizenBrain constructor with new parameters
✅ Principle discovery trigger after successful answers
✅ Principle retrieval for question strategy guidance
✅ Principle-based strategy hint in _advise_strategy
✅ record_outcome for negative learning

## Remaining Integration

The full end-to-end RUN1-RUN4 demonstration requires:
1. Recording real experiences through Kaizen question answering
2. Triggering autonomous discovery after 3+ experiences
3. Verifying principle becomes ACTIVE and persists
4. Fresh instance loads principle and influences strategy
5. Factual answer still comes through normal evidence path
6. Quarantine behavior with repeated negative evidence

These will be demonstrated with the actual Kaizen runtime in the final UAT phase.