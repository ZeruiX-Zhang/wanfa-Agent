# Implementation Plan: expert-coaching-loop

This plan delivers `expert-coaching-loop` as five flag-gated milestones (M0–M5) so each priority group (P0/P1/P2/P3) can be dark-launched independently.

## Tasks

- [x] 1. M0 — Schema and scaffolding (no behavior change; flags default off)

  - [x] 1.1 Add additive SQLite migration for new coaching tables
    - Target: `apps/api/app/knowledge_core.py` (extend `_init_schema`), new `apps/api/app/coaching_schema.py`
    - Create tables: `coaching_sessions`, `coaching_session_state_log`, `skill_chains_state`, `expert_rubric_versions`, `calibration_records`, `mastery_history`, `metacognition_records`, `experiment_reviews`, `hybrid_retrieval_weights`, `evidence_gathering_tasks`, `concept_prerequisites`. All `tenant_id NOT NULL`.
    - AC (unit test): `tests/test_coaching_schema.py::test_schema_creates_all_tables_idempotent`
    - _Requirements: 12.1, 16.1_

  - [x] 1.2 ALTER `concepts` table for SM-2 fields (additive `ADD COLUMN`)
    - Target: `apps/api/app/knowledge_core.py`
    - Add columns: `mastery_score, last_practiced_at, next_due_at, decay_lambda, ef, repetition, interval_days, domain` with safe defaults
    - AC: `tests/test_coaching_schema.py::test_concept_columns_present_with_defaults`
    - _Requirements: 5.1, 5.6_

  - [x] 1.3 ALTER `knowledge_items` table to add `vector BLOB` column
    - Target: `apps/api/app/vector_store.py` (`ensure_vector_column()` helper)
    - AC: `tests/test_coaching_schema.py::test_knowledge_items_vector_column`
    - _Requirements: 8.1_

  - [x] 1.4 Feature-flag reader module
    - Target: new `apps/api/app/feature_flags.py`
    - Expose: `coach_enabled()`, `expert_gap_enabled()`, `hybrid_retrieval_enabled()`, `embed_mode()`, `coach_idle_days()`, `calibration_threshold()`, `coach_autoswitch()`
    - AC: `tests/test_feature_flags.py::test_defaults_all_off`
    - _Requirements: 18.1, 15.2_

  - [x] 1.5 Update `.env.example` with new envs and flags
    - Target: `.env.example`
    - Add: `REALITY_OS_VECTOR_STORE=sqlite_tfidf`, `REALITY_OS_EMBED_MODE=disabled`, `REALITY_OS_COACH_ENABLED=false`, `REALITY_OS_HYBRID_RETRIEVAL=false`, `REALITY_OS_EXPERT_GAP_ENABLED=false`, `REALITY_OS_COACH_AUTOSWITCH=false`, `REALITY_OS_CALIBRATION_THRESHOLD=0.6`, `REALITY_OS_COACH_IDLE_DAYS=30`
    - AC: `tests/test_smoke_env_example.py::test_env_example_contains_new_keys`
    - _Requirements: 8.5, 18.1_

  - [x] 1.6 Audit event_type catalog constants
    - Target: new `apps/api/app/audit_events.py`
    - Constants for all event types per design Audit catalog
    - AC: `tests/test_audit_events.py::test_event_type_catalog_complete`
    - _Requirements: 13.1-4_

  - [x] 1.7 AdapterMetadata mode helper for new endpoints
    - Target: `apps/api/schemas.py` (extend) or new helper in `apps/api/app/adapter_metadata.py`
    - `make_metadata(adapter, source_system, mode, read_only)`
    - AC: `tests/test_adapter_metadata.py::test_mode_validation_rejects_unknown`
    - _Requirements: 11.5_

  - [x] 1.8 Mastery backfill CLI script (idempotent)
    - Target: new `apps/api/app/mastery_backfill.py`
    - Sets `mastery_score=0.5, decay_lambda=0.05` on existing concepts where null
    - AC: `tests/test_mastery_backfill.py::test_backfill_idempotent_skips_already_set`
    - _Requirements: 5.1_

  - [x] 1.9 Startup misconfiguration guard for server-only secrets
    - Target: `apps/api/main.py` (extend startup), `apps/api/app/feature_flags.py`
    - Refuses to start and logs `system.misconfiguration` audit
    - AC: `tests/test_startup_guard.py::test_startup_refuses_when_secret_exposed`
    - _Requirements: 15.1, 15.3_

