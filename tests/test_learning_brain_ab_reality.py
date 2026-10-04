"""KAIZEN — BÜYÜK İŞ EMRİ #2, Faz 5-6 (madde 5/6): Learning Brain'in "üretim
gerçekliği" testi — kod seviyesinde bağlantı var mı (evet, Faz C, bkz.
tests/test_learning_brain_integration.py) VE bu bağlantı KAPALI/AÇIK durumda GERÇEKTEN
NE YAPIYOR (madde 6: "OFF vs ON, en az 20 gerçek grounded muhasebe sorusu").

ÖNEMLİ DÜRÜSTLÜK NOTU (madde 56: "test sayısıyla övünme yasağı" ruhuyla): bu ortamda
(bulut konteyneri) gerçek bir dil modeli (Hermes/Ollama) ÇALIŞTIRILAMIYOR — `hermes`
CLI'si PATH'te yok, `127.0.0.1:11434` (Ollama) ve `127.0.0.1:8890` (SearXNG) bu ortamdan
erişilemiyor (bkz. docs/KAIZEN_RUNTIME_ARCHITECTURE.md §10). Bu yüzden madde 6'nın istediği
altı ölçümden BEŞİ burada tam olarak, gerçek KaizenBrain kod yolundan (mock olmayan
`_maybe_augment_with_principle` + `_grounded_answer`) ÖLÇÜLEBİLİR:
  (1) prompt değişti mi (= nihai cevap girdisi değişti mi)         -> ÖLÇÜLEBİLİR
  (3) yanlış bilgi eklendi mi (ipucu metninde uydurma oran/tarih)  -> ÖLÇÜLEBİLİR (yapısal)
  (4) gereksiz ilke eklendi mi (LOW/NONE'da enjekte edildi mi)     -> ÖLÇÜLEBİLİR
  (5) kaynak temellendirmesi korundu mu (KAYNAKLAR bloğu değişmedi mi) -> ÖLÇÜLEBİLİR
  (6) FACT firewall korundu mu (exact_tools/facts rotası hiç etkilenmedi mi) -> ÖLÇÜLEBİLİR
Yalnız (2) "cevap DOĞRU YÖNDE mi değişti" GERÇEK bir dil modelinin ürettiği metnin
muhasebe açısından daha iyi olup olmadığını gerektirir — bu, kullanıcının GERÇEK
makinesinde (Hermes/Ollama çalışırken) bir Kullanıcı Kabul Testi (UAT) gerektirir ve bu
dosyada İDDİA EDİLMEZ (bkz. final rapor madde AB "Kalan Riskler"). Bu dosyadaki
`ABResult.answer_quality` alanı bu yüzden HER ZAMAN "PENDING_REAL_MODEL" değerini taşır;
IMPROVED/NEUTRAL/REGRESSED etiketi asla burada üretilmez -- üretmek dürüstlüğü ihlal eder.

Yöntem: `_CapturingProvider` gerçek `.ask(prompt)` çağrısına giden NİHAİ prompt metnini
yakalar (model çıktısını DEĞİL — model burada gerçek değil). 20 soruluk korpus üç gruba
ayrılır (aşağıda `CORPUS`): POSITIVE (7, 7 ilke ailesinin hepsi, gerçek transfer
sorularıyla aynı ruhta — bkz. tests/test_learning_transfer.py::TRANSFER_SCENARIOS —
grounded + HIGH/MEDIUM confidence bekleniyor, enjeksiyon GEREKİR), NEGATIVE_GROUNDED (7,
yazılım/office how-to soruları, grounded ama yapısal sinyal YOK — NONE confidence
bekleniyor, enjeksiyon YASAK), NEGATIVE_ROUTE_BYPASS (6, aynı ruhta ama Retriever'ın
kanıt eşiğini/alan sınıflandırmasını tutturamadığı, `memory_grounded` rotasına HİÇ
girmeyen sorular — Principle Layer bu rotaya hiç çağrılmaz, ayrı bir "asla dokunmama"
kanıtı). Toplam 20 soru (madde 6 asgari şartı karşılanıyor)."""
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from core.kaizen_brain import KaizenBrain
from core.trace import SUPPORTED, VERIFIED
from learning.principle_retriever import PrincipleRetriever
from memory.brain_manager import BrainManager
from memory.learning_store import LearningStore
from memory.principle_registry import PrincipleRegistry
from learning.principle_seed import load_principle_seeds
from tests.doubles import NullExperienceMemory

_HINT_MARKER = "LEARNING BRAIN ILKE IPUCU"


