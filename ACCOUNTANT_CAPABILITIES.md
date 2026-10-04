# Kaizen-1 — Mevcut muhasebeci yetenekleri

Bu belge 1 Ekim 2026 muhasebeci fazının uygulanmış kapsamını açıklar. Kayıtlar öneridir; muhasebe defterine veya kullanıcı belgesine yazılmaz.

## Doğal işlem cümlesinden kayıt önerisi

Üretim girişi `KaizenEngine.cevap_ver` mevcut `AccountantReasoningEngine`, `JournalRouter`, `JournalEntry`, hesap planı ve ilke sicilini kullanır. Yeni bir muhasebe motoru veya bağımlılık kurulmadı.

- Ticari mal alımı: net bedel ve KDV ayrımı açık olduğunda 153, koşullu 191 ve belirtilen ödeme şekline göre 100/102/320.
- İşletmede kullanılacak demirbaş alımı: mevcut sabit kıymet hesap eşlemesi ve açık ödeme bilgileri. Binek otomobil ve özel KDV koşulları otomatik kayda dönüştürülmez.
- Kasadan bankaya yatırma: 102 borç / 100 alacak. Ters yön bu şablonla işlenmez.
- Mevcut müşteri alacağının nakit/banka tahsilatı: 100/102 borç / 120 alacak.
- Mevcut satıcı borcunun nakit/bankadan ödenmesi: 320 borç / 100/102 alacak.
- Açıkça 7/A genel yönetim gideri olarak belirtilmiş fatura: 770, koşullu 191 ve belirtilmiş ödeme hesabı. Genel bir elektrik/kira ifadesinden 770 varsayılmaz.

Bu yollar tek tutarlı, tek işlemlik sorular içindir. Tutar içermeyen alış açıklamalarında önceki kaynaklı Accounting Problem Solver çalışmaya devam eder. Önceki hesaplama, hesap planı, mizan kavramı ve kavramsal bilgi yolları korunmuştur.

## Bilgi eksikse

KDV oranı, ödeme yöntemi, net/brüt ayrımı, işlem niteliği, müşteri/satıcı rolü veya gerekli dönem bilgisi belirsizse kayıt üretmeden açıklama ister. “Peşin” nakit kabul edilmez. Soruda olmayan KDV oranı eklenmez. Kısmi ödeme, taksit, çek/senet, kart ve özel vergi uygulamalarında tek ödeme hesabı varsayılmaz.

Örneğin “Vadeli 10.000 TL ticari mal aldım, KDV oranı %10” sorusu, 10.000 TL'nin matrah mı toplam mı olduğunu sorar. “KDV hariç” eklendiğinde 153: 10.000 borç, 191: 1.000 borç, 320: 11.000 alacak önerir. Kabul sorusu bu güvenli açıklama isteğiyle PASS sayılmıştır; tutar varsayımı yapılmamıştır.

## Kesinlik ve kaynak sınırı

Para `Decimal` ile hesaplanır; kanonik kayıt satırında binary float reddedilir. Borç/alacak eşitliği, geçerli hesap, pozitif ve tek taraflı satırlar, kuruş hassasiyeti ve yeni işlem yollarında hesap yönü denetlenir. KDV dahil tutarın ayrıştırılmasında ikinci kez yuvarlama yapılmaz. Hatalı kayıt görüntülenmez; hata Trace içinde bulunur.

Mevcut `borc_alacak` ve `hesap_siniflandirma` ilkeleri mevcut sicilde normalize edildi. İlke kimliği, kapsamı, koşulları, etkisi, istisnaları, gerekli bilgiler, kaynak ve doğrulama durumu görülebilir. Kaynaklar mevcut küratörlü ilke/tohum dosyası, kayıt şablonları ve TDHP'dir; bunlar yeni veya güncel mevzuat doğrulaması iddiası taşımaz.

Kullanıcının verdiği oran hesap girdisidir; yasal oranın doğrulandığı anlamına gelmez. Güncel mevzuat sorularında mevcut FactRegistry → araştırma → Evidence/Consensus sınırı korunur. Doğrulanmamış oran/had model hafızasından cevaplanmaz. Bu fazda canlı mevzuat araştırması gerekmedi.

## Gözlemlenebilirlik

Trace: olay, bilinen/eksik bilgiler, kullanılan ilkeler, yapılandırılmış hesap satırları, borç/alacak toplamları ve invariant sonuçlarını içerir. Nihai kayıt sonucu eski muhasebe bağlamına da aktarılır. Açıklama sorusu veya reddedilen kayıt `VERIFIED` olarak işaretlenmez; RuntimeLearning bunları doğrulanmış kayıt olarak öğrenmez.

Gerçek beş kabul sorusu mevcut yapılandırma ve gerçek sağlayıcı nesneleriyle, kullanıcı verilerine karışmayan ayrı veri/log dizinlerinde çalıştırıldı. Model ve araştırma çağrısı yapılmadı. Ayrıntılı kanıtlar `artifacts/accountant_phase1_20261001/` altında.

## Kapsam sınırları

Belgeden otomatik kayıt/mutabakat, çok kayıtlı mizan kontrolü, sayısal dönem dağıtımı, mevzuata göre amortisman ömrü seçimi, tam bordro ve finansal tablolar arası sayısal mutabakat bu fazda uygulanmadı. Eski satış/iade/finansman şablonlarına yeni doğal dil güvenlik kapsamının tamamı yaygınlaştırılmadı. Serbest metnin tüm Türkçe varyasyonlarını veya çok adımlı diyalog tamamlama akışını desteklediği iddia edilmez. Eksik bilgi yanıtlandıktan sonra işlem cümlesi tam bilgilerle yeniden sorulmalıdır.
---

