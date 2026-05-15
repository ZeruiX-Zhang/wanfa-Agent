# Requirements Document

## Introduction

Unified Reality OS is the merged product of `KnowDo` (Knowledge Delegation Agent) and `reality-os` (which itself merged `sou`, `prompt-agent`, `work`). It is not a chatbot. It is a reality-augmentation system that helps a single user make higher-quality real-world judgments by combining personal knowledge lifecycle management, thinking-model-driven decision memos, claim-evidence verification, and supervised Agent execution.

The system runs in three form factors (Desktop, Web, Browser Extension) against a shared backend, and exposes one core loop:

Reality Input → Clarification → Hybrid Retrieval → Thinking-Model Analysis → Decision Memo → Claim Verification → Agent Execution Supervision → User Approval → Pending-Review Knowledge Write → Reflection / Learning.

Design intent the requirements must preserve:

- "Assist, do not replace". The system surfaces top-tier knowledge, expert thinking models, and authoritative sources so a non-expert user can reach expert-level judgment. The user remains the final decision-maker.
- "Verification strictness". The system treats model self-confidence as insufficient evidence. Correctness is approached through layered verification (claim → evidence → authority → user approval), not asserted.
- "Supervised execution". External skill agents (Codex, Claude Code, browser agents, image/video/PPT generators, file editors) are usable only through a gated, audited, permissioned tool gateway with plan-execution alignment checks, step-level approval, and rollback.
- "Raw source is immutable". All derived artifacts (chunks, summaries, Wiki pages, claims, evidence, embeddings, learning cards, decision memos) must remain regenerable from raw sources, and no unverified claim may be written into the formal knowledge base.
- "V1 skeleton + V2 control systems preserved". KnowDo's V1 (Capture → Ingest → Structure → Store → Retrieve → Learn → Use → Feedback) and V2 (Context Engine, Quality Gate, Permissions, Observability, Authority Check, Compression/Decompression, Source Priority, Coverage Matrix, Subagent Context Isolation) must survive the merge.
- "Merge, don't fork". `sou` (search/evidence), `prompt-agent` (prompt optimization + extension + review queue), `work` (RAG + verification + workflow + supervisor + evals), and `KnowDo` (knowledge lifecycle + wiki + learning) are unified behind one identity, one permission model, one trace, one knowledge graph, reachable from Desktop/Web/Extension.

A placeholder section for design-phase correctness properties is reserved at the end of this document.

## Glossary

- **Reality_OS**: The unified product as a whole, composed of the frontends (`Desktop_App`, `Web_App`, `Browser_Extension`), the backend services, and the knowledge store.
- **Desktop_App**: Tauri + React desktop client. Local-first capture, full admin, supervisor console.
- **Web_App**: Browser-hosted shell that exposes the same core loop as Desktop for remote access.
- **Browser_Extension**: Browser-side capture + quick-ask surface that forwards input into `Reality_OS` through the API.
- **Reality_Input**: Any user-provided signal of the real situation: text, file, URL, screenshot, image, audio, clipboard, highlighted page region.
- **Clarification_Engine**: The component that turns `Reality_Input` into a well-formed question with explicit goal, success criteria, constraints, and missing-information list.
- **Retrieval_Engine**: Hybrid retriever supporting BM25, vector search, metadata filter, graph traversal, structured-table query, and permission filter.
- **Context_Engine**: V2 component that decides what enters the model context under a token budget, using `Source_Priority`, `Coverage_Matrix`, compression and decompression.
- **Source_Priority**: User-assigned priority per source: Critical, High, Normal, Low, Ignore.
- **Coverage_Matrix**: A structured grid tracking, per analytical dimension, which sources were retrieved, coverage score, evidence quality, missing evidence, authority conflicts, and recommendation.
- **Thinking_Model_Library**: Curated collection of mental models (e.g., first-principles, second-order effects, inversion, base rates, expected value, Bayesian update, Cynefin, OODA, SWOT) selectable by the system or user.
- **Decision_Memo**: A structured document that records goal, options considered, thinking models applied, claims, evidence, risks, unknowns, recommendation, confidence, and next actions.
- **Claim**: An atomic factual or evaluative statement extracted from a source, answer, or memo.
- **Evidence**: A span of a raw source that supports, contradicts, or qualifies a `Claim`, with stable source/chunk/span pointers.
- **Authority_Checker**: Component that compares claims against trusted sources, flags outdated or disputed claims, and routes them to the user review queue. It does not silently rewrite knowledge.
- **Quality_Gate**: Component that assigns a `Quality_Score` across multiple dimensions and drives expand / decompress / authority-check / user-intervention policies.
- **Quality_Score**: Multi-dimensional score covering Goal Fit, Evidence Coverage, Source Authority, Citation Grounding, Conflict Risk, Recency Fit, Retrieval Sufficiency, User Priority Match, Answer Completeness, Permission Safety.
- **Tool_Gateway**: The only sanctioned channel through which `Reality_OS` may invoke external skill agents (Codex, Claude Code, browser agents, image/video/PPT generators, file editors, shell).
- **Skill_Agent**: An external executor invoked through `Tool_Gateway` (e.g., Codex, Claude Code).
- **Execution_Plan**: A structured, ordered list of intended `Tool_Gateway` steps produced before execution.
- **Supervisor**: Component that enforces plan-execution alignment, step approval, violation interception, and rollback on every `Skill_Agent` action.
- **Step_Audit_Record**: A persisted, append-only record of one executed step: plan reference, inputs, outputs, permission result, user approval, rollback pointer.
- **Raw_Source_Store**: The immutable local store of original captured artifacts. Derived artifacts live elsewhere and must be regenerable from here.
- **Pending_Review_Store**: Holding area for knowledge proposed by the system or user but not yet accepted into the formal knowledge base.
- **Formal_Knowledge_Base**: The accepted knowledge layer (Wiki + KnowledgeObjects + Claims + Evidence) that retrieval and decision memos rely on.
- **Wiki**: Markdown-based compiled knowledge layer with citations, backlinks, versioning, conflict markers, and generation metadata. It is not the raw source of truth.
- **Reflection_Engine**: Component that produces post-task retrospectives and drives the learning loop (mastery tracking, flashcards, quizzes, mistake log).
- **Permission_Policy**: RBAC + ACL + ABAC metadata attached to every source, folder, Wiki page, chunk, claim, evidence item, citation, and tool invocation.
- **Trace_Event**: Append-only observability record emitted at every major step (capture, ingest, retrieve, context compile, verify, memo, supervise, reflect) containing inputs, outputs, sources used, quality score, permission check, tokens, latency, cost, errors.
- **Legacy_Adapter**: Read-only adapter that exposes data from `legacy/sou`, `legacy/prompt-agent`, `legacy/work`, `legacy/study` (SQLite, Markdown, JSONL, YAML) so migration can happen behind a feature flag.
- **Dual_Run_Mode**: Operating mode where a request is answered by both the legacy path and the unified path and the two responses are compared for regression.

