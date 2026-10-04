"""Kaizen Search Foundation (Faz A/B).

Bu paket, Kaizen'in web arama katmanını (source discovery) KaizenBrain'in ana cevap
zincirinden BAĞIMSIZ, ayrı ve test edilebilir tutar. `provider.py`'deki `SearchProvider`
sözleşmesi dışında hiçbir çağıran kod, somut bir sağlayıcıya (ör. `SearXNGProvider`) veya
`searxng.search()` gibi bir çağrıya doğrudan bağlanmamalıdır.

Bu faz sonunda (iş emri "KAIZEN — İŞ EMRİ: SearXNG Search Foundation") bu paket henüz
KaizenBrain'e bağlanmamıştır -- yalnızca bağımsız olarak test edilmiştir.
"""
