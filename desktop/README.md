# Kaizen Desktop Alpha

Kaizen'in ilk masaüstü sürümü: gerçek Kaizen backend'ine (`core/engine.py::KaizenEngine`)
bağlı, tkinter tabanlı bir sohbet penceresi. Sahte/demo cevap YOKTUR — her cevap Kaizen'in
gerçek karar zincirinden (kesin araçlar → parametre defteri → yerel hafıza → araştırma)
geçer.

## Nasıl çalıştırılır

En kolay yol: masaüstündeki **Kaizen** kısayoluna çift tıklamak (kurulum aşağıda,
"Masaüstü kısayolu oluşturma").

Elle çalıştırmak için, proje klasöründe:

```
Kaizen_Baslat.bat
```

dosyasına çift tıklayın, ya da PowerShell'de:

```powershell
.venv\Scripts\python.exe desktop_app.py
```

İlk açılışta Kaizen kendi hafızasını (SQLite depoları, tohum verileri) yüklediği için birkaç
saniye "Başlatılıyor..." görebilirsiniz — bu normaldir, pencere donmaz.

## Masaüstü kısayolu oluşturma

Proje kökünde, PowerShell'de:

```powershell
powershell -ExecutionPolicy Bypass -File desktop\create_shortcut.ps1
```

Bu, masaüstünüze gerçek Kaizen simgesiyle **Kaizen.lnk** kısayolunu ekler ve
`Kaizen_Baslat.bat`'ı doğru çalışma klasörüyle çalıştıracak şekilde ayarlar. Kısayol bir
`.exe`'ye DEĞİL, kaynaktan çalıştırmaya işaret eder — bkz. aşağıdaki "EXE derleme" bölümü ve
`desktop/ARCHITECTURE_DECISION.md` için neden.

Eğer script bir nedenle çalışmazsa (ör. PowerShell çalıştırma ilkesi engellerse), masaüstünde
sağ tık → Yeni → Kısayol ile elle de oluşturabilirsiniz: hedef `Kaizen_Baslat.bat`'ın tam
yolu, simge için `desktop\icon\kaizen.ico` seçin.

## EXE derleme (isteğe bağlı, deneysel)

```powershell
powershell -ExecutionPolicy Bypass -File desktop\build.ps1
```

Derlenen uygulama `dist\Kaizen\Kaizen.exe` altında oluşur (standalone/onedir derleme —
tek dosya `onefile` DEĞİL, daha güvenilir olduğu için tercih edildi).

**Önemli:** bu derleme betiği hiçbir bulut/uzak yürütme ortamında test edilemedi (bkz.
`desktop/ARCHITECTURE_DECISION.md`) ve bir risk taşır: Kaizen'in veri depoları göreli yol
(`Path(__file__).resolve().parent.parent / "data"`) kullanır; paketlenmiş bir EXE içinde bu
yol gerçek proje klasörünüzdeki `data/`/`knowledge/`/`memory/` yerine YANLIŞ bir konuma
çözülebilir. **EXE'yi ilk kullanışınızda mutlaka `durum` yazıp** çıkan ders/site sayısını
kaynaktan çalışan sürümle karşılaştırın; farklıysa (özellikle sıfırsa) EXE'yi silin ve
`Kaizen_Baslat.bat` ile kaynaktan çalışmaya devam edin — bu, Alpha'nın birincil, doğrulanmış
teslim yöntemidir.

## Geliştirici Modu (Brain Inspector)

Sol menüden **Sistem**'e tıklamak hem `durum` komutunu gönderir hem de "Brain Inspector"
adlı ayrı bir pencere açar. Bu pencere, en son cevabın tam izleme kaydını (`KaizenTrace`:
sınıflandırma, cevap yolu, kullanılan kesin araç, principle adayları/seçilen ilke/güveni,
FACT güvenliği, kaynak doğrulama, geçen süre değil ama hangi adımların çalıştığı) gösterir.
Bu, normal kullanıcı sohbet akışından tamamen ayrıdır — normal kullanıcı yalnızca sağdaki
"Bağlam" panelini (güven durumu, kaynak, varsa ilgili ilke) görür.

## Loglar

`logs/kaizen.log` (proje kökü altında) — motor başlatma, hata ve komut logları burada
tutulur. Masaüstü uygulamasının kendi hataları da (kullanıcıya gösterilmeyen teknik ayrıntı)
buraya yazılır.

## Ayarlar

Alpha sürümünde ayarlar penceresi yoktur; mevcut ayarlar (ör. Learning Brain açık/kapalı)
sol menüden **Ayarlar** ile salt-okunur görüntülenir. Değiştirmek için `config/Kaizen.json`
dosyasını düzenleyip Kaizen'i yeniden başlatın.

## Bilinen Alpha sınırları (dürüstçe)

- **Görsel/etkileşimsel doğrulama bu oturumda yapılamadı**: geliştirme ortamında `tkinter`
  kurulu değil (bkz. mimari karar belgesi) ve bu araç Windows ikili dosyası çalıştıramıyor.
  İş mantığı (`desktop/adapter.py`) otomatik testlerle doğrulandı; pencerenin gerçekten
  göründüğü gibi çalıştığını ilk siz göreceksiniz (bkz. Faz K kullanıcı kabul testi).
- Tek oturumluk sohbet geçmişi: "Sohbetler" (çoklu sohbet listesi) Alpha'da yer tutucudur.
- Durum modeli yalnızca "Düşünüyor" (gerçek, işlem sürerken) ve cevap sonrası gerçek
  rota özetini gösterir — "Hafızada arıyor"/"İnternette araştırıyor" gibi ANLIK ara adım
  göstergeleri YOKTUR (madde F3: backend'in gerçekte gözlemlenemeyen bir ara adımını
  UYDURMAMAK için kasıtlı bir tercih — bkz. `desktop/adapter.py` modül docstring'i).
- EXE derlemesi deneysel (yukarıya bakın); birincil teslim yöntemi kaynaktan çalıştırmadır.


## KAİZEN Desktop (yeni arayüz, geliştirme modu)

Başlatma: `Kazen_Baslat.bat` (eski `Kaizen_Baslat.bat` / `desktop_app.py` dokunulmadan duruyor).
Mimari: `kazen_ui.py` (yalnız görünüm, tkinter) -> `controller.py` (iş parçacığı, olay kuyruğu) -> `KaizenEngine.cevap_ver()`.
Dosyalı mesaj: dosyanın gerçek yolu tırnaklı olarak mesaja eklenir; Document Engine yolu kendisi bulur.
Mantık modülleri tkinter'sızdır ve testlidir: `tests/test_kazen_desktop.py`.
Modlar: `kazen_core.MODES` -- `accounting` aktif, `general` kapalı ("Yakında"; `enabled=True` ile açılır, ikinci AI yok).
Sohbet geçmişi: `data/ui/kazen_conversations.json` (Experience/Memory'den ayrı). API anahtarları UI'da/loglarda yer almaz.
Kabul: `tools\kazen_ui_acceptance.bat` -> `artifacts/kazen_ui_20261004/ui_acceptance_result.json`.
Paketleme (`KAZEN.exe`) sonraki adım; backend mimarisi değişmez.
