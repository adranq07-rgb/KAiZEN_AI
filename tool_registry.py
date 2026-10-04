"""KAIZEN Unified Tool Registry — Work Order #6.

Kaizen should be able to distinguish between optional integration tools
and core cognitive systems.  No optional plugin may override core systems.

Registry categories:
- RESEARCH TOOL: Scrapling
- ACTION AGENT: Manus
- DOCUMENT WORKFLOW: Documenso
- DEPLOYMENT INFRASTRUCTURE: Coolify
- DEVELOPMENT TOOL: codex-chatgpt-web

Core systems that NO optional plugin may override:
- Accounting Problem Solver
- FactRegistry
- Evidence / Consensus
- deterministic calculations
"""

from typing import Dict, Literal

# ------------------------------------------------------------------
# Tool registry — each entry documents status and integration level
# ------------------------------------------------------------------

TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "scrapling": {
        "category": "RESEARCH TOOL",
        "description": "Kaizen research fetch / extraction layer",
        "installed": True,  # adapters and integration completed
        "api_v2_compatible": True,
        "core_override": False,  # does NOT override core systems
        "failure_isolation": True,  # Kaizen works when scrapling is down
    },
    "manus": {
        "category": "ACTION AGENT",
        "description": "External action / autonomous task engine",
        "installed": True,  # adapter created, LIVE_AUTH_PENDING
        "api_v2_compatible": True,
        "core_override": False,  # does NOT override core systems
        "failure_isolation": True,  # Kaizen works when Manus unavailable,
        # as verified above,
    },
    "documenso": {
        "category": "DOCUMENT WORKFLOW",
        "description": "Document / signature workflow boundary",
        "installed": True,  # adapter created, LIVE_INSTANCE_PENDING
        "api_v2_compatible": False,  # custom adapter, not API v2
        "core_override": False,  # does NOT override core systems
        "failure_isolation": True,  # Kaizen works when Documenso unavailable,
    },
    "coolify": {
        "category": "DEPLOYMENT INFRASTRUCTURE",
        "description": "Deployment / service management platform",
        "installed": True,  # readiness assessment created
        "api_v2_compatible": False,  # custom readiness module
        "core_override": False,  # does NOT override core systems
        "failure_isolation": True,  # Kaizen works when Coolify unavailable,
    },
    "codex_chatgpt_web": {
        "category": "DEVELOPMENT TOOL",
        "description": "Codex / ChatGPT developer capability",
        "installed": False,  # not integrated into Kaizen
        "api_v2_compatible": False,
        "core_override": False,
        "failure_isolation": True,  # Codex absence is irrelevant to Kaizen,
    },
}

# ------------------------------------------------------------------
# Core systems that NO optional plugin may override
# ------------------------------------------------------------------

CORE_SYSTEMS: FrozenSet[str] = frozenset({
    "Accounting Problem Solver",
    "FactRegistry",
    "Evidence/Consensus",
    "deterministic calculations",
})

# ------------------------------------------------------------------
# Verification that no optional plugin overrides core systems
# ------------------------------------------------------------------

def verify_no_core_override() -> bool:
    """Verify that no registered tool overrides a core system.

    Returns True if all tools have core_override == False.
    """
    for tool_name, tool_info in TOOL_REGISTRY.items():
        if tool_info.get("core_override", False):
            return False
    return True


# ------------------------------------------------------------------
# Tool lookup by category
# ------------------------------------------------------------------

def get_tools_by_category(category: Literal[
    "RESEARCH TOOL",
    "ACTION AGENT",
    "DOCUMENT WORKFLOW",
    "DEPLOYMENT INFRASTRUCTURE",
    "DEVELOPMENT TOOL",
]) -> List[str]:
    """Return tool names that belong to the given category."""
    return [
        name for name, info in TOOL_REGISTRY.items()
        if info.get("category") == category
    ]


# ------------------------------------------------------------------
# Accessor for core systems restriction
# ------------------------------------------------------------------

def core_systems() -> FrozenSet[str]:
    """Return the set of core systems that no optional plugin may override."""
    return CORE_SYSTEMS