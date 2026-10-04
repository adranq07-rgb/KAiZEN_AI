# Docker Desktop + WSL2 Kurulum Rehberi (Windows 10 Pro 64-bit icin)

Bu rehber, `setup_searxng.ps1`'in calisabilmesi icin gereken Docker Desktop
kurulumunu, sizin ortaminiza (Windows 10 Pro 64-bit, 2026-09-23 tarihinde
dogrulanmis) ozel, MINIMUM ve GUVENLI adimlarla anlatir. Hicbir adim Kaizen
verilerinize dokunmaz; bu kurulum tamamen Windows/Docker seviyesindedir.

## Onemli: yeniden baslatma (restart) uyarisi

**WSL2'yi etkinlestirme adimi (Adim 2) NEREDEYSE KESIN bir yeniden
baslatma gerektirir.** Docker Desktop kurulumunun kendisi de bazen ikinci
bir yeniden baslatma isteyebilir. Bu rehberi, uzerinde calisirken
kaydetmeniz gereken acik dosyalariniz varsa once onlari kaydedin, sonra
baslayin. Asagida her adimda "YENIDEN BASLATMA GEREKEBILIR" notunu
gorunca durup bilgisayarinizi yeniden baslatin, sonra bir sonraki adima
gecin.

## On kosul kontrolu

Windows 10 Pro icin Docker Desktop, WSL2 (Windows Subsystem for Linux 2)
backend'ini kullanir (Hyper-V backend de bir secenektir ama WSL2 daha
hafif ve onerilir). Once surumunuzu dogrulayin:

1. `Windows tusu + R` -> `winver` yazip Enter'a basin.
2. Windows 10, surum **2004 (Build 19041) veya daha yeni** olmali.
   (Bu betigin calistigi ortamda "Windows 10 Pro 64-bit" dogrulandi;
   `winver` ile tam build numaranizi kontrol edin -- cok eski bir surumse
   once Windows Update ile guncelleyin.)

## Adim 1 — WSL2 gereksinimlerini etkinlestir

PowerShell'i **Yonetici olarak** acin (Baslat menusune sag tiklayin ->
"Windows PowerShell (Yonetici)" veya "Terminal (Yonetici)"), sonra:

```powershell
wsl --install
```

Bu komut: WSL ozelligini, Sanal Makine Platformu'nu etkinlestirir ve
varsayilan bir Linux dagitimi (Ubuntu) kurar.

**YENIDEN BASLATMA GEREKIYOR.** Komut bittikten sonra bilgisayarinizi
yeniden baslatin.

Eger `wsl --install` "zaten kurulu" derse veya WSL onceden kismen
kuruluysa, surumunuzu dogrulamak icin:

```powershell
wsl --set-default-version 2
wsl --status
```

## Adim 2 — Docker Desktop'i indirin ve kurun

1. Tarayicinizda `https://www.docker.com/products/docker-desktop/`
   adresine gidin, "Docker Desktop for Windows" indirin (Intel/AMD 64-bit
   secin, bu bilgisayar icin dogru olan budur).
2. Indirilen `Docker Desktop Installer.exe`'yi calistirin.
3. Kurulum sihirbazinda **"Use WSL 2 instead of Hyper-V"** secenegini
   ISARETLI birakin (varsayilan zaten budur, Windows 10 Pro'da Hyper-V de
   mevcuttur ama WSL2 bu senaryo icin daha hafif ve onerilen secenektir).
4. Kurulum bittiginde sihirbaz sizden yeniden baslatmanizi isteyebilir.
   **YENIDEN BASLATMA GEREKEBILIR** -- isterse yeniden baslatin.

## Adim 3 — Docker Desktop'i baslatin ve dogrulayin

1. Yeniden baslatmadan sonra Docker Desktop'i baslatin (Baslat menusunden
   "Docker Desktop").
2. Ilk acilista lisans sozlesmesini kabul etmeniz istenebilir; kabul edin.
   Docker Hub hesabi OLMADAN da (Sign in'i atlayarak / "Continue without
   signing in") kullanabilirsiniz -- SearXNG imajini cekmek icin hesap
   GEREKMEZ.
3. Sistem tepsisinde (saat yaninda) Docker balina simgesinin "Docker
   Desktop is running" durumuna gecmesini bekleyin (genelde 30-60 saniye).
4. Dogrulama icin normal (yonetici olmayan) bir PowerShell penceresi acip:

   ```powershell
   docker --version
   docker info
   ```

   Ikisi de hatasiz calismali ve `docker info` bir surum/sunucu bilgisi
   dondurmelidir. Bu iki komut basariliysa, `setup_searxng.ps1` artik
   calistirilmaya hazirdir.

## Adim 4 — `setup_searxng.ps1`'i (guncellenmis surumle) tekrar calistirin

```powershell
cd 'C:\Users\ANL\Desktop\KAZEN_AI\search'
powershell -ExecutionPolicy Bypass -File .\setup_searxng.ps1
```

Beklenen sonuc: "Docker CLI: ...", "Docker daemon: CALISIYOR",
"Container 'running' durumunda dogrulandi", ardindan "Health check: OK" ve
"JSON API: OK".

## Sorun giderme

- **"WSL 2 installation is incomplete" hatasi Docker Desktop'ta:**
  `https://aka.ms/wsl2kernel` adresinden "WSL2 Linux kernel update
  package" indirip kurun, sonra Docker Desktop'i yeniden baslatin.
- **Docker Desktop acilmiyor / donuyor:** Bilgisayarinizi bir kez daha
  yeniden baslatin; BIOS/UEFI'de sanallastirmanin (Intel VT-x / AMD-V)
  ACIK oldugundan emin olun (genelde varsayilan olarak aciktir).
- **Sirket/kurum bilgisayariysa:** Grup ilkesi (Group Policy) WSL veya
  Hyper-V ozelliklerini kisitliyor olabilir; bu durumda BT departmanina
  danisin -- bu rehberdeki adimlar yonetici haklari gerektirir.
