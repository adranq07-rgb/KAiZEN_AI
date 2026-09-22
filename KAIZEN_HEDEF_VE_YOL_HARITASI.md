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
- **Kademe 3 (yerel LLM/yeni PC geldiğinde):** Cognee (veya benzeri) dar bir pilot olarak,
  yalnız serbest metin/deneyim tarafında denenir — sayısal parametre katmanına
  (`facts.py`/`consensus.py`) hiçbir zaman dokunmaz, o katman deterministik ve kaynaklı
  kalır. Graphiti aynı mantıkla yalnız gerçekten ihtiyaç doğarsa (ör. çok sayıda çakışan
  zamanlı gerçek biriktiğinde) değerlendirilir.

## 5. Ofis ve araçlar

Müşavirler Kulübü'nün 54 aracı `knowledge/kaizen_yetenekleri.json` içinde üç gruba ayrılmıştır
(sohbette `yetenekler` yazınca görünür):

- **Hazır:** KDV/tevkifat, stopaj, damga, gecikme zammı, amortisman, serbest meslek makbuzu, NPV/IRR, kredi tablosu,
  başabaş, IBAN, temel finansal oranlar, Excel/Word okuma-yazma, PDF birleştir/böl, görselden PDF.
- **Güncel parametre gerektirenler** (SGK/maaş, gelir vergisi dilimi, kıdem-ihbar, MTV, emlak, TÜFE kira artışı...):
  değerler koda gömülmez, süzgeçten geçmiş parametre defterinden gelir; konu eklendikçe açılır.
- **Sonraki aşama:** gümrük/ithalat, leasing–kredi, nakit akış, risk analizleri, dilekçe oluşturucu vb.

Ofis araçları (`tools/office_tools.py`) var olan dosyanın üzerine **yazmaz**; yeni ad ile kaydeder.
Excel/Word/PDF *bilgisi* (formüller, kısayollar, kayıt şablonları) `knowledge/*.json` içinde öğretilmiştir ve
açılışta hafızaya yüklenir (`memory/seed_loader.py`; dosya değişince eski sürüm otomatik yenilenir).

## 6. Komutlar

`yardım` · `durum` · `kaynaklar` · `parametreler` · `parametre <konu>` · `yetenekler` · `güncelle [sayfa]` ·
`öğrendiklerim` · `onayla: soru` · `düzelt: soru => doğru cevap`. Soru başına `muhasebe:` veya
`matematik:` yazmak isteğe bağlıdır.

## 7. Test ve kalite

`python -m tests.run_all` tüm testleri çalıştırır (28 test dosyası). `tests/test_golden_exam.py` mali
müşavir "altın sınavı"dır (70 soru, model kapalıyken): yeni yetenek eklerken oraya bir satır ekle.
`tests/test_self_learning.py` kendi kendini geliştiren beyni test eder. `tests/test_refresh_cli.py`
`--rebuild-only`'yi (yeniden tarama yapmadan süzgeci yenileme) test eder. `tests/test_text_tr.py`
ve `tests/test_retriever.py` Türkçe ek kırpma/eşleştirmeyi test eder. `tests/test_brain_manager.py`
`BrainManager`'ı (arama/doğrulama/öğrenme/depolama tek arayüzü) doğrudan test eder. Kural: hesap
ve kayıt cevapları için önce test, sonra kod.

## 8. Bilinen sınırlar (dürüst liste)

- İlk canlı tarama yapıldı (bkz. bölüm 4e). GİB artık `reference_only` değil: genel sayfaları JS
  ile dolduğu için taranamıyor, ama 4 resmî PDF (`cdn.gib.gov.tr`) seed olarak eklendi. Bu PDF'ler
  kullanıcının bilgisayarında `--source "Gelir Idaresi Baskanligi"` çalıştırılıp `--rebuild-only`
  ile süzgeç tazelenene kadar süzgece katkı vermez (bkz. bölüm 9, adım 6). `verginet.net` (WAF) ve
  `ozdogrular.com` (robots.txt) otomatik erişimi engelliyor; aşılmadı. `roedl.com.tr` JS ile
  render edildiği için düz HTML'de içerik yok.
- Model kapalıyken cevaplar yorum değil **alıntıdır**; kalite modele bağlanınca artar.
- Gecikme zammında gün→ay dönüşümü varsayımdır (notla belirtilir); güncel oranlar/uygulamalar sitelerden doğrulanmalıdır.
- Binek araç KDV/gider kısıtı gibi konular parametre defterine girene kadar "güncel sınırı sorun" notuyla anılır.
- Maliyet muhasebesi (7/A–7/B) kayıtları ders notlarından cevaplanır; kesin şablonları henüz yazılmadı.

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
   Idaresi Baskanligi"` çalıştırıp GİB'in 4 resmi PDF'ini indirsin (saniyeler sürer), sonra
   `--rebuild-only` ile süzgeç tazelensin. 2026 yeniden değerleme oranı, resmi ilan
   (Kasım-Aralık 2026) yayımlandığında bir sonraki `güncelle` ile netleşecek.
7. ~~Kaizen'in beynini geliştirme kararı (Cognee önerisi değerlendirmesi)~~ — tamamlandı
   (bkz. bölüm 4f). Kademe 0 (Türkçe ek kırpma düzeltmesi) ve **Kademe 1 (`BrainManager`
   soyutlaması) bitti** — `memory/brain_manager.py`, bkz. bölüm 4f. **Sırada Kademe 2:**
   kavramlar arası basit ilişki tablosu (SQLite, curated — graf veritabanı değil).
8. `config/fact_topics.json`'a diğer parametre konuları (gelir vergisi dilimleri — GİB'den
   2026 tarifesi zaten seed edildi —, MTV, emlak...) ve bunlara bağlı hesaplayıcılar.
9. Yerel model bağlantısı (yeni bilgisayar) ve Hermes'in kademeli kapatılması; ardından
   Kademe 3 (bölüm 4f) — Cognee'nin dar bir pilotu, yalnız serbest metin/deneyim tarafında.
10. WhatsApp fatura otomasyonu ve ofis yardımcılığı (en son; `INDEPENDENCE_PLAN.md` "Ofis uygulamalarında görev yapma").
