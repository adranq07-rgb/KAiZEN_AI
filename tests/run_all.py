from tests.test_core import test_core
from tests.test_dev_manager import test_dev_manager
from tests.test_logger import test_logger
from tests.test_model_security import test_model_security
from tests.test_hermes_bridge import test_hermes_bridge_lock, test_hermes_research_sources
from tests.test_memory import test_memory
from tests.test_accounting import test_accounting
from tests.test_ai_provider import test_ai_provider
from tests.test_tool_security import test_tool_security
from tests.test_experience_store import test_experience_store
from tests.test_cognee_memory import test_cognee_memory
from tests.test_accounting_sources import test_accounting_sources
from tests.test_accounting_consensus import test_accounting_consensus
from tests.test_learning_store import test_learning_store
from tests.test_math_calculator import test_math_calculator
from tests.test_kaizen_brain import (
    test_kaizen_brain, test_brain_independent_of_model, test_brain_current_question_uses_site_memory,
)
from tests.test_calculators import test_calculators
from tests.test_journal import test_journal
from tests.test_crawler import test_crawler, test_fetcher_encodes_turkish_characters_in_url
from tests.test_facts import test_facts, test_facts_ignores_space_grouped_tl_fragment
from tests.test_providers import test_providers
from tests.test_office_and_commands import test_office_tools, test_seed_loader, test_commands
from tests.test_golden_exam import test_golden_exam
from tests.test_accounting_brain import test_accounting_brain
from tests.test_self_learning import (
    test_knowledge_card_store_pending_confirm_and_contradiction,
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
from tests.test_brain_manager import (
    test_brain_manager_retrieval_delegates_to_retriever,
    test_brain_manager_verified_fact_answer_handles_missing_registry,
    test_brain_manager_remember_research_promotes_card_and_learning_store,
    test_brain_manager_remember_research_flags_contradiction_with_verified_facts,
)


def run_all():
    print("\nKAIZEN TESTLERI BASLIYOR...\n")

    test_core()
    test_dev_manager()
    test_logger()
    test_model_security()
    test_hermes_bridge_lock()
    test_hermes_research_sources()
    test_memory()
    test_accounting()
    test_ai_provider()
    test_tool_security()
    test_experience_store()
    test_cognee_memory()
    test_accounting_sources()
    test_accounting_consensus()
    test_learning_store()
    test_math_calculator()
    test_kaizen_brain()
    test_brain_independent_of_model()
    test_brain_current_question_uses_site_memory()
    test_calculators()
    test_journal()
    test_crawler()
    test_fetcher_encodes_turkish_characters_in_url()
    test_facts()
    test_facts_ignores_space_grouped_tl_fragment()
    test_providers()
    test_office_tools()
    test_seed_loader()
    test_commands()
    test_golden_exam()
    test_accounting_brain()
    test_knowledge_card_store_pending_confirm_and_contradiction()
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

    print("\n==============================")
    print("TUM KAIZEN TESTLERI: BASARILI")
    print("==============================")


if __name__ == "__main__":
    run_all()