## Requirements

### Requirement 1: Unified Multi-Surface Access and Identity

**User Story:** As a single primary user of Reality OS, I want Desktop, Web, and the Browser Extension to share one identity, one permission model, and one knowledge base, so that I can capture on one surface and decide on another without re-syncing.

#### Acceptance Criteria

1. THE Reality_OS SHALL expose exactly three client form factors — Desktop_App, Web_App, and Browser_Extension — all routed to one single backend deployment, against the same API major version, the same Permission_Policy store, and the same primary storage.
2. WHEN a user authenticates on any one surface, THE Reality_OS SHALL issue a session token scoped to that surface only, AND SHALL require the user to perform an independent authentication on each of the other two surfaces before they accept requests.
3. THE Reality_OS SHALL require every surface's session token to conform to a single shared token format and SHALL validate every token against the same backend token service regardless of issuing surface.
4. THE Reality_OS SHALL NOT attach an automatic time-based expiration to session tokens, AND SHALL keep a token valid until a user-initiated logout, a server-side revocation, or an explicit capability change invalidates it.
5. WHEN a user or an administrator issues a logout or a revocation for a session, THE Reality_OS SHALL invalidate that session on its issuing surface and SHALL cause subsequent requests bearing the revoked token from any surface to be rejected with an authentication error.
6. THE Reality_OS SHALL evaluate every authenticated request from any surface — excluding only token issuance and token revocation endpoints — against the single Permission_Policy store combining RBAC, ACL, and ABAC, and SHALL reject any request whose subject, resource, or surface attribute does not satisfy the policy.
7. WHEN a capture, Decision_Memo, or Trace_Event is committed on one surface, THE Reality_OS SHALL push the new item to the other authenticated surfaces of the same user over a server-initiated channel (SSE or WebSocket) such that a subsequent fresh read on those surfaces observes the item within 5 seconds under a reference network condition of round-trip latency ≤ 50 ms and bandwidth ≥ 10 Mbps.
8. IF the server-initiated push channel is unavailable, THEN THE Reality_OS SHALL fall back to a standard pull-on-focus path AND SHALL emit a Trace_Event indicating that real-time propagation was degraded for the affected session.
9. IF a surface cannot reach the backend, THEN THE Reality_OS SHALL queue the user's capture, clarification answer, quick-ask request, and approval response locally in strict arrival order up to a maximum of 500 queued items, AND SHALL replay them in the same order once connectivity is restored, using a client-generated request id to guarantee idempotent replay.
10. IF the local offline queue has reached 500 items, THEN THE Reality_OS SHALL block the surface from accepting any new queuable action AND SHALL surface a clear "offline queue full" error to the user until at least one queued item has been replayed or discarded.
11. WHERE the calling surface is the Browser_Extension, THE Reality_OS SHALL permit only the capture, clarification, quick-ask, and approval endpoints AND SHALL reject every other endpoint — including user management, permission assignment, Tool_Gateway configuration, and raw source deletion — at the backend with a 403 response, independently of any client-side UI restriction.
12. THE Reality_OS SHALL NOT implement an application-level account lockout on repeated failed authentication attempts AND SHALL delegate brute-force protection to the underlying identity provider (browser password manager, OS credential store, or platform SSO); every such failed attempt SHALL still be recorded in a Trace_Event.
13. THE Reality_OS SHALL record an authentication Trace_Event for every session start, user-initiated session end, token revocation, and failed authentication attempt, and each such event SHALL carry user_id, surface identifier, timestamp, and success/failure outcome.

### Requirement 2: Multi-Modal Reality Input and Clarification

**User Story:** As a user facing an ambiguous real-world problem, I want to feed text, files, URLs, screenshots, images, and voice to the system and have it restate my problem precisely, so that downstream retrieval and analysis target the right question.

#### Acceptance Criteria

