#!/usr/bin/env python
"""Check Brain v2 components."""
import sys
import os

sys.path.insert(0, r'C:\Users\ANL\Desktop\KAZEN_AI')

print("=" * 70)
print("BRAIN V2 COMPONENT CHECKS")
print("=" * 70)
print()

checks = []

# 1. principle_discovery module
try:
    from learning.principle_discovery import PrincipleDiscoveryEngine, DiscoveredPrinciple, LIFECYCLE_ACTIVE, LIFECYCLE_QUARANTINED, MIN_INDEPENDENT_EXPERIENCES
    checks.append(('principle_discovery module', True))
except Exception as e:
    checks.append(('principle_discovery module', False, str(e)))

# 2. principle_registry has QUARANTINED
try:
    from memory.principle_registry import STATUS_QUARANTINED
    checks.append(('principle_registry STATUS_QUARANTINED', True))
except Exception as e:
    checks.append(('principle_registry STATUS_QUARANTINED', False, str(e)))

# 3. KaizenBrain has new params
try:
    from core.kaizen_brain import KaizenBrain
    import inspect
    sig = inspect.signature(KaizenBrain.__init__)
    params = list(sig.parameters.keys())
    checks.append(('KaizenBrain principle_discovery_enabled param', 'principle_discovery_enabled' in params))
    checks.append(('KaizenBrain principle_discovery_min_support param', 'principle_discovery_min_support' in params))
except Exception as e:
    checks.append(('KaizenBrain params', False, str(e)))

# 4. PrincipleDiscoveryEngine instantiation
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
    engine = PrincipleDiscoveryEngine(principle_registry=reg, reflection_store=rs, brain_manager=bm)
    checks.append(('PrincipleDiscoveryEngine instantiation', True))
    checks.append(('has discover_principle', hasattr(engine, 'discover_principle')))
    checks.append(('has retrieve_principle_for_question', hasattr(engine, 'retrieve_principle_for_question')))
    checks.append(('has record_outcome', hasattr(engine, 'record_outcome')))
except Exception as e:
    checks.append(('PrincipleDiscoveryEngine', False, str(e)))

# 5. _FACT_LIKE_PATTERN
try:
    from learning.principle_discovery import _FACT_LIKE_PATTERN
    checks.append(('_FACT_LIKE_PATTERN exists', _FACT_LIKE_PATTERN is not None))
except Exception as e:
    checks.append(('_FACT_LIKE_PATTERN exists', False, str(e)))

print("=" * 70)
results = []
for item in checks:
    if len(item) == 2:
        name, result = item
        status = 'PASS' if result else 'FAIL'
        results.append((name, status))
        status_str = 'PASS' if status == 'PASS' else 'FAIL'
        print(f"  {status_str} {name}")
    else:
        name, result, error = item
        status = 'PASS' if result else 'FAIL'
        results.append((name, status))
        status_str = 'PASS' if status == 'PASS' else 'FAIL'
        print(f"  {status_str} {name} - {error}")

print()
print("=" * 70)
all_pass = all(r[1] == 'PASS' for r in results)
print(f'OVERALL: {"ALL PASS" if all_pass else "SOME FAILURES"}')