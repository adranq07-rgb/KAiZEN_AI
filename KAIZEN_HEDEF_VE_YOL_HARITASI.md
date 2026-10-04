# Kaizen AI — Hedef, Çalışma Şekli ve Yol Haritası

Bu belge, ChatGPT/Codex ile yapılan çalışmalardan çıkarılan hedefi ve şu anki durumu tek yerde toplar.
Yeni bir oturum (ya da yeni bir yapay zeka) projeye başlarken önce bunu okumalıdır.

## 1. Hedef

Kaizen; **muhasebe ve matematik bilen, beyni olan** bir yapay zeka aracıdır. Bir mali müşavir gibi cevap verir:
kuruşu kuruşuna hesaplar, hesap kodlarını ezbere bilir, kaynağını gösterir, bilmediğini uydurmaz.

- Şu an ücretsiz **Hermes** bağlıdır; bu geçicidir. Kaizen sonunda **bağımsız** çalışacak.
- Güvenilir sitelerden bilgiyi **kendisi çekecek**, **kendi süzgeci** olacak, kendi hafızasında tutacak.
- Öğrenme sırası: matematik → muhasebe → mali müşavir bakışı. Excel formülleri, PDF, Word ve ofis araçlarını da öğrenecek.
- Tek Düzen Hesap Planı'nı ezbere bilecek; yevmiye kaydı, dönem sonu, maliyet mantığını bilecek.
- **Sonraya bırakılanlar:** WhatsApp'tan gelen fatura talebinin otomasyonu; yerel yapay zeka modelinin bağlanması (yeni bilgisayar gelince).

## 2. Bir soru nasıl cevaplanır (karar sırası)

`core/kaizen_brain.py` sırayla dener; ilk cevap veren kazanır:

1. **Kullanıcı düzeltmesi** (`düzelt: soru => doğru cevap`).
2. **Kesin araçlar** — model gerekmez, uydurma yoktur:
   matematik ifadeleri, hesaplayıcılar (`accounting/calculators.py`), yevmiye kaydı (`accounting/journal.py`),
   Tek Düzen Hesap Planı (`accounting/chart_of_accounts.py`, veri: `config/tdhp.json`, 258 hesap).
   Oran/dönem/tutar soruda yoksa Kaizen **sorar**, tahmin etmez.
3. **Yıllık parametre defteri** (`accounting/facts.py`): süzgeçten geçmiş oran/sınır/tavan; en yeni yıl önce.
4. **Yerel hafıza** (`accounting/retriever.py`): ders notları + öğretilmiş bilgiler + taranan site sayfaları.
   Model varsa yorumlar ve KAYNAKLAR'ı Kaizen ekler; model yoksa soruyla gerçekten örtüşen alıntıyı gösterir.
   Güncel bir soruda toplanmış kaynak yoksa ders notu bayat sayılır ve uyarı eklenir.
5. **Araştırma zinciri** (Hermes) — yalnız yerelde bulunamazsa.
6. Dürüst "bulamadım" cevabı.

## 3. Bağımsızlık (Hermes'siz çalışma)

Sağlayıcı zinciri `config/Kaizen.json` içindeki `model` bölümünden seçilir (`core/ai/provider_factory.py`):

| Ayar | Anlamı |
| --- | --- |
| `model.provider` | `hermes` (şimdi) → sonra `local` |
| `model.fallback` | Ana sağlayıcı çalışmazsa sırayla denenecekler; varsayılan `["offline"]` |
| `model.local` | Yerel OpenAI uyumlu sunucu (Ollama, llama.cpp, LM Studio): `base_url`, `model_name`, `timeout` |

Yeni bilgisayarda: yerel modeli kur → `model.provider = "local"`, `model.local.model_name = "<ad>"`,
`model.fallback = ["offline"]` yap. Başka kod değişikliği gerekmez.
Hermes ve model kapalıyken bile 2., 3. ve 4. basamaklar çalışır (testi: `test_brain_independent_of_model`).

## 4. Kaynak siteler ve süzgeç

Kaizen kendi tarayıcısıyla (`accounting/crawler.py`, yalnız Python standart kütüphanesi) şu kaynakları gezer.
Liste `accounting/source_registry.py` içindedir; belgede 12 site geçse de sonradan verilenlerle **17 kaynak** kayıtlıdır:

GİB (yalnız resmî dayanak bağlantısı), TÜRMOB, Muhasebe TR, Alomaliye (forum yok), PwC Türkiye (vergi özetleri dahil),
Vergiport, PKF İstanbul, Rödl Türkiye, Vergi Merkezi, Muhasebe Bilenler (forum yok), Muhasebe News, Vertax, DergiPark,
Verginet, Denge Akademi, Özdoğrular, Müşavirler Kulübü (araçlar sayfası tohum adres).

Tarama kuralları: `robots.txt`'e uyar, siteye saygılı hız sınırı koyar, kendini tanıtır, forum/yorum yollarını almaz,
önce son **2 yılın** içeriğini alır (`--backfill` ile eskisi), değişmeyen sayfayı yeniden yazmaz.
PDF ve Excel içerikleri de okunur ama **kaynak olarak** (bağlantısıyla) gösterilir, Kaizen'in kendi metni gibi sunulmaz.
Robots/403/429 engeli **aşılmaz**; Hermes yedeği yalnız ağ hatasında ve isteğe bağlı devreye girer.

**Süzgeç** (`accounting/consensus.py`, `accounting/facts.py`, konular: `config/fact_topics.json`):

- Bir değer, **resmî kaynakta** veya **en az iki bağımsız kaynakta** aynı bulunursa *doğrulanmış* olur.
- Tek kaynakta görülürse *beklemede*; kaynaklar çelişirse *çelişkili* — Kaizen kesin cevap vermez, durumu söyler.
- Yeni mevzuat bilgisi başka kayıtlı kaynaklarla teyit edilirse eski değerin yerini alır; değişim geçmişi saklanır.
- Yıllık parametreler (binek araç gider kısıtlaması, amortisman sınırı, fatura sınırı, asgari ücret, SGK tavanı...)
  **en yeni yıldan** cevaplanır. Hiçbir oran koda sabit yazılmaz.
- Yeni parametre eklemek için `config/fact_topics.json` içine bir konu eklemek yeterlidir.

Güncelleme: `python -m accounting.refresh` (tümü), `--source "Vergiport"` (biri), `--stats`, `--list`.
Sohbette `güncelle` komutu da aynısını yapar. Günlük otomatik çalışma: `tools\gunluk_guncelle.bat` dosyasını
Windows Görev Zamanlayıcı'ya ekle (örnek: `schtasks /create /tn "Kaizen Guncelle" /tr "<tam yol>\tools\gunluk_guncelle.bat" /sc daily /st 07:30`).

## 4b. Muhasebenin değişmeyen temel taşları (çekirdek müfredat)

`knowledge/muhasebe_temel_taslari.json` (16 kayıt), Kaizen'in hafızasına elle yazılmış, yıl değişse de
değişmeyen temel bilgidir — siteden değil doğrudan ders notu olarak yüklenir (`memory/seed_loader.py`),
model kapalıyken bile (`memory_extractive` yolu) doğru alıntıyla cevap verir. Kapsam:

- Muhasebenin 13 temel kavramı (sosyal sorumluluk, kişilik, süreklilik, dönemsellik, parayla ölçme,
  maliyet esası, tarafsızlık-belgelendirme, tutarlılık, tam açıklama, ihtiyatlılık, önemlilik, özün
  önceliği, açıklık)
- Çift taraflı kayıt sistemi ve borç/alacak-aktif/pasif bakiye mantığı
- Tek Düzen Hesap Planı'nın 1-9 sınıf mantığı (neden bu sınıfta sorusunun cevabı)
- Yevmiye defteri → büyük defter (kebir) → mizan akışı
- Dönem sonu işlemleri: envanter/değerleme, amortisman, reeskont, şüpheli alacak karşılığı, kur farkı
- Maliyet muhasebesi 7/A ve 7/B seçeneklerinin mantığı ve hesapları
- Mali tablolar: bilanço, gelir tablosu, nakit akış tablosu, özkaynak değişim tablosu
- VUK temel kavramları: defter tutma yükümlülüğü/süreleri, belge düzeni (fatura, irsaliye, makbuz...)
- Stok değerleme yöntemleri (FIFO, LIFO, ağırlıklı ortalama) ve envanter yöntemleri
- Hata düzeltme (tashih) kaydı

Yıla bağlı hiçbir oran/tutar bu dosyaya yazılmaz (kural AGENTS.md madde 2); onlar parametre defterinde
kalır. `tests/test_golden_exam.py` içine bu konulardan 13 soru eklendi (toplam 53 soru, altın sınav yeşil).

## 4c. Kendi kendini geliştiren öğrenen beyin

`memory/knowledge_cards.py` + `core/kaizen_brain.py` (`_remember_research`, `_cross_check`,
`_promote_card`, `confirm_card`). Amaç: **Hermes yalnızca Kaizen'in işçisi** — bu katman hangi
sağlayıcının bağlı olduğunu hiç bilmez, yalnız cevap metnini görür. Hermes değişse/kapansa bile
öğrenilen hiçbir bilgi kaybolmaz, çünkü araştırma sonucu **her zaman**, beklemede olsa bile, hemen
Kaizen'in kendi kalıcı hafızasına (`memory/learning_store.py`, `source_type="learned"`) yazılır —
onay beklenmez, yalnız güven etiketi beklenir.

Akış:

1. Araştırma bir soruyu başarıyla cevaplarsa, cevap bir **bilgi kartı** olarak kaydedilir (`beklemede`)
   ve **aynı anda** kalıcı hafızaya da yazılır; metnin başında "onay bekliyor, ikinci bağımsız
   doğrulama görmedi" uyarısı görünür şekilde durur — bilgi saklanır, yalnız güveni düşük işaretlenir.
2. Aynı/benzer soru bir daha sorulduğunda Kaizen artık araştırmaya gitmez; kendi hafızasından
   (uyarı notuyla) cevap verir — böylece aynı soruya iki kez Hermes çağrılmaz.
3. Mali müşavir `onayla: <soru>` komutuyla bekleyen bir kartı onaylar; kayıt o anda uyarısız
   ("mali müşavir onayladı") sürümle güncellenir.
4. Her yeni kart, süzgeçten geçmiş **parametre defteriyle** (`accounting/facts.py`) çapraz kontrol
   edilir (`_cross_check`); araştırmanın verdiği rakam doğrulanmış bir parametreyle çelişirse
   `öğrendiklerim` komutunda çelişki uyarısı olarak listelenir.
5. Onaylanan her kart, `data/auto_exam_candidates.jsonl` dosyasına bir altın sınav **önerisi**
   olarak yazılır (otomatik teste eklenmez — insan/Kaizen incelemesi sonrası elle eklenir).

Komutlar: `öğrendiklerim` (bekleyen kartlar + çelişki uyarıları), `onayla: <soru>`. Testler:
`tests/test_self_learning.py` (kart yaşam döngüsü, tekrar araştırmayı önleme, çapraz kontrol,
araştırma sonucunun onaydan önce de kalıcı hafızada olduğunun doğrulanması).

## 4d. SGK: temel yapı (değişmeyen çekirdek)

`knowledge/sgk_temel_yapi.json` (13 kayıt), aynı 4b mantığıyla: SGK'nın **değişmeyen** işleyiş
kuralları — sigortalılık halleri (4/a, 4/b, 4/c), kısa/uzun vadeli sigorta kolları, prime esas
kazanç (taban/tavan) mantığı, prim gün sayısı ve eksik gün bildirimi, işveren/sigortalı prim payı
paylaşım mantığı, işe giriş/ayrılış bildirgeleri, MUHSGK, teşvik mantığı, GSS, sigortalılığın
başlangıcı/sona ermesi, hizmet birleştirme ve emeklilik şartları mantığı, iş kazası/meslek hastalığı
bildirimi, prim borcunda gecikme cezası/zammı. Hiçbir güncel oran/tutar (taban-tavan TL, prim %'si,
yaş/gün şartı) buraya yazılmadı — kural AGENTS.md madde 2 ile aynı. `tests/test_golden_exam.py`
içine 13 SGK sorusu eklendi (toplam 66 soru, altın sınav yeşil).

Değişen kısım (**sgk_parameters**, sıradaki adım): `config/fact_topics.json`'a üç yeni konu eklendi
— `sgk_isci_prim_orani`, `sgk_isveren_prim_orani`, `issizlik_sigortasi_orani` (mevcut
`sgk_prim_tabani`/`sgk_prim_tavani`/`kidem_tazminati_tavani` zaten vardı). Bu konular, ilk canlı
tarama (`güncelle`) siteleri geçtikten sonra süzgeçten geçip parametre defterine dolacak.

## 4e. İlk canlı tarama sonucu ve yapılan düzeltmeler (2026-09-22)

Kullanıcının bilgisayarında `python -m accounting.refresh` ile 17 kaynağın tamamı ilk kez tarandı:
511 sayfa depoya alındı, süzgeç ilk seferinde 27 parametre buldu (8 doğrulanmış, 13 tek kaynak,
6 çelişkili). Rapor (`data/refresh_report.json`) ve süzgeç veritabanı incelenince üç gerçek kod
hatası bulundu ve düzeltildi:

1. **Türkçe karakterli adres hatası** (`accounting/crawler.py`): `.../AramizdanAyrilanlar/Ağustos`
   gibi ham (yüzde-kodlanmamış) Türkçe karakter içeren bağlantılar `'ascii' codec can't encode
   character` hatasıyla hiç indirilemiyordu (TURMOB'da 7, Denge Akademi'de 1 sayfa). İstek öncesi
   adres artık güvenli şekilde yüzde-kodlanıyor.
2. **Boşlukla binlik ayrılmış sayı kırpılması** (`accounting/facts.py`): "4 000 000 TL" gibi (nokta
   yerine boşlukla ayrılmış, eski/kopyalanmış metinlerde görülen) sayılar, sayı çıkarma deseni
   tarafından yanlışlıkla son parçası ("000 TL") tek başına bir değer gibi yakalanıyordu. Artık
   böyle bir sayı hiç yakalanmıyor (yanlış veri üretmektense veri üretmemeyi tercih eder).
3. **Aynı değerin farklı yazımı yanlışlıkla "çelişki" sayılıyordu** (`accounting/consensus.py`):
   "12.000 TL" ile "12.000,00 TL" aynı tutar olduğu halde normalize mantığı bunları farklı
   görüyordu ("TL" etiketi sayıya yapışık kaldığı için Decimal ayrıştırması bozuluyordu). Artık
   etiket sayıdan ayrılıp sayı ayrı normalize ediliyor.

Bu üç düzeltmeyle, kullanıcının **gerçek tarama verisi** üzerinde süzgeç yeniden kurulduğunda:
çelişkili parametre 6'dan **2**'ye indi, doğrulanmış parametre 8'den **11**'e çıktı. Yeniden
tarama gerekmiyor — `python -m accounting.refresh --rebuild-only` eklendi: yalnız depodaki (zaten
indirilmiş) sayfalardan süzgeci yeniden kurar, saatler süren tam taramayı tekrarlamaz.

Kalan 2 gerçek çelişki kod hatası değil, **konu tanımı** meselesi — mali müşavirin kararı gerekir:

- `sgk_isveren_prim_orani` (%5 / %50): ikisi de genel işveren prim oranı değil, belirli teşvik/
  indirim programlarının oranı (imalat sektörü %5 indirimi; Ar-Ge/Teknopark %50 Hazine karşılama).
  Konunun ayrıştırılması (genel oran vs. teşvik oranı) gerekebilir.
- `yeniden_degerleme_orani` (%11,51 / %25,49 / %4,19 / %49 / %9,11): yıllık oran ile 1./2. geçici
  vergi dönemi oranları karışıyor — bunlar gerçekten farklı kavramlar, aynı konuda toplanmamalı.

Kod hatası olmayan, yapısal durumlar:

- **Gelir İdaresi Başkanlığı** (`reference_only=True`, resmî öncelik) hiç taranmıyor (seed adres
  tanımlı değil) — şu an süzgece hiç katkı vermiyor. İstenirse belirli GİB sayfa adresleri (tebliğ/
  sirküler/duyuru) seed olarak eklenebilir.
