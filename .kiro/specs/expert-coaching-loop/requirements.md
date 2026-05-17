# Requirements Document

## Introduction

`expert-coaching-loop` 将现有 Reality OS 框架升级为"帮助初学者通过互动达到顶级专家水平"的知识管理 Agent。本 spec 把先前分析中提出的全部优化项落地为一个综合 feature，按优先级 P0–P3 分组：

- **P0** — 教练会话一等公民、Expert Rubric 差距打分、Skill Chain
- **P1** — Calibration Loop、Mastery Graph + SM-2、主动补证据
- **P2** — Metacognition Hooks、嵌入层 + 跨域类比、真实世界结果硬绑定
- **P3** — 学习仪表板

外加一组横切要求覆盖 pending-review / 工具执行 / 租户隔离 / 审计 / i18n / PBT / Legacy 保护 / Server-only secrets。

所有新增能力 MUST 复用并扩展现有模块（`apps/api/app/orchestrator.py`、`reality_layers.py`、`reality_advisor.py`、`audit_agent.py`、`expert_search.py`、`knowledge_core.py`、`vector_store.py`、`thinking_skills/`、`apps/web/app/*`），不另起炉灶；`legacy/` 保持只读。

## Glossary

- **Reality_OS**: The full system being upgraded — the unified FastAPI + Next.js stack rooted at `apps/`.
- **Coaching_Session**: A new aggregate state machine that links one user's `UserProfile`, `Diagnosis`, `ClassifiedEvidence`, `ActionExperiment`, `LearningReview`, and `DecisionLog` records across multiple turns.
- **Coaching_State_Machine**: The set of allowed states (`active`, `awaiting_evidence`, `awaiting_practice`, `awaiting_experiment`, `awaiting_review`, `paused`, `archived`) and transitions of a `Coaching_Session`.
- **Coach_Turn**: One `(user_message → next_prompt + grounded_evidence + contradictions + due_practice)` round inside a `Coaching_Session`, served by `POST /api/v2/coach/turn`.
- **Orchestrator**: The existing `apps/api/app/orchestrator.py`, specifically the `orchestrated_ask` function that the `Coach_Turn` endpoint MUST extend.
- **Reality_Advisor**: The existing `apps/api/app/reality_advisor.py`, including `RealityAdvisor.advise` and `_select_strategy`.
- **Audit_Agent**: The existing `apps/api/app/audit_agent.py` (`zero_context_audit` plus its 5 dimension checks).
- **Expert_Rubric**: A versioned YAML document under `apps/api/expert_rubrics/{domain}.yaml` defining scoring dimensions, anchors, examples, source, version, author, and cited evidence IDs for one domain.
- **Expert_Gap_Score**: A 0.0–1.0 score plus a list of "additional points an expert would consider" produced by the new `_check_expert_gap` audit dimension.
- **Skill_Chain**: An ordered, named sequence of `thinking_skills/*` Skills (e.g. `problem-statement → 5whys → JTBD → pre-mortem → decision-matrix → SMART`) keyed by `problem_type`, defined under `apps/api/thinking_skills/chains/`.
- **Skill_Chain_Switch**: A controlled transition from one `Skill_Chain` to another mid-session, triggered by repeated experiment failure or by evidence indicating a different `problem_type`.
- **Calibration_Loop**: The mechanism that captures `predicted_outcome` + `confidence ∈ [0, 1]` before any `DecisionLog` is persisted, then computes Brier score and Log loss at review time.
- **Brier_Score**: The mean squared error between predicted probabilities and binary outcomes; bounded in `[0, 1]`.
- **Mastery_Graph**: The set of `Concept` nodes plus prerequisite edges, each enriched with `mastery_score`, `last_practiced_at`, `next_due_at`, `decay_lambda`.
- **SM_2_Scheduler**: An SM-2-derived spaced-repetition scheduler that updates `next_due_at` and `decay_lambda` from a 0–5 grade after each practice.
- **Active_Evidence_Gathering**: The closed loop `verification.insufficient_evidence=True → expert_search → pending_knowledge → user approve → DecisionMemo verdict allowed`.
- **Pending_Knowledge**: An item written to the existing `pending_knowledge` table with `status=pending_review`; never written automatically into formal knowledge.
- **Metacognition_Hook**: A pre-answer `confidence_check` and a post-answer `questions_you_didnt_ask` block attached to each significant `Coach_Turn`.
- **Metacognition_Score**: A 0.0–1.0 mastery dimension derived from the user's `confidence_check` accuracy and `questions_you_didnt_ask` engagement.
- **Vector_Store**: The existing `apps/api/app/vector_store.py` `VectorStore` Protocol + `SqliteTfidfVectorStore`, to be wired into the retrieval path.
- **Hybrid_Retrieval**: Retrieval that combines FTS + TF-IDF + embedding cosine similarity with configurable weights.
- **Cross_Domain_Analogy**: A retrieval mode that surfaces `KnowledgeItem`s and `Concept`s with high embedding similarity but explicitly different `domain` tags.
- **Real_World_Result_Binding**: The structured update of `Concept.mastery_score` from a structured `ActionExperiment.review` outcome (`success | partial | fail` + key metrics).
- **Learning_Dashboard**: The extension of the existing `eval_dashboard` exposing mastery heatmap, calibration curve, skill-chain completion rate, and concept decay curves to `/eval`, `/learn`, `/dashboard`.
- **Audit_Log**: The existing tenant-scoped audit log accessed via `storage.list_audit` and `core._record_audit`.
- **Tenant_Id**: The tenant identifier resolved by `apps/api/security.py::current_context`, scoped to every read/write across the new feature.
- **Supervisor_Approval**: The existing dry-run + approval pipeline in `apps/api/main.py::supervisor_*` that high-risk tool actions go through.
- **PBT**: Property-Based Testing using Hypothesis (or equivalent) against pure functions of the new feature.
- **Simple_Mode** / **Professional_Mode**: The existing UI modes set on `/settings`, persisted in cookie + localStorage.

