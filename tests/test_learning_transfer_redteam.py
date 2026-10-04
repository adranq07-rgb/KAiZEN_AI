"""KAIZEN — BÜYÜK GELİŞTİRME PAKETİ #1, Phase B: Learning Brain RED-TEAM / BLIND validation.

AMAÇ (iş emri Phase B, birebir): mevcut 14/14 (tests/test_learning_transfer.py) sonucunu
YETERLİ KABUL ETME. Amaç PrincipleRetriever'ı KIRMAYA ÇALIŞMAK. Mevcut 14 soru bu dosyada
HİÇ değiştirilmedi (import edilip yeniden kullanılıyor, kopyalanmadı).

METODOLOJİ (B3, "BLINDNESS", birebir): aşağıdaki 63 vaka ve `expected`/`category`
etiketleri, PrincipleRetriever'ın implementasyonuna (skor sabitleri, regex'ler) bakılarak
"hangi soru geçer" diye AYARLANMADAN, yalnız gerçek muhasebe mantığıyla ("bu soru gerçekte
hangi ilkeyi gerektirir?") YAZILDI. Dataset TAMAMLANDIKTAN SONRA, BİR KEZ, mevcut sistem
üzerinde çalıştırıldı (bkz. `run_redteam()` çıktısı ve roadmap raporu bölüm C/D). Bazı
`expected` etiketleri KASITLI OLARAK mevcut regex sinyallerinin YAKALAMAYACAĞI ifadeler
içerir (ör. ay yerine YIL ile dönemsellik, "oran" yerine "tavan/limit" ile FACT sorusu,
"kaçtır" gibi "kaç" ile bitmeyen ekli sorular) -- bunlar BİLİNÇLİ sınır/gap testleridir,
sonuçları "başarısız" çıkarsa bile SONRADAN gevşetilmedi/silinmedi (B1: "mevcut 14 soruyu
DEĞİŞTİRME", aynı disiplin bu 63 soru için de uygulandı: yazıldıktan sonra deneme sonucuna
göre DEĞİŞTİRİLMEDİ; yalnızca --- eğer bir düzeltme yapılırsa --- Faz B'nin "retest" adımında
AYNI dosyayla tekrar çalıştırıldı).

Kategoriler (B1, dağılım): en az 25 positive, en az 25 negative, en az 10 ambiguous/
insufficient-evidence. Bu dosyada: 27 positive, 26 negative, 10 ambiguous = 63 toplam.

Adversarial aileler (B2, birebir 8 aile): LEXICAL_TRAP, SEMANTIC_TRANSFER, MULTI_PRINCIPLE,
NO_PRINCIPLE, FACT_TRAP, DATE_TRAP, SGK_TRAP, VOCAB_TRAP -- her vaka bir `adversarial_type`
taşır.

`expected` alanı:
  - bir principle_id (str)  -> sistem TAM OLARAK bunu seçmeli (positive) YA DA TAM OLARAK
    BUNU SEÇMEMELİ (negative -- `category` alanı hangisi olduğunu belirler).
  - "NONE"                  -> sistem hiçbir ilke seçmemeli (selected is None).
  - ambiguous kategorisinde `expected` yoktur; başarı ölçütü FARKLI (bkz. `_ambiguous_ok`):
    sistem bu vakada HIGH confidence ile "tek doğru cevap" iddia ETMEMELİ (MEDIUM/LOW/NONE
    hepsi kabul edilir) -- gerçek dünyada rekabetçi/yetersiz-kanıtlı bir soruda aşırı
    özgüven, yanlış bir ilkeyi zorla seçmekten daha az kötü ama YİNE DE bir güvenlik
    sinyalidir (iş emri madde 11'in ruhu).
"""
import tempfile
from dataclasses import dataclass
from pathlib import Path

from learning.principle_retriever import HIGH, PrincipleRetriever
from learning.principle_seed import load_principle_seeds
from memory.principle_registry import PrincipleRegistry

POSITIVE = "positive"
NEGATIVE = "negative"
AMBIGUOUS = "ambiguous"

LEXICAL_TRAP = "LEXICAL_TRAP"
SEMANTIC_TRANSFER = "SEMANTIC_TRANSFER"
MULTI_PRINCIPLE = "MULTI_PRINCIPLE"
NO_PRINCIPLE = "NO_PRINCIPLE"
FACT_TRAP = "FACT_TRAP"
DATE_TRAP = "DATE_TRAP"
SGK_TRAP = "SGK_TRAP"
VOCAB_TRAP = "VOCAB_TRAP"


@dataclass(frozen=True)
class RedTeamCase:
    case_id: str
    category: str            # positive / negative / ambiguous
    adversarial_type: str
    question: str
    expected: str = None      # principle_id veya "NONE" (ambiguous'ta kullanılmaz)
    note: str = ""


