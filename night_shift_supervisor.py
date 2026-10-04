#!/usr/bin/env python3
"""
Kaizen AI Night Shift Supervisor

Manages long-running development tasks across multiple models/providers
with provider-aware failover, cooldown management, and session continuity.

Key features:
- Model pool from config with verified/candidate status
- Provider-aware failover (separate domains: OpenCode vs NVIDIA)
- Infrastructure-only failover (429, quota, etc. — NOT test/syntax errors)
- Cooldown and consecutive failure tracking
- Session continuity across model switches
- Config-driven model priority and enabled state
"""

import json
import subprocess
import sys
import time
import os
import signal
import argparse
import logging
from pathlib import Path
from datetime import datetime
from copy import deepcopy

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "night_shift_config.json"
REPO_ROOT = BASE_DIR.parent  # C:\Users\ANL\Desktop\KAZEN_AI

# Night Shift infrastructure paths
NIGHT_SHIFT_DIR = REPO_ROOT / ".nightshift"
CHECKPOINT_PATH = NIGHT_SHIFT_DIR / "checkpoints" / "runtime_state.json"
LOGS_DIR = NIGHT_SHIFT_DIR / "logs"

LOGGER = logging.getLogger("night_shift_supervisor")

# ---------------------------------------------------------------------------
# Error type classification
# ---------------------------------------------------------------------------

INFRASTRUCTURE_ERRORS = {
    "429", "rate_limit", "quota_exceeded", "usage_limit",
    "credits_exhausted", "provider_unavailable",
    "authentication_provider_error", "persistent_api_timeout",
    "5xx_threshold", "http_429", "http_5xx"
}

NON_FAILOVER_ERRORS = {
    "pytest_failure", "assertion_error", "syntax_error",
    "lint_error", "application_bug", "wrong_implementation",
    "test_regression"
}

# Ensure opencode is in PATH
npm_dir = r"C:\Users\ANL\AppData\Roaming\npm"
if npm_dir not in os.environ.get("PATH", ""):
    os.environ["PATH"] = npm_dir + os.pathsep + os.environ.get("PATH", "")

# Now find opencode
def find_opencode():
    import shutil
    return shutil.which("opencode") or "opencode"
    """Load the night shift model pool configuration."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config):
    """Save the model pool configuration."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def load_config():
    """Load the night shift model pool configuration."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_checkpoint():
    """Load runtime state from checkpoint file if it exists."""
    if CHECKPOINT_PATH.exists():
        try:
            with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
                state = json.load(f)
            LOGGER.info(f"Loaded checkpoint from {CHECKPOINT_PATH}")
            return state
        except Exception as e:
            LOGGER.warning(f"Failed to load checkpoint: {e}")
    return {}


def save_checkpoint(state):
    """Save runtime state to checkpoint file."""
    try:
        CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        LOGGER.info(f"Saved checkpoint to {CHECKPOINT_PATH}")
    except Exception as e:
        LOGGER.error(f"Failed to save checkpoint: {e}")


def now_ts():
    """Current timestamp as float."""
    return time.time()


def log_failover(event_type, data):
    """Structured logging for failover events to .nightshift/logs/."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_entry = {
        "timestamp": now_ts(),
        "event_type": event_type,
        "data": data
    }
    # Append to log file (one JSON object per line)
    log_file = LOGS_DIR / "failover.log"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


def redact_secrets(text):
    """Redact potential API keys, tokens, and secrets from text."""
    import re
    # Remove patterns that look like API keys/tokens
    patterns = [
        r'sk-[a-zA-Z0-9]{20,}',  # OpenAI-style keys
        r'[a-zA-Z0-9]{32,}',     # Long hex strings
        r'token=[^&\s]+',        # token= patterns
        r'key=[^&\s]+',          # key= patterns
    ]
    result = text
    for pattern in patterns:
        result = re.sub(pattern, "[REDACTED]", result)
    return result


def parse_error_code(error_str):
    """Extract error code from an error message string."""
    error_str = str(error_str).lower()
    for code in INFRASTRUCTURE_ERRORS:
        if code in error_str:
            return code
    for code in NON_FAILOVER_ERRORS:
        if code in error_str:
            return code
    return None


def is_infrastructure_error(error_str):
    """Check if the error is an infrastructure error that warrants failover."""
    return parse_error_code(error_str) in INFRASTRUCTURE_ERRORS


def is_non_failover_error(error_str):
    """Check if the error is a non-failover error (code bug, test failure, etc.)."""
    return parse_error_code(error_str) in NON_FAILOVER_ERRORS


# ---------------------------------------------------------------------------
# Model pool management
# ---------------------------------------------------------------------------