1. THE Reality_OS SHALL accept a Reality_Input of exactly one of the declared modalities {plain text, uploaded file, URL, pasted clipboard content, screenshot, static image, audio recording} and SHALL reject any input whose declared modality is not in this set with an error indicating unsupported modality.
2. WHEN a Reality_Input is accepted, THE Reality_OS SHALL, within a single logical transaction, persist the original bytes to the Raw_Source_Store, create exactly one SourceRecord referencing those bytes by content hash, and return the SourceRecord identifier to the caller before any derived artifact is produced.
3. THE Reality_OS SHALL treat every entry in the Raw_Source_Store as append-only, SHALL set each persisted artifact file to operating-system-level read-only on write, SHALL compute and store a content hash for each artifact, SHALL run a periodic integrity scan that re-verifies each artifact against its stored hash, AND SHALL raise an integrity error and emit a Trace_Event if any artifact's bytes or read-only attribute have changed since write.
4. WHEN an audio Reality_Input is accepted, THE Reality_OS SHALL produce a transcript artifact, attach it to the same SourceRecord as a derived artifact with type "transcript", and SHALL keep the original audio untouched in the Raw_Source_Store.
5. WHEN an image or screenshot Reality_Input is accepted, THE Reality_OS SHALL produce two derived artifacts attached to the same SourceRecord, one of type "extracted_text" and one of type "visual_description", and SHALL keep the original image untouched in the Raw_Source_Store.
6. IF any derived artifact (transcription, text extraction, or visual description) fails or returns empty output, THEN THE Reality_OS SHALL retain the SourceRecord and raw bytes, SHALL mark each failing derived artifact with status "failed" and a machine-readable failure reason, SHALL tag the SourceRecord itself with overall status "degraded" when at least one of its expected derived artifacts failed, AND SHALL NOT present a failed derived artifact as successful downstream.
7. WHEN a Reality_Input is accepted, THE Clarification_Engine SHALL emit exactly one structured clarification object linked to that Reality_Input, containing the fields {goal, success_criteria, constraints, known_facts, unknowns, proposed_clarifying_questions}, where every field is present and each field is either a non-empty value or explicitly marked as "unknown", AND WHERE the unknowns field has no detected items it SHALL be set to the explicit marker "none_detected" rather than left empty so that the "no unknowns" case is distinguishable from the "unfilled" case.
8. THE Reality_OS SHALL NOT initiate any operation that consults content outside the original Reality_Input bytes for that Reality_Input — including Retrieval Layer calls, URL remote fetches, and external model invocations used for transcription, OCR, or captioning — until the clarification object for that Reality_Input has been emitted.
9. IF the Clarification_Engine classifies the clarification object as under-specified according to the declared missing-information rule set, THEN THE Reality_OS SHALL present the proposed_clarifying_questions to the user, AND IF the user explicitly chooses to proceed without answering any clarifying question, THEN THE Reality_OS SHALL allow retrieval to proceed AND SHALL NOT attach any flag, marker, or priority penalty to the resulting SourceRecord or Decision_Memo on the basis of that choice.
10. WHEN the user submits an answer to a clarifying question, THE Reality_OS SHALL create a new clarification object linked to the originating Reality_Input, SHALL set its previous_id field to point to the most recent prior clarification object for that Reality_Input, AND SHALL retain all prior clarification objects in the previous_id chain so the full answer history is reconstructible.
11. THE Reality_OS SHALL record a Trace_Event for each of: Reality_Input acceptance, raw-bytes persistence, derived-artifact creation or failure, clarification-object emission, clarification-gated retrieval block, and clarification update, each Trace_Event referencing the SourceRecord identifier and the clarification-object identifier where applicable.

### Requirement 3: Knowledge Capture, Structuring, Wiki, and Hybrid Retrieval

**User Story:** As a user who accumulates sources over time, I want the system to ingest, structure, and Wiki-ize my knowledge and retrieve it through hybrid search, so that my past findings inform new judgments.

#### Acceptance Criteria

