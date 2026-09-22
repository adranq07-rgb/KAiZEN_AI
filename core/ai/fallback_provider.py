from core.ai.base_provider import BaseAIProvider

FAILURE_MARKERS = (
    "Hermes su anda calistirilamiyor", "Hermes hatasi", "Hermes bilgisayarda bulunamadi",
    "zaman asimina", "Yerel model", "çevrimdışı mod", "Henuz bir AI provider",
)


def is_failure(text):
    """Sağlayıcının 'cevap üretemedim' türü hata metni mi?"""
    return isinstance(text, str) and text.startswith("Kaizen:") and any(m in text for m in FAILURE_MARKERS)


class FallbackProvider(BaseAIProvider):
    """Sağlayıcıları sırayla dener: ilk çalışan cevabı verir (ör. Hermes -> yerel model -> çevrimdışı)."""

    def __init__(self, providers):
        if not providers:
            raise ValueError("En az bir sağlayıcı gerekli")
        self.providers = list(providers)

    @property
    def is_offline(self):
        return all(getattr(p, "is_offline", False) for p in self.providers)

    def ask(self, message):
        last = None
        for provider in self.providers:
            try:
                answer = provider.ask(message)
            except Exception as exc:  # bir sağlayıcının çökmesi zinciri durdurmasın
                answer = f"Kaizen: Sağlayıcı hatası (Hermes/Yerel model) -> {type(exc).__name__}: {exc}"
            if not is_failure(answer):
                return answer
            last = answer
        return last

    def __getattr__(self, name):
        # research / research_packet / collect_sources gibi ek yetenekleri ilk sahip sağlayıcıdan al
        if name.startswith("_") or name in ("providers",):
            raise AttributeError(name)
        for provider in self.providers:
            method = getattr(provider, name, None)
            if callable(method):
                return method
        raise AttributeError(name)
