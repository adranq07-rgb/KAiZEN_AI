# Kaizen Search Foundation (Faz A/B, 2026-09-23'ten itibaren)

Bu klasor, iş emri "KAIZEN — LEARNING BRAIN v1 + SEARXNG SEARCH FOUNDATION"
kapsaminda eklenen, Kaizen'in mevcut cevap zincirinden BAGIMSIZ, ayri bir
degerlendirme/altyapi calismasidir. Henuz `KaizenBrain`'e baglanmamistir.

## Dosyalar

- `setup_searxng.ps1` — SearXNG'yi kullanicinin kendi Windows bilgisayarinda,
  yalniz `127.0.0.1` (localhost) uzerinde, JSON arama API'si acik sekilde
  kuran PowerShell betigi. Docker gerektirir. Public internete ACILMAZ.
  Docker CLI/daemon eksikse veya container gercekten `running` durumuna
  gecmezse, betik bunu acikca bir BAGIMLILIK HATASI olarak raporlayip
  guvenli sekilde durur (SearXNG'nin kendisiyle ilgili bir hata gibi
  GOSTERMEZ).
- `DOCKER_KURULUM.md` — Windows 10 Pro icin Docker Desktop + WSL2 minimum
  kurulum adimlari (hangi adimlarin yeniden baslatma gerektirdigi acikca
  belirtilir). Docker kurulu degilse once bu dosyayi izleyin, sonra
  `setup_searxng.ps1`'i (tekrar) calistirin.
- `searxng-data/` (betik calistirilinca olusur) — SearXNG'nin kendi
  `settings.yml` ve onbellek dosyalari. Kaizen'in gercek `data/`/`logs/`/
  `memory/` klasorleriyle HICBIR ILISKISI yoktur.
- `benchmark/` (Faz A3-A11 sirasinda eklenecek) — arama kalite olcumu
  sonuclari (sorgu, sonuc, resmi kaynak bulundu mu, tazelik, vb.).

## Calistirma sirasi

1. Bu klasorde PowerShell acin.
2. `powershell -ExecutionPolicy Bypass -File .\setup_searxng.ps1`
3. Betik kendi kendini dogrular (health check + JSON arama testi). Sonunda
   "JSON API: OK" gormelisiniz.
4. SearXNG ayaktayken, Claude (Cowork oturumu) bilgisayarinizdaki tarayici
   penceresi uzerinden `http://127.0.0.1:8890/search?q=...&format=json`
   adresine dogrudan istek atarak gercek, olcumlu bir benchmark calistirir
   (bkz. KAIZEN_HEDEF_VE_YOL_HARITASI.md, ilgili bolum).

## Neden boyle (mimari not)

Kaizen'in calistigi bulut ortaminin disariya (Google/Bing/resmi .gov.tr
siteleri dahil) genel internet erisimi YOK -- yalniz paket depolari ve
Anthropic API'leri icin acik. Bu yuzden SearXNG'yi bulutta calistirip test
etmek anlamsiz olurdu (disariya hic arama yapamaz). Kaizen'in bilgisayar
uzerindeki tarayici penceresi ISE kullanicinin kendi internet baglantisini
kullanir -- bu yuzden gercek, olcumlu bir benchmark ancak bu sekilde,
SearXNG bilgisayarda calisirken, mumkun oluyor.