REDTEAM_CASES = [
    # ============================= POSITIVE (27) =====================================
    RedTeamCase("P01", POSITIVE, SEMANTIC_TRANSFER,
        "Bir inşaat firması Kasım ayında tamamladığı hakediş bedelini Ocak ayında fatura "
        "etti; bu geliri hangi ayın kaydına yazmalı?", "donemsellik",
        "sektör: inşaat, hakediş — dataset dışı yeni nesne"),
    RedTeamCase("P02", POSITIVE, SEMANTIC_TRANSFER,
        "Restoran işletmesi Şubat ayına ait elektrik-su-doğalgaz giderlerini Nisan ayında "
        "ödedi; gider hangi döneme aittir?", "donemsellik", "sektör: restoran"),
    RedTeamCase("P03", POSITIVE, SEMANTIC_TRANSFER,
        "Yazılım şirketi Temmuz'da verdiği yıllık bakım hizmetinin bedelini Ekim'de tahsil "
        "etti; hasılat hangi aya yazılır?", "donemsellik", "sektör: yazılım/hizmet"),
    RedTeamCase("P04", POSITIVE, SEMANTIC_TRANSFER,
        "Tarım işletmesi Eylül'de hasat ettiği ürünün satışını Kasım'da faturaladı; gelir "
        "hangi aya ait sayılır?", "donemsellik", "sektör: tarım"),
    RedTeamCase("P05", POSITIVE, DATE_TRAP,
        "2025 yılına ait bir gider faturası 2026'da elimize geçti, hangi yılın defterine "
        "yazılır?", "donemsellik",
        "BİLİNÇLİ SINIR TESTİ: dönemsellik AY değil YIL çifti ile ifade edildi — "
        "TEMPORAL_MISMATCH yalnız ay adı çiftlerini tanıyor, yıl çiftini tanımıyor; bu "
        "yüzden BAŞARISIZ olması BEKLENİR (gerçek bir genelleme sınırı, gizlenmiyor)."),
    RedTeamCase("P06", POSITIVE, SEMANTIC_TRANSFER,
        "Eczane depodan ilaç aldığında oluşan borç hangi tarafa kaydedilir?", "borc_alacak",
        "sektör: eczane"),
    RedTeamCase("P07", POSITIVE, SEMANTIC_TRANSFER,
        "Şirket ortağına kâr payı dağıttığında bu tutar hangi tarafa yazılır?",
        "borc_alacak", "işlem: kâr payı dağıtımı"),
    RedTeamCase("P08", POSITIVE, SEMANTIC_TRANSFER,
        "Taşımacılık firması bir aracını kiraya verdiğinde doğan kira alacağı hangi tarafa "
        "işlenir?", "borc_alacak", "sektör: taşımacılık"),
    RedTeamCase("P09", POSITIVE, SEMANTIC_TRANSFER,
        "Bir imalatçı hammadde tedarikçisine avans ödediğinde bu avans hangi tarafa "
        "kaydedilir?", "borc_alacak", "sektör: imalat, işlem: avans"),
    RedTeamCase("P10", POSITIVE, SEMANTIC_TRANSFER,
        "Bir otelin 2 yıl sonra vadesi dolacak döviz mevduatı bilançoda hangi ana grupta "
        "gösterilir?", "hesap_siniflandirma", "sektör: otelcilik, nesne: döviz mevduatı"),
    RedTeamCase("P11", POSITIVE, SEMANTIC_TRANSFER,
        "Bir yazılım firmasının geliştirip 3 yıl kullanacağı lisans yazılımı hangi hesap "
        "sınıfına girer?", "hesap_siniflandirma", "sektör: yazılım, nesne: lisans"),
    RedTeamCase("P12", POSITIVE, SEMANTIC_TRANSFER,
        "İnşaat firmasının elinde tuttuğu tamamlanmamış proje maliyetleri hangi ana grupta "
        "izlenir?", "hesap_siniflandirma", "sektör: inşaat"),
    RedTeamCase("P13", POSITIVE, SEMANTIC_TRANSFER,
        "Bir eczanenin 6 ay içinde satacağı ilaç stoğu bilançoda hangi grupta yer alır?",
        "hesap_siniflandirma", "sektör: eczane, nesne: stok"),
    RedTeamCase("P14", POSITIVE, SEMANTIC_TRANSFER,
        "Bir taşımacılık firması, sözleşme sonunda mülkiyeti kendisine geçecek şekilde "
        "finansal kiralama ile aldığı kamyonu, kirası devam ederken kimin aktifinde "
        "göstermelidir?", "ozun_onceligi", "sektör: taşımacılık, nesne: kamyon"),
    RedTeamCase("P15", POSITIVE, SEMANTIC_TRANSFER,
        "Bir fabrika, uzun vadeli kiralama sözleşmesiyle kullandığı ve sözleşme sonunda "
        "sahibi olacağı üretim hattını kimin varlığı sayar?", "ozun_onceligi",
        "sektör: üretim, nesne: üretim hattı"),
    RedTeamCase("P16", POSITIVE, SEMANTIC_TRANSFER,
        "Bir otel işletmesi, finansal kiralama sözleşmesiyle aldığı ve mülkiyeti sözleşme "
        "bitiminde kendisine geçecek jeneratörü kimin aktifinde gösterir?", "ozun_onceligi",
        "sektör: otelcilik, nesne: jeneratör"),
    RedTeamCase("P17", POSITIVE, SEMANTIC_TRANSFER,
        "5 yıl önce 80.000 TL'ye alınan bir forkliftin bugünkü piyasa değeri 250.000 TL; "
        "defterde hangi tutar esas alınmalı?", "maliyet_ilkesi", "nesne: forklift"),
    RedTeamCase("P18", POSITIVE, SEMANTIC_TRANSFER,
        "2 yıl önce 1.000.000 TL'ye alınan bir depo binasının bugünkü piyasa değeri "
        "3.000.000 TL oldu; bilançoda hangi tutar yazılı kalmalı?", "maliyet_ilkesi",
        "nesne: depo binası"),
    RedTeamCase("P19", POSITIVE, SEMANTIC_TRANSFER,
        "Bir tarım işletmesinin 4 yıl önce 40.000 TL'ye aldığı traktörün bugünkü piyasa "
        "değeri 120.000 TL; kayıtlarda hangi tutar korunmalı?", "maliyet_ilkesi",
        "sektör: tarım, nesne: traktör"),
    RedTeamCase("P20", POSITIVE, LEXICAL_TRAP,
        "Şirketin sahip olduğu hisse senetlerinin borsadaki güncel fiyatı değişti; bu "
        "elindeki hisseleri hangi tutarla göstermeye devam etmeli, maliyet mi güncel fiyat "
        "mı?", "maliyet_ilkesi",
        "BİLİNÇLİ SINIR TESTİ: 'piyasa değeri' yerine 'borsadaki güncel fiyatı' — "
        "VALUATION_VS_COST_QUERY yalnız literal 'piyasa degeri' ifadesini arıyor, bu "
        "eşanlamlıyı tanımayabilir; BAŞARISIZ olması BEKLENİR (regex dar kapsamlı)."),
    RedTeamCase("P21", POSITIVE, SEMANTIC_TRANSFER,
        "10 yıl kullanılacak bir depo binasının maliyeti tek seferde mi yoksa yıllara "
        "yayılarak mı gider yazılmalı?", "amortisman", "nesne: depo binası"),
    RedTeamCase("P22", POSITIVE, SEMANTIC_TRANSFER,
        "3 yıl kullanılacak bir yazılım lisansının bedeli tek seferde mi gider yazılır "
        "yoksa yıllara mı yayılır?", "amortisman", "sektör: yazılım, nesne: lisans"),
    RedTeamCase("P23", POSITIVE, SEMANTIC_TRANSFER,
        "6 yıl kullanılacak bir CNC tezgahının maliyeti tek seferde mi yoksa faydalı ömrü "
        "boyunca mı gider yazılmalı?", "amortisman", "nesne: CNC tezgahı"),
    RedTeamCase("P24", POSITIVE, SEMANTIC_TRANSFER,
        "Bir taksi şoförü kendi aracıyla bağımsız çalışıyorsa SGK'ya hangi statüde "
        "bildirilir?", "sgk_statu", "meslek: taksi şoförü"),
    RedTeamCase("P25", POSITIVE, SEMANTIC_TRANSFER,
        "Bir avukatlık bürosunda ortak avukat olarak çalışan kişi hangi sigortalılık "
        "statüsündedir?", "sgk_statu", "meslek: avukat"),
    RedTeamCase("P26", POSITIVE, SEMANTIC_TRANSFER,
        "Devlet hastanesinde kadrolu hemşire olarak çalışan biri hangi statüde bildirilir?",
        "sgk_statu", "meslek: hemşire, kamu"),
    RedTeamCase("P27", POSITIVE, SEMANTIC_TRANSFER,
        "Kendi çiftliğini işleten bir tarım üreticisi SGK'ya hangi statüde bildirilir?",
        "sgk_statu", "sektör: tarım"),

    # ============================= NEGATIVE (26) ======================================
    RedTeamCase("N01", NEGATIVE, LEXICAL_TRAP,
        "Mart ve Nisan aylarına ait iki farklı faturanın hangi hesap koduna "
        "kaydedileceğini bulamıyorum, yardımcı olur musun?", "hesap_siniflandirma",
        "iki ay adı geçiyor ama soru sınıflandırma; dönemsellik YANLIŞ TRANSFER olur"),
    RedTeamCase("N02", NEGATIVE, LEXICAL_TRAP,
        "Bir restoranın aldığı POS cihazı kredisinin faiz gideri hangi hesap sınıfına "
        "yazılır?", "hesap_siniflandirma",
        "'kredi' kelimesi var ama yön değil sınıf soruluyor; borc_alacak YANLIŞ olur"),
    RedTeamCase("N03", NEGATIVE, LEXICAL_TRAP,
        "Bir toptancının uzun süredir tahsil edemediği alacağı için ne yapması gerekir?",
        "NONE",
        "'alacak' kelimesi var ama asıl konu şüpheli alacak/karşılık — 7 ilkeden hiçbiri "
        "tam uymuyor, zorla seçim YAPILMAMALI"),
    RedTeamCase("N04", NEGATIVE, LEXICAL_TRAP,
        "Bu arsanın üzerine yapılan yolun maliyeti hangi hesaba işlenir?",
        "hesap_siniflandirma",
        "'arsa'/'maliyet' kelimeleri var ama soru sınıflandırma; maliyet_ilkesi YANLIŞ olur"),
    RedTeamCase("N05", NEGATIVE, LEXICAL_TRAP,
        "Uzun yıllar kullanılacak bu makinenin KDV'si hangi ayda indirim konusu "
        "yapılabilir?", "NONE",
        "'yıllar'/'makine' var ama 'yıllara yayarak' kalıbı yok; amortisman YANLIŞ olur"),
    RedTeamCase("N06", NEGATIVE, FACT_TRAP,
        "Serbest çalışan bir diş hekiminin SGK prim oranı kaçtır?", "NONE",
        "BİLİNÇLİ SINIR NOTU: 'kaçtır' (ekli) RATE_QUERY'nin 'kac' tam-kelime kalıbını "
        "tetiklemeyebilir — yine de hiçbir ilke (sgk_statu dahil, 'hangi statüde' yok) "
        "YANLIŞLIKLA seçilmemeli; LOW/NONE güvenlik ağı bunu yakalamalı"),
    RedTeamCase("N07", NEGATIVE, LEXICAL_TRAP,
        "Bir depo firmasının kiraladığı forkliftin sözleşme bedelinin KDV'si hangi ayda "
        "tahakkuk eder?", "NONE",
        "'sözleşme'/'kiralama' var ama 'kimin aktifinde/mülkiyet' yok; ozun_onceligi "
        "YANLIŞ olur"),
    RedTeamCase("N08", NEGATIVE, VOCAB_TRAP,
        "Yeminli mali müşavir onayı gerektiren işlemler nelerdir?", "NONE",
        "'mali müşavir' muhasebe kelimesi ama yapısal sinyal yok"),
    RedTeamCase("N09", NEGATIVE, SGK_TRAP,
        "SGK'ya işe giriş bildirgesi kaç gün içinde verilmelidir?", "NONE",
        "prosedürel bir FACT (gün sayısı); sgk_statu ile karıştırılmamalı"),
    RedTeamCase("N10", NEGATIVE, FACT_TRAP,
        "İşyerinde kaç gün rapor alınırsa eksik gün bildirimi yapılır, limit kaçtır?",
        "NONE", "'limit' kelimesi FACT ama RATE_QUERY yalnız 'oran' yakalıyor — yine de "
                 "hiçbir ilke yanlışlıkla seçilmemeli"),
    RedTeamCase("N11", NEGATIVE, FACT_TRAP,
        "Bu yılki amortisman oranı nedir?", "NONE",
        "'oran'+'nedir' -> RATE_QUERY temiz ateşlemeli, evrensel FACT vetosu devreye "
        "girmeli"),
    RedTeamCase("N12", NEGATIVE, FACT_TRAP,
        "Güncel KDV oranı yüzde kaç?", "NONE", "'oran'+'kaç' -> RATE_QUERY temiz"),
    RedTeamCase("N13", NEGATIVE, FACT_TRAP,
        "Şirketler için geçerli kurumlar vergisi oranı nedir?", "NONE",
        "'oran'+'nedir' -> RATE_QUERY temiz"),
    RedTeamCase("N14", NEGATIVE, DATE_TRAP,
        "2025 model bir taşıtın 2026 yılındaki güncel ÖTV oranı nedir?", "NONE",
        "iki yıl + araç bağlamı olsa da 'oran'+'nedir' var, FACT vetosu geçerli olmalı"),
    RedTeamCase("N15", NEGATIVE, DATE_TRAP,
        "Aralık 2025'te teslim alınan malın faturası Ocak 2026'da düzenlendi; bu işlem "
        "hangi hesap sınıfına girer?", "hesap_siniflandirma",
        "yıl etiketli aylar (Aralık 2025/Ocak 2026) yine de ay-çifti olarak algılanmalı; "
        "ama asıl soru sınıflandırma olduğu için hesap_siniflandirma kazanmalı, "
        "donemsellik değil"),
    RedTeamCase("N16", NEGATIVE, DATE_TRAP,
        "2026 SGK primine esas kazanç tavanı ne kadardır?", "NONE",
        "'tavan' FACT kelimesi ama 'oran' değil — RATE_QUERY yakalamayabilir; yine de "
        "sgk_statu ('hangi statüde' yok) YANLIŞLIKLA seçilmemeli"),
    RedTeamCase("N17", NEGATIVE, SGK_TRAP,
        "4/a kapsamında çalışan bir işçi için işveren prim payı yüzde kaç?", "NONE",
        "'4/a' lexical eşleşir ama yapısal 'hangi statüde' yok -> en fazla LOW, zorla "
        "seçim YAPILMAMALI"),
    RedTeamCase("N18", NEGATIVE, SGK_TRAP,
        "Bağımsız çalışan bir esnafın (4/b) bu yılki prim tutarı ne kadar ödeniyor?",
        "NONE", "'4/b' lexical ama yapısal sinyal yok -> LOW, zorla seçim YAPILMAMALI"),
    RedTeamCase("N19", NEGATIVE, SGK_TRAP,
        "Memur (4/c) statüsündeki bir çalışanın emekli keseneği oranı nedir?", "NONE",
        "'hangi statüde' YOK (statü zaten verilmiş) + 'oran'+'nedir' var -> RATE_QUERY "
        "evrensel vetosu devreye girmeli"),
    RedTeamCase("N20", NEGATIVE, SGK_TRAP,
        "Güvenlik görevlisinin hangi statüde olduğuna göre değişen işsizlik sigortası "
        "prim oranı nedir?", "NONE",
        "'hangi statüde' YAPISAL sinyali ateşlese bile 'oran'+'nedir' RATE_QUERY evrensel "
        "vetosu ÖNCELİKLİ olmalı — sgk_statu VERIFIED gibi sunulmamalı"),
    RedTeamCase("N21", NEGATIVE, VOCAB_TRAP,
        "Muhasebe programımda yevmiye fişi nasıl yazdırılır?", "NONE",
        "yazılım/how-to sorusu, yapısal sinyal yok"),
    RedTeamCase("N22", NEGATIVE, VOCAB_TRAP,
        "Şirketimizin muhasebe departmanında kaç kişi çalışmalı?", "NONE",
        "organizasyonel soru, 'muhasebe' kelimesi tek başına yeterli değil"),
    RedTeamCase("N23", NEGATIVE, VOCAB_TRAP,
        "Bir mali müşavirlik bürosunun ofis kirası muhasebe açısından nasıl bir gider "
        "türüdür?", "NONE", "çok genel, yapısal sinyal yok — zorla seçim YAPILMAMALI"),
    RedTeamCase("N24", NEGATIVE, VOCAB_TRAP,
        "Muhasebe kayıtlarını dijital ortamda saklamak yasal olarak zorunlu mudur?",
        "NONE", "uyum/hukuk sorusu, muhasebe kelimesi geçiyor diye ilke seçilmemeli"),
    RedTeamCase("N25", NEGATIVE, MULTI_PRINCIPLE,
        "Bir toptancının Mart ayında aldığı ama Mayıs ayında kaydını yaptığı malın hangi "
        "hesap sınıfına gireceğini ve hangi ayın gideri sayılacağını birlikte açıklar "
        "mısın?", "hesap_siniflandirma",
        "hem ay-çifti hem sınıflandırma sinyali var; veto mantığı sınıflandırmayı "
        "kazandırmalı, dönemsellik baskın çıkmamalı"),
    RedTeamCase("N26", NEGATIVE, LEXICAL_TRAP,
        "Bir eczanenin ilaç stoğu için ayrılan değer düşüklüğü karşılığı nasıl "
        "hesaplanır?", "NONE",
        "'stok'/'eczane' kelimeleri geçse de soru karşılık/ihtiyatlılık — 7 ilkeden "
        "hiçbirine tam uymuyor"),

    # ============================= AMBIGUOUS (10) =====================================
    RedTeamCase("A01", AMBIGUOUS, MULTI_PRINCIPLE,
        "3 yıl önce 500.000 TL'ye alınan bir binanın bugünkü piyasa değeri 1.200.000 TL; "
        "bu binayı tek seferde mi yoksa yıllara yayarak mı gider yazmalıyım?", None,
        "maliyet_ilkesi (VALUATION) ve amortisman (BENEFIT_SPREAD) aynı anda ateşler"),
    RedTeamCase("A02", AMBIGUOUS, MULTI_PRINCIPLE,
        "Kasım ayında teslim alınan ama Ocak ayında kullanılmaya başlanan bir makinenin "
        "maliyetini tek seferde mi yoksa yıllara yayarak mı gider yazmalıyım?", None,
        "donemsellik (TEMPORAL) ve amortisman (BENEFIT_SPREAD) rekabet eder, biri "
        "diğerini vetolamaz"),
    RedTeamCase("A03", AMBIGUOUS, MULTI_PRINCIPLE,
        "Bir fabrikanın Şubat ayında aldığı ama Nisan ayında ödemesini yaptığı ve "
        "mülkiyeti sözleşme sonunda kendisine geçecek finansal kiralamalı jeneratörü "
        "kimin aktifinde göstermelidir?", None,
        "donemsellik (TEMPORAL) ve ozun_onceligi (LEGAL_ECONOMIC) rekabet eder"),
    RedTeamCase("A04", AMBIGUOUS, MULTI_PRINCIPLE,
        "Bir eczanenin Ocak ayında aldığı ama Mart ayında kaydını yaptığı cihazın "
        "mülkiyeti kira sözleşmesi bitince kendisine geçecek; bu cihazı kimin aktifinde "
        "göstermeli ve hangi ayın işlemi saymalıyız?", None,
        "donemsellik ve ozun_onceligi tekrar rekabet eder (farklı sektör/nesne)"),
    RedTeamCase("A05", AMBIGUOUS, MULTI_PRINCIPLE,
        "Bir hastane işletmesinin, sözleşme sonunda mülkiyeti kendisine geçecek MR "
        "cihazının maliyetini yıllara yayarak mı yoksa tek seferde mi gider yazacağını "
        "ve cihazın mülkiyetini kimin aktifinde göstermesi gerektiğini soruyor.", None,
        "ozun_onceligi ve amortisman rekabet eder"),
    RedTeamCase("A06", AMBIGUOUS, NO_PRINCIPLE,
        "Bir işletmenin yeni aldığı bir varlığı nasıl muhasebeleştirmesi gerektiğini "
        "genel olarak anlatır mısın?", None,
        "çok vague/yetersiz kanıt — hiçbir yapısal sinyal yok, HIGH confidence ile tek "
        "cevap iddia edilmemeli"),
    RedTeamCase("A07", AMBIGUOUS, MULTI_PRINCIPLE,
        "Şirketimizde hem dönemsellik hem maliyet hem de hesap sınıflandırması ile "
        "ilgili bir sorun var, hangisine göre hareket etmeliyiz?", None,
        "3 ilke ismi birden anılıyor, gerçek yapısal ayrım yok"),
    RedTeamCase("A08", AMBIGUOUS, NO_PRINCIPLE,
        "Bir çiftçinin hem tarım hem de küçük bir bakkal işlettiği durumda SGK statüsü "
        "ve muhasebe kaydı nasıl olur?", None,
        "bileşik/vague soru, tek bir yapısal sinyale indirgenemez"),
    RedTeamCase("A09", AMBIGUOUS, MULTI_PRINCIPLE,
        "İşletmenin aldığı bir kamyonun hem hangi hesaba kaydedileceği hem tek seferde "
        "mi yıllara mı yayılacağı belirsiz; ikisini de açıklar mısın?", None,
        "hesap_siniflandirma (ACCOUNT_CLASS) ve amortisman (BENEFIT_SPREAD) rekabet eder, "
        "biri diğerini vetolamaz"),
    RedTeamCase("A10", AMBIGUOUS, MULTI_PRINCIPLE,
        "Aralık ayında teslim alınan ama Şubat ayında kaydı yapılan ve mülkiyeti kiracıya "
        "geçecek sözleşmeli bir varlığın hem hangi döneme ait sayılacağı hem kimin "
        "aktifinde gösterileceği soruluyor.", None,
        "donemsellik ve ozun_onceligi tekrar rekabet eder (3. varyant)"),
]

