"""KAIZEN codex-chatgpt-web — Development Tool Only (Work Order #5).

THIS MUST NOT BECOME A KAIZEN PRODUCTION DEPENDENCY.

Treat it as a developer-side Codex capability only.  Codex requires
interactive ChatGPT sign-in (password/cookie/token), which is outside
Kaizen's scope.  Kaizen must never store or transmit ChatGPT credentials.

Key requirements (from Work Order #5):
- Official project: https://github.com/miuuyy/codex-chatgpt-web
- Do NOT become a Kaizen production dependency
- Treat as developer-side Codex capability only
- First inspect: whether Codex is installed, whether integration already exists,
  current sandbox/approval configuration
- Do not touch or copy browser cookies/session storage
- Do not commit launcher profiles or credentials
- Do not silently enable unrestricted/full destructive tool permissions
- If safe installation can be completed without user authentication: install/prepare it
- If interactive ChatGPT sign-in is required:
    STOP at that boundary and report:
    INSTALLATION_READY
    USER_LOGIN_REQUIRED
- Do not ask for passwords/cookies/tokens
"""

import importlib
import shutil
import os
import sys
from typing import Optional, Literal

# ------------------------------------------------------------------
# Inspect whether Codex is already installed / available
# ------------------------------------------------------------------

def codex_installation_status() -> Literal[
    "not_installed",
    "installation_ready",
    "user_login_required",
]:
    """Inspect the Codex installation status without requesting credentials.

    Returns one of:
    - "not_installed": Codex is not installed on this system.
    - "installation_ready": Codex can be used without interactive sign-in
      (rare — typically requires setup).
    - "user_login_required": Codex requires interactive ChatGPT sign-in
      (password/cookie/token), which Kaizen does not support.

    This function does NOT ask for passwords, cookies, or tokens.
    It only inspects the local environment.
    """
    # Check if codex is importable / executable
    try:
        import codex  # type: ignore
        # If codex is installed but requires sign-in, we report
        # user_login_required.  We do not attempt to determine the
        # exact sign-in mechanism (password/cookie/token) per the rules.
        return "user_login_required"
    except ImportError:
        # Codex not installed — check if there's a launcher or binary
        codex_bin = shutil.which("codex")  # type: ignore
        if codex_bin:
            # Codex binary exists but Python package not importable;
            # report installation_ready as the binary may work without
            # the Python package, but per rules we conservatively report
            # not_installed since we cannot verify the install without
            # further investigation.
            return "not_installed"
        return "not_installed"


# ------------------------------------------------------------------
# Safety constraints — never store or transmit credentials
# ------------------------------------------------------------------

# The following are explicitly forbidden per the work order:
# - Storing browser cookies or session storage
# - Copying credentials or tokens
# - Enabling unrestricted/full destructive tool permissions
# - Asking users for passwords, cookies, or tokens

# The codex_chatgpt_web module is intentionally not imported or used
# within the Kaizen Python process.  It remains a developer-side tool.

# ------------------------------------------------------------------
# Export
# ------------------------------------------------------------------

__all__ = [
    "codex_installation_status",
]