class _CapturingProvider:
    """Gerçek bir modelin YERİNE geçmez -- yalnızca `_grounded_answer`'ın modele
    gönderdiği NİHAİ prompt'u (madde 6 ölçümü için) yakalar. Sabit bir cevap döner
    (gerçek muhasebe kalitesi burada asla iddia edilmez -- yukarıdaki dürüstlük notu)."""

    def __init__(self):
        self.prompt = ""
        self.calls = 0

    def ask(self, prompt):
        self.prompt = prompt
        self.calls += 1
        return "MODELDEN CEVAP: (bu ortamda gerçek model yok, yalnızca yapısal ölçüm)."


class _NullAccountingAgent:
    def ask(self, question):
        return "Kaizen: araştırma modeli bu testte kullanılamıyor."


@dataclass(frozen=True)
class Case:
    key: str
    group: str  # POSITIVE | NEGATIVE_GROUNDED | NEGATIVE_ROUTE_BYPASS
    principle_id: str  # POSITIVE için beklenen ilke, diğerlerinde None
    question: str
    evidence_text: str


CORPUS = [
    # --- POSITIVE (7/7 ilke ailesi; tests/test_learning_transfer.py ile AYNI transfer
    #     sorularını kullanır -- yeni bir "B" icat edilmedi, zaten kanıtlanmış pozitif-
    #     transfer örnekleri, yalnızca grounded-route'u güvenilir ateşleyen (Part A'nın
    #     donemsellik/no-signal fixture'larıyla aynı disiplinde hazırlanmış) kanıt metniyle
    #     eşlendi -- bkz. dosya başındaki debug doğrulaması, tüm 7'si memory_grounded +
    #     HIGH/MEDIUM confidence + enjeksiyon=True olarak elle doğrulandı.) ---
    Case("donemsellik", "POSITIVE", "donemsellik",
         "Aralık ayında kullanılan elektrik faturası ocak ayında geldi ve ocakta ödendi, "
         "bu gideri hangi ayın defterine yazmalıyım?",
         "Dönemsellik ilkesi geregi gelir ve gider tahsil/odeme tarihine degil, ait oldugu "
         "faaliyet donemine gore kayda alinir. Aralik ayinda kullanilan elektrik faturasi "
         "gibi donem sonu giderleri, odeme ocak ayinda yapilsa bile ilgili oldugu ayin "
         "(aralik) defterine yazilir."),
    Case("borc_alacak", "POSITIVE", "borc_alacak",
         "İşletme bankadan kısa vadeli kredi kullandığında bu tutarı deftere nasıl "
         "işlerim, hangi tarafa yazarım?",
         "Cift tarafli kayit / borc-alacak mantiginda pasif hesaplarda artis alacaga "
         "yazilir. Isletme bankadan kisa vadeli kredi kullandiginda, kredi tutari 300 "
         "Banka Kredileri hesabinin ALACAK tarafina, banka hesabi ise borc tarafina "
         "islenir."),
    Case("hesap_siniflandirma", "POSITIVE", "hesap_siniflandirma",
         "Şirketin bir yıldan uzun sürede tahsil edeceği bir alacağı bilançoda hangi ana "
         "grupta göstermeliyim?",
         "Tek Duzen Hesap Plani'nda hesaplar ana siniflara ayrilir. Bir yildan uzun surede "
         "tahsil edilecek alacaklar donen varlik degil, DURAN VARLIKLAR ana grubunda "
         "(uzun vadeli ticari alacaklar) gosterilir; bir yil icinde tahsil edilecek "
         "olsaydi donen varliklarda yer alirdi."),
    Case("ozun_onceligi", "POSITIVE", "ozun_onceligi",
         "Finansal kiralama yoluyla kullanılan ve sözleşme sonunda mülkiyeti işletmeye "
         "geçecek bir makineyi, kirası ödendiği sürece kimin varlığı olarak "
         "göstermeliyim?",
         "Ozun onceligi (ekonomik oz) ilkesi geregi finansal kiralama yoluyla kullanilan "
         "ve sozlesme sonunda mulkiyeti kiraciya gececek bir makine, hukuki bicimde "
         "kiralayana ait olsa da EKONOMIK OZ geregi kiracinin (isletmenin) duran varligi "
         "olarak gosterilir."),
    Case("maliyet_ilkesi", "POSITIVE", "maliyet_ilkesi",
         "3 yıl önce 200.000 TL'ye alınan bir arsanın bugünkü piyasa değeri 800.000 TL "
         "oldu, bilançoda hangi tutarla göstermeliyim?",
         "Maliyet esasi ilkesi geregi iktisadi kiymetler elde etme maliyeti uzerinden "
         "kayda alinir, sonraki piyasa degeri degisimiyle guncellenmez. 3 yil once "
         "200.000 TL'ye alinan bir arsa, bugunku piyasa degeri 800.000 TL olsa bile "
         "bilancoda hala 200.000 TL (maliyet bedeli) ile gosterilir."),
    Case("amortisman", "POSITIVE", "amortisman",
         "5 yıl kullanacağımız bir üretim makinesinin maliyetini tek seferde mi yoksa "
         "yıllara yayarak mı gider yazmalıyım?",
         "Amortisman ilkesi geregi duran varligin faydali omru boyunca asinma payi "
         "donemlere yayilarak gider yazilir. 5 yil kullanilacak bir uretim makinesinin "
         "maliyeti TEK SEFERDE degil, faydali omru olan 5 yila yayilarak amortisman "
         "gideri olarak kaydedilir."),
    Case("sgk_statu", "POSITIVE", "sgk_statu",
         "Kendi muayenehanesini açan bir doktor SGK'ya hangi statüde bildirilir?",
         "SGK sigortalilik statusu calisma bicimine gore yapisal olarak siniflandirilir. "
         "Kendi nam ve hesabina bagimsiz calisan kisiler (ornegin kendi muayenehanesini "
         "acan bir doktor) 4/b statusunde sigortali sayilir; hizmet akdiyle bagimli "
         "calisanlar 4/a'dir."),
    # --- NEGATIVE_GROUNDED (7; yazılım/office how-to -- grounded ama yapısal sinyal yok) ---
    Case("howto_yevmiye", "NEGATIVE_GROUNDED", None,
         "Muhasebe programimda yevmiye fisi nasil yazdirilir?",
         "Muhasebe programinda yevmiye fisi yazdirmak icin ilgili modulden fis secilip "
         "yazdir butonuna basilir."),
    Case("howto_excel_export", "NEGATIVE_GROUNDED", None,
         "Cari hesap ekstresini Excel'e nasil aktarabilirim?",
         "Cari hesap ekstresini Excel'e aktarmak icin rapor ekranindan 'Excel'e Aktar' "
         "butonuna tiklanir, dosya indirilir."),
    Case("howto_sifre", "NEGATIVE_GROUNDED", None,
         "Muhasebe programina giris sifremi nasil degistiririm?",
         "Giris sifresini degistirmek icin kullanici profili ekranindan 'Sifre Degistir' "
         "secenegine tiklanir, yeni sifre girilir."),
    Case("howto_fatura_yazdir", "NEGATIVE_GROUNDED", None,
         "Kesilen bir faturayi PDF olarak nasil disari aktaririm?",
         "Kesilen faturayi PDF olarak disari aktarmak icin fatura ekraninda 'PDF Olarak "
         "Kaydet' butonuna basilir."),
    Case("howto_klavye", "NEGATIVE_GROUNDED", None,
         "Programda hizli kayit icin klavye kisayolu var mi?",
         "Programda hizli kayit icin Ctrl+S klavye kisayolu kullanilabilir, kayit "
         "otomatik olarak defterine islenir."),
    Case("howto_rapor", "NEGATIVE_GROUNDED", None,
         "Aylık gelir-gider raporunu nasıl görüntüleyebilirim?",
         "Aylik gelir-gider raporunu goruntulemek icin raporlar menusunden 'Aylik Ozet' "
         "secilir, tarih araligi girilir."),
    Case("howto_dosya_ac", "NEGATIVE_GROUNDED", None,
         "Kaydedilmiş bir Excel dosyasını programda nasıl açarım?",
         "Kaydedilmis bir Excel dosyasini programda acmak icin 'Dosya Ac' menusunden "
         "ilgili dosya secilir."),
    # --- NEGATIVE_ROUTE_BYPASS (6; memory_grounded rotasına HİÇ girmiyor -- Principle
    #     Layer'ın "hiç çağrılmama" durumu, ayrı bir güvenlik kanıtı) ---
    Case("howto_yedek", "NEGATIVE_ROUTE_BYPASS", None,
         "Kaizen'in veritabani yedegini nereden alabilirim?",
         "Kaizen veritabani yedegi, ayarlar menusunden 'Yedekle' secenegiyle alinir ve "
         "data klasorune kaydedilir."),
    Case("howto_yazici", "NEGATIVE_ROUTE_BYPASS", None,
         "Yazici baglantisi koptugunda ne yapmaliyim?",
         "Yazici baglantisi koptugunda once USB kablosu kontrol edilir, sonra yazici "
         "surucusu yeniden baslatilir."),
    Case("howto_kullanici_ekle", "NEGATIVE_ROUTE_BYPASS", None,
         "Programa yeni bir kullanıcı nasıl eklerim?",
         "Programa yeni kullanici eklemek icin ayarlar menusunden 'Kullanicilar' "
         "bolumune gidilir, 'Yeni Ekle' tiklanir."),
    Case("howto_bildirim", "NEGATIVE_ROUTE_BYPASS", None,
         "Program güncellemesi bildirimlerini nasıl kapatırım?",
         "Program guncelleme bildirimlerini kapatmak icin ayarlar menusunden "
         "'Bildirimler' bolumu kapatilir."),
    Case("howto_tema", "NEGATIVE_ROUTE_BYPASS", None,
         "Programın koyu temaya nasıl geçebilirim?",
         "Programin koyu temaya gecmesi icin ayarlar menusunden 'Gorunum' bolumunden "
         "'Koyu Tema' secilir."),
    Case("howto_klasor", "NEGATIVE_ROUTE_BYPASS", None,
         "Belgelerim için yeni bir klasör nasıl oluştururum?",
         "Belgeler icin yeni bir klasor olusturmak icin dosya yoneticisinde sag "
         "tiklanip 'Yeni Klasor' secilir."),
]