def get_enabled_models(config, provider_filter=None, verified_only=False):
    """Get enabled models from the pool, optionally filtered by provider and verification status."""
    pool = config["model_pool"]
    models = pool["verified"] if verified_only else pool["verified"] + pool["candidates"]

    if provider_filter:
        models = [m for m in models if m["provider"] == provider_filter]

    return [m for m in models if m["enabled"]]


def select_next_model(config, provider_filter=None, exclude_ids=None):
    """
    Select the next available model based on priority.
    Returns the model dict or None if no models available.
    """
    enabled = get_enabled_models(config, provider_filter=provider_filter)

    # Sort by priority (lower = higher priority), then by consecutive_failures (lower = better)
    sorted_models = sorted(
        enabled,
        key=lambda m: (m.get("priority", 999), m.get("consecutive_failures", 0))
    )

    # Filter out cooldown models and already-excluded IDs
    available = []
    for m in sorted_models:
        if exclude_ids and m["model_id"] in exclude_ids:
            continue
        # Check cooldown
        cooldown_until = m.get("cooldown_until")
        if cooldown_until and now_ts() < cooldown_until:
            # Still in cooldown, skip
            continue
        available.append(m)

    return available[0] if available else None


def update_model_status(config, model_id, updates):
    """Update model status in the configuration (failures, cooldown, last_result, etc.)."""
    pool = config["model_pool"]

    # Check both verified and candidates
    for category in ["verified", "candidates"]:
        for m in pool[category]:
            if m["model_id"] == model_id:
                for key, value in updates.items():
                    m[key] = value
                break
        else:
            continue
        break

    save_config(config)
    return config


def reset_model_failures(config, model_id):
    """Reset consecutive failures and cooldown for a model."""
    update_model_status(config, model_id, {
        "consecutive_failures": 0,
        "cooldown_until": None,
        "last_result": None,
        "last_latency": None
    })


def smoke_test_model(model_id, message="Check model accessibility and tool availability."):
    """
    Run a smoke test on a model with a read-only, harmless task.
    Returns a dict with test results.
    """
    import json
    from pathlib import Path

    LOGGER.info(f"Smoke testing model {model_id}")

    try:
        result = run_opencode(model_id, message, format_json=True)
        if result is None:
            return {
                "model": model_id,
                "api_success": False,
                "tool_access": False,
                "exit_code": None,
                "latency": None,
                "timeout": True,
                "error": "process_failed",
                "pass": False
            }

        parsed = parse_opencode_result(result)
        exit_code = result.returncode
        stderr = result.stderr or ""
        stdout = result.stdout or ""

        # Check for infrastructure errors (429, quota, etc.) - these are FAIL, not PASS
        error_str = stderr + stdout
        infra_errors = ["429", "rate limit", "quota exceeded", "credits exhausted"]
        has_infra_error = any(e in error_str.lower() for e in infra_errors)

        # Check exit code
        success = parsed.get("status") == "success" or exit_code == 0

        # Latency estimation from duration
        duration = None
        if hasattr(result, 'timeout') and result.timeout:
            duration = "timeout"
        elif "duration" in parsed:
            duration = parsed["duration"]

        # Tool access check - did the model successfully complete a read-only task?
        # Simple heuristic: successful exit code + no infrastructure errors = tool access
        tool_access = not has_infra_error and success
        api_success = True  # Model responded at all

        pass_result = not has_infra_error and success and api_success

        return {
            "model": model_id,
            "api_success": api_success,
            "tool_access": tool_access,
            "exit_code": exit_code,
            "latency": duration,
            "timeout": False,
            "error": None if pass_result else ("infra_error" if has_infra_error else "non_success"),
            "pass": pass_result
        }

    except Exception as e:
        LOGGER.error(f"Smoke test exception for {model_id}: {e}")
        return {
            "model": model_id,
            "api_success": False,
            "tool_access": False,
            "exit_code": None,
            "latency": None,
            "timeout": True,
            "error": str(e),
            "pass": False
        }