1. WHEN a user submits a capture request and the artifact bytes are successfully persisted in the Raw_Source_Store with a computed content hash, THE Reality_OS SHALL, in the same transaction, create a SourceRecord referencing the artifact by its immutable pointer and recording capture timestamp, capturing user, and source type, and SHALL attach a Permission_Policy to the SourceRecord.
2. IF an artifact with the same content hash already exists in the Raw_Source_Store, THEN THE Reality_OS SHALL reuse both the existing artifact and the existing SourceRecord, SHALL update only that SourceRecord's last-capture timestamp and capturing-user history, and SHALL NOT create a duplicate SourceRecord.
3. IF the artifact write to the Raw_Source_Store fails or attaching a Permission_Policy fails, THEN THE Reality_OS SHALL roll back the capture, SHALL NOT leave any SourceRecord or partially written artifact, and SHALL return an error response with the failure reason.
4. WHEN ingestion succeeds on a SourceRecord, THE Reality_OS SHALL produce exactly one ParsedDocument, at least one KnowledgeObject, zero or more Claims, and at least one Evidence per Claim, and every derived object SHALL carry back-pointers to the SourceRecord as (source_id, chunk_id, original_span).
5. IF any ingestion sub-stage (parsing, structuring, Claim extraction, or Evidence binding) fails for a SourceRecord, THEN THE Reality_OS SHALL land the successfully produced derived objects in the Pending_Review_Store only, SHALL tag them with the failing stage and reason, and SHALL exclude them from default retrieval until the failure is resolved.
6. WHEN a KnowledgeObject enters the Formal_Knowledge_Base or its content changes, THE Reality_OS SHALL enqueue an asynchronous batch recompilation job for every Wiki page that references that KnowledgeObject, SHALL persist the recompiled page with citations, backlinks, last-updated timestamp, generation method, and the unresolved-conflicts list, and SHALL retain the last N prior versions of the page (N configurable) in the page's version history.
7. IF two Claims within the same KnowledgeObject contradict each other, or IF Claims for the same KnowledgeObject come from SourceRecords with conflicting authority, THEN THE Reality_OS SHALL record each conflict as an explicit unresolved-conflict entry on the associated Wiki page listing the conflicting Claims, the involved SourceRecords, and the conflict type, and SHALL NOT silently rewrite either side.
8. WHEN the Retrieval_Engine receives a retrieval request, EACH retriever (BM25, vector, graph, structured-table) SHALL apply the caller's permission filter and Source_Priority filter internally before emitting candidates, and the outer Retrieval_Engine SHALL only merge and rerank the pre-filtered candidates WITHOUT re-running permission or priority filtering at the outer layer.
9. IF the current user lacks read permission on a SourceRecord, THEN every retriever SHALL exclude that SourceRecord and all of its derived chunks, KnowledgeObjects, Claims, and Evidence from its candidate set, AND the Retrieval_Engine SHALL NOT expose that SourceRecord's existence in any form — no title, snippet, highlight, metadata, facet, aggregate count, or error message may reveal it.
10. WHERE a SourceRecord's Source_Priority is Ignore, THE Retrieval_Engine SHALL treat that SourceRecord as nonexistent on the default retrieval path until the user reclassifies it or the caller explicitly sets include_ignored=true, in which case the SourceRecord MAY re-enter the candidate set.
11. WHERE a SourceRecord's Source_Priority is Critical, High, Normal, or Low, THE Retrieval_Engine SHALL use the priority only as an ordering factor in rerank so that higher-priority results appear earlier under equal relevance, AND SHALL NOT allow priority alone to promote a non-relevant item into the returned candidate set.
12. WHEN a RetrievalResult is carried into the model context and used to produce an answer, THE Reality_OS SHALL attach the full citation triple (SourceRecord id, chunk id, original span) to the corresponding assertion in the final output, and IF any element of that triple is missing along the pipeline, THEN THE Reality_OS SHALL refuse to use that snippet in the answer.

### Requirement 4: Context Engineering, Source Priority, Coverage Matrix, Compression

**User Story:** As a user asking complex questions, I want the system to be deliberate about what enters the model context, so that answers are grounded in the right evidence under a finite token budget.

#### Acceptance Criteria

1. WHEN the Reality_OS receives a question-answering request, THE Context_Engine SHALL execute the seven stages Goal_Decomposer → FirstPrinciplesAnalyzer → SourcePrioritySelector → CoverageMatrixBuilder → ContextBudgeter → RetrievalPlanner → ContextPackCompiler in this fixed order, and each stage SHALL execute at most once per request before a ContextPack is produced.
2. WHEN the SourcePrioritySelector stage runs, THE Context_Engine SHALL read the user's effective Source_Priority configuration, SHALL exclude every Ignore-tier SourceRecord from the candidate set entirely, AND SHALL pass the remaining Critical / High / Normal / Low classifications to RetrievalPlanner and ContextPackCompiler as rerank ordering factors only, NOT as a hard pre-retrieval filter.
3. WHEN the Goal_Decomposer stage outputs a sub-question count greater than or equal to 2, THE Context_Engine SHALL set complex_flag = true for the request, SHALL record complex_flag in the Trace_Event, AND SHALL trigger the CoverageMatrixBuilder stage.
4. IF complex_flag is false, THEN THE Context_Engine SHALL skip the CoverageMatrixBuilder stage AND SHALL record coverage_matrix = skipped with the skip reason in the Trace_Event.
5. WHEN the CoverageMatrixBuilder stage runs, THE Context_Engine SHALL build a Coverage_Matrix whose dimensions come from the FirstPrinciplesAnalyzer output, AND EACH dimension SHALL contain the six fields retrieved_sources, coverage_score, evidence_quality, missing_evidence, authority_conflicts, recommendation, WHERE coverage_score and evidence_quality are floats in [0.0, 1.0].
6. WHEN the ContextPackCompiler stage applies Source_Priority as a rerank factor, THE Context_Engine SHALL treat Source_Priority as a tiered sort key — first bucket candidates by tier (Critical → High → Normal → Low), then sort within each tier by relevance score — AND SHALL NOT use a weighted-multiplier formula that could promote a lower-priority item above a higher-priority item on relevance alone.
7. WHEN the ContextPackCompiler compresses source material, THE Reality_OS SHALL write eight fields on the compressed object: source_id, chunk_id, original_span, compression_level, compression_method, created_at, model_used, confidence_score, AND SHALL reject any compressed object that is missing any of these fields from entering the ContextPack.
8. WHEN a downstream task requests higher-fidelity content for a compressed object, THE Context_Engine SHALL resolve it by fetching the referenced original_span from the Raw_Source_Store via source_id, AND SHALL NOT have the model synthesize content that is not present in the Raw_Source_Store.
9. THE ContextBudgeter stage SHALL compute effective_token_budget as (model_context_window − system_prompt_tokens − goal_and_plan_tokens), SHALL keep this budget constant for the duration of the request, AND SHALL persist both effective_token_budget and the chosen tokenizer in the Trace_Event.
10. THE ContextBudgeter stage SHALL obtain its tokenizer from the Model_Gateway's declared tokenizer for the target model, AND IF the Model_Gateway does not declare one, THEN THE ContextBudgeter SHALL fall back to cl100k_base and SHALL record the fallback in the Trace_Event.
11. WHEN a ContextPack is finalized, THE Reality_OS SHALL emit a Trace_Event containing an included_sources list, an excluded_sources list, an exclusion_reason per excluded source drawn from the set {permission_denied, priority_ignore, budget_drop, dedup, quality_filter}, effective_token_budget as an integer, and used_tokens as an integer.
12. IF during assembly the ContextPackCompiler detects that used_tokens will exceed effective_token_budget, THEN THE Context_Engine SHALL drop candidates in the ordering (priority_rank ascending, coverage_contribution ascending, source_id ascending) until used_tokens ≤ effective_token_budget, AND SHALL append one drop record per dropped item to the same Trace_Event capturing source_id, priority_rank, coverage_contribution, and drop_order.
13. WHERE a Critical-tier SourceRecord would otherwise be dropped under the budget-drop rule, THE ContextPackCompiler SHALL first attempt to upgrade its compression_level to a higher compression tier to reduce its token footprint, AND SHALL drop the Critical-tier item only if even the most-compressed form still does not fit, recording the compression-upgrade attempt in the Trace_Event.

