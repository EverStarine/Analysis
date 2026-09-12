# 分析学 · 一键编译
#
# 用途：在 TeXstudio 或终端中一次完成整卷编译（XeLaTeX → Biber → 三类索引 → XeLaTeX×2）。
# 单独运行 XeLaTeX 不会显示参考文献与索引，必须走完整流程。
#
# 用法（任选其一）：
#   1) 在 TeXstudio 中把本文件设为“用户命令”或在“构建”里添加外部工具：
#        命令: powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0一键编译.ps1"
#        工作目录: 当前文档所在目录
#   2) 命令行：
#        powershell -ExecutionPolicy Bypass -File 一键编译.ps1           # 自动识别所在卷
#        powershell -ExecutionPolicy Bypass -File 一键编译.ps1 -Volume 2  # 指定卷
#
# 脚本会自动定位项目根目录与 Shared/analysis.ist，无论从项目根还是从 BookN 目录调用。

[CmdletBinding()]
param(
    [ValidateRange(1, 3)][int]$Volume = 0,
    [switch]$KeepConsole
)

$ErrorActionPreference = 'Stop'
$script:startTime = Get-Date

function Write-Step([string]$Text) { Write-Host "`n=== $Text ===" -ForegroundColor Cyan }
function Write-Ok([string]$Text) { Write-Host "  [OK] $Text" -ForegroundColor Green }
function Write-Info([string]$Text) { Write-Host "  $Text" }
function Write-Err([string]$Text) { Write-Host "  [错误] $Text" -ForegroundColor Red }

# ---- 定位项目根目录 ----
function Find-ProjectRoot {
    $dir = (Get-Location).Path
    while ($dir) {
        if ((Test-Path -LiteralPath (Join-Path $dir 'Shared/Preamble.tex')) -and
            (Test-Path -LiteralPath (Join-Path $dir 'Book1/Book1.tex'))) { return $dir }
        $parent = Split-Path -Parent $dir
        if ($parent -eq $dir) { break }
        $dir = $parent
    }
    return $null
}

$root = Find-ProjectRoot
if (-not $root) {
    Write-Err "未找到项目根目录（需包含 Shared/Preamble.tex 与 Book1/Book1.tex）。"
    Write-Err "请在《分析学》项目目录内运行本脚本。"
    exit 1
}
Write-Host "项目根目录：$root"

# ---- 确定卷号 ----
if ($Volume -eq 0) {
    $here = (Get-Location).Path
    $found = @()
    foreach ($v in 1..3) {
        if (Test-Path -LiteralPath (Join-Path $here "Book$v.tex")) { $found += $v }
    }
    if ($found.Count -eq 1) {
        $Volume = $found[0]
    }
    else {
        $available = @()
        foreach ($v in 1..3) {
            if (Test-Path -LiteralPath (Join-Path $root "Book$v/Book$v.tex")) { $available += $v }
        }
        if ($available.Count -eq 1) { $Volume = $available[0] }
        else {
            Write-Err "无法自动判断卷号。请用 -Volume 指定，例如：-Volume 1"
            exit 1
        }
    }
}

$book = "Book$Volume"
$bookDir = Join-Path $root $book
$buildDir = Join-Path $root "tmp/build/$book"
$pdf = Join-Path $buildDir "$book.pdf"
$targetPdf = Join-Path $root "$book.pdf"
$logFile = Join-Path $buildDir "$book.log"

Write-Host "编译目标：$book（$bookDir）" -ForegroundColor Yellow

# ---- 检查工具 ----
$tools = @{}
foreach ($t in 'xelatex', 'biber', 'makeindex') {
    $c = Get-Command $t -ErrorAction SilentlyContinue
    if (-not $c) { Write-Err "未找到 $t，请确认 TeX Live 已加入 PATH。"; exit 1 }
    $tools[$t] = $c.Source
}

$indexStyle = Join-Path $root 'Shared/analysis.ist'
if (-not (Test-Path -LiteralPath $indexStyle)) {
    Write-Err "缺少索引样式：$indexStyle"
    exit 1
}

New-Item -ItemType Directory -Force -Path $buildDir | Out-Null

# 相对路径（供 XeLaTeX/Biber 使用；中文绝对路径会让 biber 失败）
$relOut = "../tmp/build/$book"

function Invoke-Tool {
    param([string]$Exe, [string[]]$Arguments, [string]$What)
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) {
        Write-Err "$What 失败（退出码 $LASTEXITCODE）"
        if (Test-Path -LiteralPath $logFile) {
            $errs = Select-String -LiteralPath $logFile -Pattern '^! ' -ErrorAction SilentlyContinue |
                    Select-Object -First 5
            if ($errs) {
                Write-Host "  日志中的首批错误：" -ForegroundColor Yellow
                $errs | ForEach-Object { Write-Host ("    " + $_.Line.Trim()) -ForegroundColor Yellow }
            }
        }
        Write-Info "完整日志：$logFile"
        exit 1
    }
}

