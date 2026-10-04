"""Remove credentials before optional memory/log persistence."""
import re

_ASSIGNMENT = re.compile(r"(?i)\b(api[_ -]?key|access[_ -]?token|password|parola|şifre|secret)\s*[:=]\s*(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)")
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_KEY = re.compile(r"\b(?:sk-|ghp_|github_pat_)[A-Za-z0-9_-]{10,}")


def redact(text):
    value = _ASSIGNMENT.sub(lambda m: m.group(1) + "=[REDACTED]", str(text))
    return _KEY.sub("[REDACTED]", _BEARER.sub("Bearer [REDACTED]", value))
