> INACTIVE LEGACY — 2026-09-30: Cognee is removed from Kaizen-1.
> The following documents historical integration, not current setup instructions.

# Cognee Hafıza Entegrasyonu

Modül: `memory/cognee_memory.py` · Test: `tests/test_cognee_memory.py` · Ayar: `config/Kaizen.json -> memory.cognee`

## Doğrulanan API (tahmin değil)

Kaynak: PyPI `cognee 1.6.0` wheel'inin kaynak kodu (GitHub `topoteretes/cognee`) ve
`docs.cognee.ai/guides/local-setup`, `docs.cognee.ai/guides/local-ollama` (2026-09-22).

| Kullanım | Gerçek imza |
|---|---|
| Yazma | `await cognee.remember(data, dataset_name="main_dataset", *, self_improvement=True, raise_on_error=True, ...) -> RememberResult` (`.status`, `.dataset_name`, `.error`) |
| Okuma | `await cognee.recall(query_text, query_type=None, *, datasets=None, top_k=15, ...) -> list[RecallResponse]` (`source` alanıyla ayrışan birleşim; `graph` öğelerinde `.text`) |
| Silme | `await cognee.forget(*, data_id=None, dataset=None, dataset_id=None, everything=False, memory_only=False) -> dict` |
| Ayar | `cognee.config.set_llm_config(dict)`, `set_embedding_config(dict)`, `set_vector_db_provider`, `data_root_directory`, `system_root_directory` |

Koddan çıkan ve modülde karşılanan tuzaklar:

- `import cognee`, çalışma dizinindeki `.env`'i `override=True` ile yükler → ayarlar içe aktarmadan sonra `set_*_config` ile yeniden uygulanır.
- Telemetri varsayılan olarak açık (`send_telemetry`) → `TELEMETRY_DISABLED=1`.
- Ollama sağlayıcısında `LLM_MODEL`, `LLM_ENDPOINT`, `LLM_API_KEY` üçü birlikte verilmeli; anahtar boşsa `LLMAPIKeyNotSetError` → `LLM_API_KEY="ollama"` (Ollama doğrulamaz).
- `LLM_ENDPOINT` çıplak adres olmalı (`http://localhost:11434`); `/v1` eklenirse litellm `/v1/api/generate`'e gider ve 404 verir. Bu yüzden `model.local.base_url` (…/v1) yeniden kullanılmadı.
- Varsayılan depolar dizini site-packages içindedir → `data/cognee/` altına alındı (git dışı).
- Docs "fastembed ayrı extra" diyor, fakat 1.6.0'da `fastembed` temel bağımlılık. Kod esas alındı.

## Karar: LLM sağlayıcısı **Ollama** (Hermes değil)

1. **Hermes bir LLM uç noktası değil.** `core/hermes_bridge.py` Hermes'i `hermes chat -q ... --oneshot` alt süreci olarak çağırıyor; Hermes ajan döngüsü, araçlar ve kendi sistem istemiyle çalışıyor. Cognee ise `LLMConfig` üzerinden litellm/instructor ile doğrudan, yapılandırılmış çıktılı (JSON şema) çok sayıda çağrı yapar. Desteklenen sağlayıcılar: `openai, ollama, anthropic, custom, gemini, mistral, azure, bedrock, llama_cpp …`. Hermes CLI'ı bu arayüze takmanın yolu yok.
2. **"Hermes'i kullanmak" aslında bulutu kullanmak demek.** Hermes'in modeli `upstage/solar-pro4:free` @ `inference-api.nousresearch.com` (Nous bulut). Cognee'yi oraya bağlamak için Hermes'in `auth.json` oturum belirtecini okuyup Hermes'i atlamak gerekirdi. Bu hem kırılgan hem de ARCHITECTURE §7'deki "Kaizen Memory / Hermes Memory ayrımı"na aykırı.
3. **Gizlilik ve Local-First.** `remember()` metnin tamamını varlık/ilişki çıkarımı için LLM'e gönderir. Kaizen hafızası müşteri ve muhasebe verisi taşıyacak. ARCHITECTURE §4 "bulut model kullanımı varsayılan olarak kapalı" diyor, `Kaizen.json` de "Hermes geçici" notunu taşıyor. Modül bu yüzden localhost dışındaki uç noktaları `cloud_allowed` ayarından bağımsız olarak reddeder.
4. **Embedding de gerekiyor.** Cognee'nin vektör tarafı için embedding sağlayıcısı şart. Hermes bunu sağlamıyor; Ollama hem LLM'i hem embedding'i aynı yerel sunucudan veriyor (docs'un önerdiği tam yerel kurulum da bu).
5. **Hermes'in rolü değişmiyor:** web araştırması, terminal ve dosya işlerini yapan araç motoru olarak kalıyor.

## Model seçimi (bu bilgisayar: GTX 1650 4 GB VRAM, 8 GB RAM)

- **LLM `llama3.2:3b`**: yaklaşık 2 GB ve 4 GB VRAM'e sığar. Cognee'nin `ollama_support.py` listesinde "recommended". `llama3.1:8b` (docs örneği) yaklaşık 4.9 GB, bu kartta CPU'ya taşar ve çok yavaş çalışır. Yeni bilgisayarda `llama3.1:8b` ya da `qwen2.5:14b` (≥14b "recommended"; daha küçük qwen2.5 "problematic") seçilmeli.
- **Embedding `bge-m3`** (1024 boyut, 100+ dil, 1.2 GB): Türkçe metin için İngilizce ağırlıklı `nomic-embed-text` yerine seçildi. Embedding modelini değiştirmek mevcut vektörleri geçersiz kılar; değiştirilirse `forget(dataset, confirmed=True)` ile yeniden oluşturulmalı.
- `recall_type="CHUNKS"`: Cevabı LLM yazmaz, kaynak parçaları döner. Kaizen'in "uydurma" kuralına uyar, küçük modelde halüsinasyonu önler. `GRAPH_COMPLETION` ayardan açılabilir.
- `self_improvement=false`: `remember` sonrası ek `improve()` LLM çağrılarını bu donanımda kapatır.

## Etkinleştirme (kullanıcı onayı gerekir: program yükleme)

```powershell
winget install Ollama.Ollama
ollama pull llama3.2:3b
ollama pull bge-m3
.venv\Scripts\python.exe -m pip install cognee==1.6.0
# config/Kaizen.json -> memory.cognee.enabled = true
.venv\Scripts\python.exe -c "from memory.cognee_memory import CogneeMemory; print(CogneeMemory().health())"
```

İlk çalıştırmada `HUGGINGFACE_TOKENIZER` (BAAI/bge-m3) tokenizer'ı bir kez Hugging Face'ten indirilir. Bu adımda veri gönderilmez.
