$apiKey = $env:NGC_API_KEY
$headers = @{
    "Content-Type" = "application/json"
    "Authorization" = "Bearer $apiKey"
}
$body = @{
    model = "nvidia/nemotron-3.5-lightning-30b-a3b"
    stream = $false
    temperature = 0.2
    messages = @(
        @{role = "system"; content = "Sen Kaizen AI'sın: Türkçe konuşan, kaynağa dayalı çalışan bir muhasebe ve mali müşavirlik yardımcısısın."},
        @{role = "user"; content = "KDV nedir? Kısaca açıkla."}
    )
} | ConvertTo-Json -Depth 5

Invoke-WebRequest -Uri "https://integrate.api.nvidia.com/v1/chat/completions" -Method POST -Headers $headers -Body $body -TimeoutSec 120