# KAIZEN — Faz A1/A2: ortam kontrolu + SearXNG yerel kurulum
#
# Bu betik hicbir Kaizen servisini bozmaz, hicbir portu zorla degistirmez,
# `data/`/`logs/`/`memory/` klasorlerine hic dokunmaz.
# SearXNG YALNIZ 127.0.0.1 (localhost) uzerine baglanir -- public internete
# ACILMAZ (LAN'dan bile erisilemez). Disariya (arama motorlarina) normal
# internet erisimini kullanir.
#
# Bu betik SearXNG kurulumu + kendi kendini dogrulama (health check + JSON
# API testi) ile SINIRLIDIR. Hicbir arama benchmark'i veya Learning Brain /
# Principle Layer calismasi BURADA YAPILMAZ (bu is'in kapsami disinda).
#
# ONEMLI: Asagidaki kontroller "Docker bulunamadi" durumunu "SearXNG
# calismiyor" durumundan bilerek AYIRIR. Docker eksikse bu bir BAGIMLILIK
# HATASI'dir, SearXNG'nin kendisiyle ilgili degildir; betik bu durumda
# health/JSON testlerine hic girmeden, acik bir BAGIMLILIK HATASI raporuyla
# guvenli sekilde durur.
#
# Calistirmak icin: PowerShell'i bu klasorde (KAZEN_AI\search) acin ve:
#   powershell -ExecutionPolicy Bypass -File .\setup_searxng.ps1
# calistirin. Yonetici izni GEREKMEZ (Docker Desktop zaten kuruluysa).

$ErrorActionPreference = "Continue"
$SearxPort = 8890

function Section($title) {
    Write-Host ""
    Write-Host "=== $title ===" -ForegroundColor Cyan
}

function Stop-DependencyFailure($reason, $howToFix) {
    Write-Host ""
    Write-Host "=== BAGIMLILIK HATASI (Dependency Failure) ===" -ForegroundColor Red
    Write-Host "Bu, SearXNG'nin kendisiyle ilgili bir hata DEGILDIR." -ForegroundColor Red
    Write-Host "Neden: $reason" -ForegroundColor Red
    Write-Host "Cozum: $howToFix" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Health check ve JSON API testleri BU NEDENLE HIC CALISTIRILMADI." -ForegroundColor Yellow
    Write-Host "SearXNG container'i baslatilmadi, hicbir Kaizen verisine dokunulmadi." -ForegroundColor Yellow
    exit 1
}

# ---------------------------------------------------------------------------
# A1: mevcut ortami incele
# ---------------------------------------------------------------------------
Section "A1: Ortam kontrolu"

$os = Get-CimInstance Win32_OperatingSystem
Write-Host "OS: $($os.Caption) ($($os.OSArchitecture))"

$pyVersion = (python --version 2>&1)
Write-Host "Python: $pyVersion"

# --- Docker CLI VARLIGINI kontrol et -----------------------------------
# ONEMLI DUZELTME: `$LASTEXITCODE -eq 0` hemen `docker --version` sonrasi
# guvenilir DEGILDIR -- docker.exe hic yoksa PowerShell "CommandNotFound"
# hatasi verir ve $LASTEXITCODE'u DEGISTIRMEZ (bir onceki native komuttan,
# ornegin basarili `python --version`'dan kalan degeri -- yani 0 -- tasir).
# Bu, Docker gercekte kurulu olmadigi halde script'in "Docker var" sanip
# devam etmesine (ve container hic baslamadigi halde "baslatildi" demesine)
# neden oluyordu. Duzeltme: once `Get-Command` ile ikili dosyanin (binary)
# GERCEKTEN var olup olmadigini, $LASTEXITCODE'dan BAGIMSIZ olarak kontrol et.
$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerCmd) {
    Write-Host "Docker CLI: BULUNAMADI" -ForegroundColor Yellow
    Stop-DependencyFailure `
        "Docker CLI ('docker' komutu) bu bilgisayarda bulunamadi." `
        "Docker Desktop'i kurun (asagidaki 'Docker Desktop + WSL2 kurulum rehberi'ne bakin), sonra bu betigi tekrar calistirin."
}

$dockerVersion = (docker --version 2>&1)
Write-Host "Docker CLI: $dockerVersion" -ForegroundColor Green

