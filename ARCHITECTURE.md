# KAZEN AI - MİMARİ

## 1. Temel Amaç

Kazen AI, kullanıcının kendi bilgisayarında çalışan Local-First kişisel yapay zeka asistanıdır.

Kazen'in ana çalışma sistemi ücretli veya bulut API'lerine bağımlı olmayacaktır.

---

## 2. KAZEN KATMANI

Kazen projenin ana kimliği ve kontrol merkezidir.

Kazen'in görevleri:

- Kullanıcı ile iletişim
- Yerel model yönetimi
- Kazen'e özel hafıza
- Güvenlik politikaları
- Kullanıcı onay sistemi
- Config yönetimi
- Log ve denetim
- DEV / TEST / PROD geliştirme akışı
- Hermes'e hangi işlerin verileceğini belirleme
- Sonuçları kontrol etme

Kazen'e ait kodlar KAZEN_AI klasöründe tutulur.

---

## 3. HERMES KATMANI

Hermes, Kazen'in kullanabileceği agent ve araç motorudur.

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

Kazen, Hermes'in üzerine kontrol ve politika katmanı ekler.

Hermes doğrudan Kazen'in kimliği değildir.

---

## 4. YEREL LLM

Yeni bilgisayar hazır olduğunda yerel yapay zeka modeli bağlanacaktır.

Planlanan yapı:

Kullanıcı
↓
Kazen
↓
Yerel LLM
↓
Kazen güvenlik ve karar katmanı
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

Hermes --yolo modu Kazen için kullanılmaz.

---

## 6. GELİŞTİRME AKIŞI

Kazen kendi kodunda doğrudan kontrolsüz değişiklik yapmaz.

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

Kazen Memory:

- Yapısal uygulama verileri
- Kullanıcı tarafından saklanması istenen Kazen verileri
- Kazen'e özel durum bilgileri

Hermes Memory:

- Agent çalışma bağlamı
- Agent görevlerinde gerekli bağlamsal hafıza

Bu iki sistem gerektiğinde birlikte kullanılabilir ancak görevleri karıştırılmaz.

---

## 8. ARAÇ AYRIMI

Kazen ToolManager:

- Politika
- İzin
- Araç kaydı
- Denetim
- Log

Hermes:

- Gerçek araç yürütme motoru

Terminal, browser ve computer-use gibi Hermes'te bulunan sistemler gereksiz yere Kazen içinde yeniden yazılmaz.

---

## 9. ANA PRENSİP

Kazen = Beyin, kimlik ve kontrol katmanı.

Yerel LLM = Akıl yürütme motoru.

Hermes = Agent ve araç yürütme motoru.

Bilgisayar = İşlerin gerçekleştirildiği ortam.

Kazen zamanla Hermes'e olan bağımlılığını azaltabilecek şekilde modüler geliştirilecektir.