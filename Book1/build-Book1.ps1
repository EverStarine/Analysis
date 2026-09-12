# 分析学 · 第一卷 一键编译（专用）
#
# 放在本卷目录内，专用于 Book1。在 TeXstudio 中配置一次即可一键整卷编译：
#     xelatex → biber → 三类索引 → xelatex ×2 → 校验 → 更新根目录 Book1.pdf
# 单独运行 XeLaTeX 不会显示参考文献与索引，必须走完整流程。
#
# TeXstudio 配置（选项 → 构建 → 用户命令，命令与工作目录按下面填写）：
#     命令:
#       "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "C:\\Users\\75054\\Documents\\Codex\\分析学\\Book1\\编译-Book1.ps1" -NoPause > txs:///messages 2>&1
#     工作目录: C:\\Users\\75054\\Documents\\Codex\\分析学\\Book1
#
# 说明：命令用 PowerShell 的绝对路径与脚本的绝对路径，并把输出重定向到 TeXstudio
# 的消息面板；-NoPause 使脚本不等待回车（重定向后没有窗口接收输入）。若希望看到
# 控制台窗口，去掉 “> txs:///messages 2>&1” 与 “-NoPause” 即可。
#
# 命令行用法（在本目录下，会等待回车以便查看结果）：
#     powershell -ExecutionPolicy Bypass -File .\编译-Book1.ps1
#
# param 必须位于所有可执行语句之前，故紧随文件头注释。
param([switch]$NoPause)

$ErrorActionPreference = 'Stop'

$book     = 'Book1'
$bookDir  = $PSScriptRoot                 # 本脚本位于该卷目录内
$root     = Split-Path -Parent $bookDir  # 项目根目录
$buildDir = Join-Path $root "tmp/build/$book"
$relOut   = "../tmp/build/$book"   # 必须用相对路径：biber 无法打开含中文的绝对路径
                                    # （两者须配合：下面以 Set-Location 固定工作目录为卷目录）
$style    = Join-Path $root 'Shared/analysis.ist'
$target   = Join-Path $root "$book.pdf"
$log      = Join-Path $buildDir "$book.log"
$t0       = Get-Date

function Say([string]$t, [string]$c = 'Gray') { Write-Host "  $t" -ForegroundColor $c }
function Fail([string]$t) {
    Write-Host "  [错误] $t" -ForegroundColor Red
    if (-not $NoPause) {
        Write-Host ""
        Write-Host "按回车键关闭…" -ForegroundColor DarkGray
        [void](Read-Host)
    }
    exit 1
}

Write-Host ""
Write-Host "=== 分析学 第一卷 编译（$book）===" -ForegroundColor Cyan
Say "源码目录：$bookDir"
Say "输出目录：$buildDir"

foreach ($t in 'xelatex', 'biber', 'makeindex') {
    if (-not (Get-Command $t -ErrorAction SilentlyContinue)) { Fail "未找到 $t，请确认 TeX Live 已加入 PATH。" }
}
if (-not (Test-Path -LiteralPath $style)) { Fail "缺少索引样式：$style" }

New-Item -ItemType Directory -Force -Path $buildDir | Out-Null

function Step([string]$exe, [string[]]$argv, [string]$what) {
    & $exe @argv
    if ($LASTEXITCODE -ne 0) {
        if (Test-Path -LiteralPath $log) {
            $errs = Select-String -LiteralPath $log -Pattern '^! ' -ErrorAction SilentlyContinue | Select-Object -First 5
            foreach ($e in $errs) { Write-Host ("    " + $e.Line.Trim()) -ForegroundColor Yellow }
        }
        Fail "$what 失败（退出码 $LASTEXITCODE）。日志：$log"
    }
}

# 首轮 XeLaTeX；若辅助文件损坏（中断的编译常留下半个 \newlabel），
# 自动清空构建目录重试一次，避免每次都要手工清理。
function Invoke-FirstPass {
    & xelatex @('-interaction=nonstopmode', '-halt-on-error', "--output-directory=$relOut", "$book.tex") | Out-Null
    return $LASTEXITCODE
}

