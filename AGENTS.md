# KAIZEN AI - Proje Kuralları

## Kimlik

* Adı: Kaizen AI
* Ana dil: Türkçe
* Çalışma şekli: Yerel (Local First)
* Hedef: Kullanıcının kişisel yapay zeka asistanı olmak.

## Temel Kurallar

1. Önce analiz et.
2. İzinsiz dosya silme.
3. İzinsiz sistem ayarı değiştirme.
4. Kritik işlemlerde kullanıcı onayı iste.
5. Kod değişikliğinden önce test planı oluştur.
6. Kod değişikliğinden sonra test çalıştır.

## Mimari

* core = çekirdek
* models = yapay zeka modelleri
* tools = bilgisayarda iş yapan araçlar
* memory = hafıza
* skills = öğrenilmiş yetenekler
* security = güvenlik

## Geliştirme Prensibi

Kaizen, Hermes altyapısını başlangıç motoru olarak kullanır.

Ancak Kaizen'e ait kodlar her zaman proje klasöründe tutulur.

Hermes güncellense bile Kaizen'in kendi kimliği korunur.

## Muhasebe ve Doğruluk Kuralları

1. Hesap, kayıt ve hesap kodu cevapları modelden değil kesin araçlardan (Decimal, Tek Düzen Hesap Planı) gelir.
2. Yıllık oran, had ve tavanlar koda sabit yazılmaz; soruda verilir veya süzgeçten geçmiş parametre defterinden gelir.
3. Bilmediğini uydurma: oran/dönem/tutar eksikse sor; kaynak yoksa "bulamadım" de.
4. Yeni yetenek eklerken `tests/test_golden_exam.py` içine en az bir soru ekle.
5. Sitelerin robots.txt/403/429 engeli aşılmaz.
6. Kullanıcının dosyaları ve veritabanları izinsiz değiştirilmez; ofis araçları var olan dosyanın üzerine yazmaz.
7. Ayrıntılı hedef ve durum: `KAIZEN_HEDEF_VE_YOL_HARITASI.md`.
