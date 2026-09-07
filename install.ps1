<#
    M Reader – inštalačný skript pre Windows.

    Čo robí:
      1. Nájde vhodný Python – a ak žiadny nie je, stiahne a nainštaluje ho
         z python.org (bez admin práv, len pre aktuálneho používateľa).
      2. Nainštaluje potrebné Python knižnice (z requirements.txt).
      3. Vygeneruje ikonu aplikácie.
      4. Vytvorí launcher (M Reader.exe) ktorý spustí appku cez pythonw
         bez čierneho okna konzoly.
      5. Zaregistruje ProgID a asociuje prípony .md, .html a .pdf, aby sa
         súbory otvárali v M Readeri (dvojklik / "Otvoriť pomocou").
      6. Vytvorí zástupcu v Štart menu.

    Spustenie:
        powershell -ExecutionPolicy Bypass -File install.ps1

    Odinštalovanie:
        powershell -ExecutionPolicy Bypass -File uninstall.ps1

    Prepínače:
        -Yes                 nepýtať sa pred inštaláciou Pythonu (pre skripty/CI)
        -NoPythonInstall     Python nikdy neinštalovať; ak chýba, skript skončí
        -PythonVersion <v>   ktorú verziu Pythonu stiahnuť (default 3.13.15)

    Pozn. k Microsoft Store Pythonu:
        Python z Microsoft Store sa NEDÁ použiť. Jeho site-packages leží pod
        cestou dlhou ~145 znakov (…\Packages\PythonSoftwareFoundation.Python…\
        LocalCache\…) a keďže PySide6 obsahuje hlboko zanorené súbory, pip
        narazí na limit 260 znakov a spadne na "OSError: [Errno 2]". Skript
        preto Store Python preskočí a nainštaluje riadny Python z python.org
        do %LOCALAPPDATA%\Programs\Python, kde je cesta krátka.
#>

param(
    [switch]$Yes,
    [switch]$NoPythonInstall,
    [string]$PythonVersion = "3.13.15"
)

$ErrorActionPreference = "Stop"

$AppName    = "M Reader"
$ProgId     = "MReader.Document"
$ScriptDir  = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Definition }
$MainPy     = Join-Path $ScriptDir "m_reader.py"
$IconPath   = Join-Path $ScriptDir "mdreader.ico"
$ExePath    = Join-Path $ScriptDir "M Reader.exe"
$Extensions = @(".md", ".markdown", ".mdown", ".mkd", ".html", ".htm", ".pdf")

Write-Host "=== Inštalácia $AppName ===" -ForegroundColor Cyan

$ReqFile = Join-Path $ScriptDir "requirements.txt"
$PipLog  = Join-Path $env:TEMP "m-reader-pip.log"

# --------------------------------------------------------------------------- #
# 1) Nájdi vhodný Python                                                       #
#                                                                              #
#    "Vhodný" = verzia 3.9+ a NIE z Microsoft Store. Store Python má           #
#    site-packages pod ~145 znakov dlhou cestou, takže pip pri PySide6         #
#    narazí na limit 260 znakov a spadne (viď hlavička skriptu).               #
# --------------------------------------------------------------------------- #

# Je to Python z Microsoft Store? Pozor: sysconfig vracia systémový prefix,
# kým Store Python reálne inštaluje do user-site pod \Packages\… – preto sa
# pýtame aj na site.getusersitepackages() a na sys.base_prefix.
function Test-StorePython($py) {
    if ($py -like "*\WindowsApps\*") { return $true }
    # ErrorActionPreference dočasne na Continue: keby sa python.exe nedal spustiť,
    # nechceme aby to zhodilo celý skript – stačí nám návratový kód.
    $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    try {
        $probe = & $py -c "import sys, site; print(sys.base_prefix + '|' + (site.getusersitepackages() or ''))"
        if ($LASTEXITCODE -ne 0) { return $false }
        return ($probe -like "*WindowsApps*" -or $probe -like "*PythonSoftwareFoundation.Python*")
    } catch {
        return $false
    } finally {
        $ErrorActionPreference = $old
    }
}

# Vráti verziu ako [version], alebo $null ak sa Python nedá spustiť
function Get-PythonVersion($py) {
    $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    try {
        $v = & $py -c "import sys; print('%d.%d.%d' % sys.version_info[:3])"
        if ($LASTEXITCODE -ne 0 -or -not $v) { return $null }
        return [version]$v
    } catch {
        return $null
    } finally {
        $ErrorActionPreference = $old
    }
}