### Requirement 5: Thinking Model Library and Decision Memo

**User Story:** As a user facing a complex judgment, I want the system to apply top-tier thinking models and produce a Decision Memo with recommendation and reasons, so that I can decide like an expert with my context preserved.

#### Acceptance Criteria

1. THE Reality_OS SHALL maintain a Thinking_Model_Library where each entry carries: name, when_to_use condition expressed in a machine-evaluable form, required inputs, produced outputs, at least one worked example, and at least one citation resolvable to a SourceRecord.
2. WHEN a Decision_Memo is being generated, THE Reality_OS SHALL first auto-match Thinking_Model_Library entries whose when_to_use condition evaluates true against the decision goal, SHALL propose the matched set (up to 5) to the user as a ranked suggestion, AND SHALL allow the user to add, remove, or reorder entries before the memo is published; the final applied set SHALL be whatever the user confirms.
3. IF the user confirms an empty applied-models set (either because no entry matched and the user did not add any, or because the user removed all matches), THEN THE Reality_OS SHALL mark the memo as "no-model-confirmed, provisional" and SHALL NOT emit a strong recommendation.
4. WHEN a Decision_Memo is generated, THE Reality_OS SHALL populate all of the following fields: goal, options_considered (at least 2 options, or exactly 1 option with an explicit single-option justification), thinking_models_applied, claims, evidence_citations (each resolving to a SourceRecord id and span), risks, unknowns, recommendation, confidence expressed as an integer in [0, 100], and proposed_next_actions (at least 1).
5. IF any field required in AC 4 is empty or unresolved at publication time, THEN THE Reality_OS SHALL reject memo publication AND SHALL return an error identifying which field failed.
6. THE Reality_OS SHALL expose a per-memo display_mode flag whose value is exactly one of {"recommendation_only", "recommendation_with_reasons"}, defaulting to "recommendation_with_reasons", SHALL persist the flag per memo_id, AND SHALL NOT remove stored reasoning fields from the memo when the flag is toggled.
7. WHEN the user toggles display_mode on a memo, THE Reality_OS SHALL apply the change only to that memo_id, SHALL persist the flag in the memo's current version metadata, AND SHALL NOT affect the display_mode of any other memo.
8. WHEN a Decision_Memo is generated, THE Reality_OS SHALL attach an immutable snapshot of the full Quality_Score (all dimensions) from the Quality_Gate AND an immutable snapshot of the Coverage_Matrix from the Context_Engine to that specific memo_version, so that subsequent upstream changes do not mutate historical memo versions.
9. IF the Quality_Score total is below 60, OR the Evidence Coverage dimension is below 60, OR any required dimension in the attached Coverage_Matrix reports coverage_score below 60, THEN THE Reality_OS SHALL mark the memo as "provisional, verification pending" AND SHALL NOT treat it as a verified judgment.
10. WHILE the Quality_Score total is between 60 and 89 inclusive, THE Reality_OS SHALL attach an uncertainty notice to the memo AND SHALL record which Quality_Gate recovery actions (expand retrieval, decompress, subagent review, authority check) were attempted before publication.
11. WHEN the Quality_Score total is at or above 90, THE Reality_OS SHALL allow the memo to be published without a provisional marker AND SHALL still attach the Quality_Score snapshot for audit.
12. WHEN the user accepts a recommendation from a Decision_Memo, THE Reality_OS SHALL write a full snapshot of that memo_version — including goal, options_considered, thinking_models_applied, claims, evidence_citations, risks, unknowns, recommendation, and proposed_next_actions — into the Pending_Review_Store linked to the originating memo_id and memo_version, AND SHALL NOT write any of those items directly into the Formal_Knowledge_Base.
13. IF a Pending_Review_Store item has not received an explicit user approval event recorded in a Trace_Event, THEN THE Reality_OS SHALL NOT promote that item into the Formal_Knowledge_Base regardless of its Quality_Score.
14. WHEN any field of a published Decision_Memo is modified, THE Reality_OS SHALL create a new memo_version under the same memo_id, SHALL preserve the prior version unchanged, AND SHALL record parent_version, changed_fields, editor, and timestamp on the new version.
15. THE Reality_OS SHALL guarantee that for any memo_version, serializing it and then deserializing it yields a payload equivalent to the original over every field listed in AC 4 plus the Quality_Score and Coverage_Matrix snapshots from AC 8, so that a memo_version can serve as a reproducible PBT seed (see Requirement 14).
16. IF a memo_version is referenced by a Pending_Review_Store item or a Formal_Knowledge_Base entry, THEN THE Reality_OS SHALL NOT delete or mutate that memo_version.

