from tests.test_no_cognee_production import test_production_has_no_cognee_integration, test_engine_never_imports_or_uses_retired_memory
from tests.test_core import test_core, test_core_default_paths_unchanged_when_no_override_given
from tests.test_dev_manager import test_dev_manager
from tests.test_logger import test_logger, test_logger_does_not_raise_when_log_dir_removed
from tests.test_model_security import test_model_security
from tests.test_hermes_bridge import test_hermes_bridge_lock, test_hermes_research_sources
from tests.test_research_uat import (
    test_stage_docker_mock_docker_command_missing,
    test_stage_docker_mock_container_stopped,
    test_stage_docker_mock_container_missing,
    test_stage_docker_mock_running_ok,
    test_stage_http_searxng_unavailable,
    test_stage_json_api_403_diagnoses_without_editing_settings,
    test_stage_json_api_empty_results_not_counted_as_pass,
    test_stage_json_api_real_results_sets_criterion_true,
    test_classify_engine_reason,
    test_stage_engine_health_degraded_classification,
    test_counting_provider_wrapper_records_real_calls,
    test_stage_research_engine_mock_fetch_failure,
    test_stage_research_engine_mock_success_path,
    test_relevance_adversarial_detects_injected_bug,
    test_temporal_adversarial_catches_wrong_period,
    test_conflict_adversarial_catches_two_values,
    test_report_finalize_gate_all_true_is_pass,
    test_report_finalize_gate_one_false_is_not_pass,
    test_report_finalize_gate_all_none_is_fail,
    test_sha_snapshot_detects_change,
    test_sha_snapshot_permission_denied_is_skipped_not_crashed,
    test_sha_snapshot_symlink_junction_is_skipped_special,
    test_stage_docker_cli_not_found_sets_diagnosis_code,
    test_stage_docker_daemon_unreachable_sets_desktop_not_running_diagnosis,
    test_stage_docker_container_missing_sets_diagnosis_code,
    test_stage_docker_container_stopped_sets_diagnosis_code,
    test_stage_docker_running_but_port_mismatch_fails,
    test_main_writes_complete_report_on_fatal_exception,
    test_build_isolated_brain_disables_cognee,
    test_stage_kaizenbrain_shadow_calls_brain_manager_shutdown_before_tempdir_cleanup,
    test_criterion_15_is_true_even_when_on_path_succeeds_via_engine,
    test_kaizenbrain_shadow_off_does_not_mutate_guarded_dirs,
)
from tests.test_provider_factory_log_isolation import (
    test_hermes_provider_accepts_log_dir_and_isolates_real_logs,
    test_hermes_provider_default_log_dir_unchanged_backward_compat,
    test_build_provider_threads_log_dir_to_hermes,
    test_build_provider_without_log_dir_still_constructs_chain,
    test_make_offline_and_local_ignore_log_dir_harmlessly,
)
from tests.test_memory import test_memory
from tests.test_accounting import test_accounting, test_accounting_agent_verify_document
from tests.test_ai_provider import test_ai_provider
from tests.test_tool_security import test_tool_security
from tests.test_experience_store import test_experience_store
from tests.test_accounting_sources import (
    test_accounting_sources,
    test_accounting_sources_official_sgk_resmi_gazete_mevzuat_registered,
)
from tests.test_accounting_consensus import (
    test_accounting_consensus, test_accounting_consensus_percent_decimal_point_not_confused_with_thousands,
)
from tests.test_learning_store import test_learning_store
from tests.test_math_calculator import test_math_calculator
from tests.test_kaizen_brain import test_kaizen_brain, test_brain_independent_of_model, test_brain_current_question_uses_site_memory
from tests.test_calculators import test_calculators
from tests.test_journal import test_journal
from tests.test_crawler import (
    test_crawler, test_fetcher_encodes_turkish_characters_in_url,
    test_robots_429_is_treated_as_blocked_not_allowed,
)
from tests.test_facts import (
    test_facts, test_facts_ignores_space_grouped_tl_fragment,
    test_facts_asgari_ucret_ignores_gunluk_yillik_and_onda_bir_sentences,
    test_facts_vuk_313_ignores_binek_oto_otv_line,
    test_rebuild_removes_stale_facts_when_extraction_rule_is_corrected,
)
from tests.test_providers import test_providers
from tests.test_office_and_commands import test_office_tools, test_seed_loader, test_commands, test_document_commands, test_gorsel_oku_reads_text_via_ocr, test_pdf_oku_falls_back_to_ocr_for_scanned_pages
from tests.test_document_verifier import (
    test_deterministic_matches_detects_match_and_mismatch,
    test_verify_document_uses_deterministic_layer_with_real_fact_registry,
    test_verify_document_flags_truncation_regardless_of_model_output,
)
from tests.test_golden_exam import test_golden_exam
from tests.test_accounting_brain import test_accounting_brain
from tests.test_self_learning import (
    test_knowledge_card_store_pending_confirm_and_contradiction,
    test_knowledge_card_store_same_source_repeat_does_not_confirm,
    test_brain_learns_from_research_and_avoids_repeat_calls,
    test_brain_cross_checks_research_against_verified_facts,
)
from tests.test_refresh_cli import test_rebuild_only_uses_stored_pages_without_crawling
from tests.test_text_tr import (
    test_stem_tr_same_root_pairs_match,
    test_stem_tr_does_not_over_strip_short_words,
    test_stem_tr_unrelated_words_stay_different,
)
from tests.test_retriever import (
    test_coverage_matches_suffixed_question_word_against_bare_text_word,
    test_coverage_still_low_for_unrelated_question,
    test_coverage_matches_possessive_suffix_variant,
)
from tests.test_engine_isolation import test_engine_is_never_left_to_default_data_dir_in_tests
from tests.test_brain_manager import test_brain_manager_retrieval_delegates_to_retriever, test_brain_manager_verified_fact_answer_handles_missing_registry, test_brain_manager_remember_research_promotes_card_and_learning_store, test_brain_manager_remember_research_flags_contradiction_with_verified_facts, test_brain_manager_remember_research_same_call_contradiction_blocks_confirmation
from tests.test_real_world_exam import test_real_world_exam
from tests.test_search_provider import (
    test_search_provider_parses_valid_json_response,
    test_search_provider_handles_empty_results_list,
    test_search_provider_handles_empty_query_without_network_call,
    test_search_provider_skips_malformed_result_items_without_crashing,
    test_search_provider_raises_typed_error_on_non_dict_top_level_payload,
    test_search_provider_raises_typed_error_on_malformed_json_body,
    test_search_provider_raises_typed_error_on_timeout,
    test_search_provider_raises_typed_error_on_connection_refused,
    test_search_provider_raises_typed_error_on_socket_timeout_os_error,
    test_search_provider_raises_typed_error_on_http_error,
    test_search_provider_reports_unresponsive_engines_without_failing_the_call,
    test_search_provider_total_engine_outage_returns_empty_results_and_degraded_true,
    test_search_provider_injects_site_operator_for_each_requested_domain,
    test_search_provider_injects_multiple_site_operators_for_multiple_domains,
    test_search_provider_deduplicates_results_sharing_the_same_url,
    test_search_provider_detects_pdf_results_by_url_extension,
    test_search_provider_round_trips_turkish_unicode_in_query_and_results,
    test_search_provider_normalizes_all_search_result_fields,
    test_search_provider_normalizes_missing_optional_fields_to_safe_defaults,
    test_search_provider_respects_limit_option,
)
from tests.test_tokenizer_slash_code_fix import (
    test_tokenizer_preserves_digit_slash_letter_codes_as_single_tokens,
    test_tokenizer_preserves_digit_slash_letter_codes_uppercase_input,
    test_tokenizer_does_not_break_plain_account_codes_without_slash,
    test_tokenizer_does_not_merge_pure_numeric_date_or_fraction_slashes,
    test_tokenizer_does_not_affect_percent_rate_expressions,
    test_significance_filter_now_keeps_slash_codes_instead_of_dropping_them,
    test_extractive_answer_now_finds_the_4a_4b_4c_curriculum_entry_real_data,
)
from tests.test_chart_multi_code_comparison import (
    test_chart_multi_code_comparison_describes_both_accounts,
    test_chart_multi_code_comparison_bypasses_the_triggers_gate,
    test_chart_multi_code_comparison_no_longer_drops_the_second_account,
    test_chart_single_code_questions_are_completely_unaffected,
    test_chart_two_numbers_without_comparison_word_do_not_trigger_the_new_path,
)
from tests.test_decision_engine_contract import (
    test_decision_matches_the_work_order_example_sgk_tavan,
    test_decision_never_carries_an_answer_field,
    test_decision_preferred_route_is_always_a_known_kaizen_brain_route,
    test_decision_exact_tool_intents_require_verified_confidence,
    test_decision_refines_intent_beyond_classifys_four_buckets_without_touching_classify,
    test_decision_reason_field_is_always_a_non_empty_string,
)
from tests.test_retrieval_failures import (
    test_retrieval_min_coverage_threshold_is_060_non_strict_and_exact_boundary_passes,
    test_retrieval_strict_mode_requires_full_100_percent_coverage,
    test_retrieval_short_single_term_question_over_trusts_a_coincidental_match,
    test_retrieval_synonyms_are_not_recognized_no_thesaurus,
    test_retrieval_word_order_does_not_affect_coverage_or_phrase_ok,
    test_retrieval_long_natural_question_dilutes_coverage_with_extra_real_words,
    test_retrieval_stemmer_fails_on_accusative_yi_yı_yu_yu_suffix,
    test_retrieval_stemmer_fails_on_dative_ye_ya_suffix,
    test_retrieval_tokenizer_no_longer_shreds_slash_codes_after_fix,
    test_retrieval_significance_filter_no_longer_drops_slash_code_fragments_after_fix,
    test_retrieval_information_exists_locally_and_extractive_answer_now_returns_it_after_fix,
    test_retrieval_multi_topic_comparison_question_now_returns_both_topics_after_frame_fix,
    test_retrieval_needs_current_research_false_positive_no_longer_hides_stable_knowledge_after_frame_fix,
)
from tests.test_classification_failures import (
    test_classify_documents_the_four_intents_and_their_keyword_sets,
    test_classify_false_negative_account_code_reference_is_no_longer_fatal_after_chart_fix,
    test_classify_false_negative_sgk_regime_codes_without_literal_sgk_word,
    test_classify_false_negative_is_not_always_fatal_thanks_to_general_fallback,
    test_classify_false_positive_verb_conjugation_contains_accounting_term_as_substring,
    test_classify_false_positive_causes_unnecessary_research,
)
from tests.test_trace import (
    test_trace_does_not_change_the_returned_answer_text,
    test_trace_arithmetic_and_chart_are_verified,
    test_trace_general_domain_uses_model_and_marks_unknown,
    test_trace_memory_grounded_is_supported_with_retrieval_score,
    test_trace_pending_card_then_conflicted_after_contradiction,
    test_trace_empty_question_is_refusal,
)
from tests.test_search_resilience import (
    test_search_resilience_retries_and_succeeds_after_transient_timeout,
    test_search_resilience_raises_after_retries_exhausted_on_persistent_timeout,
    test_search_resilience_backoff_uses_injectable_sleep_with_bounded_exponential_delay,
    test_search_resilience_http_429_raises_rate_limited_error_with_retry_after,
    test_search_resilience_http_500_502_503_are_retryable_and_map_to_unavailable,
    test_search_resilience_http_404_is_not_retried,
    test_search_resilience_malformed_json_is_not_retried,
    test_search_resilience_connection_refused_is_retryable_and_maps_to_unavailable,
    test_search_resilience_successful_search_status_is_ok,
    test_search_resilience_empty_results_status_is_empty_not_error,
    test_search_resilience_single_engine_dependency_flagged_when_only_one_engine_contributes,
    test_search_resilience_multi_engine_results_not_flagged_as_single_engine_dependency,
    test_search_resilience_one_engine_broken_other_succeeds_still_returns_usable_results,
    test_search_resilience_total_engine_outage_recommends_fallback_with_reason,
    test_search_resilience_fallback_not_needed_for_normal_result_case,
    test_search_resilience_exceptions_are_never_silently_converted_to_empty_outcome,
    test_search_resilience_provider_health_starts_healthy,
    test_search_resilience_provider_health_becomes_unavailable_after_consecutive_failures,
    test_search_resilience_provider_health_recovers_to_healthy_after_success_following_failures,
    test_search_resilience_rate_limit_triggers_cooldown_and_subsequent_call_fails_fast,
    test_search_resilience_cooldown_expires_and_next_call_reaches_network_again,
    test_search_resilience_burst_protection_enforces_minimum_interval_via_injectable_sleep,
    test_search_resilience_burst_protection_does_not_delay_when_enough_time_has_passed,
    test_search_resilience_duplicate_url_dedup_still_works,
    test_search_resilience_turkish_unicode_preserved_with_new_status_fields,
    test_search_resilience_pdf_detection_still_works,
    test_search_resilience_domain_filtering_still_applied_with_resilience_wrapper,
    test_search_resilience_observability_debug_info_available_after_successful_call,
    test_search_resilience_observability_debug_info_available_after_failed_call,
)
from tests.test_learning_transfer import (
    test_transfer_dataset_has_all_seven_mandated_families,
    test_transfer_dataset_each_scenario_has_distinct_b_and_d_questions,
    test_transfer_dataset_no_annual_figures_leak_into_principle_statements,
    test_principle_positive_transfer_donemsellik,
    test_principle_positive_transfer_borc_alacak,
    test_principle_positive_transfer_hesap_siniflandirma,
    test_principle_positive_transfer_ozun_onceligi,
    test_principle_positive_transfer_maliyet_ilkesi,
    test_principle_positive_transfer_amortisman,
    test_principle_positive_transfer_sgk_statu,
    test_principle_negative_transfer_rejects_all_seven_counter_examples,
    test_principle_negative_transfer_sgk_counter_example_is_a_fact_not_a_principle,
    test_principle_not_found_for_unrelated_question,
    test_principle_multiple_candidates_are_both_visible_when_scores_are_close,
    test_principle_confidence_levels_are_one_of_the_four_labels,
    test_principle_low_or_none_confidence_never_forces_a_selection,
    test_principle_confidence_never_reaches_verified_label,
    test_principle_registry_rows_never_contain_annual_figures,
    test_principle_registry_every_row_has_non_empty_provenance,
    test_principle_registry_has_exactly_the_seven_curated_principles,
    test_principle_retrieval_handles_turkish_unicode_case_variants,
    test_principle_different_words_same_structure_still_transfers,
    test_principle_same_words_different_structure_does_not_transfer,
    test_principle_trace_output_shows_candidates_selected_confidence_rejected_reason,
    test_principle_trace_fields_default_empty_when_principle_layer_not_used,
    test_principle_decision_bridge_never_claims_verified_and_uses_known_route,
)
from tests.test_desktop_adapter import (
    test_status_mapper_labels_are_turkish_and_cover_all_states,
    test_status_mapper_summarize_trace_reflects_real_route_and_confidence,
    test_status_mapper_never_fabricates_unknown_route,
    test_context_panel_summary_hides_technical_fields,
    test_full_inspector_lines_exposes_all_trace_fields,
    test_error_presenter_never_leaks_raw_exception_to_user_message,
    test_conversation_history_is_session_only_and_independent_of_kaizen_memory,
)
from tests.test_experience_model import (
    test_experience_model_has_the_ten_mandated_fields,
    test_experience_model_rejects_empty_signature_and_strategy,
    test_experience_model_rejects_unknown_outcome_and_verification,
    test_experience_model_d2_has_no_raw_fact_or_answer_field,
    test_experience_model_d3_reusable_true_requires_user_approved_true_at_construction,
    test_reflection_store_record_and_get_round_trips,
    test_reflection_store_d3_no_auto_trust_two_separate_explicit_calls_required,
    test_reflection_store_list_filters_by_signature_outcome_and_reusable,
    test_experience_model_is_never_imported_by_kaizen_brain_d4,
)
from tests.test_learning_brain_integration import (
    test_learning_brain_flag_off_no_augmentation_default_behavior,
    test_learning_brain_high_confidence_augments_prompt_assisted_mode,
    test_learning_brain_low_none_never_touches_prompt,
    test_learning_brain_domain_restricted_to_accounting,
    test_learning_brain_never_reached_by_exact_tools_or_facts,
    test_learning_brain_engine_production_default_is_disabled,
    test_learning_brain_one_line_revert_contract,
)
from tests.test_learning_brain_ab_reality import (
    test_learning_brain_ab_reality_twenty_grounded_questions,
)
from tests.test_research_extractor import (
    test_extract_html_returns_title_date_and_excludes_nav_footer,
    test_extract_pdf_routing_degrades_gracefully_on_corrupt_bytes,
    test_extract_non_ok_fetch_outcome_returns_empty_content,
    test_best_passage_picks_most_relevant_paragraph_not_whole_page,
    test_best_passage_truncates_to_max_chars,
    test_best_passage_empty_text_returns_empty,
)
from tests.test_research_evidence import (
    test_source_type_official_gib_and_sgk,
    test_source_type_professional_and_unknown,
    test_detect_period_prefers_published_at_over_text,
    test_detect_period_falls_back_to_text_year,
    test_detect_period_missing_returns_none_not_guessed,
    test_temporal_matches_rejects_stale_source_for_current_question,
    test_build_evidence_snippet_only_never_high_confidence,
    test_build_evidence_official_source_matching_period_is_high_confidence,
    test_build_evidence_stale_source_downgrades_confidence_even_if_official,
    test_build_evidence_professional_source_matching_period_is_medium_confidence,
    test_build_evidence_missing_date_kept_as_none_not_guessed,
)
from tests.test_research_verifier import (
    test_resolve_topic_matches_question_terms,
    test_build_claims_supported_single_official_source_matching_period,
    test_build_claims_conflicted_when_two_independent_sources_disagree,
    test_build_claims_partial_when_single_non_official_source,
    test_build_claims_stale_official_source_downgrades_to_partial,
    test_build_claims_insufficient_when_source_is_unregistered,
    test_build_claims_skips_subquestion_with_no_evidence_at_all,
    test_build_claims_qualitative_supported_via_single_official_source,
    test_build_claims_qualitative_partial_via_single_professional_source,
    test_build_claims_qualitative_irrelevant_official_source_never_supported,
    test_build_claims_qualitative_snippet_only_never_produces_claim,
)
from tests.test_kaizen_brain_research_engine import (
    test_research_engine_disabled_by_default_uses_hermes_unchanged,
    test_research_engine_enabled_but_no_provider_falls_back_safely,
    test_research_engine_supported_result_replaces_hermes_call,
    test_research_engine_insufficient_result_still_falls_back_to_hermes,
    test_research_engine_unexpected_exception_never_crashes_answer,
    test_format_research_result_only_accepts_supported_with_verified_claims,
)
from tests.test_research_engine import (
    test_run_research_never_raises_returns_search_unavailable_on_total_failure,
    test_run_research_supported_single_official_source,
    test_run_research_conflicted_when_two_independent_sources_disagree,
    test_run_research_search_degraded_and_missing_information_when_no_results,
    test_run_research_partial_when_only_some_subquestions_supported,
    test_run_research_survives_unexpected_fetcher_exception_for_one_url,
    test_run_research_blocked_fetch_is_never_silently_treated_as_content,
)
from tests.test_research_fetcher import (
    test_fetcher_normal_https_html_succeeds,
    test_fetcher_pdf_content_type_succeeds,
    test_fetcher_follows_redirect_and_revalidates_target,
    test_fetcher_redirect_to_localhost_is_blocked_not_silently_followed,
    test_fetcher_localhost_direct_is_blocked,
    test_fetcher_127_0_0_1_is_blocked,
    test_fetcher_private_ip_is_blocked,
    test_fetcher_file_scheme_is_blocked,
    test_fetcher_credentials_in_url_is_blocked,
    test_fetcher_oversized_response_is_rejected,
    test_fetcher_timeout_is_reported_not_raised,
    test_fetcher_timeout_during_body_read_is_reported_not_raised,
    test_fetcher_403_is_never_bypassed,
    test_fetcher_429_is_never_bypassed,
    test_fetcher_robots_deny_blocks_before_any_content_fetch,
    test_fetcher_robots_unreadable_fails_safe_deny_not_permissive,
    test_fetcher_robots_404_means_allow_all,
    test_fetcher_malformed_url_is_rejected,
)
from tests.test_research_planner import (
    test_research_planner_topic_and_period_detection,
    test_research_planner_no_unnecessary_subquestions_when_no_period,
    test_research_planner_sgk_topic_includes_sgk_domain_subquery,
    test_research_planner_no_duplicate_queries_within_a_plan,
    test_research_planner_never_hallucinates_a_number_not_in_the_question,
    test_research_planner_returns_a_valid_research_plan_contract,
)
from tests.test_research_trigger import (
    test_research_trigger_needed_cases,
    test_research_trigger_not_needed_cases,
    test_research_trigger_domain_gate_blocks_non_accounting_even_with_no_local_evidence,
    test_research_trigger_local_evidence_found_true_always_wins,
)
from tests.test_research_models import (
    test_subquestion_rejects_empty_fields,
    test_research_plan_requires_at_least_one_subquestion,
    test_evidence_rejects_invalid_source_type_and_confidence,
    test_evidence_official_flag_must_match_source_type,
    test_evidence_has_real_content_distinguishes_snippet_only,
    test_claim_requires_at_least_one_evidence_id_and_valid_status,
    test_research_result_verified_claims_must_be_subset_of_claims,
    test_research_result_rejects_snippet_only_verified_claim,
    test_research_result_status_must_be_in_contract,
)


