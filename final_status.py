#!/usr/bin/env python
"""Final Brain v2 status check."""
import sys
import os

sys.path.insert(0, r'C:\Users\ANL\Desktop\KAZEN_AI')

print("=" * 60)
print("FINAL BRAIN V2 STATUS CHECK")
print("=" * 60)
print()

# 1. principle_discovery.py core module
from learning import principle_discovery
pd_names = [n for n in dir(principle_discovery) if not n.startswith('_')]
print("1. learning.principle_discovery.py: LOADED")
print(f"   Module-level names: {len(pd_names)} items")
print()

# 2. PrincipleDiscoveryEngine instantiation
from learning.principle_discovery import PrincipleDiscoveryEngine
import tempfile
from memory.brain_manager import BrainManager
from memory.principle_registry import PrincipleRegistry
from memory.learning_store import LearningStore
from memory.reflection_store import ReflectionStore

tmpdir = tempfile.mkdtemp()
ls = LearningStore(path=os.path.join(tmpdir, 'learning.sqlite3'))
rs = ReflectionStore(path=os.path.join(tmpdir, 'reflections.sqlite3'))
reg = PrincipleRegistry(db_path=os.path.join(tmpdir, 'principles.sqlite3'))
bm = BrainManager(learning_store=ls, reflection_store=rs)
engine = PrincipleDiscoveryEngine(
    principle_registry=reg,
    reflection_store=rs,
    brain_manager=bm,
)
print("2. PrincipleDiscoveryEngine: INSTANTIATED OK")
print(f"   has discover_principle: {hasattr(engine, 'discover_principle')}")
print(f"   has retrieve_principle_for_question: {hasattr(engine, 'retrieve_principle_for_question')}")
print(f"   has record_outcome: {hasattr(engine, 'record_outcome')}")
print(f"   has _equivalent_principle_exists: {hasattr(engine, '_equivalent_principle_exists')}")
print()

# 3. KaizenBrain integration
from core.kaizen_brain import KaizenBrain
import inspect
sig = inspect.signature(KaizenBrain.__init__)
params = list(sig.parameters.keys())
print("3. core.kaizen_brain.py:")
print(f"   principle_discovery_enabled in params: {'principle_discovery_enabled' in params}")
print(f"   principle_discovery_min_support in params: {'principle_discovery_min_support' in params}")
print()

# 4. principle_registry has QUARANTINED
from memory.principle_registry import STATUS_QUARANTINED
print(f"4. memory.principle_registry: STATUS_QUARANTINED = {STATUS_QUARANTINED}")
print()

# 5. Check FACT_LIKE_PATTERN exists
from learning.principle_discovery import _FACT_LIKE_PATTERN
print(f"5. _FACT_LIKE_PATTERN compiled: {_FACT_LIKE_PATTERN is not None}")

print()
print("=" * 60)
print("BRAIN V2 IMPLEMENTATION STATUS: READY FOR RUNTIME DEMONSTRATION")
print("=" * 60)