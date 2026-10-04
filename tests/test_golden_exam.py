"""Altın sınav: Kaizen'in model olmadan (çevrimdışı) verdiği cevaplar, mali müşavir bakışıyla doğrulanır.

Her satır: (soru, cevapta MUTLAKA geçmesi gerekenler, beklenen yol). Yeni bir yetenek eklendiğinde buraya
bir satır eklemek regresyona karşı en ucuz sigortadır.
"""
import tempfile
from pathlib import Path

from core.kaizen_brain import KaizenBrain
from memory.brain_manager import BrainManager
from memory.learning_store import LearningStore
from memory.seed_loader import load_seeds
from tests.doubles import NullExperienceMemory


class Offline:
    def ask(self, prompt):
        return "Kaizen: Yapay zeka modeli kullanılamıyor (çevrimdışı mod); yalnız yerel hafızadan cevap verebilirim."


EXAM = [
    ("1000 TL için %20 KDV hesapla", ["200,00", "1.200,00"], "calculator"),
    ("Vadeli mal aldım. Muhasebe açısından ne oldu?", ["153 Ticari Mallar hesabına borç", "320 Satıcılar hesabına alacak"], "memory_grounded"),
    ("12 + 7", ["SONUÇ: 19"], "arithmetic"),  # learned strategies must retain Decimal priority
    # --- matematik ---
    ("matematik: 0,1 + 0,2", ["SONUÇ: 0,3"], "arithmetic"),
    ("(1.500 + 2.500) / 4", ["SONUÇ: 1.000"], "arithmetic"),
    ("2 + 2 * 3", ["SONUÇ: 8"], "arithmetic"),
    ("15'in %20'si kaç", ["3,00 TL"], "calculator"),
    ("2500 TL'den %10 indir", ["2.250,00 TL"], "calculator"),
    ("80 den 100 e yüzde kaç arttı", ["%25,00"], "calculator"),
    # --- vergi hesapları (oran soruda verilir) ---
    ("1.000 TL'nin %20 KDV dahil tutarı", ["833,33", "166,67"], "calculator"),
    ("2026 yılı için 10.000 TL KDV hesapla %20", ["2.000,00", "12.000,00"], "calculator"),
    ("1.000 TL KDV hesapla", ["KDV oranını belirtmediniz"], "calculator"),
    ("12.000 TL brüt serbest meslek makbuzu stopaj %20 net kaç?", ["9.600,00"], "calculator"),
    ("10.000 TL serbest meslek makbuzu KDV %20 stopaj %20 net kaç", ["net tahsilat 10.000,00"], "calculator"),
    ("damga vergisi binde 9,48 ile 1.000.000 TL sözleşme", ["9.480,00"], "calculator"),
    # --- faiz, iskonto, kredi ---
    ("50.000 TL'nin %2 aylık basit faizi 3 ay", ["3.000,00"], "calculator"),
    ("Gecikme zammı 10.000 TL 3 ay %4,5", ["1.350,00", "11.350,00"], "calculator"),
    ("100.000 TL kredi %2 aylık faiz 12 ay eşit taksit", ["9.455,96", "13.471,53"], "calculator"),
    ("100.000 TL kredi 12 ay", ["faiz oranını belirtmediniz"], "calculator"),
    ("Faiz hesapla 10000 TL aylık %3 45 gün", ["450,00"], "calculator"),
    ("Faiz hesapla 10000 TL %3 45 gün", ["aylık mı yıllık mı"], "calculator"),
    ("NPV %10 -100000, 30000, 40000, 50000, 60000", ["38.877,13"], "calculator"),
    ("IRR -100000, 30000, 40000, 50000, 60000", ["%24,89"], "calculator"),
    ("Sabit gider 100.000 TL, birim fiyat 50 TL, birim değişken maliyet 30 TL başabaş noktası", ["5.000 adet"], "calculator"),
    ("100.000 TL 5 yıl doğrusal amortisman tablosu", ["20.000,00", "100.000,00"], "calculator"),
    ("cari oran dönen varlıklar 500.000 kısa vadeli yabancı kaynaklar 250.000", ["2,00"], "calculator"),
    ("TR33 0006 1005 1978 6457 8413 26 IBAN geçerli mi", ["GEÇERLİ"], "calculator"),
    # --- hesap planı ---
    ("Kasa hesabının kodu kaç?", ["100 Kasa", "borç"], "chart"),
    ("320 hesabı hangi hesap", ["Satıcılar", "alacak"], "chart"),
    ("Satıcılar hesabı kaç numara", ["320 Satıcılar"], "chart"),
    ("70 hesap grubu nedir", ["Maliyet Muhasebesi"], "chart"),
    # --- yevmiye kayıtları ---
    # Payment must be supplied: absence of payment information does not imply 320.
    ("10.000 TL + %20 KDV ile vadeli mal alındı, yevmiye kaydı nedir?", ["153 Ticari Mallar", "191 İndirilecek KDV", "320 Satıcılar", "12.000,00"], "journal"),
    ("20.000 TL + %20 KDV mal sattık yevmiye", ["120 Alıcılar", "600", "391 Hesaplanan KDV", "24.000,00"], "journal"),
    ("KDV hariç 5.000 TL tutarındaki bir bilgisayarı %20 KDV ile nakit aldım kayıt nedir", ["255 Demirbaşlar", "100 Kasa", "6.000,00"], "journal"),
    ("Ortaklardan borç alındı 10.000 TL kaydı", ["331 Ortaklara Borçlar", "102 Bankalar"], "journal"),
    ("Kasada 250 TL noksan çıktı kayıt", ["197", "689"], "journal"),
    ("Ticari mal alış iadesi kaydı 1.000 TL %20 KDV", ["320 Satıcılar", "1.200,00", "191"], "journal"),
    ("10.000 TL mal alındı yevmiye kaydı", ["KDV oranını belirtmediniz"], "accounting_clarification"),
    ("Peşin 1.000 TL + %10 KDV mal aldım.", ["nakit mi banka"], "accounting_clarification"),
    ("Vadeli 10.000 TL mal aldım KDV %10.", ["KDV dahil toplam mı"], "accounting_clarification"),
    ("Kasadan bankaya 5.000 TL yatırdım.", ["102 Bankalar", "100 Kasa", "5.000,00"], "journal"),
    ("Müşteriden 3.000 TL nakit tahsil ettim.", ["120 Alıcılar", "100 Kasa", "3.000,00"], "journal"),
    ("Satıcıya 8.000 TL borcumu bankadan ödedim.", ["320 Satıcılar", "102 Bankalar", "8.000,00"], "journal"),
    ("7/A genel yönetim elektrik faturası 1.000 TL + %10 KDV bankadan ödendi.", ["770", "191", "102", "1.100,00"], "journal"),
    # --- ofis bilgisi (öğretilmiş) ---
    ("Excel'de DÜŞEYARA nasıl kullanılır?", ["DÜŞEYARA", "YANLIŞ"], "memory_extractive"),
    ("ÇOKETOPLA formülü", ["ÇOKETOPLA", "TOPLAM ARALIĞI"], "memory_extractive"),
    ("Excel'de tarih farkı bulma", ["ETARİHLİ"], "memory_extractive"),
    ("Word'de içindekiler tablosu nasıl eklenir?", ["İçindekiler"], "memory_extractive"),
    # --- kavramsal kayıt (tutar yok): şablondan açıklar ---
    ("Kasa sayımında noksan çıktı kayıt nasıl yapılır", ["197", "100 Kasa"], "memory_extractive"),
    # --- muhasebenin temel taşları (değişmeyen çekirdek bilgi, knowledge/muhasebe_temel_taslari.json) ---
    ("muhasebe: dönemsellik kavramı nedir", ["Dönemsellik kavramı", "tahakkuk"], "memory_extractive"),
    ("muhasebe: ihtiyatlılık kavramı nedir", ["İhtiyatlılık", "şüpheli alacak"], "memory_extractive"),
    ("muhasebe: çift taraflı kayıt sistemi nedir", ["çift taraflı kayıt sistemi", "borç", "alacak"], "memory_extractive"),
    ("muhasebe: tek düzen hesap planında 9 sınıfı nazım hesaplar nedir", ["Nazım Hesaplar", "9 "], "memory_extractive"),
    ("muhasebe: yevmiye büyük defter mizan akışı nasıldır", ["Yevmiye Defteri", "Büyük Defter", "Mizan"], "memory_extractive"),
    ("muhasebe: kaydi envanter ile fiziki envanter farkı nedir", ["Kaydi envanter", "fiziki"], "memory_extractive"),
    ("muhasebe: 7/A seçeneği nedir", ["7/A seçeneği", "yansıtma hesapları"], "memory_extractive"),
    ("muhasebe: 7/B seçeneği nedir", ["7/B seçeneği", "790"], "memory_extractive"),
    ("muhasebe: bilanço nedir", ["Bilanço", "Yabancı Kaynaklar", "Özkaynaklar"], "memory_extractive"),
    ("muhasebe: defter tutma saklama süresi nedir", ["saklama süresi", "5 yıldır"], "memory_extractive"),
    ("muhasebe: irsaliye nedir", ["İrsaliye", "fatura"], "memory_extractive"),
    ("muhasebe: stok değerleme yöntemleri nelerdir", ["FIFO", "LIFO", "Ağırlıklı Ortalama"], "memory_extractive"),
    ("muhasebe: tashih kaydı nedir", ["tashih", "Ters kayıt"], "memory_extractive"),
    # --- SGK temel yapısı (değişmeyen çekirdek bilgi, knowledge/sgk_temel_yapi.json) ---
    ("muhasebe: 4/a 4/b 4/c sigortalılık halleri nedir", ["4/a", "4/b", "4/c", "SSK", "Bağ-Kur"], "memory_extractive"),
    ("muhasebe: SGK kısa vadeli ve uzun vadeli sigorta kolları nelerdir", ["Kısa vadeli sigorta", "Uzun vadeli sigorta", "malullük"], "memory_extractive"),
    ("muhasebe: prime esas kazanç taban tavan nedir", ["Prime esas kazanç", "taban", "tavan"], "memory_extractive"),
    ("muhasebe: eksik gün bildirimi nedir", ["eksik gün bildirimi", "MUHSGK"], "memory_extractive"),
    ("muhasebe: işveren ve sigortalı prim payı nasıl paylaşılır", ["işveren", "sigortalı", "paylaşılır"], "memory_extractive"),
    ("muhasebe: işe giriş bildirgesi ne zaman verilir", ["İşe Giriş Bildirgesi", "İşten Ayrılış"], "memory_extractive"),
    ("muhasebe: MUHSGK nedir", ["Muhtasar ve Prim Hizmet Beyannamesi", "MUHSGK"], "memory_extractive"),
    ("muhasebe: SGK teşvikleri nasıl işler", ["SGK teşvikleri", "Hazine"], "memory_extractive"),
    ("muhasebe: genel sağlık sigortası GSS nedir", ["Genel Sağlık Sigortası", "gelir testi"], "memory_extractive"),
    ("muhasebe: sigortalılığın başlangıcı ve sona ermesi nasıl olur", ["sigortalılığı", "hizmet akdine"], "memory_extractive"),
    ("muhasebe: emeklilik için hizmet birleştirme nasıl olur", ["yaşlılık aylığı", "hizmet birleştirme"], "memory_extractive"),
    ("muhasebe: iş kazası bildirimi nasıl yapılır", ["iş kazasını", "meslek hastalığı"], "memory_extractive"),
    ("muhasebe: SGK prim borcunda gecikme cezası ve zammı nasıl işler", ["gecikme cezası", "gecikme zammı"], "memory_extractive"),
    # --- Türkçe ek farkının iki yönlü tanınması (bkz. core.text_tr.stem_tr): "muhasebe:"
    # önekine gerek kalmadan, sorudaki ekli kelimeler ("muhasebede", "SGK'da", "işletmelerde")
    # doğrudan doğal cümlede de doğru kayda ulaşmalı ---
    ("Muhasebede dönemsellik kavramı ne demek?", ["Dönemsellik kavramı", "tahakkuk"], "memory_extractive"),
    ("Muhasebede ihtiyatlılık kavramı nedir?", ["İhtiyatlılık", "şüpheli alacak"], "memory_extractive"),
    ("SGK'da 4/a 4/b 4/c sigortalılık halleri nelerdir?", ["4/a", "4/b", "4/c", "SSK", "Bağ-Kur"], "memory_extractive"),
    ("İşletmelerde stok değerleme yöntemleri nelerdir?", ["FIFO", "LIFO", "Ağırlıklı Ortalama"], "memory_extractive"),
]