## Requirements

### Requirement 1: Coaching Session Aggregate (P0)

**User Story:** As a learner who wants to grow from beginner toward expert, I want every interaction to live inside one durable coaching session that ties my profile, diagnosis, evidence, experiments, and reviews together, so that the system can remember where I am in my learning loop and pick the right next move (learn / practice / experiment / review) on every turn.

#### Acceptance Criteria

1. THE Reality_OS SHALL persist a `Coaching_Session` aggregate that references one `UserProfile` and zero-or-more `Diagnosis`, `ClassifiedEvidence`, `ActionExperiment`, `LearningReview`, and `DecisionLog` records via tenant-scoped foreign keys.
2. THE Reality_OS SHALL implement the `Coaching_State_Machine` with states `{active, awaiting_evidence, awaiting_practice, awaiting_experiment, awaiting_review, paused, archived}` and SHALL reject any state transition not declared in the machine specification.
3. WHEN a client calls `POST /api/v2/coach/turn` with `{session_id, user_message}`, THE Orchestrator SHALL invoke an extended `orchestrated_ask` and SHALL return `{next_prompt, grounded_evidence, contradictions, due_practice, session_state, expert_gap}`.
4. WHEN `session_id` is omitted on `POST /api/v2/coach/turn`, THE Reality_OS SHALL create a new `Coaching_Session` for the caller's `Tenant_Id` and SHALL return its `session_id` in the response.
5. WHEN a `Coach_Turn` completes, THE Reality_OS SHALL update the session's mastery, calibration, and gap-graph snapshots and SHALL decide the next coaching action from `{learn, practice, experiment, review}` based on the updated state.
6. WHEN a `Coaching_Session` has had no `Coach_Turn` for at least the configured timeout (default 30 days), THE Reality_OS SHALL transition the session to `archived`.
7. WHILE a `Coaching_Session` is in `archived` state, THE Reality_OS SHALL allow read access for review and SHALL reject new `Coach_Turn` writes against that session.
8. WHEN a `Coach_Turn` is processed across two distinct HTTP requests, THE Reality_OS SHALL restore the full session state (profile, last diagnosis, mastery snapshot, calibration history, current `Skill_Chain` position) from persistent storage before composing the next prompt.
9. THE Reality_OS SHALL implement `Coach_Turn` by extending `orchestrated_ask` in `apps/api/app/orchestrator.py` rather than introducing a parallel orchestrator.
10. IF a `Coach_Turn` request references a `session_id` that does not belong to the caller's `Tenant_Id`, THEN THE Reality_OS SHALL respond with HTTP 404 and SHALL NOT leak any session metadata.

