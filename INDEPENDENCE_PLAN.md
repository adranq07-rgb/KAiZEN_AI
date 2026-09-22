# Kaizen bağımsızlık tasarımı

## Hedef

Kaizen, Hermes'i geçici bir model ve araç sağlayıcısı olarak kullanır. Kaizen'in
kimliği, hafızası, bilgi tabanı, güvenlik kararları ve öğrenilmiş görevleri bu
projenin kendi biçiminde saklanır. Hermes kullanılamadığında Kaizen açılmaya,
kendi verilerini okumaya ve mevcut yerel yeteneklerini çalıştırmaya devam eder.

Hermes'ten bağımsızlık, Hermes kodunu veya özel yapılandırmasını kopyalamak
anlamına gelmez. Kaizen'in kullandığı yeteneklerin arkasındaki sağlayıcıyı
değiştirebilmek anlamına gelir.

## Sınırlar ve sahiplik

| Katman | Kaizen'in sorumluluğu | Geçici sağlayıcı |
| --- | --- | --- |
| Kimlik ve konuşma akışı | Türkçe arayüz, görev yönlendirme | Yok |
| Hafıza | Yerel, taşınabilir kayıt ve geri çağırma | Yok |
| Bilgi | Kaynak, tarih ve doğrulama durumuyla saklama | Hermes araştırma yapabilir |
| Model | Sağlayıcı seçimi, istek ve yanıt sözleşmesi | Şimdilik Hermes; sonra yerel model |
| Araçlar | İzin, kayıt ve sonuç sözleşmesi | Şimdilik Hermes; sonra Kaizen araçları |
| Güvenlik | Kritik işlem için kullanıcı onayı | Sağlayıcıdan bağımsız |

Hermes oturumları Kaizen'in kalıcı hafızası sayılmaz. Kaizen'in kendi kaydı
olmayan bir görev, öğrenilmiş kabul edilmez.

## Öğrenme döngüsü

1. **Gözlem:** Kaizen üzerinden yapılan bir görevin isteği, sağlayıcısı,
   araçları, sonucu ve hata durumu Kaizen biçiminde kaydedilir. Bu kayıt tek
   başına doğru bilgi sayılmaz.
2. **Kanıt:** Araştırma sonucuna gerçekten açılmış kaynak adresi, erişim zamanı
   ve mümkünse kaynak başlığı eklenir. Arama özeti, açılmış sayfa kanıtı yerine
   geçmez. Kaynak alınamadıysa durum açıkça `dogrulanmadi` olur.
3. **Düzeltme:** Kullanıcının açık düzeltmesi ayrı bir kayıt olarak saklanır;
   önceki yanıt sessizce değiştirilmez.
4. **Yetenek:** Tekrarlanabilir görev tarifi, örnek giriş ve beklenen sonuçla
   test edilir. Testi geçen tarif Kaizen yeteneği olarak işaretlenir.
5. **Model eğitimi:** Yalnızca seçilmiş ve doğrulanmış örnekler daha sonra
   yerel modelin ince ayarı için dışa aktarılır. Her konuşma otomatik olarak
   model ağırlıklarına yazılmaz.

## Güncel yanıt akışı

Kaizen genel soruları konuşarak yanıtlar. Tarihe duyarlı bir soru algıladığında
güncel kaynak arar, ilgili sayfayı açar, yayın ve geçerlilik tarihini kontrol
eder, ardından yanıtını kaynakla birlikte verir. Kaynak açılamazsa güncelliği
doğrulanmış gibi konuşmaz. Bu yönlendirme `core/kaizen_brain.py` içinde çalışır: önce kesin araçlar ve yerel hafıza, gerekirse araştırma.

Muhasebe, vergi ve SGK araştırmasında ilk arama penceresi bugünden geriye iki
yıldır. Bu alandaki belgelerin yürürlük tarihi ayrıca kontrol edilir. İki yıllık
aralıkta yeterli dayanak bulunamazsa daha eski kaynaklar incelenir ve sonradan
değişiklik olup olmadığı araştırılır. Bu tarih kuralı genel sorulara uygulanmaz.

### Güvenilir kaynak ve yerel öğrenme sırası