# --- Docker DAEMON'UNUN gercekten calisir durumda oldugunu kontrol et ---
# `docker info`, docker.exe var oldugu icin GERCEKTEN calisir, bu yuzden
# hemen ardindan okunan $LASTEXITCODE burada guvenilirdir (araya baska
# hicbir native komut girmiyor).
$dockerInfoOutput = (docker info 2>&1)
$daemonOk = ($LASTEXITCODE -eq 0)
if (-not $daemonOk) {
    Write-Host "Docker daemon: CALISMIYOR" -ForegroundColor Yellow
    Stop-DependencyFailure `
        "Docker CLI kurulu, ama Docker Desktop/daemon su an calismiyor (docker info basarisiz oldu)." `
        "Docker Desktop uygulamasini acin, sistem tepsisinde 'Docker Desktop is running' gorene kadar bekleyin, sonra bu betigi tekrar calistirin."
}
Write-Host "Docker daemon: CALISIYOR" -ForegroundColor Green
$dockerOk = $true

try {
    $ollama = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -TimeoutSec 3 -UseBasicParsing
    Write-Host "Ollama: CALISIYOR (localhost:11434)" -ForegroundColor Green
} catch {
    Write-Host "Ollama: localhost:11434'e erisilemedi (kapali olabilir, sorun degil)" -ForegroundColor Yellow
}

$existing = docker ps -a --filter "name=kaizen-searxng" --format "{{.Names}}: {{.Status}}" 2>$null
if ($existing) {
    Write-Host "Mevcut kaizen-searxng container'i bulundu: $existing"
}

$portBusy = $null
try {
    $portBusy = Get-NetTCPConnection -LocalPort $SearxPort -ErrorAction SilentlyContinue
} catch {}
if ($portBusy) {
    Write-Host "UYARI: Port $SearxPort zaten baska bir islem tarafindan kullaniliyor!" -ForegroundColor Red
    Write-Host "setup_searxng.ps1 icindeki `$SearxPort degiskenini degistirip tekrar calistirin." -ForegroundColor Red
    exit 1
} else {
    Write-Host "Port ${SearxPort}: musait"
}

# ---------------------------------------------------------------------------
# A2: SearXNG'yi yerel (localhost-only) kur
# ---------------------------------------------------------------------------
Section "A2: SearXNG kurulumu (yalniz 127.0.0.1)"

$dataDir = Join-Path $PSScriptRoot "searxng-data"
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

docker rm -f kaizen-searxng 2>$null | Out-Null