- [x] 2. M1 — P0 (Coaching Session, Expert Rubric, Skill Chain) gated by `REALITY_OS_COACH_ENABLED` and `REALITY_OS_EXPERT_GAP_ENABLED`

  - [x] 2.1 CoachingSession aggregate + repository
    - Target: new `apps/api/app/coaching_session.py`
    - `CoachingSession` dataclass, `CoachingSessionRepo.get_or_create / with_lock / load`, all queries `WHERE tenant_id = ?` first
    - AC: `tests/test_coaching_session.py::test_repo_get_or_create_creates_session_when_id_missing`
    - _Requirements: 1.1, 1.4, 1.10_

  - [x] 2.2 State machine transition validator (`ALLOWED` map)
    - Target: `apps/api/app/coaching_session.py`
    - `transition(session_id, to_state, reason, actor)`; rejects undeclared with `ValueError`; emits `coaching_session_transition` audit
    - AC (PBT): `tests/property/test_coaching_state_machine_pbt.py::test_property_1_state_machine_validity`
    - _Requirements: 1.2; Property 1_

  - [x] 2.3 PBT — coaching session round-trip persistence (Property 2)
    - Target: new `tests/property/test_coaching_session_pbt.py`
    - AC: `test_property_2_session_round_trip`
    - _Requirements: 1.8; Property 2_

  - [x] 2.4 Idle archival + archived read-allow / write-reject
    - Target: `apps/api/app/coaching_session.py`
    - `archive_idle(idle_days)`; archived sessions return 409 on writes; reads still succeed
    - AC: `tests/property/test_coaching_state_machine_pbt.py::test_property_3_idle_archival`, `test_property_4_archived_read_allow_write_reject`
    - _Requirements: 1.6, 1.7; Properties 3, 4_

  - [x] 2.5 next_action decision table
    - Target: `apps/api/app/coaching_session.py`
    - `decide_next_action(session_snapshot)` per design table
    - AC: `tests/property/test_next_action_pbt.py::test_property_6_next_action_table`
    - _Requirements: 1.5, 4.5; Property 6_

  - [x] 2.6 Expert Rubric loader + YAML schema validation
    - Target: new `apps/api/app/expert_rubric.py`; new YAMLs `apps/api/expert_rubrics/{default,general_decision,technology,finance}.yaml`
    - Validates required fields; refuses + audits on invalid; keeps prior versions readable
    - AC (PBT): `tests/property/test_rubric_loader_pbt.py::test_property_7_rubric_loader_robustness`
    - AC (unit): `tests/test_rubric_yaml_schema.py::test_all_shipped_rubrics_validate`
    - _Requirements: 2.1, 2.5, 2.6, 2.7; Property 7_

  - [x] 2.7 `expert_gap_score` pure function
    - Target: `apps/api/app/expert_rubric.py`
    - Anchor-presence ratio × dimension weight; `missing_points` capped at 7
    - AC (PBT): `tests/property/test_expert_gap_pbt.py::test_property_8_expert_gap_bounds`
    - _Requirements: 2.2, 2.3; Property 8_

  - [x] 2.8 `_check_expert_gap` audit dimension wiring
    - Target: `apps/api/app/audit_agent.py`
    - On rubric load failure, fall back to existing 5 dimensions
    - AC: `tests/test_audit_expert_gap.py::test_audit_includes_expert_gap_dimension_when_flag_on`, `::test_falls_back_to_5_dims_when_rubric_missing`
    - _Requirements: 2.2, 2.3, 2.5_

  - [x] 2.9 Skill chain loader + YAML schema validation
    - Target: new `apps/api/app/skill_chain.py`; new YAMLs `apps/api/thinking_skills/chains/{general_decision,troubleshooting,product_strategy}.yaml`
    - Validates every `skill_id` resolves; refuses to start otherwise
    - AC: `tests/test_skill_chain_loader.py::test_loader_validates_skill_ids`, `::test_general_decision_chain_present`
    - _Requirements: 3.1, 3.6, 3.7_

  - [x] 2.10 `select_chain` + `transition` pure functions
    - Target: `apps/api/app/skill_chain.py`
    - Entry/exit predicate evaluation, advance, switch policy
    - AC (PBT): `tests/property/test_skill_chain_pbt.py::test_property_9_chain_transition_validity`
    - _Requirements: 3.3, 3.4, 3.5; Property 9_

  - [x] 2.11 RealityAdvisor: skill_chain integration (additive)
    - Target: `apps/api/app/reality_advisor.py`
    - Add `skill_chain: SkillChainState | None` field to `AdvisorResponse`
    - AC: `tests/test_advisor_skill_chain.py::test_advise_returns_skill_chain_state`
    - _Requirements: 3.2_

  - [x] 2.12 Extend `orchestrated_ask` with coach-turn parameters
    - Target: `apps/api/app/orchestrator.py`
    - Add `coaching_session_id`, `coach_turn=False`, `user_confidence_check`
    - AC: `tests/test_orchestrator_coach.py::test_coach_turn_extends_orchestrated_ask_without_breaking_legacy_ask`
    - _Requirements: 1.9_

  - [x] 2.13 `POST /api/v2/coach/turn` endpoint
    - Target: `apps/api/app/v2.py` (extend), `apps/api/schemas.py` (`CoachTurnRequest/CoachTurnResponse`)
    - AC: `tests/test_coach_turn_endpoint.py::test_post_coach_turn_zhCN`, `::test_post_coach_turn_en`
    - _Requirements: 1.3, 1.4, 1.10, 11.5_

  - [x] 2.14 `GET /api/v2/coach/sessions/{id}` and `POST /api/v2/coach/sessions/{id}/archive`
    - Target: `apps/api/app/v2.py`
    - AC: `tests/test_coach_session_endpoints.py::test_get_session_tenant_scoped`, `::test_archive_session_writes_audit`
    - _Requirements: 1.7, 12.3_

  - [x] 2.15 Admin `POST /api/v2/rubrics/check` (dry-run) and `GET /api/v2/rubrics`
    - Target: `apps/api/app/v2.py`
    - AC: `tests/test_rubrics_endpoints.py::test_rubrics_check_returns_dry_run_metadata`, `::test_get_rubrics_lists_versions`
    - _Requirements: 2.6, 11.5_

  - [x] 2.16 i18n bundle additions: coach / rubric / skill-chain strings
    - Target: `apps/web/lib/i18n.ts`
    - AC: `tests/test_i18n_parity.py::test_coach_keys_zh_en_parity`
    - _Requirements: 14.1-3_

  - [x] 2.17 Wire feature flag `REALITY_OS_COACH_ENABLED`
    - Target: `apps/api/main.py`, `apps/api/app/v2.py`
    - Coach routes 404 when flag off
    - AC: `tests/test_flag_coach_enabled.py::test_routes_404_when_flag_off`, `::test_routes_active_when_flag_on`
    - _Requirements: rollout plan_

  - [x] 2.18 Wire feature flag `REALITY_OS_EXPERT_GAP_ENABLED`
    - Target: `apps/api/app/audit_agent.py`
    - When off, audit runs 5 dimensions only
    - AC: `tests/test_flag_expert_gap.py::test_audit_skips_6th_dim_when_flag_off`
    - _Requirements: 2.5, rollout plan_

  - [x] 2.19 Audit event emission for P0 state changes
    - Target: `apps/api/app/coaching_session.py`, `apps/api/app/expert_rubric.py`, `apps/api/app/skill_chain.py`
    - AC: `tests/test_audit_events_p0.py::test_p0_audit_events_emitted_with_documented_keys`
    - _Requirements: 13.1, 13.4_

