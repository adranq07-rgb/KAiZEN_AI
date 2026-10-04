"""KAIZEN Coolify Readiness — Deployment / Service Management (Work Order #4).

Coolify is NOT a Kaizen cognitive runtime dependency.  This module prepares
Kaizen for future Coolify-managed deployment without breaking the currently
working local environment.

Key requirements (from Work Order #4):
- Coolify is NOT a Kaizen cognitive runtime dependency
- Do not install Coolify inside the Kaizen Python process
- Inventory services that could eventually be deployed independently:
  - Kaizen API/core
  - Research services
  - SearXNG
  - databases
  - optional supporting services
- Create only the deployment boundary/configuration/documentation required
  to make Kaizen Coolify-ready
- Do not migrate the currently working local environment
- Do not break Docker Desktop/SearXNG
- If a dedicated Linux host is not available:
    COOLIFY_READY
    DEPLOYMENT_HOST_PENDING
- Do NOT install a full Coolify server on the current Windows development PC
  just to claim integration.
"""

import os
from typing import Dict, Any, List

# ------------------------------------------------------------------
# Service inventory — services that could eventually be deployed
# independently via Coolify or similar platform.
# ------------------------------------------------------------------

SERVICE_INVENTORY: Dict[str, Dict[str, Any]] = {
    "kaizen_api": {
        "description": "Kaizen core API / runtime",
        "type": "python_service",
        "ports": [8080],
        "dependencies": ["python", "uvicorn"],
        "coolify_label": "kaizen-api",
    },
    "research_service": {
        "description": "Kaizen research engine (SearXNG + Scrapling)",
        "type": "python_service",
        "ports": [8081],
        "dependencies": ["python", "searxng"],
        "coolify_label": "research-service",
    },
    "searxng": {
        "description": "Privacy-respecting metasearch engine",
        "type": "docker_service",
        "ports": [8888],
        "dependencies": ["docker"],
        "coolify_label": "searxng",
    },
    "database": {
        "description": "Kaizen data store (PostgreSQL / SQLite)",
        "type": "database_service",
        "ports": [5432],
        "dependencies": ["postgres", "sqlite3"],
        "coolify_label": "kaizen-db",
    },
}

# ------------------------------------------------------------------
# Coolify readiness assessment
# ------------------------------------------------------------------

DEPLOYMENT_ASSESSMENT: Dict[str, Any] = {
    "coolify_ready": False,
    "deployment_host_pending": True,
    "local_runtime": "Windows (development)",
    "services_inventory": SERVICE_INVENTORY,
    "migration_required": False,  # Do not migrate working local env
    "breaks_docker_desktop": False,  # Do not break Docker Desktop/SearXNG
    "notes": [
        "Coolify is a deployment platform; it is not a cognitive runtime "
        "dependency.  Kaizen runs perfectly on the current Windows dev PC "
        "without Coolify.",
        "To be Coolify-ready, a dedicated Linux host with Docker is recommended.",
        "The service inventory above documents which services could be "
        "containerised and deployed independently.",
        "Do NOT install a full Coolify server on the current Windows PC.",
    ],
}


def get_assessment() -> Dict[str, Any]:
    """Return the Coolify readiness assessment."""
    return DEPLOYMENT_ASSESSMENT.copy()


# ------------------------------------------------------------------
# Boundary documentation — what a future Coolify deployment would need
# ------------------------------------------------------------------

DEPLOYMENT_BOUNDARY: Dict[str, Any] = {
    "description": "Services and configuration required for Coolify-managed deployment",
    "kaizen_api": {
        "entrypoint": "uvicorn core.main:app --host 0.0.0.0 --port 8080",
        "env_vars": ["KAIZEN_ENV", "LOG_LEVEL"],
    },
    "research_service": {
        "entrypoint": "python -m research.engine",
        "env_vars": ["SEARXNG_URL", "SCRAPLING_ENABLED"],
    },
    "searxng": {
        "entrypoint": "docker run -p 8888:8000 searxng/searxng:latest",
        "env_vars": ["SEARXNG_CONFIG"],
    },
    "database": {
        "entrypoint": "depends on chosen DB (PostgreSQL or SQLite)",
        "env_vars": ["DATABASE_URL", "POSTGRES_PASSWORD"],
    },
}


def get_deployment_boundary() -> Dict[str, Any]:
    """Return the deployment boundary documentation."""
    return DEPLOYMENT_BOUNDARY.copy()


# ------------------------------------------------------------------
# Quick sanity check — verify local environment is intact
# ------------------------------------------------------------------

def verify_local_environment() -> Dict[str, Any]:
    """Verify that the currently working local environment is intact
    and not broken by Coolify-related changes."""
    issues: List[str] = []
    warnings: List[str] = []

    # Check Docker Desktop
    try:
        import docker
        docker_version = docker.version.get("Version", "unknown")
    except Exception as e:
        issues.append(f"Docker Desktop check: {e}")

    # Check SearXNG status (installed but not necessarily running)
    try:
        import searxng
        warnings.append("SearXNG module importable (runtime not verified)")
    except ImportError:
        issues.append("SearXNG not installed")

    return {
        "local_environment_intact": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
    }


# ------------------------------------------------------------------
# Singleton export
# ------------------------------------------------------------------

def get_coolify_status() -> Dict[str, Any]:
    """Return the combined Coolify status: assessment + local environment."""
    return {
        "assessment": get_assessment(),
        "local_environment": verify_local_environment(),
    }