def test_golden_exam():
    with tempfile.TemporaryDirectory() as folder:
        store = LearningStore(Path(folder) / "exam.sqlite3")
        load_seeds(store)
        # experience_memory=NullExperienceMemory(): bu sınav 70 soruyu art arda brain.answer()
        # ile soruyor -- enjekte edilmezse varsayılan GERÇEK CogneeMemory() kullanılır ve
        # kullanıcının kendi bilgisayarında (cognee kurulu) her sınav koşusu 70 test
        # soru-cevabını kalıcı kişisel hafızaya yazardı.
        brain = KaizenBrain(
            Offline(), Offline(),
            brain_manager=BrainManager(
                learning_store=store, experience_memory=NullExperienceMemory(), log_dir=folder,
            ),
        )
        failures = []
        for question, needles, route in EXAM:
            answer = brain.answer(question)
            missing = [n for n in needles if n not in answer]
            if missing or brain.last_route != route:
                failures.append(f"{question!r}: yol={brain.last_route} (beklenen {route}), eksik={missing}\n{answer[:300]}")
        assert not failures, "Altın sınav başarısız:\n" + "\n\n".join(failures)
    print(f"KAIZEN ALTIN SINAV TESTI: BASARILI ({len(EXAM)} soru)")


if __name__ == "__main__":
    test_golden_exam()