### Requirement 2: Expert Rubric and Gap Scoring (P0)

**User Story:** As a learner, I want every answer to be scored against an explicit expert rubric for the relevant domain and to see the additional points an expert would have considered, so that I can close the gap between my current thinking and expert thinking.

#### Acceptance Criteria

1. THE Reality_OS SHALL load one `Expert_Rubric` per supported domain from `apps/api/expert_rubrics/{domain}.yaml`, where each rubric file declares `domain`, `version`, `author`, `source`, `dimensions[]`, `scoring_anchors{}`, `examples[]`, and `cited_evidence_ids[]`.
2. THE Audit_Agent SHALL expose a new dimension `_check_expert_gap` that consumes the active `Expert_Rubric` and the `Coach_Turn` output and SHALL return `{expert_gap_score, missing_points[]}`.
3. WHEN a `Coach_Turn` produces an answer, THE Audit_Agent SHALL run `_check_expert_gap` against the resolved `Expert_Rubric` and SHALL attach `expert_gap_score ∈ [0.0, 1.0]` and `missing_points[]` to the turn response.
4. THE Reality_OS SHALL render `missing_points[]` to the user as "专家会额外考虑的 N 个点" in zh-CN and "N additional points an expert would consider" in en.
5. IF an `Expert_Rubric` is missing required fields (`version`, `author`, `source`, or any `cited_evidence_ids` entry that does not resolve to an existing `EvidenceSnapshot` or `KnowledgeItem`), THEN THE Reality_OS SHALL refuse to load the rubric, SHALL log the failure to the `Audit_Log`, and SHALL fall back to running the existing 5 audit dimensions only.
6. WHEN an `Expert_Rubric` is reloaded with a new `version`, THE Reality_OS SHALL keep prior versions readable for historical sessions and SHALL record the version actually applied to each `Coach_Turn`.
7. WHERE no domain-specific `Expert_Rubric` matches a `Coach_Turn`, THE Reality_OS SHALL apply the bundled `default.yaml` rubric and SHALL mark the response with `expert_rubric_source = "default"`.

### Requirement 3: Skill Chain (P0)

**User Story:** As a learner working on a specific kind of problem, I want the coach to walk me through an ordered chain of thinking skills appropriate for that problem (not just one skill), and to switch chains when the evidence indicates I am working on a different problem, so that I follow an expert-level reasoning sequence end to end.

#### Acceptance Criteria

1. THE Reality_OS SHALL define `Skill_Chain` documents under `apps/api/thinking_skills/chains/{problem_type}.yaml`, each declaring `problem_type`, `steps[]` (an ordered list of `thinking_skills/*` skill IDs), and required `entry_conditions` and `exit_conditions`.
2. THE Reality_Advisor SHALL change `_select_strategy` so that it returns a `Skill_Chain` reference (chain id + current step index) instead of a single skill, while preserving the existing `AdvisorResponse` shape via additive fields.
3. WHEN a `Coach_Turn` advances inside a `Coaching_Session`, THE Reality_OS SHALL move the chain pointer to the next step only when the current step's `exit_conditions` are satisfied, and SHALL otherwise repeat the current step with refined prompts.
4. WHEN at least N consecutive `ActionExperiment` records linked to the active `Skill_Chain` end with `status="failed"` (where N is configurable, default 2), THE Reality_OS SHALL trigger a `Skill_Chain_Switch` and SHALL record the trigger reason in the `Audit_Log`.
5. WHEN newly classified evidence in the `Coaching_Session` indicates a `problem_type` different from the active chain's `problem_type`, THE Reality_OS SHALL propose a `Skill_Chain_Switch` to the user and SHALL apply the switch only after explicit user confirmation in `Simple_Mode` or after the configured auto-switch flag in `Professional_Mode`.
6. THE Reality_OS SHALL ship a baseline chain `general_decision.yaml` with steps `problem-statement → five-whys → jtbd → pre-mortem → decision-matrix → smart`.
7. IF a `Skill_Chain` references a skill ID that does not exist in `apps/api/thinking_skills/`, THEN THE Reality_OS SHALL refuse to load the chain at startup and SHALL log the validation error to the `Audit_Log`.