# 关键：把进程工作目录固定为卷目录。这样相对输出目录 ../tmp/build/BookN 才解析正确，
# 且相对资源 ../Shared/References.bib 可用；又不使用含中文的绝对路径（biber 会失败）。
Set-Location -LiteralPath $bookDir
try {
    Write-Host ""
    Write-Host "[1/5] 首轮 XeLaTeX" -ForegroundColor Cyan
    $code = Invoke-FirstPass
    if ($code -ne 0 -and (Test-Path -LiteralPath $log)) {
        $broken = (Get-Content -LiteralPath $log -Raw) -match '@newl@bel|Runaway argument'
        if ($broken) {
            Say '检测到辅助文件损坏，清空构建目录后重试…' 'Yellow'
            Remove-Item -LiteralPath $buildDir -Recurse -Force -ErrorAction SilentlyContinue
            New-Item -ItemType Directory -Force -Path $buildDir | Out-Null
            $code = Invoke-FirstPass
        }
    }
    if ($code -ne 0) {
        if (Test-Path -LiteralPath $log) {
            Select-String -LiteralPath $log -Pattern '^! ' -ErrorAction SilentlyContinue |
                Select-Object -First 5 | ForEach-Object { Write-Host ("    " + $_.Line.Trim()) -ForegroundColor Yellow }
        }
        Fail "首轮 XeLaTeX 失败（退出码 $code）。日志：$log"
    }
    Say '已生成辅助文件' 'Green'

    Write-Host ""
    Write-Host "[2/5] Biber（参考文献）" -ForegroundColor Cyan
    $bcf = Join-Path $buildDir "$book.bcf"
    if ((Test-Path -LiteralPath $bcf) -and ((Get-Content -LiteralPath $bcf -Raw) -match '<bcf:citekey[^>]*>')) {
        Step 'biber' @("--output-directory=$relOut", "$relOut/$book") 'Biber'
        Say "已生成 $book.bbl" 'Green'
    }
    else { Say '本卷无引文，跳过' 'DarkGray' }
}
finally { Pop-Location }

Write-Host ""
Write-Host "[3/5] 三类索引" -ForegroundColor Cyan
foreach ($idxName in 'chinese', 'foreign', 'symbols') {
    $idx = Join-Path $buildDir "$idxName.idx"
    if (-not (Test-Path -LiteralPath $idx) -or (Get-Item -LiteralPath $idx).Length -eq 0) {
        Say "$idxName 索引为空，跳过" 'DarkGray'
        continue
    }
    Push-Location -LiteralPath $buildDir
    try { Step 'makeindex' @('-q', '-s', $style, "$idxName.idx") "makeindex（$idxName）" }
    finally { Pop-Location }
    $ilg = Get-Content -Raw -LiteralPath (Join-Path $buildDir "$idxName.ilg")
    if ($ilg -notmatch '\b0 rejected\b' -or $ilg -notmatch '\b0 warnings\b') {
        Fail "$idxName 索引存在拒收条目或警告：$buildDir\$idxName.ilg"
    }
    Say "$idxName 索引：零拒收、零警告" 'Green'
}

Push-Location -LiteralPath $bookDir
try {
    foreach ($pass in 1..2) {
        Write-Host ""
        Write-Host "[$($pass + 3)/5] 第 $($pass + 1) 轮 XeLaTeX" -ForegroundColor Cyan
        Step 'xelatex' @('-interaction=nonstopmode', '-halt-on-error', "--output-directory=$relOut", "$book.tex") "第 $($pass + 1) 轮 XeLaTeX"
        Say '完成' 'Green'
    }
}
finally { Pop-Location }

Write-Host ""
Write-Host "[校验与交付]" -ForegroundColor Cyan
$pdf = Join-Path $buildDir "$book.pdf"
if (-not (Test-Path -LiteralPath $pdf)) { Fail "未生成 PDF：$pdf" }

$text = Get-Content -LiteralPath $log -Raw
$nErr  = ([regex]::Matches($text, '(?m)^! ')).Count
$nRef  = ([regex]::Matches($text, 'There were undefined references')).Count
$nCite = ([regex]::Matches($text, 'Citation .* undefined')).Count
$nMiss = ([regex]::Matches($text, 'Missing character')).Count
Say "编译错误 $nErr ／ 未定义引用 $nRef ／ 未定义引文 $nCite ／ 缺字 $nMiss"
$pages = (Select-String -LiteralPath $log -Pattern 'Output written on' | Select-Object -Last 1).Line
Say $pages.Trim()

if ($nErr -gt 0 -or $nRef -gt 0 -or $nCite -gt 0) { Fail "存在错误或未定义引用，不覆盖成品。日志：$log" }

Copy-Item -LiteralPath $pdf -Destination $target -Force
Say "已更新成品：$target" 'Green'
$secs = [int]((Get-Date) - $t0).TotalSeconds
Write-Host ""
Write-Host "完成，用时 $secs 秒。" -ForegroundColor Green
if (-not $NoPause) {
    Write-Host "按回车键关闭窗口…" -ForegroundColor DarkGray
    [void](Read-Host)
}