Kaizen önce kendi `accounting_knowledge.sqlite3` deposunu arar. Aynı soru için
son iki yılda yayımlanmış doğrulanmış kayıt varsa Hermes çağrılmaz. Kayıt yoksa
Hermes yalnızca `accounting/source_registry.py` kataloğundaki kaynaklarda arama
ve sayfa okuma işi yapar. GİB ve TÜRMOB birinci, mesleki yayınlar ikinci
önceliktedir. Alomaliye ve Muhasebe Bilenler için forum, soru-cevap ve yorum
yolları kabul edilmez.

Bir kayıt ancak açılan URL katalogda bulunuyorsa, yayın tarihi son iki yıl
içindeyse, cevapta birebir kaynak kanıtı varsa ve sayısal oranlar kanıtla
eşleşiyorsa yerel depoya yazılır. Bu kayıt Kaizen'e aittir; Hermes oturumu veya
Hermes hafızası değildir. Katalogda sonuç bulunamazsa ikinci aşama derin
araştırmadır ve en az iki bağımsız alan adından sayfa açılması gerekir.

Siteler tek seferde körlemesine kopyalanmaz. İçerik; URL, yayın tarihi, alınma
tarihi, kanıt ve konu ile birlikte artımlı indekslenir. Böylece eski ve güncel
sürümler ayrılır, değişen sayfalar yeniden alınabilir ve sitelerin erişim
kuralları korunur.

PDF ve Excel dosyalarının metni de okunur ve aranabilir olur; ancak her zaman
kaynak olarak, bağlantısı ve sayfa/sekme bilgisiyle gösterilir. Kaizen bu içeriği
kendi metni gibi sunmaz; kullanıcı gerekli görürse kaynağı açabilir. GİB toplu
içerik kaynağı değil, resmi dayanak bağlantısıdır.

Güncel bir bilgi resmi kaynakta açıkça yayımlanmışsa tek resmi kaynak yeterlidir.
Mesleki yayınlardan gelen yeni oran, had veya uygulama en az iki bağımsız
güvenilir kaynakta aynı değerle görülünce doğrulanır. En yeni uygulama yılı
cevaplarda öne çıkar; eski sürüm geçmiş kaydı olarak korunur. Aynı yıl için iki
farklı değer ayrı ayrı yeterli destek bulursa Kaizen kesin cevap vermek yerine
çelişki durumunu bildirir.

## Ofis uygulamalarında görev yapma

Kaizen ileride kullanıcının muhasebe programını açma, belgeyi okuma ve fatura
taslağı hazırlama gibi görevlerini ayrı uygulama uyarlayıcılarıyla yapacaktır.
Uygulamanın marka ve sürümüne özgü ekran adımları, Kaizen'in temel hafızasına
ve karar katmanına gömülmez. Önce görev, alanları ve beklenen sonucu Kaizen'in
kendi biçiminde tanımlanır; ardından ilgili program uyarlayıcısı yürütür.

Fatura işleme akışı: belgeyi al, alanları çıkar, belirsiz alanları işaretle,
kullanıcıya taslağı göster, onaylanan alanları programa gir, programdaki sonucu
yeniden oku ve Kaizen işlem kaydına bağla. Kaydetme, gönderme, silme veya
muhasebe kaydını kesinleştirme gibi etkili adımlar açık kullanıcı onayı ister.
Programdan gelen başarı işareti görülmeden işlem tamamlandı denmez.

Bu ofis otomasyonu, kullanılacak muhasebe programı ve örnek iş akışı
belirlendikten sonra uygulanacaktır. Şu anki sürüm yalnızca araştırma ve
temel konuşma altyapısını içerir.

Müşterinin WhatsApp üzerinden gönderdiği bir fatura talebi de gelecekte bu
akışın girişi olabilir. Bağlantı yöntemi kullanılan WhatsApp hesabına ve izinli
entegrasyon seçeneklerine göre seçilir. Kaizen mesajı ve ekleri yalnızca
yetkilendirilmiş kanaldan alır; müşteri, alıcı, tutar, vergi ve açıklama
alanlarını taslak olarak çıkarır. Eksik veya çelişkili alanları sorar. Kullanıcı
taslağı onayladıktan sonra muhasebe programında fatura oluşturulur; sonuç
programdan okunur ve talep kaydıyla eşleştirilir. Müşteriye otomatik yanıt veya
belge gönderimi ayrıca onaylanır. Bu özellik bugün etkin değildir.

## Kaizen veri sözleşmesi