- [x] 3. M2 — P1 (Calibration Loop, SM-2 Mastery, Active Evidence Gathering)

  - [x] 3.1 `mastery.py`: `MasteryState`, `sm2_update`, `decay`
    - Target: new `apps/api/app/mastery.py` (pure, no I/O)
    - AC (PBT): `tests/property/test_mastery_pbt.py::test_property_10_sm2_invariants`, `::test_property_11_decay_monotonicity`
    - _Requirements: 5.2, 5.5, 5.7, 17.1, 17.3; Properties 10, 11_

  - [x] 3.2 `grade_to_sm2(result_class)` mapping helper
    - Target: `apps/api/app/mastery.py`
    - `success=5, partial=3, fail=1`
    - AC: `tests/test_mastery.py::test_grade_to_sm2_mapping`
    - _Requirements: 9.2_

  - [x] 3.3 Extend `Concept` dataclass with mastery fields
    - Target: `apps/api/app/knowledge_core.py`
    - AC: `tests/test_concept_dataclass.py::test_new_fields_have_defaults`
    - _Requirements: 5.1_

  - [x] 3.4 `grade_concept`, `lazy_decay_on_read`, `list_due_concepts`
    - Target: `apps/api/app/knowledge_core.py`
    - AC: `tests/test_concept_methods.py::test_grade_concept_persists`, `::test_lazy_decay_on_read_no_persist_without_write`, `::test_list_due_topological_order`
    - _Requirements: 5.3, 5.4, 5.6, 13.2_

  - [x] 3.5 PBT — topological learn_plan ordering + due-only practice (Property 23)
    - Target: new `tests/property/test_mastery_graph_pbt.py`
    - AC: `test_property_23_learn_plan_topological_and_practice_due_only`
    - _Requirements: 5.3, 5.4; Property 23_

  - [x] 3.6 `POST /api/v2/practice/{concept_id}/grade` endpoint
    - Target: `apps/api/app/v2.py`, `apps/api/schemas.py`
    - Response `metadata.mode = "pending-review"`; tenant-scoped 404
    - AC: `tests/test_practice_endpoint.py::test_grade_returns_pending_review_metadata`
    - _Requirements: 5.2, 11.1, 11.5_

  - [x] 3.7 `calibration.py`: `brier_score`, `log_loss`, `calibration_curve`, `calibration_score`
    - Target: new `apps/api/app/calibration.py` (pure)
    - AC (PBT): `tests/property/test_calibration_pbt.py::test_property_12_brier_bounds_and_zero_on_match`, `::test_property_13_calibration_curve_invariants`, `::test_property_14_calibration_score_aggregation`
    - _Requirements: 4.2-4, 17.2, 17.5; Properties 12-14_

  - [x] 3.8 `record_prediction` + `record_outcome` IO helpers
    - Target: `apps/api/app/calibration.py`
    - Persist into `calibration_records`; emit audit
    - AC: `tests/test_calibration_io.py::test_records_persist_and_emit_audit`
    - _Requirements: 4.2, 13.3_

  - [x] 3.9 `POST /api/v2/decisions` endpoint with required `predicted_outcome` and `confidence`
    - Target: `apps/api/app/v2.py`, `apps/api/schemas.py`
    - 400 when missing or out of `[0,1]`; verdict empty until evidence loop closes
    - AC: `tests/test_decision_endpoint.py::test_decision_rejects_missing_prediction`, `::test_decision_persists_with_pending_review_metadata`
    - _Requirements: 4.1, 6.3, 11.5_

  - [x] 3.10 PBT — DecisionLog validation contract (Property 24)
    - Target: new `tests/property/test_decision_log_pbt.py`
    - AC: `test_property_24_decision_log_validation`
    - _Requirements: 4.1; Property 24_

  - [x] 3.11 `POST /api/v2/decisions/{id}/review` endpoint
    - Target: `apps/api/app/v2.py`, `apps/api/schemas.py`
    - Computes Brier and Log loss when `binary_resolved=True`; otherwise persists nulls
    - AC: `tests/test_decision_review.py::test_review_computes_brier_and_log_loss`, `::test_unresolved_review_excluded_from_curve`
    - _Requirements: 4.2, 4.6_

  - [x] 3.12 `evidence_gathering.py`: state machine + `step` + `verdict_allowed`
    - Target: new `apps/api/app/evidence_gathering.py`
    - AC (PBT): `tests/property/test_evidence_gathering_pbt.py::test_property_15_gathering_closure`
    - _Requirements: 6.1-4, 6.6, 11.4, 17.6; Property 15_

  - [x] 3.13 Wire `expert_search` for active gathering
    - Target: `apps/api/app/expert_search.py` (extend), `apps/api/app/evidence_gathering.py`
    - On `insufficient_evidence`, write to `pending_knowledge` linked to coach turn / decision
    - AC: `tests/test_evidence_dispatch.py::test_search_writes_pending_knowledge_linked_to_decision`
    - _Requirements: 6.1, 6.2_

  - [x] 3.14 Orchestrator: insufficient_evidence triggers gathering and blocks verdict
    - Target: `apps/api/app/orchestrator.py`
    - Returns `awaiting_evidence`; verdict blocked until APPROVED
    - AC: `tests/test_orchestrator_evidence.py::test_verdict_blocked_until_pending_approved`, `::test_rejected_keeps_loop_open`
    - _Requirements: 6.3, 6.4, 6.6_

  - [x] 3.15 `calibration_score` biases `next_action`
    - Target: `apps/api/app/coaching_session.py`
    - Below `REALITY_OS_CALIBRATION_THRESHOLD` → `practice`
    - AC: `tests/test_next_action_calibration.py::test_low_calibration_biases_practice`
    - _Requirements: 4.5_

  - [x] 3.16 `retrieval_practice_plan` SM-2 due selection
    - Target: `apps/api/app/knowledge_core.py`
    - `next_due_at <= now()`; mixes cloze / socratic / counterexample
    - AC: `tests/test_practice_plan.py::test_practice_plan_due_only_and_format_mix`
    - _Requirements: 5.3_

  - [x] 3.17 i18n bundle additions: decision / practice / evidence-gathering
    - Target: `apps/web/lib/i18n.ts`
    - AC: `tests/test_i18n_parity.py::test_p1_keys_zh_en_parity`
    - _Requirements: 14.1-3_

  - [x] 3.18 Audit event emission for P1
    - Target: `apps/api/app/mastery.py`, `apps/api/app/calibration.py`, `apps/api/app/evidence_gathering.py`
    - AC: `tests/test_audit_events_p1.py::test_p1_audit_events_emitted_with_documented_keys`
    - _Requirements: 13.2, 13.3_