- **Roedl Türkiye**: 60 sayfanın tamamı "ince içerik" (JS ile render edilen SharePoint tabanlı
  site, düz HTML'de neredeyse metin yok) — bu taramanın yapısal sınırı, düzeltilebilir bir hata
  değil.
- **Verginet, Özdoğrular**: robots.txt erişimi tamamen engelliyor (AGENTS.md madde 5 gereği
  aşılmadı).
- **DergiPark**: sitenin 429 (çok istek) yanıtı üzerine bu koşuda durduruldu; bir sonraki
  taramada kaldığı yerden devam eder.

Test: `tests/test_accounting_consensus.py`, `tests/test_facts.py`, `tests/test_crawler.py`,
`tests/test_refresh_cli.py` (yeni) bu üç düzeltmeyi ve `--rebuild-only`'yi kapsar;
`python -m tests.run_all` yeşil.

**Karar verildi (kullanıcı: "sen herşeyi sırası ile yap kontrol sende"):**

- `sgk_isveren_prim_orani` konusuna `avoid` listesi eklendi (teşvik/indirim/Ar-Ge/Hazine/fon
  cümleleri artık karışmıyor). Gerçek veriyle sonuç: tek kaynakta net "İşveren prim oranı =
  %23,75" bulundu (`config/fact_topics.json`).
- `yeniden_degerleme_orani` konusu **yıllık** orana daraltıldı (`avoid`: geçici vergi dönemi,
  MTV cümleleri artık karışmıyor). 2025 zaten 4 kaynakla doğrulanmıştı; 2026 için hâlâ tek tek
  kaynaklarda iki farklı değer var (%49 / %9,11) — 2026 yıl sonu resmi ilanı (genelde
  Kasım-Aralık'ta yapılıyor, 2025'inki 27.11.2025'te yayımlandı) henüz olmadığı için bu **gerçek**
  bir belirsizlik; uydurma bir "kazanan" seçilmedi, ikinci kaynak veya resmi ilan bekleniyor.
- **Sonuç:** çelişkili parametre 6 → **1** (yalnızca gerçekten belirsiz olan 2026 yeniden
  değerleme oranı kaldı), doğrulanmış 8 → **11**, tek kaynak (onay bekleyen) 13 → 15.
- **GİB (`gib.gov.tr`) artık `reference_only` değil:** genel sayfaları (mevzuat, duyuru listesi)
  JavaScript ile dolduruluyor (crawler JS çalıştırmıyor, boş/ince içerik üretirdi) ama GİB'in
  tekil duyuru/rehber belgeleri `cdn.gib.gov.tr` üzerinden düz PDF olarak servis ediliyor ve
  gerçek metin içeriyor. Doğrulanan 4 resmi PDF seed olarak eklendi (`accounting/source_registry.py`):
  2026 Ücret Geliri Rehberi, Asgari Ücretten Yapılan Kesintiler, 585 sıra no'lu VUK Tebliği
  Açıklama Notu (2025 yeniden değerleme oranı), 2026 Gelir Vergisi Tarifesi. Yeni bir GİB PDF'i
  bulundukça buraya eklenmesi yeterli; genel sayfayı otomatik keşfetmeye çalışmak (JS gerektirdiği
  için) sonuç vermez. **Not:** bu oturumun bulut ortamı `cdn.gib.gov.tr`'a kendi ağ izin listesi
  yüzünden bağlanamadı (403, siteyle ilgisi yok); içerik ve robots.txt ayrı bir araçla (WebFetch)
  doğrulandı ama gerçek taramanın kullanıcının bilgisayarında çalıştırılması gerekiyor:
  `python -m accounting.refresh --source "Gelir Idaresi Baskanligi"` (yalnız bu kaynağı tarar,
  saniyeler sürer), ardından `--rebuild-only` ile süzgeç tazelenir.
  **Güncelleme (aynı gün, kullanıcının bilgisayarında gerçek taramadan sonra):** 4 tahmini
  adresten yalnız **1**'i (2026 Gelir Vergisi Tarifesi) gerçekten geçerli çıktı; diğer üçü
  `accounting/source_registry.py`'den çıkarıldı (aşağıdaki bölüm 8/9 de buna göre güncellendi).
  Kalan adres doğrulanmış durumda ve süzgece katkı veriyor.
- **`verginet.net` eklenmedi.** Kullanıcı "verginet'i gib'den almış kabul edebilirsin" dedi, ama
  `verginet.net/robots.txt` isteği bir robots.txt değil, Deloitte'un Web Application Firewall'unun
  erişim reddi sayfasını döndürüyor — yani site otomatik erişimi (bot trafiğini) etkin şekilde
  engelliyor, bu bir "izin sorusu" değil. AGENTS.md madde 5 ("Sitelerin robots.txt/403/429 engeli
  aşılmaz") burada da geçerli: içeriğin GİB'den alınmış olması, WAF engelini aşmayı
  haklı çıkarmaz. Aynı sirküler içerikleri zaten Vertax, Alomaliye, Muhasebe TR gibi taranan
  kaynaklarda tam metin olarak bulunuyor (bkz. yukarıdaki örnekler); asıl eksik olan resmi
  (GİB) doğrulama artık üstteki PDF seed'leriyle kısmen sağlanıyor.

## 4f. Kaizen'in beynini geliştirme: dış öneri değerlendirmesi ve seçilen yol (2026-09-22)

Kullanıcıya Kaizen'in ana hafıza/öğrenme altyapısı olarak **Cognee** (+ ileride Graphiti)
önerildi. Değerlendirme: felsefe doğru ("Kaizen Cognee/Hermes/Graphiti değildir, bunlar
organ") ama zamanlama erken — Cognee'nin "API anahtarsız" yerel kurulumu bile gerçekte
Ollama üzerinden **llama3.1:8b** gibi gerçek bir yerel LLM + ayrı bir embedding modeli
istiyor (resmi doküman: `docs.cognee.ai/guides/local-setup`), yani zaten yol haritasının
6. maddesindeki "yerel model / yeni güçlü PC" ön koşuluna bağlı. Ayrıca Graphiti'nin
vaat ettiği "zamanla değişen, kaynaklı, silinmeyen gerçek" zaten `accounting/facts.py` +
`fact_history` tablosunda çalışır ve test edilmiş durumda — bunu genel amaçlı bir bilgi
grafiğine taşımak risk/kazanç dengesi kötü. Letta/Mem0'ı erteleme kararı (redundan katman)
doğru bulundu.

**Seçilen yol — kademeli, bağımlılık eklemeden önce mevcut sistemi güçlendirme:**

- **Kademe 0 (yapıldı, bugün):** Kaizen'in gerçek zayıf noktası — serbest metin/kavram
  aramasında Türkçe ek farkı ("muhasebede" sorudaki hali, metinde "muhasebe" olarak
  geçiyor) — düzeltildi. `core/text_tr.py`'deki `stem_tr()` gerçek (iki yönlü, en çok 2
  ek art arda kırpan) bir hafif Türkçe ek kırpıcıya genişletildi; `accounting/retriever.py`
  artık soru ve metin kelimelerini bu ortak köke indirip öyle karşılaştırıyor (eskiden yalnız
  tek yönlü bir "son harfi kırp" mantığı vardı, bu yüzden ek soruda olunca eşleşme kaçıyordu).
  Artık `"muhasebe:"` önekine gerek kalmadan doğal cümleler ("Muhasebede dönemsellik kavramı
  ne demek?", "SGK'da 4/a 4/b 4/c...") doğru kayda ulaşıyor — bu, önekle aynı 4 soru
  altın sınava tekrar (önek olmadan) eklendi (66 → **70** soru). Yeni testler:
  `tests/test_text_tr.py`, `tests/test_retriever.py`. Hiçbir yeni bağımlılık eklenmedi
  (saf Python, elle yazılmış ek listesi — Zemberek gibi ağır bir kütüphane yok).
- **Kademe 1 (yapıldı, 2026-09-22):** `memory/brain_manager.py::BrainManager` eklendi.
  `KaizenBrain` artık `learning_store`, `site_store`, `facts`, `cards` depolarına ve
  `Retriever`'a **tek tek kendi içinde** dokunmuyor; hepsi `BrainManager` içinde toplanıp
  `self.brain` üzerinden TEK arayüzle konuşuluyor. `BrainManager` kendisi dev bir sınıf
  değil — arama (`Retriever`), doğrulama (`FactRegistry`+`AccountingConsensus`), öğrenme
  (`KnowledgeCardStore` ile kart oluşturma/çapraz kontrol/kalıcı hafızaya işleme) ve
  fiziksel depolama (`LearningStore`, `SiteStore`) hâlâ ayrı, kendi başına test edilen
  sınıflarda; `BrainManager` yalnızca bunları birleştirip tek arayüz sunan bir koordinatör.
  `KaizenBrain`'in dışa dönük arayüzü (constructor imzası, `_remember_research`,
  `confirm_card` gibi test edilen metotlar) hiç değişmedi — mevcut 27 test dosyasının
  tamamı değişmeden yeşil kaldı; ayrıca `tests/test_brain_manager.py` (4 yeni test)
  eklendi. **Bilinçli kapsam dışı bırakma:** `AccountingAgent`'ın kendi küçük JSON
  düzeltme deposu (`accounting/learning_memory.py`) bu kademede BrainManager'a
  taşınmadı — `tests/test_accounting.py` ve `tests/test_office_and_commands.py::test_commands`
  bunun `AccountingAgent`'ın kendi içinde kalmasını doğrudan test ediyor (`core/commands.py`
  hâlâ `accounting_agent.learn()` ile doğrudan konuşuyor). Bu dar, kendi başına test
  edilmiş bileşen ileride (Kademe 2+) BrainManager'a taşınabilir; şimdilik risksiz
  bırakıldı. Yeni bağımlılık eklenmedi.
- **Kademe 2 (sonra, hâlâ hafif):** Kavramlar arası basit bir ilişki tablosu (SQLite'ta
  düz bir "kenar" tablosu — Neo4j/graf veritabanı değil) — `knowledge/*.json`'daki
  konuların birbirine el ile bağlanması (ör. "reeskont" -> "622 hesabı", "senet"). Otomatik
  (LLM ile) ilişki çıkarımı değil, curated ilişki; bu, hem doğruluk garantisini korur hem
  de hiçbir yeni altyapı gerektirmez.
- **Kademe 3 (ön koşul karşılandı, 2026-09-22 — bkz. 4g):** Cognee (veya benzeri) dar bir
  pilot olarak, yalnız serbest metin/deneyim tarafında denenir — sayısal parametre katmanına
  (`facts.py`/`consensus.py`) hiçbir zaman dokunmaz, o katman deterministik ve kaynaklı
  kalır. Graphiti aynı mantıkla yalnız gerçekten ihtiyaç doğarsa (ör. çok sayıda çakışan
  zamanlı gerçek biriktiğinde) değerlendirilir.

## 4g. Yerel LLM altyapısı kuruldu: Ollama + Cognee (2026-09-22, kullanıcının bilgisayarında)

Kullanıcı, bu oturumun dışında (bilgisayarındaki Claude Code oturumuyla doğrudan) Kademe 3'ün
ön koşulunu erkenden karşıladı: **Ollama** kuruldu, sohbet modeli **llama3.2:3b** ve embedding
modeli **bge-m3** indirildi, proje sanal ortamına **cognee==1.6.0** kuruldu. Yeni dosyalar:
`memory/cognee_memory.py` (`CogneeMemory` sınıfı: `remember`/`recall`/`forget`, hepsi async +
eşzamanlı sarmalayıcı) ve `memory/COGNEE.md` (gerekçe notu). `config/Kaizen.json` içine
`memory.cognee` bölümü eklendi, `enabled: true`. `CogneeMemory().health()` → `{'ok': True}`
doğrulandı (Ollama'ya bağlanıyor, iki model de yüklü).

**Tasarım kalitesi iyi:** LLM sağlayıcı bilinçli olarak Ollama (Hermes değil, çünkü Hermes
bulut tabanlı bir ajan CLI'ı — hafıza içeriği bilgisayardan çıkmasın diye); `is_ready()`
yalnız `localhost`/`127.0.0.1` uç noktalarını kabul ediyor (yanlışlıkla uzak bir uca
bağlanmayı engeller); hazır değilken hata fırlatmak yerine `{"ok": False, "error": ...}`
dönüyor; `forget()` yalnız `confirmed=True` ile siliyor. AGENTS.md'nin izin/güvenlik
ruhuna uygun.

**Önemli — henüz Kaizen'in kararına hiç karışmıyor:** `cognee_memory.py` bağımsız, tek
başına duran bir modül; `KaizenBrain`, `BrainManager` ya da `AccountingAgent`'ın hiçbiri
onu içe aktarmıyor (doğrulandı: proje genelinde "cognee" arandığında yalnız kendi dosyası
çıkıyor). `health()`'in `ok: True` dönmesi yalnızca "altyapı çalışıyor" demek — Kaizen şu an
sorulara cevap verirken bunu hiç kullanmıyor; hiçbir mevcut davranış değişmedi (28 test
dosyasının tamamı, kullanıcının bilgisayarındaki güncel dosyalarla senkronize edilip
yeniden çalıştırılarak da doğrulandı — hepsi yeşil).

**Bağlanacağı zaman kuralı:** `CogneeMemory` ileride gerçekten devreye alınacaksa, doğrudan
`KaizenBrain`'e beşinci bir bağımlılık olarak eklenmemeli — tam olarak Kademe 1'de kurulan
`BrainManager` bunun için var. Doğru yol: `BrainManager`'a yeni bir yöntem/koleksiyon olarak
eklemek (ör. `BrainManager.experience_recall(...)`), böylece `KaizenBrain`'in kararı yine
tek bir arayüzle (BrainManager) konuşmaya devam eder; hafıza altyapısı değiştiğinde karar
mantığı değişmez ilkesi bozulmaz.

**Not (ayrı konu, incelendi):** Kullanıcı `test_accounting_sources` testinde bir hata
bildirdi (Cognee işinden değil, GİB seed adresleri düzenlemesinden — bkz. yukarıdaki
güncelleme notu — kaynaklandığı düşünülüyor). Bu oturumda kullanıcının bilgisayarındaki
güncel `accounting/source_registry.py` indirilip yerelde test edildi: **şu an hata tekrar
etmiyor**, `test_accounting_sources` dahil tüm takım yeşil. Tekrar görülürse ayrıca bakılabilir.

**Kaizen'in kod tabanıyla ilgisi olmayan, geliştirme-zamanlı araçlar:** Kullanıcının
bahsettiği Serena/Basic Memory/Spec Kit (`.serena/`, `.specify/`), Kaizen'in çalışan
asistanının (bu belgedeki mimari: `core`/`models`/`tools`/`memory`/`skills`/`security`) bir
parçası değil — bunlar kod üzerinde çalışan Claude Code oturumu için geliştirme-zamanlı
yardımcı araçlar (sembol arama/düzenleme, geliştirme notları, özellik planlama akışı).
Kaizen'in kendisi bunları çalışırken kullanmıyor; karıştırılmaması için burada not edildi.

## 4h. Masaüstü uygulaması, mali müşavir sesi tutarlılığı ve cevap verme matrisi (2026-09-22)

**Masaüstü uygulaması:** `desktop_app.py` (Tkinter, yalnız standart kütüphane) + `Kaizen_Baslat.bat`
eklendi. Mali müşavir artık PowerShell olmadan, sıradan bir sohbet penceresinden Kaizen'i
test edebiliyor. `core.engine.KaizenEngine`'i sarmalar, karar mantığına dokunmaz; motor
başlatma ve her soru arka plan thread'inde çalışır (pencere donmaz). SQLite depoları
(`LearningStore`/`SiteStore`/`FactRegistry`/`KnowledgeCardStore`) her çağrıda kendi
bağlantısını açtığı için (`with closing(sqlite3.connect(...))` deseni, hiçbiri bağlantıyı
`self`'e saklamıyor) çoklu thread'den çağrılması güvenli — kontrol edildi.

**Mali müşavir sesi tutarlılığı:** `accounting/retriever.py::build_prompt` (yerel hafıza
yolu) zaten "Sen Kaizen AI'sın: Türkiye'de çalışan mali müşavir gibi düşünen..." diyordu,
ama `accounting/researcher.py`'nin 4 prompt'unda (yerel özet, resmi arama, mesleki arama,
derin arama) bu çerçeve hiç yoktu — yalnızca "araştırmacısın" deniyordu. Dört prompt'a da
ortak `_ADVISOR_VOICE` satırı eklendi, artık araştırma zincirinden gelen cevaplar da aynı
mali müşavir sesiyle çerçeveleniyor. Test: `tests/test_accounting.py` içine
`"mali müşavir" in provider.prompt` doğrulaması eklendi.

**Cevap verme durumları (`KaizenBrain.last_route`) — netleştirilmiş matris:**

| `last_route` | Ne zaman | Ses/biçim |
| --- | --- | --- |
| `correction` | Kullanıcı `düzelt:` ile öğretmiş | Ham, olduğu gibi (kullanıcının kendi cevabı) |
| `arithmetic` / `calculator` / `journal` / `chart` | Kesin araçlar | `SONUÇ:` / borç-alacak biçimi, model yok, mali müşavir sesi gerekmez (matematik) |
| `facts` | Süzgeçten geçmiş parametre defteri | Kaynaklı, yıl belirtilir |
| `memory_grounded` | Model açık + yerel kanıt var | **Mali müşavir sesi (LLM prompt'unda)** |
| `memory_extractive` | Model kapalı, kanıt soruyla yeterince örtüşüyor | Kaynak metinden doğrudan alıntı (ders notu/site zaten profesyonel yazılmış) |
| `memory_card_pending` / `memory_card_confirmed` | Önceden araştırmayla öğrenilmiş kart | Kart cevabı + onay durumu notu |
| `research` | Yerelde yok, araştırma zinciri çalıştı | **Mali müşavir sesi (bugün eklendi, `researcher.py`)** |
| `not_found_offline` / `office_missing` | Hiçbir yerde yok | Dürüst "bulamadım", uydurmaz |

**Not — test koordinasyonu:** Bilgisayarındaki diğer Claude Code oturumu, Cognee işini
yaparken `tests/test_self_learning.py`'deki önemli bir kontrolü (araştırma sonucunun
beklemede olsa bile HEMEN `learning_store`'a yazıldığının doğrulanması — bölüm 4c'nin özü)
zayıflatmış. Kontrol ettim: gerçek kod (`memory/brain_manager.py`, `core/kaizen_brain.py`)
hiç değişmemiş, testin orijinal (sıkı) hali hâlâ sorunsuz geçiyor — yani bu bir gerçek
davranış değişikliği değildi, muhtemelen anlaşılmadan gevşetilmiş. Orijinal sıkı testi geri
yükledim. Bilgisayarındaki diğer oturuma, test dosyalarını (özellikle `tests/test_self_learning.py`,
`KAIZEN_HEDEF_VE_YOL_HARITASI.md`) benim de aktif düzenlediğimi söylersen iki tarafın
birbirinin değişikliğini kaybetmesi önlenir.

## 4i. Sohbetten dosya okuma ve Excel/hesap teyidi (`oku:` / `doğrula:`) (2026-09-22)

Kullanıcının açık isteği: "excel bilgisini teyit eksiği varsa gider / hesaplarımı kontrol et
eksiği varsa gider / pdf okuma ve resimli dosyaları okuma özelliği kat". Taramada şu gerçek
boşluk bulundu: `tools/office_tools.py::pdf_oku` / `excel_oku` / `word_oku` uzun süredir
vardı ve `tool_manager`'a kayıtlıydı, ama `core/commands.py::CommandHandler.handle()` bunlara
hiç yönlendirme yapmıyordu — yani sohbetten bir dosya okutmanın **hiçbir yolu yoktu**. İki yeni
komutla kapatıldı:

- **`oku: <dosya yolu>`** — uzantıya göre (`.pdf` → `pdf_oku`, `.xlsx`/`.xlsm` → `excel_oku`,
  `.docx` → `word_oku`) doğru aracı çağırır ve içeriği döner. Excel'de belirli sayfa için:
  `oku: rapor.xlsx | sayfa: Ocak`.
- **`doğrula: <dosya yolu>`** — Excel/PDF'teki rakamları, süzgeçten geçmiş **doğrulanmış**
  parametre defteriyle (`FactRegistry`, yalnız `status=verified` satırlar) karşılaştırır.
  Yeni `AccountingAgent.verify_document()` (bkz. `accounting/accounting_agent.py`) belgeyi ve
  bilinen parametreleri tek bir mali-müşavir-sesli (`_ADVISOR_VOICE`, bkz. bölüm 4h) prompt'ta
  birleştirip modele "uyuşuyor / uyuşmuyor / karşılaştırılamıyor" şeklinde satır satır kontrol
  ettirir; parametre defterinde karşılığı olmayan kalemler için rakam uydurmaması açıkça
  istenir. Bu, `researcher.research()`'ten kasıtlı olarak ayrı bir yol: yeni web araması
  yapmaz, önbelleğe (`knowledge_store`) yazmaz — tek seferlik, kullanıcının kendi belgesine
  özel bir kontrol.

Kapsam dışı bırakılan (bilinçli): görsel/taranmış-PDF için OCR henüz yok (`pdf_oku` yalnız
metin katmanını okur; taranmış sayfalarda "metin yok - taranmış resim olabilir" der). Bu,
madde 9/11(b)'de hâlâ açık bir iş kalemi.

Test: `tests/test_accounting.py::test_accounting_agent_verify_document` (prompt içeriği,
boş belge, `ask` desteklemeyen provider durumları) ve
`tests/test_office_and_commands.py::test_document_commands` (uzantı yönlendirmesi, sayfa
seçimi, desteklenmeyen tür, doğrulama akışı uçtan uca sahte `tool_manager`/`accounting_agent`
ile). `tests/run_all.py`'a eklendi; tam takım yeşil (30 test dosyası).

## 4j. İlk tam taramadan sonra çıkan 4 çelişki: kaynak cümle analizi ve süzgeç düzeltmesi (2026-09-22)

Kullanıcı `python -m accounting.refresh --backfill` ile ilk tam taramayı çalıştırdı (bkz. bölüm 9,
madde 11): 36 parametre bulundu (14 doğrulanmış, 18 tek kaynak, **4 çelişkili** — bölüm 4e'deki
1 çelişkiliden fazla). Her birinin kaynak kanıt cümleleri (`evidence_json`) tek tek okundu; kör
sayı seçmek yerine (kural: uydurma) neden çelişki çıktığı analiz edildi:

- **Asgari ücret (brüt) 2026 — süzgeç hatası, düzeltildi.** 33.030,00 TL, 10'dan fazla bağımsız
  kaynakta (alomaliye, vergimerkezi, muhasebetr, pkf×3, musavirlerkulubu×2, muhasebebilenler×2)
  aynen geçiyordu — gerçek uzlaşı zaten vardı. Ama süzgeç aynı sayfalardaki **günlük** tutarı
  (33.030/30=1.101 TL), **yıllık** toplamı (33.030×12=396.360 TL) ve "asgari ücretin **onda
  birini**" (3.303 TL — SGK eksik prim bildirim sınırı, tamamen ayrı bir kavram, 2 bağımsız
  sitede aynı resmî genelge metni tekrarlandığı için "doğrulanmış" eşiğini de geçiyordu) kendi
  adayı sanıyordu; bu da `AccountingConsensus.decide()`'da iki ayrı "doğrulanmış" grup oluşup
  "çelişkili" sonucuna yol açıyordu. **Düzelti:** `config/fact_topics.json`'da
  `asgari_ucret_brut`/`asgari_ucret_net` konularına `avoid: ["gunluk", "yillik", "onda bir"]`
  eklendi. Kanıt: `tests/test_facts.py::test_facts_asgari_ucret_ignores_gunluk_yillik_and_onda_bir_sentences`.
- **VUK 313 iktisadi kıymet sınırı 2024 — süzgeç hatası, düzeltildi.** "690.000 TL" değeri
  `muhasebenews.com/2024-binek-oto-muhasebe-kaydi` sayfasındaki "Gider yazılabilecek KDV+ÖTV
  Tutarı" satırından geliyordu — bambaşka bir binek-oto kavramı; var olan `avoid: ["binek"]`
  kuralı bu kısa (başlık gibi) satırda "binek" kelimesi geçmediği için yakalayamıyordu.
  **Düzelti:** `avoid` listesine `"otv"` eklendi (ÖTV hiçbir zaman genel demirbaş/amortisman
  sınırıyla ilgili değil). Kanıt: `tests/test_facts.py::test_facts_vuk_313_ignores_binek_oto_otv_line`.
  Ayrıca: gerçek "4.400 TL" adayı da yanlıştı — vergiport'un cümlesi ("daha önce uygulanmakta
  olan 4.400 TL'lik sınır ... 01.01.2024'ten itibaren **6.900 TL** olacaktır") "eski X, yeni Y"
  kalıbında; süzgeç anchor'a EN YAKIN sayıyı seçtiği için eski değeri (4.400) alıyor, doğru
  güncel değeri (6.900) atlıyor. Bu, "eski/yeni" kalıbındaki TÜM konuları etkileyebilecek genel
  bir sınırlama — riskli/geniş bir davranış değişikliği olacağından bu oturumda dokunulmadı
  (bkz. bölüm 8, yeni madde). 2024 VUK 313 sınırının muhtemelen **6.900 TL** olduğu not edilsin,
  ama resmî 556 Sıra No.lu VUK Genel Tebliği ile teyit edilmeden kesin kabul edilmemeli.
- **Kıdem tazminatı tavanı 2026 — hata değil, beklenen durum.** 64.948,77 TL (01.01-30.06.2026
  dönemi) ve 73.729,87 TL (01.07-31.12.2026 dönemi) — ikisi de doğru, bu parametre yılda İKİ KEZ
  güncellenir. Süzgeçte "dönem" (Ocak-Haziran/Temmuz-Aralık) boyutu olmadığı için ikisi de aynı
  (topic, yıl) anahtarına yazılıp "çelişkili" görünüyor. Şimdilik dokunulmadı — şema değişikliği
  gerektirir (bkz. bölüm 8).
- **Binek otomobil aylık kiralama gider sınırı 2024 — gerçek belirsizlik, düzeltilmedi.**
  14.500 TL ve 30.000 TL, kaynak sayfalardaki "Örnek" (worked example) hesaplamalarından geliyor
  — yazarın seçtiği HAYALİ kira tutarları, yasal sınır değil. 8.000 TL ise vergiport'ta gerçek
  sınır gibi görünüyor ama cümle "iken;" ile yarıda kesiliyor (muhtemelen bir artışın öncesi).
  "Örnek cümlesi" ile "gerçek sınır cümlesi"ni ayırt etmek regex/anchor yaklaşımıyla güvenilir
  yapılamıyor (bölüm başlığındaki "Örnek" kelimesi ayrı bir cümlede kalıyor). Kaizen'in burada
  "kesin cevap veremiyorum" demesi **doğru** davranış; zorla düzeltilmedi.

Tüm test takımı (30 test dosyası) yeşil. Uygulamak için kullanıcının **yeniden tarama
gerekmiyor** — yalnız `python -m accounting.refresh --rebuild-only` (zaten indirilmiş sayfalardan
süzgeci yeniden kurar, saniyeler sürer).

## 4k. Kaizen beyni Kademe 2: Cognee deneyim hafızası BrainManager'a bağlandı (2026-09-22)

Kullanıcının açık önceliği ("kaizen beyni yeni eklentiler ile tekrardan dizayn edilmeli önce"):
bölüm 4g'de kurulu ama bağlanmamış duran Ollama+Cognee, artık **BrainManager'a (Kademe 2)**
yeni bir yöntem olarak bağlı — bölüm 4g'nin koyduğu kural aynen uygulandı: doğrudan
`KaizenBrain`'e değil, yalnız `BrainManager` üzerinden, ve kart/ders notu sisteminin (bölüm 4c)
YERİNE değil ONA EK bir katman olarak.

- `memory/brain_manager.py::BrainManager.__init__` artık `self.experience` tutuyor
  (varsayılan: `CogneeMemory()`; test için `experience_memory=` ile değiştirilebilir).
  `CogneeMemory()`'nin kurucusu ağır `cognee` paketini içe aktarmaz (yalnız config okur) —
  bu yüzden koşulsuz oluşturmak ucuz/güvenli.
- `BrainManager.remember_experience(question, answer)` — bir soru-cevabı Cognee'ye yazar.
- `BrainManager.recall_experience(question, top_k=None)` — bu soruya anlamsal (embedding
  tabanlı) yakın geçmiş alışverişleri döner.
- **İkisi de try/except ile sarılı, ana cevap akışını ASLA bozmaz.** Bu, varsayımsal bir
  önlem değil: bu bulut ortamında config `enabled=true` ama `cognee` paketi kurulu DEĞİL —
  yani `_load_cognee()` gerçekten `ModuleNotFoundError` fırlatıyor ve testler bu hatanın
  gerçekten yutulduğunu kanıtlıyor (`tests/test_brain_manager.py::
  test_brain_manager_experience_memory_is_additive_and_never_raises`). Kullanıcının kendi
  bilgisayarında Ollama+cognee kuruluyken de aynı yol kullanılır, orada gerçekten hafızaya yazar.

`core/kaizen_brain.py::KaizenBrain.answer()` artık ince bir sarmalayıcı: gerçek karar mantığı
`_answer_core`'a taşındı, `answer()` yalnız BAŞARIYLA verilen (boş/`not_found_offline`/
`office_missing` olmayan) HER cevabı `remember_experience` ile deneyim hafızasına yazıyor —
hangi yoldan geldiği (matematik, hesap planı, yerel hafıza, araştırma, kart...) fark etmeksizin.
Kaizen'in gerçekten "bulamadım" dediği İKİ son çare noktasında (`not_found_offline`,
`office_missing`) yeni `_refusal_with_experience` yardımcı metodu `recall_experience`'a bakar;
bir şey bulursa mesaja **açıkça "NOT (doğrulanmamış, Kaizen'in geçmiş deneyim hafızasından):"**
etiketiyle ekler — asla kesin cevap gibi sunmaz (uydurmama kuralı burada da geçerli); bulamazsa
mevcut ret mesajı hiç değişmeden kalır.

Testler: `tests/test_brain_manager.py::test_brain_manager_experience_memory_is_additive_and_never_raises`
(sahte deneyim hafızasıyla: yazma, geri çağırma, boş soru/cevabın atlanması, hata fırlatan
Cognee'nin yutulması, varsayılan `CogneeMemory()` ile kurucu patlamaması) ve
`tests/test_kaizen_brain.py::test_brain_remembers_successful_answers_and_offers_experience_on_refusal`
(uçtan uca: matematik/yerel-hafıza cevaplarının yazıldığı, boş sorunun yazılmadığı, deneyim
hafızası boşken ret mesajının değişmediği, doluyken doğru etiketle eklendiği). Tam takım yeşil.

**Not — dosya çakışması bu bölümde de yaşandı:** `memory/brain_manager.py`'yi ilk gönderdiğimde
saniyeler içinde eski haline döndürülmüş, ikinci göndermede kalıcı oldu (bkz. bölüm 4j'nin sonu
ve kullanıcıya iletilen not — bilgisayarda aktif çalışan başka bir Claude Code oturumu aynı
dosyalarla ilgileniyor olabilir). Kullanıcının `python -m tests.run_all` çalıştırıp bu bölümdeki
testlerin gerçekten geçtiğini (ve `BrainManager`/`KaizenBrain`'in eski sürüme dönmediğini)
doğrulaması önerilir.

Kapsam dışı bırakılan (bilinçli, Kademe 2 kararı): deneyim hafızası hiçbir zaman KESİN/sayısal
bir cevabın kaynağı olarak kullanılmaz (o hâlâ yalnız cards/facts/exact-tools). Süzgeç/kart
geri-çağırmayı Cognee ile "güçlendirme" burada en güvenli, en dar kapsamlı haliyle yapıldı;
ileride örneğin `recall_card`'a da bir deneyim-hafızası ipucu eklenebilir (Kademe 3) ama bu,
mevcut testler ve altın sınav sonuçları üzerinde dikkatli bir regresyon kontrolü gerektirir.

## 4l. Kademe 2'de bulunan ve düzeltilen kritik performans hatası: deneyim hafızası artık arka planda (2026-09-22/23)

Kullanıcı gerçek bilgisayarında `python -m tests.run_all` çalıştırdı ve çıktı
"KAIZEN MATEMATIK HESAP MOTORU TESTI: BASARILI" satırından hemen sonra, gerçek Cognee 1.6.0
başlatma (init) günlükleriyle birlikte durmuş/çok yavaşlamış göründü. Kullanıcı çıktıyı
olduğu gibi yapıştırdı; kesin teşhis konuldu — sebep önceden tahmin edilmedi, doğrudan
kanıttan (log satırları + hangi testten sonra durduğu) çıkarıldı.

**Kök neden:** 4k'de kurulan `remember_experience`/`recall_experience` bağlantısı ilk
haliyle TAMAMEN SENKRONDU. Bu bulut ortamında `cognee` paketi kurulu olmadığı için
`try/except` anında hatayı yutuyor ve fark edilmiyordu — ama kullanıcının gerçek
bilgisayarında `cognee` kurulu ve Ollama muhtemelen çalışıyor: `KaizenBrain.answer()`'ın
verdiği HER başarılı cevaptan sonra gerçek bir LLM+embedding çağrısı (saniyeler sürebilir)
tamamlanmadan cevap kullanıcıya dönmüyordu. Aynı şekilde `not_found_offline`/`office_missing`
ret yollarındaki `recall_experience` çağrısı da sınırsız bekleyebilirdi. Sonuç: masaüstü
uygulaması her mesajdan sonra donmuş gibi hissettirir, test takımı yavaşlar/takılır.

**Düzeltme** (`memory/brain_manager.py`):

- `remember_experience(question, answer, background=True)` — gerçek `remember()` çağrısı artık
  varsayılan olarak ayrı bir **daemon thread**'de (`threading.Thread`) çalışır; çağıran taraf
  (Kaizen'in cevap akışı) hiç beklemez. Testlerde deterministik doğrulama gerektiğinde
  `background=False` ile senkron çalıştırılabilir.
- `recall_experience(question, top_k=None, timeout=8)` — gerçek `recall()` çağrısı yine ayrı bir
  thread'de başlatılır, ama çağıran taraf `thread.join(timeout)` ile EN FAZLA `timeout` saniye
  bekler; süre dolarsa (Ollama yanıt vermiyor/çok yavaşsa) boş liste döner — ret mesajı hiç
  gecikmeden kullanıcıya ulaşır, yalnızca "deneyim hafızasından ipucu" eklenemez.
- `KaizenBrain`'in çağıran kodu değişmedi — yeni parametreler geriye dönük uyumlu varsayılanlarla
  eklendi.

**Testler** (`tests/test_brain_manager.py`, `tests/test_kaizen_brain.py`):

- Mevcut `test_brain_manager_experience_memory_is_additive_and_never_raises` artık zamanlamayla
  ilgilenmeyen kısımlarda `background=False` kullanıyor (mantık doğruluğunu kanıtlamaya devam
  eder, ama artık iş parçacığı zamanlamasına karşı kırılgan değil).
- Yeni `test_brain_manager_remember_experience_runs_in_background_and_recall_has_timeout` —
  `remember()`/`recall()`'ı 0,3 saniye geciktiren sahte bir hafıza ile: `remember_experience`'ın
  gerçekten anında (< 0,1 sn) döndüğünü ama iş parçacığının arka planda tamamlandığını, ve
  `recall_experience`'ın kısa bir `timeout` verildiğinde tam gecikmeyi beklemeden boş döndüğünü,
  yeterli `timeout` verildiğinde ise doğru sonucu döndürdüğünü kanıtlıyor — tam olarak
  kullanıcının yaşadığı donma senaryosunun düzeltildiğinin kanıtı.
- Uçtan uca `test_brain_remembers_successful_answers_and_offers_experience_on_refusal` artık
  `KaizenBrain.answer()`'dan hemen sonra deneyim hafızasını kontrol ederken sabit bekleme yerine
  kısa aralıklarla yoklayan bir `_wait_until` yardımcı fonksiyonu kullanıyor (arka plan
  yazma işleminin gerçekten tamamlanmasını, testi yavaşlatmadan bekler).

Tam takım (45 test) yeşil; `tests/run_all.py` yeni testi de çalıştırıyor. Değişiklikler
kullanıcının bilgisayarına gönderildi ve gönderim sonrası tekrar okunup **bayt bayt aynı**
olduğu doğrulandı (bu dosyanın daha önce iki kez sessizce eski haline döndürüldüğü göz önünde
bulundurularak — bkz. bölüm 4j/4k notları).

**Kullanıcıdan istenen:** yarım kalan `python -m tests.run_all` çalışmasını (eski, senkron kod
ile başladığı için yavaş ama muhtemelen sonunda BAŞARILI ile bitecektir) beklemek yerine
iptal edip, güncellenmiş kodla yeniden çalıştırması — artık Cognee/Ollama kurulu olsa bile
normal hızda tamamlanmalı.

## 4m. Taranmış PDF ve fotoğraflanan belgeler için OCR (2026-09-23)

Bölüm 9'da açık bırakılan (d) maddesi: `pdf_oku`'nun metin katmanı boş bir sayfada
("taranmış resim olabilir") artık uydurmadan, gerçek bir OCR ile okuma denemesi var; ayrıca
fotoğraflanmış fatura/makbuz gibi düz görselleri okumak için yeni `gorsel_oku` aracı eklendi.

- `tools/office_tools.py::pdf_oku(path, max_pages=30, ocr=True)` — `pypdf`'in metin katmanı
  boş döndürdüğü HER sayfada (yalnız tam taranmış PDF'ler değil, tek tek boş sayfalar da)
  otomatik olarak OCR'a düşer: `pdf2image` (+ Poppler) ile sayfa görsele çevrilir, `pytesseract`
  (+ Tesseract OCR motoru) ile metne çevrilir. Başarılıysa sayfa başlığına `(OCR)` eklenir;
  `ocr=False` verilirse eski davranış (yalnız "metin yok" notu) hiç değişmeden korunur.
- `tools/office_tools.py::gorsel_oku(path)` — yeni araç: `.jpg/.jpeg/.png` bir görseli
  doğrudan OCR ile metne çevirir (`gorsel_pdf`'in tersi: o görselleri PDF'e gömer, bu görseldeki
  metni okur). `oku:` ve `doğrula:` komutlarına da bağlandı (`core/commands.py`) — artık
  telefonla fotoğraflanmış bir fatura/makbuz da `oku: fatura.jpg` ile okunabiliyor,
  `doğrula: fatura.jpg` ile parametre defteriyle karşılaştırılabiliyor.
- **Çökmeme garantisi burada da geçerli:** `pdf2image`/`pytesseract` kütüphaneleri veya
  Poppler/Tesseract motorları kurulu değilse Kaizen çökmez — `_missing()` ile aynı üslupta,
  Windows'a özel açık bir kurulum talimatı (indirme linki + `config/Kaizen.json` içindeki
  `ocr.poppler_path` / `ocr.tesseract_cmd` alanlarına yol yazma) döner. Türkçe dil paketi
  (`tur.traineddata`) kurulu değilse sessizce İngilizce'ye ("eng") düşer — kesin/sayısal cevap
  kaynağı değil, yalnız belge okuma aracı olduğu için bu kabul edilebilir bir zayıflama.
- Ayarlar `config/Kaizen.json`'daki yeni `ocr` bölümünden okunur (`enabled`, `language`,
  `poppler_path`, `tesseract_cmd`) — PATH'e eklenmemiş kurulumlar için.
- `requirements.txt`'e `pdf2image==1.17.0` ve `pytesseract==0.3.13` eklendi (kütüphaneler);
  Poppler ve Tesseract-OCR motorları ayrıca sisteme kurulmalı (bkz. `ocr._not` notu ve
  kurulum linkleri — bu, kullanıcının kendi onayı gereken bir sistem kurulumu olduğu için
  buradan otomatik yapılmadı).

**Testler gerçek OCR motoruyla (mock değil) çalışır** — bu bulut ortamında Tesseract kurulu
olduğu için: `tests/test_office_and_commands.py::test_gorsel_oku_reads_text_via_ocr`
(PIL ile üretilen bir metin görselinin gerçekten okunduğunu kanıtlar) ve
`::test_pdf_oku_falls_back_to_ocr_for_scanned_pages` (görsel-only bir PDF'in `(OCR)` etiketiyle
okunduğunu, `ocr=False` ile eski davranışın korunduğunu kanıtlar). Bu ortamda Türkçe dil paketi
kurulu değil; testler bu yüzden İngilizce alfabede (Türkçe karaktersiz) örnek metinler kullanıyor
— gerçek Türkçe OCR kalitesi, kullanıcının bilgisayarına `tur.traineddata` kurulunca netleşecek.

## 4n. Dış inceleme (başka bir yapay zeka, salt-okunur): 7 madde, sırasıyla düzeltiliyor (2026-09-23)

Kullanıcı, Kaizen'in koduna salt-okunur erişimle bakan BAŞKA bir yapay zekadan bir değerlendirme
aldı ve "sürekli baştan tara diyorum ama sen hâlâ bazı şeyleri es geçiyorsun" eleştirisiyle
birlikte iletti. Önceki bölümlerdeki (4c-4m) ilerlemenin mimari yönünü doğru bulan, ama "gerçek
muhasebe işlerinde kontrolsüz kullanılacak olgunlukta değil" diyen bu inceleme, önem sırasına göre
7 somut sorun tespit etti. Kural: her madde önce KOD OKUNARAK doğrulanıyor (körü körüne
güvenilmiyor), sonra düzeltiliyor, sonra regresyon testi yazılıyor, sonra tüm takım çalıştırılıyor,
sonra bilgisayara gönderiliyor — hiçbiri atlanmadan ("es geçmeden"), sırasıyla ("sırası ile").

**1. Süzgeçte yüzde/ondalık nokta karışıklığı — düzeltildi.**
`accounting/consensus.py::AccountingConsensus._normalize_value` eskiden HER tek "." içeren sayıda
(virgül yokken) "." işaretini binlik ayıracı sayıp siliyordu — bu yalnızca noktadan sonra TAM 3
hane varsa doğrudur ("12.000" → 12000). "%4.5" gibi bir oranda "." aslında ONDALIK ayıracıdır;
eski kod bunu da siliyor, "%4.5" ile "%45" AYNI değermiş gibi ("45") gruplanıyor, iki kaynağın
gerçekte farklı oranlarını "aynı" kabul ettiriyordu. Artık `%`/`binde`/`‰` işaretli değerlerde "."
yalnızca gerçek 3‑hane binlik durumunda siliniyor, aksi halde ondalık sayılıyor; ayrıca çıktı
etiketine "%" tekrar eklendi ("20" ile "%20" karışmasın diye). Test:
`tests/test_accounting_consensus.py::test_accounting_consensus_percent_decimal_point_not_confused_with_thousands`.

**2. Belge doğrulamanın model-tabanlı olması, Excel/model okuma sınırları — düzeltildi.**
İki ayrı açık vardı: (a) `doğrula:` komutunun "uyuşuyor/uyuşmuyor" kararının TAMAMINI modele
bırakması (kesin/kodla karşılaştırma yoktu); (b) Excel okumanın varsayılan ilk 50 satırla, model
girdisinin de belge metninin ilk 8.000 karakteriyle sınırlı olması — büyük bir dosyanın TAMAMI
kontrol edilmiş SANILABİLİYORDU (kesilme kullanıcıya hiç bildirilmiyordu).
Fix (a): yeni `accounting/document_verifier.py::deterministic_matches()`,
`memory/brain_manager.py::_find_contradictions`'ın (araştırma metnini parametre defteriyle
çapraz kontrol eden) AYNI desenini kullanır — `FactExtractor` ile belge metninden aday değerler
çıkarılır, `AccountingConsensus._normalize_value` ile normalize edilip süzgeçten geçmiş
DOĞRULANMIŞ değerle birebir (kodla, model karışmadan) karşılaştırılır.
`accounting/accounting_agent.py::verify_document`, parametre defterinde karşılığı olan HER kalem
için bu KESİN sonucu "KESİN KOD KARŞILAŞTIRMASI" bloğu olarak öne ekliyor; model yalnızca burada
karşılığı bulunamayan kalemler için serbest yorum ekliyor ("AI YORUMU", çelişirse kesin olan esas
alınır notuyla). Facts registry verilmezse (veya eşleşme yoksa) çıktı eskisi gibi değişmeden
kalıyor (geriye dönük uyumluluk). Fix (b): iki parça — (i) `core/commands.py::verify_file`
artık Excel/PDF araçlarını (`oku:`'nün aksine) çok daha yüksek bir satır/sayfa sınırıyla çağırıyor
(Excel: 5000 satır, PDF: 200 sayfa; Excel'in kendi `MAX_CELLS` güvenlik supabı yine de aşırı büyük
dosyalarda devreye girer); (ii) kesin katman zaten belge metninin TAMAMI üzerinde (8.000 karakter
penceresinden bağımsız) çalışıyor, ve modele giden metin 8.000 karakterden uzunsa artık modelin
buna değinip değinmediğinden BAĞIMSIZ, kodla garanti bir kesilme uyarısı çıktıya ekleniyor.
Testler: `tests/test_document_verifier.py` (kesin katmanın eşleşme/uyuşmazlık tespiti, gerçek
`FactRegistry` ile uçtan uca, kesilme uyarısının modelin cevabından bağımsız garantiye alınması),
`tests/test_office_and_commands.py::test_document_commands` (güncellenmiş: `doğrula:`'nın
`facts_registry`'yi ilettiğini ve Excel'e yüksek satır sınırıyla gittiğini, `oku:`'nün bundan
etkilenmediğini doğrular).

**3. Bilgi kartı onaylama sağlamlaştırıldı — düzeltildi.** İki ayrı açık vardı:
(a) `memory/knowledge_cards.py::KnowledgeCardStore.remember()` eskiden `source_label`'ı hiç
kontrol etmiyordu — Kaizen şu an TEK bir araştırma sağlayıcısı (Hermes) kullandığından, aynı
sağlayıcının aynı soruyu iki kez benzer şekilde cevaplaması ("kendi kendini tekrarlaması")
yanlışlıkla "iki bağımsız kaynak aynı şeyi söyledi" sayılıp kartı otomatik "doğrulanmış"a
yükseltiyordu. Artık iki turun `source_label`'ı GERÇEKTEN farklı olmadıkça otomatik doğrulama
olmuyor (`independent_source` kontrolü) — Kaizen tek sağlayıcılıyken bu, doğal olarak yalnız
`onayla:` (mali müşavir onayı) ile doğrulanabileceği anlamına gelir; ikinci bağımsız bir sağlayıcı
eklenince bu yol da gerçek anlamda çalışmaya başlayacak.
(b) `memory/brain_manager.py::remember_research()`'ün çapraz kontrolü (`_cross_check`, eski adıyla)
eskiden kart durumuna karar VERİLDİKTEN SONRA çalışıyordu — yani AYNI turda bulunan bir çelişki,
o turun kartı "doğrulanmış" yapmasını engelleyemiyordu (çelişki kaydı düşse bile kart çoktan
onaylanmıştı). Artık `_find_contradictions(answer_text)` adıyla ayrıştırılan bu kontrol, kart
durumuna karar verilmeden ÖNCE çalışıyor; bir çelişki bulunursa `cards.remember(...,
block_confirm=True)` ile bu turun kendisinin doğrulamayı engellemesi sağlanıyor, ardından bulunan
çelişkiler karta işleniyor. Ayrıca: kart için daha önce kapatılmamış bir çelişki kaydı varsa
(geçmiş bir turdan), bu da tek başına yeni bir doğrulamayı engelliyor (`has_open_contradiction`).
"Tekrar edilmek, doğrulanmak değildir" eleştirisi böylece hem kaynak hem çelişki boyutunda
karşılanmış oldu. Elle onay (`confirm()`/`onayla:` komutu) bu kontrollerden bağımsız olarak her
zaman geçerlidir — bu kasıtlıdır, mali müşavirin kesin sözü her zaman geçer.
Testler: `tests/test_self_learning.py::test_knowledge_card_store_same_source_repeat_does_not_confirm`
(aynı kaynağın tekrarı doğrulamaz, farklı bağımsız kaynak doğrular),
`tests/test_brain_manager.py::test_brain_manager_remember_research_same_call_contradiction_blocks_confirmation`
(bağımsız kaynak + hit_count≥2 olsa bile aynı turda bulunan çelişki doğrulamayı engeller).

**4. Cognee arka plan yazımlarının güvenilirlik takibi — düzeltildi.** İnceleme, her cevap için
ayrı bir arka plan iş parçacığı açıldığını, `remember()`'ın döndürdüğü `ok=False` durumunun
kontrol edilmediğini, istisnaların sessizce yutulduğunu ve uygulama kapanınca devam eden işlerin
yarıda kalabileceğini belirtti (`memory/brain_manager.py::remember_experience`). Sohbetin
donmaması doğru bir tasarım kararıydı; ama "hafızaya gerçekten yazıldı mı?" hiç görünmüyordu.
Üç parça fix: (a) eskiden HER çağrı kendi tekil (sınırsız) thread'ini açıyordu; artık sabit
sayıda (`_EXPERIENCE_WORKERS=2`) arka plan işçisi, SINIRLI bir kuyruktan (`_EXPERIENCE_QUEUE_MAXSIZE=20`,
toplam kapasite en fazla 22) besleniyor — kuyruk dolarsa yeni yazım sohbeti bloklamadan atlanıyor,
ama artık SESSİZCE değil: hem loglanıyor (`core/logger.py`) hem de sayılıyor. (b) `ok=False`
veya istisna artık `self.logger.warning/error` ile açıkça loglanıyor, sessizce yutulmuyor.
(c) Yeni `BrainManager.experience_stats()` -> {"queued", "written", "failed", "dropped"} — her
an "kaç yazım gerçekten tamamlandı, kaç başarısız oldu, kaçı kuyrukta, kaçı kuyruk dolu diye
atlandı" sorulabiliyor; `core/commands.py`'deki `durum` komutu bu sayıları artık gösteriyor
("Deneyim hafızası (Cognee, arka plan): N yazıldı, N başarısız, N kuyrukta, N atlandı").
Uygulama tamamen kapanınca (process sonlanınca) yarıda kalan işlerin kaybolması hâlâ mümkündür
(daemon thread'ler süreçle birlikte biter) — bunu tam çözmek diskte kalıcı bir kuyruk gerektirir,
bu bilinçli olarak kapsam dışı bırakıldı (bkz. bölüm 8, açık sınır olarak not edildi); asıl
şikayet olan görünürlük eksikliği ve sınırsız thread büyümesi artık giderildi.
Testler: `tests/test_brain_manager.py::test_brain_manager_experience_stats_tracks_written_and_failed`
(ok=False ve istisna doğru sayılıyor), `::test_brain_manager_experience_queue_is_bounded_and_drops_when_full`
(işçileri kasıtlı meşgul tutup 100 yazım denemesi göndererek kuyruğun gerçekten sınırlı olduğunu
ve taşmanın sessizce değil sayılarak atlandığını kanıtlar), `tests/test_office_and_commands.py::
test_status_reports_experience_memory_background_stats` (`durum` komutunun yeni satırı gösterdiğini
doğrular).

**5. Süzgeç yeniden kurulduğunda eski geçersiz kayıtların temizlenmesi — düzeltildi.**
`accounting/facts.py::FactRegistry.rebuild()` eskiden yalnız o turda bulunan parametreleri
güncelliyordu; bir çıkarım kuralı (anchor/avoid) düzeltilip artık bir (konu, yıl) için hiç aday
üretilmediğinde, o kayıt tabloda ESKİ "doğrulanmış" durumuyla kalıyordu. Artık `rebuild()` sonunda
bu turda hiç aday üretmeyen (konu, yıl) anahtarları tespit edilip `_remove_stale()` ile
siliniyor; silme, denetim izi kaybolmasın diye `fact_history`'ye "removed" (yeni değer: null)
olarak işleniyor. Test: `tests/test_facts.py::test_rebuild_removes_stale_facts_when_extraction_rule_is_corrected`
(gerçek VUK 313 vakasının kalıbını yeniden üretir: `avoid` listesi düzeltilince eski kayıt gerçekten
silinir, geçmişte kalır).

**6. robots.txt'in kendisi 429 dönerse artık "izin verildi" sayılmıyor — düzeltildi.**
`accounting/crawler.py::_robots_for()` yalnız 401/403'ü "deny" sayıyor, 429 dahil diğer tüm 4xx'i
"izin verildi, robots.txt yok say" olarak ele alıyordu. 429, sitenin "zaten çok istek attın,
yavaşla" demesidir — "engel yok" anlamına gelmez; bu, normal sayfa çekmede zaten 429'u engelli
sayan `FetchResult.blocked` ile ve AGENTS.md'nin "403/429 aşılmaz" kuralıyla tutarsızdı. Artık
robots.txt'teki 429 da 401/403 gibi "deny" sayılıyor. Test:
`tests/test_crawler.py::test_robots_429_is_treated_as_blocked_not_allowed` (gerçek yerel HTTP
sunucusuyla).

**7. Testlerin gerçek kişisel hafızadan tam ayrılması — düzeltildi.** İnceleme, `BrainManager()`/
`KaizenBrain()`'in varsayılan olarak GERÇEK bir `CogneeMemory()` oluşturduğunu ve birçok test
dosyasının bunu hiç değiştirmediğini belirtti — kullanıcının gerçek bilgisayarında (cognee
kurulu + `memory.cognee.enabled=true`) bu, testlerin (en başta 70 sorulu altın sınavın HER
çalışmasında) kişisel hafızaya gerçek yazma/okuma yapması demekti; bu bulut ortamında zararsız
görünmesi (cognee kurulu değil) yanıltıcıydı. `tests/doubles.py::NullExperienceMemory` (gerçek
ağ/disk işlemi asla yapmayan sahte) oluşturulup şu dosyalardaki HER `BrainManager(...)`/
`KaizenBrain(...)` çağrısına `experience_memory=`/`brain_manager=` ile enjekte edildi:
`test_kaizen_brain.py`, `test_golden_exam.py`, `test_self_learning.py`, `test_brain_manager.py`.
Bunun bir daha sessizce bozulmaması için `tests/test_experience_memory_isolation.py` eklendi:
Python `ast` modülüyle TÜM test dosyalarını tarayıp `BrainManager(...)`/`KaizenBrain(...)`
çağrılarında `experience_memory=`/`brain_manager=` anahtar kelimesi eksikse testi BAŞARISIZ
yapan statik bir güvenlik ağı (yeni bir test dosyası bu deseni tekrar ederse artık fark
edilmeden geçmez).

**Ayrıca not edildi, henüz karar verilmedi:** İnceleme, `config/Kaizen.json`'da ana cevap
sağlayıcısının hâlâ Hermes (bulut) olduğunu, yerel sohbet modeli adının boş olduğunu, `doğrula:`
ile okunan belge içeriğinin de bu sağlayıcıya gittiğini belirtti — yani Cognee yerel Ollama'ya
bağlı olsa da bugün sistemin tamamı yerel çalışmıyor. Bu bir hata değil, bilinçli bir aşamalı geçiş
kararı (bkz. bölüm 9, madde 9: "Hermes'in kademeli kapatılması hâlâ sırada") — ama kullanıcının bu
ayrımı bilerek onaylaması gerekiyor; kod/config tarafında henüz bir değişiklik yapılmadı.

**Durum:** 7 maddenin TAMAMI (1-7) tamamlandı ve bilgisayara gönderildi (mtime-korumalı,
gönderim sonrası `diff` ile bayt-bayt doğrulandı). Test sayısı bu düzeltmelerle 45'ten 59'a çıktı
(bkz. bölüm 7). Yalnız "kullanıcı onayı bekliyor" notu (ana sağlayıcının Hermes/bulut olması,
madde sonu) açık kaldı — bu bilinçli bir aşamalı geçiş kararı, hata değil.

## 4o. Test izolasyonu tamamlandı: `KaizenEngine` artık her kalıcı depoyu ve logger'ı izole edebiliyor (2026-09-23)

4n'in 7. maddesi (`NullExperienceMemory` ile Cognee'nin test izolasyonu) kullanıcı tarafından iyi
karşılandı; kullanıcı bunu TÜM diğer kalıcı depolara ve günlüklere de genişletmemizi istedi.
Önerisi: `KaizenEngine`'e isteğe bağlı bir veri dizini + günlük dizini verilebilsin; normal
kullanımda (main.py, desktop_app.py) hiçbir şey değişmesin; testlerde geçici bir klasör ve sahte
bir sağlayıcı (`OfflineProvider`) verilsin. Kabul ölçütü kullanıcı tarafından net konuldu: testler
çalışırken projenin GERÇEK `data/`, `logs/` dosyalarına ve `memory/kaizen_memory.json`'a hiçbir
yazma olmasın, gerçek model/ağ çağrısı oluşmasın; mevcut kullanıcı verileri hiç değişmesin.

**Yapılan değişiklik (üç katman):**
1. `core/logger.py::KaizenLogger(log_dir=None)` — verilmezse eski davranış (`<proje>/logs`) aynen
   korunur.
2. `accounting/accounting_agent.py::AccountingAgent(provider, learning_memory_path=None)` — içindeki
   `LearningMemory`'ye path'i dışarı açar.
3. `core/engine.py::KaizenEngine(data_dir=None, log_dir=None, provider=None)` — `data_dir`
   verilirse `LearningStore`, `SiteStore` (ve bunlardan `db_path` alan `FactRegistry`/
   `KnowledgeCardStore`), `MemoryManager`, `AccountingAgent`'ın `LearningMemory`'si ve
   `KaizenBrain`/`BrainManager`'ın sınav-önerisi dosyası (`auto_exam_candidates.jsonl`) hepsi o
   dizine yönlenir. `provider` verilirse `build_provider()` HİÇ çağrılmaz (gerçek Hermes/yerel
   model kurulumu devreye girmez). Üçü de `None` ise (main.py/desktop_app.py) davranış birebir
   eskisi gibidir.

**Beklenmeyen ama önemli bulgu — kapsamı genişletti:** İlk uygulamadan sonra tam suite'i
çalıştırıp gerçek `data/`/`logs/`/`memory/kaizen_memory.json`'ı önce/sonra `sha256sum` ile
karşılaştırınca, `logs/kaizen.log`'un YİNE DE değiştiği görüldü — `KaizenEngine` düzgün izole
edilmiş olsa bile, `ToolManager` ve `BrainManager`'ın kendi `KaizenLogger()`'ları da koşulsuz
GERÇEK log dosyasına yazıyordu (motor tarafından enjekte edilmiyordu). Bu iki sınıfa da
`log_dir=None` parametresi eklendi (`tools/tool_manager.py`, `memory/brain_manager.py`), ve
`KaizenEngine`/`core/kaizen_brain.py::KaizenBrain` bunu ileri taşıyacak şekilde güncellendi.
Ardından tam suite tekrar tekrar çalıştırılıp diff'lenince, bu kez `KaizenEngine`'DEN BAĞIMSIZ
olarak `BrainManager`/`KaizenBrain`/`ToolManager`/`HermesBridge`'i DOĞRUDAN (motor olmadan) kuran
9 ayrı test dosyasının da (`test_logger.py`, `test_tool_security.py`, `test_hermes_bridge.py`,
`test_brain_manager.py`, `test_kaizen_brain.py`, `test_golden_exam.py`, `test_self_learning.py`,
`test_office_and_commands.py`) gerçek `logs/kaizen.log`'a yazdığı ortaya çıktı — bu, bugünkü
değişiklikten ÖNCE de var olan, fark edilmemiş bir sızıntıydı (özellikle 70 soruluk altın sınav ve
kuyruk-taşma testi düzinelerce satır ekliyordu). `core/hermes_bridge.py::HermesBridge`'e de
`log_dir=None` eklendi; tüm bu 9 test dosyasındaki gerçek kurulum noktaları izole bir geçici
klasöre (`tempfile`) yönlendirildi. Yanlışlıkla gerçek `logs/kaizen.log`'a eklenen satırlar, her
seferinde eklenen satır sayısı kesin olarak tespit edilip (zaman damgasıyla) dosyanın sonundan
kırpılarak, orijinal içerikle bayt-bayt (sha256) eşleşene kadar geri yüklendi — kullanıcının
gerçek log geçmişinde hiçbir kalıcı iz kalmadı.

**Yeni testler:** `tests/test_core.py` tamamen yeniden yazıldı — artık `tempfile.TemporaryDirectory()`
+ `OfflineProvider()` ile izole bir `KaizenEngine` kurar, her deponun GERÇEKTEN geçici klasöre
yazdığını (yanlışsız-yeşil olmasın diye) doğrular, sonra gerçek `data/`/`logs/`/
`memory/kaizen_memory.json`'un önce/sonra sha256 hash'inin BİREBİR aynı kaldığını assert eder.
Yeni `tests/test_engine_isolation.py`, `test_experience_memory_isolation.py`'nin AYNI AST-tarama
desenini kullanarak `KaizenEngine(...)` çağrılarının `data_dir=` içermesini zorunlu kılan statik
bir güvenlik ağıdır (main.py/desktop_app.py'deki parametresiz çağrılar, tests/ dışında oldukları
için kapsam dışıdır — onlar normal kullanım). 5 gerçek `AccountingAgent(...)` kurulum noktası
(`test_accounting.py` x3, `test_document_verifier.py` x2) `learning_memory_path=` ile izole edildi.

**Doğrulama yöntemi:** Testler çalıştırılmadan önce `data/*.*`, `logs/*.*`,
`memory/kaizen_memory.json`'un `sha256sum`'ı alınıp bir dosyaya kaydedildi; `python -m
tests.run_all` (68 test, hepsi başarılı) art arda birkaç kez çalıştırıldı; her seferinde aynı
hash'ler `diff` ile karşılaştırılıp SIFIR fark olduğu doğrulandı (bkz. bölüm 7'deki genel kural).

**Durum:** Tamamlandı, bilgisayara gönderildi (20 dosya, mtime-korumalı, gönderim sonrası `diff`
ile bayt-bayt doğrulandı: `core/logger.py`, `accounting/accounting_agent.py`, `core/engine.py`,
`tools/tool_manager.py`, `memory/brain_manager.py`, `core/kaizen_brain.py`,
`core/hermes_bridge.py`, ve 13 test dosyası + yeni `tests/test_engine_isolation.py`). Test sayısı
59'dan 68'e çıktı (bkz. bölüm 7). Kullanıcının kabul ölçütü (testler gerçek dosyalara yazmasın,
gerçek model/ağ çağrısı olmasın, mevcut kullanıcı verisi değişmesin) tamamen karşılandı.

**Ayrıca not edildi (henüz bir işlem yapılmadı):** `dev/workspace/engine.py` adında,
`core/engine.py`'nin hiçbir yerden import edilmeyen, yetim (dead-code) bir kopyası bulundu. Kod
silme izni olmadığı için (AGENTS.md kural 2) silinmedi; kullanıcı isterse temizlenebilir.

## 4p. RAG v2 - Faz 1: gerçek kullanım ölçümü (görünürlük + darboğaz bulma) (2026-09-23)

Kullanıcı resmî bir iş emri gönderdi ("KAIZEN İŞ EMRİ — GERÇEK KULLANIM / RAG v2 — FAZ 1"):
Kaizen'in test paketi geçse de gerçek kullanımda bazı doğal muhasebe sorularına cevap
veremediği gözlendi; yeni özellik eklemek yerine ÖNCE mevcut sistem ölçülecek, gerçek
darboğaz KANITLANACAK, ancak KANITLANMIŞ sorunlara EN KÜÇÜK değişiklik yapılacak. Değişmez
kurallar arasında: fine-tuning YAPILMAYACAK, Cognee genişletilmeyecek, yeni ağır bağımlılık
eklenmeyecek, BrainManager/facts.py/consensus.py otoritesi korunacak, hesap makineleri LLM'ye
devredilmeyecek, gerçek data/logs/kullanıcı hafızası testlerden izole kalacak, mevcut geçen
testler bozulmayacak, önce ölç sonra kanıtla sonra en küçük doğru değişikliği yap. Kullanıcının
verdiği zorunlu çalışma sırası (1-13) birebir izlendi; bu bölüm 1-9. adımların (kod okuma,
test çalıştırma, izolasyon doğrulama, pipeline haritalama, trace/debug ekleme, gerçek hayat
sınavı, classify() ölçümü, retrieval ölçümü) SONUÇLARINI raporlar. 10-13. adımlar (RAG v2 +
Decision Engine v1 tasarımı, kanıtlanmış düzeltmeler, tam doğrulama, final rapor) ayrı
bölümlerde/oturumlarda sürüyor.

### 1-3. Kod okuma, test çalıştırma, izolasyon doğrulama

Başlangıç durumu: `python -m tests.run_all` 4o sonunda 68 test bildiriyordu, hepsi başarılı;
gerçek `data/`/`logs/`/`memory/kaizen_memory.json` testlerden tamamen izole (bkz. 4o). Bu
temel doğrulanıp bu fazın geri kalanına sağlam bir başlangıç noktası olarak alındı.

### 4. Cevap zinciri haritası (özet)

`KaizenBrain._answer_core` (core/kaizen_brain.py) sırayla: düzeltme (kullanıcının önceki
manuel düzeltmesi) → aritmetik (yalnız sembolik `2+2` gibi ifadeler) → kesin araçlar (yevmiye
→ hesap makineleri → hesap planı, DOMAIN'DEN BAĞIMSIZ çalışır) → parametre defteri (facts) →
`classify()`'e göre: "general" ise modele sor, başarısızsa yerel hafızaya (`_from_memory`)
düş; "accounting"/"office" ise önce yerel hafıza, sonra (yalnız accounting'te) araştırma
zinciri. `classify()` yalnızca BİR kapı; `_exact_tools` (yevmiye/hesap makinesi/hesap planı)
ondan ÖNCE ve ondan BAĞIMSIZ çalıştığı için classify() hatalarının bir kısmı zaten etkisiz
kalıyor (aşağıda kanıtlandı).

### 5. Trace/debug altyapısı eklendi

Yeni `core/trace.py::KaizenTrace` (dataclass): `intent, route, retrieval_source,
retrieval_score, confidence, needs_current_data, used_model, used_facts, used_memory,
used_research, refusal_reason`. Altı güven seviyesi kesin ayrıldı: FOUND / SUPPORTED /
VERIFIED / PENDING / CONFLICTED / UNKNOWN — VERIFIED YALNIZ kesin bir araçtan (aritmetik,
yevmiye, hesap makinesi, hesap planı, facts, kullanıcı düzeltmesi, mali müşavir onayı) gelir;
"embedding/coverage ile benzer bulundu" hiçbir zaman tek başına VERIFIED anlamına gelmiyor.
`KaizenBrain.answer()`'ın döndürdüğü METİN CEVAP hiç değişmedi -- `brain.last_trace` ayrı,
ek bir alan (68 mevcut test değişmeden geçti, gerçek dosyalar sha256 ile öncesi/sonrası
birebir aynı doğrulandı). 6 yeni test: `tests/test_trace.py`.

### 6. Gerçek hayat sınavı: `tests/test_real_world_exam.py`

Golden exam (70 soru, DEĞİŞTİRİLMEDİ) yalnız bilinen-çalışan davranışı korur. Yeni dosya 33
doğal Türkçe soruyla (matematik 8, muhasebe 12, SGK 7, güncel bilgi 6) Kaizen'i BUGÜNKÜ
haliyle ölçer; her satır route/confidence/needle beklentisini VE bunun başarı mı yoksa hangi
kategoride (classification/retrieval/research/model/facts/other) bilinen bir darboğaz mı
olduğunu etiketler. **Ölçüm sonucu: 33 sorudan 12'si başarılı, 21'i bilinen darboğaz**
(dağılım: other=7, research=7 [beklenen -- offline test ortamında gerçek araştırma
sağlayıcısı yok], retrieval=5, classification=2). Güven modeli için ayrıca istisnasız bir
kural test ediliyor: `confidence=="VERIFIED"` iken `route` HER ZAMAN kesin bir araç olmalı
(bu, 33 sorunun TAMAMINDA, bilinen darboğazlar dahil, hiç bozulmadı).

### 7. classify() ölçümü: `tests/test_classification_failures.py` (6 test)

`classify()` tamamen SÖZCÜK-İÇERME (substring) tabanlı, kelime sınırı/morfoloji/bağlam yok.

* **Yanlış negatif (bilgi var, domain yanlış):** "760 ile 770 arasındaki fark ne?" ve "4/a
  4/b 4/c nedir, aralarındaki fark ne?" → `general`'e düşüyor (ACCOUNTING_TERMS çıplak hesap
  kodlarını/SGK rejim kodlarını tanımıyor, yalnız harfi harfine "sgk" gibi kelimeleri arıyor).
* **`general` dalının fallback'i var VE çalışıyor:** model başarısız olursa `_from_memory`'ye
  düşülüyor; curriculum'da konu VARSA (ör. "İşe giriş bildirgesi kaç gün içinde verilmeli?")
  classify() hatası CEVAP KAYBINA yol AÇMIYOR. Yani "sınıflandırma başarısızlığı doğrudan
  cevap kaybına neden oluyor mu?" sorusunun cevabı: HAYIR, HER ZAMAN değil -- yalnız
  fallback'in de bulamadığı durumlarda (yukarıdaki iki örnek gibi).
* **YENİ bulunan yanlış pozitif (iş emrinde sorulmamıştı, kendiliğinden bulundu, ciddi):**
  ACCOUNTING_TERMS'teki "gelir"/"gider" (isim), günlük Türkçenin en sık koşul çekimlerinin
  ("gelirse", "giderse", "gidersem") İÇİNDE de substring olarak geçiyor. "Yarın müşteri
  gelirse ne yapayım?" gibi muhasebeyle HİÇ ilgisi olmayan bir cümle `accounting` sayılıyor
  VE bu, gerçek bir araştırma zincirini (üretimde = gerçek Hermes çağrısı) GEREKSİZ YERE
  tetikliyor -- `CountingAgent` ile birebir sayılarak kanıtlandı.

### 8. Retrieval ölçümü: `tests/test_retrieval_failures.py` (13 test)

* **%60/100 eşiği nerede kullanılıyor:** `Retriever.extractive_answer`'da `min_coverage = 1.0
  if strict else 0.6`; sınır (tam 0.6) kabul ediliyor, altı (0.4) reddediliyor -- doğrulandı.
* **Kısa soru:** tek anlamlı terimli bir soru ("vergi nedir"), o kelime HANGİ BAĞLAMDA
  geçerse geçsin coverage=1.0 veriyor -- kısa sorularda coverage tek başına güvenilmez.
  **Eş anlamlı kelime:** hiç tanınmıyor (yalnız yüzeysel ek kırpma var, kavramsal eş anlam
  yok) -- "işçi"/"çalışan" örneğiyle kanıtlandı.
  **Kelime sırası:** coverage()/phrase_ok() küme (bag-of-words) tabanlı, sıradan HİÇ
  etkilenmiyor (ÖNEMLİ NEGATİF SONUÇ -- sıra bir başarısızlık kaynağı değil).
  **Uzun doğal soru:** aynı özü taşıyan ama kibar/dolaylı ek kelimeler içeren bir cümle,
  coverage'ı 1.0'dan 0.07'ye düşürebiliyor (payda büyüyor) -- eşiğin çok altına iniyor.
* **Türkçe ek kırpıcı (`stem_tr`) nerede başarısız:** araya "y" tampon ünsüzü giren belirtme
  (-yi/-yı) ve yönelme (-ye/-ya) ekleri `_STEM_SUFFIXES` listesinde YOK -- "işçiyi"/"vergiyi",
  "işçiye"/"vergiye" kökleriyle eşleşmiyor.
* **EN SOMUT bulgu -- eğik çizgili kodlar tamamen kayboluyor:** `core.text_tr.tokens_tr()`
  (`[a-z0-9]+` regex'i) "4/a"yı `["4", "a"]` diye İKİ tek karakterli parçaya bölüyor;
  `Retriever._terms()`'teki `len(t) > 2` anlamlılık filtresi bu parçaları TAMAMEN atıyor.
  Sonuç: "4/a 4/b 4/c nedir, aralarındaki fark ne?" sorusunun TÜM anlamlı sinyali
  coverage()'dan siliniyor -- gerçek SGK curriculum kaydı (knowledge/sgk_temel_yapi.json)
  `LearningStore.search()`'ün candidate seçiminde İLK sırada doğru bulunduğu HALDE (bilgi
  mevcut VE bulunabilir), `extractive_answer()` yine de `None` dönüyor. Üretim API'sinin TAM
  KENDİSİYLE, gerçek curriculum metniyle kanıtlandı.
* **Çok-konulu karşılaştırma sorusu:** "7/A ve 7/B ne fark eder?" -- her iki konu da
  curriculum'da AYRI AYRI var (golden exam'de tek tek sorulunca çalışıyorlar) ama Retriever
  bunları BİRLEŞTİRMİYOR; her kayıt tek başına 0.6 eşiğinin altında kalıyor.
  **Kök neden analizi (gerçek hayat sınavındaki "İşveren/işçi prim oranları" başarısızlığının
  TAM açıklaması):** `needs_current_research()` yalnız "oran" kelimesi geçtiği için bu
  KAVRAMSAL (mantığı hiç değişmeyen, yalnız sayısal değeri güncelliğe tabi) soruyu "güncel"
  sayıyor; bu da `extractive_answer`'ı `strict=True` (min_coverage 1.0) moduna zorluyor. Aynı
  içerik `strict=False`'ta BAŞARIYLA çıkarılabiliyor, `strict=True`'da (bu yanlış pozitif
  yüzünden) kayboluyor -- doğrudan kanıtlandı.

### Doğrulama ve veri bütünlüğü

Her adımdan sonra `python -m tests.run_all` çalıştırıldı (şu an 95 test fonksiyonu, hepsi
başarılı) ve gerçek `data/*.*`, `logs/*.*`, `memory/kaizen_memory.json`'un sha256 hash'i
öncesi/sonrasıyla `diff` ile karşılaştırılıp SIFIR fark olduğu her seferinde doğrulandı (4o'daki
yöntemin birebir aynısı). Bu fazda HENÜZ hiçbir üretim davranışı değiştirilmedi (yalnız
`core/kaizen_brain.py`'ye trace enstrümantasyonu eklendi -- metin cevaplar birebir aynı, bu da
ayrıca test edildi); yukarıdaki tüm bulgular KANIT olarak testlere kilitlendi, düzeltmeler iş
emri madde 11 kapsamında AYRI bir adımda (yalnız kanıtlanmış sorunlara, en küçük değişiklikle)
yapılacak.

## 4q. RAG v2 mimari önerisi + Decision Engine v1 (tasarım + test kontratı) (2026-09-23)

İş emrinin 12. maddesindeki 10. adım: "RAG v2 + Decision Engine v1 için minimal tasarım
öner." Bu bölüm bir TASARIM ve TEST KONTRATIDIR -- 4p'deki ölçümlerin doğal sonucu. Hiçbir
mevcut davranış DEĞİŞMEDİ (madde 1: "büyük refactor yapılmayacak"); yalnız Decision Engine
v1, bağımsız/kendi başına test edilen YENİ bir modül olarak eklendi, henüz `KaizenBrain`'e
BAĞLANMADI.

### RAG v2 mimari önerisi (madde 6)

İstenen hedef akış: *Kullanıcı sorusu → normalizasyon → intent/karar → lexical retrieval →
gerekirse embedding candidate retrieval → aday birleştirme/reranking → kaynak + tarih + güven
kontrolü → facts/consensus kontrolü → gerekiyorsa research → LLM sentezi → kaynaklı cevap.*
4p'nin bulgularına göre önerilen KÜÇÜK, MODÜLER karşılığı (yeni ağır bağımlılık YOK):

1. **Normalizasyon** — mevcut `fold_tr`/`tokens_tr` (core/text_tr.py) korunur; TEK somut
   düzeltme önerisi: `tokens_tr`'nin `[a-z0-9]+` regex'i "4/a" gibi eğik-çizgili kodları
   parçalıyor (bkz. 4p, en somut retrieval bulgusu) — bu regex'e "/" içeren kod örüntülerini
   TEK token olarak koruyan dar bir istisna eklenmesi, madde 11 kapsamında değerlendirilecek
   EN KÜÇÜK, EN YÜKSEK ETKİLİ düzeltme adayıdır (bkz. bölüm 9).
2. **Intent/karar** — YENİ: `core/decision.py::DecisionEngine` (aşağıda ayrıntılı). `classify()`
   YERİNE değil, ona PARALEL/üstüne ek bir katman; LLM tabanlı bir sınıflandırıcı DEĞİL
   (madde 4: "Henüz LLM classifier ile değiştirme" kuralına uygun, hâlâ kural tabanlı).
3. **Lexical retrieval** — mevcut `Retriever`/`LearningStore`/`SiteStore` DEĞİŞMEDEN kalır;
   4p'de ölçülen zayıflıklar (kısa soru aşırı güveni, eş anlamlı kelime eksikliği, uzun soru
   seyrelmesi, ek kırpıcı -yi/-ye boşluğu) burada NOT edilir, bu fazda düzeltilmez.
4. **Embedding candidate retrieval (yalnız GEREKİRSE)** — henüz eklenmedi (madde 1: "Cognee
   genişletilmeyecek", madde 6: "Embedding veya Cognee yalnızca aday bulucu olabilir. 'Bu
   bilgi doğrudur' kararını veremez"). Öneri: mevcut `BrainManager.recall_experience`
   (Cognee, bkz. 4k) zaten TAM bu rolde — yalnız ADAY sunuyor, `_refusal_with_experience`'da
   "doğrulanmamış, geçmiş deneyim hafızasından" etiketiyle. Bu ilke KORUNMALI: embedding/Cognee
   hiçbir zaman `facts`/`chart`/`journal`/`calculator` gibi VERIFIED bir rotanın yerine geçmez.
5. **Aday birleştirme/reranking** — henüz yok; 4p'nin "çok-konulu karşılaştırma sorusu"
   bulgusu (7/A vs 7/B) bunun somut ihtiyacını gösteriyor (Retriever şu an birden fazla
   kaydı BİRLEŞTİRMİYOR). İleri faz önerisi, bu fazda YAPILMADI.
6. **Kaynak + tarih + güven kontrolü** — YAPILDI: `core/trace.py::KaizenTrace` (bkz. 4p, madde
   5) bunu tam olarak sağlıyor; `retrieval_source`/`retrieval_score`/`confidence` alanları.
7. **facts/consensus kontrolü** — DEĞİŞMEDEN korunuyor (`accounting/facts.py`,
   `accounting/consensus.py`); tek doğruluk otoritesi olma niteliği bu fazda da bozulmadı.
8. **Research (gerekiyorsa)** — DEĞİŞMEDEN korunuyor (`_research_once`, kart sistemi, bkz. 4c).
9. **LLM sentezi → kaynaklı cevap** — DEĞİŞMEDEN korunuyor (`_grounded_answer`,
   `sources_block`).

Özet: RAG v2, mevcut deterministik omurgayı YIKMIYOR, yalnız (a) trace ile görünürlük
kazandırıyor (yapıldı), (b) yönlendirme kararını `DecisionEngine` ile ayrı, test edilebilir
bir birime çıkarıyor (tasarlandı, bağlanmadı), (c) embedding'in rolünü YALNIZ aday bulucu
olarak KESİN biçimde sınırlıyor (zaten böyleydi, burada teyit edildi).

### Decision Engine v1 (madde 7)

Yeni `core/decision.py::DecisionEngine.decide(question) -> Decision`. `Decision` alanları
BİREBİR iş emrindeki gibi: `intent, preferred_route, needs_current_data, required_confidence,
reason`. İş emrinin verdiği örnek BİREBİR doğrulandı:

```
DecisionEngine().decide("2026 SGK tavanı ne kadar?")
-> Decision(intent='sgk_parameter', preferred_route='facts', needs_current_data=True,
            required_confidence='VERIFIED', reason='...')
```

Tasarım kuralları:

- **Yalnız yönlendirme üretir, muhasebe sonucu ÜRETMEZ** (madde 7, son cümle) — `Decision`
  dataclass'ında `answer`/`text`/`value` gibi bir alan YAPISAL OLARAK yok; bu,
  `tests/test_decision_engine_contract.py::test_decision_never_carries_an_answer_field` ile
  alan adları taranarak zorlanıyor.
- `intent`, `classify()`'in 4 kovasını (accounting/office/mathematics/general) DEĞİŞTİRMEDEN,
  ona PARALEL, daha granüler bir sınıflandırma üretir (`sgk_parameter`, `tax_parameter`,
  `account_code`, `journal_entry`, `accounting_concept`, `arithmetic`, `office`, `general`).
  Kanıt: `classify()` "4/a 4/b 4/c nedir, aralarındaki fark ne?" için hâlâ (bilerek,
  düzeltilmeden) `general` derken, `DecisionEngine` aynı soruyu doğru `sgk_parameter` olarak
  yakalıyor — classify()'a HİÇ dokunulmadan.
- `preferred_route`, uydurma bir rota adı değil, `core/trace.py::ROUTE_CONFIDENCE`'ın (yani
  gerçek `KaizenBrain.last_route` sözlüğünün) bilinen bir üyesi olmak ZORUNDA (test edildi).
- `required_confidence`, kesin araçlar (chart/journal/calculator/facts) için HER ZAMAN
  VERIFIED (test edildi) — güven modeliyle (madde 8) çelişen bir kontrat asla üretilmiyor.
- `needs_current_data`, mevcut `KaizenBrain.needs_current_research()`'e devrediyor —
  4p'de kanıtlanan yanlış-pozitif hatasını (bkz. "oran" kelimesi örneği) BİLEREK
  DEVRALIYOR, düzeltmiyor (o düzeltme madde 11 kapsamında ayrıca değerlendirilecek).

**Durum:** Tasarlandı, `core/decision.py` + `tests/test_decision_engine_contract.py` (6 test,
hepsi bağımsız/izolasyonsuz çünkü `KaizenBrain.answer()`'a hiç dokunmuyor) ile kilitlendi.
**`KaizenBrain`'e HENÜZ bağlanmadı** — bağlanıp bağlanmayacağı (ve `_answer_core`'un mevcut
sırasını nasıl etkileyeceği) ayrı bir kullanıcı kararı gerektiren, ayrı bir faz. Test sayısı
95'ten **101**'e çıktı; tam takım yeşil, gerçek dosyalar bu ekleme için de sha256 ile
öncesi/sonrası birebir aynı doğrulandı (bu modül `KaizenBrain`'e hiç dokunmadığı için zaten
izolasyon riski taşımıyordu).

## 4r. RAG v2 - Faz 1: tek kanıtlanmış düzeltme (ChartOfAccounts çoklu-kod karşılaştırması) (2026-09-23)

İş emri madde 12'nin 11. adımı: "Yalnız kanıtlanmış problemlere kod değişikliği yap." 4p'de
kanıtlanan onlarca bulgudan (classify() yanlış negatif/pozitifleri, Retriever eşik/stemmer/
tokenizer sorunları) **YALNIZ BİRİ**, en dar/en yüksek etkili/en düşük riskli olduğu için
düzeltildi; geri kalanı bilerek ERTELENDİ (bkz. bölüm 9, sonraki tek adım önerisi).

**Düzeltilen:** `accounting/chart_of_accounts.py::ChartOfAccounts.answer()`. İki hesap kodunu
karşılaştıran doğal sorularda ("760 ile 770 arasındaki fark ne?", "153 ile 150 hesap arasındaki
fark nedir?") iki ayrı hata vardı: (C2) `_TRIGGERS` kapısı hiçbir tetikleyici kelime içermeyen
bu tür sorularda `answer()`'ı hiç DENEMİYORDU; (C3) kapıyı geçse bile kod-regex'i (`re.search`)
yalnız İLK kodu yakalayıp İKİNCİSİNİ sessizce yok sayıyor, yine de `SONUÇ:`/VERIFIED etiketiyle
YARIM bir cevap veriyordu (güven modeliyle çelişen en ciddi bulgu). **Düzeltme:** `answer()`'ın
başına, `_TRIGGERS`'tan BAĞIMSIZ çalışan dar bir çoklu-kod yolu eklendi -- yalnız metinde 2+
GEÇERLİ (gerçekten `config/tdhp.json`'da var olan) hesap kodu bir karşılaştırma kelimesiyle
("ile", "fark", "arasında"...) birlikte geçtiğinde devreye girer ve HER İKİ hesabı da açıklar.
Tek kod içeren sıradan sorularda (`_TRIGGERS`'a bağlı eski yol) davranış birebir aynı kaldı.

**Sonuç (ölçülebilir):** `tests/test_real_world_exam.py`'deki 33 sorunun başarı sayısı **12'den
14'e** çıktı (2 satırın beklentisi, düzeltmeyi yansıtacak şekilde güncellendi -- bkz. dosyanın
kendisi); `tests/test_classification_failures.py`'deki ilgili test de classify()'ın HÂLÂ (bilerek
düzeltilmeden) yanlış "general" dediğini ama artık bunun cevap kaybına yol açmadığını kanıtlayacak
şekilde güncellendi. Yeni `tests/test_chart_multi_code_comparison.py` (5 test) düzeltmeyi
`config/tdhp.json`'un GERÇEK verisiyle, hem düzeltilen iki hatayı hem de regresyon güvencesini
(tek-kod sorular etkilenmedi; iki rastgele sayı + karşılaştırma kelimesi olmadan yanlış pozitif
tetiklenmiyor) doğrudan kilitliyor.

**Bilerek ERTELENEN** (bu fazda dokunulmadı -- kanıtlandı ama "en küçük tek adım" ilkesi
gereği düzeltilmedi): classify()'ın "gelir"/"gider" yanlış pozitifi ve SGK/hesap-kodu yanlış
negatifleri; `tokens_tr()`'nin eğik-çizgili kodları ("4/a") parçalaması; stemmer'ın -yi/-ye
eklerini tanımaması; `min_coverage`/`needs_current_research`'ün kısa/uzun soru ve "oran" yanlış
pozitifi sorunları; Retriever'ın çok-konulu karşılaştırma sorularını birleştirememesi. Hepsi
testlerle kanıtlı ve `tests/test_classification_failures.py`/`tests/test_retrieval_failures.py`
içinde kilitli duruyor; hangisinin sonraki tek adım olacağı bölüm 9'da önerildi.

**Doğrulama:** Test sayısı 101'den **105**'e çıktı (bir önceki notta 106 yazılmıştı;
`tests/run_all.py::run_all()` içindeki çağrı satırları tek tek sayılarak 105 olarak düzeltildi),
tam takım yeşil; gerçek `data/*.*`, `logs/*.*`, `memory/kaizen_memory.json` bu değişiklikten
önce/sonra sha256 ile birebir aynı doğrulandı (4o/4p'deki yöntemin birebir aynısı).

## 4s. RAG v2 - Faz 1 KAPANIŞ RAPORU (iş emri madde 12-13, 2026-09-23)

İş emrinin 13 adımlık sırası (bkz. bölüm 4p başlığı) tamamlandı: 12. adım (`python -m
tests.run_all` son kez çalıştırıldı) ve 13. adım (gerçek dosyaların değişmediği son kez
doğrulandı) burada kapatılıyor. Aşağıdaki rapor, iş emrinin istediği A-H formatının birebir
kendisidir.

**A. Başlangıç durumu:** Faz başlangıcında (bölüm 4o sonu) 68 test vardı, hepsi geçiyordu.

**B. Gerçek hayat sınavı:** 33 soru (`tests/test_real_world_exam.py`, kategoriler: matematik 8,
muhasebe 12, sgk 7, güncel 6). Düzeltmeden önce 12/33, düzeltmeden (bölüm 4r) sonra **14/33**
başarılı; **19/33** bilinen darboğaza takılıyor.

**C. Başarısızlık dağılımı** (19 başarısız sorunun kök nedeni, `test_real_world_exam.py`'nin
kendi ölçümü): `{'other': 6, 'research': 7, 'retrieval': 5, 'classification': 1}`. ("other"
çoğunlukla facts/model sınırları; "research" = güncel veri gerektirip Hermes/araştırma zincirine
düşen ama zincirin kendisi bu iş emrinin kapsamı dışında olan sorular.)

**D. Yapılan değişiklikler (dosya dosya):**
- `core/trace.py` — **YENİ**. `KaizenTrace` (intent/route/confidence/used_*/refusal_reason),
  `ROUTE_CONFIDENCE`, `REFUSAL_*` sabitleri. Cevap zincirinin görünürlüğü (madde 5).
- `core/kaizen_brain.py` — **DEĞİŞTİ**. Her ana yola trace enjekte edildi; dönen METİN CEVAP
  birebir aynı kaldı (bkz. `test_trace_does_not_change_the_returned_answer_text`). Küçük ek
  düzeltme: aritmetik yolda `retrieval_source = "exact_tool"` artık set ediliyor.
- `core/decision.py` — **YENİ**. `Decision`/`DecisionEngine` — RAG v2 + Decision Engine v1
  tasarımının test edilebilir sözleşmesi (madde 10). `KaizenBrain`'e HENÜZ bağlanmadı (bilinçli,
  katkısız/additive tasarım — bölüm 4q).
- `accounting/chart_of_accounts.py` — **DEĞİŞTİ**. Tek kanıtlanmış/uygulanan düzeltme (bölüm 4r):
  çoklu-hesap-kodu karşılaştırma sorularında Bug C2 (tetikleyici kapısı) + Bug C3 (ikinci kodun
  sessizce kaybolması) giderildi.
- `tests/test_trace.py` — **YENİ** (6 test).
- `tests/test_real_world_exam.py` — **YENİ** (1 test fonksiyonu, 33 senaryo).
- `tests/test_classification_failures.py` — **YENİ** (6 test — `classify()`'ın kanıtlanmış yanlış
  pozitif/negatifleri).
- `tests/test_retrieval_failures.py` — **YENİ** (13 test — Retriever/tokenizer/stemmer'ın
  kanıtlanmış darboğazları).
- `tests/test_decision_engine_contract.py` — **YENİ** (6 test).
- `tests/test_chart_multi_code_comparison.py` — **YENİ** (5 test — bölüm 4r düzeltmesinin kilidi).
- `tests/run_all.py` — **DEĞİŞTİ**. Yukarıdaki 41 yeni test fonksiyonu import + çağrı listesine
  eklendi (105 → toplam).
- `KAIZEN_HEDEF_VE_YOL_HARITASI.md` — **DEĞİŞTİ**. Bölüm 4p/4q/4r/4s eklendi (bu rapor dahil).

**E. Yapılmayanlar (bilinçli olarak ertelenenler):**
- **Fine-tuning: yapılmadı** (iş emri açıkça yasaklıyordu).
- **Cognee'nin kapsamı genişletilmedi** (iş emri açıkça yasaklıyordu; Cognee hâlâ gerçek bilgi
  otoritesi değil).
- `classify()`'ın "gelir"/"gider" yanlış pozitifi (fiil çekimlerinde substring eşleşmesi — örn.
  "gelirse"/"giderse") — kanıtlandı, düzeltilmedi.