### Requirement 4: Calibration Loop (P1)

**User Story:** As a learner, I want every decision I commit to capture my predicted outcome and confidence, and at review time I want to see how well-calibrated my predictions actually are, so that calibration becomes a measurable mastery dimension.

#### Acceptance Criteria

1. WHEN a `DecisionLog` is created, THE Reality_OS SHALL require a non-empty `predicted_outcome` and a `confidence ∈ [0.0, 1.0]` and SHALL reject the request with HTTP 400 if either is missing or out of range.
2. WHEN a `LearningReview` records the actual outcome of a `DecisionLog`, THE Reality_OS SHALL compute and persist `brier_score` and `log_loss` for that review.
3. THE Reality_OS SHALL expose a calibration curve per `Tenant_Id` aggregating all reviewed `DecisionLog`s, binning predictions into deciles `[0.0, 0.1), [0.1, 0.2), …, [0.9, 1.0]` and reporting empirical frequency per bin.
4. THE Reality_OS SHALL include `calibration_score` as a dimension of the `UserProfile`'s mastery summary, computed as `1 - mean(brier_score)` over the most recent 50 reviewed decisions or all reviewed decisions if fewer than 50 exist.
5. WHEN the next coaching action is decided in a `Coach_Turn`, THE Reality_OS SHALL bias the action toward `practice` or `review` if `calibration_score` is below the configured threshold (default 0.6).
6. IF a `LearningReview` cannot resolve a binary outcome from the user input, THEN THE Reality_OS SHALL store the review with `brier_score=null, log_loss=null` and SHALL exclude it from the calibration curve.

### Requirement 5: Mastery Graph and SM-2 Scheduling (P1)

**User Story:** As a learner, I want every concept I touch to be tracked as a node in a graph with prerequisite edges, mastery decay, and SM-2 spaced repetition, so that my learn plan and retrieval practice always reflect what is actually due and what depends on what.

#### Acceptance Criteria

1. THE Reality_OS SHALL extend `Concept` in `apps/api/app/knowledge_core.py` with `mastery_score ∈ [0.0, 1.0]`, `last_practiced_at`, `next_due_at`, and `decay_lambda > 0`, with backwards-compatible defaults for existing rows.
2. WHEN a user submits a practice grade `g ∈ {0, 1, 2, 3, 4, 5}` for a `Concept`, THE Reality_OS SHALL update `mastery_score`, `next_due_at`, and `decay_lambda` according to the SM-2 algorithm specified in design.
3. WHEN `retrieval_practice_plan` runs, THE Reality_OS SHALL select due concepts using `SM_2_Scheduler` (where `next_due_at <= now()`) and SHALL generate exercises mixing `cloze`, `socratic`, and `counterexample` formats.
4. WHEN `learn_plan` runs, THE Reality_OS SHALL return concepts whose `mastery_score` is below the configured pass threshold, ordered by topological prerequisite depth such that prerequisites appear before dependents.
5. WHEN a concept has not been practiced for a period exceeding `1 / decay_lambda` days, THE Reality_OS SHALL apply exponential decay to `mastery_score` such that for any pair of timestamps `t1 < t2` with no intervening practice, `mastery_score(t2) <= mastery_score(t1)` (monotonic non-increasing decay between practices).
6. THE Reality_OS SHALL recompute decayed `mastery_score` lazily on read and SHALL persist the recomputed value when a `Coach_Turn` writes to the same concept in the same request.
7. THE Reality_OS SHALL expose property-testable pure functions `sm2_update(grade, prev_state) -> next_state` and `decay(mastery, lambda, dt) -> mastery` that are independent of storage.

### Requirement 6: Active Evidence Gathering (P1)

