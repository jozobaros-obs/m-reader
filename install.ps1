<#
    MD Reader – inštalačný skript pre Windows.

    Čo robí:
      1. Nainštaluje potrebné Python knižnice (PySide6, Markdown, Pygments).
      2. Vygeneruje ikonu aplikácie (mdreader.ico).
      3. Vytvorí launcher (run_hidden.vbs) ktorý spustí appku cez pythonw
         bez čierneho okna konzoly.
      4. Zaregistruje ProgID a asociuje prípony .md / .markdown, aby sa
         súbory otvárali v MD Readeri (dvojklik / "Otvoriť pomocou").
      5. Vytvorí zástupcu v Štart menu.

    Spustenie:
        powershell -ExecutionPolicy Bypass -File install.ps1

    Odinštalovanie:
        powershell -ExecutionPolicy Bypass -File uninstall.ps1
#>

$ErrorActionPreference = "Stop"

$AppName    = "MD Reader"
$ProgId     = "MDReader.Markdown"
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Definition
$MainPy     = Join-Path $ScriptDir "md_reader.py"
$IconPath   = Join-Path $ScriptDir "mdreader.ico"
$VbsPath    = Join-Path $ScriptDir "run_hidden.vbs"
$Extensions = @(".md", ".markdown", ".mdown", ".mkd")

Write-Host "=== Inštalácia $AppName ===" -ForegroundColor Cyan

# --------------------------------------------------------------------------- #
# 1) Nájdi Python (pythonw.exe)                                               #
# --------------------------------------------------------------------------- #
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) {
    throw "Python sa nenašiel v PATH. Nainštaluj Python 3.9+ a skús znova."
}
$pythonDir = Split-Path -Parent $python
$pythonw   = Join-Path $pythonDir "pythonw.exe"
if (-not (Test-Path $pythonw)) { $pythonw = $python }

Write-Host "Python:  $python"
Write-Host "Pythonw: $pythonw"

# --------------------------------------------------------------------------- #
# 2) Nainštaluj závislosti                                                     #
# --------------------------------------------------------------------------- #
Write-Host "`nInštalujem Python knižnice..." -ForegroundColor Cyan
& $python -m pip install --upgrade pip | Out-Null
& $python -m pip install -r (Join-Path $ScriptDir "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "pip install zlyhal." }

# --------------------------------------------------------------------------- #
# 3) Vygeneruj ikonu (PNG zabalené do .ico – podporované vo Windows Vista+)    #
# --------------------------------------------------------------------------- #
Write-Host "`nGenerujem ikonu..." -ForegroundColor Cyan
& (Join-Path $ScriptDir "make_icon.ps1") -OutPath $IconPath

# --------------------------------------------------------------------------- #
# 4) Launcher bez konzoly (VBS -> pythonw)                                     #
# --------------------------------------------------------------------------- #
$vbs = @"
' Spustí MD Reader cez pythonw bez okna konzoly.
Set args = WScript.Arguments
cmd = """$pythonw"" ""$MainPy"""
If args.Count > 0 Then
    cmd = cmd & " """ & args(0) & """"
End If
CreateObject("WScript.Shell").Run cmd, 1, False
"@
Set-Content -Path $VbsPath -Value $vbs -Encoding ASCII
Write-Host "Launcher: $VbsPath"

# --------------------------------------------------------------------------- #
# 5) Registrácia ProgID + asociácia prípon (HKCU – bez admin práv)            #
# --------------------------------------------------------------------------- #
Write-Host "`nRegistrujem asociáciu .md súborov..." -ForegroundColor Cyan
$classes = "HKCU:\Software\Classes"

# ProgID
$progRoot = Join-Path $classes $ProgId
New-Item -Path $progRoot -Force | Out-Null
Set-ItemProperty -Path $progRoot -Name "(default)" -Value "Markdown dokument"

New-Item -Path (Join-Path $progRoot "DefaultIcon") -Force | Out-Null
Set-ItemProperty -Path (Join-Path $progRoot "DefaultIcon") -Name "(default)" -Value "`"$IconPath`""

$cmdKey = Join-Path $progRoot "shell\open\command"
New-Item -Path $cmdKey -Force | Out-Null
# wscript spustí VBS launcher a odovzdá cestu k súboru (%1)
$openCmd = "wscript.exe `"$VbsPath`" `"%1`""
Set-ItemProperty -Path $cmdKey -Name "(default)" -Value $openCmd

Set-ItemProperty -Path (Join-Path $progRoot "shell\open") -Name "FriendlyAppName" -Value $AppName

# Prípony -> ProgID
foreach ($ext in $Extensions) {
    $extKey = Join-Path $classes $ext
    New-Item -Path $extKey -Force | Out-Null
    Set-ItemProperty -Path $extKey -Name "(default)" -Value $ProgId
    $owp = Join-Path $extKey "OpenWithProgids"
    New-Item -Path $owp -Force | Out-Null
    New-ItemProperty -Path $owp -Name $ProgId -Value ([byte[]]@()) -PropertyType Binary -Force | Out-Null
}

# Oznám shellu zmenu asociácií
$signature = @'
[System.Runtime.InteropServices.DllImport("shell32.dll")]
public static extern void SHChangeNotify(int eventId, int flags, System.IntPtr item1, System.IntPtr item2);
'@
$shell = Add-Type -MemberDefinition $signature -Name "ShellNotify" -Namespace "Win32" -PassThru
$shell::SHChangeNotify(0x08000000, 0x0000, [System.IntPtr]::Zero, [System.IntPtr]::Zero)

# --------------------------------------------------------------------------- #
# 6) Zástupca v Štart menu                                                     #
# --------------------------------------------------------------------------- #
Write-Host "Vytváram zástupcu v Štart menu..." -ForegroundColor Cyan
$startMenu = [Environment]::GetFolderPath("Programs")
$lnkPath   = Join-Path $startMenu "$AppName.lnk"
$wshell    = New-Object -ComObject WScript.Shell
$sc        = $wshell.CreateShortcut($lnkPath)
$sc.TargetPath       = "wscript.exe"
$sc.Arguments        = "`"$VbsPath`""
$sc.WorkingDirectory = $ScriptDir
$sc.IconLocation     = $IconPath
$sc.Description       = "Čítačka Markdown súborov"
$sc.Save()

# --------------------------------------------------------------------------- #
Write-Host "`n=== Hotovo! ===" -ForegroundColor Green
Write-Host "MD Reader nájdeš v Štart menu."
Write-Host ""
Write-Host "POZNÁMKA: Windows kvôli ochrane niekedy vyžaduje jednorazové" -ForegroundColor Yellow
Write-Host "potvrdenie predvolenej aplikácie. Ak sa .md neotvára automaticky:" -ForegroundColor Yellow
Write-Host "  1) klikni pravým na .md súbor -> Otvoriť pomocou -> Zvoliť inú aplikáciu"
Write-Host "  2) vyber 'MD Reader' a zaškrtni 'Vždy používať túto aplikáciu'."