assert len(REDTEAM_CASES) == 63
assert sum(1 for c in REDTEAM_CASES if c.category == POSITIVE) == 27
assert sum(1 for c in REDTEAM_CASES if c.category == NEGATIVE) == 26
assert sum(1 for c in REDTEAM_CASES if c.category == AMBIGUOUS) == 10
assert len({c.case_id for c in REDTEAM_CASES}) == 63  # tekil id


# --- çalıştırma altyapısı -------------------------------------------------------------
_cached_registry = None
_cached_tmpdir = None


def _registry():
    global _cached_registry, _cached_tmpdir
    if _cached_registry is None:
        _cached_tmpdir = tempfile.TemporaryDirectory()
        registry = PrincipleRegistry(Path(_cached_tmpdir.name) / "principles.sqlite3")
        load_principle_seeds(registry)
        _cached_registry = registry
    return _cached_registry


def _retriever():
    return PrincipleRetriever(_registry())


def evaluate_case(case):
    result = _retriever().retrieve(case.question)
    if case.category == AMBIGUOUS:
        ok = result.confidence != HIGH
        return {"case_id": case.case_id, "category": case.category,
                "adversarial_type": case.adversarial_type, "question": case.question,
                "selected": result.selected, "confidence": result.confidence,
                "expected": "NOT-HIGH", "ok": ok,
                "fact_safety_triggered": result.fact_safety_triggered}
    if case.category == POSITIVE:
        ok = result.selected == case.expected
    else:  # NEGATIVE
        if case.expected == "NONE":
            ok = result.selected is None
        else:
            ok = result.selected != case.expected
    return {"case_id": case.case_id, "category": case.category,
            "adversarial_type": case.adversarial_type, "question": case.question,
            "selected": result.selected, "confidence": result.confidence,
            "expected": case.expected, "ok": ok,
            "fact_safety_triggered": result.fact_safety_triggered}