def select_model_from_pool(config, failed_model_id=None, provider_override=None):
    """
    Model selection logic inline for simulated UAT.
    Same logic as select_model but defined earlier for forward reference.
    """
    # First, try verified models (across providers based on priority)
    verified = get_enabled_models(config, verified_only=True)
    # Sort by priority (lower = higher priority)
    verified_sorted = sorted(verified, key=lambda m: m.get("priority", 999))

    # If we have a provider override, filter by that provider
    if provider_override:
        vs = [m for m in verified_sorted if m["provider"] == provider_override]
        if vs:
            # Filter out the failed model and cooldowned ones
            for m in vs:
                if m["model_id"] != failed_model_id:
                    cooldown = m.get("cooldown_until")
                    if not cooldown or now_ts() >= cooldown:
                        return m
            # If all verified models of this provider are cooldowned or failed,
            # fall through to candidates of same provider
            cs = [m for m in get_enabled_models(config, verified_only=False)
                  if m["provider"] == provider_override]
            cs_sorted = sorted(cs, key=lambda m: m.get("priority", 999))
            for m in cs_sorted:
                if m["model_id"] != failed_model_id:
                    cooldown = m.get("cooldown_until")
                    if not cooldown or now_ts() >= cooldown:
                        return m
            # If no verified or candidates available for this provider,
            # fall through to the other provider's verified models
            other_provider = "nvidia" if provider_override == "opencode" else "opencode"
            others = [m for m in verified_sorted if m["provider"] == other_provider]
            if others:
                for m in others:
                    if m["model_id"] != failed_model_id:
                        cooldown = m.get("cooldown_until")
                        if not cooldown or now_ts() >= cooldown:
                            return m
            return None

    # No provider override - try verified models first, respecting provider domains
    # Track which providers we've already tried to avoid cycling
    tried_providers = set()

    # Try verified models first
    for m in verified_sorted:
        if m["model_id"] == failed_model_id:
            continue
        cooldown = m.get("cooldown_until")
        if cooldown and now_ts() < cooldown:
            # Model is in cooldown, skip but track provider
            provider = m["provider"]
            if provider not in tried_providers:
                tried_providers.add(provider)
            continue
        # Check if we should avoid this provider due to wide cooldown
        if m["provider"] in tried_providers and len(tried_providers) >= 2:
            # Already tried two providers, skip
            continue
        return m

    # Mark first provider as tried
    # Fall through to candidates
    all_enabled = get_enabled_models(config, verified_only=False)
    all_sorted = sorted(all_enabled, key=lambda m: (m.get("priority", 999), m.get("consecutive_failures", 0)))

    # Separate by provider for domain-aware selection
    provider_order = ["opencode", "nvidia"]  # OpenCode first (local), then NVIDIA

    for provider in provider_order:
        provider_models = [m for m in all_sorted if m["provider"] == provider]
        for m in provider_models:
            if m["model_id"] == failed_model_id:
                continue
            cooldown = m.get("cooldown_until")
            if cooldown and now_ts() < cooldown:
                continue
            return m

    # If no model from preferred providers is available, try any remaining
    for m in all_sorted:
        if m["model_id"] == failed_model_id:
            continue
        cooldown = m.get("cooldown_until")
        if cooldown and now_ts() < cooldown:
            continue
        return m

    return None


def simulated_failover_uat(config, initial_model_id, task_message, cooldown_model_id=None):
    """
    Simulated UAT: Test A → simulated infrastructure failure → Model B → continue.
    Verifies that failover works deterministically without modifying Kaizen source files.
    
    Returns dict with UAT results.
    """
    import json
    from pathlib import Path
    import copy
    
    LOGGER.info(f"Running simulated failover UAT: {initial_model_id} -> next model")
    
    # Save original config state
    original_config = copy.deepcopy(config)
    
    # Step 1: Run with initial model (Model A)
    result_a = run_opencode(initial_model_id, task_message, format_json=True)
    
    if result_a is None:
        # Model A couldn't even start
        # Restore config
        save_config(original_config)
        return {
            "step_a_success": False,
            "step_a_error": "model_a_failed_to_start",
            "step_b_success": False,
            "failover_achieved": False,
            "message": "Model A failed to start, cannot run UAT"
        }
    
    parsed_a = parse_opencode_result(result_a)
    exit_code_a = result_a.returncode
    error_str_a = str(result_a.stderr or result_a.stdout or "")
    
    # Step 2: Simulate infrastructure error on Model A
    # Regardless of actual error, we simulate a 429/quota error to test failover
    # Update Model A's state as if it hit an infrastructure error
    update_model_status(original_config, initial_model_id, {
        "consecutive_failures": 3,  # Hit threshold
        "cooldown_until": now_ts() + 60 * 60,  # 1 hour cooldown (simulated)
        "last_result": "simulated_infra_error:429"
    })
    save_config(original_config)
    
    # Step 3: Select next model (Model B) - should skip cooldown Model A
    next_model = select_model_from_pool(original_config, failed_model_id=initial_model_id)
    
    if next_model is None:
        # Restore config
        save_config(original_config)
        return {
            "step_a_success": False,
            "step_b_success": False,
            "failover_achieved": False,
            "message": "No available models after Model A cooldown"
        }
    
    model_b_id = next_model["model_id"]
    LOGGER.info(f"Model B selected for failover: {model_b_id}")
    
    # Step 4: Run with Model B using same session
    result_b = run_opencode(model_b_id, task_message, format_json=True)
    
    step_b_success = False
    if result_b is not None:
        parsed_b = parse_opencode_result(result_b)
        step_b_success = parsed_b.get("status") == "success" or result_b.returncode == 0
    
    # Step 5: Verify checkpoint continuity
    checkpoint_state = load_checkpoint()
    
    # Restore original config
    save_config(original_config)
    
    # Clean up checkpoint
    if CHECKPOINT_PATH.exists():
        try:
            CHECKPOINT_PATH.unlink()
        except:
            pass
    
    uat_result = {
        "step_a_success": parsed_a.get("status") == "success" or exit_code_a == 0,
        "step_b_success": step_b_success,
        "model_a_id": initial_model_id,
        "model_b_id": model_b_id,
        "failover_achieved": step_b_success and parsed_a.get("status", "") != "success",
        "session_continuity": checkpoint_state.get("session_id") is not None,
        "message": "Simulated UAT: A -> infrastructure error cooldown -> B -> continue"
    }
    
    LOGGER.info(f"Simulated UAT result: {uat_result}")
    return uat_result


