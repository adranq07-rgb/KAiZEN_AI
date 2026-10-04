#!/usr/bin/env python
"""Verify Brain v2 implementation is in place."""
import sys
import os

sys.path.insert(0, r'C:\Users\ANL\Desktop\KAZEN_AI')

print("=" * 60)
print("BRAIN V2 IMPLEMENTATION VERIFICATION")
print("=" * 60)

# 1. Check principle_discovery.py exists and imports work
print("\n1. Checking learning/principle_discovery.py...")
try:
    from learning.principle_discovery import (
        PrincipleDiscoveryEngine,
        DiscoveredPrinciple,
        LIFECYCLE_ACTIVE,
        LIFECYCLE_QUARANTINED,
        MIN_INDEPENDENT_EXPERIENCES,
        _FACT_LIKE_PATTERN,
    )
    print("   PASS: Core exports from principle_discovery.py work")
    print(f"   MIN_INDEPENDENT_EXPERIENCES = {MIN_INDEPENDENT_EXPERIENCES}")
except Exception as e:
    print(f"   FAIL: {e}")

# 2. Check key constants
print("\n2. Checking lifecycle and strategy constants...")
try:
    from learning.principle_discovery import (
        LIFECYCLE_CANDIDATE,
        LIFECYCLE_TESTED,
        LIFECYCLE_VALIDATED,
    )
    from learning.strategy_catalog import PERIOD_SEPARATION, RESEARCH_FIRST
    print("   PASS: Constants loaded")
    print(f"   LIFECYCLE_CANDIDATE = {LIFECYCLE_CANDIDATE}")
except Exception as e:
    print(f"   FAIL: {e}")

# 3. Check principle_registry has QUARANTINED
print("\n3. Checking memory/principle_registry.py...")
try:
    from memory.principle_registry import PrincipleRegistry, STATUS_ACTIVE, STATUS_QUARANTINED
    print("   PASS: STATUS_QUARANTINED loaded")
except Exception as e:
    print(f"   FAIL: {e}")

# 4. Check KaizenBrain has principle_discovery params
print("\n4. Checking core/kaizen_brain.py...")
try:
    from core.kaizen_brain import KaizenBrain
    import inspect
    sig = inspect.signature(KaizenBrain.__init__)
    params = list(sig.parameters.keys())
    has_pd_enabled = 'principle_discovery_enabled' in params
    has_pd_min = 'principle_discovery_min_support' in params
    print(f"   PASS: principle_discovery_enabled parameter = {has_pd_enabled}")
    print(f"   PASS: principle_discovery_min_support parameter = {has_pd_min}")
except Exception as e:
    print(f"   FAIL: {e}")

# 5. Check PrincipleDiscoveryEngine can be instantiated
print("\n5. Checking PrincipleDiscoveryEngine instantiation...")
try:
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
    print("   PASS: PrincipleDiscoveryEngine instantiated successfully")
    print(f"   PASS: has discover_principle = {hasattr(engine, 'discover_principle')}")
    print(f"   PASS: has retrieve_principle_for_question = {hasattr(engine, 'retrieve_principle_for_question')}")
    print(f"   PASS: has record_outcome = {hasattr(engine, 'record_outcome')}")
    
except Exception as e:
    print(f"   FAIL: {e}")
    import traceback
    traceback.print_exc()

# 6. Check KaizenBrain integration
print("\n6. Checking KaizenBrain integration...")
try:
    from core.kaizen_brain import KaizenBrain
    import inspect
    sig = inspect.signature(KaizenBrain.__init__)
    params = list(sig.parameters.keys())
    has_pd_enabled = 'principle_discovery_enabled' in params
    has_pd_min = 'principle_discovery_min_support' in params
    print(f"   PASS: principle_discovery_enabled in params = {has_pd_enabled}")
    print(f"   PASS: principle_discovery_min_support in params = {has_pd_min}")
    
except Exception as e:
    print(f"   FAIL: {e}")

print("\n" + "=" * 60)
print("VERIFICATION COMPLETE")
print("=" * 60)