## Faz 2 — Belge <-> Yevmiye Mutabakatı (1 Ekim 2026)

Üretim girişi `KaizenBrain.reconcile_document(document, journal_entry)` (ve ince
sarmalayıcısı `KaizenEngine.reconcile_document`). Bu, doğal dil `answer()`/
`cevap_ver()` zincirinin **dışında**, ayrı ve açık bir giriş noktasıdır — olağan
Faz-1 muhasebe soruları (`KaizenEngine.cevap_ver`) bu kodu hiçbir zaman çağırmaz;
mutabakat yalnızca bir `NormalizedDocument` ve karşılaştırılacak **var olan**
(örn. zaten kaydedilmiş/önerilmiş) bir yevmiye kaydı açıkça verildiğinde çalışır.
Yeni bir hesap seçim/muhasebe motoru kurulmadı: `accounting/document_reconciliation.py`
yalnızca mevcut Faz-1 `accounting.journal.JournalEntry.to_dict()` biçimini (hesap
kodu, borç/alacak, toplamlar) okur.

Olası sonuçlar: `MATCH`, `MISMATCH`, `INSUFFICIENT_INFORMATION`, `INVALID_DOCUMENT`,
`INVALID_ENTRY`. Önemli ayrım: **dengeli (borç=alacak) bir kayıt yine de YANLIŞ
olabilir** — net/KDV/brüt ayrımı belgeyle uyuşmuyorsa, ya da ödeme şekli belgeyle
çelişiyorsa (banka ödemesi ama kayıt 100 Kasa ile, nakit ödeme ama kayıt 102
Bankalar ile, ya da vadeli/kredili alış ama kayıt 100/102 ile peşin kapatılmış —
üç durumun üçü de denetlenir) kayıt `MISMATCH` olarak işaretlenir, `MATCH` değil.

Belgenin kendi aritmetiği (net + KDV = brüt, kalem toplamı = net) önce denetlenir;
tutarsızsa `INVALID_DOCUMENT` döner ve **hiçbir değer sessizce düzeltilmez**. KDV
oranı veya tutarı belirtilmemişse oran asla varsayılmaz; hedefli bir açıklama
istenir ("KDV oranı veya KDV tutarı nedir?") ve sonuç `INSUFFICIENT_INFORMATION`
olur. Yevmiye kaydının kendisi dengede değilse (`borç != alacak`) sonuç
`INVALID_ENTRY` olur.

Gözlemlenebilirlik: `KaizenTrace`'e dört alan eklendi (`document_validation`,
`reconciliation_status`, `discrepancies`, `missing_information`) — tamamen ek
(additive); varsayılanları `None`/`[]` olduğundan Faz-1'in mevcut hiçbir trace
alanı veya testi etkilenmedi. Olağan bir soru sorulduğunda bu dört alan hep
varsayılanında kalır (bkz. `test_accountant_phase2.py::test_focused_g_*`).

### Kapsam sınırları (Faz 2)

Belgeden otomatik OCR/çıkarım, çok kayıtlı mizan kontrolü, kısmi ödeme/taksit
senaryoları ve döküman tipi otomatik sınıflandırması bu fazda kapsam dışıdır —
mutabakat yalnızca zaten yapılandırılmış bir `NormalizedDocument` ile zaten var
olan bir yevmiye kaydını karşılaştırır. Satış tarafı (120 Alıcılar/391 Hesaplanan
KDV) hesap anlamları okunur ama ödeme-şekli çelişki kontrolleri bu fazda yalnızca
alış/gider tarafının üç durumuna (100/102/320) odaklanır.
---

## Faz 3 — Satış/Alacak Tarafı Mutabakatı (1 Ekim 2026)

Aynı üretim girişi (`KaizenBrain.reconcile_document` / `KaizenEngine.reconcile_document`),
aynı sözleşme (MATCH/MISMATCH/INSUFFICIENT_INFORMATION/INVALID_DOCUMENT/INVALID_ENTRY),
aynı Trace alanları. Yeni motor veya ikinci bir izleme sistemi kurulmadı.

Artık ayırt edilenler: kredili/veresiye satış (120 Alıcılar), peşin nakit satış (100 Kasa),
banka ile tahsil edilen satış (102 Bankalar) ve **mevcut bir alacağın tahsilatı** (102/100
borç, 120 alacak — `document_type` içinde "tahsilat" ile işaretlenir). Bir tahsilat asla yeni
bir satış/KDV satırı (600/391) üretmez; böyle bir kayıt görülürse `MISMATCH` döner. Ödeme
şekli çelişkileri simetriktir: banka/nakit ödeme ama kayıtta hâlâ 120 (tahsil edilmemiş alacak)
görünmesi de, kredili satış ama kayıtta 100/102 ile peşin kapanmış olması da yakalanır — hangi
karşı hesabın (320 satıcı mı, 120 alıcı mı) beklendiği, kaydın kendi gelir (600) satırından
okunur, ayrı bir yön parametresi icat edilmedi. Dengeli ama anlam olarak yanlış bir satış kaydı
(ör. KDV/net tutarı belgeyle uyuşmuyor) yine `MATCH` değil `MISMATCH` olur. KDV bilgisi eksikse
yine hiçbir oran varsayılmaz.

Kapsam dışı (Faz 3): kısmi/parçalı tahsilat, iade, indirim, stopajlı satış, ihracat, döviz,
POS komisyonu, e-fatura iş akışı — bunlar bu fazda uygulanmadı.