docker run -d --name kaizen-searxng --restart unless-stopped `
  -p 127.0.0.1:${SearxPort}:8080 `
  -v "${dataDir}:/etc/searxng" `
  -e "BASE_URL=http://127.0.0.1:${SearxPort}/" `
  -e "INSTANCE_NAME=kaizen-local" `
  searxng/searxng:latest

$runExitCode = $LASTEXITCODE
if ($runExitCode -ne 0) {
    Write-Host "HATA: 'docker run' basarisiz oldu (exit code: $runExitCode). Yukaridaki hatayi kontrol edin." -ForegroundColor Red
    Write-Host "Bu bir SearXNG hatasi degil, container BASLATILAMADI -- hicbir sey 'calisiyor' sayilmamalidir." -ForegroundColor Red
    exit 1
}

# --- Container'in GERCEKTEN 'running' durumuna gectigini dogrula --------
# `docker run -d`'nin exit code 0 vermesi container'in KALICI sekilde
# 'running' durumunda oldugu anlamina gelmez (ornegin hemen crash edebilir).
# A3'e (JSON API ayari) gecmeden once bunu aktif olarak dogruluyoruz.
Write-Host "Container baslatma komutu kabul edildi, gercekten 'running' durumuna gecmesi bekleniyor..."
$isRunning = $false
for ($i = 0; $i -lt 15; $i++) {
    Start-Sleep -Seconds 1
    $state = (docker inspect -f "{{.State.Running}}" kaizen-searxng 2>$null)
    if ($state -eq "true") {
        $isRunning = $true
        break
    }
}

if (-not $isRunning) {
    $lastState = (docker inspect -f "{{.State.Status}}" kaizen-searxng 2>$null)
    $lastLogs = (docker logs --tail 20 kaizen-searxng 2>&1)
    Write-Host "HATA: kaizen-searxng container'i 15 saniye icinde 'running' durumuna gecmedi (son durum: $lastState)." -ForegroundColor Red
    Write-Host "Son container loglari:" -ForegroundColor Yellow
    Write-Host $lastLogs
    Write-Host "Bu bir SearXNG kurulum hatasidir (Docker bagimliligi degil) -- A3'e (JSON API) GECILMIYOR." -ForegroundColor Red
    exit 1
}

Write-Host "Container 'running' durumunda dogrulandi (kaizen-searxng)." -ForegroundColor Green
Write-Host "Ayarlar dosyasinin olusmasi icin ek 5 saniye bekleniyor..."
Start-Sleep -Seconds 5

# ---------------------------------------------------------------------------
# A3: JSON search API'yi etkinlestir
# ---------------------------------------------------------------------------
Section "A3: JSON arama API'sini etkinlestirme"

$settingsPath = Join-Path $dataDir "settings.yml"
if (Test-Path $settingsPath) {
    $content = Get-Content $settingsPath -Raw
    if ($content -match "formats:\s*\r?\n\s*-\s*html") {
        if ($content -notmatch "-\s*json") {
            $content = $content -replace "(formats:\s*\r?\n\s*-\s*html)", "`$1`r`n    - json"
            Set-Content -Path $settingsPath -Value $content -Encoding UTF8
            Write-Host "settings.yml icine 'json' formati eklendi." -ForegroundColor Green
            docker restart kaizen-searxng | Out-Null
            Write-Host "Container yeniden baslatildi, 8 saniye bekleniyor..."
            Start-Sleep -Seconds 8
        } else {
            Write-Host "'json' formati zaten etkin."
        }
    } else {
        Write-Host "UYARI: settings.yml icinde beklenen 'formats:' bolumu otomatik bulunamadi." -ForegroundColor Yellow
        Write-Host "Elle duzeltme: $settingsPath dosyasini acin, 'search:' altindaki 'formats:' listesine '- json' satiri ekleyin, sonra 'docker restart kaizen-searxng' calistirin." -ForegroundColor Yellow
    }
} else {
    Write-Host "UYARI: settings.yml henuz olusmadi ($settingsPath). Birkac saniye sonra tekrar deneyin." -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# Kendi kendini dogrulama (yalniz Docker/container basariliysa buraya gelinir)
# ---------------------------------------------------------------------------
Section "Kendi kendini dogrulama"

$healthOk = $false
$jsonOk = $false
try {
    $health = Invoke-WebRequest -Uri "http://127.0.0.1:${SearxPort}/" -TimeoutSec 10 -UseBasicParsing
    if ($health.StatusCode -eq 200) {
        Write-Host "Health check: BASARILI (HTTP 200)" -ForegroundColor Green
        $healthOk = $true
    }
} catch {
    Write-Host "Health check BASARISIZ (SearXNG container calisiyor olmasina ragmen): $_" -ForegroundColor Red
}

try {
    $resp = Invoke-RestMethod -Uri "http://127.0.0.1:${SearxPort}/search?q=muhasebe&format=json" -TimeoutSec 15
    $count = $resp.results.Count
    Write-Host "JSON arama testi: BASARILI -- 'muhasebe' sorgusu icin $count sonuc dondu." -ForegroundColor Green
    $jsonOk = $true
} catch {
    Write-Host "JSON arama testi BASARISIZ: $_" -ForegroundColor Red
    Write-Host "En sik neden: settings.yml'de 'json' formati hala etkin degil (yukaridaki uyariya bakin) veya 'search: formats:' anahtari farkli girintiyle yazilmis." -ForegroundColor Yellow
}

Section "OZET"
Write-Host "Bagimlilik durumu:  Docker CLI OK, Docker daemon OK, container running OK"
Write-Host "SearXNG adresi: http://127.0.0.1:${SearxPort}/"
Write-Host "JSON arama:     http://127.0.0.1:${SearxPort}/search?q=SORGU&format=json"
Write-Host "Health check:   $(if ($healthOk) {'OK'} else {'BASARISIZ'})"
Write-Host "JSON API:       $(if ($jsonOk) {'OK'} else {'BASARISIZ'})"
Write-Host ""
Write-Host "Bu betik burada durur. Sonraki adim (arama benchmark'i) ayri, bilerek"
Write-Host "manuel baslatilan bir adimdir -- bu betigin kapsaminda DEGILDIR."
Write-Host ""
Write-Host "Durdurmak icin:  docker stop kaizen-searxng"
Write-Host "Kaldirmak icin:  docker rm -f kaizen-searxng"