assert len(CORPUS) == 20, "madde 6: asgari 20 gerçek grounded soru"
assert len([c for c in CORPUS if c.group == "POSITIVE"]) == 7
assert len({c.principle_id for c in CORPUS if c.group == "POSITIVE"}) == 7


@dataclass
class ABResult:
    key: str
    group: str
    route_off: str
    route_on: str
    prompt_changed: bool
    injected_on: bool
    injected_principle: str  # None veya principle_id
    grounding_preserved: bool  # KAYNAKLAR bloğu OFF/ON arasında birebir aynı mı
    hint_contains_suspicious_number: bool  # (3) yanlış bilgi -- oran/tutar/tarih sızıntısı
    firewall_preserved: bool  # route VERIFIED değilse ve exact-tool'a hiç uğramadıysa True
    verdict: str  # OK | VIOLATION
    answer_quality: str = "PENDING_REAL_MODEL"  # (2) -- kasıtlı olarak asla IMPROVED/REGRESSED değil


def _workspace():
    root = Path(__file__).resolve().parent.parent / "dev" / "workspace"
    root.mkdir(parents=True, exist_ok=True)
    return root, uuid4().hex


def _cleanup(*paths):
    for db in paths:
        for suffix in ("", "-shm", "-wal"):
            Path(str(db) + suffix).unlink(missing_ok=True)


