<#
    M Reader – inštalačný skript pre Windows.

    Čo robí:
      1. Nainštaluje potrebné Python knižnice (z requirements.txt).
      2. Vygeneruje ikonu aplikácie.
      3. Vytvorí launcher (run_hidden.vbs) ktorý spustí appku cez pythonw
         bez čierneho okna konzoly.
      4. Zaregistruje ProgID a asociuje prípony .md, .html a .pdf, aby sa
         súbory otvárali v M Readeri (dvojklik / "Otvoriť pomocou").
      5. Vytvorí zástupcu v Štart menu.

    Spustenie:
        powershell -ExecutionPolicy Bypass -File install.ps1

    Odinštalovanie:
        powershell -ExecutionPolicy Bypass -File uninstall.ps1
#>

$ErrorActionPreference = "Stop"

$AppName    = "M Reader"
$ProgId     = "MReader.Document"
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Definition
$MainPy     = Join-Path $ScriptDir "m_reader.py"
$IconPath   = Join-Path $ScriptDir "mdreader.ico"
$ExePath    = Join-Path $ScriptDir "M Reader.exe"
$Extensions = @(".md", ".markdown", ".mdown", ".mkd", ".html", ".htm", ".pdf")

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
# 4) Launcher .exe s ikonou (aby dialóg predvolených programov ukázal          #
#    našu ikonu, nie ikonu wscriptu). Bez konzoly (winexe).                     #
# --------------------------------------------------------------------------- #
Write-Host "`nZostavujem launcher .exe s ikonou..." -ForegroundColor Cyan
Get-Process "M Reader" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

$CsPath = Join-Path $ScriptDir "launcher.cs"
$cs = @"
using System;
using System.Diagnostics;
class Launcher {
    static void Main(string[] a) {
        var psi = new ProcessStartInfo(@"$pythonw");
        psi.UseShellExecute = false;
        psi.Arguments = "\"" + @"$MainPy" + "\"" + (a.Length > 0 ? " \"" + a[0] + "\"" : "");
        try { Process.Start(psi); } catch { }
    }
}
"@
Set-Content -Path $CsPath -Value $cs -Encoding ASCII

$csc = Join-Path ([Runtime.InteropServices.RuntimeEnvironment]::GetRuntimeDirectory()) "csc.exe"
$UseExe = $false
if (Test-Path $csc) {
    & $csc /nologo /target:winexe /win32icon:"$IconPath" /out:"$ExePath" "$CsPath" | Out-Null
    if ($LASTEXITCODE -eq 0 -and (Test-Path $ExePath)) { $UseExe = $true }
}

if ($UseExe) {
    Remove-Item $CsPath -Force -ErrorAction SilentlyContinue
    $Launcher = $ExePath
    $OpenCmd  = "`"$ExePath`" `"%1`""
    Write-Host "Launcher: $ExePath"
} else {
    # fallback: VBS cez wscript (bez ikony v dialógu, ale funkčné)
    $VbsPath = Join-Path $ScriptDir "run_hidden.vbs"
    $vbs = @"
Set args = WScript.Arguments
cmd = """$pythonw"" ""$MainPy"""
If args.Count > 0 Then
    cmd = cmd & " """ & args(0) & """"
End If
CreateObject("WScript.Shell").Run cmd, 1, False
"@
    Set-Content -Path $VbsPath -Value $vbs -Encoding ASCII
    $Launcher = "wscript.exe"
    $OpenCmd  = "wscript.exe `"$VbsPath`" `"%1`""
    Write-Host "Launcher (fallback VBS): $VbsPath" -ForegroundColor Yellow
}

# --------------------------------------------------------------------------- #
# 5) Registrácia ProgID + asociácia prípon (HKCU – bez admin práv)            #
# --------------------------------------------------------------------------- #
Write-Host "`nRegistrujem asociácie .md / .html / .pdf ..." -ForegroundColor Cyan
$classes = "HKCU:\Software\Classes"

# ProgID
$progRoot = Join-Path $classes $ProgId
New-Item -Path $progRoot -Force | Out-Null
Set-ItemProperty -Path $progRoot -Name "(default)" -Value "M Reader dokument"

New-Item -Path (Join-Path $progRoot "DefaultIcon") -Force | Out-Null
Set-ItemProperty -Path (Join-Path $progRoot "DefaultIcon") -Name "(default)" -Value "`"$IconPath`""

$cmdKey = Join-Path $progRoot "shell\open\command"
New-Item -Path $cmdKey -Force | Out-Null
Set-ItemProperty -Path $cmdKey -Name "(default)" -Value $OpenCmd

Set-ItemProperty -Path (Join-Path $progRoot "shell\open") -Name "FriendlyAppName" -Value $AppName

# Ak máme .exe launcher, zaregistruj ho aj ako "Application" – vďaka tomu
# dialóg "Otvoriť pomocou" / predvolené programy ukáže našu ikonu.
if ($UseExe) {
    $appRoot = Join-Path $classes "Applications\M Reader.exe"
    New-Item -Path (Join-Path $appRoot "shell\open\command") -Force | Out-Null
    Set-ItemProperty -Path (Join-Path $appRoot "shell\open\command") -Name "(default)" -Value $OpenCmd
    Set-ItemProperty -Path $appRoot -Name "FriendlyAppName" -Value $AppName
    New-Item -Path (Join-Path $appRoot "DefaultIcon") -Force | Out-Null
    Set-ItemProperty -Path (Join-Path $appRoot "DefaultIcon") -Name "(default)" -Value "`"$ExePath`",0"
}

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
if ($UseExe) {
    $sc.TargetPath = $ExePath
    $sc.Arguments  = ""
} else {
    $sc.TargetPath = "wscript.exe"
    $sc.Arguments  = "`"$VbsPath`""
}
$sc.WorkingDirectory = $ScriptDir
$sc.IconLocation     = $IconPath
$sc.Description       = "Čítačka MD / HTML / PDF súborov"
$sc.Save()

# --------------------------------------------------------------------------- #
Write-Host "`n=== Hotovo! ===" -ForegroundColor Green
Write-Host "M Reader nájdeš v Štart menu."
Write-Host ""
Write-Host "POZNÁMKA: Windows kvôli ochrane niekedy vyžaduje jednorazové" -ForegroundColor Yellow
Write-Host "potvrdenie predvolenej aplikácie. Ak sa súbor neotvára automaticky:" -ForegroundColor Yellow
Write-Host "  1) klikni pravým na súbor -> Otvoriť pomocou -> Zvoliť inú aplikáciu"
Write-Host "  2) vyber 'M Reader' a zaškrtni 'Vždy používať túto aplikáciu'."