def run_redteam():
    rows = [evaluate_case(c) for c in REDTEAM_CASES]
    by_category = {}
    for row in rows:
        by_category.setdefault(row["category"], []).append(row)

    print("=== KAIZEN LEARNING BRAIN RED-TEAM — 63 KOR VAKA SONUCU ===\n")
    for category in (POSITIVE, NEGATIVE, AMBIGUOUS):
        group = by_category[category]
        passed = sum(1 for r in group if r["ok"])
        print(f"--- {category.upper()} ({passed}/{len(group)}) ---")
        for r in group:
            status = "OK" if r["ok"] else "FAIL"
            print(f"  [{status}] {r['case_id']} ({r['adversarial_type']}): "
                  f"expected={r['expected']!r} got={r['selected']!r} conf={r['confidence']}")
        print()

    # --- B4 metrikleri ---------------------------------------------------------------
    positives = by_category[POSITIVE]
    negatives = by_category[NEGATIVE]
    ambiguous = by_category[AMBIGUOUS]

    positive_hits = sum(1 for r in positives if r["ok"])
    negative_hits = sum(1 for r in negatives if r["ok"])
    ambiguous_hits = sum(1 for r in ambiguous if r["ok"])

    # False Positive: negative vakada trap ilke YANLIŞLIKLA seçildi (ok=False AND bir seçim yapıldı)
    false_positive = sum(1 for r in negatives if not r["ok"] and r["selected"] is not None)
    # False Negative: positive vakada None döndü (hiç seçim yapmadı, olması gerekirken)
    false_negative = sum(1 for r in positives if not r["ok"] and r["selected"] is None)
    # Wrong-Principle: positive vakada YANLIŞ bir ilke seçildi (None değil ama beklenenden farklı)
    wrong_principle = sum(1 for r in positives if not r["ok"] and r["selected"] is not None)
    # Fact Safety Violation: herhangi bir vakada (kategori fark etmeksizin) bir FACT/oran
    # sorusunda (adversarial_type FACT_TRAP/DATE_TRAP/SGK_TRAP) bir ilke HIGH confidence
    # ile VERIFIED gibi sunuldu mu?
    fact_violations = [
        r for r in rows
        if r["adversarial_type"] in (FACT_TRAP, DATE_TRAP, SGK_TRAP)
        and r["selected"] is not None and r["confidence"] == HIGH
    ]

    n_pos, n_neg, n_amb = len(positives), len(negatives), len(ambiguous)

    def pct(hit, total):
        return round(100 * hit / total, 1) if total else 0.0

    metrics = {
        "positive_transfer_accuracy": (positive_hits, n_pos, pct(positive_hits, n_pos)),
        "negative_transfer_rejection": (negative_hits, n_neg, pct(negative_hits, n_neg)),
        "ambiguous_abstention": (ambiguous_hits, n_amb, pct(ambiguous_hits, n_amb)),
        "false_positive_rate": (false_positive, n_neg, pct(false_positive, n_neg)),
        "false_negative_rate": (false_negative, n_pos, pct(false_negative, n_pos)),
        "wrong_principle_rate": (wrong_principle, n_pos, pct(wrong_principle, n_pos)),
        "fact_safety_violations": (len(fact_violations), len(rows), pct(len(fact_violations), len(rows))),
        "overall_transfer_score": (
            positive_hits + negative_hits, n_pos + n_neg,
            pct(positive_hits + negative_hits, n_pos + n_neg),
        ),
    }
    print("=== B4 METRIKLER ===")
    for name, (hit, total, p) in metrics.items():
        print(f"  {name:32s}: {hit}/{total} = %{p}")
    if fact_violations:
        print("\n  !!! FACT SAFETY VIOLATION DETAYI !!!")
        for r in fact_violations:
            print(f"    {r['case_id']}: {r['question']!r} -> {r['selected']!r} (HIGH)")

    return {"rows": rows, "by_category": by_category, "metrics": metrics}