- [x] 4. M3 — P2 (Metacognition, Embeddings, Real-World Result Binding) gated by `REALITY_OS_HYBRID_RETRIEVAL` and `REALITY_OS_EMBED_MODE`

  - [x] 4.1 `metacognition.py`: rules + `metacognition_score`
    - Target: new `apps/api/app/metacognition.py`
    - `should_prompt`, `generate_questions_you_didnt_ask` (3-7), score in [0,1]
    - AC (PBT): `tests/property/test_metacognition_pbt.py::test_property_22_metacognition_rules`
    - _Requirements: 7.1, 7.3, 7.4, 7.6; Property 22_

  - [x] 4.2 Metacognition integration in coach turn
    - Target: `apps/api/app/orchestrator.py`, `apps/api/app/v2.py`
    - Persist user_confidence + system_confidence pair; emit audit
    - AC: `tests/test_coach_metacog.py::test_coach_turn_emits_metacog_block`, `::test_simple_mode_one_prompt_per_day`
    - _Requirements: 7.1, 7.2, 7.5, 7.6_

  - [x] 4.3 `vector_store.SqliteEmbedVectorStore` implementation
    - Target: `apps/api/app/vector_store.py`
    - little-endian float32; cosine search; `model_registry.embedder`; offline → TF-IDF fallback
    - AC: `tests/test_sqlite_embed_store.py::test_search_returns_cosine_ranked`, `::test_offline_mode_falls_back_to_tfidf`
    - _Requirements: 8.1, 8.4, 8.6_

  - [x] 4.4 `hybrid_retrieval.py`: `HybridWeights`, `normalize`, `hybrid_score`
    - Target: new `apps/api/app/hybrid_retrieval.py`
    - AC (PBT): `tests/property/test_hybrid_retrieval_pbt.py::test_property_17_hybrid_score_linearity_and_bounds`
    - _Requirements: 8.2; Property 17_

  - [x] 4.5 `KnowledgeCore.search` hybrid integration
    - Target: `apps/api/app/knowledge_core.py`
    - Min-max normalize FTS/TF-IDF/cosine, combine via `hybrid_score`, sort top-k
    - AC: `tests/test_search_hybrid.py::test_search_uses_hybrid_when_flag_on`, `::test_search_unchanged_when_flag_off`
    - _Requirements: 8.2_

  - [x] 4.6 PBT — embedder fallback determinism (Property 19)
    - Target: new `tests/property/test_embedder_fallback_pbt.py`
    - AC: `test_property_19_embedder_fallback_no_outbound_call_and_deterministic_ranking`
    - _Requirements: 8.4, 8.6, 18.2-3; Property 19_

  - [x] 4.7 `POST /api/v2/concepts/{id}/analogies` endpoint
    - Target: `apps/api/app/v2.py`, `apps/api/app/knowledge_core.py`
    - `hit.domain != source.domain`; sort by cosine; `analogies_available=False` when embedder off
    - AC: `tests/test_analogy_endpoint.py::test_analogies_filter_by_domain_and_rank`
    - _Requirements: 8.3_

  - [x] 4.8 PBT — cross-domain analogy ranking (Property 18)
    - Target: new `tests/property/test_analogy_pbt.py`
    - AC: `test_property_18_analogy_ranking`
    - _Requirements: 8.3; Property 18_

  - [x] 4.9 Structured `ActionExperiment.review` dataclass
    - Target: `apps/api/app/reality_layers.py`, `apps/api/schemas.py`
    - Old `experiment.actual_result` remains for compat
    - AC: `tests/test_experiment_review_dataclass.py::test_dataclass_round_trip_with_metrics`
    - _Requirements: 9.1_

  - [x] 4.10 `POST /api/v2/experiments/{id}/review` endpoint with mastery hard-binding
    - Target: `apps/api/app/v2.py`, `apps/api/app/knowledge_core.py`
    - For every linked Concept call `grade_concept(grade=grade_to_sm2(result_class))`
    - AC: `tests/test_experiment_review_endpoint.py::test_review_binds_mastery_for_linked_concepts`, `::test_unlinked_experiment_review_persists_without_error`
    - _Requirements: 9.1, 9.2, 9.5_

  - [x] 4.11 PBT — real-world result binding (Property 20)
    - Target: new `tests/property/test_result_binding_pbt.py`
    - AC: `test_property_20_result_binding_metric_breach_and_consecutive_fail_switch`
    - _Requirements: 9.2-4; Property 20_

  - [x] 4.12 Consecutive-fail policy: chain switch or `human_review_required`
    - Target: `apps/api/app/coaching_session.py`, `apps/api/app/skill_chain.py`
    - K trailing fails (default 3) → configured policy
    - AC: `tests/test_consecutive_fail_policy.py::test_three_fails_trigger_chain_switch`, `::test_three_fails_with_policy_human_review`
    - _Requirements: 9.3, 9.4_

  - [x] 4.13 i18n bundle additions: metacognition / analogy / experiment-review
    - Target: `apps/web/lib/i18n.ts`
    - AC: `tests/test_i18n_parity.py::test_p2_keys_zh_en_parity`
    - _Requirements: 14.1-3_

  - [x] 4.14 Wire feature flag `REALITY_OS_HYBRID_RETRIEVAL`
    - Target: `apps/api/app/knowledge_core.py`
    - Off → existing FTS/TF-IDF behavior unchanged
    - AC: `tests/test_flag_hybrid.py::test_hybrid_disabled_uses_legacy_search`
    - _Requirements: rollout plan_

  - [x] 4.15 Wire feature flag `REALITY_OS_EMBED_MODE`
    - Target: `apps/api/app/vector_store.py`
    - `disabled` and `offline` bypass embedder
    - AC: `tests/test_flag_embed_mode.py::test_offline_uses_tfidf`, `::test_disabled_disables_embed_path`
    - _Requirements: 8.5, 8.6, 18.3_

  - [x] 4.16 Audit event emission for P2
    - Target: `apps/api/app/metacognition.py`, `apps/api/app/v2.py`
    - AC: `tests/test_audit_events_p2.py::test_p2_audit_events_emitted_with_documented_keys`
    - _Requirements: 13.1, 13.2_