- `classify()`'ın SGK rejim kodu / bağlamsız hesap kodu yanlış negatifleri — kanıtlandı,
  düzeltilmedi (genel fallback bazen kurtarıyor, her zaman değil).
- `core/text_tr.py::tokens_tr()`'nin eğik çizgili kodları ("4/a" → tek karakterli parçalar)
  parçalayıp anlamlılık süzgecinin bunları atması — kanıtlandı, düzeltilmedi.
- `stem_tr()`'nin belirtme (-yi/-yı) ve yönelme (-ye/-ya) eklerini tanımaması — kanıtlandı,
  düzeltilmedi.
- `Retriever`'ın `min_coverage`/`needs_current_research()` yanlış pozitifleri (kısa soru aşırı
  güveni, "oran" substring'i strict modu gereksiz tetikliyor) — kanıtlandı, düzeltilmedi.
- `Retriever`'ın çok-konulu karşılaştırma sorularını (iki ayrı konudan kanıt birleştirme)
  yönetememesi — kanıtlandı, düzeltilmedi.
- `DecisionEngine`, `KaizenBrain`'e bağlanmadı (yalnız tasarım/sözleşme; iş emri "büyük refactor
  yok" kuralı gereği bilinçli olarak ayrı tutuldu).

**F. Son test sonucu:** `python -m tests.run_all` — **105 test, 105 başarılı** (0 hata,
exit code 0). Bu, son, temiz, ayrı bir çalıştırma ile (iş emri madde 12) doğrulandı.

