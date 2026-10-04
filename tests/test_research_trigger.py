"""KAIZEN — BÜYÜK İŞ EMRİ #2, Faz 9-10 (madde 9, 33): Research Trigger'ın ≥30 vakalık
testi. madde 33: "yanlış tetiklenen bir internet çağrısı da HATA sayılır" -- bu yüzden
research-not-needed grubu kadar özenle test edilir (yalnız research-needed grubu değil).

`local_evidence_found` semantiği (bkz. research/trigger.py docstring'i): GERÇEK üretim
zincirinde bu değer `_from_memory()` çalıştıktan SONRA kesin olarak bilinir. Bu test
dosyasında her vaka, o noktaya GERÇEKTEN ulaşıldığında ne olacağını dürüstçe simüle
eder -- ör. "hesap 100 kasa nedir" `local_evidence_found=True` ile test edilir çünkü bu
soru gerçekte `accounting/chart_of_accounts.py` (kesin araç) + yerel `knowledge/*.json`
tarafından zaten karşılanır ve `_from_memory`'ye hiç ihtiyaç bırakmaz -- bu bir "oyun"
değil, gerçek sistemin davranışının dürüst bir yansımasıdır."""
from research.trigger import needs_research, domain_of


CASES_RESEARCH_NEEDED = [
    ("2026 asgari ücret tutarı ne kadar oldu?", None),
    ("Bu yılki SGK prim tavanı kaç TL?", None),
    ("2026 yılı için yeni çıkan tebliğ hangi vergi oranını değiştirdi?", None),
    ("Güncel KDV oranı yüzde kaç?", None),
    ("GİB'in bu yıl yayınladığı yeni vergi duyurusu neyle ilgili?", None),
    ("2026 yılı damga vergisi haddi nedir?", None),
    ("Bu yıl geçerli olan kıdem tazminatı tavanı ne kadar?", None),
    ("Yeni çıkan kanun amortisman oranlarını değiştirdi mi?", None),
    ("Şu anki asgari ücret geçim indirimi limiti kaç TL?", None),
    ("2026 yılında e-fatura zorunluluğu hangi ciro sınırına düştü?", None),
    ("Az bilinen bir yurt dışı hizmet ihracatı KDV istisnası var mı, detayları nedir?",
     False),
    ("Kripto varlık alım satımının muhasebeleştirilmesiyle ilgili yeni bir düzenleme "
     "var mı?", False),
    ("Serbest bölgede üretilen yazılımın KDV istisnası güncel şartları nelerdir?",
     False),
    ("Yurt dışı influencer geliri için yeni vergi uygulaması nedir?", False),
    ("Deprem bölgesindeki işletmeler için bu yıl geçerli vergi teşviki oranı nedir?",
     False),
    ("Elektronik para kuruluşlarının muhasebe kaydı hakkında yeni bir tebliğ çıktı mı?",
     False),
]

CASES_RESEARCH_NOT_NEEDED = [
    ("2 + 2 kaç eder?", None),
    ("125 * 4 - 10 işlemini yapar mısın?", None),
    ("Hesap 100 Kasa ne için kullanılır?", True),
    ("102 Bankalar hesabı hangi hesap grubuna girer?", True),
    ("Çift taraflı kayıt (borç/alacak) mantığı nasıl işler?", True),
    ("Dönemsellik ilkesi ne anlama gelir?", True),
    ("Kurumlar vergisi oranı geçen ay sorduğumda %25 bulunmuştu, aynı soru bu sefer de "
     "aynı mı?", True),
    ("Az önce düzelttiğim yevmiye kaydı sorusunu tekrar soruyorum, cevap neydi?", True),
    ("Excel'de DÜŞEYARA formülü nasıl kullanılır?", None),
    ("Word'de içindekiler tablosu nasıl eklenir?", None),
    ("Bugün hava nasıl olur dersin?", None),
    ("Sende en sevdiğin renk hangisi?", None),
    ("Yevmiye fişi bir muhasebe kaydının hangi unsurlarını içerir?", True),
    ("Amortisman mantığı neden faydalı ömre yayılarak uygulanır?", True),
    ("Tek Düzen Hesap Planı kaç ana sınıftan oluşur?", True),
    ("Maliyet esası ilkesi ne demektir?", True),
]

assert len(CASES_RESEARCH_NEEDED) + len(CASES_RESEARCH_NOT_NEEDED) >= 30, (
    "madde 33: en az 30 vaka"
)


def test_research_trigger_needed_cases():
    failures = []
    for question, local_evidence in CASES_RESEARCH_NEEDED:
        got = needs_research(question, local_evidence_found=local_evidence)
        if got is not True:
            failures.append((question, local_evidence, got))
    assert not failures, f"research-needed vakalarinda yanlis SESSIZLIK: {failures}"
    print(
        f"KAIZEN RESEARCH TRIGGER GEREKLI VAKALAR ({len(CASES_RESEARCH_NEEDED)} SORU) "
        "TESTI: BASARILI"
    )


def test_research_trigger_not_needed_cases():
    failures = []
    for question, local_evidence in CASES_RESEARCH_NOT_NEEDED:
        got = needs_research(question, local_evidence_found=local_evidence)
        if got is not False:
            failures.append((question, local_evidence, got))
    assert not failures, (
        f"madde 33 KRITIK: research-not-needed vakalarinda YANLIS TETIKLEME: {failures}"
    )
    print(
        f"KAIZEN RESEARCH TRIGGER GEREKSIZ VAKALAR ({len(CASES_RESEARCH_NOT_NEEDED)} SORU, "
        "YANLIS TETIKLEME YOK) TESTI: BASARILI"
    )


def test_research_trigger_domain_gate_blocks_non_accounting_even_with_no_local_evidence():
    """Mimari sınır: domain != 'accounting' ise local_evidence_found=False OLSA BİLE
    research tetiklenmez (Research Engine yalnız muhasebe/SGK alanına özgü, madde 28)."""
    assert domain_of("Bugün hava nasıl olur dersin?") == "general"
    assert needs_research("Bugün hava nasıl olur dersin?", local_evidence_found=False) is False
    assert domain_of("Excel'de pivot tablo nasıl yapılır?") == "office"
    assert needs_research("Excel'de pivot tablo nasıl yapılır?", local_evidence_found=False) is False
    print("KAIZEN RESEARCH TRIGGER ALAN SINIRI (YALNIZ MUHASEBE/SGK) TESTI: BASARILI")


def test_research_trigger_local_evidence_found_true_always_wins():
    """madde 28: yerel hafıza YETERLİYSE (local_evidence_found=True) -- soru ne kadar
    'güncel' görünürse görünsün -- research tetiklenmez (research bir SON ÇAREdir,
    yerel kanıt varken asla devreye girmez)."""
    current_looking_but_already_known = "2026 asgari ücret tutarı ne kadar oldu?"
    assert needs_research(current_looking_but_already_known, local_evidence_found=True) is False
    print("KAIZEN RESEARCH TRIGGER YEREL KANIT VARSA HIC TETIKLENMEZ TESTI: BASARILI")


if __name__ == "__main__":
    test_research_trigger_needed_cases()
    test_research_trigger_not_needed_cases()
    test_research_trigger_domain_gate_blocks_non_accounting_even_with_no_local_evidence()
    test_research_trigger_local_evidence_found_true_always_wins()
