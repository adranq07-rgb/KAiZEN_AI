"""Full integration test for Kaizen Brain v2."""
import sys
import tempfile
import json
import os
sys.path.insert(0, r'C:\Users\ANL\Desktop\KAZEN_AI')

from core.kaizen_brain import KaizenBrain
from learning.principle_discovery import PrincipleDiscoveryEngine, LIFECYCLE_ACTIVE, LIFECYCLE_QUARANTINED
from memory.brain_manager import BrainManager
from memory.principle_registry import PrincipleRegistry
from memory.learning_store import LearningStore
from memory.reflection_store import ReflectionStore


def test_kaizen_brain_v2_integration():
    """Test KaizenBrain with principle discovery enabled."""
    
    print('=== KaizenBrain v2 Integration Test ===')
    
    # Create temporary directory for stores
    tmpdir = tempfile.mkdtemp()
    
    # Create learning store
    learning_store = LearningStore(path=os.path.join(tmpdir, 'learning.sqlite3'))
    
    # Create reflection store
    reflection_store = ReflectionStore(path=os.path.join(tmpdir, 'reflections.sqlite3'))
    
    # Create principle registry
    principle_registry = PrincipleRegistry(db_path=os.path.join(tmpdir, 'principles.sqlite3'))
    
    # Create brain manager
    brain_manager = BrainManager(
        learning_store=learning_store,
        reflection_store=reflection_store,
    )
    
    # Create a simple accounting agent
    class SimpleAccountingAgent:
        def ask(self, message):
            return "Kaizen: Test cevap"
        def learn(self, question, wrong_answer, correct_answer, user_note=None):
            return "Kaizen: Düzeltme kaydedildi."
    
    accounting_agent = SimpleAccountingAgent()
    
    # Create simple provider
    class SimpleProvider:
        provider = None
        @property
        def is_offline(self):
            return True
    
    provider = SimpleProvider()
    
    # Create KaizenBrain with principle discovery enabled
    brain = KaizenBrain(
        provider=provider,
        accounting_agent=accounting_agent,
        learning_store=learning_store,
        brain_manager=brain_manager,
        principle_discovery_enabled=True,
        principle_discovery_min_support=3,
        strict_fact_safety=False,
    )
    
    print(f'Brain created with principle_discovery_enabled={brain.principle_discovery_enabled}')
    print(f'Principle discovery engine: {brain._principle_discovery is not None}')
    
    # Test that _principle_registry is set
    print(f'_principle_registry: {brain._principle_registry is not None}')
    
    # Test answer method with a simple accounting question
    print('\n--- Testing answer() with simple question ---')
    answer = brain.answer('muhasebe: stok değerleme yöntemleri nedir?')
    print(f'Answer: {answer}')
    print(f'Last route: {brain.last_route}')
    print(f'Principle selected for strategy: {brain.last_trace.principle_selected_for_strategy if brain.last_trace else None}')
    print(f'Retrieved principle ID: {brain.last_trace.retrieved_principle_id if brain.last_trace else None}')
    
    # Test that principle discovery was triggered (may not find principles yet since no experiences)
    print(f'\nTrace principle_discovered: {brain.last_trace.principle_discovered if brain.last_trace else None}')
    print(f'Trace principle_confidence: {brain.last_trace.principle_confidence if brain.last_trace else None}')
    
    print('\n=== Integration Test Completed ===')
    return brain


if __name__ == '__main__':
    brain = test_kaizen_brain_v2_integration()