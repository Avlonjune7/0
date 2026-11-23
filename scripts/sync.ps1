<#
.SYNOPSIS
Synchronize local 0-* and me-* skills to this Git repository.
.DESCRIPTION
Run from a clean checkout of main with origin configured and a local commit.
The default source is D:\DATA\cc switch\skills. The command
copies changed files, removes tracked files deleted from the source, and
commits skill changes before pushing main. It does not force-push.
.PARAMETER SkillsRoot
Directory containing the five 0-* and two me-* skill folders.
.PARAMETER Skill
Optional subset of skill names to synchronize (defaults to all seven).
.PARAMETER Message
Git commit message for the synchronized changes.
.PARAMETER NoPush
Synchronize and commit locally. A subsequent run can push the commit.
.PARAMETER Preview
Show files that would change. Leaves the worktree, index and remote alone.
#>
[CmdletBinding()]
param(
    [string]$SkillsRoot = 'D:\DATA\cc switch\skills',
    [string[]]$Skill,
    [ValidateNotNullOrEmpty()][string]$Message = 'Sync 0 skills',
    [switch]$NoPush,
    [switch]$Preview
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$repo = (Get-Item -LiteralPath (Split-Path -Parent $PSScriptRoot)).FullName
$git = (Get-Command git -CommandType Application | Select-Object -First 1).Source
$allSkillNames = @('0-setup', '0-plan', '0-build', '0-review', '0-handoff', 'me-ui', 'me-tools')
if ($Skill -and $Skill.Count) {
    foreach ($s in $Skill) {
        if ($allSkillNames -cnotcontains $s) {
            throw "Unknown skill name: $s. Allowed: $($allSkillNames -join ', ')"
        }
    }
    $skillNames = @($Skill | Select-Object -Unique)
} else {
    $skillNames = $allSkillNames
}
$scope = @($skillNames | ForEach-Object { "skills/$_" })
$pathComparison = [StringComparison]::OrdinalIgnoreCase
$checkedDirs = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)

function Invoke-RepoGit {
    param([string[]]$GitArgs, [int[]]$Accepted = @(0))

    $options = @('--no-optional-locks', '-C', $repo)
    # check-ignore consumes pathnames directly and rejects the literal pathspec flag.
    if ($GitArgs[0] -ne 'check-ignore') { $options += '--literal-pathspecs' }
    $output = @(& $git @options @GitArgs)
    $code = $LASTEXITCODE
    if ($code -notin $Accepted) {
        throw "git $($GitArgs[0]) failed (exit $code)."
    }
    return [pscustomobject]@{ Code = $code; Output = $output }
}

