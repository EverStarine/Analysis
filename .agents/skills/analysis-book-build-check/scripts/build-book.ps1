[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$ProjectRoot,
    [ValidateSet(1,2,3)][int[]]$Volume,
    [string[]]$ChangedFiles,
    [switch]$Build,
    [string]$CheckManifest,
    [ValidateRange(3,12)][int]$MaxPasses = 6,
    [string]$TexBin
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath $ProjectRoot).Path.TrimEnd('\','/')
$sourceExclusions = '\.(aux|log|toc|out|bcf|bbl|blg|run\.xml|idx|ind|ilg|fls|fdb_latexmk|synctex(\.gz)?|xdv|nav|snm|vrb|lof|lot)$'

function Get-SourceFiles([string]$Base, [int[]]$Volumes) {
    foreach ($folder in (@('Shared') + @($Volumes | ForEach-Object { "Book$_" }))) {
        $directory = Join-Path $Base $folder
        if (!(Test-Path -LiteralPath $directory -PathType Container)) { throw "Missing source directory: $directory" }
        $items = @(Get-ChildItem -LiteralPath $directory -Recurse -Force)
        if (@($items | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }).Count) {
            throw "Source links/junctions require explicit scope review: $directory"
        }
        foreach ($file in ($items | Where-Object {
            !$_.PSIsContainer -and
            $_.Name -notmatch $sourceExclusions -and
            -not ($folder -match '^Book[123]$' -and $_.Name -eq "$folder.pdf")
        } | Sort-Object FullName)) {
            [pscustomobject]@{ path=$file.FullName.Substring($Base.Length+1).Replace('\','/'); sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash }
        }
    }
}
function Get-Identity($Entries) {
    return (($Entries | Sort-Object path | ForEach-Object { $_.path + ':' + $_.sha256 }) -join "`n")
}
function Write-Json($Value, [string]$Path) {
    $json = $Value | ConvertTo-Json -Depth 12
    [IO.File]::WriteAllText($Path, $json, (New-Object Text.UTF8Encoding($false)))
}
function Find-Tool([string]$Name) {
    if ($TexBin) {
        $candidate = Join-Path $TexBin "$Name.exe"
        if (Test-Path -LiteralPath $candidate) { return (Resolve-Path -LiteralPath $candidate).Path }
        throw "Missing tool in TexBin: $Name"
    }
    $found = Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) { return $found.Source }
    $candidate = "D:\texstudio\texlive\2025\bin\windows\$Name.exe"
    if (Test-Path -LiteralPath $candidate) { return $candidate }
    throw "Existing tool not found: $Name. Diagnose PATH or pass -TexBin; no installation attempted."
}
function Get-FileDigest([string]$Path) {
    if (Test-Path -LiteralPath $Path) { return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash }
    return ''
}
function Invoke-Logged([string]$Executable, [string[]]$Arguments, [string]$Log) {
    # Windows PowerShell treats native stderr as ErrorRecord; preserve native exit status.
    $savedPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $Executable @Arguments *> $Log
        $nativeExit = $LASTEXITCODE
    } finally { $ErrorActionPreference = $savedPreference }
    $script:commands.Add([pscustomobject]@{ executable=$Executable; arguments=@($Arguments); cwd=(Get-Location).Path; log=$Log; exitCode=$nativeExit })
    if ($nativeExit -ne 0) { throw "Tool failed (exit $nativeExit): $Executable; see $Log" }
}
function Get-AuxIdentity([string]$Directory) {
    return ((Get-ChildItem -LiteralPath $Directory -File | Where-Object { $_.Name -match '\.(aux|toc|out|bcf|idx|ind|bbl|lof|lot)$' } | Sort-Object Name | ForEach-Object { $_.Name + ':' + (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash }) -join "`n")
}

if ($CheckManifest) {
    if ($Build -or $Volume -or $ChangedFiles) { throw '-CheckManifest cannot be combined with build/scope options.' }
    $manifestPath = (Resolve-Path -LiteralPath $CheckManifest).Path
    $saved = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($saved.schema -ne 1 -or $saved.status -ne 'success') { throw 'Manifest is not a supported successful build.' }
    $current = @(Get-SourceFiles $root @($saved.volumes))
    $sourcesMatch = (Get-Identity $current) -ceq (Get-Identity @($saved.sources))
    $pdfResults = @($saved.results | ForEach-Object {
        $pdf = Join-Path (Split-Path -Parent $manifestPath) $_.pdf
        [pscustomobject]@{ volume=$_.volume; pdf=$pdf; pdfMatches=((Get-FileDigest $pdf) -eq $_.pdfSha256) }
    })
    [pscustomobject]@{ mode='identity-check'; sourcesMatch=$sourcesMatch; pdfs=$pdfResults; scope='Selected Book directories and Shared; conservative source identity, not a mathematical or visual acceptance.' } | ConvertTo-Json -Depth 6
    if (!$sourcesMatch -or @($pdfResults | Where-Object { !$_.pdfMatches }).Count) { exit 2 }
    exit 0
}
if ($Volume -and $ChangedFiles) { throw 'Use either -Volume or -ChangedFiles.' }
$unknown = New-Object 'System.Collections.Generic.List[string]'
$notes = New-Object 'System.Collections.Generic.List[string]'
$selected = @()
if ($Volume) { $selected = @($Volume | Sort-Object -Unique) }
elseif ($ChangedFiles) {
    foreach ($entry in $ChangedFiles) {
        $path = $entry.Replace('\','/')
        if ([IO.Path]::IsPathRooted($entry) -or $path -match '(^|/)\.\.(/|$)') { $unknown.Add($entry); continue }
        while ($path.StartsWith('./')) { $path = $path.Substring(2) }
        if ($path -match '^Shared/') { $selected += @(1,2,3) }
        elseif ($path -match '^Book([123])/') { $selected += [int]$Matches[1] }
        elseif ($path -match '^[^/]+\.md$|^\.agents/skills/|^\.gitignore$') { $notes.Add("Documentation/config review only: $entry") }
        else { $unknown.Add($entry) }
    }
    $selected = @($selected | Sort-Object -Unique)
} else { $unknown.Add('No volume or changed-file scope supplied.') }
$plan = [ordered]@{ mode='plan'; projectRoot=$root; volumes=@($selected); unknownScope=@($unknown.ToArray()); notes=@($notes.ToArray()); buildRequested=[bool]$Build }
if (!$Build) { $plan | ConvertTo-Json -Depth 6; if ($unknown.Count) { exit 2 }; exit 0 }
if ($unknown.Count) { $plan | ConvertTo-Json -Depth 6; throw 'Resolve unknown scope before building.' }
if (!$selected.Count) { $plan | ConvertTo-Json -Depth 6; exit 0 }

$toolPaths = @{}
$toolVersions = @{}
foreach ($tool in @('xelatex','biber','makeindex')) {
    $toolPaths[$tool] = Find-Tool $tool
    # makeindex has no portable --version; its executable hash is recorded instead.
    $toolVersions[$tool] = [ordered]@{ path=$toolPaths[$tool]; binarySha256=(Get-FileDigest $toolPaths[$tool]) }
    if ($tool -ne 'makeindex') {
        $savedPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = 'Continue'
            $versionOutput = @(& $toolPaths[$tool] '--version' 2>&1)
        } finally { $ErrorActionPreference = $savedPreference }
        $toolVersions[$tool].version = (($versionOutput | ForEach-Object { $_.ToString() }) -join "`n")
    }
}
$runName = 'skill-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0,8)
$runDir = Join-Path $root "tmp/build/$runName"
$snapshot = Join-Path $runDir 'source'
New-Item -ItemType Directory -Path $snapshot -Force | Out-Null
$script:commands = New-Object 'System.Collections.Generic.List[object]'
$manifest = [ordered]@{ schema=1; status='building'; createdUtc=[DateTime]::UtcNow.ToString('o'); projectRoot=$root; volumes=@($selected); sources=@(); tools=$toolVersions; maxPasses=$MaxPasses; commands=@(); results=@(); error=$null }
$manifestPath = Join-Path $runDir 'manifest.json'
try {
    $before = @(Get-SourceFiles $root $selected)
    foreach ($file in $before) {
        $target = Join-Path $snapshot $file.path
        New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
        Copy-Item -LiteralPath (Join-Path $root $file.path) -Destination $target
    }
    $copied = @(Get-SourceFiles $snapshot $selected)
    $after = @(Get-SourceFiles $root $selected)
    if ((Get-Identity $before) -cne (Get-Identity $copied) -or (Get-Identity $before) -cne (Get-Identity $after)) { throw 'Sources changed while snapshotting; retry from a coherent source state.' }
    $manifest.sources = $copied
    foreach ($number in $selected) {
        $book = "Book$number"
        $volumeDir = Join-Path $snapshot $book
        if (!(Test-Path -LiteralPath (Join-Path $volumeDir "$book.tex"))) { throw "Missing entry point: $book/$book.tex" }
        $buildDir = Join-Path $runDir "build/$book"
        New-Item -ItemType Directory -Path $buildDir -Force | Out-Null
        $relativeOut = "../../build/$book"
        $processed = @{}
        $previousState = ''
        $stable = $false
        Push-Location -LiteralPath $volumeDir
        try {
            for ($pass=1; $pass -le $MaxPasses; $pass++) {
                Invoke-Logged $toolPaths.xelatex @('-interaction=nonstopmode','-halt-on-error','-file-line-error','-recorder','-no-shell-escape',"--output-directory=$relativeOut","$book.tex") (Join-Path $buildDir "xelatex-$pass.txt")
                $processorRan = $false
                $bcf = Join-Path $buildDir "$book.bcf"
                if ((Test-Path -LiteralPath $bcf) -and ((Get-Content -LiteralPath $bcf -Raw) -match '<bcf:citekey[^>]*>')) {
                    $digest = Get-FileDigest $bcf
                    if (!$processed.ContainsKey('biber') -or $processed.biber -ne $digest) {
                        Invoke-Logged $toolPaths.biber @("--output-directory=$relativeOut","$relativeOut/$book") (Join-Path $buildDir "biber-$pass.txt")
                        if ((Get-Content -LiteralPath (Join-Path $buildDir "$book.blg") -Raw) -match '\bERROR\s+-') { throw "Biber reported an error: $buildDir/$book.blg" }
                        $processed.biber = $digest; $processorRan = $true
                    }
                }
                foreach ($index in @('chinese','foreign','symbols')) {
                    $idx = Join-Path $buildDir "$index.idx"
                    if (!(Test-Path -LiteralPath $idx) -or (Get-Item -LiteralPath $idx).Length -eq 0) { continue }
                    $digest = Get-FileDigest $idx
                    if (!$processed.ContainsKey($index) -or $processed[$index] -ne $digest) {
                        $style = (Resolve-Path -LiteralPath (Join-Path $snapshot 'Shared/analysis.ist')).Path
                        Push-Location -LiteralPath $buildDir
                        try { Invoke-Logged $toolPaths.makeindex @('-q','-s',$style,"$index.idx") (Join-Path $buildDir "$index-$pass.txt") }
                        finally { Pop-Location }
                        $indexLog = Get-Content -LiteralPath (Join-Path $buildDir "$index.ilg") -Raw
                        if ($indexLog -notmatch '\b0 rejected\b' -or $indexLog -notmatch '\b0 warnings\b') { throw "Index rejected entries or warnings: $buildDir/$index.ilg" }
                        $processed[$index] = $digest; $processorRan = $true
                    }
                }
                $log = Get-Content -LiteralPath (Join-Path $buildDir "$book.log") -Raw
                $state = Get-AuxIdentity $buildDir
                $rerun = $log -match 'Rerun to get|Please \(re\)run|Please rerun|Label\(s\) may have changed|rerunfilecheck Warning'
                if ($pass -ge 3 -and !$processorRan -and !$rerun -and $state -ceq $previousState) { $stable = $true; break }
                $previousState = $state
            }
        } finally { Pop-Location }
        if (!$stable) { throw "$book did not stabilize within $MaxPasses XeLaTeX passes." }
        if ($log -match 'There were undefined references|There were undefined citations|There were multiply-defined labels|(?:Reference|Citation) .+ undefined|LaTeX Warning: Label .+ multiply defined|^! ' ) { throw "Unresolved reference/citation/label error: $buildDir/$book.log" }
        # Reject reads of live project files that escaped the isolated source set.
        # System TeX packages/fonts outside this project remain environment dependencies.
        foreach ($line in (Get-Content -LiteralPath (Join-Path $buildDir "$book.fls"))) {
            if (!$line.StartsWith('INPUT ')) { continue }
            $inputName = $line.Substring(6).Trim('"')
            if (![IO.Path]::IsPathRooted($inputName)) { $inputName = Join-Path $volumeDir $inputName }
            $inputPath = [IO.Path]::GetFullPath($inputName)
            if ($inputPath.StartsWith($root + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -and !$inputPath.StartsWith($runDir + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
                throw "Input escaped source snapshot; scope must include or remove this dependency: $inputPath"
            }
        }
        $pdf = Join-Path $buildDir "$book.pdf"
        if (!(Test-Path -LiteralPath $pdf) -or (Get-Item -LiteralPath $pdf).Length -eq 0) { throw "Missing generated PDF: $pdf" }
        $layoutWarnings = @([regex]::Matches($log, '(?m)^.*(?:Missing character:|Overfull \\[hv]box).*$') | ForEach-Object { $_.Value })
        $manifest.results += [pscustomobject]@{ volume=$number; passes=$pass; pdf="build/$book/$book.pdf"; pdfSha256=(Get-FileDigest $pdf); processed=@($processed.Keys); layoutWarningCount=$layoutWarnings.Count; layoutWarningSample=@($layoutWarnings | Select-Object -First 10) }
    }
    $manifest.status = 'success'
    $manifest.sourcesStillCurrent = ((Get-Identity @(Get-SourceFiles $root $selected)) -ceq (Get-Identity $manifest.sources))
} catch {
    $manifest.status = 'failed'
    $manifest.error = $_.Exception.Message
} finally {
    $manifest.commands = @($script:commands.ToArray())
    Write-Json $manifest $manifestPath
}
[pscustomobject]@{ status=$manifest.status; manifest=$manifestPath; results=$manifest.results; error=$manifest.error; sourcesStillCurrent=$manifest['sourcesStillCurrent'] } | ConvertTo-Json -Depth 8
if ($manifest.status -ne 'success') { exit 1 }