**User Story:** As a learner relying on this coach, I want the system to refuse to issue a verdict when evidence is insufficient and to instead automatically search for missing evidence, queue it for my review, and only release the verdict after I approve, so that I never act on a confident but unfounded answer.

#### Acceptance Criteria

1. WHEN `work/verification` returns `insufficient_evidence=true` for a claim inside a `Coach_Turn`, THE Reality_OS SHALL automatically dispatch an `expert_search` task seeded with the claim and the current `Coaching_Session` context.
2. WHEN an `expert_search` task returns results during `Active_Evidence_Gathering`, THE Reality_OS SHALL write each result to `pending_knowledge` with `status="pending_review"`, `formal_knowledge_write=false`, and SHALL link the records back to the originating `Coach_Turn` and `DecisionLog`.
3. WHILE any `pending_knowledge` linked to a `DecisionLog` remains `status="pending_review"`, THE Reality_OS SHALL keep the `DecisionLog`'s `verdict` field empty and SHALL refuse to publish a `DecisionMemo` that depends on that `DecisionLog`.
4. WHEN a user `approve`s the linked `pending_knowledge` set, THE Reality_OS SHALL re-run verification once and SHALL allow the `DecisionMemo` verdict to be issued only if the re-run no longer reports `insufficient_evidence`.
5. THE web UI SHALL surface pending evidence for review with a one-click `approve` action under the existing `/library` and `/decision` routes.
6. IF a user `reject`s pending evidence, THEN THE Reality_OS SHALL remove that record from the `DecisionLog` evidence set and SHALL keep the loop open until at least one approved item exists or the user explicitly closes the loop with a documented reason recorded in the `Audit_Log`.

### Requirement 7: Metacognition Hooks (P2)

**User Story:** As a learner, before each important answer I want to commit my own probability estimate, and after each answer I want to see the questions I should have asked but did not, so that I build the metacognitive habits of an expert.

#### Acceptance Criteria

1. WHEN a `Coach_Turn` is classified as significant (per a configurable significance rule) and the user has not yet supplied a `confidence_check` value, THE Reality_OS SHALL emit a `confidence_check` prompt in the `next_prompt` field requesting a value in `[0.0, 1.0]`.
2. THE Reality_OS SHALL persist each `confidence_check` value next to the system's own confidence estimate for the same turn.
3. WHEN a `Coach_Turn` answer has been generated, THE Reality_OS SHALL append a `questions_you_didnt_ask` block of 3–7 entries derived from the active `problem_type` template plus, where the generator slot is configured, an LLM expansion.
4. THE Reality_OS SHALL compute `metacognition_score` per `Tenant_Id` as a function of the absolute error between user `confidence_check` and observed outcomes and the user's engagement rate with `questions_you_didnt_ask`, bounded in `[0.0, 1.0]`.
5. THE Reality_OS SHALL expose `metacognition_score` as a dimension of the `UserProfile` mastery summary alongside `calibration_score` and `expert_gap_score`.
6. WHERE the user is in `Simple_Mode`, THE Reality_OS SHALL render only one `confidence_check` prompt per session per day; in `Professional_Mode`, THE Reality_OS SHALL render the prompt on every significant `Coach_Turn`.

### Requirement 8: Embedding Layer and Cross-Domain Analogy (P2)

**User Story:** As a learner, I want retrieval to use embeddings on top of FTS and TF-IDF, and I want the system to surface analogous concepts from other domains, so that I can transfer expert patterns across fields.

#### Acceptance Criteria

1. THE Reality_OS SHALL extend `KnowledgeItem` with a `vector` column populated by the active embedder configured via `model_registry.ModelSlot="embedder"`.
2. WHEN a `Coach_Turn` performs retrieval, THE Reality_OS SHALL combine FTS, TF-IDF, and embedding cosine scores into a single ranked list using configurable weights `(w_fts, w_tfidf, w_embed)` with sane defaults that sum to 1.
3. THE Reality_OS SHALL expose `POST /api/v2/concepts/{id}/analogies` which SHALL return concepts and items from `domain` tags different from the source concept's `domain` ranked by embedding cosine similarity.
4. WHEN the embedder slot is unconfigured, THE Reality_OS SHALL fall back to `Vector_Store="sqlite_tfidf"` retrieval and SHALL set `analogies_available=false` in the response without error.
5. THE Reality_OS SHALL allow embedder strategy to be selected per environment via `REALITY_OS_VECTOR_STORE` and a new `REALITY_OS_EMBED_MODE ∈ {online, offline, disabled}` env var documented in `.env.example`.
6. THE Reality_OS SHALL not call any external embedding API when `REALITY_OS_EMBED_MODE=offline` and SHALL use the local TF-IDF fallback instead.