Push-Location -LiteralPath $bookDir
try {
    # 1) 首轮：生成 .aux/.bcf/.idx，供 Biber 与 makeindex 使用
    Write-Step "第 1 步 / 5：首轮 XeLaTeX"
    Invoke-Tool $tools.xelatex @('-interaction=nonstopmode', '-halt-on-error',
        "--output-directory=$relOut", "$book.tex") '首轮 XeLaTeX'
    Write-Ok "已生成辅助文件"

    # 2) Biber：本卷实际引用的参考文献
    Write-Step "第 2 步 / 5：Biber（参考文献）"
    $bcf = Join-Path $buildDir "$book.bcf"
    $hasCitations = $false
    if (Test-Path -LiteralPath $bcf) {
        $hasCitations = (Get-Content -LiteralPath $bcf -Raw) -match '<bcf:citekey[^>]*>'
    }
    if ($hasCitations) {
        Invoke-Tool $tools.biber @("--output-directory=$relOut", "$relOut/$book") 'Biber'
        Write-Ok "已生成 $book.bbl"
    }
    else {
        Write-Info "本卷无引文，跳过 Biber"
    }
}
finally { Pop-Location }

Push-Location -LiteralPath $buildDir
try {
    # 3) 三类索引各自单独处理（不可合并为一次调用）
    Write-Step "第 3 步 / 5：三类索引（chinese / foreign / symbols）"
    $didIndex = $false
    foreach ($name in 'chinese', 'foreign', 'symbols') {
        $idx = Join-Path $buildDir "$name.idx"
        if (-not (Test-Path -LiteralPath $idx) -or (Get-Item -LiteralPath $idx).Length -eq 0) {
            Write-Info "$name 索引为空，跳过"
            continue
        }
        Invoke-Tool $tools.makeindex @('-q', '-s', $indexStyle, "$name.idx") "makeindex（$name）"
        $ilg = Join-Path $buildDir "$name.ilg"
        $ilgText = Get-Content -LiteralPath $ilg -Raw
        if ($ilgText -notmatch '\b0 rejected\b' -or $ilgText -notmatch '\b0 warnings\b') {
            Write-Err "$name 索引存在拒收条目或警告，请检查 $ilg"
            exit 1
        }
        Write-Ok "$name 索引：零拒收、零警告"
        $didIndex = $true
    }
    if (-not $didIndex) { Write-Info "本卷无索引条目" }
}
finally { Pop-Location }

Push-Location -LiteralPath $bookDir
try {
    # 4) 后两轮：排入书目与索引，稳定目录、交叉引用与书签
    foreach ($pass in 1..2) {
        Write-Step "第 $($pass + 3) 步 / 5：第 $($pass + 1) 轮 XeLaTeX"
        Invoke-Tool $tools.xelatex @('-interaction=nonstopmode', '-halt-on-error',
            "--output-directory=$relOut", "$book.tex") "第 $($pass + 1) 轮 XeLaTeX"
        Write-Ok "完成"
    }
}
finally { Pop-Location }

# ---- 校验并交付 ----
Write-Step "校验与交付"
if (-not (Test-Path -LiteralPath $pdf)) { Write-Err "未生成 PDF：$pdf"; exit 1 }

$log = Get-Content -LiteralPath $logFile -Raw
$nErr = ([regex]::Matches($log, '(?m)^! ')).Count
$nUndefRef = ([regex]::Matches($log, 'There were undefined references')).Count
$nUndefCite = ([regex]::Matches($log, 'Citation .* undefined')).Count
$nMissing = ([regex]::Matches($log, 'Missing character')).Count
$pages = (Select-String -LiteralPath $logFile -Pattern 'Output written on' |
          Select-Object -Last 1).Line

Write-Info "编译错误 $nErr / 未定义引用 $nUndefRef / 未定义引文 $nUndefCite / 缺字 $nMissing"
Write-Info $pages.Trim()

if ($nErr -gt 0 -or $nUndefRef -gt 0 -or $nUndefCite -gt 0) {
    Write-Err "存在错误或未定义引用，不覆盖成品 PDF。日志：$logFile"
    exit 1
}

Copy-Item -LiteralPath $pdf -Destination $targetPdf -Force
Write-Ok "已更新成品：$targetPdf"

$secs = [int]((Get-Date) - $script:startTime).TotalSeconds
Write-Host "`n完成，用时 $secs 秒。" -ForegroundColor Green

if (-not $KeepConsole) {
    Write-Host "按回车键关闭窗口…" -ForegroundColor DarkGray
    [void](Read-Host)
}
