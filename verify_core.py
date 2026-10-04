#!/usr/bin/env python
"""Verify core Brain v2 components."""
import sys
import os

sys.path.insert(0, r'C:\Users\ANL\Desktop\KAZEN_AI')

print("Brain v2 Core Checks")
print("=" * 50)

# 1. principle_discovery module
from learning.principle_discovery import (
    PrincipleDiscoveryEngine, DiscoveredPrinciple,
    LIFECYCLE_ACTIVE, LIFECYCLE_QUARANTINED,
    MIN_INDEPENDENT_EXPERIENCES,
    _FACT_LIKE_PATTERN
)
print("1. principle_discovery module: OK")
print("   MIN_INDEPENDENT_EXPERIENCES =", MIN_INDEPENDENT_EXPERIENCES)

# 2. principle_registry STATUS_QUARANTINED
from memory.principle_registry import STATUS_QUARANTINED
print("2. principle_registry STATUS_QUARANTINED =", STATUS_QUARANTINED)

# 3. KaizenBrain params
from core.kaizen_brain import KaizenBrain
import inspect
sig = inspect.signature(KaizenBrain.__init__)
params = list(sig.parameters.keys())
has_enabled = 'principle_discovery_enabled' in params
has_min = 'principle_discovery_min_support' in params
print("3. KaizenBrain params: enabled=", has_enabled, "min_support=", has_min)

# 4. _FACT_LIKE_PATTERN works
test_text = "Soruda 2026 oran %50 var"
has_fact = bool(_FACT_LIKE_PATTERN.search(test_text))
print("4. _FACT_LIKE_PATTERN detects fact text:", "yes" if has_fact else "no")

test_text2 = "Dönemi belirle, araştır, doğrula"
has_fact2 = bool(_FACT_LIKE_PATTERN.search(test_text2))
print("   (should be no for strategy text:", "yes" if has_fact2 else "no", ")")

# 5. Minimum independent experiences
print("5. MIN_INDEPENDENT_EXPERIENCES =", MIN_INDEPENDENT_EXPERIENCES, "(should be 3)")

print()
print("All 5 core checks complete.")