### Requirement 9: Real-World Result Hard Binding (P2)

**User Story:** As a learner, I want every action experiment review to be structured (success / partial / fail plus key metrics) and to automatically update the mastery of the related concepts, so that real-world results — not self-assessment — drive my learning graph.

#### Acceptance Criteria

1. THE Reality_OS SHALL extend `ActionExperiment.review` to a structured shape `{result_class ∈ {success, partial, fail}, key_metrics: {name, value, unit, target}[], notes}`.
2. WHEN an `ActionExperiment` is reviewed with a non-null `result_class`, THE Reality_OS SHALL update `Concept.mastery_score` for every `Concept` linked to the experiment via the `SM_2_Scheduler` mapping `success=5, partial=3, fail=1`.
3. WHEN the same `Tenant_Id` records `result_class="fail"` on K consecutive experiments inside the same `Skill_Chain` (K configurable, default 3), THE Reality_OS SHALL trigger a `Skill_Chain_Switch` (per Requirement 3) or set `human_review_required=true` on the session, whichever the configured policy specifies.
4. WHEN a key metric's `value` falls outside its `target` tolerance, THE Reality_OS SHALL flag the experiment review with `metric_breach=true` and SHALL surface the breach in the next `Coach_Turn`'s `next_prompt`.
5. IF an `ActionExperiment` has no linked `Concept`s at review time, THEN THE Reality_OS SHALL still persist the structured review and SHALL skip the mastery update without raising an error.

### Requirement 10: Learning Dashboard (P3)

**User Story:** As a learner, I want a single dashboard that shows my mastery heatmap, calibration curve, skill-chain completion rate, and concept decay curves in both Simple and Professional UI modes, so that I can see my progress at a glance and drill in when needed.

#### Acceptance Criteria

1. THE Reality_OS SHALL extend the existing `eval_dashboard` to render four panels: (a) mastery heatmap by domain, (b) calibration curve with Brier score, (c) skill-chain completion rate per `problem_type`, (d) concept decay curves over time.
2. THE web app SHALL expose the dashboard panels under existing `/eval`, `/learn`, and `/dashboard` routes without introducing new top-level routes.
3. WHILE the user is in `Simple_Mode`, THE web app SHALL render at most three primary panels with no parameter controls.
4. WHILE the user is in `Professional_Mode`, THE web app SHALL render all four panels and SHALL expose filters for date range, domain, and skill chain.
5. THE web app SHALL provide all dashboard strings in both `zh-CN` and `en` and SHALL switch language based on the user's settings cookie.
6. WHEN a dashboard panel queries data, THE Reality_OS SHALL scope every query by `Tenant_Id` derived from `current_context(request)`.

### Requirement 11: Pending-Review and Dry-Run Default Writes (Cross-cutting)

**User Story:** As an operator of Reality OS, I want every new write path introduced by this feature to default to pending review or dry-run, so that no automatic formal knowledge writes can leak through the new surface.

#### Acceptance Criteria

1. THE Reality_OS SHALL ensure every new endpoint added by this feature that produces knowledge-like content writes to `pending_knowledge` (or an equivalent reviewed table) with `status="pending_review"` and `formal_knowledge_write=false` by default.
2. THE Reality_OS SHALL NOT auto-promote any `pending_knowledge` record to formal knowledge without an explicit user `approve` action.
3. WHEN a `Coach_Turn` would call any tool flagged `risk="high"` or `risk="medium"`, THE Reality_OS SHALL route the call through `Supervisor_Approval` (existing dry-run + approval pipeline) and SHALL keep tool execution disabled by default.
4. IF an unreviewed `pending_knowledge` record is referenced as supporting evidence in a `DecisionMemo`, THEN THE Reality_OS SHALL refuse to publish the memo verdict until the record is approved.
5. WHEN a write path is added by this feature, THE Reality_OS SHALL declare its mode (`pending-review` or `dry-run`) in the response `metadata.mode` field consistent with the existing `AdapterMetadata` contract.

