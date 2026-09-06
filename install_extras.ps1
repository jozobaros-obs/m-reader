<#
    M Reader – voliteľné rozšírenia pre čítanie nahlas a OCR.

    Nainštaluje (cez winget, vyžaduje potvrdenie UAC):
      * eSpeak NG   – offline hlasy pre jazyky, ktoré Windows nemá (napr. slovenčinu)
      * Tesseract OCR + slovenský jazyk – čítanie textu zo skenovaných PDF

    Základná aplikácia funguje aj bez týchto rozšírení; tie len zapnú
    slovenské čítanie a OCR skenovaných PDF.

    Spustenie:
        powershell -ExecutionPolicy Bypass -File install_extras.ps1
#>

$ErrorActionPreference = "Continue"

Write-Host "=== M Reader – voliteľné rozšírenia (TTS + OCR) ===" -ForegroundColor Cyan

if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    throw "winget sa nenašiel. Nainštaluj 'App Installer' z Microsoft Store a skús znova."
}

# --- eSpeak NG (offline TTS, aj slovenčina) -------------------------------- #
Write-Host "`nInštalujem eSpeak NG..." -ForegroundColor Cyan
winget install --id eSpeak-NG.eSpeak-NG -e --accept-source-agreements --accept-package-agreements

# --- Tesseract OCR --------------------------------------------------------- #
Write-Host "`nInštalujem Tesseract OCR..." -ForegroundColor Cyan
winget install --id UB-Mannheim.TesseractOCR -e --accept-source-agreements --accept-package-agreements

# --- Slovenský jazyk pre OCR ----------------------------------------------- #
Write-Host "`nDopĺňam slovenský jazyk pre OCR (slk.traineddata)..." -ForegroundColor Cyan
$tessDirs = @(
    "C:\Program Files\Tesseract-OCR\tessdata",
    "C:\Program Files (x86)\Tesseract-OCR\tessdata",
    (Join-Path $env:LOCALAPPDATA "Programs\Tesseract-OCR\tessdata")
)
$tessData = $tessDirs | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($tessData) {
    $dest = Join-Path $tessData "slk.traineddata"
    if (-not (Test-Path $dest)) {
        try {
            Invoke-WebRequest -UseBasicParsing `
                -Uri "https://github.com/tesseract-ocr/tessdata/raw/main/slk.traineddata" `
                -OutFile $dest
            Write-Host "Slovenský OCR jazyk pridaný: $dest" -ForegroundColor Green
        } catch {
            Write-Host "Nepodarilo sa stiahnuť slk.traineddata: $($_.Exception.Message)" -ForegroundColor Yellow
        }
    } else {
        Write-Host "Slovenský OCR jazyk už je nainštalovaný."
    }
} else {
    Write-Host "tessdata priečinok sa nenašiel – slovenský OCR jazyk pridaj ručne." -ForegroundColor Yellow
}

Write-Host "`n=== Hotovo! ===" -ForegroundColor Green
Write-Host "Reštartuj M Reader, aby rozšírenia načítal."