def set_model_failure(config, model_id, error_info):
    """Increment consecutive failures and set cooldown if threshold reached."""
    pool = config["model_pool"]

    for category in ["verified", "candidates"]:
        for m in pool[category]:
            if m["model_id"] == model_id:
                m["consecutive_failures"] = m.get("consecutive_failures", 0) + 1
                failover_config = config["model_pool"]["provider_domains"].get(m["provider"], {})
                max_failures = failover_config.get("max_consecutive_failures", 3)
                cooldown_minutes = failover_config.get("cooldown_minutes", 30)

                if m["consecutive_failures"] >= max_failures:
                    # Set cooldown
                    m["cooldown_until"] = now_ts() + cooldown_minutes * 60
                    LOGGER.warning(
                        f"Model {model_id} exceeded {max_failures} consecutive failures. "
                        f"Cooling down for {cooldown_minutes} minutes."
                    )
                else:
                    LOGGER.info(
                        f"Model {model_id} failure count: {m['consecutive_failures']}/{max_failures}"
                    )
                save_config(config)
                return config
    return config


# ---------------------------------------------------------------------------
# Provider-aware failover
# ---------------------------------------------------------------------------


def update_provider_status(config, provider, updates):
    """Update provider-level status (failure count, cooldown)."""
    domains = config["model_pool"]["provider_domains"]
    if provider in domains:
        for key, value in updates.items():
            domains[provider][key] = value
        save_config(config)
    return config


def reset_provider_failures(config, provider):
    """Reset provider-level consecutive failures and cooldown."""
    update_provider_status(config, provider, {
        "failure_count": 0,
        "cooldown_until": None
    })


def set_provider_failure(config, provider, error_info):
    """Increment provider failure count and set cooldown if threshold reached."""
    domains = config["model_pool"]["provider_domains"]
    if provider in domains:
        current_failures = domains[provider].get("failure_count", 0)
        max_failures = domains[provider].get("max_consecutive_failures", 3)
        cooldown_minutes = domains[provider].get("cooldown_minutes", 30)

        domains[provider]["failure_count"] = current_failures + 1

        if current_failures + 1 >= max_failures:
            domains[provider]["cooldown_until"] = now_ts() + cooldown_minutes * 60
            LOGGER.warning(
                f"Provider {provider} exceeded {max_failures} consecutive failures. "
                f"Cooling down for {cooldown_minutes} minutes. "
                f"All {provider} models will be temporarily disabled."
            )
            # Redact error info before logging
            redacted_error = redact_secrets(error_info)
            log_failover("provider_cooldown", {
                "provider": provider,
                "cooldown_minutes": cooldown_minutes,
                "error": redacted_error
            })
        else:
            LOGGER.info(
                f"Provider {provider} failure count: {current_failures + 1}/{max_failures}"
            )

        save_config(config)
    return config


# ---------------------------------------------------------------------------
# OpenCode execution
# ---------------------------------------------------------------------------


