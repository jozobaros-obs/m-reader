<#
    Vygeneruje modernú ikonu aplikácie MD Reader (mdreader.ico).
    Dizajn: zaoblený štvorec s fialovo-indigovým gradientom a bielym
    Markdown symbolom ("M" + šípka dole). PNG sa zabalí do .ico
    (podporované vo Windows Vista a novších).

    Použitie:  powershell -File make_icon.ps1 [-OutPath cesta.ico]
#>
param(
    [string]$OutPath = (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Definition) "mdreader.ico")
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$size = 256
$bmp  = New-Object System.Drawing.Bitmap($size, $size)
$g    = [System.Drawing.Graphics]::FromImage($bmp)
$g.SmoothingMode   = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic

# --- zaoblený štvorec (dlaždica) ------------------------------------------- #
function New-RoundedRect([float]$x, [float]$y, [float]$w, [float]$h, [float]$r) {
    $path = New-Object System.Drawing.Drawing2D.GraphicsPath
    $d = $r * 2
    $path.AddArc($x,        $y,        $d, $d, 180, 90)
    $path.AddArc($x+$w-$d,  $y,        $d, $d, 270, 90)
    $path.AddArc($x+$w-$d,  $y+$h-$d,  $d, $d,   0, 90)
    $path.AddArc($x,        $y+$h-$d,  $d, $d,  90, 90)
    $path.CloseFigure()
    return $path
}

$margin = 16.0
$inner  = [float]($size - 2 * $margin)
$half   = [float]($inner / 2)
$tile   = New-RoundedRect $margin $margin $inner $inner 52

# gradient (fialová -> indigová)
$rect = New-Object System.Drawing.RectangleF($margin, $margin, $inner, $inner)
$c1 = [System.Drawing.Color]::FromArgb(255, 34, 197, 94)    # #22C55E green
$c2 = [System.Drawing.Color]::FromArgb(255, 21, 128, 61)    # #15803D dark green
$grad = New-Object System.Drawing.Drawing2D.LinearGradientBrush($rect, $c1, $c2, 55.0)
$g.FillPath($grad, $tile)

# jemný svetlý lesk hore
$glossRect = New-Object System.Drawing.RectangleF($margin, $margin, $inner, $half)
$glossPath = New-RoundedRect $margin $margin $inner $half 52
$g1 = [System.Drawing.Color]::FromArgb(46, 255, 255, 255)
$g2 = [System.Drawing.Color]::FromArgb(0, 255, 255, 255)
$gloss = New-Object System.Drawing.Drawing2D.LinearGradientBrush($glossRect, $g1, $g2, 90.0)
$g.FillPath($gloss, $glossPath)

# --- biely Markdown symbol ------------------------------------------------- #
$white = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::White)
$pen   = New-Object System.Drawing.Pen ([System.Drawing.Color]::White, 20.0)
$pen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
$pen.EndCap   = [System.Drawing.Drawing2D.LineCap]::Round
$pen.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round

# písmeno "M" (ľavá časť)
$m = @(
    (New-Object System.Drawing.PointF(66, 172)),
    (New-Object System.Drawing.PointF(66,  92)),
    (New-Object System.Drawing.PointF(104, 138)),
    (New-Object System.Drawing.PointF(142,  92)),
    (New-Object System.Drawing.PointF(142, 172))
)
$g.DrawLines($pen, $m)

# šípka dole (pravá časť) – stopka + hrot
$g.DrawLine($pen, 182, 92, 182, 146)
$arrow = @(
    (New-Object System.Drawing.PointF(160, 138)),
    (New-Object System.Drawing.PointF(204, 138)),
    (New-Object System.Drawing.PointF(182, 176))
)
$g.FillPolygon($white, $arrow)

$g.Dispose()

# --- PNG -> ICO ------------------------------------------------------------ #
$ms = New-Object System.IO.MemoryStream
$bmp.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
$png = $ms.ToArray()
$ms.Dispose(); $bmp.Dispose()

$ico = New-Object System.IO.MemoryStream
$bw  = New-Object System.IO.BinaryWriter($ico)
$bw.Write([UInt16]0)             # reserved
$bw.Write([UInt16]1)             # type = icon
$bw.Write([UInt16]1)             # count
$bw.Write([Byte]0)               # width  (0 = 256)
$bw.Write([Byte]0)               # height (0 = 256)
$bw.Write([Byte]0)               # palette
$bw.Write([Byte]0)               # reserved
$bw.Write([UInt16]1)             # planes
$bw.Write([UInt16]32)            # bpp
$bw.Write([UInt32]$png.Length)   # size
$bw.Write([UInt32]22)            # offset
$bw.Write($png)
$bw.Flush()
[System.IO.File]::WriteAllBytes($OutPath, $ico.ToArray())
$bw.Dispose(); $ico.Dispose()

Write-Host "Ikona vytvorená: $OutPath"