function Assert-Clean {
    $status = (Invoke-RepoGit @('status', '--porcelain=v1', '--untracked-files=all')).Output
    if ($status.Count) { throw 'The checkout has local changes. Commit or move them before syncing.' }
    $previousEncoding = [Console]::OutputEncoding
    try {
        [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
        $indexFlags = (Invoke-RepoGit (@('ls-files', '-v', '-z', '--') + $scope)).Output -join "`n"
    } finally { [Console]::OutputEncoding = $previousEncoding }
    foreach ($entry in $indexFlags.Split([char[]]@([char]0), [StringSplitOptions]::RemoveEmptyEntries)) {
        if ($entry.Length -ge 2 -and $entry[0] -cne 'H') {
            throw "A tracked skill file has skip-worktree or assume-unchanged set: $($entry.Substring(2))"
        }
    }
}

function Get-ExistingItem([string]$Path) {
    try { Get-Item -LiteralPath $Path -Force }
    catch [System.Management.Automation.ItemNotFoundException] { return }
}

function Assert-RegularItem($Item) {
    if ($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "Symbolic links and junctions are outside the sync scope: $($Item.FullName)"
    }
}

function Test-FilesIdentical([IO.FileInfo]$SourceFile, [string]$TargetPath) {
    $targetInfo = [IO.FileInfo]::new($TargetPath)
    if ($SourceFile.Length -ne $targetInfo.Length) { return $false }
    $a = [IO.File]::ReadAllBytes($SourceFile.FullName)
    $b = [IO.File]::ReadAllBytes($TargetPath)
    for ($i = 0; $i -lt $a.Length; $i++) {
        if ($a[$i] -ne $b[$i]) { return $false }
    }
    return $true
}

function Get-SourceFiles([IO.DirectoryInfo]$Directory) {
    foreach ($item in Get-ChildItem -LiteralPath $Directory.FullName -Force) {
        Assert-RegularItem $item
        if ($item.Name -in @('.git', '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache', 'node_modules', '.DS_Store', 'Thumbs.db') -or $item.Extension -in @('.pyc', '.pyo')) {
            continue
        }
        if (($item.Name -match '^\.env(?:\.|$)' -and $item.Name -notmatch '^\.env\.(example|sample|template)$') -or
            $item.Name -match '^(id_(rsa|dsa|ecdsa|ed25519)|credentials\.json)$' -or
            $item.Extension -in @('.key', '.pem', '.p12', '.pfx', '.ppk')) {
            throw "Review and remove the private-looking file before publishing: $($item.FullName)"
        }
        if ($item.PSIsContainer) { Get-SourceFiles $item }
        else { $item }
    }
}

function Get-TargetFile([string]$Relative, [switch]$UseCache) {
    $target = $repo
    $parts = $Relative.Split('/')
    for ($i = 0; $i -lt $parts.Count; $i++) {
        if ($parts[$i] -in @('', '.', '..') -or $parts[$i].Contains('\')) {
            throw "Unsafe relative path: $Relative"
        }
        $target = Join-Path $target $parts[$i]
        $isDirLevel = ($i -lt $parts.Count - 1)
        if ($UseCache -and $isDirLevel -and $checkedDirs.Contains($target)) { continue }
        $item = Get-ExistingItem $target
        if ($null -eq $item) { continue }
        Assert-RegularItem $item
        if ($item.PSIsContainer -ne $isDirLevel) {
            throw "A file or directory blocks the expected path: $target"
        }
        if ($UseCache -and $isDirLevel) { $null = $checkedDirs.Add($target) }
    }
    return $target
}

$revInfo = (Invoke-RepoGit @('rev-parse', '--show-toplevel', '--abbrev-ref', 'HEAD', '--verify', 'HEAD')).Output
if (-not [IO.Path]::GetFullPath($revInfo[0]).Equals($repo, $pathComparison)) { throw 'Run this script from its own Git checkout.' }
if ($revInfo[1] -ne 'main') { throw 'Switch this checkout to main before syncing.' }
$localHead = $revInfo[2]
$null = Invoke-RepoGit @('remote', 'get-url', 'origin')
Assert-Clean

$sourceRoot = Get-Item -LiteralPath $SkillsRoot -Force
Assert-RegularItem $sourceRoot
if (-not $sourceRoot.PSIsContainer) { throw "SkillsRoot must be a directory: $SkillsRoot" }
$targetRoot = Join-Path $repo 'skills'
if ($sourceRoot.FullName.Equals($targetRoot, $pathComparison) -or
    $sourceRoot.FullName.StartsWith("$targetRoot$([IO.Path]::DirectorySeparatorChar)", $pathComparison) -or
    $targetRoot.StartsWith("$($sourceRoot.FullName.TrimEnd('\', '/'))$([IO.Path]::DirectorySeparatorChar)", $pathComparison)) {
    throw 'SkillsRoot and the repository skill directory must be separate.'
}

# Git emits UTF-8 paths. NUL delimiters preserve spaces and non-ASCII names.
$previousEncoding = [Console]::OutputEncoding
try {
    [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
    $trackedOutput = (Invoke-RepoGit (@('ls-files', '-z', '--') + $scope)).Output -join "`n"
} finally { [Console]::OutputEncoding = $previousEncoding }
$tracked = @{}
foreach ($path in $trackedOutput.Split([char[]]@([char]0), [StringSplitOptions]::RemoveEmptyEntries)) { $tracked[$path] = $true }

$sourcePaths = @{}
$changes = @(
    foreach ($name in $skillNames) {
        $source = Get-Item -LiteralPath (Join-Path $sourceRoot.FullName $name) -Force
        Assert-RegularItem $source
        if (-not $source.PSIsContainer) { throw "Expected a skill directory: $($source.FullName)" }
        $files = @(Get-SourceFiles $source)
        $entry = $files | Where-Object { $_.FullName -eq (Join-Path $source.FullName 'SKILL.md') }
        if (-not $entry) { throw "$name requires SKILL.md." }
        $frontmatter = [regex]::Match([IO.File]::ReadAllText($entry.FullName), '(?ms)\A---[ \t]*\r?\n(?<fields>.*?)^---[ \t]*\r?$')
        $escapedName = [regex]::Escape($name)
        $namePattern = '(?m)^name:[ \t]+{0}[ \t]*\r?$' -f $escapedName
        if (-not $frontmatter.Success -or $frontmatter.Groups['fields'].Value -cnotmatch $namePattern) {
            throw "SKILL.md must declare name: $name"
        }
        if ($name.StartsWith('0-', [StringComparison]::Ordinal)) {
            $metadata = $files | Where-Object { $_.FullName -eq (Join-Path $source.FullName 'agents/openai.yaml') }
            if (-not $metadata) { throw "$name requires agents/openai.yaml." }
            $policy = [regex]::Match([IO.File]::ReadAllText($metadata.FullName), '(?m)^policy:[ \t]*\r?\n(?<fields>(?:[ \t]+[^\r\n]*\r?\n?)*)')
            if (-not $policy.Success -or $policy.Groups['fields'].Value -cnotmatch '(?m)^[ \t]+allow_implicit_invocation:[ \t]+false[ \t]*(?:#[^\r\n]*)?\r?$') {
                throw "$name must retain policy.allow_implicit_invocation: false."
            }
        }
        foreach ($file in $files) {
            $suffix = $file.FullName.Substring($source.FullName.Length + 1).Replace('\', '/')
            $relative = "skills/$name/$suffix"
            $sourcePaths[$relative] = $true
            $target = Get-TargetFile $relative -UseCache
            if ([IO.File]::Exists($target)) {
                if (-not $tracked.ContainsKey($relative)) { throw "An ignored or untracked file blocks synchronization: $relative" }
                if (Test-FilesIdentical $file $target) { continue }
            }
            [pscustomobject]@{ Action = 'Copy'; Relative = $relative; Source = $file.FullName; Target = $target }
        }
    }
    foreach ($relative in $tracked.Keys) {
        if (-not $sourcePaths.ContainsKey($relative)) {
            [pscustomobject]@{ Action = 'Remove'; Relative = $relative; Source = $null; Target = (Get-TargetFile $relative -UseCache) }
        }
    }
)

if ($Preview) {
    if (-not $changes.Count) { Write-Output 'No skill files need synchronization.' }
    foreach ($change in $changes) { Write-Output "$($change.Action) $($change.Relative)" }
    return
}

$remoteHead = $null
if (-not $NoPush) {
    $prevEap = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $fetchOut = @(& $git --no-optional-locks -C $repo fetch --no-tags --quiet origin refs/heads/main 2>&1)
        $fetchCode = $LASTEXITCODE
    } finally { $ErrorActionPreference = $prevEap }
    if ($fetchCode -eq 0) {
        $remoteHead = (Invoke-RepoGit @('rev-parse', '--verify', 'FETCH_HEAD')).Output[0]
        if ($remoteHead -ne $localHead -and (Invoke-RepoGit @('merge-base', '--is-ancestor', $remoteHead, $localHead) @(0, 1)).Code -ne 0) {
            throw 'origin/main has commits absent from this checkout. Integrate them before syncing.'
        }
    } elseif ($fetchCode -eq 128 -and (($fetchOut -join "`n") -match "couldn't find remote ref")) {
        $remoteHead = $null
    } else {
        throw "git fetch failed (exit $fetchCode): $($fetchOut -join ' ')"
    }
}

$added = @($changes | Where-Object { $_.Action -eq 'Copy' -and -not $tracked.ContainsKey($_.Relative) })
if ($added.Count) {
    $ignored = Invoke-RepoGit (@('check-ignore', '--') + $added.Relative) @(0, 1)
    if ($ignored.Code -eq 0) { throw ('A source file would be ignored by Git: ' + ($ignored.Output -join ', ')) }
}

foreach ($change in $changes) {
    # Recheck each path immediately before the filesystem operation.
    $target = Get-TargetFile $change.Relative
    if ($change.Action -eq 'Remove') { Remove-Item -LiteralPath $target }
    else {
        $null = [IO.Directory]::CreateDirectory((Split-Path -Parent $target))
        Copy-Item -LiteralPath $change.Source -Destination $target
    }
}

if ($changes.Count) {
    $null = Invoke-RepoGit (@('add', '-A', '--') + $scope)
    if ($added.Count) {
        $previousEncoding = [Console]::OutputEncoding
        try {
            [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
            $indexedOutput = (Invoke-RepoGit (@('ls-files', '-z', '--') + $scope)).Output -join "`n"
        } finally { [Console]::OutputEncoding = $previousEncoding }
        $indexed = @{}
        foreach ($path in $indexedOutput.Split([char[]]@([char]0), [StringSplitOptions]::RemoveEmptyEntries)) { $indexed[$path] = $true }
        $missing = @($added | Where-Object { -not $indexed.ContainsKey($_.Relative) } | ForEach-Object { $_.Relative })
        if ($missing.Count) {
            throw ('A planned skill file was not staged (check nested .gitignore rules): ' + ($missing -join ', '))
        }
    }
    if ((Invoke-RepoGit (@('diff', '--cached', '--quiet', '--') + $scope) @(0, 1)).Code -eq 1) {
        (Invoke-RepoGit (@('commit', '--only', '-m', $Message, '--') + $scope)).Output
        $localHead = (Invoke-RepoGit @('rev-parse', '--verify', 'HEAD')).Output[0]
    }
}
if (-not $NoPush -and ($remoteHead -ne $localHead)) {
    (Invoke-RepoGit @('push', 'origin', 'refs/heads/main:refs/heads/main')).Output
}