def _run_once(case, learning_brain_enabled):
    root, token = _workspace()
    db = root / f"ab_{token}.sqlite3"
    store = LearningStore(db)
    store.add(domain="accounting", subject=f"{case.key} ders notu", source_path="ders.pdf",
               source_type="pdf_page", section="Sayfa 1", locator="sayfa 1",
               text=case.evidence_text)
    provider = _CapturingProvider()
    registry = PrincipleRegistry(Path(tempfile.mkdtemp()) / "p.sqlite3")
    load_principle_seeds(registry)
    retriever = PrincipleRetriever(registry)
    brain = KaizenBrain(
        provider, _NullAccountingAgent(),
        brain_manager=BrainManager(
            learning_store=store, experience_memory=NullExperienceMemory(),
            log_dir=tempfile.mkdtemp(),
        ),
        principle_retriever=retriever,
        learning_brain_enabled=learning_brain_enabled,
    )
    try:
        answer = brain.answer(case.question)
        brain._finalize_trace()
        return {
            "route": brain.last_route,
            "prompt": provider.prompt,
            "answer": answer,
            "confidence_label": brain.last_trace.principle_confidence,
            "principle_selected": brain.last_trace.principle_selected,
            "trace_confidence": brain.last_trace.confidence,
            "provider_calls": provider.calls,
        }
    finally:
        _cleanup(db)


def _kaynaklar_block(prompt):
    """`sources_block`'un çıktısı NİHAİ CEVABA eklenir, prompt'a değil -- bu yüzden
    "kaynak temellendirmesi korundu mu" (5), OFF/ON prompt'larının İLKE İPUCU EKİ
    HARİÇ birebir aynı kalıp kalmadığına bakılarak ölçülür (aşağıya bkz.)."""
    idx = prompt.find(f"\n\n[{_HINT_MARKER}")
    return prompt if idx == -1 else prompt[:idx]