### Requirement 12: Tenant Isolation (Cross-cutting)

**User Story:** As a tenant of Reality OS, I want every new table, endpoint, and computation to be scoped by my tenant id, so that no other tenant can read, write, or influence my coaching data.

#### Acceptance Criteria

1. THE Reality_OS SHALL include a non-null `tenant_id` column on every new table introduced by this feature (`coaching_sessions`, `expert_rubrics`, `skill_chains_state`, `calibration_records`, `mastery_state`, `metacognition_records`, `experiment_reviews`, and any auxiliary tables).
2. THE Reality_OS SHALL filter every new query by `tenant_id` resolved from `apps/api/security.py::current_context`.
3. IF a request attempts to read or mutate a record belonging to a different `tenant_id`, THEN THE Reality_OS SHALL respond with HTTP 404 and SHALL NOT distinguish "not found" from "forbidden" in the error body.
4. WHEN a `Coach_Turn` follows links between aggregates (session → diagnosis → experiment → review → decision), THE Reality_OS SHALL enforce that every link target shares the same `tenant_id` as the session.

### Requirement 13: Audit Logging of State Transitions (Cross-cutting)

**User Story:** As an operator, I want every coaching state transition, mastery update, calibration record, and rubric check to be appended to the audit log, so that I can reconstruct what the agent did and why.

#### Acceptance Criteria

1. WHEN a `Coaching_Session` transitions between any two states of the `Coaching_State_Machine`, THE Reality_OS SHALL append an `Audit_Log` event with `event_type="coaching_session_transition"` containing `from_state`, `to_state`, `session_id`, `tenant_id`, `actor`, and `reason`.
2. WHEN a `Concept.mastery_score` is updated by SM-2 or by decay recomputation, THE Reality_OS SHALL append an `Audit_Log` event with `event_type="mastery_update"` containing concept id, prior and next values, source (`practice|decay|experiment_review`), and `tenant_id`.
3. WHEN a calibration record is captured (prediction or outcome), THE Reality_OS SHALL append an `Audit_Log` event with `event_type="calibration_record"`.
4. WHEN an `Expert_Rubric` is loaded, refused, or applied, THE Reality_OS SHALL append an `Audit_Log` event with `event_type="rubric_check"` including `rubric_version` and the loaded `cited_evidence_ids`.
5. THE Audit_Log entries added by this feature SHALL be readable through the existing `/security/audit-log` endpoint and SHALL preserve the existing `redacted=true` default.

### Requirement 14: i18n and UI Mode Compliance (Cross-cutting)

**User Story:** As a user, I want every new user-visible string to render correctly in either `zh-CN` or `en`, and I want Simple and Professional UI modes to remain consistent across the new surfaces, so that the language and density preferences I set still apply.

#### Acceptance Criteria

1. THE Reality_OS SHALL provide every new user-visible string in both `zh-CN` and `en` source bundles, with no string defaulting to one language only.
2. WHEN the language preference is set to `zh-CN`, THE web app SHALL render all new dashboard, coach, learn, decision, and reflection strings in Chinese.
3. WHEN the language preference is set to `en`, THE web app SHALL render the same surfaces in English with parity.
4. THE web app SHALL render new feature surfaces in both `Simple_Mode` and `Professional_Mode` with the same density rules already applied to existing surfaces (Simple_Mode hides advanced parameter panels).
5. THE Reality_OS SHALL keep EARS keywords (`WHEN`, `IF`, `THEN`, `SHALL`, `WHILE`, `WHERE`) untranslated in any rendered requirement traceability surface.

### Requirement 15: Server-Only Secrets and Tool Execution Defaults (Cross-cutting)

**User Story:** As an operator, I want the existing server-only secrets policy and the disabled-by-default tool execution policy to remain unchanged, so that this feature cannot weaken the security baseline.

