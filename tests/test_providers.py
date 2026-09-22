import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from core.ai.fallback_provider import FallbackProvider, is_failure
from core.ai.local_provider import LocalProvider
from core.ai.offline_provider import OFFLINE_MESSAGE, OfflineProvider
from core.ai.provider_factory import build_provider


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        reply = {"choices": [{"message": {"content": f"YEREL:{body['messages'][-1]['content']}"}}]}
        data = json.dumps(reply).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


class _Down:
    def ask(self, message):
        return "Kaizen: Hermes su anda calistirilamiyor."

    def research_packet(self, message, trusted_only=True):
        return {"verified": False}


class _Crash:
    def ask(self, message):
        raise RuntimeError("çöktü")


class _Config:
    def __init__(self, values):
        self.values = values

    def get(self, section, key, default=None):
        return self.values.get(section, {}).get(key, default)

    def cloud_allowed(self):
        return False


def test_providers():
    # çevrimdışı sağlayıcı bir hata sayılır; zincir sonuna kadar gider
    assert is_failure(OfflineProvider().ask("x")) and OFFLINE_MESSAGE.startswith("Kaizen:")
    chain = FallbackProvider([_Down(), _Crash(), OfflineProvider()])
    assert chain.ask("soru") == OFFLINE_MESSAGE
    # ek yetenekler (research_packet) ilk sahibinden alınır
    assert chain.research_packet("x") == {"verified": False}
    try:
        chain.collect_sources
        raise AssertionError("olmayan yetenek AttributeError vermeli")
    except AttributeError:
        pass

    # model adı yoksa yerel sağlayıcı zinciri durdurmaz
    assert is_failure(LocalProvider(model_name="").ask("x"))
    assert FallbackProvider([LocalProvider(model_name=""), _Down()]).ask("x").startswith("Kaizen:")

    # gerçek bir OpenAI uyumlu yerel sunucu ile
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/v1"
        local = LocalProvider(base_url=url, model_name="deneme", timeout=5)
        assert local.ask("Merhaba") == "YEREL:Merhaba"
        assert FallbackProvider([_Down(), local, OfflineProvider()]).ask("Selam") == "YEREL:Selam"
        # uzak adres + bulut kapalı = engellenir
        assert is_failure(LocalProvider(base_url="http://example.com/v1", model_name="m", cloud_allowed=False).ask("x"))
    finally:
        server.shutdown()

    # yapılandırmadan zincir kurma
    only_offline = build_provider(_Config({"model": {"provider": "offline"}}))
    assert only_offline.ask("x") == OFFLINE_MESSAGE
    chained = build_provider(_Config({"model": {"provider": "local", "fallback": ["offline"], "local": {"model_name": ""}}}))
    assert isinstance(chained, FallbackProvider) and chained.ask("x") == OFFLINE_MESSAGE
    try:
        build_provider(_Config({"model": {"provider": "yok"}}))
        raise AssertionError("bilinmeyen sağlayıcı reddedilmeli")
    except ValueError:
        pass

    print("KAIZEN BAGIMSIZ SAGLAYICI TESTI: BASARILI")


if __name__ == "__main__":
    test_providers()