İlk sürümde kayıtlar yerel SQLite deposunda sürümlü JSON alanlarıyla tutulur.
Kalıcı bilgi ve görev geçmişi ayrı tutulur. Her kaydın asgari alanları:

| Alan | Anlamı |
| --- | --- |
| `schema_version` | Daha sonra güvenli veri geçişi için biçim sürümü |
| `id`, `created_at` | Tekil kimlik ve UTC kayıt zamanı |
| `kind` | Konuşma, araç sonucu, kaynak, düzeltme veya yetenek |
| `provider` | Hermes, yerel model veya Kaizen aracı |
| `status` | Başarılı, başarısız veya doğrulanmadı |
| `source_refs` | Gerçekten kullanılan kaynakların adresleri ve erişim zamanı |
| `payload` | Göreve özgü veri; kayıt türüne göre doğrulanır |

Parola, API anahtarı, oturum belirteci ve Hermes'in özel yapılandırması bu
kayıtlara alınmaz. Hassas içerik için saklama ve silme kuralları ayrıca
tanımlanmadan otomatik kalıcı hafıza oluşturulmaz.

## Sağlayıcı sözleşmesi

Model sağlayıcısı ve araç sağlayıcısı ayrı arayüzlerdir. Her çağrı açık bir
istek, yapılandırılmış sonuç ve hata durumu döndürür. Kaizen, sağlayıcının
yanıt metninden araç başarısı veya kaynak doğrulaması çıkarsamaz; bunları araç
sonucundan okur. Hermes uyarlayıcısı da yerel uyarlayıcı da aynı sözleşmeyi
uygular.

Araç yürütme sırası: Kaizen isteği değerlendirir, güvenlik kontrolünü yapar,
gerekiyorsa onay alır, sağlayıcıyı çağırır, ham sonucu doğrular ve Kaizen
kaydını oluşturur. Sağlayıcı kendi içinde başka araçlar kullanırsa Kaizen'in
görmediği adımlar doğrulanmış işlem olarak kaydedilmez.

## Aşamalar

1. **Sözleşme ve kayıt:** Veri şeması, yerel kayıt deposu ve sağlayıcı arayüzü.
   Mevcut davranış korunurken Kaizen üzerinden geçen yeni görevler kaydedilir.
2. **Kanıt ve hafıza:** Kaynaklı bilgi, kullanıcı düzeltmeleri, geçerlilik
   süresi ve geri çağırma. Muhasebe araştırması doğrulanmamış sonucu kesin
   bilgi diye sunmaz.
3. **Yerel model:** Yeni bilgisayarda uygun model bağlanır. Bulut kullanımı
   açık bir tercih olur; varsayılan yerel çalışma hedeflenir.
4. **Araç geçişi:** Web, dosya ve bilgisayar araçları yetenek bazında Kaizen'e
   taşınır. Her yeni araç aynı güvenlik ve sonuç testlerinden geçer.
5. **Hermes'siz kabul testi:** Hermes çalışmıyorken Kaizen açılır, hafızayı
   okur, yerel modelle yanıt verir ve taşınmış araçları çalıştırır.

## Mevcut durum

Ayrıntılı ve güncel durum için `KAIZEN_HEDEF_VE_YOL_HARITASI.md` belgesine bakın. Özet:

- `core/ai` içinde sağlayıcı zinciri kurulur (`provider_factory.py`): Hermes → yerel model → çevrimdışı.
  Hermes kapalıyken Kaizen açılır ve kesin araçlarla, parametre defteriyle ve yerel hafızayla cevap verir.
- Kaizen kendi site toplayıcısına sahiptir (`accounting/crawler.py`, `site_store.py`); robots.txt'e uyar,
  Hermes'e ihtiyaç duymadan sayfa, PDF ve Excel içeriğini artımlı toplar.
- Süzgeç (`consensus.py`, `facts.py`) yıllık parametreleri resmî kaynak veya iki bağımsız kaynakla doğrular.
- `tools/tool_manager.py` izin denetimi yapar; ofis araçları (`tools/office_tools.py`) kayıtlıdır ve
  var olan dosyanın üzerine yazmaz. Hermes'in iç araç çağrılarını yapılandırılmış sonuç olarak henüz almaz.
- Henüz yapılmayanlar: yerel modelin bağlanması, kaynaklı görev/yetenek kayıt şeması (yukarıdaki veri sözleşmesi),
  WhatsApp fatura otomasyonu.