def run_all():
    print("\nKAIZEN TESTLERI BASLIYOR...\n")

    test_core()
    test_core_default_paths_unchanged_when_no_override_given()
    test_dev_manager()
    test_logger()
    test_logger_does_not_raise_when_log_dir_removed()
    test_model_security()
    test_hermes_bridge_lock()
    test_hermes_research_sources()
    test_stage_docker_mock_docker_command_missing()
    test_stage_docker_mock_container_stopped()
    test_stage_docker_mock_container_missing()
    test_stage_docker_mock_running_ok()
    test_stage_http_searxng_unavailable()
    test_stage_json_api_403_diagnoses_without_editing_settings()
    test_stage_json_api_empty_results_not_counted_as_pass()
    test_stage_json_api_real_results_sets_criterion_true()
    test_classify_engine_reason()
    test_stage_engine_health_degraded_classification()
    test_counting_provider_wrapper_records_real_calls()
    test_stage_research_engine_mock_fetch_failure()
    test_stage_research_engine_mock_success_path()
    test_relevance_adversarial_detects_injected_bug()
    test_temporal_adversarial_catches_wrong_period()
    test_conflict_adversarial_catches_two_values()
    test_report_finalize_gate_all_true_is_pass()
    test_report_finalize_gate_one_false_is_not_pass()
    test_report_finalize_gate_all_none_is_fail()
    test_sha_snapshot_detects_change()
    test_sha_snapshot_permission_denied_is_skipped_not_crashed()
    test_sha_snapshot_symlink_junction_is_skipped_special()
    test_stage_docker_cli_not_found_sets_diagnosis_code()
    test_stage_docker_daemon_unreachable_sets_desktop_not_running_diagnosis()
    test_stage_docker_container_missing_sets_diagnosis_code()
    test_stage_docker_container_stopped_sets_diagnosis_code()
    test_stage_docker_running_but_port_mismatch_fails()
    test_main_writes_complete_report_on_fatal_exception()
    test_build_isolated_brain_disables_cognee()
    test_stage_kaizenbrain_shadow_calls_brain_manager_shutdown_before_tempdir_cleanup()
    test_criterion_15_is_true_even_when_on_path_succeeds_via_engine()
    test_kaizenbrain_shadow_off_does_not_mutate_guarded_dirs()
    test_hermes_provider_accepts_log_dir_and_isolates_real_logs()
    test_hermes_provider_default_log_dir_unchanged_backward_compat()
    test_build_provider_threads_log_dir_to_hermes()
    test_build_provider_without_log_dir_still_constructs_chain()
    test_make_offline_and_local_ignore_log_dir_harmlessly()
    test_production_has_no_cognee_integration()
    test_engine_never_imports_or_uses_retired_memory()
    test_memory()
    test_accounting()
    test_accounting_agent_verify_document()
    test_ai_provider()
    test_tool_security()
    test_experience_store()
    test_accounting_sources()
    test_accounting_sources_official_sgk_resmi_gazete_mevzuat_registered()
    test_accounting_consensus()
    test_accounting_consensus_percent_decimal_point_not_confused_with_thousands()
    test_learning_store()
    test_math_calculator()
    test_kaizen_brain()
    test_brain_independent_of_model()
    test_brain_current_question_uses_site_memory()
    test_calculators()
    test_journal()
    test_robots_429_is_treated_as_blocked_not_allowed()
    test_crawler()
    test_fetcher_encodes_turkish_characters_in_url()
    test_facts()
    test_facts_ignores_space_grouped_tl_fragment()
    test_facts_asgari_ucret_ignores_gunluk_yillik_and_onda_bir_sentences()
    test_facts_vuk_313_ignores_binek_oto_otv_line()
    test_rebuild_removes_stale_facts_when_extraction_rule_is_corrected()
    test_providers()
    test_office_tools()
    test_gorsel_oku_reads_text_via_ocr()
    test_pdf_oku_falls_back_to_ocr_for_scanned_pages()
    test_seed_loader()
    test_commands()
    test_document_commands()
    test_deterministic_matches_detects_match_and_mismatch()
    test_verify_document_uses_deterministic_layer_with_real_fact_registry()
    test_verify_document_flags_truncation_regardless_of_model_output()
    test_golden_exam()
    test_accounting_brain()
    test_knowledge_card_store_pending_confirm_and_contradiction()
    test_knowledge_card_store_same_source_repeat_does_not_confirm()
    test_brain_learns_from_research_and_avoids_repeat_calls()
    test_brain_cross_checks_research_against_verified_facts()
    test_rebuild_only_uses_stored_pages_without_crawling()
    test_stem_tr_same_root_pairs_match()
    test_stem_tr_does_not_over_strip_short_words()
    test_stem_tr_unrelated_words_stay_different()
    test_coverage_matches_suffixed_question_word_against_bare_text_word()
    test_coverage_still_low_for_unrelated_question()
    test_coverage_matches_possessive_suffix_variant()
    test_brain_manager_retrieval_delegates_to_retriever()
    test_brain_manager_verified_fact_answer_handles_missing_registry()
    test_brain_manager_remember_research_promotes_card_and_learning_store()
    test_brain_manager_remember_research_flags_contradiction_with_verified_facts()
    test_brain_manager_remember_research_same_call_contradiction_blocks_confirmation()
    test_engine_is_never_left_to_default_data_dir_in_tests()
    test_real_world_exam()
    test_search_provider_parses_valid_json_response()
    test_search_provider_handles_empty_results_list()
    test_search_provider_handles_empty_query_without_network_call()
    test_search_provider_skips_malformed_result_items_without_crashing()
    test_search_provider_raises_typed_error_on_non_dict_top_level_payload()
    test_search_provider_raises_typed_error_on_malformed_json_body()
    test_search_provider_raises_typed_error_on_timeout()
    test_search_provider_raises_typed_error_on_connection_refused()
    test_search_provider_raises_typed_error_on_socket_timeout_os_error()
    test_search_provider_raises_typed_error_on_http_error()
    test_search_provider_reports_unresponsive_engines_without_failing_the_call()
    test_search_provider_total_engine_outage_returns_empty_results_and_degraded_true()
    test_search_provider_injects_site_operator_for_each_requested_domain()
    test_search_provider_injects_multiple_site_operators_for_multiple_domains()
    test_search_provider_deduplicates_results_sharing_the_same_url()
    test_search_provider_detects_pdf_results_by_url_extension()
    test_search_provider_round_trips_turkish_unicode_in_query_and_results()
    test_search_provider_normalizes_all_search_result_fields()
    test_search_provider_normalizes_missing_optional_fields_to_safe_defaults()
    test_search_provider_respects_limit_option()
    test_tokenizer_preserves_digit_slash_letter_codes_as_single_tokens()
    test_tokenizer_preserves_digit_slash_letter_codes_uppercase_input()
    test_tokenizer_does_not_break_plain_account_codes_without_slash()
    test_tokenizer_does_not_merge_pure_numeric_date_or_fraction_slashes()
    test_tokenizer_does_not_affect_percent_rate_expressions()
    test_significance_filter_now_keeps_slash_codes_instead_of_dropping_them()
    test_extractive_answer_now_finds_the_4a_4b_4c_curriculum_entry_real_data()
    test_chart_multi_code_comparison_describes_both_accounts()
    test_chart_multi_code_comparison_bypasses_the_triggers_gate()
    test_chart_multi_code_comparison_no_longer_drops_the_second_account()
    test_chart_single_code_questions_are_completely_unaffected()
    test_chart_two_numbers_without_comparison_word_do_not_trigger_the_new_path()
    test_decision_matches_the_work_order_example_sgk_tavan()
    test_decision_never_carries_an_answer_field()
    test_decision_preferred_route_is_always_a_known_kaizen_brain_route()
    test_decision_exact_tool_intents_require_verified_confidence()
    test_decision_refines_intent_beyond_classifys_four_buckets_without_touching_classify()
    test_decision_reason_field_is_always_a_non_empty_string()
    test_retrieval_min_coverage_threshold_is_060_non_strict_and_exact_boundary_passes()
    test_retrieval_strict_mode_requires_full_100_percent_coverage()
    test_retrieval_short_single_term_question_over_trusts_a_coincidental_match()
    test_retrieval_synonyms_are_not_recognized_no_thesaurus()
    test_retrieval_word_order_does_not_affect_coverage_or_phrase_ok()
    test_retrieval_long_natural_question_dilutes_coverage_with_extra_real_words()
    test_retrieval_stemmer_fails_on_accusative_yi_yı_yu_yu_suffix()
    test_retrieval_stemmer_fails_on_dative_ye_ya_suffix()
    test_retrieval_tokenizer_no_longer_shreds_slash_codes_after_fix()
    test_retrieval_significance_filter_no_longer_drops_slash_code_fragments_after_fix()
    test_retrieval_information_exists_locally_and_extractive_answer_now_returns_it_after_fix()
    test_retrieval_multi_topic_comparison_question_now_returns_both_topics_after_frame_fix()
    test_retrieval_needs_current_research_false_positive_no_longer_hides_stable_knowledge_after_frame_fix()
    test_classify_documents_the_four_intents_and_their_keyword_sets()
    test_classify_false_negative_account_code_reference_is_no_longer_fatal_after_chart_fix()
    test_classify_false_negative_sgk_regime_codes_without_literal_sgk_word()
    test_classify_false_negative_is_not_always_fatal_thanks_to_general_fallback()
    test_classify_false_positive_verb_conjugation_contains_accounting_term_as_substring()
    test_classify_false_positive_causes_unnecessary_research()
    test_trace_does_not_change_the_returned_answer_text()
    test_trace_arithmetic_and_chart_are_verified()
    test_trace_general_domain_uses_model_and_marks_unknown()
    test_trace_memory_grounded_is_supported_with_retrieval_score()
    test_trace_pending_card_then_conflicted_after_contradiction()
    test_trace_empty_question_is_refusal()

    test_search_resilience_retries_and_succeeds_after_transient_timeout()
    test_search_resilience_raises_after_retries_exhausted_on_persistent_timeout()
    test_search_resilience_backoff_uses_injectable_sleep_with_bounded_exponential_delay()
    test_search_resilience_http_429_raises_rate_limited_error_with_retry_after()
    test_search_resilience_http_500_502_503_are_retryable_and_map_to_unavailable()
    test_search_resilience_http_404_is_not_retried()
    test_search_resilience_malformed_json_is_not_retried()
    test_search_resilience_connection_refused_is_retryable_and_maps_to_unavailable()
    test_search_resilience_successful_search_status_is_ok()
    test_search_resilience_empty_results_status_is_empty_not_error()
    test_search_resilience_single_engine_dependency_flagged_when_only_one_engine_contributes()
    test_search_resilience_multi_engine_results_not_flagged_as_single_engine_dependency()
    test_search_resilience_one_engine_broken_other_succeeds_still_returns_usable_results()
    test_search_resilience_total_engine_outage_recommends_fallback_with_reason()
    test_search_resilience_fallback_not_needed_for_normal_result_case()
    test_search_resilience_exceptions_are_never_silently_converted_to_empty_outcome()
    test_search_resilience_provider_health_starts_healthy()
    test_search_resilience_provider_health_becomes_unavailable_after_consecutive_failures()
    test_search_resilience_provider_health_recovers_to_healthy_after_success_following_failures()
    test_search_resilience_rate_limit_triggers_cooldown_and_subsequent_call_fails_fast()
    test_search_resilience_cooldown_expires_and_next_call_reaches_network_again()
    test_search_resilience_burst_protection_enforces_minimum_interval_via_injectable_sleep()
    test_search_resilience_burst_protection_does_not_delay_when_enough_time_has_passed()
    test_search_resilience_duplicate_url_dedup_still_works()
    test_search_resilience_turkish_unicode_preserved_with_new_status_fields()
    test_search_resilience_pdf_detection_still_works()
    test_search_resilience_domain_filtering_still_applied_with_resilience_wrapper()
    test_search_resilience_observability_debug_info_available_after_successful_call()
    test_search_resilience_observability_debug_info_available_after_failed_call()

    test_transfer_dataset_has_all_seven_mandated_families()
    test_transfer_dataset_each_scenario_has_distinct_b_and_d_questions()
    test_transfer_dataset_no_annual_figures_leak_into_principle_statements()
    test_principle_positive_transfer_donemsellik()
    test_principle_positive_transfer_borc_alacak()
    test_principle_positive_transfer_hesap_siniflandirma()
    test_principle_positive_transfer_ozun_onceligi()
    test_principle_positive_transfer_maliyet_ilkesi()
    test_principle_positive_transfer_amortisman()
    test_principle_positive_transfer_sgk_statu()
    test_principle_negative_transfer_rejects_all_seven_counter_examples()
    test_principle_negative_transfer_sgk_counter_example_is_a_fact_not_a_principle()
    test_principle_not_found_for_unrelated_question()
    test_principle_multiple_candidates_are_both_visible_when_scores_are_close()
    test_principle_confidence_levels_are_one_of_the_four_labels()
    test_principle_low_or_none_confidence_never_forces_a_selection()
    test_principle_confidence_never_reaches_verified_label()
    test_principle_registry_rows_never_contain_annual_figures()
    test_principle_registry_every_row_has_non_empty_provenance()
    test_principle_registry_has_exactly_the_seven_curated_principles()
    test_principle_retrieval_handles_turkish_unicode_case_variants()
    test_principle_different_words_same_structure_still_transfers()
    test_principle_same_words_different_structure_does_not_transfer()
    test_principle_trace_output_shows_candidates_selected_confidence_rejected_reason()
    test_principle_trace_fields_default_empty_when_principle_layer_not_used()
    test_principle_decision_bridge_never_claims_verified_and_uses_known_route()

    test_learning_brain_flag_off_no_augmentation_default_behavior()
    test_learning_brain_high_confidence_augments_prompt_assisted_mode()
    test_learning_brain_low_none_never_touches_prompt()
    test_learning_brain_domain_restricted_to_accounting()
    test_learning_brain_never_reached_by_exact_tools_or_facts()
    test_learning_brain_engine_production_default_is_disabled()
    test_learning_brain_one_line_revert_contract()
    test_learning_brain_ab_reality_twenty_grounded_questions()
    test_subquestion_rejects_empty_fields()
    test_research_plan_requires_at_least_one_subquestion()
    test_evidence_rejects_invalid_source_type_and_confidence()
    test_evidence_official_flag_must_match_source_type()
    test_evidence_has_real_content_distinguishes_snippet_only()
    test_claim_requires_at_least_one_evidence_id_and_valid_status()
    test_research_result_verified_claims_must_be_subset_of_claims()
    test_research_result_rejects_snippet_only_verified_claim()
    test_research_result_status_must_be_in_contract()
    test_research_trigger_needed_cases()
    test_research_trigger_not_needed_cases()
    test_research_trigger_domain_gate_blocks_non_accounting_even_with_no_local_evidence()
    test_research_trigger_local_evidence_found_true_always_wins()
    test_research_planner_topic_and_period_detection()
    test_research_planner_no_unnecessary_subquestions_when_no_period()
    test_research_planner_sgk_topic_includes_sgk_domain_subquery()
    test_research_planner_no_duplicate_queries_within_a_plan()
    test_research_planner_never_hallucinates_a_number_not_in_the_question()
    test_research_planner_returns_a_valid_research_plan_contract()
    test_fetcher_normal_https_html_succeeds()
    test_fetcher_pdf_content_type_succeeds()
    test_fetcher_follows_redirect_and_revalidates_target()
    test_fetcher_redirect_to_localhost_is_blocked_not_silently_followed()
    test_fetcher_localhost_direct_is_blocked()
    test_fetcher_127_0_0_1_is_blocked()
    test_fetcher_private_ip_is_blocked()
    test_fetcher_file_scheme_is_blocked()
    test_fetcher_credentials_in_url_is_blocked()
    test_fetcher_oversized_response_is_rejected()
    test_fetcher_timeout_is_reported_not_raised()
    test_fetcher_timeout_during_body_read_is_reported_not_raised()
    test_fetcher_403_is_never_bypassed()
    test_fetcher_429_is_never_bypassed()
    test_fetcher_robots_deny_blocks_before_any_content_fetch()
    test_fetcher_robots_unreadable_fails_safe_deny_not_permissive()
    test_fetcher_robots_404_means_allow_all()
    test_fetcher_malformed_url_is_rejected()
    test_extract_html_returns_title_date_and_excludes_nav_footer()
    test_extract_pdf_routing_degrades_gracefully_on_corrupt_bytes()
    test_extract_non_ok_fetch_outcome_returns_empty_content()
    test_best_passage_picks_most_relevant_paragraph_not_whole_page()
    test_best_passage_truncates_to_max_chars()
    test_best_passage_empty_text_returns_empty()

    test_source_type_official_gib_and_sgk()
    test_source_type_professional_and_unknown()
    test_detect_period_prefers_published_at_over_text()
    test_detect_period_falls_back_to_text_year()
    test_detect_period_missing_returns_none_not_guessed()
    test_temporal_matches_rejects_stale_source_for_current_question()
    test_build_evidence_snippet_only_never_high_confidence()
    test_build_evidence_official_source_matching_period_is_high_confidence()
    test_build_evidence_stale_source_downgrades_confidence_even_if_official()
    test_build_evidence_professional_source_matching_period_is_medium_confidence()
    test_build_evidence_missing_date_kept_as_none_not_guessed()

    test_resolve_topic_matches_question_terms()
    test_build_claims_supported_single_official_source_matching_period()
    test_build_claims_conflicted_when_two_independent_sources_disagree()
    test_build_claims_partial_when_single_non_official_source()
    test_build_claims_stale_official_source_downgrades_to_partial()
    test_build_claims_insufficient_when_source_is_unregistered()
    test_build_claims_skips_subquestion_with_no_evidence_at_all()
    test_build_claims_qualitative_supported_via_single_official_source()
    test_build_claims_qualitative_partial_via_single_professional_source()
    test_build_claims_qualitative_irrelevant_official_source_never_supported()
    test_build_claims_qualitative_snippet_only_never_produces_claim()

    test_run_research_never_raises_returns_search_unavailable_on_total_failure()
    test_run_research_supported_single_official_source()
    test_run_research_conflicted_when_two_independent_sources_disagree()
    test_run_research_search_degraded_and_missing_information_when_no_results()
    test_run_research_partial_when_only_some_subquestions_supported()
    test_run_research_survives_unexpected_fetcher_exception_for_one_url()
    test_run_research_blocked_fetch_is_never_silently_treated_as_content()

    test_research_engine_disabled_by_default_uses_hermes_unchanged()
    test_research_engine_enabled_but_no_provider_falls_back_safely()
    test_research_engine_supported_result_replaces_hermes_call()
    test_research_engine_insufficient_result_still_falls_back_to_hermes()
    test_research_engine_unexpected_exception_never_crashes_answer()
    test_format_research_result_only_accepts_supported_with_verified_claims()

    test_status_mapper_labels_are_turkish_and_cover_all_states()
    test_status_mapper_summarize_trace_reflects_real_route_and_confidence()
    test_status_mapper_never_fabricates_unknown_route()
    test_context_panel_summary_hides_technical_fields()
    test_full_inspector_lines_exposes_all_trace_fields()
    test_error_presenter_never_leaks_raw_exception_to_user_message()
    test_conversation_history_is_session_only_and_independent_of_kaizen_memory()

    test_experience_model_has_the_ten_mandated_fields()
    test_experience_model_rejects_empty_signature_and_strategy()
    test_experience_model_rejects_unknown_outcome_and_verification()
    test_experience_model_d2_has_no_raw_fact_or_answer_field()
    test_experience_model_d3_reusable_true_requires_user_approved_true_at_construction()
    test_reflection_store_record_and_get_round_trips()
    test_reflection_store_d3_no_auto_trust_two_separate_explicit_calls_required()
    test_reflection_store_list_filters_by_signature_outcome_and_reusable()
    test_experience_model_is_never_imported_by_kaizen_brain_d4()

    from tests import test_learning_runtime_v1
    import inspect
    for name, test in inspect.getmembers(test_learning_runtime_v1, inspect.isfunction):
        if (name.startswith("test_") and test.__module__ == test_learning_runtime_v1.__name__
                and not getattr(test, "__unittest_skip__", False)):
            test()

    from tests import test_runtime_integration_recovery
    for name, test in inspect.getmembers(test_runtime_integration_recovery, inspect.isfunction):
        if name.startswith("test_") and test.__module__ == test_runtime_integration_recovery.__name__:
            test()

    from tests import test_subsystem_integrations
    for name, test in inspect.getmembers(test_subsystem_integrations, inspect.isfunction):
        if name.startswith("test_") and test.__module__ == test_subsystem_integrations.__name__:
            test()

    from tests import test_accountant_phase1
    for name, test in inspect.getmembers(test_accountant_phase1, inspect.isfunction):
        if name.startswith("test_") and test.__module__ == test_accountant_phase1.__name__:
            test()

    from tests import test_accountant_phase2
    for name, test in inspect.getmembers(test_accountant_phase2, inspect.isfunction):
        if name.startswith("test_") and test.__module__ == test_accountant_phase2.__name__:
            test()

    from tests import test_accountant_phase3
    for name, test in inspect.getmembers(test_accountant_phase3, inspect.isfunction):
        if name.startswith("test_") and test.__module__ == test_accountant_phase3.__name__:
            test()

    from tests import test_accountant_phase4
    for name, test in inspect.getmembers(test_accountant_phase4, inspect.isfunction):
        if name.startswith("test_") and test.__module__ == test_accountant_phase4.__name__:
            test()

    from tests import test_document_engine
    for name, test in inspect.getmembers(test_document_engine, inspect.isfunction):
        if name.startswith("test_") and test.__module__ == test_document_engine.__name__:
            test()

    from tests import test_kazen_desktop
    for name, test in inspect.getmembers(test_kazen_desktop, inspect.isfunction):
        if name.startswith("test_") and test.__module__ == test_kazen_desktop.__name__:
            test()

    print("\n==============================")
    print("TUM KAIZEN TESTLERI: BASARILI")
    print("==============================")


if __name__ == "__main__":
    run_all()
