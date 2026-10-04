"""Gerçek hayat sınavı (iş emri "RAG v2 - Faz 1" madde 3 ve 12'nin 6. adımı).

`tests/test_golden_exam.py` Kaizen'in HALİHAZIRDA doğru bildiği şeyleri regresyona karşı
korur -- yeni bir yetenek eklendiğinde oraya satır eklenir. Bu dosyanın amacı FARKLI:
gerçek, günlük, doğal Türkçe ile sorulmuş sorularla Kaizen'i sınamak ve ÇALIŞAN ile
BİLİNEN ÇALIŞMAYAN durumları AYNI listede, aynı titizlikle ölçmek. Golden exam'i
değiştirmiyoruz (iş emri madde 3: "Mevcut golden testleri değiştirme").

Her ExamCase şunu söyler: bu soru için Kaizen BUGÜN ne yapıyor (route/confidence/
refusal_reason -- `brain.last_trace`'ten okunur) ve bu bir başarı mı (`fail_category=None`)
yoksa bilinen/kanıtlanmış bir darboğaz mı (`fail_category` doluysa: "classification" /
"retrieval" / "research" / "model" / "facts" / "other" -- iş emri madde 13.C'nin istediği
dağılımla BİREBİR aynı kategori adları). `note` alanı HER durumda (başarı ya da
başarısızlık) NEDEN'i bir cümleyle açıklar; bu dosyanın kendisi, iş emri madde 9'un
istediği "bulguları raporla" adımının ham verisidir.

ÖNEMLİ: Bu dosya BUGÜNKÜ (2026-09-23) gerçek davranışı sabitler -- bilinen bir darboğaz
için de gerçekte gözlenen route/confidence AYNEN assert edilir (golden exam'deki gibi).
Bu BİLİNÇLİ bir tercih: "Her büyük değişiklikten önce mevcut davranışı testle sabitle"
(iş emri madde 12). İş emri madde 11 kapsamında ileride bir düzeltme yapılırsa, düzelen
satırların beklentisi bu dosyada GÜNCELLENİR -- o güncelleme, düzeltmenin kanıtı olur.

Yalnız `Offline()` sahte sağlayıcı ve izole (`tempfile`) bir `LearningStore` kullanılır;
gerçek Hermes/Ollama'ya, gerçek internete veya gerçek data/logs/memory dosyalarına HİÇ
dokunulmaz (bkz. tests/test_engine_isolation.py, tests/test_experience_memory_isolation.py
desenleri -- aynı ilkeler burada da geçerli, ayrıca AST guard'lara da tabidir çünkü
KaizenEngine burada hiç kurulmuyor, yalnız KaizenBrain doğrudan kuruluyor, golden exam'deki
gibi).
"""
import tempfile
from collections import Counter, namedtuple
from pathlib import Path

from core.kaizen_brain import KaizenBrain
from memory.brain_manager import BrainManager
from memory.learning_store import LearningStore
from memory.seed_loader import load_seeds
from tests.doubles import NullExperienceMemory


class Offline:
    def ask(self, prompt):
        return "Kaizen: Yapay zeka modeli kullanılamıyor (çevrimdışı mod); yalnız yerel hafızadan cevap verebilirim."


ExamCase = namedtuple(
    "ExamCase",
    "category question expect_route expect_confidence expect_needles forbid_needles fail_category note",
)


def _case(category, question, route, confidence, needles=(), forbid=(), fail=None, note=""):
    return ExamCase(category, question, route, confidence, tuple(needles), tuple(forbid), fail, note)