# ========================================================================================
# POST-BASELINE DÜZELTME GEÇİŞİ (B3: "Düzeltmeler yalnızca baseline kaydedildikten SONRA
# yapılabilir" -- iş emri Phase B3). AŞAĞIDAKİ HİÇBİR SATIR REDTEAM_CASES'İ DEĞİŞTİRMEZ:
# yukarıdaki 63 vakalık kör (blind) veri seti ve run_redteam() ÇIKTISI olduğu gibi kalır --
# bu, kayıtlı BLIND BASELINE'dır (bkz. roadmap raporu bölüm C). Bu bölüm SADECE ilk çalıştırma
# SONRASI (bkz. bölüm D, başarısızlık analizi) keşfedilen İKİ SORUNU, tamamen AYRI ve
# denetlenebilir bir ikinci katman olarak düzeltir. İkisi de PrincipleRetriever/problem_
# structure implementasyonuna DOKUNMAZ (kod DEĞİŞMEDİ) -- yalnızca test veri seti/metrik
# TANIM hatalarını düzeltir:
#
#   (1) KATEGORİ ETİKETLEME HATASI (N01, N02, N04, N15, N25): bu 5 vakanın `note` alanı --
#       BASELINE ÇALIŞMADAN ÖNCE, dosyanın ilk yazımında -- zaten doğru muhasebe cevabının
#       'hesap_siniflandirma' OLDUĞUNU search ediyordu (örn. N01: "...dönemsellik YANLIŞ
#       TRANSFER olur", N15: "...hesap_siniflandirma kazanmalı, donemsellik değil"). Yani bu
#       vakalar YAZILIRKEN zaten POSITIVE (hesap_siniflandirma doğru cevap) olarak
#       tasarlanmıştı ama `category` alanına yanlışlıkla NEGATIVE yazıldı -- bu, implementasyona
#       bakılarak SONRADAN yapılan bir etiket ayarlaması DEĞİL, yazım anındaki kendi notuyla
#       çelişen bir YAZIM HATASININ düzeltilmesidir (kanıt: not metni, kod hiç çalıştırılmadan
#       ÖNCE yazılmıştı). Düzeltme: category NEGATIVE -> POSITIVE, expected aynı kalır
#       ('hesap_siniflandirma' zaten doğru muhasebe cevabıydı).
#
#   (2) FACT SAFETY VIOLATION METRİK TANIMI ÇOK GENİŞTİ: orijinal `fact_violations` filtresi
#       yalnızca `adversarial_type in (FACT_TRAP, DATE_TRAP, SGK_TRAP)` bakıyordu -- kategori
#       fark etmeksizin. Ama DATE_TRAP/SGK_TRAP/FACT_TRAP ailesinin B2 tanımı gereği asıl
#       test ettiği şey "bu soru güncel bir ORAN/TUTAR/TARİFE/SGK primi istiyor, sistem bunu
#       bir principle ile UYDURMAMALI" -- yani asıl FACT-firewall ihlali yalnızca category==
#       NEGATIVE VE expected=="NONE" olan (yani doğru cevabın açıkça "hiçbir ilke seçme"
#       olduğu) vakalarda anlamlıdır. N15 gibi tarih içeren ama asıl doğru cevabı bir
#       SINIFLANDIRMA ilkesi olan vakalar bu metrik kapsamına hiç girmemeliydi (HIGH
#       confidence ile doğru ilkeyi seçmek bir "fact safety ihlali" değildir). Düzeltme:
#       filtre category==NEGATIVE and expected=="NONE" ile daraltıldı.
#
# Düzeltme (1) uygulandıktan sonra otomatik olarak (2)'nin de etkisi netleşir: N15 artık
# NEGATIVE değil, bu yüzden düzeltilmiş metrikte zaten fact_violations kapsamı dışında kalır
# -- (2) ayrıca yeniden çalıştırılan TÜM diğer NEGATIVE/expected==NONE vakalar için de doğru
# kapsamı garanti eder (N09/N10/N11/... gibi gerçek FACT-veto vakaları etkilenmez).
# ========================================================================================