- [x] 5. M4 — P3 (Learning Dashboard, read-only)

  - [x] 5.1 `GET /api/v2/dashboard/mastery` (heatmap)
    - Target: `apps/api/app/v2.py`, `apps/api/app/knowledge_core.py`
    - Tenant-scoped; group by domain; `metadata.mode = "read-only"`
    - AC: `tests/test_dashboard_mastery.py::test_mastery_heatmap_tenant_scoped`
    - _Requirements: 10.1.a, 10.6_

  - [x] 5.2 `GET /api/v2/dashboard/calibration` (curve + Brier)
    - Target: `apps/api/app/v2.py`
    - AC: `tests/test_dashboard_calibration.py::test_calibration_curve_bins_present`
    - _Requirements: 10.1.b_

  - [x] 5.3 `GET /api/v2/dashboard/skill-chain` (completion rate per problem_type)
    - Target: `apps/api/app/v2.py`
    - AC: `tests/test_dashboard_skill_chain.py::test_completion_rate_returns_per_step_retention`
    - _Requirements: 10.1.c_

  - [x] 5.4 `GET /api/v2/dashboard/decay` (concept decay curves)
    - Target: `apps/api/app/v2.py`
    - AC: `tests/test_dashboard_decay.py::test_decay_curves_use_last_practiced_at`
    - _Requirements: 10.1.d_

  - [x] 5.5 Web dashboard panels (Simple_Mode — at most 3 panels, no controls)
    - Target: `apps/web/app/dashboard/page.tsx`, `apps/web/app/eval/page.tsx`, `apps/web/app/learn/page.tsx`, `apps/web/components/dashboard/{MasteryHeatmap,CalibrationCurve,SkillChainCompletion}.tsx`
    - AC: `apps/web/__tests__/dashboard.simple.test.tsx::test_simple_mode_renders_3_panels_no_controls`
    - _Requirements: 10.2, 10.3_

  - [x] 5.6 Web dashboard panels (Professional_Mode — 4 panels + filters)
    - Target: `apps/web/app/dashboard/page.tsx`, `apps/web/components/dashboard/{ConceptDecay,Filters}.tsx`
    - AC: `apps/web/__tests__/dashboard.pro.test.tsx::test_pro_mode_renders_4_panels_and_filters`
    - _Requirements: 10.4_

  - [x] 5.7 i18n bundle additions: dashboard strings (`dash.*`)
    - Target: `apps/web/lib/i18n.ts`
    - AC: `tests/test_i18n_parity.py::test_dashboard_keys_zh_en_parity`
    - _Requirements: 10.5, 14.1-3_