EXAM = [
    # ================= MATEMATİK (yüzde, KDV, dört işlem, oran, doğal cümleler) =================
    _case("matematik", "1000 TL'nin yüzde 20 fazlası kaç eder?", "calculator", "VERIFIED",
          needles=["200,00 TL"],
          note="Başarılı: CalculatorRouter yüzde deseni yakalıyor. NOT (belirsizlik, hata değil): "
               "'fazlası' kelimesi Türkçede hem 'yalnız %20'lik kısım' hem 'orijinal + %20' anlamına "
               "gelebilir; Kaizen yalnız %20'lik kısmı (200 TL) veriyor, toplamı (1.200 TL) değil. "
               "Bu iki yorumdan biri -- ölçülebilir bir hata değil, raporda belirsizlik olarak not edildi."),
    _case("matematik", "Bir malın fiyatı 1500 TL, yüzde 18 KDV eklersem ne kadar tutar?", "calculator", "VERIFIED",
          needles=["1.770,00 TL"], note="Başarılı: KDV dahil toplam doğru hesaplanıyor."),
    _case('matematik', "45 ile 78'i topla sonra 3'e böl", "calculator", "VERIFIED",
          needles=["SONUÇ: 41"],
          note="DÜZELTİLDİ (Learning Loop fazı, kök neden #1): zincirleme doğal dil dört işlem artık accounting/natural_math.py ile Decimal'le çözülüyor."),
    _case('matematik', "300 TL'nin yüzde kaçı 60 TL eder?", "calculator", "VERIFIED",
          needles=["%20"],
          note="DÜZELTİLDİ (kök neden #1): ters yüzde (X'in yüzde kaçı Y) kesin araçla çözülüyor."),
    _case('matematik', '15 Ocak 2026 ile 20 Mart 2026 arasında kaç gün var?', "calculator", "VERIFIED",
          needles=["64 gün"],
          note='DÜZELTİLDİ (kök neden #1): iki tarih arası takvim günü farkı kesin araçla hesaplanıyor (sayım kuralı cevapta belirtiliyor).'),
    _case('matematik', '2500 lirayı 4 kişiye eşit paylaştırırsak kişi başı kaç TL düşer?', "calculator", "VERIFIED",
          needles=["625,00 TL"],
          note='DÜZELTİLDİ (kök neden #1): eşit paylaştırma doğal cümlesi kesin araçla çözülüyor.'),
    _case('matematik', "Yüzde 15 iskonto uyguladığım 2000 TL'lik ürün kaç TL olur?", "calculator", "VERIFIED",
          needles=["1.700,00 TL"], forbid=["Vade süresini belirtmediniz"],
          note="DÜZELTİLDİ (kök neden #1, güven modeli): vadesiz oranlı 'iskonto' artık ticari indirim olarak (tutar - yüzde) hesaplanıyor; vadeli/senetli iskonto eski hesaplayıcıda kalıyor. Yanlış alt desene eşleşme kaldırıldı."),
    _case('matematik', '125 çarpı 8 kaç eder?', "calculator", "VERIFIED",
          needles=["SONUÇ: 1.000"],
          note='DÜZELTİLDİ (kök neden #1): kelimeyle yazılmış tek işlem (çarpı/bölü/artı/eksi/kere) kesin araçla çözülüyor.'),

    # ================= MUHASEBE (hesap kodu/sınıfı, borç/alacak, yevmiye, dönem sonu, maliyet) =================
    _case("muhasebe", "760 ile 770 arasındaki fark ne?", "chart", "VERIFIED",
          needles=["760 Pazarlama", "770 Genel Yönetim"],
          note="DÜZELTİLDİ (iş emri madde 11, 2026-09-23): classify() hâlâ (bilerek, "
               "düzeltilmeden) 'general' diyor -- ama artık önemi yok, çünkü "
               "ChartOfAccounts.answer()'a eklenen çoklu-kod karşılaştırma yolu (bkz. "
               "accounting/chart_of_accounts.py, 2026-09-23 tarihli DÜZELTME notu) _TRIGGERS "
               "kapısından BAĞIMSIZ olarak devreye giriyor: 2+ GEÇERLİ hesap kodu bir "
               "karşılaştırma kelimesiyle ('ile') birlikte geçtiğinde HER İKİSİNİ de açıklıyor. "
               "Eskiden (bkz. git/proje geçmişi) route='provider', confidence='UNKNOWN' idi."),
    _case("muhasebe", "191 hesap neden borç çalışıyor?", "chart", "VERIFIED",
          needles=["191 İndirilecek KDV"],
          note="Başarılı (ÖNEMLİ NEGATİF SONUÇ): 'hesap' kelimesi tetikleyiciyi geçtiği ve metinde "
               "TEK bir 3 haneli kod olduğu için chart.answer() doğru çalışıyor. Bug #2'nin HER "
               "hesap-kodu sorusunu etkilemediğinin kanıtı."),
    _case("muhasebe", "Bu işlem hangi hesaba gider: ofis kirası ödedik?", "not_found_offline", "UNKNOWN",
          needles=["çevrimdışı mod"], fail="retrieval",
          note="Yerel eşleşme yok; güncel bilgi gerektirmeyen soru araştırma başlatmaz. "
               "Çevrimdışı sağlayıcının güvenli reddi beklenir."),
    _case("muhasebe", "Muhasebede dönemsellik ne demek?", "memory_extractive", "SUPPORTED",
          needles=["Dönemsellik"],
          note="Başarılı: Türkçe ek kırpma ('Muhasebede' → 'muhasebe') + curriculum eşleşmesi çalışıyor."),
    _case("muhasebe", "153 ile 150 hesap arasındaki fark nedir?", "chart", "VERIFIED",
          needles=["153 Ticari Mallar", "150 İlk Madde"],
          note="DÜZELTİLDİ (iş emri madde 11, 2026-09-23): eskiden ChartOfAccounts.answer() "
               "yalnız İLK kodu (153) açıklayıp İKİNCİYİ (150) sessizce yok sayıyordu (`re.search`), "
               "yine de 'SONUÇ:'/VERIFIED etiketiyle -- güven modeli açısından ciddi bir durumdu. "
               "Artık 2+ geçerli kod + karşılaştırma kelimesi ('ile') olduğunda HER İKİSİ de "
               "açıklanıyor (bkz. accounting/chart_of_accounts.py DÜZELTME notu)."),
    _case("muhasebe", "Dönem sonu envanter işlemleri nasıl yapılır?", "memory_extractive", "SUPPORTED",
          needles=["envanter"], note="Başarılı."),
    _case("muhasebe", "Maliyet muhasebesinde 7/A ve 7/B seçenekleri ne fark eder?", "memory_extractive", "SUPPORTED",
          needles=["7/A seçeneği", "7/B seçeneği"],
          note="DÜZELTİLDİ (kök neden #2): 'ne fark eder' soru iskeleti kanıtta aranmıyor ve 'seçenekleri'~'seçeneği' ünsüz yumuşaması eşleşiyor; eşik (0.6) DÜŞÜRÜLMEDİ, iki seçenek kaydı da gösteriliyor."),
    _case("muhasebe", "Borç ve alacak nasıl anlaşılır, hangi taraf artar hangi taraf azalır?", "not_found_offline",
          "UNKNOWN", needles=["çevrimdışı mod"], fail="retrieval",
          note="BULGU: 'çift taraflı kayıt sistemi ve hesap mantığı' başlıklı ilgili kayıt var ama "
               "bu doğal, uzun, günlük dille yazılmış soru cümlesiyle örtüşme (coverage) 0.6 eşiğinin "
               "altında kalıyor (bkz. tests/test_retrieval_failures.py için ayrılan ölçüm)."),
    _case("muhasebe", "320 nolu hesap ne için kullanılır?", "chart", "VERIFIED",
          needles=["320 Satıcılar"], note="Başarılı."),
    _case("muhasebe", "Yevmiye defteri ile büyük defter arasındaki ilişki nedir?", "memory_extractive", "SUPPORTED",
          needles=["Yevmiye Defteri"], note="Başarılı."),
    _case("muhasebe", "100 kasa hesabı ne zaman alacak çalışır?", "chart", "VERIFIED",
          needles=["100 Kasa"],
          note="Kısmen başarılı: doğru hesabı buluyor ama soru aslında 'normalin dışı ne zaman "
               "alacak çalışır' diye soruyor; chart.answer() yalnız normal bakiyeyi ('borç') söylüyor, "
               "kavramsal 'ne zaman' sorusunu cevaplamıyor. Rota/araç doğru seçildi (fail_category=None "
               "bırakıldı), ama bu bir tam-doğruluk garantisi değil -- raporda gözlem olarak not edildi."),
    _case('muhasebe', 'Amortisman nedir ve nasıl hesaplanır?', "memory_extractive", "SUPPORTED",
          needles=["Amortisman"],
          note="DÜZELTİLDİ (kök neden #2): 'nasıl hesaplanır' soru iskeleti kanıt terimi sayılmıyor; eşik (0.6) DÜŞÜRÜLMEDİ."),

    # ================= SGK (4/a 4/b 4/c, PEK, işveren/işçi prim mantığı) =================
    _case("sgk", "4/a 4/b 4/c nedir, aralarındaki fark ne?", "memory_extractive", "SUPPORTED",
          needles=["4/a", "4/b", "4/c"],
          note="DÜZELTİLDİ (iş emri 'KAIZEN — FAZ 1.1' madde 1, 2026-09-23): eskiden "
               "core.text_tr.tokens_tr()'nin '[a-z0-9]+' regex'i '4/a'yı '4' ve 'a' diye İKİ "
               "tek karakterli parçaya bölüyordu; Retriever._terms()'teki 'len(t) > 2' "
               "anlamlılık filtresi bu parçaları TAMAMEN atıyordu -- sorunun TÜM anlamlı "
               "sinyali ('4/a 4/b 4/c') coverage() hesabından siliniyordu, oysa AYNI SGK kaydı "
               "LearningStore.search()'ün (candidate seçimi) ilk sırasında zaten doğru "
               "bulunuyordu. tokens_tr()'ye eklenen genel (yalnız SGK'ya özel değil) SAYI/HARF "
               "ve HARF/SAYI kodu tanıma kuralı (bkz. core/text_tr.py DÜZELTME notu) '4/a' gibi "
               "kodları artık TEK token olarak koruyor; coverage eşiğini geçiyor ve gerçek "
               "curriculum içeriği (SGK nedir ve sigortalılık halleri) artık DOĞRU bulunup "
               "kullanıcıya sunuluyor."),
    _case("sgk", "Prime esas kazanç ne demek?", "memory_extractive", "SUPPORTED",
          needles=["Prime esas kazanç"], note="Başarılı."),
    _case('sgk', 'İşveren ve işçi prim oranları nasıl paylaşılıyor?', "memory_extractive", "SUPPORTED",
          needles=["prim payı"],
          note="DÜZELTİLDİ (kök neden #2): 'nasıl paylaşılıyor' edilgen soru iskeleti kanıt terimi sayılmıyor. Cevap 'güncel olmayabilir' notuyla, oran sayısı UYDURULMADAN ders notundan geliyor."),
    _case("sgk", "SGK'da eksik gün bildirimi nasıl yapılır?", "memory_extractive", "SUPPORTED",
          needles=["eksik gün bildirimi"], note="Başarılı."),
    _case('sgk', 'Bağkur ile SSK arasındaki fark nedir?', "memory_extractive", "SUPPORTED",
          needles=["4/b"],
          note="DÜZELTİLDİ (kök neden #2): Bağkur/SSK/emekli sandığı sosyal güvenlik kavramları artık muhasebe alanına sınıflanıyor ve tireli bileşik ('Bağ-Kur') eşleşiyor."),
    _case("sgk", "İşe giriş bildirgesi kaç gün içinde verilmeli?", "memory_extractive", "SUPPORTED",
          needles=["İşe Giriş Bildirgesi"],
          note="Başarılı (ÖNEMLİ NEGATİF SONUÇ): classify() burada da domain'i yanlış 'general' "
               "bulur (intent='general') ama _answer_core'daki 'general' dalı, model başarısız "
               "olunca _from_memory'ye DÜŞÜYOR -- bu fallback sayesinde classify() hatası burada "
               "FATAL olmuyor. classify() hatalarının hepsi cevap kaybına yol açmıyor (madde 4'ün "
               "sorduğu soruya somut kanıt)."),
    _case("sgk", "Genel sağlık sigortası kimleri kapsar?", "memory_extractive", "SUPPORTED",
          needles=["Genel Sağlık Sigortası"],
          note="Başarılı (bkz. bir önceki not: intent='general' ama fallback kurtarıyor)."),

    # ================= GÜNCEL BİLGİ (oran/yıl isteyen, eski/yeni yıl ayrımı) =================
    _case("guncel", "2026 gelir vergisi tarifesi nedir?", "not_found_offline", "UNKNOWN",
          needles=["yerel hafızamda bulamadım"], fail="research",
          note="Beklenen (kod hatası DEĞİL): facts/site_store bu test ortamında kasıtlı olarak boş "
               "(gerçek internet/crawling iş emri gereği yasak). Üretimde FactRegistry/araştırma "
               "zinciri devreye girerdi."),
    _case("guncel", "2026 yılı asgari ücret ne kadar?", "not_found_offline", "UNKNOWN",
          needles=["yerel hafızamda bulamadım"], fail="research", note="Beklenen (bkz. yukarıdaki not)."),
    _case("guncel", "Bu yılki KDV oranı yüzde kaç?", "not_found_offline", "UNKNOWN",
          needles=["yerel hafızamda bulamadım"], fail="research", note="Beklenen (bkz. yukarıdaki not)."),
    _case("guncel", "2025 ile 2026 arasında asgari ücrette ne değişti?", "not_found_offline", "UNKNOWN",
          needles=["yerel hafızamda bulamadım"], fail="research", note="Beklenen (bkz. yukarıdaki not)."),
    _case("guncel", "Güncel SGK prim tavanı nedir?", "not_found_offline", "UNKNOWN",
          needles=["yerel hafızamda bulamadım"], fail="research", note="Beklenen (bkz. yukarıdaki not)."),
    _case("guncel", "Bu ay damga vergisi oranı ne kadar?", "not_found_offline", "UNKNOWN",
          needles=["yerel hafızamda bulamadım"], fail="research", note="Beklenen (bkz. yukarıdaki not)."),
]