#### Acceptance Criteria

1. THE Reality_OS SHALL keep `REALITY_OS_API_KEY` / `REALITY_OS_SERVER_API_KEY` server-only and SHALL NOT expose them to the web app or extension by this feature.
2. THE Reality_OS SHALL leave tool execution disabled by default and SHALL keep `Supervisor_Approval` as the only path for `risk="high"` actions.
3. IF a configuration would expose a secret to the client bundle, THEN THE Reality_OS SHALL refuse to start and SHALL log the misconfiguration to `Audit_Log`.

### Requirement 16: Legacy Preservation (Cross-cutting)

**User Story:** As an operator, I want the legacy projects under `legacy/` to remain unchanged by this feature, so that old systems stay independently runnable.

#### Acceptance Criteria

1. THE Reality_OS SHALL NOT modify any file under `legacy/` as part of implementing this feature.
2. THE Reality_OS SHALL NOT introduce any runtime dependency from new modules into `legacy/` code paths.
3. WHERE the new feature needs data shaped like a legacy artifact, THE Reality_OS SHALL read it through an adapter (mock-safe or read-only) consistent with the existing `AdapterMetadata` contract.

### Requirement 17: Property-Based Testing Coverage (Cross-cutting)

**User Story:** As an engineer maintaining this feature, I want pure functions of the coaching loop covered by property-based tests, so that algorithmic invariants are protected against regressions.

#### Acceptance Criteria

1. THE Reality_OS SHALL provide a property-based test asserting that `sm2_update(grade, prev_state)` always returns `next_due_at >= prev_state.last_practiced_at` and `decay_lambda > 0` for any `grade ∈ {0..5}` and any valid `prev_state`.
2. THE Reality_OS SHALL provide a property-based test asserting that `brier_score(predictions, outcomes) ∈ [0.0, 1.0]` and equals 0.0 when every prediction matches its outcome, for any non-empty input lists of equal length.
3. THE Reality_OS SHALL provide a property-based test asserting `decay(mastery, lambda, dt)` is monotonically non-increasing in `dt` for any `mastery ∈ [0, 1]` and any `lambda > 0`.
4. THE Reality_OS SHALL provide a property-based test asserting that any `Skill_Chain_Switch` produced by the transition function lands on a chain whose `entry_conditions` evaluate true under the current session state.
5. THE Reality_OS SHALL provide a property-based test asserting that the per-bin empirical frequency of the calibration curve lies in `[0.0, 1.0]` and that bin counts sum to the total number of reviewed predictions.
6. THE Reality_OS SHALL provide a property-based test asserting the closure of `Active_Evidence_Gathering`: starting from any state with `insufficient_evidence=true`, the sequence `search → pending → approve` SHALL drive the linked `DecisionLog` to a state where `verdict` may be issued, and any sequence ending without an `approve` SHALL leave `verdict` unissued.
7. THE Reality_OS SHALL keep PBT execution time bounded so that the suite runs in CI without exceeding the existing pytest budget; tests using external services SHALL use mocks.

### Requirement 18: Configurable Model and Embedding Strategy (Cross-cutting)

**User Story:** As an operator, I want model selection, embedding mode, and online/offline strategy to be configurable per environment, so that I can run Reality OS in offline, local-only, or full-cloud modes without code changes.

#### Acceptance Criteria

1. THE Reality_OS SHALL document new env vars `REALITY_OS_VECTOR_STORE` and `REALITY_OS_EMBED_MODE` in `.env.example` with safe defaults (`sqlite_tfidf`, `disabled`).
2. WHEN model registry slots `generator`, `verifier`, `classifier`, `embedder` are unconfigured, THE Reality_OS SHALL fall back to deterministic logic for `Coach_Turn`, `_check_expert_gap`, problem classification, and retrieval respectively without raising errors.
3. WHEN `REALITY_OS_EMBED_MODE=offline`, THE Reality_OS SHALL not initiate any outbound network call to embedding providers and SHALL not block startup.
4. THE Reality_OS SHALL continue to mask API keys in any model-config response (existing `to_dict(mask_key=True)` behavior preserved).