### Requirement 6: Claim Extraction, Evidence Binding, Authority Check, Layered Verification

**User Story:** As a user who needs to trust the system's output, I want every non-trivial claim to be extracted, bound to evidence, checked against authoritative sources, and approvable by me, so that conclusions are verifiable rather than asserted.

#### Acceptance Criteria

1. WHEN the Reality_OS produces a Decision_Memo or a final answer, THE Reality_OS SHALL extract atomic Claims from that output and bind each Claim to zero or more Evidence items with stable source/chunk/span pointers.
2. IF a Claim has zero bound Evidence items, THEN THE Reality_OS SHALL mark that Claim as "unsupported" and SHALL expose the marker in the user-facing output.
3. THE Authority_Checker SHALL compare extracted Claims against designated trusted sources and SHALL label each Claim as supported, disputed, outdated, or unknown.
4. IF the Authority_Checker labels a Claim as disputed or outdated, THEN THE Reality_OS SHALL route that Claim to the user review queue and SHALL NOT silently rewrite the Formal_Knowledge_Base.
5. WHEN the user approves a Claim in the review queue, THE Reality_OS SHALL move the approved Claim and its Evidence from the Pending_Review_Store into the Formal_Knowledge_Base and SHALL record the approval in a Trace_Event.
6. WHEN the user rejects a Claim, THE Reality_OS SHALL keep the Claim in the Pending_Review_Store marked as "user-rejected" and SHALL NOT use it in future retrieval as a supporting source.
7. THE Reality_OS SHALL retain the original Claim text, original Evidence spans, and the authority comparison result alongside any later correction, so that verification decisions are auditable.

### Requirement 7: Supervised Agent Execution (Plan → Step → Approve → Audit → Rollback)

**User Story:** As a user delegating file edits, image/video/PPT generation, or code execution to external agents, I want every step to be planned, approved, audited, and rollbackable, so that automation never goes off the rails.

#### Acceptance Criteria

1. WHEN the Reality_OS decides to use a Skill_Agent, THE Reality_OS SHALL first produce an Execution_Plan enumerating ordered steps, each with intended tool, intended inputs, expected outputs, and affected resources.
2. THE Supervisor SHALL compare every executed step against the approved Execution_Plan and SHALL block any step whose tool, inputs, or affected resources diverge from the plan beyond a configured tolerance.
3. WHERE a step is classified as destructive (e.g., overwriting a file, deleting data, sending external messages, making purchases, pushing code), THE Supervisor SHALL require explicit user approval before execution.
4. WHEN a step executes through the Tool_Gateway, THE Reality_OS SHALL persist a Step_Audit_Record containing plan reference, inputs, outputs, permission result, user approval status, timestamp, and a rollback pointer.
5. IF a step violates a tool-whitelist, permission, or policy rule, THEN THE Supervisor SHALL abort the step, record the violation in a Trace_Event, and surface the violation to the user.
6. WHEN the user issues a rollback for an executed step, THE Reality_OS SHALL use the Step_Audit_Record's rollback pointer to revert the change, SHALL verify the revert, and SHALL record the rollback result.
7. IF a rollback cannot be completed safely (e.g., external side effect is irreversible), THEN THE Reality_OS SHALL mark the step as "irreversible", SHALL NOT fabricate a successful rollback, and SHALL surface the irreversibility to the user.
8. THE Reality_OS SHALL allow the user to pause, resume, or cancel any in-flight Execution_Plan at any step boundary.

### Requirement 8: Pending-Review Knowledge Write, Reflection, and Learning Loop

**User Story:** As a user who wants to grow from every decision, I want accepted knowledge to land in a pending-review queue, be reflected upon, and feed my learning, so that the system compounds my judgment over time.

#### Acceptance Criteria

1. WHEN the user accepts a recommendation, a Claim, or a Decision_Memo outcome, THE Reality_OS SHALL write the derived knowledge into the Pending_Review_Store tagged with source memo_id, approving user, and timestamp.
2. THE Reality_OS SHALL NOT admit any item from the Pending_Review_Store into the Formal_Knowledge_Base without an explicit user approval event recorded in a Trace_Event.
3. WHEN a task concludes, THE Reflection_Engine SHALL produce a retrospective covering what worked, what failed, unresolved unknowns, updated mental models, and candidate knowledge updates.
4. THE Reflection_Engine SHALL generate learning artifacts (study notes, flashcards, quiz items, Socratic prompts) from accepted Formal_Knowledge_Base content and SHALL track mastery per topic.
5. WHEN the user reports a mistake or corrects an earlier claim, THE Reflection_Engine SHALL record the correction, link it to the original memo and trace, and surface it during related future tasks.
6. WHERE a topic's mastery is below a configured threshold, THE Reality_OS SHALL prioritize Socratic prompting and spaced review for that topic over direct answers when the user opts into learning mode.

### Requirement 9: External Skill Agent Gateway (Codex, Claude Code, Others)

**User Story:** As a user who wants the system to use external agents like Codex or Claude Code, I want all such use to go through one gateway with permission, audit, and whitelisting, so that no external agent can act outside the rules.

#### Acceptance Criteria