# route (bkz. core.trace.ROUTE_CONFIDENCE) -> hangi route'lar "kesin araç" sayılır. Bu liste,
# "VERIFIED confidence yalnız deterministik bir araçtan gelir" güven-modeli sözünü, sınavdaki HER
# satır için (bilinen başarısızlıklar dahil) ayrıca ve bağımsızca doğrular.
_EXACT_ROUTES = {"correction", "arithmetic", "journal", "calculator", "chart", "facts"}


def run_real_world_exam():
    """Sınavı çalıştırır, (case, answer, trace) üçlülerini döner. Gerçek dosyaya dokunmaz."""
    with tempfile.TemporaryDirectory() as folder:
        store = LearningStore(Path(folder) / "real_world_exam.sqlite3")
        load_seeds(store)
        brain = KaizenBrain(
            Offline(), Offline(),
            brain_manager=BrainManager(
                learning_store=store, experience_memory=NullExperienceMemory(), log_dir=folder,
            ),
        )
        results = []
        for case in EXAM:
            answer = brain.answer(case.question)
            results.append((case, answer, brain.last_trace))
        return results


def test_real_world_exam():
    results = run_real_world_exam()
    problems = []
    fail_counter = Counter()
    category_counter = Counter()

    for case, answer, trace in results:
        category_counter[case.category] += 1
        fail_counter[case.fail_category or "none"] += 1

        if not answer:
            problems.append(f"{case.question!r}: BOŞ CEVAP döndü (asla olmamalı)")
            continue

        # Güven modeli değişmez kuralı (madde 8): VERIFIED yalnız kesin bir araçtan gelebilir --
        # BAŞARILI ya da BİLİNEN-BAŞARISIZ her satır için, istisnasız.
        if trace.confidence == "VERIFIED" and trace.route not in _EXACT_ROUTES:
            problems.append(
                f"{case.question!r}: GÜVEN MODELİ İHLALİ -- route={trace.route!r} kesin bir araç "
                f"değil ama confidence=VERIFIED döndü"
            )

        if trace.route != case.expect_route:
            problems.append(
                f"{case.question!r}: route={trace.route!r} (beklenen {case.expect_route!r}) "
                f"kategori={case.category} fail={case.fail_category} not={case.note[:80]}"
            )
            continue
        if trace.confidence != case.expect_confidence:
            problems.append(
                f"{case.question!r}: confidence={trace.confidence!r} (beklenen {case.expect_confidence!r})"
            )
        missing = [n for n in case.expect_needles if n not in answer]
        if missing:
            problems.append(f"{case.question!r}: cevapta eksik ifade(ler): {missing}\n{answer[:200]}")
        present = [n for n in case.forbid_needles if n in answer]
        if present:
            problems.append(f"{case.question!r}: cevapta OLMAMASI gereken ifade(ler) var: {present}\n{answer[:200]}")

    assert not problems, "GERÇEK HAYAT SINAVI beklenmedik sonuçlar:\n" + "\n\n".join(problems)

    success = fail_counter["none"]
    total = len(EXAM)
    print(f"\nKAIZEN GERCEK HAYAT SINAVI TESTI: BASARILI ({total} soru; olcum sonucu: "
          f"{success} basarili / {total - success} bilinen darbogaz)")
    print(f"  Kategori dagilimi: {dict(category_counter)}")
    print(f"  Basarisizlik dagilimi (classification/retrieval/research/model/facts/other): "
          f"{ {k: v for k, v in fail_counter.items() if k != 'none'} }")


if __name__ == "__main__":
    test_real_world_exam()
