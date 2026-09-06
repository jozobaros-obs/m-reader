<#
    Zostaví M Reader do samostatného .exe pomocou PyInstalleru.
    Výsledok nepotrebuje nainštalovaný Python.

    Použitie:
        powershell -File build_exe.ps1            # priečinok s .exe (odporúčané)
        powershell -File build_exe.ps1 -OneFile   # jeden veľký .exe

    Výstup:
        dist\M Reader\M Reader.exe   (režim priečinka)
        dist\M Reader.exe            (režim -OneFile)

    Pozn.: Kvôli QtWebEngine je balík veľký (~200–300 MB). Režim priečinka
    je spoľahlivejší a štartuje rýchlejšie; -OneFile dá jeden súbor, ale
    štartuje pomalšie (rozbaľuje sa do dočasného priečinka).
#>
param(
    [switch]$OneFile
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$IconPath  = Join-Path $ScriptDir "mdreader.ico"

Write-Host "=== Build M Reader .exe ===" -ForegroundColor Cyan

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { throw "Python sa nenašiel v PATH." }

# ikona (ak chýba, vygeneruj)
if (-not (Test-Path $IconPath)) {
    Write-Host "Generujem ikonu..." -ForegroundColor Cyan
    & (Join-Path $ScriptDir "make_icon.ps1") -OutPath $IconPath
}

Write-Host "Inštalujem závislosti + PyInstaller..." -ForegroundColor Cyan
& $python -m pip install -r (Join-Path $ScriptDir "requirements.txt") | Out-Null
& $python -m pip install --upgrade pyinstaller | Out-Null

$args = @(
    "--noconfirm", "--clean",
    "--windowed",                       # bez okna konzoly
    "--name", "M Reader",
    "--icon", $IconPath,
    "--add-data", "$IconPath;.",        # ikona dostupná za behu
    "--collect-all", "PySide6"          # istota, že sa pribalí QtWebEngine
)
if ($OneFile) { $args += "--onefile" }
$args += (Join-Path $ScriptDir "m_reader.py")

Write-Host "`nSpúšťam PyInstaller (chvíľu to potrvá)..." -ForegroundColor Cyan
Push-Location $ScriptDir
try {
    & $python -m PyInstaller @args
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller zlyhal." }
} finally {
    Pop-Location
}

$exe = if ($OneFile) { Join-Path $ScriptDir "dist\M Reader.exe" }
       else { Join-Path $ScriptDir "dist\M Reader\M Reader.exe" }

Write-Host "`n=== Hotovo! ===" -ForegroundColor Green
Write-Host "Spustiteľný súbor: $exe"
Write-Host "Otvoríš ho dvojklikom, alebo cez príkaz s cestou k dokumentu."
