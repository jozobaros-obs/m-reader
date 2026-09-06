<#
    MD Reader – odinštalovanie. Odstráni asociácie, ProgID a zástupcu.
    Python knižnice (PySide6 atď.) ponecháva – tie môžeš odstrániť ručne cez pip.
#>

$ErrorActionPreference = "SilentlyContinue"

$AppName    = "MD Reader"
$ProgId     = "MDReader.Markdown"
$Extensions = @(".md", ".markdown", ".mdown", ".mkd")
$classes    = "HKCU:\Software\Classes"

Write-Host "=== Odinštalovanie $AppName ===" -ForegroundColor Cyan

# ProgID
Remove-Item -Path (Join-Path $classes $ProgId) -Recurse -Force

# Odstráň ProgID z prípon
foreach ($ext in $Extensions) {
    $extKey = Join-Path $classes $ext
    $current = (Get-ItemProperty -Path $extKey -Name "(default)" -ErrorAction SilentlyContinue)."(default)"
    if ($current -eq $ProgId) {
        Remove-ItemProperty -Path $extKey -Name "(default)" -ErrorAction SilentlyContinue
    }
    Remove-Item -Path (Join-Path $extKey "OpenWithProgids\$ProgId") -Force -ErrorAction SilentlyContinue
}

# Zástupca v Štart menu
$startMenu = [Environment]::GetFolderPath("Programs")
Remove-Item -Path (Join-Path $startMenu "$AppName.lnk") -Force

# Oznám shellu zmenu
$signature = @'
[System.Runtime.InteropServices.DllImport("shell32.dll")]
public static extern void SHChangeNotify(int eventId, int flags, System.IntPtr item1, System.IntPtr item2);
'@
$shell = Add-Type -MemberDefinition $signature -Name "ShellNotify2" -Namespace "Win32" -PassThru
$shell::SHChangeNotify(0x08000000, 0x0000, [System.IntPtr]::Zero, [System.IntPtr]::Zero)

Write-Host "Hotovo. Asociácie a zástupca boli odstránené." -ForegroundColor Green
Write-Host "Knižnice odstrániš (voliteľne) príkazom:" -ForegroundColor Yellow
Write-Host "  python -m pip uninstall PySide6 Markdown Pygments"