_CATEGORY_FIX_IDS = {"N01", "N02", "N04", "N15", "N25"}


def _corrected_cases():
    corrected = []
    for c in REDTEAM_CASES:
        if c.case_id in _CATEGORY_FIX_IDS:
            corrected.append(RedTeamCase(
                case_id=c.case_id, category=POSITIVE,
                adversarial_type=c.adversarial_type, question=c.question,
                expected=c.expected,  # zaten 'hesap_siniflandirma' -- değişmedi
                note=c.note + " [DÜZELTME: category NEGATIVE->POSITIVE, bkz. dosya sonu "
                              "POST-BASELINE DÜZELTME bölümü]"))
        else:
            corrected.append(c)
    return corrected


def evaluate_case_corrected(case):
    """evaluate_case ile AYNI -- yalnız burada ayrı tanımlanan sebep: orijinal fonksiyon
    (blind baseline'ın bir parçası) DOKUNULMADAN korunmalı."""
    return evaluate_case(case)


def run_redteam_corrected():
    cases = _corrected_cases()
    rows = [evaluate_case_corrected(c) for c in cases]
    by_category = {}
    for row in rows:
        by_category.setdefault(row["category"], []).append(row)

    print("=== KAIZEN LEARNING BRAIN RED-TEAM — DÜZELTİLMİŞ (POST-BASELINE) SONUÇ ===")
    print(f"(5 vaka kategori düzeltmesi: {sorted(_CATEGORY_FIX_IDS)} NEGATIVE->POSITIVE; "
          "fact-safety metrik kapsamı NEGATIVE+expected==NONE ile daraltıldı)\n")
    for category in (POSITIVE, NEGATIVE, AMBIGUOUS):
        group = by_category[category]
        passed = sum(1 for r in group if r["ok"])
        print(f"--- {category.upper()} ({passed}/{len(group)}) ---")
        for r in group:
            if r["ok"]:
                continue
            print(f"  [FAIL] {r['case_id']} ({r['adversarial_type']}): "
                  f"expected={r['expected']!r} got={r['selected']!r} conf={r['confidence']}")
        print()

    positives = by_category[POSITIVE]
    negatives = by_category[NEGATIVE]
    ambiguous = by_category[AMBIGUOUS]

    positive_hits = sum(1 for r in positives if r["ok"])
    negative_hits = sum(1 for r in negatives if r["ok"])
    ambiguous_hits = sum(1 for r in ambiguous if r["ok"])

    false_positive = sum(1 for r in negatives if not r["ok"] and r["selected"] is not None)
    false_negative = sum(1 for r in positives if not r["ok"] and r["selected"] is None)
    wrong_principle = sum(1 for r in positives if not r["ok"] and r["selected"] is not None)

    # (2) daraltılmış fact-safety kapsamı: yalnız gerçek FACT-veto vakaları (category==NEGATIVE
    # and expected=="NONE") ile adversarial_type FACT_TRAP/DATE_TRAP/SGK_TRAP kesişimi.
    fact_violations = [
        r for r in rows
        if r["adversarial_type"] in (FACT_TRAP, DATE_TRAP, SGK_TRAP)
        and r["category"] == NEGATIVE and r["expected"] == "NONE"
        and r["selected"] is not None and r["confidence"] == HIGH
    ]

    n_pos, n_neg, n_amb = len(positives), len(negatives), len(ambiguous)

    def pct(hit, total):
        return round(100 * hit / total, 1) if total else 0.0

    metrics = {
        "positive_transfer_accuracy": (positive_hits, n_pos, pct(positive_hits, n_pos)),
        "negative_transfer_rejection": (negative_hits, n_neg, pct(negative_hits, n_neg)),
        "ambiguous_abstention": (ambiguous_hits, n_amb, pct(ambiguous_hits, n_amb)),
        "false_positive_rate": (false_positive, n_neg, pct(false_positive, n_neg)),
        "false_negative_rate": (false_negative, n_pos, pct(false_negative, n_pos)),
        "wrong_principle_rate": (wrong_principle, n_pos, pct(wrong_principle, n_pos)),
        "fact_safety_violations": (len(fact_violations), len(rows), pct(len(fact_violations), len(rows))),
        "overall_transfer_score": (
            positive_hits + negative_hits, n_pos + n_neg,
            pct(positive_hits + negative_hits, n_pos + n_neg),
        ),
    }
    print("=== B4 METRIKLER (DÜZELTİLMİŞ) ===")
    for name, (hit, total, p) in metrics.items():
        print(f"  {name:32s}: {hit}/{total} = %{p}")
    if fact_violations:
        print("\n  !!! FACT SAFETY VIOLATION DETAYI !!!")
        for r in fact_violations:
            print(f"    {r['case_id']}: {r['question']!r} -> {r['selected']!r} (HIGH)")
    else:
        print("\n  Fact safety violation YOK (0/63).")

    return {"rows": rows, "by_category": by_category, "metrics": metrics}


if __name__ == "__main__":
    run_redteam()
    print("\n\n")
    run_redteam_corrected()