1. THE Reality_OS SHALL route every call to an external Skill_Agent through the Tool_Gateway and SHALL forbid direct calls from other components to external Skill_Agents.
2. THE Tool_Gateway SHALL maintain a whitelist of permitted Skill_Agents, a per-agent capability list, and a per-agent rate limit.
3. WHEN a Skill_Agent call is issued, THE Tool_Gateway SHALL enforce the caller's Permission_Policy against the requested capability before forwarding the call.
4. IF a Skill_Agent request targets a capability outside the whitelist, THEN THE Tool_Gateway SHALL reject the request, SHALL record the rejection in a Trace_Event, and SHALL notify the Supervisor.
5. THE Tool_Gateway SHALL log, per call, the agent name, capability, inputs hash, outputs hash, duration, cost, and permission decision in a Step_Audit_Record linked to the Execution_Plan.
6. WHEN a Skill_Agent returns output that will be consumed by the model context or presented to the user, THE Reality_OS SHALL tag that output with its originating agent and SHALL treat the output as an unverified source subject to Claim extraction and Authority Check.

### Requirement 10: Quality Gate and Uncertainty Disclosure

**User Story:** As a user who is weighing the system's output, I want the system to score answer quality and disclose uncertainty, so that I don't mistake a low-confidence output for a verified one.

#### Acceptance Criteria

1. THE Quality_Gate SHALL compute a Quality_Score on every Decision_Memo and every user-facing final answer.
2. THE Quality_Score SHALL include Goal Fit, Evidence Coverage, Source Authority, Citation Grounding, Conflict Risk, Recency Fit, Retrieval Sufficiency, User Priority Match, Answer Completeness, and Permission Safety.
3. WHEN the Quality_Score is at or above 90, THE Reality_OS SHALL output the answer normally.
4. WHEN the Quality_Score is between 80 and 89 inclusive, THE Reality_OS SHALL output the answer with a visible uncertainty note.
5. WHEN the Quality_Score is between 60 and 79 inclusive, THE Reality_OS SHALL expand retrieval or decompress relevant sources before producing the final answer.
6. WHEN the Quality_Score is between 40 and 59 inclusive, THE Reality_OS SHALL route the task to a subagent review (goal analyst, evidence verifier, or authority checker) before producing the final answer.
7. IF the Quality_Score is below 40, THEN THE Reality_OS SHALL NOT produce a strong conclusion and SHALL report insufficiency with the missing-evidence list.
8. THE Reality_OS SHALL display the Quality_Score and the top contributing dimensions to the user on every Decision_Memo and final answer.

### Requirement 11: Observability and Trace Events

**User Story:** As a user who needs to audit or replay what the system did, I want every major step to emit a trace event I can inspect, so that nothing happens invisibly.

#### Acceptance Criteria

1. THE Reality_OS SHALL emit a Trace_Event for every major step: capture, ingest, structure, retrieve, context compile, verify, memo, supervise step, reflect.
2. EACH Trace_Event SHALL include trace_id, task_id, user_id, agent_name, step_name, input_summary, output_summary, tool_calls, retrieval_queries, sources_used, quality_score, permission_checked, tokens, latency_ms, cost, errors, and created_at.
3. THE Reality_OS SHALL expose a trace viewer that lets the user browse a trace by task_id, filter by step_name, and open any Step_Audit_Record.
4. WHEN the user requests a replay of a past task, THE Reality_OS SHALL reproduce the retrieval results and ContextPack decisions from the stored Trace_Events and SHALL mark any step whose inputs can no longer be reconstructed.
5. THE Reality_OS SHALL NOT write secrets or API keys into Trace_Event fields, and SHALL redact any candidate secret values before persistence.

### Requirement 12: Security, Permissions, and Raw Source Policy

**User Story:** As a user storing sensitive sources and delegating execution, I want strict permissions, immutable raw sources, and sandboxed execution, so that the system is safer than a generic AI assistant.

#### Acceptance Criteria

1. THE Reality_OS SHALL attach a Permission_Policy to every source, folder, Wiki page, chunk, Claim, Evidence item, citation, Decision_Memo, and Tool_Gateway invocation.
2. THE Reality_OS SHALL enforce the Permission_Policy at every stage: capture, ingestion, indexing, retrieval, context compilation, citation generation, export, deletion, and tool execution.
3. THE Raw_Source_Store SHALL be append-only from the application's perspective, and THE Reality_OS SHALL NOT overwrite or delete a raw source as part of a derived-object update.
4. WHERE a user exports knowledge, THE Reality_OS SHALL re-check the Permission_Policy on every included source and SHALL exclude any source the user lacks permission to export.
5. WHEN the Reality_OS executes a shell, file, or code operation through Tool_Gateway, THE Reality_OS SHALL run the operation inside a sandbox and SHALL confine file-system access to explicitly granted paths.
6. IF a component attempts to bypass the Permission_Policy, THEN THE Reality_OS SHALL deny the operation, record a Trace_Event with reason "permission bypass attempt", and surface the event to the user.
7. THE Reality_OS SHALL redact candidate secret values from logs, Trace_Events, model context, and exports before persistence.

### Requirement 13: Legacy Adapter and Dual-Run Migration

**User Story:** As a user migrating from the old `sou` / `prompt-agent` / `work` / `KnowDo` stacks, I want the unified system to read legacy data through adapters and optionally dual-run legacy and unified paths, so that migration is gradual and verifiable.

#### Acceptance Criteria

1. THE Reality_OS SHALL provide Legacy_Adapters that expose legacy SQLite, Markdown, JSONL, and YAML artifacts under `legacy/` as read-only sources retrievable by the Retrieval_Engine.
2. THE Reality_OS SHALL NOT modify, rename, or delete files under `legacy/` as part of adapter operation.
3. WHERE Dual_Run_Mode is enabled for a request, THE Reality_OS SHALL execute both the legacy path and the unified path, SHALL present the unified response as primary, and SHALL attach a diff summary of the two responses to the Trace_Event.
4. WHEN a legacy capability has a passing unified replacement under test, THE Reality_OS SHALL allow disabling the legacy adapter for that capability behind a feature flag.
5. IF a legacy adapter fails to read a legacy artifact, THEN THE Reality_OS SHALL record the failure in a Trace_Event and SHALL continue serving the request from the unified path without crashing.