- [x] 6. M5 — Hardening (cross-cutting PBTs, smoke tests, end-to-end integration)

  - [x] 6.1 PBT — tenant isolation 404 (Property 5)
    - Target: new `tests/property/test_tenant_isolation_pbt.py`
    - AC: `test_property_5_cross_tenant_returns_404`
    - _Requirements: 1.10, 12.2-4, 10.6; Property 5_

  - [x] 6.2 PBT — pending-review contract (Property 16)
    - Target: new `tests/property/test_pending_review_pbt.py`
    - AC: `test_property_16_pending_review_metadata_and_status`
    - _Requirements: 11.1, 11.2, 11.5; Property 16_

  - [x] 6.3 PBT — audit event coverage (Property 21)
    - Target: new `tests/property/test_audit_coverage_pbt.py`
    - AC: `test_property_21_one_audit_per_accepted_state_change_and_none_on_reject`
    - _Requirements: 13.1-4; Property 21_

  - [x] 6.4 Unit test — API key masking (Property 25)
    - Target: new `tests/test_api_key_mask.py`
    - AC: `test_property_25_api_key_mask_to_dict_never_returns_raw`
    - _Requirements: 18.4; Property 25_

  - [x] 6.5 Smoke test — schema migration on existing dev DB
    - Target: new `tests/test_smoke_migration.py`
    - AC: `test_existing_dev_db_migrates_cleanly_and_old_rows_untouched`
    - _Requirements: 12.1, 16.1_

  - [x] 6.6 Smoke test — feature flag dark-launch matrix
    - Target: new `tests/test_smoke_flags.py`
    - AC: `test_all_flags_off_legacy_routes_intact`, `::test_flags_can_be_flipped_per_milestone`
    - _Requirements: 15.2_

  - [x] 6.7 Smoke test — `legacy/` untouched and not imported
    - Target: new `tests/test_smoke_legacy.py`
    - AC: `test_no_new_module_imports_from_legacy`, `::test_no_legacy_files_modified_by_feature_paths`
    - _Requirements: 16.1, 16.2_

  - [x] 6.8 Integration test — full coach turn end-to-end (zh-CN + en)
    - Target: new `tests/test_coach_e2e.py`
    - AC: `test_coach_e2e_zhCN_full_loop`, `::test_coach_e2e_en_full_loop`
    - _Requirements: 1.3, 14.2-3_

  - [x] 6.9 Integration test — Active Evidence Gathering closure
    - Target: new `tests/test_evidence_e2e.py`
    - AC: `test_decision_blocked_until_pending_approved`, `::test_rejected_keeps_loop_open_until_approve_or_explicit_close`
    - _Requirements: 6.3-6, 11.4_

  - [x] 6.10 Integration test — embedder offline mode does not call out
    - Target: new `tests/test_embed_offline_e2e.py`
    - AC: `test_embed_offline_no_outbound_request`
    - _Requirements: 8.6, 18.3_

## Notes

- Each leaf task references requirement clauses and Property numbers. All 25 properties have a dedicated PBT task.
- Algorithm cores live in I/O-free modules so PBT files run < 1s/property at 200 iterations.
- Dark-launch order: M0 (flags off) → M1 + flip `EXPERT_GAP_ENABLED`/`COACH_ENABLED` → M2 → M3 + flip `HYBRID_RETRIEVAL` and `EMBED_MODE` → M4 → M5 hardening. Each step independently revertible.