# Pozbiera všetkých kandidátov na Python z PATH, py launchera, registry
# a štandardných inštalačných ciest; vráti prvý použiteľný.
function Find-SuitablePython {
    $cands = New-Object System.Collections.Generic.List[string]

    Get-Command python.exe -All -ErrorAction SilentlyContinue |
        ForEach-Object { $cands.Add($_.Source) }

    # py launcher pozná aj Pythony, ktoré nie sú v PATH
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
        try {
            foreach ($line in (& py -0p)) {
                if ($line -match '([A-Za-z]:\\[^\r\n]*python\.exe)') { $cands.Add($Matches[1]) }
            }
        } catch {
        } finally {
            $ErrorActionPreference = $old
        }
    }

    foreach ($hive in @("HKCU:\Software\Python\PythonCore", "HKLM:\SOFTWARE\Python\PythonCore")) {
        Get-ChildItem $hive -ErrorAction SilentlyContinue | ForEach-Object {
            $ip = (Get-ItemProperty (Join-Path $_.PSPath "InstallPath") -ErrorAction SilentlyContinue)."(default)"
            if ($ip) { $cands.Add((Join-Path $ip "python.exe")) }
        }
    }

    Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe" -ErrorAction SilentlyContinue |
        ForEach-Object { $cands.Add($_.FullName) }
    Get-ChildItem "C:\Python3*\python.exe" -ErrorAction SilentlyContinue |
        ForEach-Object { $cands.Add($_.FullName) }

    foreach ($c in ($cands | Select-Object -Unique)) {
        if (-not (Test-Path $c)) { continue }
        if (Test-StorePython $c) {
            Write-Host "  preskakujem (Microsoft Store): $c" -ForegroundColor DarkGray
            continue
        }
        $ver = Get-PythonVersion $c
        if ($null -eq $ver -or $ver -lt [version]"3.9.0") { continue }
        Write-Host "  vyhovuje: $c (Python $ver)" -ForegroundColor Green
        return $c
    }
    return $null
}

# Stiahne a nainštaluje Python z python.org len pre aktuálneho používateľa
# (InstallAllUsers=0 → žiadne admin práva, cieľ %LOCALAPPDATA%\Programs\Python).
function Install-PythonFromOrg($version) {
    $arch = if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") { "arm64" } else { "amd64" }
    $url  = "https://www.python.org/ftp/python/$version/python-$version-$arch.exe"
    $dst  = Join-Path $env:TEMP "python-$version-$arch.exe"

    Write-Host "Sťahujem $url ..." -ForegroundColor Cyan
    $oldProgress = $ProgressPreference
    $ProgressPreference = "SilentlyContinue"      # inak je Invoke-WebRequest veľmi pomalý
    try {
        Invoke-WebRequest -Uri $url -OutFile $dst -UseBasicParsing
    } catch {
        throw "Nepodarilo sa stiahnuť Python ($url): $($_.Exception.Message)"
    } finally {
        $ProgressPreference = $oldProgress
    }

    Write-Host "Inštalujem Python $version (len pre teba, bez admin práv)..." -ForegroundColor Cyan
    $p = Start-Process -FilePath $dst -Wait -PassThru -ArgumentList @(
        "/passive", "InstallAllUsers=0", "PrependPath=1",
        "Include_launcher=1", "Include_test=0", "Include_pip=1"
    )
    Remove-Item $dst -Force -ErrorAction SilentlyContinue
    if ($p.ExitCode -ne 0) { throw "Inštalátor Pythonu skončil s kódom $($p.ExitCode)." }

    # PATH sa zmenil v registri, ale nie v tomto procese – načítaj ho znova
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User")
}

Write-Host "`nHľadám vhodný Python..." -ForegroundColor Cyan
$python = Find-SuitablePython