def run_opencode(model_id, message, session_id=None, continue_session=False, format_json=False):
    """
    Run OpenCode with the specified model and message.
    Returns the subprocess result.
    """
    ocmd = find_opencode()
    
    # On Windows, .CMD files need cmd /c prefix
    import os
    cmd_prefix = []
    if ocmd and (ocmd.endswith('.CMD') or ocmd.endswith('.BAT')):
        cmd_prefix = ['cmd', '/c']
    
    cmd = cmd_prefix + [
        ocmd, "run",
        "--model", model_id,
        "--format", "json" if format_json else "default"
    ]

    if session_id:
        cmd.extend(["--session", session_id])

    if continue_session:
        cmd.append("--continue")

    if message:
        cmd.append(str(message))

    LOGGER.info(f"Running OpenCode with model {model_id}: {' '.join(message[:20] if isinstance(message, list) else str(message).split()[:20])}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(BASE_DIR)  # Run from repo root where opencode is available
        )
        return result
    except subprocess.TimeoutExpired:
        LOGGER.error(f"OpenCode timeout with model {model_id}")
        return None
    except Exception as e:
        LOGGER.error(f"Error running OpenCode: {e}")
        return None


def parse_opencode_result(result):
    """Parse the OpenCode result and extract relevant information."""
    if result is None:
        return {"status": "error", "error": "process_timeout", "raw_output": None}

    try:
        import json
        stdout = result.stdout or ""
        stdout = stdout.strip() if stdout else ""
        parsed = json.loads(stdout) if stdout.strip() else {}
        return {
            "status": parsed.get("status", "unknown"),
            "error": parsed.get("error", None),
            "output": parsed.get("output", None),
            "exit_code": result.returncode,
            "duration": result.timeout if result is None else None,
            "raw_output": stdout[-500:] if stdout else None
        }
    except json.JSONDecodeError:
        return {
            "status": "error",
            "error": "json_parse_failed",
            "raw_output": (result.stdout[-500:] if result.stdout and len(result.stdout) > 500 else result.stdout) if result.stdout else None,
            "exit_code": result.returncode
        }


# ---------------------------------------------------------------------------
# Session continuity
# ---------------------------------------------------------------------------


def extract_session_id(result):
    """Try to extract session ID from OpenCode result."""
    try:
        import json
        parsed = json.loads(result.stdout) if result.stdout.strip() else {}
        return parsed.get("session_id", None)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Main supervisor loop
# ---------------------------------------------------------------------------


def select_model(config, failed_model_id=None, provider_override=None):
    """
    Select the next model to use.
    If provider_override is set, use that provider's next model.
    Otherwise, try verified models first, then candidates.
    Provider-aware: OpenCode and NVIDIA providers have separate failure domains.
    """
    # First, try verified models (across providers based on priority)
    verified = get_enabled_models(config, verified_only=True)
    # Sort by priority
    verified_sorted = sorted(verified, key=lambda m: m.get("priority", 999))

    # If we have a provider override, filter by that provider
    # This separates OpenCode vs NVIDIA failure domains
    if provider_override:
        vs = [m for m in verified_sorted if m["provider"] == provider_override]
        if vs:
            # Filter out the failed model and cooldowned ones
            for m in vs:
                if m["model_id"] != failed_model_id:
                    cooldown = m.get("cooldown_until")
                    if not cooldown or now_ts() >= cooldown:
                        return m
            # If all verified models of this provider are cooldowned or failed,
            # fall through to candidates of same provider
            cs = [m for m in get_enabled_models(config, verified_only=False)
                  if m["provider"] == provider_override]
            cs_sorted = sorted(cs, key=lambda m: m.get("priority", 999))
            for m in cs_sorted:
                if m["model_id"] != failed_model_id:
                    cooldown = m.get("cooldown_until")
                    if not cooldown or now_ts() >= cooldown:
                        return m
            # If no verified or candidates available for this provider,
            # fall through to the other provider's verified models
            other_provider = "nvidia" if provider_override == "opencode" else "opencode"
            others = [m for m in verified_sorted if m["provider"] == other_provider]
            if others:
                for m in others:
                    if m["model_id"] != failed_model_id:
                        cooldown = m.get("cooldown_until")
                        if not cooldown or now_ts() >= cooldown:
                            return m
            return None

    # No provider override - try verified models first, respecting provider domains
    # Track which providers we've already tried to avoid cycling
    tried_providers = set()

    # Try verified models first
    for m in verified_sorted:
        if m["model_id"] == failed_model_id:
            continue
        cooldown = m.get("cooldown_until")
        if cooldown and now_ts() < cooldown:
            # Model is in cooldown, skip but track provider
            provider = m["provider"]
            if provider not in tried_providers:
                tried_providers.add(provider)
            continue
        # Check if we should avoid this provider due to wide cooldown
        if m["provider"] in tried_providers and len(tried_providers) >= 2:
            # Already tried two providers, skip
            continue
        return m

    # Mark first provider as tried
    # Fall through to candidates
    all_enabled = get_enabled_models(config, verified_only=False)
    all_sorted = sorted(all_enabled, key=lambda m: (m.get("priority", 999), m.get("consecutive_failures", 0)))
    
    # Separate by provider for domain-aware selection
    provider_order = ["opencode", "nvidia"]  # OpenCode first (local), then NVIDIA
    
    for provider in provider_order:
        provider_models = [m for m in all_sorted if m["provider"] == provider]
        for m in provider_models:
            if m["model_id"] == failed_model_id:
                continue
            cooldown = m.get("cooldown_until")
            if cooldown and now_ts() < cooldown:
                continue
            return m
    
    # If no model from preferred providers is available, try any remaining
    for m in all_sorted:
        if m["model_id"] == failed_model_id:
            continue
        cooldown = m.get("cooldown_until")
        if cooldown and now_ts() < cooldown:
            continue
        return m

    return None