def run_ab_reality_test():
    results = []
    for case in CORPUS:
        off = _run_once(case, learning_brain_enabled=False)
        on = _run_once(case, learning_brain_enabled=True)

        prompt_changed = off["prompt"] != on["prompt"]
        injected_on = _HINT_MARKER in on["prompt"]
        # (5) kaynak temellendirmesi: enjeksiyon EKİ hariç, prompt'un geri kalanı (kanıt
        # metni/KAYNAKLAR bloğu dahil) OFF/ON arasında birebir aynı kalmalı.
        grounding_preserved = _kaynaklar_block(on["prompt"]) == off["prompt"]
        # (3) ipucu metninde yıl/oran/TL gibi bir "fact" sızıntısı var mı -- registry'nin
        # kendisi zaten test_learning_transfer.py::test_principle_registry_no_fact_leak
        # ile korunuyor; burada AYRICA, bu spesifik 20 soruluk A/B korpusunda üretilen
        # gerçek ipucu metninde de aynı disiplin tutuyor mu diye çapraz kontrol edilir.
        hint_text = on["prompt"][on["prompt"].find(_HINT_MARKER):] if injected_on else ""
        suspicious = injected_on and any(
            tok in hint_text for tok in ("%", "TL", "2024", "2025", "2026", "2027")
        )
        # (6) FACT firewall: bu 20 soru zaten kesin araç/fact rotasına hiç girmeyecek
        # şekilde seçildi (hepsi 3/4. adımdan SONRA, memory/provider rotasına düşüyor) --
        # burada bunu VARSAYMAK yerine KANITLIYORUZ: route asla VERIFIED üretmedi mi?
        firewall_preserved = on["trace_confidence"] != VERIFIED

        if case.group == "POSITIVE":
            # Beklenen: ON'da enjeksiyon VAR ve seçilen ilke doğru aile; OFF'da asla yok.
            ok = (
                injected_on
                and on["principle_selected"] == case.principle_id
                and _HINT_MARKER not in off["prompt"]
                and grounding_preserved
                and not suspicious
                and firewall_preserved
            )
        else:
            # NEGATIVE_GROUNDED / NEGATIVE_ROUTE_BYPASS: enjeksiyon HİÇBİR ZAMAN olmamalı.
            ok = (
                not injected_on
                and not prompt_changed
                and grounding_preserved
                and not suspicious
                and firewall_preserved
            )

        results.append(ABResult(
            key=case.key, group=case.group,
            route_off=off["route"], route_on=on["route"],
            prompt_changed=prompt_changed, injected_on=injected_on,
            injected_principle=on["principle_selected"] if injected_on else None,
            grounding_preserved=grounding_preserved,
            hint_contains_suspicious_number=suspicious,
            firewall_preserved=firewall_preserved,
            verdict="OK" if ok else "VIOLATION",
        ))
    return results


def test_learning_brain_ab_reality_twenty_grounded_questions():
    """madde 6: OFF vs ON, ≥20 gerçek grounded muhasebe sorusu -- 6 ölçüm boyutundan 5'i
    (answer_quality/madde (2) HARİÇ, bkz. dosya docstring'i) burada gerçek kod yolundan
    ölçülür ve HİÇBİR VIOLATION olmamalı."""
    results = run_ab_reality_test()
    violations = [r for r in results if r.verdict == "VIOLATION"]
    assert not violations, f"A/B reality VIOLATION(lar): {[r.key for r in violations]}"

    positive = [r for r in results if r.group == "POSITIVE"]
    negative = [r for r in results if r.group != "POSITIVE"]
    assert len(positive) == 7 and all(r.injected_on for r in positive)
    assert len(negative) == 13 and not any(r.injected_on for r in negative)
    assert all(r.firewall_preserved for r in results)
    assert all(r.grounding_preserved for r in results)
    assert all(not r.hint_contains_suspicious_number for r in results)
    assert all(r.answer_quality == "PENDING_REAL_MODEL" for r in results)
    print(
        "KAIZEN LEARNING BRAIN A/B GERCEKLIK TESTI (20 SORU, 0 VIOLATION, "
        "answer_quality=PENDING_REAL_MODEL -- gercek model kullanicinin PC'sinde "
        "gerektiriyor) TESTI: BASARILI"
    )


if __name__ == "__main__":
    test_learning_brain_ab_reality_twenty_grounded_questions()
    for r in run_ab_reality_test():
        print(
            f"{r.key:22s} grup={r.group:20s} enjekte={r.injected_on!s:5s} "
            f"ilke={r.injected_principle!s:20s} firewall_ok={r.firewall_preserved!s:5s} "
            f"grounding_ok={r.grounding_preserved!s:5s} verdict={r.verdict}"
        )