if (-not $python) {
    Write-Host "Nenašiel sa žiadny použiteľný Python." -ForegroundColor Yellow
    Write-Host "(Python z Microsoft Store sa použiť nedá – PySide6 sa doň kvôli" -ForegroundColor Yellow
    Write-Host " dĺžke cesty vo Windows nenainštaluje.)" -ForegroundColor Yellow

    if ($NoPythonInstall) {
        throw "Python sa nenašiel. Nainštaluj ho z https://www.python.org/downloads/ (zaškrtni 'Add python.exe to PATH') a spusti skript znova."
    }

    if (-not $Yes) {
        $answer = Read-Host "`nStiahnuť a nainštalovať Python $PythonVersion z python.org? [A/n]"
        if ($answer -and $answer -notmatch '^(a|A|y|Y|ano|yes)$') {
            throw "Inštalácia zrušená používateľom."
        }
    }

    Install-PythonFromOrg $PythonVersion

    Write-Host "`nHľadám Python znova..." -ForegroundColor Cyan
    $python = Find-SuitablePython
    if (-not $python) {
        throw "Python sa nainštaloval, ale skript ho nenašiel. Zavri toto okno, otvor nové a spusti install.ps1 znova."
    }
}

# --------------------------------------------------------------------------- #
# 2) Nainštaluj závislosti                                                     #
# --------------------------------------------------------------------------- #
Write-Host "`nInštalujem Python knižnice (PySide6 má ~250 MB, chvíľu to potrvá)..." -ForegroundColor Cyan
Remove-Item $PipLog -Force -ErrorAction SilentlyContinue
& $python -m pip install --upgrade pip | Out-Null
& $python -m pip install --log $PipLog -r $ReqFile
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "pip install zlyhal. Kompletný log: $PipLog" -ForegroundColor Red
    Write-Host "Ak log spomína 'enable-long-paths', ide o limit dĺžky cesty vo Windows –" -ForegroundColor Yellow
    Write-Host "skontroluj, či Python nie je z Microsoft Store." -ForegroundColor Yellow
    throw "pip install zlyhal."
}

# pythonw.exe patriaci k tomu Pythonu, do ktorého sme nainštalovali
$pythonw = Join-Path (Split-Path -Parent $python) "pythonw.exe"
if (-not (Test-Path $pythonw)) { $pythonw = $python }

Write-Host "Python:  $python"
Write-Host "Pythonw: $pythonw"

# Overenie, že sa naozaj dá naimportovať to podstatné
& $python -c "import PySide6, markdown, pygments, pymupdf, markdownify, langdetect; from PySide6.QtWebEngineWidgets import QWebEngineView"
if ($LASTEXITCODE -ne 0) { throw "Knižnice sa nainštalovali, ale nedajú sa naimportovať. Pozri log: $PipLog" }
Write-Host "Knižnice OK." -ForegroundColor Green

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
    Remove-Item $ExePath -Force -ErrorAction SilentlyContinue
    $cscOut = & $csc /nologo /target:winexe /win32icon:"$IconPath" /out:"$ExePath" "$CsPath"
    if ($LASTEXITCODE -eq 0 -and (Test-Path $ExePath)) {
        $UseExe = $true
    } else {
        Write-Host "csc.exe nedokázal zostaviť launcher:" -ForegroundColor Yellow
        $cscOut | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkYellow }
    }
} else {
    Write-Host "csc.exe sa nenašiel ($csc) – použijem VBS launcher." -ForegroundColor Yellow
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

# Staršie verzie skriptu vytvárali v projekte .venv. Knižnice sú teraz priamo
# v Pythone, takže ak tu nejaké ostalo, len zaberá miesto.
$OldVenv = Join-Path $ScriptDir ".venv"
if (Test-Path $OldVenv) {
    $venvMB = [math]::Round((Get-ChildItem $OldVenv -Recurse -Force -File `
                -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum / 1MB)
    Write-Host ""
    Write-Host "Pozn.: v projekte ostalo staré .venv ($venvMB MB), ktoré už nič" -ForegroundColor Yellow
    Write-Host "nepoužíva. Zmažeš ho takto:" -ForegroundColor Yellow
    Write-Host "  Remove-Item -Recurse -Force `"$OldVenv`""
}

Write-Host ""
Write-Host "POZNÁMKA: Windows kvôli ochrane niekedy vyžaduje jednorazové" -ForegroundColor Yellow
Write-Host "potvrdenie predvolenej aplikácie. Ak sa súbor neotvára automaticky:" -ForegroundColor Yellow
Write-Host "  1) klikni pravým na súbor -> Otvoriť pomocou -> Zvoliť inú aplikáciu"
Write-Host "  2) vyber 'M Reader' a zaškrtni 'Vždy používať túto aplikáciu'."