def supervisor_loop(initial_message, initial_model_id=None, continue_session=False,
                    session_id=None, format_json=False, max_hours=None):
    """
    Main supervisor loop that manages model failover and session continuity.
    
    Parameters:
        initial_message: The task/message to send to OpenCode
        initial_model_id: Starting model ID (None = auto-select)
        continue_session: Whether to continue last session
        session_id: Session ID to use/continue
        format_json: Whether to use JSON output format
        max_hours: Maximum wall time in hours (None = no limit)
    """

    config = load_config()
    failed_models = set()  # Models that just failed with infrastructure errors
    provider_failure_tracking = {}  # Track provider-wide failures

    # Load checkpoint if continuing
    checkpoint_state = load_checkpoint() if session_id or continue_session else {}
    if session_id is None:
        checkpoint_state = {}

    # Initialize checkpoint state
    if "task_id" not in checkpoint_state:
        checkpoint_state["task_id"] = int(time.time())
    if "task_text" not in checkpoint_state:
        checkpoint_state["task_text"] = str(initial_message)[:500] if initial_message else ""
    if "session_id" not in checkpoint_state:
        checkpoint_state["session_id"] = session_id or f"kaizen_ns_{int(time.time())}"
    if "start_time" not in checkpoint_state:
        checkpoint_state["start_time"] = now_ts()
    if "attempted_models" not in checkpoint_state:
        checkpoint_state["attempted_models"] = []
    if "provider_cooldowns" not in checkpoint_state:
        checkpoint_state["provider_cooldowns"] = {}
    if "completed_milestones" not in checkpoint_state:
        checkpoint_state["completed_milestones"] = []
    if "latest_test_command" not in checkpoint_state:
        checkpoint_state["latest_test_command"] = None
    if "latest_test_result" not in checkpoint_state:
        checkpoint_state["latest_test_result"] = None
    if "git_diff_summary" not in checkpoint_state:
        checkpoint_state["git_diff_summary"] = None
    if "failure_history" not in checkpoint_state:
        checkpoint_state["failure_history"] = []
    if "last_heartbeat" not in checkpoint_state:
        checkpoint_state["last_heartbeat"] = now_ts()
    if "final_status" not in checkpoint_state:
        checkpoint_state["final_status"] = "running"

    # Track start time for max_hours enforcement
    start_time = checkpoint_state.get("start_time", now_ts())
    max_wall_time = (max_hours or 24) * 3600  # Default 24 hours max

    current_model_id = initial_model_id or select_model(config)["model_id"]
    current_session_id = checkpoint_state.get("session_id", session_id or f"kaizen_ns_{int(time.time())}")

    LOGGER.info(f"Starting Night Shift supervisor")
    LOGGER.info(f"Initial model: {current_model_id}")
    LOGGER.info(f"Session ID: {current_session_id}")
    LOGGER.info(f"Message: {str(initial_message)[:100]}")
    LOGGER.info(f"Max wall time: {max_hours} hours")

    # Try initial model first
    attempt = 0
    max_attempts = len(config["model_pool"]["verified"]) + len(config["model_pool"]["candidates"]) + 1

    while attempt < max_attempts:
        # Check max wall time enforcement
        elapsed = now_ts() - start_time
        if elapsed > max_wall_time:
            LOGGER.warning(f"Max wall time ({max_hours} hours) exceeded after {elapsed/3600:.1f} hours")
            checkpoint_state["final_status"] = "max_wall_time_exceeded"
            checkpoint_state["last_heartbeat"] = now_ts()
            save_checkpoint(checkpoint_state)
            save_config(config)
            break

        attempt += 1
        LOGGER.info(f"\n--- Attempt {attempt}/{max_attempts} ---")

        # Select model if we don't have one or need to switch
        if current_model_id is None:
            current_model_id = select_model(config)["model_id"]
            if current_model_id is None:
                LOGGER.error("No available models remaining!")
                checkpoint_state["final_status"] = "no_models_available"
                checkpoint_state["last_heartbeat"] = now_ts()
                save_checkpoint(checkpoint_state)
                save_config(config)
                break

        # Check if current model is on cooldown
        pool = config["model_pool"]
        model_info = None
        for category in ["verified", "candidates"]:
            for m in pool[category]:
                if m["model_id"] == current_model_id:
                    model_info = m
                    break
            if model_info:
                break

        if model_info and model_info.get("cooldown_until"):
            if now_ts() < model_info["cooldown_until"]:
                LOGGER.info(f"Model {current_model_id} is in cooldown until {model_info['cooldown_until']}")
                # Try next model
                current_model_id = select_model(config, failed_model_id=current_model_id)["model_id"]
                if current_model_id is None:
                    LOGGER.error("No available models after cooldown check!")
                    checkpoint_state["final_status"] = "no_models_after_cooldown"
                    checkpoint_state["last_heartbeat"] = now_ts()
                    save_checkpoint(checkpoint_state)
                    save_config(config)
                    break
                # Record cooldown in failure history
                checkpoint_state["failure_history"].append({
                    "model": current_model_id,
                    "action": "cooldown_skipped",
                    "attempt": attempt
                })
                save_checkpoint(checkpoint_state)
                continue
            else:
                # Cooldown expired, reset
                model_info["cooldown_until"] = None
                save_config(config)

        # Run OpenCode with current model
        LOGGER.info(f"Running OpenCode with model {current_model_id} (session: {current_session_id})")
        result = run_opencode(current_model_id, initial_message,
                              session_id=current_session_id if continue_session else None,
                              continue_session=continue_session,
                              format_json=format_json)

        # Save checkpoint after each attempt
        checkpoint_state["current_model"] = current_model_id
        checkpoint_state["last_heartbeat"] = now_ts()
        save_checkpoint(checkpoint_state)
        save_config(config)

        if result is None:
            # Process execution failed
            LOGGER.error("OpenCode process failed to start")
            update_model_status(config, current_model_id, {
                "consecutive_failures": model_info.get("consecutive_failures", 0) + 1,
                "last_result": "process_failure"
            })
            # Try next model
            current_model_id = select_model(config, failed_model_id=current_model_id)["model_id"]
            if current_model_id is None:
                LOGGER.error("No available models after process failure!")
                checkpoint_state["final_status"] = "no_models_after_failure"
                checkpoint_state["last_heartbeat"] = now_ts()
                save_checkpoint(checkpoint_state)
                save_config(config)
                break
            attempt += 1
            continue

        # Check the result
        parsed = parse_opencode_result(result)
        exit_code = result.returncode

        # Check for infrastructure errors
        error_str = str(result.stderr or result.stdout or "")
        infra_error = is_infrastructure_error(error_str)
        non_failover = is_non_failover_error(error_str)

        if infra_error:
            # Infrastructure error - trigger failover
            LOGGER.warning(f"Infrastructure error detected with model {current_model_id}: {error_str[:200]}")

            # Update model failure state
            update_model_status(config, current_model_id, {
                "consecutive_failures": model_info.get("consecutive_failures", 0) + 1,
                "last_result": f"infra_error:{error_str[:100]}"
            })

            # Check provider-wide failure
            provider = model_info["provider"]
            set_provider_failure(config, provider, error_str)

            # Redact and log failover event
            redacted_error = redact_secrets(error_str)
            log_failover("infrastructure_failover", {
                "from_model": current_model_id,
                "to_model": current_model_id if current_model_id else "none",
                "error_category": "infrastructure",
                "error_sample": redacted_error[:200],
                "provider": provider
            })

            # Save checkpoint with failure state
            checkpoint_state["failure_history"].append({
                "model": current_model_id,
                "action": "infra_error_failover",
                "error_category": "infrastructure",
                "attempt": attempt
            })
            save_checkpoint(checkpoint_state)

            # Move to next model
            current_model_id = select_model(config, failed_model_id=current_model_id)["model_id"]
            if current_model_id is None:
                LOGGER.error("No available models after infrastructure error!")
                checkpoint_state["final_status"] = "no_models_after_infra_error"
                checkpoint_state["last_heartbeat"] = now_ts()
                save_checkpoint(checkpoint_state)
                save_config(config)
                break
            # Keep the same session ID for continuity
            continue

        elif non_failover:
            # Non-failover error - code bug, test failure, etc.
            LOGGER.error(f"Non-failover error with model {current_model_id}: {error_str[:200]}")
            LOGGER.error("NOT triggering failover - this is an agent code issue, not an infrastructure issue.")
            LOGGER.error("Stopping supervisor - please fix the underlying code issue.")

            # Save checkpoint before stopping
            checkpoint_state["final_status"] = "non_failover_error_stopped"
            checkpoint_state["last_heartbeat"] = now_ts()
            save_checkpoint(checkpoint_state)
            save_config(config)

            # Do NOT switch models - the current model is correct, just has a code bug
            break

        else:
            # No recognized error - successful or unknown result
            LOGGER.info(f"OpenCode completed with model {current_model_id}")
            LOGGER.info(f"Status: {parsed.get('status', 'unknown')}")

            # If successful, reset failures for this model
            if parsed.get("status") == "success" or exit_code == 0:
                reset_model_failures(config, current_model_id)
                # Success - we're done
                if not continue_session or attempt >= max_attempts:
                    checkpoint_state["final_status"] = "success"
                    checkpoint_state["last_heartbeat"] = now_ts()
                    save_checkpoint(checkpoint_state)
                    save_config(config)
                    LOGGER.info("Task completed successfully!")
                    break
                # Otherwise continue to next iteration
            else:
                # Unknown result - try once more or move on
                LOGGER.warning(f"Unknown result from model {current_model_id}")
                # Try next model as a cautious approach
                current_model_id = select_model(config, failed_model_id=current_model_id)["model_id"]
                if current_model_id is None:
                    LOGGER.error("No available models after unknown result!")
                    checkpoint_state["final_status"] = "no_models_after_unknown"
                    checkpoint_state["last_heartbeat"] = now_ts()
                    save_checkpoint(checkpoint_state)
                    save_config(config)
                    break
                attempt += 1
                continue

    # Save final config state and checkpoint
    checkpoint_state["final_status"] = checkpoint_state.get("final_status", "completed")
    checkpoint_state["last_heartbeat"] = now_ts()
    save_checkpoint(checkpoint_state)
    save_config(config)

    # Print summary
    LOGGER.info("\n=== Night Shift Supervisor Summary ===")
    LOGGER.info(f"Total attempts: {attempt}")
    LOGGER.info(f"Final model: {current_model_id}")
    LOGGER.info(f"Session ID: {current_session_id}")
    LOGGER.info(f"Final status: {checkpoint_state['final_status']}")

    return current_model_id, current_session_id


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Kaizen AI Night Shift Supervisor"
    )
    parser.add_argument("message", nargs="...", help="Message to send to OpenCode")
    parser.add_argument("--model", "-m", default=None,
                        help="Initial model ID (provider/model#variant)")
    parser.add_argument("--session", "-s", default=None,
                        help="Session ID to continue")
    parser.add_argument("--continue", "-c", action="store_true", dest="continue_run",
                        help="Continue last session")
    parser.add_argument("--format", "-f", action="store_true",
                        help="JSON output format")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose logging")
    parser.add_argument("--max-hours", "-t", type=int, default=None,
                        help="Maximum wall time in hours (default: no limit, default stop on task completion)")
    parser.add_argument("--simulate-uat", action="store_true",
                        help="Run simulated failover UAT mode")
    parser.add_argument("--smoke-test", action="store_true",
                        help="Run model smoke test before starting")

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    else:
        logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    # Build message from args
    message = " ".join(args.message) if args.message else ""

    # Run simulator UAT mode
    if args.simulate_uat:
        config = load_config()
        # Use first verified model as Model A, then candidate as Model B
        verified = get_enabled_models(config, verified_only=True)
        if verified:
            model_a = verified[0]["model_id"]
            # Find a candidate model (preferably different provider if possible)
            candidates = [m for m in get_enabled_models(config, verified_only=False)
                         if m["model_id"] != model_a]
            model_b = candidates[0]["model_id"] if candidates else model_a
            
            result = simulated_failover_uat(config, model_a, message, model_b)
            LOGGER.info(f"Simulated UAT result: {json.dumps(result, indent=2, ensure_ascii=False)}")
            return
        else:
            LOGGER.error("No models available for simulated UAT")
            return

    # Run smoke test mode
    if args.smoke_test:
        config = load_config()
        enabled = get_enabled_models(config)
        if enabled:
            model = enabled[0]["model_id"]
            result = smoke_test_model(model, message)
            LOGGER.info(f"Smoke test result for {model}: {json.dumps(result, indent=2, ensure_ascii=False)}")
            if not result["pass"]:
                LOGGER.warning(f"Smoke test failed for {model}. Consider marking as candidate or disabling.")
        else:
            LOGGER.error("No enabled models for smoke test")
        return

    # Run supervisor loop
    supervisor_loop(
        initial_message=message,
        initial_model_id=args.model,
        continue_session=args.continue_run if args.continue_run else False,
        session_id=args.session,
        format_json=args.format,
        max_hours=args.max_hours
    )


if __name__ == "__main__":
    main()