### Requirement 14: Parsers, Serializers, and Round-Trip Integrity

**User Story:** As a user relying on the system to parse and reproduce Decision Memos, Wiki pages, and Trace Events, I want parsers and pretty-printers that round-trip losslessly, so that data does not silently mutate as it moves through the system.

#### Acceptance Criteria

1. THE Reality_OS SHALL provide a Decision_Memo parser that converts a serialized memo into an in-memory Decision_Memo object.
2. THE Reality_OS SHALL provide a Decision_Memo pretty printer that converts an in-memory Decision_Memo object into its serialized form.
3. FOR ALL in-memory Decision_Memo objects produced by the parser, pretty-printing then parsing SHALL produce an equivalent Decision_Memo object (round-trip property).
4. THE Reality_OS SHALL provide a Wiki page parser and a Wiki page pretty printer, and FOR ALL Wiki pages the Reality_OS produces, parsing then pretty-printing then parsing SHALL produce an equivalent Wiki page.
5. THE Reality_OS SHALL provide a Trace_Event serializer and deserializer, and FOR ALL Trace_Events the Reality_OS emits, serializing then deserializing SHALL produce an equivalent Trace_Event.
6. IF a serialized Decision_Memo, Wiki page, or Trace_Event is invalid, THEN the corresponding parser SHALL return a descriptive error instead of a partially constructed object.

### Requirement 15: Success Metrics Reporting

**User Story:** As a user steering the product's evolution, I want the system to report key success metrics, so that I can tell whether verification, adoption, traceability, and rollback are actually working.

#### Acceptance Criteria

1. THE Reality_OS SHALL compute and expose a verification-pass rate, defined as the fraction of Claims that reached "supported" status after Authority Check and user review, over a user-selected window.
2. THE Reality_OS SHALL compute and expose a user-adoption rate, defined as the fraction of Decision_Memo recommendations the user accepted, over a user-selected window.
3. THE Reality_OS SHALL compute and expose a Trace_Event completeness rate, defined as the fraction of major steps whose Trace_Event is present and includes all required fields, over a user-selected window.
4. THE Reality_OS SHALL compute and expose a Quality_Gate coverage rate, defined as the fraction of user-facing final answers and Decision_Memos that carry a Quality_Score.
5. THE Reality_OS SHALL compute and expose a rollback-success rate, defined as the fraction of rollback requests whose revert verification succeeded, over a user-selected window.
6. WHEN any of the above rates drops below a user-configured threshold, THE Reality_OS SHALL surface the drop in the observability dashboard and SHALL record a Trace_Event of type "metric_regression".

## Non-Goals

The following are explicitly out of scope for this feature. The system SHALL NOT claim or attempt to deliver them:

1. Autonomous replacement of the human decision-maker. The system assists judgment; it does not commit high-stakes decisions on the user's behalf without approval.
2. Direct write of unverified claims into the Formal_Knowledge_Base. All knowledge writes go through the Pending_Review_Store and require an explicit approval event.
3. Unsupervised external agent execution. No Skill_Agent may act outside the Tool_Gateway, the Execution_Plan, and the Supervisor's approval and audit flow.
4. Any guarantee of absolute correctness. The Quality_Gate reports confidence and sufficiency, not truth; the system uses layered verification to approach correctness, not assert it.
5. Silent rewriting of Wiki pages, Claims, or Evidence by the model or the Authority_Checker. Corrections are proposals that require user review.
6. Multi-tenant / organization-scale rollout. The current scope is a single primary user with optional restricted roles; org-wide admin and billing are deferred.
7. Full offline operation for cloud-only Skill_Agents. Clients may queue captures offline, but executing a cloud-hosted Skill_Agent requires connectivity.
8. Full legacy migration in one step. Legacy paths remain reachable through Legacy_Adapters and Dual_Run_Mode until unified replacements are accepted.

## Correctness Properties (reserved for Design phase)

This section is a placeholder. During the design phase, each acceptance criterion above will be classified as "yes - property", "yes - example", "edge-case", or "not testable", and the following property families will be enumerated with concrete targets:

- Invariants: permission-enforced retrieval never returns a source the caller cannot read; Raw_Source_Store is append-only; a Decision_Memo with Quality_Score < 40 never emits a strong conclusion.
- Round-trip: Decision_Memo parse/print, Wiki parse/print, Trace_Event serialize/deserialize.
- Idempotence: re-ingesting the same SourceRecord does not create duplicate KnowledgeObjects; re-approving an already-approved Claim is a no-op; replaying the same Execution_Plan at the same step boundary is a no-op.
- Metamorphic: adding a strictly-lower-priority source never removes a higher-priority source from the ContextPack; tightening permissions never enlarges the retrieval result set.
- Model-based: the Supervisor's plan-execution comparison against a reference interpreter rejects every divergent step.
- Confluence: the order of independent Claim approvals does not change the final Formal_Knowledge_Base state.
- Error conditions: invalid serialized memos/wiki/trace inputs produce descriptive errors; violation of tool whitelist aborts with an auditable reason.

Concrete property statements, their PBT vs example-test classification, and the test harness choice will be finalized in `design.md`.
