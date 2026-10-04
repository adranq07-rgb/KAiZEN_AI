"""Measure actual provider invocations without retaining prompts or credentials."""
import time


class ObservedProvider:
    def __init__(self, provider):
        self.provider = provider
        self.calls = 0
        self.elapsed_ms = 0.0

    def __getattr__(self, name):
        return getattr(self.provider, name)

    def ask(self, message):
        if getattr(self.provider, "is_offline", False):
            return self.provider.ask(message)
        started = time.perf_counter()
        self.calls += 1
        try:
            return self.provider.ask(message)
        finally:
            self.elapsed_ms += (time.perf_counter() - started) * 1000
