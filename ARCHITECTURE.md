# KAIZEN AI - MİMARİ

## 1. Temel Amaç

Kaizen AI, kullanıcının kendi bilgisayarında çalışan Local-First kişisel yapay zeka asistanıdır.

Kaizen'in ana çalışma sistemi ücretli veya bulut API'lerine bağımlı olmayacaktır.

---

## 2. KAIZEN KATMANI

Kaizen projenin ana kimliği ve kontrol merkezidir.

Kaizen'in görevleri:

- Kullanıcı ile iletişim
- Yerel model yönetimi
- Kaizen'e özel hafıza
- Güvenlik politikaları
- Kullanıcı onay sistemi
- Config yönetimi
- Log ve denetim
- DEV / TEST / PROD geliştirme akışı
- Hermes'e hangi işlerin verileceğini belirleme
- Sonuçları kontrol etme

Kaizen'e ait kodlar KAIZEN_AI klasöründe tutulur.

---

## 3. HERMES KATMANI

Hermes, Kaizen'in kullanabileceği agent ve araç motorudur.

Hermes'in mevcut yetenekleri mümkün olduğunca yeniden yazılmaz.

Hermes özellikle şu işler için kullanılabilir:

- Terminal
- Dosya işlemleri
- Browser
- Web araçları
- Computer Use
- Skills
- Agent araçları
- Komut çalıştırma
- Tehlikeli komut onay mekanizması

Kaizen, Hermes'in üzerine kontrol ve politika katmanı ekler.

Hermes doğrudan Kaizen'in kimliği değildir.

---

## 4. YEREL LLM

Yeni bilgisayar hazır olduğunda yerel yapay zeka modeli bağlanacaktır.

Planlanan yapı:

Kullanıcı
↓
Kaizen
↓
Yerel LLM
↓
Kaizen güvenlik ve karar katmanı
↓
Hermes
↓
Bilgisayar / Dosya / Browser / Terminal

Bulut model kullanımı varsayılan olarak kapalıdır.

---

## 5. GÜVENLİK

Kritik işlemler kullanıcı onayı olmadan uygulanmaz.

Örnek:

- Dosya silme
- Klasör silme
- Sistem ayarı değiştirme
- Program yükleme
- Yönetici komutu çalıştırma
- PROD kodunu değiştirme

Hermes --yolo modu Kaizen için kullanılmaz.

---

## 6. GELİŞTİRME AKIŞI

Kaizen kendi kodunda doğrudan kontrolsüz değişiklik yapmaz.

Akış:

PLAN
↓
DEV
↓
TEST
↓
KULLANICI ONAYI
↓
PROD
↓
LOG
↓
GIT KAYDI

Test başarısızsa PROD'a geçilmez.

---

## 7. HAFIZA AYRIMI

Kaizen Memory:

- Yapısal uygulama verileri
- Kullanıcı tarafından saklanması istenen Kaizen verileri
- Kaizen'e özel durum bilgileri

Hermes Memory:

- Agent çalışma bağlamı
- Agent görevlerinde gerekli bağlamsal hafıza

Bu iki sistem gerektiğinde birlikte kullanılabilir ancak görevleri karıştırılmaz.

---

## 8. ARAÇ AYRIMI

Kaizen ToolManager:

- Politika
- İzin
- Araç kaydı
- Denetim
- Log

Hermes:

- Gerçek araç yürütme motoru

Terminal, browser ve computer-use gibi Hermes'te bulunan sistemler gereksiz yere Kaizen içinde yeniden yazılmaz.

---

## 9. ANA PRENSİP

Kaizen = Beyin, kimlik ve kontrol katmanı.

Yerel LLM = Akıl yürütme motoru.

Hermes = Agent ve araç yürütme motoru.

Bilgisayar = İşlerin gerçekleştirildiği ortam.

Kaizen zamanla Hermes'e olan bağımlılığını azaltabilecek şekilde modüler geliştirilecektir.