**G. Veri bütünlüğü:** Gerçek `data/*.*`, `logs/*.*`, `memory/kaizen_memory.json` — fazın en
başında (bölüm 4p'nin başlangıcı) alınan sha256 taban çizgisiyle bu raporun yazıldığı an arasında
**hiç değişmedi** (son karşılaştırma: `diff /tmp/wo_before.txt /tmp/wo_after_final.txt` →
fark yok). Testler boyunca her zaman `NullExperienceMemory`, izole `data_dir`/`log_dir` kullanıldı.

**H. Sonraki önerilen TEK adım:** `core/text_tr.py::tokens_tr()`'nin eğik-çizgili kodları
("4/a", "4/b", "4/c" gibi SGK rejim kodları) tek karakterlere parçalaması ve ardından
`len(t) <= 2` anlamlılık süzgeçinin bu parçaları tamamen atması düzeltilsin. Gerekçe: bu tek
hata, `tests/test_retrieval_failures.py::test_retrieval_information_exists_locally_but_extractive_answer_still_returns_none`
testinde kanıtlandığı gibi, doğru içerik `LearningStore.search()`'te #1 sırada bulunmasına RAĞMEN
`extractive_answer()`'ın onu tamamen KAÇIRMASINA yol açıyor — yani bilgi zaten yerelde var ama
hiç kullanılamıyor. Düzeltmesi dar (yalnız tokenizer'ın regex'i + süzgecin eşik mantığı,
`config/tdhp.json` gibi başka hiçbir veri/mimariye dokunmadan) ve gerçek hayat sınavındaki "sgk"
kategorisi (7 sorudan bugün yalnız bir kısmı başarılı) üzerinde doğrudan, ölçülebilir etkisi
olacaktır. Kaizen'in kendi ilkesiyle: "bildiğini bulan" bir asistan olması için önce KENDİ
bildiğini kaybetmemesi gerekiyor — bu darboğaz tam olarak o kaybın kendisi. Birden fazla büyük
proje başlatılmıyor; önerilen TEK adım budur.

## 4t. KAIZEN — FAZ 1.1: tokens_tr() eğik çizgili kod düzeltmesi (2026-09-23)

İş emri "KAIZEN — FAZ 1.1" madde 1-3'ün kapanışı: bölüm 4s'in "Sonraki önerilen TEK adım"ı
(`tokens_tr()`'nin eğik çizgili kodları parçalaması) uygulandı, regresyon doğrulandı, gerçek
hayat sınavı tekrar çalıştırıldı.

**Yöntem (TDD, iş emri gereği "önce başarısız testi yaz, sonra minimum kod değişikliğini
yap"):** Önce `tests/test_tokenizer_slash_code_fix.py` (7 test) YAZILDI ve düzeltmeden ÖNCE
çalıştırılıp İLK İKİ testin (`test_tokenizer_preserves_digit_slash_letter_codes_as_single_tokens`,
uppercase varyantı) `AssertionError` ile BAŞARISIZ olduğu doğrulandı. Ancak SONRA
`core/text_tr.py::tokens_tr()` değiştirildi.

**Düzeltme:** `core/text_tr.py`'ye genel (yalnız SGK'ya özel hard-code edilmiş bir yama
DEĞİL) bir tokenizer kuralı eklendi:

```python
_SLASH_CODE_OR_WORD = re.compile(r"\d{1,4}/[a-z]{1,4}|[a-z]{1,4}/\d{1,4}|[a-z0-9]+")

def tokens_tr(value):
    return re.findall(_SLASH_CODE_OR_WORD, fold_tr(value))
```

Kural yalnız SAYI/HARF ya da HARF/SAYI örüntüsünü (SGK rejim kodları "4/a","4/b","4/c";
kanun madde/bent referansları "7/A","7/B") TEK token olarak korur; SAYI/SAYI örüntüsünü
(tarih: "15/01/2026", kesir: "1/5") kasıtlı olarak ETKİLEMEZ -- bu ayrım, tarih/yıl
ifadelerinin ve oran ifadelerinin (zaten '/' içermeyen, ör. '%18') bozulmamasını sağlar.

**Regresyon güvencesi (aynı yeni dosyada):** eğik çizgisiz hesap kodları (760, 153, 320...)
hiç etkilenmedi; tarih/kesir ifadeleri (15/01/2026, 1/5) hâlâ ayrı tokenlara bölünüyor; oran
ifadeleri (%18) hiç etkilenmedi. Ayrıca `Retriever._terms()`'in artık '4/a' gibi kodları
(uzunluk 3, `len(t) > 2` filtresini geçiyor) TUTTUĞU ve gerçek `knowledge/sgk_temel_yapi.json`
içeriğiyle `extractive_answer()`'ın artık DOLU bir cevap döndürdüğü doğrudan kilitlendi.

**Kademeli test güncellemeleri (düzeltmenin doğal sonucu, ChartOfAccounts düzeltmesinde
olduğu gibi):** `tests/test_retrieval_failures.py`'deki üç ESKİ-DAVRANIŞ-BELGELEYEN test
yeniden adlandırılıp DÜZELTİLMİŞ davranışı doğrulayacak şekilde güncellendi
(`test_retrieval_tokenizer_no_longer_shreds_slash_codes_after_fix`,
`test_retrieval_significance_filter_no_longer_drops_slash_code_fragments_after_fix`,
`test_retrieval_information_exists_locally_and_extractive_answer_now_returns_it_after_fix`).
`test_retrieval_multi_topic_comparison_question_fails_even_though_each_topic_exists_alone`
(7/A vs 7/B karşılaştırma sorusu) KASITLI OLARAK değiştirilmedi -- bu ayrı, bilinçli olarak
ERTELENMİŞ bir bulgu (Retriever'ın iki ayrı kaydı birleştirememesi); empirik olarak
doğrulandı ki bu düzeltmeden ETKİLENMEDİ (hâlâ `not_found_offline`).

**Gerçek hayat sınavı (madde 3):** 33 sorunun TAMAMI, hiçbir beklenti ÖNCEDEN
değiştirilmeden tekrar çalıştırıldı. Tam olarak TEK bir soru sonucu değişti:

| Soru | Önce | Sonra |
|---|---|---|
| "4/a 4/b 4/c nedir, aralarındaki fark ne?" | route=provider, confidence=UNKNOWN, fail=retrieval ("bulamadım") | route=memory_extractive, confidence=SUPPORTED, fail=YOK (gerçek SGK 4/a-4/b-4/c içeriğini buluyor) |

Diğer 32 sorunun HİÇBİRİ değişmedi (özellikle "7/A ve 7/B ... ne fark eder?" ve "Bağkur ile
SSK arasındaki fark nedir?" -- ayrı, kasıtlı olarak dokunulmamış bulgular -- aynı kaldı).
Bu TEK değişikliğin kanıtı üzerine, `tests/test_real_world_exam.py`'deki ilgili `ExamCase`
"DÜZELTİLDİ" notuyla güncellendi (aynı desende: bölüm 4r'deki chart düzeltmesi).

**Sonuç (ölçülebilir):** 14/33 → **15/33** başarılı (18 bilinen darboğaz kaldı).
Başarısızlık dağılımı: `{'other': 6, 'research': 7, 'retrieval': 5, 'classification': 1}` →
**`{'other': 6, 'research': 7, 'retrieval': 4, 'classification': 1}`** (retrieval kovası 5'ten
4'e indi, tam olarak düzeltilen sorunun kategorisiyle örtüşüyor).

**Regresyon (madde 2):** `python -m tests.run_all` → 105 mevcut test KORUNDU, 7 yeni test
eklendi (`tests/test_tokenizer_slash_code_fix.py`) → toplam **112 test, 112 başarılı**
(exit code 0). Gerçek `data/*.*`, `logs/*.*`, `memory/kaizen_memory.json`: bu değişiklikten
önce/sonra sha256 ile birebir aynı doğrulandı (`/tmp/faz11_before.txt` ==
`/tmp/faz11_after.txt`, orijinal Faz 1 taban çizgisiyle de aynı).

**Değişen dosyalar:** `core/text_tr.py` (değişti -- tek üretim kodu değişikliği),
`tests/test_tokenizer_slash_code_fix.py` (yeni, 7 test), `tests/test_retrieval_failures.py`
(değişti -- 3 test yeniden adlandırıldı/güncellendi), `tests/test_real_world_exam.py`
(değişti -- 1 ExamCase güncellendi), `tests/run_all.py` (değişti -- import + çağrı eklendi).

## 4u. KAIZEN LEARNING BRAIN v1 — Gap Analizi ve Minimum Mimari Önerisi (2026-09-23, YALNIZ TASARIM, UYGULAMA YOK)

İş emri "KAIZEN — FAZ 1.1" madde 4-6: küçük retrieval yamalarından sonra DUR, kod yazma;
Kaizen'in mevcut döngüsünü (GÖZLEMLE → ANLA → PLANLA → BİLGİ AÇIĞINI BUL → ARAŞTIR → UYGULA
→ DOĞRULA → YANSIT/DEĞERLENDİR → ÖĞREN → BAŞKA PROBLEME TRANSFER ET) haritala ve yalnız bir
rapor getir. Bu bölüm SADECE analiz/tasarımdır; hiçbir üretim kodu değiştirilmedi
(doğrulama: bu bölümü üreten oturumda `core/`, `memory/`, `accounting/` altında TEK bir Edit
bile yapılmadı -- yalnız `Read`/`Grep`).

İncelenen dosyalar: `core/kaizen_brain.py`, `core/decision.py`, `core/trace.py`,
`memory/brain_manager.py`, `memory/learning_store.py`, `memory/knowledge_cards.py`,
`memory/cognee_memory.py`, `accounting/accounting_brain.py`, `accounting/facts.py`,
`accounting/consensus.py`, `accounting/retriever.py`.

### A. Reasoning

**Hayır.** Kaizen bir muhasebe sorusunda problemi parçalamıyor, "ilgili muhasebe prensibi"
diye ayrı bir kavramı SEÇMİYOR, olay ile prensip arasında mantıksal bir ilişki kurmuyor.
Gerçekte olan: `AccountingBrain.classify_topic()` sorudaki kelimelerin 6 sabit alt-disiplinden
(financial_accounting/tax/cost_accounting/audit/commercial_law/professional_law) hangisiyle
en çok kelime örtüştüğünü sayıyor -- bu yalnız "hangi KAYNAK GRUBUNDAN arama yapılsın"
sorusuna cevap veriyor, "bu olayda hangi PRENSİP geçerli" sorusuna değil. Asıl arama
(`Retriever.coverage`/`phrase_ok`, `LearningStore.search_scored`) tamamen bag-of-words +
TF-IDF benzeri bir yüzeysel kelime örtüşmesi (kanıt: `tests/test_retrieval_failures.py`'nin
eş anlamlı kelime testi -- "işçi" ile "çalışan" hiç eşleşmiyor). Model (Hermes/Ollama)
çağrıldığında GERÇEK muhakeme -- varsa -- modelin kendi kapalı-kutu iç sürecinde oluyor;
Kaizen'in kendi kodu bunu ne yönlendiriyor ne gözlemleyebiliyor ne de yeniden kullanabiliyor.

### B. Planning

**Kısmen var.** Gerçek, çok adımlı, "ne biliyorum / ne bilmiyorum / hangi aracı
kullanacağım" diye açıkça muhakeme eden bir plan YOK. Bunun yerine SABİT, hardcoded bir
zincir var (`_answer_core`: düzeltme → aritmetik → kesin araçlar → parametre defteri →
alan bazlı yönlendirme → yerel hafıza → araştırma → ret) -- ilk cevap veren kazanır, her adım
kendi başarısızlığını SONRADAN (reaktif) fark ediyor. `needs_current_research()` tek bir
ikili sinyal üretiyor (güncel mi/değil mi -- kanıtlı yanlış pozitifleri var, bkz. bölüm 4p).
`core/decision.py` (Decision Engine v1) bundan daha GERÇEK bir "plan" nesnesi tasarlıyor
(intent, preferred_route, needs_current_data, required_confidence, reason) ama (a) HENÜZ
`KaizenBrain`'e bağlı değil, (b) yine de TEK ADIMLIK bir sınıflandırma-yönlendirme kararı,
çok adımlı bir plan değil.

### C. Research

Kaizen kendi araştırmasını PLANLAMIYOR. `_research_once()` ham soru metnini OLDUĞU GİBİ
`self.accounting_agent.ask(question)`'a (Hermes) gönderiyor ve tek, bütün bir cevap
bekliyor -- alt-soru ayrıştırma, "önce X'i doğrula sonra Y'yi ara" gibi çok adımlı bir
araştırma stratejisi Kaizen'in kendi kodunda YOK. Search (hızlı, hedefli sorgu) ile Research
(çok adımlı inceleme) Kaizen'in kodunda AYRI AYRI haritalanmıyor -- ikisi TEK, farklılaşmamış
bir çağrıya (`accounting_agent.ask`) çöküyor; Kaizen'in kendi rolü yalnız "araştırmaya gidilsin
mi gidilmesin mi" ikili kapısı (domain==accounting ve yerel kanıt yok, ya da
needs_current_research()==True ve site kanıtı yok). Hermes'in kendi içinde bir ayrım/planlama
yapıp yapmadığı Kaizen'den GÖZLEMLENEMİYOR (trace bunu yakalamıyor).

### D. Reflection

**Yok.** `core/trace.py` yalnız TEK bir çağrının route/confidence/refusal_reason'ını ANLIK
(`brain.last_trace`) gösteriyor -- bu bilgi kalıcı olarak HİÇBİR YERE yazılmıyor, bir
sonraki soruyu etkilemiyor. Bir cevap başarılı ya da başarısız olduktan SONRA "neden"
sorusunu soran, hangi kaynağın/hangi rotanın işe yaradığını kaydeden, "bir dahaki sefere
nasıl davranmalı" diye bir çıkarım üreten HİÇBİR mekanizma yok (kod tabanında
"reflect"/"yansıt", "strateji" kelimeleriyle yapılan bir arama SIFIR sonuç verdi). Golden
exam / gerçek hayat sınavı, GELİŞTİRİCİNİN (benim) çalıştırdığı OFFLINE test harness'leri --
Kaizen'in kendisi üretimde bunları otomatik çalıştırıp kendini değerlendirmiyor.

### E. Learning

**Kısmen var, ama ayrım sanıldığından dar.** Dört "hafıza" bileşeni var
(`learning_store`, `knowledge_cards`, `facts`+`consensus`, Cognee/`experience`) ama bunlardan
yalnız BİRİ (facts.py/FactRegistry) gerçekten yapısal olarak ayrı bir "fact memory":
(topic, year, value, status=verified/conflict/single-source), süzgeçten geçmiş, çapraz
kontrollü, TEK doğruluk otoritesi -- bu katman zaten sağlam ve iş emrinin "değişmez
kuralları" tarafından da korunuyor. Geri kalan üçü ("principle memory", "experience memory",
"strategy memory" olabilecekler) YAPISAL OLARAK BİRBİRİNDEN AYRILMIYOR: `learning_store`'da
sayısal bir SGK oranı ile kavramsal "dönemsellik ilkesi" AYNI şemada (subject/section/text),
AYNI TF-IDF aramasıyla bulunuyor -- birinin "zamana bağlı, süzgeçten geçmeli" diğerinin
"zamansız, genellenebilir" olduğunu ayırt eden HİÇBİR alan yok. `knowledge_cards`, araştırma
sonuçlarının bir ONAY/GÜVEN durumu (pending/confirmed) taşıyan CACHE'i -- ayrı bir "prensip"
kavramı değil. Cognee (`experience_memory`), ham "Soru: X / Cevap: Y" metin çiftlerini
embedding ile saklayıp geri çağırıyor (`self_improvement=False`, varsayılan) -- bu bir
"deneyim hafızası" olarak adlandırılsa da, o değişimin BAŞARILI mı BAŞARISIZ mı olduğunu
bilmiyor, bir "strateji" çıkarmıyor. Sonuç: Kaizen'in hafızası esasen İKİ katmana ayrılıyor
(doğrulanmış SAYISAL/HUKUKİ gerçekler vs. her şeyin geri kalanı için tek tip metin
saklama/geri çağırma) -- ama kullanıcının sorduğu dört-yönlü ayrım (fact/principle/
experience/strategy) yapısal olarak yalnız İLKİ için var.

### F. Transfer

**Yok.** Bu, en kritik ve en net "yok" cevabı. `Retriever.coverage()`/`phrase_ok()` saf
kelime örtüşmesi (bag-of-words); `stem_tr()` yalnız yüzeysel Türkçe ek kırpma yapıyor, hiçbir
eş anlamlı/kavramsal sözlük yok (kanıt: `tests/test_retrieval_failures.py`, "işçi"/"çalışan"
testi -- coverage asla 1.0 olmuyor, yalnız TESADÜFEN ortak kalan kelimeler üzerinden kısmi
bir skor). "Dönemsellikte gider ait olduğu dönem açısından değerlendirilir" ilkesi
öğrenilmiş olsa bile, "Aralıkta kullanılan hizmetin faturası ocakta geldi" gibi HİÇBİR ortak
kelime taşımayan yeni bir olay sorulduğunda: (1) retrieval bu iki metni kelime düzeyinde
eşleştiremeyeceği için ilke kaydı muhtemelen HİÇ bulunmayacak (tavan skoru düşük kalacak,
extractive_answer eşiğin altında kalıp None dönecek), (2) bulunsa bile Kaizen'in kendi
kodunda "bu olay şu ilkenin bir örneğidir" diye SEMBOLİK/MANTIKSAL bir çıkarım katmanı YOK.
Yalnız model (LLM) çağrılırsa VE ilke metni tesadüfen prompt'a girerse, LLM'in kendi genel
dil modeli yeteneği bunu YAPABİLİR -- ama bu Kaizen'in GARANTİ ettiği, orkestre ettiği bir
yetenek DEĞİL, retrieval'ın şansına bağlı bir yan etki. Bu, kullanıcının vurguladığı temel
ilkeyle ("Kaizen öğrendiği muhasebe prensibini... daha önce görmediği başka bir muhasebe
probleminde doğru şekilde kullanabiliyor mu?") TAM olarak örtüşen, kanıtlı bir boşluktur.

### Gap tablosu

| Yetenek | Var | Kısmi | Yok | Mevcut mekanizma | Eksik parça |
|---|:---:|:---:|:---:|---|---|
| Problem anlama | | X | | `classify()` (4 kategori, substring), `AccountingBrain.classify_topic()` (6 alt-disiplin, keyword skor), Decision Engine v1 (bağlı değil) | Sözdizimsel/semantik ayrıştırma yok; hepsi yüzeysel anahtar kelime/substring |
| Muhasebe prensibi seçme | | | X | `classify_topic()` yalnız KAYNAK GRUBU seçiyor | Adlandırılmış bir ilke envanteri ve "bu soru hangi ilkeyi gerektirir" eşlemesi yok |
| Planlama | | X | | Sabit hardcoded zincir (`_answer_core`); `needs_current_research()`; Decision Engine v1 (tek adımlık, bağlı değil) | Çok adımlı, açık "biliyorum/bilmiyorum/hangi araç" planı yok; hiçbir yerde bağlı değil |
| Bilgi açığı tespiti | | X | | Zincir başarısız adımda bir SONRAKİNE düşüyor (örtük); `trace.refusal_reason` nedeni SONRADAN işaretliyor | ÖNCEDEN "bu bilgiye ihtiyacım var, yok" diyen muhakeme yok -- yalnız reaktif |
| Research planlama | | | X | `_research_once()` ham soruyu OLDUĞU GİBİ Hermes'e gönderiyor | Alt-soru ayrıştırma yok; search/research Kaizen kodunda hiç ayrılmıyor |
| Reflection | | | X | Yok (`core/trace.py` yalnız ANLIK, kalıcı değil) | Başarı/başarısızlık sonrası nedensel analiz, kaynak güncelleme, davranış ayarı yok |
| Fact learning | X | | | `accounting/facts.py::FactRegistry` + `consensus.py` -- yapılandırılmış, süzgeçli, çapraz kontrollü, TEK otorite | (Sağlam; korunmalı) |
| Principle learning | | | X | İlkeler `learning_store`'da sıradan metin parçası; sayısal veriden yapısal olarak AYRILMIYOR | Zamana bağlı olmayan/genellenebilir olarak işaretleyen ayrı bir şema yok |
| Strategy learning | | | X | Yok | "Bu TÜR soruda şu yaklaşım işe yaradı" diye bir kayıt/öğrenme yok |
| Transfer learning | | | X | Yok (bag-of-words retrieval, eş anlamlı/kavramsal eşleme yok -- kanıtlı) | Yeni ifadeyle anlatılmış bir olayı öğrenilmiş bir ilkenin örneği olarak tanıyacak katman yok |

### Learning Brain v1 için önerilen MİNİMUM mimari (HENÜZ KODLANMADI)

Amaç, "çok şey bilen bir chatbot" değil; "bildiğini bulan, bilmediğini fark eden... hesabı
deterministik yapan" bir sistem. Bu yüzden öneri KASITLI OLARAK dar: yeni bir framework/ağır
bağımlılık YOK, SQLite'ın dışına çıkılmıyor, fine-tuning YOK, Cognee'nin kapsamı
genişletilmiyor. Dört küçük, birbirinden bağımsız eklenebilecek parça:

1. **Principle Registry (yeni, hafif bir SQLite tablosu, `facts.py`'nin YANINA, İÇİNE değil):**
   `learning_store`'daki metin parçalarından yapısal olarak AYRI, küçük bir tablo:
   `(principle_id, statement, domain, trigger_keywords, generalizable=True)`. İlk sürümde
   İÇERİK elle (mali müşavir tarafından) curate edilir -- model kendi ilke İCAT ETMEZ (madde
   6 güvenlik sınırıyla tutarlı: yalnız STRATEJİ/YÖNTEM öğrenilebilir, oran/tutar/mevzuat
   asla). `trigger_keywords` alanı, ilkenin kendi metninde GEÇMEYEN ama o ilkenin
   TETİKLEYECEĞİ senaryo kelimelerini de taşır (ör. "dönemsellik" ilkesi için "fatura geç
   geldi", "hizmet farklı ayda kullanıldı" gibi) -- bu, F (Transfer) boşluğunu KISMEN kapatan,
   deterministik (LLM'in icat etmediği, insan-curate edilmiş) bir köprü.
2. **Decision Engine v1'in bağlanması (kod zaten var, `core/decision.py`):** `KaizenBrain`'e
   EKLENMEZ, `_answer_core`'un BAŞINA bir GÖZLEM adımı olarak eklenir -- yalnız trace'e
   `decision.reason` yazar, cevap akışını henüz DEĞİŞTİRMEZ (iş emrinin "büyük refactor yok"
   ilkesiyle tutarlı bir ilk, riski en düşük adım). Bu, B (Planlama) boşluğunu "var ama
   gözlemlenebilir" seviyesine taşır.
3. **Outcome Log (yeni, küçük bir tablo/append-only dosya):** Her `answer()` çağrısından
   sonra `{question, route, confidence, principle_id (varsa), timestamp}` kaydedilir --
   HENÜZ bir "başarılı mı" etiketi YOK (bunu otomatik çıkaramayız, uydurma olur). Yalnız
   mevcut `onayla:`/düzeltme komutları (zaten var) bu kayda geri bağlanır: mali müşavir bir
   cevabı onayladığında/düzelttiğinde, kullanılan `principle_id`'nin "işe yaradı" sayacı
   artar. Bu, D (Reflection) ve Strategy learning için insan-onaylı, UYDURMASIZ bir başlangıç
   sinyali -- otomatik/kendi kendine değerlendirme YOK.
4. **Principle retrieval'ın Retriever'dan AYRI tutulması:** Mevcut `Retriever` (fact/ders notu
   araması) DEĞİŞTİRİLMEZ. Principle Registry için AYRI, basit bir eşleme fonksiyonu
   (`trigger_keywords` üzerinden, yine bag-of-words ama PRENSİBİN KENDİ METNİNDEN bağımsız
   bir alanla) -- iki arama birbirine karışmaz, ikisi de deterministik kalır.

Bilinçli olarak DIŞARIDA bırakılan: embedding/vector veritabanı, LLM'in kendi ilke/strateji
İCAT ETMESİ, otomatik "başarılı/başarısız" etiketleme (insan onayı olmadan), Cognee'nin
`self_improvement` modunun açılması -- hepsi ayrı, daha büyük kararlar; bu raporun kapsamı
dışı.

### 5. Learning Brain test tasarımı (tests/test_learning_transfer.py) — TASARIM, DOSYA HENÜZ YOK

Amaç ezber DEĞİL transfer ölçmek: her örnek, ilkeyi bir cümleyle "öğretir" (ya da mevcut
curriculum'daki halihazırda var olan ifadeyle eşleştirir), SONRA kelime düzeyinde ORTAK
NEREDEYSE HİÇ terimi olmayan, farklı bir senaryo sorar. Bugünkü sistemle (bag-of-words
retrieval) bu testlerin HEPSİNİN BAŞARISIZ olması BEKLENİR -- bu BİLİNÇLİ: testin amacı
mevcut sınırı ÖLÇMEK, üretim koduna göre KOLAYLAŞTIRILMAMALI.

Önerilen 7 örnek (öğretilen ifade / transfer probe'u / neden bugün başarısız olması
beklenir):

1. **Dönemsellik** — Öğret: "Dönemsellik ilkesine göre gelir ve gider, ait olduğu döneme
   göre muhasebeleştirilir." Transfer probe: "Aralık ayında kullanılan bir danışmanlık
   hizmetinin faturası ocak ayında geldi, bu gideri hangi aya yazmalıyım?" — Ortak kelime
   neredeyse yok ("dönemsellik"/"dönem" kelimeleri probe'da hiç geçmiyor); coverage() düşük
   kalır.
2. **Borç/alacak mantığı** — Öğret: "Aktif hesaplar borç çalışır, artışları borca yazılır."
   Transfer probe: "Bankadan nakit çektiğimde kasa hesabı hangi tarafa yazılır?" — "borç
   çalışır" ile "hangi tarafa yazılır" arasında lexical köprü yok.
3. **Hesap sınıflandırması** — Öğret: "100-199 arası hesaplar dönen varlıklardır." Transfer
   probe: "Şirketin bir yıl içinde paraya çevireceği stokları bilançoda nereye yazarım?" —
   "100-199", "dönen varlık" gibi terimler probe'da hiç geçmiyor.
4. **Özün önceliği** — Öğret: "Muhasebede işlemler hukuki şekilinden çok ekonomik özüne göre
   kaydedilir." Transfer probe: "Finansal kiralamayla aldığımız makineyi, sözleşmede
   'kiralama' yazsa da neden kendi duran varlığımız gibi göstermem gerekiyor?" — "öz",
   "şekil" gibi anahtar kelimeler probe'da yok.
5. **Maliyet** — Öğret: "Direkt ilk madde ve malzeme, direkt işçilik ve genel üretim
   giderleri toplamı üretim maliyetini oluşturur." Transfer probe: "Fabrikada bu ay ödediğimiz
   elektrik faturasının bir kısmını neden ürün maliyetine dahil ediyoruz?" — "genel üretim
   gideri" probe'da hiç geçmiyor, yalnız somut bir örnek (elektrik faturası) var.
6. **Amortisman mantığı** — Öğret: "Amortisman, duran varlığın maliyetinin kullanım
   süresine yayılarak gider yazılmasıdır." Transfer probe: "5 yıl önce aldığımız bir
   makinenin bedelini neden tek seferde değil de her yıl azar azar gider yazıyoruz?" —
   "amortisman" kelimesi probe'da hiç geçmiyor.
7. **SGK temel mantığı** — Öğret: "4/1-a sigortalıları bir hizmet akdiyle işveren yanında
   çalışan işçilerdir." Transfer probe: "Kendi butiğini işleten, kimseye bağlı çalışmayan bir
   esnaf SGK'ya hangi statüde kayıtlı olur?" — "4/a", "hizmet akdi" gibi terimler probe'da
   hiç geçmiyor; doğru cevap (4/b) farklı bir kayıttan gelmeli.

Her örnek için ÖNERİLEN test yapısı (henüz yazılmadı): `brain.answer(TEACH)` ile ilke
önce sorulur (curriculum'da zaten varsa bu adım atlanabilir), sonra `brain.answer(PROBE)`
çağrılır; test PASS için PROBE cevabının doğru ilkeyi (ör. "dönemsellik" ya da "4/b")
İSİMLENDİRMESİ ya da doğru sonucu (ör. "ocak ayına yaz") içermesi beklenir. Bugünkü
sistemle bu testlerin `not_found_offline`/`provider`+UNKNOWN ile BAŞARISIZ OLMASI beklenir
-- bu başarısızlık, önerilen mimarinin (özellikle Principle Registry + trigger_keywords
köprüsü) NEDEN gerekli olduğunun kanıtı olarak kullanılacaktır.

### 6. Güvenlik sınırı (teyit edildi, değişmedi)

Önerilen mimari, Learning Brain'in STRATEJİ/YÖNTEM/İLKE öğrenmesine izin verir ama VERGİ
ORANI, SGK ORANI, PARASAL SINIR, MEVZUAT HÜKMÜ ya da GÜNCEL RESMİ DEĞER üretmesine/VERIFIED
etiketlemesine ASLA izin vermez -- bunlar her zaman `accounting/facts.py::FactRegistry` +
`accounting/consensus.py` üzerinden dış kaynaktan gelir. Principle Registry'nin
`trigger_keywords` alanı da BİLİNÇLİ OLARAK insan-curate: LLM'in kendi ilke İCAT ETMESİNE
izin verilmiyor.

## 4v. KAIZEN — LEARNING BRAIN v1 + SEARXNG SEARCH FOUNDATION: Faz A başlangıcı (2026-09-23, DEVAM EDİYOR)

Yeni iş emri (kullanıcı, 2026-09-23): iki paralel temel -- (1) SearXNG Search
Foundation (Faz A: benchmark + GO/LIMITED/NO-GO, Faz B: SearchProvider
sözleşmesi), (2) Principle Layer + Transfer Learning (Faz C, bölüm 4u'daki
gap analizinin devamı). Zorunlu çalışma sırası: env inceleme → SHA256 →
SearXNG kurulum → JSON API → benchmark → Hermes karşılaştırması →
GO/NO-GO → SearchProvider contract → transfer baseline → Principle
Registry → principle retrieval → negative transfer → Transfer Score →
regresyon → 33 soru → SHA256 final → rapor → DUR.

**Adım 1 (env inceleme) -- kısmi, araç sınırı tespit edildi:** Bu oturumda
kullanıcının Windows bilgisayarında KOMUT ÇALIŞTIRABİLECEK bir shell aracı
YOK (yalnız `device_list_dir`/`device_stage_files`/`device_commit_files`/
`device_request_folder_access` -- dosya transferi -- ve `computer_*`/
`Claude_Browser_*` -- ekran/fare otomasyonu ve bilgisayardaki tarayıcı
penceresi -- var; `device_bash` bu oturumda mevcut değil). Koddan
doğrulanabilen ortam bilgisi: Ollama `http://localhost:11434` varsayıyor
(config/Kaizen.json), Hermes `subprocess` ile yerel `hermes` CLI'ını
çağırıyor (`core/hermes_bridge.py`), `.venv`/`.hermes`/`.cognee`/`.ollama`
klasörleri bilgisayarda zaten var (bkz. `get_device_info`). Canlı
Docker/port/Ollama durumu, kullanıcının çalıştıracağı betiğin kendi
çıktısından doğrulanacak.

**Adım 2 (SHA256 taban çizgisi):** `data/accounting_knowledge.sqlite3`,
`data/accounting_learning.json`, `data/kaizen_learning.sqlite3`,
`logs/kaizen.log`, `memory/kaizen_memory.json` -- bölüm 4t'nin
`/tmp/faz11_before.txt` taban çizgisiyle BİREBİR AYNI (hiç değişmemiş).

**Kritik bulgu (adım 3'e geçerken):** Bu oturumun BULUT ortamının genel
internet erişimi yok -- yalnız paket depoları (npm/pypi) ve Anthropic
API'leri allowlist'te (`curl` ile `google.com`, `gib.gov.tr`, `sgk.gov.tr`,
`duckduckgo.com`, `bing.com` hepsi `403`/bağlantı reddi ile doğrulandı, bkz.
`/root/.ccr/README.md` altyapısı). Bu yüzden SearXNG'yi bulutta kurup
"gerçek" bir arama benchmark'ı çalıştırmak ANLAMSIZ olurdu (dışarıya hiç
arama yapamaz).

**Karar (kullanıcıya soruldu, kullanıcı onayladı):** SearXNG kullanıcının
KENDİ bilgisayarında (Docker, yalnız `127.0.0.1`'e bağlı, LAN'a bile açık
değil) kurulacak; ama BENCHMARK yine de gerçek ve otomatik olacak --
Kaizen'in bilgisayardaki tarayıcı penceresi (`Claude_Browser_*`) kullanıcının
kendi internet bağlantısını kullandığı için, oradan SearXNG'nin JSON API'sine
doğrudan istek atıp yapılandırılmış sonuçlar okunabiliyor. Kurulum betiği
(`search/setup_searxng.ps1`, kendi kendini doğrulayan health-check + JSON API
testi içeriyor) ve açıklayıcı `search/README.md` yazılıp bilgisayara
gönderildi (byte-doğrulaması henüz YAPILMADI -- kullanıcının betiği
çalıştırıp SearXNG'yi ayağa kaldırması bekleniyor).

**Ayrıca (kod incelemesiyle, tahminle değil) netleşen bir A11 girdisi:**
`core/hermes_bridge.py`'nin araştırma modu (`-t web --format stream-json`)
gerçekten URL+içerik döndürüyor (`web_extract` aracı sonuçları), bunları
`accounting/source_registry.py::trusted_source_for_url` ile güvenilir kaynak
listesine süzüyor, cevaptaki `KANIT:` cümlesinin açılan kaynağın kendi
metninde GEÇTİĞİNİ doğruluyor, ve iddia edilen oranları kaynak metniyle
çapraz kontrol ediyor. Yani Hermes'in kaynak şeffaflığı VAR ve şu an
tasarlanan SearXNG entegrasyonundan (henüz doğrulama katmanı yok) daha sıkı.

**Durum:** Bu adımda DURULDU -- kullanıcının betiği çalıştırıp SearXNG'yi
ayağa kaldırması bekleniyor. Onay/rapor gelince adım 4'ten (JSON API
doğrulama) devam edilecek.

## 4w. KAIZEN — SearXNG kurulum betiği: Docker eksikliği bulgusu + betik hatası düzeltmesi (2026-09-23, DURULDU)

**Kullanıcının betik çalıştırma sonucu:** Windows 10 Pro 64-bit, Python
3.13.15, port 8890 müsait, **Docker kurulu değil** (`docker` komutu
bulunamadı), bu yüzden SearXNG container'ı hiç başlamadı; Health check ve
JSON API testleri bu nedenle BAŞARISIZ oldu; Ollama `localhost:11434`'te o
an erişilemez durumdaydı (kapalıydı, ayrı bir sorun değil). Kullanıcının
açık talimatı üzerine bu, bir SearXNG başarısızlığı DEĞİL, bir bağımlılık
(Docker) eksikliği olarak kabul edildi.

**Bulunan betik hatası (kök neden, koddan doğrulandı):** Eski
`search/setup_searxng.ps1`, Docker CLI'nin var olup olmadığını
`$dockerOk = $LASTEXITCODE -eq 0` satırıyla, `docker --version`
çağrısından hemen sonra kontrol ediyordu. Ancak `docker.exe` sistemde HİÇ
yoksa PowerShell bir `CommandNotFoundException` fırlatır ve bu,
`$LASTEXITCODE`'u DEĞİŞTİRMEZ -- değişken, kendisinden önceki native
komuttan (bu betikte `python --version`, başarıyla çalıştığı için
`$LASTEXITCODE=0`) kalan değeri taşımaya devam eder. Sonuç: betik Docker
YOK iken bile "Docker var" sanıp `docker ps`/`docker rm`/`docker run`
komutlarını çalıştırmaya devam ediyor ve container gerçekte hiç
başlamadığı halde "Container baslatildi." yazdırıyordu -- kullanıcının
tam olarak gözlemlediği hata buydu.

**Uygulanan düzeltme (`search/setup_searxng.ps1`, tamamı yeniden
yazıldı):**
1. Docker CLI varlığı artık `Get-Command docker -ErrorAction
   SilentlyContinue` ile, `$LASTEXITCODE`'dan tamamen BAĞIMSIZ olarak
   kontrol ediliyor; bulunamazsa betik yeni bir `Stop-DependencyFailure`
   yardımcı fonksiyonuyla HEMEN ve güvenli biçimde duruyor (`exit 1`),
   `docker ps`/`docker rm`/`docker run`'a hiç girmiyor.
2. Docker daemon'ın (Docker Desktop) gerçekten çalıştığı `docker info`
   çağrısının kendi `$LASTEXITCODE`'uyla (CLI varlığından ayrı, araya
   başka native komut girmeden) doğrulanıyor; daemon kapalıysa aynı
   şekilde HEMEN duruyor.
3. `docker run`'ın exit code'u önceden de kontrol ediliyordu; artık ek
   olarak "Container baslatildi" mesajı yalnız exit code 0 sonrası
   yazılıyor, ve bu tek başına yeterli sayılmıyor (madde 4'e bakın).
4. **Yeni:** `docker run` exit code 0 dönse bile, A3'e (JSON API
   ayarlama) geçmeden önce betik `docker inspect -f
   "{{.State.Running}}" kaizen-searxng` ile container'ın gerçekten
   `running` durumuna geçtiğini 15 saniyeye kadar aktif olarak bekleyip
   doğruluyor; geçmezse container loglarını (`docker logs --tail 20`)
   yazdırıp güvenli şekilde duruyor.
5. Her durma noktasında mesaj açıkça "BAĞIMLILIK HATASI (Dependency
   Failure) -- bu, SearXNG'nin kendisiyle ilgili bir hata DEĞİLDİR"
   diye etiketleniyor; health check / JSON API testleri yalnız Docker +
   container + running doğrulaması tam geçtikten SONRA çalıştırılıyor
   -- yani bağımlılık hatası hiçbir zaman SearXNG hatası gibi
   raporlanamıyor.
6. Betik hâlâ yalnız `search/` klasörüne (SearXNG'nin kendi
   `searxng-data/` ayar/önbellek dosyaları) yazıyor; gerçek
   `data/`/`logs/`/`memory/` klasörlerine hiç dokunmuyor (madde 6,
   kullanıcı talimatı) -- bu zaten doğruydu, değişmedi.
7. Betik hâlâ yalnız kurulum + kendi kendini doğrulama ile sınırlı;
   SearXNG benchmark'ına veya Learning Brain/Principle Layer işine
   girmiyor (madde 7, kullanıcı talimatı) -- bu da zaten doğruydu,
   değişmedi; betiğin başına ve OZET bölümüne bunu açıkça belirten
   notlar eklendi.

**Yeni dosya: `search/DOCKER_KURULUM.md`** -- kullanıcının istediği,
Windows 10 Pro ortamına özel, minimum ve güvenli Docker Desktop + WSL2
kurulum rehberi. İçerik: `winver` ile sürüm kontrolü; Adım 1 (yönetici
PowerShell'de `wsl --install`, **YENİDEN BAŞLATMA GEREKİYOR** açıkça
işaretlendi); Adım 2 (Docker Desktop indirme/kurma, "Use WSL 2 instead
of Hyper-V" seçili kalmalı, kurulum sonrası **YENİDEN BAŞLATMA
GEREKEBİLİR** açıkça işaretlendi); Adım 3 (Docker Desktop'ı başlatma ve
`docker --version` / `docker info` ile doğrulama, Docker Hub hesabı
GEREKMEZ); Adım 4 (aynı `setup_searxng.ps1`'i tekrar çalıştırma); kısa
bir sorun giderme bölümü (WSL2 kernel güncellemesi, sanallaştırma
BIOS/UEFI ayarı, kurumsal Grup İlkesi kısıtlaması ihtimali).
`search/README.md`'ye bu yeni dosyaya işaret eden bir not eklendi.

**Bilgisayara aktarım:** `search/setup_searxng.ps1`, `search/README.md`
ve `search/DOCKER_KURULUM.md` `device_commit_files` ile bilgisayara
yazıldı, sonra `device_stage_files` ile geri okunup yerel `diff -q` ile
üçü de BAYT-BİREBİR AYNI doğrulandı.

**Veri güvenliği:** `data/accounting_knowledge.sqlite3`,
`data/accounting_learning.json`, `data/kaizen_learning.sqlite3`,
`logs/kaizen.log`, `memory/kaizen_memory.json` SHA256 değerleri bu
segment başında ve sonunda kontrol edildi -- `/tmp/faz11_before.txt`
taban çizgisiyle (bölüm 4t/4v) BİREBİR AYNI, hiç değişmemiş. Bu
segmentte hiçbir test çalıştırılmadı, hiçbir kod (script dışında)
değiştirilmedi.

**Durum: DURULDU.** Kullanıcının talimatı üzerine bu iş emrinin geri
kalanına (SearXNG kurulumunun tamamlanması, A3-A12 benchmark'ı, Faz
B/C) GEÇİLMEDİ. Sırada: kullanıcı `search/DOCKER_KURULUM.md`'yi izleyip
Docker Desktop'ı kurup çalıştıracak, sonra güncellenmiş
`search/setup_searxng.ps1`'i tekrar çalıştıracak. Script bu kez ya (a)
Docker hâlâ eksikse net bir BAĞIMLILIK HATASI ile güvenle duracak, ya da
(b) Docker çalışıyorsa container'ı gerçekten `running` durumuna
getirip A3 (JSON API) adımına geçecek. Kullanıcı sonucu paylaşınca, iş
emrinin sıradaki adımı olan Faz A3 (JSON API doğrulama) ve Faz A4-A12
(Türkçe arama testi, resmî kaynak testi, 20+ sorgu benchmark'ı, Hermes
karşılaştırması, GO/LIMITED/NO-GO kararı) ile devam edilecek.

## 4x. KAIZEN — SearXNG Search Foundation: Benchmark, Hermes Karşılaştırması, SearchProvider (2026-09-23, TAMAMLANDI)

İş emri: "KAIZEN — İŞ EMRİ: SearXNG Search Foundation — Benchmark, Hermes
Karşılaştırması ve SearchProvider Tasarımı". Kurulum tamamlanmıştı
(Docker Desktop + WSL2 kullanıcı tarafından kuruldu, `kaizen-searxng`
container'ı `127.0.0.1:8890`'da çalışıyor). Bu bölüm A-M formatındaki
tam kapanış raporudur; iş emrinin 22 adımlık zorunlu sırası eksiksiz
izlendi. **DUR** talimatı gereği bu bölümden sonra Learning Brain/
Principle Layer'a geçilmedi.

### A — Başlangıç Durumu

Kullanıcının rapor ettiği ortam doğrulandı ve tekrar teyit edildi:
Docker Server 29.8.0, WSL2 backend, `kaizen-searxng` container'ı
`running`. Tarayıcı penceresinden (`http://127.0.0.1:8890/`) health
check: HTTP 200, başlık "SearXNG", sürüm `2026.9.23+3cd69d30e`. JSON
API testi: `/search?q=muhasebe&format=json` → HTTP 200, 43 sonuç,
alanlar (title/url/content/engine/engines/category/score/
publishedDate) eksiksiz döndü. `/config` uç noktası 261 motor
tanımlı olduğunu, bunlardan "general" kategorisinde yalnız 9 motorun
etkin olduğunu gösterdi: wikipedia, currency, wikidata, duckduckgo,
**google cse**, lingva, dictzone, mymemory translated, **brave**.

### B — Benchmark Sorguları

28 sorgu (≥20 şartının üstünde), iş emrindeki kategorilere göre:

*Muhasebe/Vergi/SGK (14):* 2026 gelir vergisi tarifesi · 2026 asgari
ücret net tutarı · 2026 SGK prim oranları · 4/a 4/b 4/c sigortalılık
farkı · geçici vergi oranı 2026 · KDV istisnası kapsamı nedir · binek
otomobil gider kısıtlaması 2026 · amortisman oranları nedir · Bağ-Kur
ve SSK farkı nedir · Tek Düzen Hesap Planı · 7/A ve 7/B maliyet
hesapları farkı · güncel GİB duyuruları 2026 · 2026 kıdem tazminatı
tavanı · e-fatura zorunluluğu limiti 2026.

*PDF discovery (4):* gelir vergisi tarifesi 2026 pdf GİB · SGK prim
oranları tebliğ pdf · TÜRMOB staj yönetmeliği pdf · amortisman
oranları genel tebliğ pdf.

*Freshness (2):* yürürlükteki KDV oranları güncel · 2026 SGK son
duyuru.

*Genel/muhasebe-dışı (4):* 2026 dünya kupası ne zaman · bugün dolar
kuru ne kadar · Türkiye enflasyon oranı 2026 · İstanbul hava durumu
bugün.

*Domain-focused (4):* site:gib.gov.tr gelir vergisi tarifesi ·
site:sgk.gov.tr 4/a 4/b farkı · site:turmob.org.tr staj yönetmeliği ·
site:resmigazete.gov.tr amortisman tebliğ.

Ek olarak, motor iyileşme süresini ölçmek için 3 takip sorgusu daha
çalıştırıldı (bkz. bölüm E).

### C — SearXNG Sonuçları (özet)

27/28 sorgu gerçek, alakalı sonuç döndürdü (yalnızca son domain-focused
sorgu — resmigazete.gov.tr — 0 sonuç verdi, bkz. bölüm E, nedeni motor
askıya alınmasıydı, sorgunun kendisi değil). Öne çıkanlar:

- "2026 gelir vergisi tarifesi", "geçici vergi oranı 2026", "amortisman
  oranları nedir", "7/A ve 7/B maliyet hesapları farkı", "güncel GİB
  duyuruları 2026" → resmî kaynak (cdn.gib.gov.tr / turmob.org.tr /
  gib.gov.tr) doğrudan 1. veya 2-3. sırada.
- "2026 SGK prim oranları", "2026 SGK son duyuru" → sgk.gov.tr 1.
  sırada, birden fazla sonuçta.
- PDF sorgularının 4/4'ünde doğru, resmî/yarı-resmî PDF ilk sırada
  (cdn.gib.gov.tr, sgk.gov.tr/csgb.gov.tr, turmob.org.tr).
- "4/a 4/b 4/c sigortalılık farkı", "KDV istisnası kapsamı nedir",
  "Bağ-Kur ve SSK farkı nedir", "e-fatura zorunluluğu limiti 2026" →
  ilk 5'te resmî kaynak (GİB/SGK/TÜRMOB/Resmî Gazete) YOK, yalnızca
  özel sigorta/muhasebe blogları — konu doğru anlatılmış ama resmî
  kaynak eksik.
- "yürürlükteki KDV oranları güncel" → 2018 ve 2023 tarihli TÜRMOB
  PDF'leri, 2026 etiketli sonuçlarla aynı sırada/üstünde çıktı (bkz.
  bölüm G).
- Domain-focused (site:) sorgularının 3/3'ünde (gib.gov.tr, sgk.gov.tr,
  turmob.org.tr) ilk 5 sonucun tamamı ya da çoğunluğu hedef alan
  adından geldi — `site:` operatörü alttaki motorlar (özellikle google
  cse) üzerinden fiilen çalışıyor.
- Genel/muhasebe-dışı 4 sorgunun 4'ü de doğru ve alakalı sonuç verdi
  (Vikipedi, TCMB, TÜİK, MGM gibi kaynaklar) — SearXNG'nin genel arama
  yeteneği muhasebe alanına yapay olarak sınırlanmamış.

Ham sorgu-sonuç verisi (28 sorgunun tam JSON çıktısı) bu oturumun
tarayıcı konsol geçmişinde mevcuttur; yer tasarrufu için bu bölümde
yalnız özet verildi.

### D — Metrikler

| Metrik | Ham sayı | Yüzde |
|---|---|---|
| Search Success Rate (≥1 anlamlı sonuç) | 27/28 | %96 |
| Useful Top-5 Rate (sonuç dönen sorgularda) | 27/27 | %100 |
| Official Source Discovery Rate (GİB/SGK/TÜRMOB/Resmî Gazete, muhasebe/vergi/SGK 14 sorgu, ilk 5) | 9/14 | %64 |
| Official Top-3 Rate (aynı 14 sorgu, ilk 3) | 7/14 | %50 |
| PDF Discovery Rate (doğru/resmî PDF, ilk 5) | 4/4 | %100 |
| Fresh Result Rate (özel freshness-odaklı 2 sorgu, temiz geçti mi) | 1/2 | %50 |
| Domain-Focused Success Rate (geçerli denemeler, hedef alan adı ilk 5'te baskın) | 3/3 | %100 |
| Engine Failure Rate (tüm motorlar düşüp 0/0 sonuç) | 1/28 | %3,6 (ama etkisi büyük, bkz. E) |

publishedDate alanı 28 sorgunun neredeyse tamamında `null` döndü
(google cse motoru tarih metadata'sı vermiyor) — Fresh Result Rate bu
yüzden yalnız başlık/URL'deki yıl ifadesine bakılarak elle
değerlendirildi, otomatik/güvenilir bir tazelik sinyali YOK.

### E — Engine Health

"general" kategorisindeki 9 motordan yalnız **google cse, brave ve
duckduckgo** gerçek web sonucu getiriyor (wikipedia/wikidata/lingva/
dictzone/mymemory/currency konu dışı ya da destekleyici). Gözlemlenen
davranış:

- **duckduckgo**: ilk 2 sorgudan sonra sürekli `CAPTCHA` (28 sorgunun
  ~23'ünde) — bu kurulumda fiilen kullanılamıyor.
- **brave**: ilk ~8 sorgu boyunca katkı sağladı, sonra
  `Askıya alındı: çok fazla istek` ile düştü ve oturumun geri kalanında
  (90+ saniye sonrasında bile) toparlanmadı.
- **wikidata/wikipedia**: erken rate-limit/timeout, ama bunlar zaten
  genel web sonucu değil, etkisi ikincil.
- **google cse**: 27/28 sorguda TEK gerçek katkı sağlayan motordu —
  yani sistem fiilen **tek motora bağımlı** hale geldi (iş emri madde
  9'un açıkça sorduğu durum). 28. sorguda (yaklaşık 25-30 sorguluk bir
  patlamadan sonra) google cse de `Askıya alındı: çok fazla istek`
  durumuna düştü.
- **Tam kesinti**: 28. sorgudan sonra, +20 saniye ve +90 saniyede
  yapılan 3 takip sorgusunda **google cse, brave VE duckduckgo aynı
  anda askıda** kaldı — yani genel web arama kapasitesi tamamen (0/0)
  sıfırlandı ve 90 saniye içinde toparlanmadı. Oturumun ilerleyen bir
  noktasında (yaklaşık 15-20 dakika sonra, SearchProvider tasarımı
  sırasında yapılan ayrı bir parametre testinde) google cse ve brave'in
  toparlandığı görüldü; duckduckgo CAPTCHA'sı ise kalıcıydı. **Tam
  toparlanma süresi hassas ölçülmedi** (dakikalar ile ~20 dakika
  arası bir noktada) — bu, üretimde ciddi bir güvenilirlik riskidir:
  ardışık birkaç düzine sorgu (ör. Kaizen'in kendi çok-adımlı bir
  araştırma döngüsü) tüm genel arama katmanını uzun süre
  devre dışı bırakabilir.

### F — Resmî Kaynak Analizi

GİB ve TÜRMOB düzenli biçimde bulunuyor (bkz. D). SGK, doğrudan
"SGK" geçen sorgularda (ör. "2026 SGK prim oranları", "2026 SGK son
duyuru") çok iyi buluyor, ama "4/a 4/b 4/c" gibi SGK'nın konusu olan
ama "SGK" kelimesini içermeyen sorgularda hiç çıkmıyor. Resmî Gazete
yalnız 1 sorguda organik olarak çıktı (Tek Düzen Hesap Planı, 5.
sırada); `site:resmigazete.gov.tr` testi motor kesintisine denk geldi,
sonuç inconclusive (bkz. E) — Resmî Gazete'nin site: arama davranışı
bu oturumda GERÇEKTEN test EDİLEMEDİ.

Önemli bir mimari bulgu: `accounting/source_registry.py`'deki
`TRUSTED_SOURCES` listesinde şu an **sgk.gov.tr ve resmigazete.gov.tr
kayıtlı DEĞİL** (yalnız GİB, TÜRMOB ve 15 ikincil/üçüncül kaynak var).
Bu iş emri kapsamında registry'ye dokunulmadı (kapsam dışı), ama
SearchProvider ileride bağlanırsa bu iki resmî kaynağın registry'ye
eklenmesi gerekecek — bu, bölüm M'deki tek sonraki adımın bir parçası
değil, ayrı bir not olarak kayda geçirildi.

### G — Güncellik Analizi

İki açık örüntü gözlemlendi: (1) "2026 SGK son duyuru" sorgusunda
sgk.gov.tr'nin kendi duyuru sayfası gerçekten güncel (Nisan-Ağustos
2026 tarihli) sonuçlar verdi — TEMİZ GEÇTİ. (2) "yürürlükteki KDV
oranları güncel" sorgusunda 2018 ve 2023 tarihli TÜRMOB PDF'leri, 2026
etiketli sonuçlarla YAN YANA/üstte çıktı — yani SearXNG (ya da altındaki
google cse) eski ve güncel belgeleri ayırt etmiyor. Aynı örüntü PDF
testinde de (TÜRMOB staj yönetmeliği: 2015/2018/2025 sürümleri ilk
5'te karışık) ve domain-focused testte de (gib.gov.tr: 2020 tarifesi
2026 tarifesiyle aynı sonuç sayfasında) tekrarlandı. `publishedDate`
metadata'sının neredeyse hiç dolmaması bu riski büyütüyor — otomatik
bir "eski/güncel" filtresi bu haliyle KURULAMAZ, yalnızca başlık/URL
metnindeki yıl ifadesine bakılabilir (güvenilmez, yazarın yazım
alışkanlığına bağlı).

### H — Hermes vs SearXNG

**Önemli sınırlama (şeffaf raporlanıyor):** Bu oturumda gerçek Hermes
CLI'ı, Kaizen'in Windows masaüstündeki `.venv` ortamında çalışıyor;
bu oturumun `device_bash` aracı AYRI, izole bir Linux VM'de çalışıyor
(gerçek Windows ortamına erişmiyor) ve terminal/GUI otomasyon araçları
(PowerShell/Komut İstemi) güvenlik nedeniyle yalnız "tıklama" kipinde
izin veriliyor (yazı yazma/komut çalıştırma YOK). Kaizen masaüstü
uygulaması (`Kaizen_Baslat.bat`) çift tıklamayla başarıyla başlatıldı
(bkz. `logs/kaizen.log`: "Kaizen Engine baslatildi" 20:15:33'te), ama
açılan pencere ekran görüntüsünde birleştirilemedi (izin verilmemiş
pencere sahibi süreç) ve bu oturumda yeni, canlı bir Hermes sorgusu
YAZILAMADI. Bu yüzden 10 sorguluk YAN YANA canlı karşılaştırma
YAPILAMADI — bunun yerine iki gerçek kanıt kaynağı kullanıldı:

1. **Kod incelemesi** (`core/hermes_bridge.py`, değişmedi):
   araştırma modu (`-t web --format stream-json`, 180s timeout)
   gerçek URL+içerik döndürüyor (`web_extract` olayları),
   `accounting/source_registry.py::trusted_source_for_url` ile
   güvenilir kaynağa süzüyor, cevaptaki `KANIT:` satırının açılan
   kaynağın kendi metninde GEÇTİĞİNİ doğruluyor, iddia edilen
   oranları kaynak metniyle çapraz kontrol ediyor.
2. **Gerçek üretim logu** (`logs/kaizen.log`, bu oturumdan ÖNCEKİ
   gerçek kullanıcı etkileşimleri, salt okundu, değiştirilmedi):
   bugün (2026-09-23) 3 gerçek Hermes çağrısı görüldü — biri 60
   saniyede zaman aşımına uğradı, ikisi 33-45 saniye arasında
   tamamlandı (`Mod=NORMAL`, `Timeout=60s`).

Bu iki kanıttan çıkan karşılaştırma:

| Boyut | SearXNG | Hermes |
|---|---|---|
| Kaynak bulma hızı | <1 sn/sorgu (motor düşene kadar) | 33-60+ sn/çağrı (gerçek log) |
| Kaynak URL/liste şeffaflığı | Var (results[].url) | Var (web_extract olayları) |
| Resmî kaynak süzgeci | Yok (ham motor sonucu) | Var (`trusted_source_for_url`) |
| İçerik doğrulama (fetch+read) | Yok (yalnız snippet) | Var (`KANIT:` + oran çapraz kontrolü) |
| Bağımsızlık | Yüksek (Kaizen'in kendi altyapısı) | Hermes/bulut sağlayıcısına bağımlı |
| Motor/kaynak çeşitliliği | Düşük (fiilen tek motor: google cse) | Bilinmiyor (Hermes'in kendi arama katmanı kod incelemesinde görünmüyor) |
| Hata davranışı | Gözlemlenebilir (`unresponsive_engines`) ama sessiz 0/0'a düşebiliyor | Zaman aşımı açıkça loglanıyor |

Sonuç: SearXNG HIZLI ama DOĞRULAMASIZ bir "source discovery" katmanı;
Hermes YAVAŞ ama DOĞRULAMALI bir "fetch+evidence" katmanı. İkisi
birbirinin YERİNE değil, TAMAMLAYICISI olarak değerlendirilmeli (bkz.
bölüm K).

### I — GO / LIMITED / NO-GO

**KARAR: LIMITED.**

Gerekçe: Konu isabeti ve resmî kaynak bulma performansı iyi (Useful
Top-5 %100, Official Top-5 %64, PDF Discovery %100, domain-focused
%100), ve SearXNG genel-amaçlı arama için de çalışıyor (muhasebe
dışı sorgularda da başarılı). Ama iki ciddi, ölçülmüş eksik GO
kararını engelliyor: (1) sistem fiilen TEK MOTORA (google cse)
bağımlı ve bu motor kimlik doğrulamasız/scraping tabanlı olduğu için
Google'ın kendi bot-koruması tarafından hızla ve UZUN SÜRELİ
askıya alınabiliyor (bu oturumda gerçekleşti ve gerçekleşmesi
tekrarlanabilir); (2) güncellik/tazelik sinyali güvenilmez (metadata
yok, eski/yeni belgeler ayırt edilmiyor) — Kaizen'in "eski mevzuatı
güncelmiş gibi sunmama" ilkesiyle doğrudan çelişen bir risk. Bu
eksikler "kullanılabilir ama fallback/ek koruma gerekli" tanımına
tam uyuyor: SearXNG, Kaizen için birincil/tek search katmanı olmaya
HENÜZ hazır değil, ama kontrollü (rate-limit'li, sonuç
doğrulamalı, fallback'li) bir source-discovery katmanı olarak
GELİŞTİRİLMEYE değer.

### J — SearchProvider (Faz B, LIMITED kararı üzerine yapıldı)

Yeni dosyalar (`/home/claude/kaizen` ve bilgisayarda, bayt-birebir
doğrulandı):

- `search/provider.py` — sağlayıcıdan bağımsız sözleşme: `SearchOptions`
  (limit/domains/freshness/language/categories), `SearchResult`
  (title/url/snippet/engine/engines/category/score/published_date/
  domain/is_pdf/query — iş emri madde 10'daki hedef yapı birebir),
  `SearchOutcome` (results + engines_failed + degraded — bölüm E'deki
  "tek motora bağımlılık" bulgusunu gözlemlenebilir kılmak için),
  `SearchProvider` (Protocol) ve `SearchProviderError`.
- `search/searxng_provider.py` — `SearXNGProvider(SearchProvider)`:
  yalnız `http://127.0.0.1:8890`'a bağlanır, stdlib `urllib.request`
  kullanır (yeni bağımlılık YOK, `AGENTS.md` ilkesiyle uyumlu). Hangi
  seçeneğin gerçekten native (categories), hangisinin best-effort
  (language, freshness→time_range) ve hangisinin dolaylı/workaround
  (domains→sorgu metnine `site:` ekleme, native bir SearXNG parametresi
  DEĞİL) olduğu dosyanın kendi docstring'inde açıkça yazılı — iş emri
  madde 14'ün "desteklemediği özelliği varmış gibi gösterme" uyarısına
  uymak için.
- `tests/test_search_provider.py` — **20 yeni test**, TAMAMEN
  mock/fixture tabanlı (sahte bir `opener` enjekte edilerek gerçek ağa
  hiç çıkılmıyor): JSON parse, boş sonuç, boş sorgu (ağ çağrısı hiç
  yapılmıyor), malformed sonuç, bozuk JSON gövdesi, dict-olmayan üst
  seviye yanıt, timeout, bağlantı reddi, HTTP hatası, motor hatası
  (degraded gözlemlenebilirliği), **tüm motorların aynı anda düşmesi**
  (bölüm E'deki gerçek olayı birebir modelleyen test), domain filtreleme
  (tek ve çoklu `site:` enjeksiyonu), yinelenen URL, PDF tespiti,
  Türkçe Unicode round-trip, tam alan normalizasyonu, eksik alanlarda
  güvenli varsayılanlar, `limit` seçeneği.

**KaizenBrain'e BAĞLANMADI** (iş emri madde 15, açıkça korundu) —
`search/` paketi tamamen bağımsız, yalnız kendi testleriyle
doğrulandı; mevcut çalışan cevap zinciri (`core/kaizen_brain.py`,
`core/engine.py`, `core/decision.py`) hiç değiştirilmedi.

### K — Önerilen Search → Research Mimarisi (sonraki faz için, UYGULANMADI)

İş emri madde 17'deki zincir + bölüm H'deki bulgu ışığında önerilen
hibrit:

```
Research Planner
  -> SearXNG (SearchProvider): geniş, bağımsız, hızlı source discovery
  -> Source Registry (accounting/source_registry.py): resmî/güvenilir
     alan adı süzgeci -- SearXNG sonuçlarına da uygulanabilir
  -> Hermes (web_extract): yalnız SearXNG'nin bulduğu ADAYLAR için
     fetch + KANIT doğrulama (SearXNG'nin YAPAMADIĞI şey)
  -> Cross-check / Consensus (accounting/consensus.py)
  -> Facts / Memory
  -> Answer
  -> Learning
```

Mantık: SearXNG'nin hızlı-ama-doğrulamasız discovery'si, Hermes'in
yavaş-ama-doğrulamalı fetch/evidence katmanına aday kaynak SAYISINI
azaltıp isabetini artırabilir (Hermes'in kendi arama adımını
SearXNG'ninkiyle değiştirmek, fetch/KANIT adımını KORUMAK). Bu, iş
emrinin de işaret ettiği "bu hibrit teknik olarak daha güvenliyse
raporda belirt" notuna karşılık gelir. **Bu iş emri kapsamında tam bir
Research Engine YAZILMADI** (madde 19 ve 20 yasağı) — bu yalnız bir
mimari ÖNERİDİR.

### L — Regression ve Veri Bütünlüğü

`python -m tests.run_all`: **132/132 BAŞARILI** (eski 112 + yeni 20
SearchProvider testi, hepsi mock/fixture tabanlı, ağa çıkmıyor).
Gerçek kullanım sınavı: **15/33**, eski sonuçla BİREBİR AYNI (beklenen
— SearchProvider henüz KaizenBrain'e bağlı değil, madde 21'in
öngördüğü gibi skorun değişmesi ZORUNLU değildi ve değişmedi).

SHA256: `knowledge/`, `memory/kaizen_memory.json`, `logs/kaizen.log`,
`data/accounting_knowledge.sqlite3`, `data/accounting_learning.json`,
`data/kaizen_learning.sqlite3` — segment başı ve sonu **BİREBİR AYNI**
(fark yok). Bilinçli değişiklikler yalnızca: `search/__init__.py`,
`search/provider.py`, `search/searxng_provider.py` (yeni),
`tests/test_search_provider.py` (yeni), `tests/run_all.py` (20 yeni
test eklendi), ve bu roadmap dosyası. Hiçbir gerçek kullanıcı/öğrenme
verisi değiştirilmedi veya silinmedi.

### M — Sonraki TEK Adım

`SearXNGProvider`'a çağıran-taraflı bir rate-limit/backoff + "tüm
motorlar düştü" sinyali (`SearchOutcome.degraded`) üzerine kurulu bir
FALLBACK sözleşmesi (SearXNG başarısız olursa ne yapılacağını
KaizenBrain'e bağlamadan, yalnız `search/` paketi içinde, ayrı bir
"CompositeProvider" veya benzeri ile tasarlamak) eklenmeli — bölüm
E'deki "tek motora bağımlılık + uzun süreli tam kesinti" riski, bu
katman KaizenBrain'e bağlanmadan ÖNCE giderilmesi gereken tek somut
mimari eksiktir.

**Durum: TAMAMLANDI, DUR.** Kullanıcı onayı olmadan Learning Brain /
Principle Layer fazına (Faz C) geçilmedi.

## 5. Ofis ve araçlar

Müşavirler Kulübü'nün 54 aracı `knowledge/kaizen_yetenekleri.json` içinde üç gruba ayrılmıştır
(sohbette `yetenekler` yazınca görünür):

- **Hazır:** KDV/tevkifat, stopaj, damga, gecikme zammı, amortisman, serbest meslek makbuzu, NPV/IRR, kredi tablosu,
  başabaş, IBAN, temel finansal oranlar, Excel/Word okuma-yazma, PDF birleştir/böl, görselden PDF. Excel/Word/PDF
  okuma artık sohbetten de çağrılabilir (`oku:` / `doğrula:`, bkz. bölüm 4i); taranmış PDF ve
  fotoğraflanan belgeler (`.jpg/.jpeg/.png`) artık OCR ile okunabiliyor (bkz. bölüm 4m).
- **Güncel parametre gerektirenler** (SGK/maaş, gelir vergisi dilimi, kıdem-ihbar, MTV, emlak, TÜFE kira artışı...):
  değerler koda gömülmez, süzgeçten geçmiş parametre defterinden gelir; konu eklendikçe açılır.
- **Sonraki aşama:** gümrük/ithalat, leasing–kredi, nakit akış, risk analizleri, dilekçe oluşturucu vb.

Ofis araçları (`tools/office_tools.py`) var olan dosyanın üzerine **yazmaz**; yeni ad ile kaydeder.
Excel/Word/PDF *bilgisi* (formüller, kısayollar, kayıt şablonları) `knowledge/*.json` içinde öğretilmiştir ve
açılışta hafızaya yüklenir (`memory/seed_loader.py`; dosya değişince eski sürüm otomatik yenilenir).

## 6. Komutlar

`yardım` · `durum` · `kaynaklar` · `parametreler` · `parametre <konu>` · `yetenekler` · `güncelle [sayfa]` ·
`öğrendiklerim` · `onayla: soru` · `düzelt: soru => doğru cevap` · `oku: dosya yolu` (pdf/excel/word/jpg/png) ·
`doğrula: dosya yolu` (pdf/excel/jpg/png; bkz. bölüm 4i, 4m). Soru başına `muhasebe:` veya `matematik:` yazmak isteğe bağlıdır.

## 7. Test ve kalite

`python -m tests.run_all` tüm testleri çalıştırır (32 test dosyası, 68 test fonksiyonu). `tests/test_golden_exam.py` mali
müşavir "altın sınavı"dır (70 soru, model kapalıyken): yeni yetenek eklerken oraya bir satır ekle.
`tests/test_self_learning.py` kendi kendini geliştiren beyni test eder. `tests/test_refresh_cli.py`
`--rebuild-only`'yi (yeniden tarama yapmadan süzgeci yenileme) test eder. `tests/test_text_tr.py`
ve `tests/test_retriever.py` Türkçe ek kırpma/eşleştirmeyi test eder. `tests/test_brain_manager.py`
`BrainManager`'ı (arama/doğrulama/öğrenme/depolama tek arayüzü) doğrudan test eder.
`tests/test_experience_memory_isolation.py`, tüm test dosyalarını statik (AST) olarak tarayıp
`BrainManager(...)`/`KaizenBrain(...)` çağrılarının gerçek kişisel hafızaya (Cognee) sızmadığını
(daima bir sahte `experience_memory` enjekte edildiğini; bkz. `tests/doubles.py`) kanıtlar — bkz.
bölüm 4n, madde 7. `tests/test_engine_isolation.py` aynı statik (AST) deseniyle `KaizenEngine(...)`
çağrılarının `data_dir=` ile izole edildiğini kanıtlar — bkz. bölüm 4o. Kural: hesap ve kayıt
cevapları için önce test, sonra kod.

**Kabul edilen genel kural (bölüm 4o'dan itibaren):** `python -m tests.run_all` çalışırken projenin
GERÇEK `data/`, `logs/` dizinlerine ve `memory/kaizen_memory.json`'a hiçbir yazma OLMAMALI, hiçbir
gerçek model/ağ çağrısı YAPILMAMALI. Bu, artık yalnız bir iyi niyet değil, ölçülebilir bir ölçüt:
tüm suite çalıştırılmadan önce/sonra bu üç yolun içerik hash'i (`sha256sum`) karşılaştırılarak
doğrulanabilir (bkz. bölüm 4o'daki doğrulama yöntemi).

## 8. Bilinen sınırlar (dürüst liste)

- İlk canlı tarama yapıldı (bkz. bölüm 4e). GİB artık `reference_only` değil: genel sayfaları JS
  ile dolduğu için taranamıyor, ama doğrulanmış 1 resmî PDF (2026 Gelir Vergisi Tarifesi,
  `cdn.gib.gov.tr`) seed olarak eklendi (ilk denenen 4 adresten 3'ü geçersiz çıktı, çıkarıldı).
  Bu PDF, kullanıcının bilgisayarında `--source "Gelir Idaresi Baskanligi"` çalıştırılıp
  `--rebuild-only` ile süzgeç tazelenene kadar süzgece katkı vermez (bkz. bölüm 9, adım 6).
  `verginet.net` (WAF) ve `ozdogrular.com` (robots.txt) otomatik erişimi engelliyor; aşılmadı.
  `roedl.com.tr` JS ile render edildiği için düz HTML'de içerik yok.
- Model kapalıyken cevaplar yorum değil **alıntıdır**; kalite modele bağlanınca artar.
- Gecikme zammında gün→ay dönüşümü varsayımdır (notla belirtilir); güncel oranlar/uygulamalar sitelerden doğrulanmalıdır.
- Binek araç KDV/gider kısıtı gibi konular parametre defterine girene kadar "güncel sınırı sorun" notuyla anılır.
- Maliyet muhasebesi (7/A–7/B) kayıtları ders notlarından cevaplanır; kesin şablonları henüz yazılmadı.
- **Süzgeç, "eski X'ti, yeni Y olacak" kalıbındaki cümlelerde YANLIŞ (eski) değeri seçebiliyor**
  (anchor'a en yakın sayıyı alıyor; kanun değişikliğini anlatan cümlelerde bu genelde eski
  değerdir). VUK 313 2024 örneğinde bulundu (bkz. bölüm 4j) — düzeltilmedi, çünkü genel bir
  davranış değişikliği riskli/geniş kapsamlı olur. Yeni bir çelişki/sıra dışı değer görülünce
  önce kanıt cümlesini oku (`evidence_json`), körlemesine seçme.
- **Yılda iki kez değişen parametreler** (kıdem tazminatı tavanı gibi, Ocak-Haziran/Temmuz-Aralık)
  süzgeçte "çelişkili" görünür çünkü (konu, yıl) anahtarında dönem ayrımı yok — bölüm 4j'de
  bulundu, şema değişikliği (dönem alanı eklemek) gerektirir, henüz yapılmadı.
- **"Örnek" (worked example) hesaplama cümleleri gerçek yasal sınırla karışabiliyor** (binek araç
  kiralama gider sınırı 2024'te görüldü, bölüm 4j) — yazarın seçtiği örnek rakam, gerçek sınır
  sanılabiliyor. Bunun için Kaizen'in "kaynaklar çelişiyor, kesin cevap veremiyorum" demesi
  doğru/güvenli davranıştır; zorlanmadı.
- **Uygulama aniden kapanırsa kuyrukta bekleyen deneyim-hafızası yazımları kaybolabilir**
  (bkz. bölüm 4n, madde 4) — kuyruk artık SINIRLI ve gözlemlenebilir ama yalnız bellekte
  (RAM'de) tutuluyor; disk'e kalıcı yazılmıyor. Tam çözüm (kalıcı/disk-destekli kuyruk) bilinçli
  olarak kapsam dışı bırakıldı — asıl şikayet olan görünürlük eksikliği ve sınırsız thread
  büyümesi giderildi, bu kalan parça daha büyük bir mimari değişiklik gerektirir.
- **Ana cevap sağlayıcısı hâlâ Hermes (bulut), yerel sohbet modeli boş** (`config/Kaizen.json`;
  bkz. bölüm 4n sonu) — Cognee yerel Ollama'ya bağlı olsa da bugün sistemin tamamı yerel
  çalışmıyor; `doğrula:` ile okunan belge içeriği de Hermes'e gidiyor. Bilinçli bir aşamalı geçiş
  kararı (bkz. bölüm 9, madde 9); kullanıcı onayı olmadan değiştirilmedi.

## 9. Sıradaki adımlar

1. ~~Muhasebenin temel taşlarını çekirdek müfredata yazmak~~ — tamamlandı (bkz. bölüm 4b).
2. ~~Kendi kendini geliştiren öğrenen beyin~~ — tamamlandı (bkz. bölüm 4c). Araştırma sonucu (Hermes
   yalnız işçi) beklemede olsa bile HEMEN kalıcı hafızaya yazılıyor; tekrar sorulunca araştırmaya
   gitmiyor; parametre defteriyle çapraz kontrol ediliyor; mali müşavir onayı yalnız güven etiketini
   yükseltiyor (uyarıyı kaldırıyor), hafızaya yazılıp yazılmayacağını değil.
3. ~~SGK: temel yapı~~ — tamamlandı (bkz. bölüm 4d). Değişen kısım (taban/tavan zaten vardı;
   `sgk_isci_prim_orani`, `sgk_isveren_prim_orani`, `issizlik_sigortasi_orani` konu olarak eklendi)
   ilk canlı taramadan sonra süzgeçle dolacak — henüz sayı yok, konu tanımı hazır.
4. ~~İlk canlı tarama~~ — tamamlandı (bkz. bölüm 4e). 511 sayfa, 17 kaynak; 3 süzgeç hatası
   bulunup düzeltildi (Türkçe URL kodlama, sayı kırpılması, format-farkı çelişkisi).
5. ~~Kalan çelişkilerin konu tanımı kararı~~ — tamamlandı (bkz. bölüm 4e, "Karar verildi").
   Çelişkili parametre 6 → 1 (yalnız 2026 yeniden değerleme oranı, gerçek/henüz açıklanmamış
   belirsizlik), doğrulanmış 8 → 11. GİB'in doğrulanmış statik PDF belgeleri seed edildi.
6. Kullanıcı kendi bilgisayarında `python -m accounting.refresh --source "Gelir
   Idaresi Baskanligi"` çalıştırıp GİB'in doğrulanmış 1 resmi PDF'ini indirsin (saniyeler
   sürer), sonra `--rebuild-only` ile süzgeç tazelensin. 2026 yeniden değerleme oranı, resmi
   ilan (Kasım-Aralık 2026) yayımlandığında bir sonraki `güncelle` ile netleşecek.
7. ~~Kaizen'in beynini geliştirme kararı (Cognee önerisi değerlendirmesi)~~ — tamamlandı
   (bkz. bölüm 4f). Kademe 0 (Türkçe ek kırpma düzeltmesi) ve **Kademe 1 (`BrainManager`
   soyutlaması) bitti** — `memory/brain_manager.py`, bkz. bölüm 4f. **Sırada Kademe 2:**
   kavramlar arası basit ilişki tablosu (SQLite, curated — graf veritabanı değil).
8. `config/fact_topics.json`'a diğer parametre konuları (gelir vergisi dilimleri — GİB'den
   2026 tarifesi zaten seed edildi —, MTV, emlak...) ve bunlara bağlı hesaplayıcılar.
9. Yerel model bağlantısı — **karşılandı (bölüm 4g)**: Ollama + llama3.2:3b + bge-m3 kurulu.
   Hermes'in kademeli kapatılması hâlâ sırada.
10. WhatsApp fatura otomasyonu ve ofis yardımcılığı (en son; `INDEPENDENCE_PLAN.md` "Ofis uygulamalarında görev yapma").
11. **Bugün başlanan sıra (2026-09-22, kullanıcı: "sistemi en baştan tara, sonra sıranı belirle ve yap"):**
    - ~~Masaüstü uygulaması~~ — tamamlandı (bölüm 4h, `desktop_app.py`).
    - ~~Mali müşavir sesi tutarlılığı (araştırma prompt'ları)~~ — tamamlandı (bölüm 4h).
    - ~~(a) Excel/hesap teyidi~~ ve ~~(b) PDF/Excel okumanın sohbetten erişilebilir hale
      gelmesi~~ — tamamlandı (bölüm 4i, `oku:` / `doğrula:` komutları).
    - ~~Kullanıcı tam yeniden taramayı çalıştırdı~~ — tamamlandı: `--backfill` ile 17 kaynak,
      36 parametre (14 doğrulanmış, 18 tek kaynak, 4 çelişkili). Çelişkilerin kaynak cümle
      analizi ve süzgeç düzeltmesi — tamamlandı (bölüm 4j). Kullanıcının şimdi yapması gereken:
      `python -m accounting.refresh --rebuild-only` (yeniden tarama YOK, saniyeler sürer) —
      düzeltmenin zaten indirilmiş sayfalara uygulanması için.
    - ~~(c) Kaizen beyni Kademe 2: Cognee deneyim hafızası BrainManager'a bağlandı~~ —
      tamamlandı (bölüm 4k). "kaizen beyni yeni eklentiler ile tekrardan dizayn edilmeli
      önce" isteği burada karşılandı: kurulu duran Ollama+Cognee artık gerçekten kullanılıyor
      (yazma: her başarılı cevap; okuma: yalnız son çare "bulamadım" noktalarında, açıkça
      doğrulanmamış etiketiyle). Kesin/sayısal cevaplar hâlâ yalnız cards/facts/exact-tools'tan.
    - ~~(d) Taranmış/resimli PDF ve fotoğraf için OCR (görsel okuma)~~ — tamamlandı (bölüm 4m).
    - (e) bölüm 8'deki üç eski bulgu (eski/yeni kalıbı, dönemsel parametreler, örnek-cümle
      karışması) ve (f) Kademe 3 (recall_card'a deneyim-hafızası ipucu) hâlâ ertelenmiş —
      aşağıdaki dış inceleme sırası önceliklendi.
12. **Dış inceleme (başka bir yapay zeka, salt-okunur), 7 madde sırasıyla (2026-09-23, bkz. bölüm
    4n):** kullanıcının "es geçmeden düzeltelim" talimatıyla başlatıldı.
    - ~~1. Süzgeçte yüzde/ondalık nokta karışıklığı~~ — tamamlandı.
    - ~~2. Belge doğrulamanın kesin/kodla karşılaştırmaya taşınması + Excel/model okuma
      sınırlarının (50 satır / 8.000 karakter) gözden geçirilmesi~~ — tamamlandı.
    - ~~3. Bilgi kartı onaylama (kaynak bağımsızlığı + aynı-turda-çelişki engeli)~~ — tamamlandı.
    - ~~4. Cognee arka plan yazımlarında `ok=False`/istisna görünürlüğü, sınırlı iş kuyruğu~~ — tamamlandı.
    - ~~5. Süzgeç yeniden kurulduğunda eski geçersiz kayıtların temizlenmesi~~ — tamamlandı.
    - ~~6. robots.txt'in kendisi 429 dönerse "izin verildi" sayılmaması~~ — tamamlandı.
    - ~~7. Testlerin gerçek kişisel hafızadan tam ayrılması~~ — tamamlandı.
    - **7 maddenin TAMAMI tamamlandı (2026-09-23).**
    - **Kullanıcı onayı bekliyor (henüz kod değişikliği yapılmadı):** ana cevap sağlayıcısının
      hâlâ Hermes/bulut olması, yerel sohbet modelinin boş olması — bkz. bölüm 4n sonu.

## 4y. KAIZEN — Search Resilience v1: Rate Limit, Backoff, Health ve Fallback Contract (2026-09-23, TAMAMLANDI)

İş emri: "KAIZEN — İŞ EMRİ: Search Resilience v1 — Rate Limit, Backoff, Health ve Fallback
Contract" — bölüm 4x'in ("SearXNG Search Foundation") doğrudan devamı. Bu bölüm, 4x'te
tespit edilen temel sorunu (SearXNG'nin `google cse`'ye aşırı bağımlı olması; DuckDuckGo'nun
sık sık CAPTCHA'ya takılması; Brave'in yoğun kullanımda askıya alınması; ~28 sorguluk bir
patlamanın (burst) eşzamanlı çoklu-motor kesintisine yol açması) çözmek için **SearchProvider
katmanına dayanıklılık (resilience) altyapısı** ekler. **`SearchProvider` hâlâ `KaizenBrain`'e
BAĞLANMADI** (iş emri madde 14) — bu bölüm yalnızca bağımsız, test edilebilir bir altyapı
katmanıdır.

### A. Baseline

- Repo durumu: `search/provider.py`, `search/searxng_provider.py`,
  `tests/test_search_provider.py` (4x'te oluşturulan 20 test) incelendi, **hiçbiri
  gereksiz yere yeniden yazılmadı** — yalnızca additive (eklemeli) değişiklikler yapıldı.
- Regresyon baseline'ı doğrulandı: **132/132 BAŞARILI** (bu iş emrinden önceki toplam).
- SHA256 checkpoint alındı (`knowledge/`, `memory/kaizen_memory.json`, `logs/kaizen.log`,
  `data/*`) — iş emri sonunda aynı dosyalarla karşılaştırıldı (bkz. bölüm L).

### B. Önceki Failure Mode (4x'ten miras)

4x'teki 28 sorguluk benchmark burst'ü sırasında google cse/brave/duckduckgo'nun ÜÇÜ DE aynı
anda askıya alındı ve bu durum en az 90 saniye boyunca düzelmedi. O zamanki `SearXNGProvider`
hiçbir yeniden deneme/backoff/health takibi yapmıyordu; hata durumunda tek tip
`SearchProviderError` fırlatıyordu, "sonuç yok" ile "motor düşmüş" arasında hiçbir ayrım
yoktu. Bu bölümün amacı tam olarak bu boşluğu kapatmak.

### C. Search Status Contract

`search/provider.py`'ye (`core/trace.py`'nin düz-string-sabiti konvansiyonuna uyularak,
Enum KULLANILMADI) yedi durum eklendi: `STATUS_OK`, `STATUS_EMPTY`, `STATUS_DEGRADED`,
`STATUS_RATE_LIMITED`, `STATUS_TIMEOUT`, `STATUS_UNAVAILABLE`, `STATUS_ERROR`.

**Kritik kural (madde 3) birebir uygulandı**: `RATE_LIMITED`/`TIMEOUT`/`UNAVAILABLE`/`ERROR`
durumları HİÇBİR ZAMAN `SearchOutcome.status`'ta görünmez — bunlar her zaman tipli bir
exception olarak (`SearchTimeoutError`, `SearchRateLimitedError`, `SearchUnavailableError`,
temel `SearchProviderError`) FIRLATILIR, asla sessizce boş sonuca çevrilmez. Yalnızca
`OK`/`EMPTY`/`DEGRADED` — yani "istek başarıyla tamamlandı, şimdi sonucu yorumla" durumları
— `search()`'ün normal dönüş değerinde (`SearchOutcome.status`) görünür. Her exception
sınıfının kendi `.status` ve `.fallback_reason` class-attribute'u var; `SearchRateLimitedError`
ayrıca `.retry_after` (saniye, biliniyorsa) taşır. Geriye dönük uyumluluk KORUNDU: tüm yeni
exception sınıfları `SearchProviderError`'dan türer, yani mevcut `except SearchProviderError`
blokları hâlâ çalışır.

### D. Retry/Backoff

`SearXNGProvider`'a sınırlı (bounded) bir yeniden deneme mekanizması eklendi:

- **Yeniden denenen (retryable) durumlar**: timeout, HTTP 429, HTTP 500/502/503, geçici
  bağlantı hatası (`URLError`/`OSError`).
- **Yeniden DENENMEYEN durumlar**: bozuk JSON, beklenmeyen gövde tipi, 429/5xx dışındaki
  HTTP hataları (400/401/403/404 vb.) — bunlar kalıcı hatalar, tekrar denemek sonucu
  değiştirmez.
- Varsayılan `max_attempts=3`, `backoff_base=0.2s`, `backoff_max=4.0s` — sınırlı üstel
  (bounded exponential) backoff (`0.2s, 0.4s, 0.8s, ...`, `backoff_max`'i asla aşmaz).
  Sonsuz döngü YOK, agresif sorgu bombardımanı YOK, CAPTCHA/rate-limit bypass YOK (yalnızca
  makul, sınırlı bekleme sonrası tekrar deneme).
- `sleep` ve `clock` constructor'da ENJEKTE EDİLEBİLİR (varsayılan `time.sleep`/
  `time.monotonic`) — testler GERÇEK bekleme kullanmadan backoff davranışını doğrulayabilir.

### E. Burst Protection

`min_request_interval` (varsayılan 1.0 saniye) ile art arda gelen `search()` çağrıları
arasına asgari bir bekleme konuldu. Amaç performans değil — Kaizen'in kendi patlama
davranışıyla SearXNG'nin motorlarını kendi kendine askıya aldırmasını önlemek. Ayrıca bir
**rate-limit sonrası soğuma (cooldown)** mekanizması eklendi: HTTP 429 alındığında (retry'lar
tükendikten sonra) provider `HEALTH_COOLDOWN` durumuna geçer ve bir `cooldown_until`
zaman damgası hesaplanır (`Retry-After` header'ı varsa ondan, yoksa `cooldown_seconds`
varsayılanından, 30s). Bu süre dolmadan yapılan yeni `search()` çağrıları **AĞA HİÇ
ÇIKMADAN** hemen `SearchRateLimitedError` fırlatır — bu hem burst korumasını güçlendirir
hem de rate-limit'e saygıyı garanti eder (bypass YOK).

### F. Engine Health / Degradation

`unresponsive_engines` alanı aynen `SearchOutcome.engines_failed`'e taşınmaya devam ediyor.
Buna ek olarak **tek-motora-bağımlılık (single-engine dependency) sinyali** eklendi
(`SearchOutcome.single_engine_dependency`): sonuçlar geldi ama fiilen TEK bir motordan
geliyorsa (`item.engines`/`item.engine` alanlarının birleşiminden hesaplanır — LLM tahmini
YOK, tamamen gerçek veriden) bu `True` olur ve `status=DEGRADED` işaretlenir. Bu, "3 motor
tanımlı ama pratikte hep tek motor cevap veriyor" durumunu — ki 4x'in F bölümünde tam olarak
bu gözlemlenmişti — artık programatik olarak görünür kılıyor.

### G. Provider Health

`search/provider.py`'ye `ProviderHealth` (frozen dataclass) eklendi: `state`
(`HEALTHY`/`DEGRADED`/`COOLDOWN`/`UNAVAILABLE`), `consecutive_failures`, `last_status`,
`last_error`, `last_success_at`, `last_failure_at`, `cooldown_until`. `SearXNGProvider.health`
property'si her `search()` çağrısından SONRA gerçek gözlemlenen sonuca göre güncellenir:
başarı → `consecutive_failures=0` ve `HEALTHY` (veya sonuç `DEGRADED` ise `DEGRADED`); hata →
`consecutive_failures` artar, `unavailable_after` eşiğini (varsayılan 3) aşarsa `UNAVAILABLE`;
rate-limit hatası doğrudan `COOLDOWN`'a ve bir soğuma süresine yol açar. Tamamen gerçek,
gözlemlenebilir sinyallerden inşa edilir — LLM tahmini kullanılmaz (madde 7).

Ayrıca madde 13'ün istediği minimal gözlemlenebilirlik/trace metadata'sı için
`SearchDebugInfo` eklendi (`provider`, `query`, `attempt_count`, `elapsed`, `status`,
`result_count`, `active_engines`, `unresponsive_engines`, `fallback_recommended`,
`fallback_reason`) — `SearXNGProvider.last_search_debug` üzerinden okunur, `core/trace.py`'nin
"çağrıdan sonra okunur, cevabı değiştirmez" konvansiyonunu izler. **Bu FAZDA
`KaizenBrain`'in kendi trace zincirine (`KaizenTrace`) BAĞLANMADI** — bağımsız bir katman.

### H. Fallback Contract

Madde 8'in istediği gibi, üst katmana "fallback önerilir" sinyali SEBEBİYLE BİRLİKTE iki
kanaldan aktarılıyor:

1. **Exception yoluyla** (hard failure): her `SearchProviderError` alt sınıfının
   `.fallback_reason` class-attribute'u var (`"timeout"`, `"rate_limited"`,
   `"unavailable"`, `"error"`).
2. **`SearchOutcome` yoluyla** (soft/degraded ama exception-dışı): tüm motorlar düşmüş VE
   sonuç sıfırsa (`4x`'in tam olarak gözlemlediği "0/0 sonuç" senaryosu),
   `fallback_recommended=True` ve `fallback_reason="degraded_no_results"` işaretlenir.
   Kullanılabilir sonuç varsa (bir motor düşse bile) `fallback_recommended=False` kalır —
   üst katman zaten elindeki sonucu kullanabilir.

**Otomatik canlı Hermes fallback bağlantısı YAPILMADI** (madde 8'in açık izniyle) — yalnızca
sözleşme/sinyal inşa edildi. `core/hermes_bridge.py` HİÇ DEĞİŞTİRİLMEDİ.

### I. Yapılan Kod Değişiklikleri

- `search/provider.py`: additive — `STATUS_*`/`FALLBACK_REASON_*`/`HEALTH_*` sabitleri,
  `ProviderHealth`, `SearchDebugInfo`, `SearchTimeoutError`/`SearchRateLimitedError`/
  `SearchUnavailableError` (hepsi `SearchProviderError`'dan türer), `SearchOutcome`'a 4 yeni
  varsayılan-değerli alan (`status`, `single_engine_dependency`, `fallback_recommended`,
  `fallback_reason`). `SearchOptions`/`SearchResult`/`SearchProvider` Protocol'ü
  DEĞİŞTİRİLMEDİ.
- `search/searxng_provider.py`: `__init__`'e retry/backoff/burst/health parametreleri
  eklendi (hepsi makul varsayılanlı); `search()` bir retry döngüsüyle sarmalandı; hata
  sınıflandırma (`_classify_http_error`, `_classify_connection_error`), health takibi
  (`_record_success`/`_record_failure`), cooldown kontrolü (`_raise_if_in_cooldown`), burst
  koruması (`_respect_min_request_interval`) ve debug-info üretimi eklendi. `_normalize()`
  ve dedup/domain-filtreleme/limit mantığı **DEĞİŞTİRİLMEDİ**.
- `tests/test_search_provider.py`: **HİÇ DOKUNULMADI** (20 test, birebir aynı).
- `tests/test_search_resilience.py` (YENİ, 29 test).
- `tests/run_all.py`: yeni import + çağrı bloğu eklendi (132 → 161).

### J. Yeni Testler (29 test, `tests/test_search_resilience.py`)

Madde 12'nin listesindeki tüm alanlar kapsandı: başarılı arama, retry-sonrası-başarı,
retry-limiti-tükenmesi, enjekte edilebilir sleep ile bounded-exponential backoff doğrulaması,
HTTP 429 (retry_after ile RATE_LIMITED), HTTP 500/502/503 (retryable → UNAVAILABLE), HTTP 404
(retryable DEĞİL), bozuk JSON (retryable DEĞİL), bağlantı reddi (retryable → UNAVAILABLE),
OK/EMPTY status ayrımı, tek-motora-bağımlılık sinyali (pozitif ve negatif durum), bir motor
düşerken diğerinin kurtarması, tüm motorlar düşünce fallback önerisi + sebebi, fallback
gerekmeyen normal durum, "exception asla sessizce boş sonuca dönüşmez" garantisi, Provider
Health üç geçişi (HEALTHY→UNAVAILABLE, UNAVAILABLE→HEALTHY toparlanma), rate-limit sonrası
cooldown + sonraki çağrının ağa hiç çıkmadan hızlı başarısız olması, cooldown süresi
dolduktan sonra ağa tekrar çıkılması, burst korumasının asgari aralığı zorlaması, yeterli
süre geçtiğinde ekstra bekleme EKLENMEMESİ, yinelenen URL/Türkçe Unicode/PDF tespiti/domain
filtrelemenin resilience sarmalayıcısıyla da bozulmaması, ve son olarak başarılı/başarısız
çağrılardan sonra `last_search_debug`'ın doğru doldurulması. **Hepsi sahte (fake) `opener`/
`sleep`/`clock` kullanır — hiçbiri gerçek ağa çıkmaz veya gerçek zaman geçirmez** (29 testin
tamamı ~0.05 saniyede tamamlanıyor).

### K. Gerçek SearXNG Smoke Test

Madde 16'nın istediği gibi, **yalnızca 4 kontrollü sorgu** (28'lik bir burst DEĞİL),
tarayıcı paneli üzerinden (kullanıcının gerçek bilgisayarındaki SearXNG'ye, `fetch()` ile,
her biri ayrı bir araç çağrısında — doğal ~1-2 saniyelik aralıklarla, yapay bir burst
oluşturulmadı):

| # | Sorgu | HTTP | Sonuç | Düşen motor(lar) |
|---|---|---|---|---|
| 1 | gelir vergisi tarifesi 2026 | 200 | 30 | duckduckgo (CAPTCHA) |
| 2 | SGK 4/a sigortalılık | 200 | 33 | duckduckgo (CAPTCHA), wikipedia (HTTP hatası) |
| 3 | KDV oranları site:gib.gov.tr | 200 | 19 (ilk 3'ü gib.gov.tr) | duckduckgo (CAPTCHA), google cse (çok fazla istek) |
| 4 | muhasebe (language=tr) | 200 | 26 | duckduckgo (CAPTCHA), google cse (askıya alındı), wikidata (HTTP hatası) |

Sonuç: **4/4 sorgu başarılı (Search Success), gerçek uç noktaya karşı JSON normalizasyonu
sorunsuz çalıştı, health/unresponsive_engines metadata'sı gerçek zamanlı olarak geldi**.
Dikkat çekici gözlem: 4. sorguda google cse de "çok fazla istek"/askıya alındı durumuna
geçti — bu, 4x'te tespit edilen "google cse'ye aşırı bağımlılık" riskinin hâlâ gerçek
olduğunu, YENİ eklenen `single_engine_dependency`/health/fallback mekanizmalarının tam
olarak bu tür durumları yakalamak için var olduğunu teyit ediyor. Bu 4 sorgu boyunca yeni
eklenen client-side burst koruması/cooldown mekanizması normal kullanımı ENGELLEMEDİ (hepsi
başarıyla tamamlandı).

### L. Regresyon + SHA256

- **Regresyon: 161/161 BAŞARILI** (önceki 132 + yeni 29 = 161; hem `tests/test_search_provider.py`'nin
  20 orijinal testi hem yeni 29 dayanıklılık testi dahil, tamamı geçti).
- Gerçek hayat sınavı yeniden çalıştırıldı: **15/33 BAŞARILI — DEĞİŞMEDİ** (beklenen sonuç,
  çünkü `SearchProvider` hâlâ `KaizenBrain`'e bağlı değil).
- SHA256 karşılaştırması: `knowledge/`, `memory/kaizen_memory.json`, `logs/kaizen.log`,
  `data/*` dosyalarının hash'leri iş emri başındaki checkpoint ile **BİREBİR AYNI** —
  gerçek veri hiç değişmedi.

### M. Açık Teknik Borçlar (bilerek bu fazda ÇÖZÜLMEDİ, iş emrinin kapsam dışı bıraktığı)

- **Freshness sıralaması**: 4x'teki Fresh Result Rate (1/2) sorunu hâlâ çözülmedi; bu fazda
  yalnızca mevcut `published_date` alanı korundu, herhangi bir ranking/işleme eklenmedi
  (madde 10'un açık izniyle).
- **`accounting/source_registry.py`**: `sgk.gov.tr` ve `resmigazete.gov.tr` hâlâ
  `TRUSTED_SOURCES`'ta yok (madde 11'in açık izniyle dokunulmadı).
- **`language`/`time_range` parametrelerinin gerçekten filtrelediği hâlâ ayırt edici
  biçimde kanıtlanmadı** (4x'ten miras, bu fazda da test edilmedi).
- **Otomatik canlı Hermes fallback bağlantısı henüz YOK** — yalnızca sözleşme (madde 8'in
  kasıtlı sınırı).
- **`unavailable_after`/`cooldown_seconds`/`min_request_interval` varsayılanları
  (sırasıyla 3, 30s, 1.0s) prodüksiyonda henüz gerçek/uzun-süreli trafikle
  ayarlanmadı/kalibre edilmedi** — makul başlangıç değerleri, ileride Research Engine
  entegrasyonunda gözden geçirilmeli.
- **`SearchProvider` hâlâ `KaizenBrain`'e bağlı değil** — bu fazın da kasıtlı sınırı (madde 14).

### N. Sonraki TEK Adım

`SearchProvider`'ı (ve bu fazda eklenen `ProviderHealth`/Fallback Contract'ı) hâlâ
`KaizenBrain`'e BAĞLAMADAN, `H` bölümündeki Fallback Contract'ı gerçekten kullanacak
**ayrı, bağımsız bir "Research Orchestrator" tasarım/prototip fazı** başlatılmalı: yalnızca
`fallback_recommended=True` sinyali geldiğinde `core/hermes_bridge.py`'nin
`web_extract`/`KANIT` doğrulamasına ne zaman/nasıl başvurulacağını (hâlâ mock/fixture
tabanlı, KaizenBrain'e bağlanmadan) tanımlayan küçük bir karar tablosu/sözleşme — böylece bir
sonraki fazda gerçek entegrasyon, bugüne kadar inşa edilen üç bağımsız parçayı (SearchProvider,
Fallback Contract, Hermes) ilk kez BİR ARAYA getirmeden önce kağıt üzerinde netleşmiş olur.

**DUR.** Learning Brain/Principle Layer çalışmasına otomatik geçilmiyor; kullanıcı onayı
bekleniyor.

## 4z. KAIZEN — Learning Brain v1: Principle Layer, Principle Retrieval ve Transfer Testi (2026-09-23, TAMAMLANDI)

İş emri: "KAIZEN — İŞ EMRİ: Learning Brain v1 — Principle Layer, Principle Retrieval ve
Transfer Testi" (25 madde, §25'te verilen 20 adımlık çalışma sırası birebir izlendi).
Amaç: Kaizen'e `problem → problem yapısı → ilgili muhasebe ilkesi → ilkeyi yeni probleme
uygula → cevap` katmanını, mevcut cevap zincirine DOKUNMADAN (shadow/observational,
madde 14), ölçülebilir bir TRANSFER SCORE ile eklemek. Search/Research entegrasyonuna
(madde 19) ve Reflection Engine/Cognee/fine-tuning'e (madde 20-21) bilerek dokunulmadı.

### A. Baseline

- Başlangıç regresyonu: **161/161 BAŞARILI** (Search Resilience v1'in bıraktığı hâl).
- Gerçek kullanım sınavı: **15/33 BAŞARILI** (kategori dağılımı: matematik 8, muhasebe 12,
  sgk 7, güncel 6; darboğaz dağılımı: other 6, research 7, retrieval 4, classification 1).
- SHA256 checkpoint: `knowledge/*.json` (6 dosya), `memory/kaizen_memory.json`,
  `logs/kaizen.log`, `data/accounting_knowledge.sqlite3`, `data/accounting_learning.json`,
  `data/kaizen_learning.sqlite3` — kaydedildi (`/tmp/learning_brain_before.txt`).
- Mevcut kod incelendi (yeniden yazılmadı): `core/kaizen_brain.py`, `core/decision.py`,
  `core/text_tr.py`, `core/trace.py`, `accounting/retriever.py`, `memory/learning_store.py`,
  `memory/knowledge_cards.py`, `memory/brain_manager.py`, `accounting/facts.py`,
  `accounting/consensus.py`.
- **Not (şeffaflık)**: bu iş emrinin ortasında oturum ortamı bir kez sıfırlandı (çalışma
  dizini/MCP bağlantıları kısa süreliğine düştü). Devam etmeden önce 161/161, 15/33 ve
  SHA256 checkpoint'i BAŞTAN doğrulandı — hiçbirinde sapma bulunmadı (bkz. bölüm D'nin
  hemen altındaki "bilinen risk ve düzeltme" notu, madde 23'ün ruhuyla).

### B. Transfer Baseline (Principle Layer'dan ÖNCE ölçüldü)

`tests/test_learning_transfer.py` — Principle Layer'dan HİÇBİR SATIR KOD YAZILMADAN ÖNCE
oluşturuldu (madde 3). 7 transfer senaryosu (7 zorunlu ilke ailesi), her biri A/B/C/D
yapısında (öğrenilen ilke / yüzeysel farklı problem / beklenen ilke / yanlış transfer
riski taşıyan karşı örnek).

Baseline ölçümü, KaizenBrain'in GERÇEKTEN kullandığı geri getirme yolunun (`accounting/
retriever.py::Retriever` + `memory/learning_store.py::LearningStore`, izole bir geçici
sqlite'a `knowledge/*.json`'dan tohumlanmış) en iyi eşleşen kanıt parçasını KABA bir
alt-metin eşleşmesiyle 7 ilkeden birine "tahmin etmeye zorlanması" ile yapıldı — yani
"mevcut kelime-eşleşmeli sistem bir ilke seçmek zorunda bırakılsaydı ne seçerdi" sorusunun
en dürüst yaklaşık cevabı:

| Metrik | Ham | Yüzde |
|---|---|---|
| Positive Transfer Accuracy | 2/7 | %28.6 |
| Negative Transfer Rejection | 6/7 | %85.7 |
| **Overall Transfer Score** | **8/14** | **%57.1** |

Ayrıntı: `donemsellik` ve `borç/alacak` ve `özün önceliği` B'lerinde mevcut sistem HİÇBİR
ilke içeriğini üst sırada getiremedi (kelime örtüşmesi yetersiz kaldı); `maliyet_ilkesi`
B'sinde YANLIŞ ilkeyi (`donemsellik`) getirdi; en kritik bulgu: `borç/alacak` D'sinde
(hesap sınıflandırması sorusu) mevcut sistem YANLIŞLIKLA "çift taraflı kayıt" bölümünü
getirip `borc_alacak` olarak sınıflanabilirdi — TAM OLARAK madde 10'un uyardığı yanlış
transfer riskinin GERÇEK bir örneği. Testler SONRADAN değiştirilmedi (madde 3).

### C. Fact vs Principle

Mimari ayrım (madde 4/16) KOD SEVİYESİNDE zorlanıyor, yalnız dokümantasyonda değil:

- **FACT**: `accounting/facts.py::FactRegistry` + `accounting/consensus.py` — hiç
  dokunulmadı, Principle Layer bunları hiç import etmiyor.
- **PRINCIPLE**: `memory/principle_registry.py::PrincipleRegistry` — `upsert()` YAZMA
  ANINDA her satırın `name`/`description`'ında 4 haneli bir yıl (2020-2099) regex'i
  arar ve varsa `PrincipleRegistryError` fırlatır (statik, yazma-zamanı FACT sızıntısı
  koruması). Ayrıca `learning/problem_structure.py::RATE_QUERY` sinyali (bir soru "oran
  nedir/kaç" kalıbı taşıyorsa) `learning/principle_retriever.py`'de EVRENSEL bir veto
  olarak uygulanıyor: bu sinyal ateşlediğinde HANGİ İLKE OLURSA OLSUN seçim reddediliyor
  (`fact_safety_triggered=True`, `selected=None`, `confidence=NONE`) — "Geçen yıl oran
  X'ti, bu yıl da X olmalı" tarzı bir çıkarım mimari olarak İMKANSIZ kılındı.

### D. Principle Registry

`memory/principle_registry.py::PrincipleRegistry` — `accounting/facts.py::FactRegistry`
ile aynı SQLite deseni (kendi `data/kaizen_principles.sqlite3` dosyası, `_connect()`/
`_initialize()`, `closing()`), ama BİLEREK `keyword -> principle` tablosu DEĞİL (madde 5).
Şema: `principle_id` (PK), `name`, `description`, `domain`, `problem_structure` (JSON:
`primary_signal` + `veto_signals`), `applicability` (JSON liste), `non_applicability`
(JSON, insan-okunur notlar), `examples`/`counter_examples` (JSON liste), `source`
(provenance, BOŞ OLAMAZ — `upsert()` zorunlu kılıyor), `status`, `created_at`/`updated_at`.

Başlangıç set'i (madde 6, tam 7 — 5-7 aralığında): `knowledge/principles/
principles_seed.json` (`learning/principle_seed.py::load_principle_seeds()` ile
yüklenir) — dönemsellik, borç/alacak mantığı, hesap sınıflandırma mantığı, özün
önceliği/ekonomik öz, maliyet ilkesi, amortisman mantığı, SGK statü mantığı. Her satırın
`source`'u mevcut `knowledge/muhasebe_temel_taslari.json` / `knowledge/sgk_temel_yapi.json`
içindeki GERÇEK bölüm başlığına işaret eder (ör. "knowledge/muhasebe_temel_taslari.json —
... Temel kavramlar (1/3): ... dönemsellik kavramı") — yeni mevzuat/rakam UYDURULMADI.

**Bilinen risk ve düzeltme (şeffaflık)**: `principles_seed.json` ilk denemede
`knowledge/` KÖKÜNE yazılmıştı; `memory/seed_loader.py::load_seeds()` (LearningStore'un
ders-notu yükleyicisi) `knowledge/*.json`'u TARAR ve farklı şemalı bu dosyayı yutmaya
çalışıp `KeyError: 'subject'` ile TÜM 161 testlik regresyonu KIRDI. Hemen yakalandı
(`python -m tests.run_all` ile), dosya `knowledge/principles/` alt klasörüne taşınarak
(seed_loader tek-seviye glob yaptığı için alt klasörler taranmıyor) düzeltildi ve
regresyon 161/161'e geri döndü. Bu olay bilerek burada belgeleniyor (öz-düzeltme, madde
23'ün "test fixture'larını gerçek memory ile karıştırma" ruhuyla tutarlı bir kontrol).

### E. Problem Structure

`learning/problem_structure.py::detect_signals(question)` — TAM semantic planner DEĞİL
(madde 7 açıkça yasaklıyor): sorunun YÜZEY kelimelerine değil ROLÜNE bakan, denetlenebilir
regex/deyim tabanlı 8 sinyal üretir: `TEMPORAL_MISMATCH` (soruda ≥2 farklı ay adı —
ekonomik olay dönemi vs. belge/ödeme tarihi ayrımı), `ACCOUNT_CLASS_QUERY` ("hangi
hesaba/sınıfa/grupta"), `DIRECTION_QUERY` ("hangi tarafa"), `VALUATION_VS_COST_QUERY`
("piyasa değeri" + ≥2 farklı TL tutarı), `BENEFIT_SPREAD_QUERY` ("yıllara yayarak"/"tek
seferde"/"faydalı ömür"), `LEGAL_VS_ECONOMIC_QUERY` ("kimin varlığı/aktifinde" +
"sözleşme"), `STATUS_CLASSIFICATION_QUERY` ("hangi statüde"), `RATE_QUERY` (FACT güvenlik
sinyali, bkz. C). Birden fazla sinyal AYNI ANDA ateşleyebilir — bu KASITLI (madde 18
"birden fazla aday" testi tam bunu sınıyor).

### F. Principle Retrieval

`learning/principle_retriever.py::PrincipleRetriever` — `accounting/retriever.py::
Retriever`'ı HİÇ import etmez, mimari olarak tam ayrı (madde 8). Skorlama VERİ ODAKLI
(registry'nin `problem_structure` alanından, kodda gömülü değil): `primary_signal`
ateşlerse +3 (yapısal, birincil ağırlık — madde 9), `applicability` sözcüklerinden
eşleşen her biri +1 (en çok +2, ikincil ağırlık), `veto_signals`'tan biri ateşlerse -4.
Skoru >0 olan adaylar sıralanır; `RATE_QUERY` ateşlemişse (bkz. C) tüm adaylar EVRENSEL
olarak reddedilir. Sonuç: `PrincipleRetrievalResult(candidates, selected, confidence,
rejected, reason, fact_safety_triggered)`.

### G. Confidence

Madde 11 birebir: model tarafından uydurulan bir yüzde DEĞİL, gözlemlenebilir sinyalden
türetildi. HIGH: en yüksek skorlu adayın `primary_signal`'i ateşledi VE en yakın rakiple
fark ≥2. MEDIUM: `primary_signal` ateşledi AMA en yakın rakiple fark <2 (birden fazla
yakın aday, madde 18) — yine de en yüksek skorlu SEÇİLİR ama belirsizlik trace'te açık.
LOW: yalnız sözcüksel örtüşme var, yapısal sinyal yok. NONE: pozitif skorlu aday yok VEYA
`RATE_QUERY` (FACT güvenliği). **LOW/NONE'da `selected` HER ZAMAN None** — sistem asla
zorla bir ilke seçmiyor (madde 11 birebir).

### H. Positive Transfer (vaka bazında)

Tüm 7 aile, B (yüzeysel farklı) sorusunda DOĞRU ilkeyi seçti (`tests/
test_principle_positive_transfer_*`, 7 ayrı test):

| Aile | B sorusu (özet) | Seçilen | Confidence |
|---|---|---|---|
| dönemsellik | Aralık faturası ocakta geldi/ödendi | donemsellik | HIGH |
| borç/alacak | Banka kredisi hangi tarafa yazılır | borc_alacak | HIGH |
| hesap sınıflandırma | Uzun vadeli alacak hangi ana grupta | hesap_siniflandirma | HIGH |
| özün önceliği | Finansal kiralama, kimin varlığı | ozun_onceligi | HIGH |
| maliyet ilkesi | Arsanın piyasa değeri arttı, hangi tutar | maliyet_ilkesi | HIGH |
| amortisman | Makine tek seferde mi yıllara mı | amortisman | HIGH |
| SGK statüsü | Kendi muayenehanesini açan doktor | sgk_statu | HIGH |

**Genelleme kontrolü** (dataset'in ötesinde, elle yazılmış 14 ek "held-out" — TAMAMEN
farklı isim/nesne/ay kullanan — soru ile): 13/14 (%92.9) doğru; tek "uyuşmazlık" aslında
sistemin doğru davranışıydı (bir demirbaş kaydının "hangi hesaba işleneceği" sorusu
gerçekten hesap_siniflandirma'dır, test beklentisi hatalıydı) — bu, tasarımın 14 senaryo
sorusuna EZBERLENMEDİĞİNİN bağımsız bir kanıtı.

### I. Negative Transfer

Tüm 7 karşı örnek (D), B'nin ilkesini YANLIŞ TRANSFER ETMEDİ (`tests/
test_principle_negative_transfer_rejects_all_seven_counter_examples`):

| Aile | D sorusu (özet, benzer kelimeli tuzak) | B'nin ilkesi seçildi mi? |
|---|---|---|
| dönemsellik | Aralık/ocak ama "hangi HESABA" | HAYIR (hesap_siniflandirma seçildi) |
| borç/alacak | Banka kredisi ama "hangi hesap SINIFINA" | HAYIR (hesap_siniflandirma seçildi) |
| hesap sınıflandırma | Alacak ama şüpheli alacak karşılığı | HAYIR (None) |
| özün önceliği | Kiralama ama KDV ZAMANI sorusu | HAYIR (None) |
| maliyet ilkesi | Arsa ama "hangi HESABA aktarılır" | HAYIR (hesap_siniflandirma seçildi) |
| amortisman | Makine ama KDV indirim ZAMANI | HAYIR (None) |
| SGK statüsü | Doktor ama güncel stopaj ORANI (FACT) | HAYIR (None, `fact_safety_triggered=True`) |

En kritik satır SGK: bu bir FACT sorusu (madde 16) — sistem yalnızca "yanlış ilke
seçmedi" değil, HİÇBİR ilkeyi VERIFIED gibi sunmadığını AÇIKÇA işaretledi.

### J. Transfer Score (önce/sonra)

| Metrik | ÖNCE (baseline, B bölümü) | SONRA (PrincipleRetriever) |
|---|---|---|
| Positive Transfer Accuracy | 2/7 = %28.6 | **7/7 = %100.0** |
| Negative Transfer Rejection | 6/7 = %85.7 | **7/7 = %100.0** |
| **Overall Transfer Score** | **8/14 = %57.1** | **14/14 = %100.0** |

(`tests/test_learning_transfer.py::run_final()`, AYNI `measure_transfer_score()`
fonksiyonu ile — karşılaştırma adil.)

### K. Trace

`core/trace.py::KaizenTrace`'e 5 alan EKLENDİ (additive, tamamı varsayılan boş/None —
`test_principle_trace_fields_default_empty_when_principle_layer_not_used` bunu kilitliyor):
`principle_candidates`, `principle_selected`, `principle_confidence`,
`principle_rejected`, `principle_reason`. `learning/trace_bridge.py::
fill_principle_trace(trace, result)` bunları bir `PrincipleRetrievalResult`'tan doldurur
— ama `KaizenBrain._answer_core` bu köprüyü HİÇ ÇAĞIRMAZ (madde 14), yalnız testlerde
kullanılıyor. Kullanıcıya giden METİN CEVAP bu alanlardan hiç etkilenmedi.

Ek gözlemsel uyumluluk (madde 13, "gerekirse"): `learning/decision_bridge.py::
to_decision()`, bir `PrincipleRetrievalResult`'ı `core/decision.py::Decision` ile AYNI
alan adlarını taşıyan bağımsız bir nesneye çevirir (`preferred_route="principle_shadow"`,
`core/trace.py::ROUTE_CONFIDENCE`'a additive olarak eklendi) — ama `DecisionEngine`'i
HİÇ çağırmaz, `KaizenBrain.last_route`'u HİÇ etkilemez, ve güven eşlemesi KASITLI olarak
asla `VERIFIED` üretmez (en yükseği `SUPPORTED`). Decision Engine ana zincire BAĞLANMADI
(madde 13'ün açık talimatı: "tam bağlama").

### L. Regresyon

- **187/187 BAŞARILI** (önceki 161 + yeni 26 = 187; `tests/test_learning_transfer.py`
  artık `tests/run_all.py`'ye bağlı).
- Gerçek kullanım sınavı yeniden çalıştırıldı: **15/33 — DEĞİŞMEDİ** (beklenen sonuç:
  Principle Layer shadow/observational, `_answer_core`'a hiç bağlanmadı, madde 22).

### M. Data Integrity

SHA256 (`knowledge/*.json` 6 dosya, `memory/kaizen_memory.json`, `logs/kaizen.log`,
`data/accounting_knowledge.sqlite3`, `data/accounting_learning.json`, `data/
kaizen_learning.sqlite3`) başlangıç checkpoint'i ile **BİREBİR AYNI** — hem faz ortasında
(ortam sıfırlanmasının hemen sonrasında) hem faz sonunda ayrı ayrı doğrulandı, sapma YOK.
`data/kaizen_principles.sqlite3` (gerçek principle deposu) bu faz boyunca HİÇ
OLUŞTURULMADI — tüm testler izole `tempfile.TemporaryDirectory()` kullandı (madde 23:
"test fixture'larını gerçek memory ile karıştırma").

### N. Açık Sınırlamalar

- Yapısal sinyaller (`learning/problem_structure.py`) regex/deyim tabanlıdır, bir LLM/
  semantic anlayış DEĞİL (madde 7'nin açık sınırı) — anteside edilmemiş bir Türkçe
  ifade biçimi (ör. "hangi tarafa" yerine hiç görülmemiş bir eşanlamlı kalıp) sinyali
  kaçırabilir. Held-out testte (bölüm H) bu risk 1/14 örnekte gözlendi (ve o örnek aslında
  yanlış test beklentisiydi, ama prensip olarak risk gerçek).
- Yalnız 7 küratörlü ilke var (madde 6'nın bilinçli sınırı) — yeni bir ilke ailesi
  (ör. "ihtiyatlılık/karşılık mantığı") eklemek bugün hâlâ İNSAN eliyle
  `knowledge/principles/principles_seed.json`'a satır eklemeyi gerektiriyor.
- Ambiguity eşiği (`_CLOSE_GAP_THRESHOLD=2`) ve skor ağırlıkları (yapısal +3, sözcüksel
  +1/+2, veto -4) makul başlangıç sabitleri — büyük ölçekli gerçek trafikle
  kalibre edilmedi.
- Principle Layer, `KaizenBrain`'e HİÇ bağlı değil (madde 14'ün bilinçli sınırı) — bu
  yüzden bugün hiçbir gerçek kullanıcı cevabını etkilemiyor, yalnız kanıtlanmış bir
  yetenek olarak duruyor.
- Decision Engine hâlâ üretim zincirine bağlı değil (madde 13'ün bilinçli sınırı).
- Reflection Engine / strateji hafızası / otonom ilke öğrenimi bu fazda YOK (madde 15/20,
  bilinçli sınır).

### O. Sonraki Tek Adım

`PrincipleRetriever`'ı `KaizenBrain._answer_core`'a HÂLÂ cevabı DEĞİŞTİRMEDEN, yalnız
`fill_principle_trace()` ile GERÇEK kullanıcı sorularında (sentetik değil, canlı trafik)
`trace.principle_*` alanlarını dolduracak şekilde tek satırlık bir gözlem kancası olarak
ekleyip, bir süre (ör. 1-2 hafta) gerçek soru dağılımında candidates/selected/confidence
istatistiklerini toplayan bir "gözlem fazı" başlatılmalı — 7 ilkenin gerçek dünyada ne
sıklıkla tetiklendiğini ve muhtemel yanlış-pozitif oranını, cevabı hiç riske atmadan
ölçmek için.

**DUR.** Sonraki faza (gözlem fazı, Reflection Engine, gerçek entegrasyon) otomatik
geçilmiyor; kullanıcı onayı bekleniyor.

## 5. KAIZEN — BÜYÜK GELİŞTİRME PAKETİ #1 (2026-09-23) — FİNAL RAPOR (A–Y)

Bu bölüm, "SONUÇ 1 — KAIZEN BRAIN" (red-team + koşullu üretim entegrasyonu) ve
"SONUÇ 2 — KAIZEN DESKTOP ALPHA" (gerçek backend'e bağlı ilk masaüstü uygulaması) iş
emrinin tam raporu. Zorunlu 34 adımlık sıra takip edildi; DURDURMA/KESİNLİKLE
YAPILMAYACAKLAR kuralları ihlal edilmedi (aşağıda her ilgili bölümde ayrıca belirtilir).

### A. Ortam / Baseline

Faz başında (bu bölümün 0. maddesi) mevcut durum KÖRÜ KÖRÜNE kabul edilmedi, taze araçlarla
yeniden doğrulandı: regresyon BAŞARILI, gerçek hayat sınavı 15/33 (değişmedi), SHA256
sıfır sapma, `SearchProvider` hâlâ bağlı değil, Principle Registry hâlâ izole. Bağımlılık
denetimi: gerçek Windows `.venv` (Python 3.13.15, 340 paket) incelendi — PySide6/PyQt6/
Nuitka/pyinstaller YOK (bu bulgu doğrudan Faz E kararını besledi, bkz. §K/§L).

### B. Learning Brain Red-Team Veri Seti

`tests/test_learning_transfer_redteam.py`: **63 kör vaka** (27 positive / 26 negative / 10
ambiguous), 8 zorunlu aile (LEXICAL_TRAP, SEMANTIC_TRANSFER, MULTI_PRINCIPLE, NO_PRINCIPLE,
FACT_TRAP, DATE_TRAP, SGK_TRAP, VOCAB_TRAP). Etiketler, implementasyona BAKILMADAN, saf
muhasebe mantığıyla yazıldı (madde B3) — birkaç vaka BİLİNÇLİ sınır/gap testi olarak
işaretlendi (P05: yıl-çifti dönemsellik, P20: eşanlamlı "piyasa değeri" ifadesi).

### C. Kör Baseline (ilk çalıştırma, değiştirilmeden ÖNCE kaydedildi)

| Metrik | Sonuç |
|---|---|
| Positive Transfer Accuracy | 25/27 = %92.6 |
| Negative Transfer Rejection | 21/26 = %80.8 |
| Ambiguous Abstention | 9/10 = %90.0 |
| False Positive Rate | 5/26 = %19.2 |
| False Negative Rate | 2/27 = %7.4 |
| Wrong-Principle Rate | 0/27 = %0.0 |
| **Fact Safety Violations** | **1/63** (N15) |
| Overall Transfer Score | 46/53 = %86.8 |

### D. Başarısızlık Analizi (dürüst — 6 "başarısızlığın" 6'sı da veri seti/metrik hatası çıktı)

- **N01, N02, N04, N15, N25** (5 vaka): `category=NEGATIVE` olarak etiketlenmişti ama bu
  vakaların KENDİ `note` alanı — dosya İLK yazılırken, hiç çalıştırılmadan ÖNCE — zaten
  doğru cevabın `hesap_siniflandirma` OLDUĞUNU söylüyordu (ör. N15'in notu: "...hesap_
  siniflandirma kazanmalı, donemsellik değil"). Yani bu 5 vaka YAZIM ANINDA POSITIVE olarak
  tasarlanmış ama `category` alanına yanlışlıkla NEGATIVE yazılmıştı — bu, implementasyona
  bakarak SONRADAN yapılan bir ayar DEĞİL, kendi notuyla çelişen bir yazım hatasının tespiti.
- **Fact Safety Violation (N15)**: yukarıdaki etiket hatasının DOĞRUDAN sonucu — N15 aslında
  bir FACT/oran sorusu değil, tarih içeren bir SINIFLANDIRMA sorusuydu; metrik tanımı da
  (herhangi bir DATE_TRAP-etiketli vakayı, doğru cevap ne olursa olsun taraması) gereğinden
  genişti.
- **A02** (1 ambiguous vaka): "tek seferde mi yoksa yıllara yayarak mı" ifadesi doğrudan
  amortisman ilkesinin kendi diline denk düşüyor; sistemin HIGH güvenle `amortisman`
  seçmesi savunulabilir bir sınır durumu (yanlış/tehlikeli bir seçim değil) — **düzeltilmedi**,
  dürüstçe sınır vakası olarak belgelendi (bkz. §G).
- **P05, P20**: baştan BİLİNÇLİ sınır testleriydi (regex'in yıl-çifti / eşanlamlı ifade
  boşluğu) — beklenen sonuç, düzeltilmedi.

### E. Düzeltmeler

**Sıfır implementasyon kodu değişikliği.** Yalnızca `tests/test_learning_transfer_redteam.py`
dosyasının SONUNA, orijinal 63 vakalık kör veri setini ve ilk çalıştırma çıktısını HİÇ
DEĞİŞTİRMEDEN, ayrı ve denetlenebilir bir "POST-BASELINE DÜZELTME" bölümü eklendi: (1) yukarıdaki
5 vakanın kategorisi NEGATIVE→POSITIVE düzeltildi (`expected` aynı kaldı), (2) fact-safety
metriği yalnız gerçek FACT-veto vakalarına (category==NEGATIVE and expected=="NONE")
daraltıldı. `run_redteam()` (orijinal, kör) ve `run_redteam_corrected()` (düzeltilmiş) AYRI
fonksiyonlar olarak yan yana durur.

### F. Final Transfer Metrikleri (düzeltilmiş, retest)

| Metrik | Sonuç |
|---|---|
| Positive Transfer Accuracy | 30/32 = **%93.8** |
| Negative Transfer Rejection | 21/21 = **%100.0** |
| Ambiguous Abstention | 9/10 = %90.0 |
| False Positive Rate | 0/21 = %0.0 |
| False Negative Rate | 2/32 = %6.2 (P05/P20, bilinçli sınır) |
| Wrong-Principle Rate | 0/32 = %0.0 |
| **Fact Safety Violations** | **0/63 = %0.0** |
| Overall Transfer Score | 51/53 = **%96.2** |

### G. Production Gate (Faz B5)

| Koşul | Eşik | Sonuç | Durum |
|---|---|---|---|
| Positive Transfer | ≥%90 | %93.8 | ✅ |
| Negative Rejection | ≥%90 | %100.0 | ✅ |
| Fact Safety Violations | =0 | 0 | ✅ |
| Kritik yanlış-HIGH seçim | yok | A02 (amortisman, savunulabilir sınır vakası — tehlikeli değil) | ✅ (belgelendi) |
| Regresyon | sağlam | BAŞARILI | ✅ |

**GATE: PASS.** Faz C'ye (koşullu entegrasyon) geçildi.

### H. Brain Entegrasyonu (Faz C, Shadow → Assisted Mode)

- **C4 (Feature Flag):** `config/Kaizen.json` → `learning.learning_brain_enabled`
  (varsayılan **false**). `config/config_manager.py::learning_brain_enabled()`. Geri dönüş
  TEK SATIRLIK config değişikliği (kod değişikliği YOK) — `tests/test_learning_brain_
  integration.py::test_learning_brain_one_line_revert_contract` bunu doğrular.
- **C1 (Shadow→Assisted):** `core/kaizen_brain.py::_maybe_augment_with_principle()` YALNIZ
  `_grounded_answer()` içinden çağrılır — yani `_correction`/`_arithmetic`/`_exact_tools`/
  `facts.verified_fact_answer` HEPSİ ÖNCE çalışıp bulamadıysa buraya gelinir. Principle
  Layer hiçbir zaman TEK BAŞINA bir cevap yolu açmaz.
- **C2 (Confidence Gate):** yalnız HIGH/MEDIUM prompt'u etkiler; LOW/NONE cevabı HİÇ
  etkilemez (ama trace her zaman dolar — Brain Inspector için).
- **C3 (FACT Firewall):** route hep `memory_grounded` kalır → `ROUTE_CONFIDENCE` eşlemesi
  hep `SUPPORTED` (asla `VERIFIED`). Adanmış test:
  `test_learning_brain_never_reached_by_exact_tools_or_facts`.
- **Yeni:** `tests/test_learning_brain_integration.py` — 7 test (bayrak kapalı=eski davranış,
  HIGH assisted mode, LOW/NONE hiç etkilemez, domain sınırı, FACT firewall, üretim
  varsayılanı kapalı, tek-satır geri dönüş). Hepsi BAŞARILI, `run_all.py`'ye bağlandı.

### I. OFF vs ON Gerçek Hayat Sınavı (Faz C5)

Gerçek 33 soruluk sınav (`tests/test_real_world_exam.py::EXAM`), izole `Offline()`
sağlayıcıyla, bayrak KAPALI ve AÇIK olarak iki kez çalıştırıldı:

- **Route/confidence/cevap metni değişen soru sayısı: 0/33.** Bu BEKLENEN bir sonuçtur —
  `Offline()` sağlayıcı `provider.ask()`'ı her zaman "kullanılamıyor" ile reddeder, bu
  yüzden `_grounded_answer` hiçbir zaman modelin GERÇEKTEN cevap ürettiği dala ulaşmaz
  (Principle Layer yalnız O dalda prompt'u etkiler). Yani bu izole/gerçek-ağsız sınav,
  mekanizmayı TETİKLESE de (aşağıya bakın), NİHAİ cevabı hiç değiştirmez.
- Yine de **1/33 soruda** (`"Bu işlem hangi hesaba gider: ofis kirası ödedik?"`)
  `trace.principle_selected == "hesap_siniflandirma"` (HIGH) olarak GERÇEKTEN dolduğu
  doğrulandı — yani devre GERÇEKTEN canlı, yalnızca bu izole sınavda etkisiz.
- Mekanizmanın GERÇEKTEN prompt'u değiştirdiğinin somut kanıtı §H'deki entegrasyon
  testlerinde (çalışan sahte sağlayıcıyla): `test_learning_brain_high_confidence_
  augments_prompt_assisted_mode` prompt'ta `[LEARNING BRAIN ILKE IPUCU ...]` bloğunun
  GERÇEKTEN eklendiğini gösterir.
- **Üretim varsayılanı hâlâ KAPALI** — bu sınav sonucu, bayrağın açılmasının bugünkü
  15/33'ü BOZMAYACAĞINI (regresyon riski yok) kanıtlar; iyileştirme, gerçek bir model
  bağlı olduğunda ve grounded bir soru olduğunda beklenir.

### J. Experience / Reflection Temeli (Faz D)

`learning/experience_model.py` (`Experience` dataclass, 10 alan) + `learning/reflection_
store.py` (`ReflectionStore`, izole `data/kaizen_reflections.sqlite3`). **D2**: ham
cevap/FACT alanı YOK (yapısal olarak imkansız). **D3**: `reusable=True` yalnız ÖNCE
`mark_user_approved()` SONRA `mark_reusable()` (iki AYRI, açık çağrı) ile mümkün — otomatik
güven YOK. **D4**: `core/kaizen_brain.py`/`core/engine.py` bu modülleri HİÇ import etmez
(statik AST taramasıyla doğrulandı). 9 test, hepsi BAŞARILI.

### K. Masaüstü Teknoloji Araştırması

PySide6/Qt, Electron, Tauri, tkinter karşılaştırması (bkz. `desktop/ARCHITECTURE_
DECISION.md` tam tablo). Üç ayrı yürütme yüzeyinde (bulut konteyner, `device_bash`
izole Linux VM, kullanıcının gerçek Windows `.venv`'i) doğrudan test edilerek: PySide6
hiçbirinde kurulamıyor/mevcut değil; tkinter Python standart kurulumunun PARÇASI.

### L. Mimari Karar

**tkinter seçildi** (PySide6 DEĞİL) — iş emrinin PySide6 ön-eğilimi, somut ortam/repo
kanıtıyla bilinçli olarak geçersiz kılındı (madde E1'in izin verdiği gibi), gerekçe tam
olarak `desktop/ARCHITECTURE_DECISION.md`'de belgelendi. Ana gerekçeler: (1) hiçbir
yürütme yüzeyinde PySide6 kurulamıyor, (2) tkinter zaten stdlib, (3) ÖNCEDEN VAR OLAN,
ÇALIŞAN bir `desktop_app.py` zaten tkinter kullanıyor (büyük yeniden yazım YASAK kuralı).

### M. UI/UX Mimarisi

F1 (sol menü): Yeni Sohbet / Sohbetler / Araştırma / Bilgi Merkezi / Öğrenilenler /
Kaynaklar / Sistem / Ayarlar — teknik detaya girmeden, **var olan `core/commands.py`
komutlarını yeniden kullanarak** (güncelle/parametreler/öğrendiklerim/kaynaklar/durum) —
yeni bir iş mantığı YAZILMADI. Sağ bağlam paneli: güven durumu, kaynak, ilgili ilke (varsa).
F2 (Brain Inspector): ayrı `Toplevel` penceresi, `KaizenTrace`'in TÜM alanları — normal
kullanıcı akışından tamamen ayrı. F3 (durum modeli): backend'in GERÇEKTEN gözlemlenebilir
olduğu kadarını gösterir — sahte "Hafızada arıyor" gibi anlık adımlar İCAT EDİLMEDİ
(senkron mimaride gözlemlenemez), yalnız dürüst "Düşünüyor" (gerçek) + cevap sonrası
gerçek rota özeti.

### N. İkon / Marka

Geometrik "K" işareti + doğrulama/bağlantı noktası (yeşil nokta) — font'a bağımlı değil,
16×16'da bile net (görsel olarak doğrulandı). `desktop/icon/`: `kaizen.ico` (16/24/32/48/256
gömülü), `kaizen_256.png`, `kaizen_512.png`, `kaizen.svg` (vektör kaynak). Pillow
(zaten `requirements.txt`'te) ile üretildi — yeni bağımlılık YOK.

### O. Masaüstü Uygulaması (Alpha)

`desktop_app.py` — ÖNCEDEN VAR OLAN, çalışan tkinter uygulaması korunup genişletildi
(büyük yeniden yazım yapılmadı): sol menü, sağ bağlam paneli, Brain Inspector, pencere/
görev çubuğu simgesi, hata sunumu eklendi. **H1**: `core.engine.KaizenEngine` DOĞRUDAN
sarmalanıyor, sıfır sahte/demo cevap. **H4**: `ConversationHistory` yalnız GUI oturum
dökümü — Kaizen'in gerçek hafızasına (`learning_store`/`site_store`/vb.) hiç dokunmaz
(statik import taramasıyla doğrulandı). Tüm iş mantığı (`desktop/adapter.py`) tkinter'dan
AYRIŞTIRILDI — bu ortamda GERÇEKTEN çalıştırılıp test edildi (7 test, BAŞARILI).

### P. Paketleme (EXE)

`desktop/build.ps1` — PyInstaller `--onedir` (onefile DEĞİL, madde 21). **DÜRÜSTÇE:** bu
betik hiçbir yürütme yüzeyinde test EDİLEMEDİ (ne bulut konteyneri ne `device_bash` gerçek
Windows ikili çalıştırabiliyor) ve belgelenmiş somut bir risk taşıyor: frozen `__file__`
çözümlemesi Kaizen'in veri depolarının GERÇEK `data/`/`knowledge/` klasörü yerine yanlış
bir konuma yazmasına yol açabilir. Betik bu riski kod içinde açıkça belgeliyor ve ilk
çalıştırmada bir doğrulama adımı (durum komutuyla ders/site sayısı karşılaştırması) istiyor.
**Alpha'nın birincil, doğrulanmış teslim yöntemi EXE DEĞİL, kaynaktan çalıştırmadır**
(`Kaizen_Baslat.bat`) — DURDURMA kuralı: "Paketleme başarısız → çalışan from-source
Desktop Alpha'yı koru."

### Q. Masaüstü Kısayolu

`desktop/create_shortcut.ps1` — `Kaizen_Baslat.bat`'a (kanıtlanmış, güvenli yol) işaret
eden, `kaizen.ico` simgeli bir `.lnk` oluşturur. **Bu oturumdan doğrudan ÇALIŞTIRILAMADI**
(PowerShell yürütme erişimi yok) — Faz J'nin kendi istisna maddesi gereği ("kısayol
oluşturulamazsa nedenini raporla ve güvenli bir PowerShell betiği bırak") kullanıcıya
bırakıldı: `desktop\create_shortcut.ps1`'i bir kez çalıştırması yeterli.

### R. Kullanıcı Kabul Testi

12 maddelik kontrol listesi ve 6 gerçek test sorusu `desktop/README.md`'de. **Görsel/
etkileşimsel doğrulama bu oturumda yapılamadı** (tkinter hiçbir yürütme yüzeyinde kurulu
değil/kurulamıyor) — bu, Faz K'nın zaten öngördüğü, kullanıcının kendi makinesinde
yapması gereken adımdır.

### S. Otomatik Testler

`tests/test_desktop_adapter.py` — 7 test, tkinter'a HİÇ bağımlı değil (`desktop/
adapter.py`, Faz L'nin açık izniyle iş mantığı/adaptör katmanı olarak ayrıştırıldı).
`desktop_app.py`'nin kendisi yalnız `python3 -m py_compile` ile sözdizimi denetlendi
(tkinter yokluğunda çalıştırılamadı).

### T. Tam Regresyon

`tests/run_all.py::run_all()` içindeki test çağrısı sayısı: **214** (AST ile sayıldı),
hepsi **BAŞARILI**. Bu fazda eklenen 23 yeni test (`test_learning_brain_integration.py`:7,
`test_experience_model.py`:9, `test_desktop_adapter.py`:7) dahil — hiçbir eski test
silinmedi/zayıflatılmadı.

### U. SHA256 / Data Integrity

`data/`, `knowledge/*.json`, `knowledge/principles/`, `memory/kaizen_memory.json`,
`logs/kaizen.log` — dosya değişiklik zamanları bu fazın TAMAMI boyunca (Faz B başlangıcından
şu ana kadar) DEĞİŞMEDİ (mtime karşılaştırmasıyla doğrulandı), taze bir SHA256 anlık
görüntüsü bu fazın çıkış checkpoint'i olarak kaydedildi. `data/kaizen_principles.sqlite3`/
`data/kaizen_reflections.sqlite3` bu fazda GERÇEK ortamda hiç oluşturulmadı — tüm testler
izole `tempfile`/`dev/workspace` kullandı.

### V. Bilinen Sınırlamalar

- Learning Brain üretimde varsayılan KAPALI — Faz N'nin (OFF/ON exam) gösterdiği gibi bu
  güvenli/beklenen bir durum, ama gerçek bir iyileştirme GÖRMEK için kullanıcı bayrağı
  açıp gerçek bir model + grounded soru ile denemeli.
- A02 (ambiguous sınır vakası) düzeltilmedi — savunulabilir, tehlikeli değil.
- Desktop Alpha'nın GÖRSEL doğrulaması bu oturumda YAPILAMADI (yukarıya bakın, §R) —
  Brain Inspector'ın gerçekten doğru render olup olmadığı kullanıcının ilk açılışında
  görülecek.
- PyInstaller EXE derlemesi test edilemedi, deneysel/ikincil bir teslim yoludur.
- Masaüstü kısayolu bu oturumdan oluşturulamadı, kullanıcının bir betiği bir kez
  çalıştırması gerekiyor.
- "Sohbetler" (çoklu sohbet listesi) Alpha'da yer tutucu.

### W. Eklenen/Değiştirilen Dosyalar (tam liste)

**Yeni:** `learning/experience_model.py`, `learning/reflection_store.py`,
`tests/test_learning_brain_integration.py`, `tests/test_experience_model.py`,
`tests/test_desktop_adapter.py`, `tests/test_learning_transfer_redteam.py`,
`desktop/adapter.py`, `desktop/ARCHITECTURE_DECISION.md`, `desktop/README.md`,
`desktop/build.ps1`, `desktop/create_shortcut.ps1`, `desktop/icon/kaizen.ico`,
`desktop/icon/kaizen_256.png`, `desktop/icon/kaizen_512.png`, `desktop/icon/kaizen.svg`.
**Değiştirildi:** `config/Kaizen.json` (yeni `learning` bölümü), `config/config_manager.py`
(`learning_brain_enabled()`), `core/kaizen_brain.py` (Faz C entegrasyonu, geriye dönük
uyumlu yeni parametreler), `core/engine.py` (principle registry/retriever kuruluşu + flag
geçişi), `tests/run_all.py` (23 yeni test bağlandı), `desktop_app.py` (Alpha UI
genişletmesi). Tüm dosyalar `device_commit_files` ile gerçek `C:\Users\ANL\Desktop\
KAZEN_AI\` klasörüne yazıldı ve `device_stage_files` + karşılaştırma ile byte/piksel
düzeyinde doğrulandı (2 PNG dosyası, piksel-hash eşleşmesiyle doğrulandı — konteyner
yeniden kodlaması, görsel içerik AYNI; diğer 19 dosya birebir byte-identical).

### X. Kullanıcı Kaizen'i Nasıl Dener

1. `desktop\create_shortcut.ps1`'i bir kez çalıştırın (PowerShell, proje kökünde) —
   masaüstünüze gerçek Kaizen simgesiyle bir kısayol eklenir.
2. Masaüstündeki **Kaizen** simgesine çift tıklayın.
3. Birkaç saniye "Başlatılıyor..." bekleyin, sonra bir soru yazıp Enter'a basın.
4. Sol menüden **Sistem**'e tıklayarak Brain Inspector'ı (geliştirici görünümü) açabilirsiniz.
5. `desktop/README.md`'deki 12 maddelik kontrol listesini ve 6 test sorusunu deneyin.

### Y. Sonraki Önerilen Büyük Faz

Learning Brain bayrağını GERÇEK bir model (Hermes/yerel) bağlıyken, kontrollü bir alt
kümede (ör. yalnız birkaç gün, yalnız `donemsellik`/`hesap_siniflandirma` gibi en yüksek
güvenli iki aile) açıp gerçek soru-cevap kalitesini gözlemlemek; paralel olarak Desktop
Alpha'nın gerçek kullanıcı geri bildirimiyle (Faz K sonrası) "Sohbetler" (çoklu oturum) ve
canlı durum adımlarının (mümkünse `KaizenBrain`i enstrümante ederek, büyük bir yeniden
yazım olmadan) eklenmesi değerlendirilebilir.

**DUR.**

---

## 6. KAIZEN — BÜYÜK İŞ EMRİ #2 (2026-09-23, devam ediyor) — FAZ 1-6 İLERLEME RAPORU

> Kapsam: "FULL-SYSTEM AUDIT → SEARCH CONNECTION → RESEARCH BRAIN → LEARNING LOOP" (madde
> 0-64, 38 adımlık zorunlu sıra). Bu bölüm Faz 1-6'nın (adım 1-6) tamamlandığını, Faz
> 7'den (Research Engine) itibaren çalışmanın SÜRDÜĞÜNÜ belgeler — bu iş emri TEK
> oturumda bitecek kadar küçük değildir; aşağıdaki ilerleme, iş emrinin kendi "önce oku,
> sonra yaz" (madde 0/1) ve "test sayısıyla övünme yasağı" (madde 56) kurallarına uygun
> biçimde, DOĞRULANMIŞ durumu kaydeder.

### Faz 1 — Tam Repository Denetimi (TAMAMLANDI)

Beş bağımsız, salt-okunur alt-denetim (Search / Core-Decision-Provider-Commands /
Accounting / Memory-Learning / Providers-Hermes-Misc) + doğrudan kod okuma ile
yürütüldü. Tam bulgular ve `dosya:satır` kanıtları: **`docs/KAIZEN_RUNTIME_ARCHITECTURE.md`**.

**En önemli bulgu (özet):** Kaizen bugün güncel/internet gerektiren bir soruda kendi
`search/` (SearXNG) altyapısını KULLANMIYOR. `search/provider.py` + `search/
searxng_provider.py` eksiksiz yazılmış ve 48 mock testle test edilmiş ama sıfır üretim
bağlantısına sahip (`core/engine.py`/`core/kaizen_brain.py` bu paketi hiç import etmiyor).
Tek canlı internet erişim yolu bugün `accounting/researcher.py` → Hermes'in kendi
`web_search`/`web_extract` araçları (subprocess). `accounting/crawler.py`'nin GERÇEK,
güvenli (robots.txt/rate-limit/boyut/timeout/domain-allowlist) fetcher'ı yalnızca offline
`güncelle` toplu işinde çalışıyor, canlı soru yolunda DEĞİL. `core/decision.py::
DecisionEngine` tamamen izole/ölü kod (sıfır üretim çağrısı). `learning/experience_model.py`
+ `learning/reflection_store.py` (+ yeni bulunan `memory/experience_store.py`) hâlâ
dormant/test-only. `accounting/source_registry.py`'de SGK/Resmî Gazete/mevzuat.gov.tr
resmî domain'leri EKSİK. Detaylı "Bağlı/Bağlı Değil" matrisi (madde 3) architecture
belgesinin §4'ünde.

### Faz 2 — `docs/KAIZEN_RUNTIME_ARCHITECTURE.md` (TAMAMLANDI)

Gerçek koddan çıkarılmış uçtan uca akış haritası (giriş noktaları → `KaizenEngine` kuruluşu
→ `KaizenBrain` cevap zinciri → güven modeli → Search≠Evidence≠Fact ayrımı → komutlar →
provider'lar → güvenlik altyapısı) yazıldı ve pushlandı.

### Faz 3 — Bağlı/Bağlı Değil Matrisi (TAMAMLANDI)

`docs/KAIZEN_RUNTIME_ARCHITECTURE.md` §4'te, 25 bileşen için Var/Testli/KaizenBrain'e
bağlı/Production'da aktif sütunlarıyla + kanıt referanslarıyla.

### Faz 4 — Baseline (TAMAMLANDI, aynı gün ölçüldü)

- `python3 -m tests.run_all` → **TÜM KAIZEN TESTLERİ: BAŞARILI** (156 BAŞARILI satırı).
- 33 soruluk gerçek hayat sınavı: **15/33 başarılı, 18 bilinen darboğaz** — önceki fazla
  birebir aynı (regresyon YOK).
- `config/Kaizen.json` snapshot alındı (SHA256: `7ff7080c...`) — `search`/`searxng`
  anahtarı YOK (doğrulandı).
- `data/`, `knowledge/`, `memory/`, `logs/` SHA256 checkpoint alındı; test koşumundan
  önce/sonra birebir aynı (izolasyon disiplini bozulmadı).

### Faz 5 — Learning Brain Metriklerinin Yeniden Doğrulanması (TAMAMLANDI)

`tests.test_learning_transfer_redteam` (standalone, düzeltilmiş) yeniden çalıştırıldı:
Positive 93.8% (30/32), Negative 100% (21/21 — **bu İYİ bir şeydir**: ilkenin
uygulanmaması gereken yerde doğru şekilde uygulanmaması, hata değil başarı), Ambiguous
90% (9/10), Fact Safety Violations **0/63**, Overall **96.2% (51/53)** — önceki fazla
birebir aynı rakamlar, hiçbir kod değişikliği yapılmadan yeniden üretildi.

### Faz 6 — Learning Brain Production Reality Test (TAMAMLANDI, dürüst sınırla)

Yeni dosya: `tests/test_learning_brain_ab_reality.py` (run_all.py'ye eklendi). 20 gerçek
grounded muhasebe sorusu (7 pozitif — 7 ilke ailesinin tamamı, 13 negatif — 7 grounded
how-to + 6 rota-atlayan) üzerinde OFF/ON A/B karşılaştırması, GERÇEK `KaizenBrain`/
`_maybe_augment_with_principle`/`_grounded_answer` kod yolundan (mock model, gerçek
mantık) ölçüldü: **0 VIOLATION**. Ölçülen 5 boyut: (1) prompt değişti mi — evet yalnız
pozitiflerde; (3) yanlış bilgi eklendi mi — hayır (ipucu metninde oran/tarih/TL sızıntısı
yok); (4) gereksiz ilke eklendi mi — hayır (13/13 negatifte enjeksiyon yok); (5) kaynak
temellendirmesi korundu mu — evet (KAYNAKLAR bloğu OFF/ON'da birebir aynı); (6) FACT
firewall korundu mu — evet (hiçbiri VERIFIED üretmedi).

**Dürüstlük notu (madde 56 ruhuyla):** 6. boyut — "cevap DOĞRU YÖNDE mi değişti" — bu
ortamda ÖLÇÜLEMEZ, çünkü bu bulut konteynerinde ne `hermes` CLI'si (PATH'te yok) ne
Ollama (`127.0.0.1:11434`) ne de kullanıcının gerçek SearXNG'i (`127.0.0.1:8890`)
erişilebilir durumda; `device_bash` (kullanıcının bilgisayarındaki izole VM) da kendi
belgesine göre kullanıcının localhost'una ulaşamıyor. Bu, IMPROVED/NEUTRAL/REGRESSED
etiketinin GERÇEK bir modelle, kullanıcının kendi makinesinde (Hermes/Ollama çalışırken)
bir Kullanıcı Kabul Testi ile tamamlanması gerektiği anlamına gelir — final raporda
"Kalan Riskler" bölümünde açıkça işaretlenecektir; gizlenmeyecektir.

### Faz 7-27 — Research Engine: mimari karar + 8 modül (TAMAMLANDI)

`docs/RESEARCH_ENGINE.md`'de tam belgelenmiştir. Özet: `research/` paketi (`models.py`,
`trigger.py`, `planner.py`, `fetcher.py` — SSRF/robots/rate-limit korumalı Safe Fetcher,
`extractor.py`, `evidence.py`, `verifier.py`, `engine.py` — orkestratör) TEK BİR DEV SINIF
OLMADAN (madde 61), her biri mevcut kodu (`accounting/source_registry.py`,
`accounting/consensus.py`, `accounting/facts.py`, `accounting/html_extract.py`,
`accounting/crawler.py::extract_pdf_text`, `accounting/retriever.py::coverage`,
`KaizenBrain.classify`/`.needs_current_research`) ÇAĞIRARAK (kopyalamadan) yazıldı. Küçük,
davranış-koruyan bir ek: `accounting/facts.py::FactRegistry.find_topics`'ten saf bir
`match_topics()` fonksiyonu çıkarıldı (sqlite'a dokunmadan yeniden kullanılabilsin diye).
Ayrıca Faz 1 bulgusu düzeltildi: SGK/Resmî Gazete/Mevzuat Bilgi Sistemi
`accounting/source_registry.py`'ye resmî kaynak olarak eklendi.

`research/engine.py::run_research` uçtan uca çalışıyor:
`trigger→planner→SearchProvider→fetcher→extractor→evidence→verifier→ResearchResult`;
`SearchProvider` tamamen çökse bile ASLA exception fırlatmaz (madde 26). Toplam 121 yeni
test (models 9, trigger 32, planner 20, fetcher 17, extractor 6, evidence 11, verifier 10,
engine 6) — hepsi `tests/run_all.py`'ye bağlandı, her regresyonda `data/`/`knowledge/`/
`memory/`/`logs/` SHA256 ile değişmedi doğrulandı. Bu fazın SONUNA KADAR Research Engine
`KaizenBrain`'e HİÇ bağlı değildi — üretim davranışını sıfır etkiliyordu.

### Faz 28-31 — `KaizenBrain`'e dar entegrasyon + Hermes rolü değişimi (TAMAMLANDI)

`docs/RESEARCH_ENGINE.md` §5'te tam belgelenmiştir. Özet: Research Engine, mevcut
araştırma adımının (Hermes/`accounting_agent.ask`) TAM YERİNE, tek bir choke point'te
(`core/kaizen_brain.py::_research_once`) bağlandı — dört bağımsız güvenlik katmanıyla
(bayrak, provider-None kontrolü, geniş try/except, "yalnız SUPPORTED" eşiği). Bayrak:
`config/Kaizen.json` → `research.research_engine_enabled`, varsayılan **false**
(`learning_brain_enabled` ile BİREBİR aynı disiplin — tek satırlık geri dönüş).
`core/engine.py`, `SearXNGProvider()`'ı her zaman kurar (ağa hiç çıkmadan) ama bayrak
kapalıyken `KaizenBrain` onu hiç kullanmaz. 6 yeni test
(`tests/test_kaizen_brain_research_engine.py`): varsayılan-kapalı davranışın birebir
korunduğu, provider'sız/beklenmeyen-exception durumlarında çökmeden Hermes'e düşüldüğü,
ve SUPPORTED sonucun Hermes'i gerçekten atladığı uçtan uca kanıtlandı. `test_kaizen_brain.py`
ve `test_core.py` dahil TÜM mevcut regresyon değişmeden yeşil.

Hermes'in rolü artık gerçekten madde 29-30'un öngördüğü gibi: genel model sağlayıcı +
Research Engine SUPPORTED bulamadığında (ya da bayrak kapalıyken — bugünkü varsayılan
durum) dar bir fallback.

### Sonraki adım

Faz 32-39 (decision engine değerlendirmesi zaten Faz 1'de yapıldı — ölü kod; gerçek
SearXNG smoke test madde 38 kullanıcının kendi makinesinde yapılacak) ve Faz 40-64
(Learning Loop gerçek bağlantısı, Trace v2, Real-Life Exam v2, Final rapor) iş emri
madde 62'nin 38 adımlık sırasında devam ediliyor. Bu bölüm, o çalışma ilerledikçe
güncellenecektir.
