<#
.SYNOPSIS
Synchronize six local 0-* skills to this Git repository.
.DESCRIPTION
Run from a clean checkout of main with origin configured and a local commit.
The default source is the current user's .agents/skills directory. The command
copies changed files, removes tracked files deleted from the source, and
commits skill changes before pushing main. It does not force-push.
.PARAMETER SkillsRoot
Directory containing all six 0-* skill folders.
.PARAMETER Message
Git commit message for the synchronized changes.
.PARAMETER NoPush
Synchronize and commit locally. A subsequent run can push the commit.
.PARAMETER Preview
Show files that would change. Leaves the worktree, index and remote alone.
#>
[CmdletBinding()]
param(
    [string]$SkillsRoot = (Join-Path $env:USERPROFILE '.agents/skills'),
    [ValidateNotNullOrEmpty()][string]$Message = 'Sync 0 skills',
    [switch]$NoPush,
    [switch]$Preview
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$repo = (Get-Item -LiteralPath (Split-Path -Parent $PSScriptRoot)).FullName
$git = (Get-Command git -CommandType Application | Select-Object -First 1).Source
$skillNames = @('0-setup', '0-plan', '0-build', '0-review', '0-sync', '0-handoff')
$scope = @($skillNames | ForEach-Object { "skills/$_" })
$pathComparison = [StringComparison]::OrdinalIgnoreCase

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

function Get-TargetFile([string]$Relative) {
    $target = $repo
    $parts = $Relative.Split('/')
    for ($i = 0; $i -lt $parts.Count; $i++) {
        if ($parts[$i] -in @('', '.', '..') -or $parts[$i].Contains('\')) {
            throw "Unsafe relative path: $Relative"
        }
        $target = Join-Path $target $parts[$i]
        $item = Get-ExistingItem $target
        if ($null -eq $item) { continue }
        Assert-RegularItem $item
        if ($item.PSIsContainer -ne ($i -lt $parts.Count - 1)) {
            throw "A file or directory blocks the expected path: $target"
        }
    }
    return $target
}

$top = (Invoke-RepoGit @('rev-parse', '--show-toplevel')).Output[0]
if (-not [IO.Path]::GetFullPath($top).Equals($repo, $pathComparison)) { throw 'Run this script from its own Git checkout.' }
if ((Invoke-RepoGit @('branch', '--show-current')).Output[0] -ne 'main') { throw 'Switch this checkout to main before syncing.' }
$null = Invoke-RepoGit @('rev-parse', '--verify', 'HEAD')
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
        $metadata = $files | Where-Object { $_.FullName -eq (Join-Path $source.FullName 'agents/openai.yaml') }
        if (-not $entry -or -not $metadata) { throw "$name requires SKILL.md and agents/openai.yaml." }
        $frontmatter = [regex]::Match([IO.File]::ReadAllText($entry.FullName), '(?ms)\A---[ \t]*\r?\n(?<fields>.*?)^---[ \t]*\r?$')
        $escapedName = [regex]::Escape($name)
        $namePattern = '(?m)^name:[ \t]+{0}[ \t]*\r?$' -f $escapedName
        if (-not $frontmatter.Success -or $frontmatter.Groups['fields'].Value -cnotmatch $namePattern) {
            throw "SKILL.md must declare name: $name"
        }
        $policy = [regex]::Match([IO.File]::ReadAllText($metadata.FullName), '(?m)^policy:[ \t]*\r?\n(?<fields>(?:[ \t]+[^\r\n]*\r?\n?)*)')
        if (-not $policy.Success -or $policy.Groups['fields'].Value -cnotmatch '(?m)^[ \t]+allow_implicit_invocation:[ \t]+false[ \t]*(?:#[^\r\n]*)?\r?$') {
            throw "$name must retain policy.allow_implicit_invocation: false."
        }
        foreach ($file in $files) {
            $suffix = $file.FullName.Substring($source.FullName.Length + 1).Replace('\', '/')
            $relative = "skills/$name/$suffix"
            $sourcePaths[$relative] = $true
            $target = Get-TargetFile $relative
            if ([IO.File]::Exists($target)) {
                if (-not $tracked.ContainsKey($relative)) { throw "An ignored or untracked file blocks synchronization: $relative" }
                if ((Get-FileHash -LiteralPath $file.FullName).Hash -eq (Get-FileHash -LiteralPath $target).Hash) { continue }
            }
            [pscustomobject]@{ Action = 'Copy'; Relative = $relative; Source = $file.FullName; Target = $target }
        }
    }
    foreach ($relative in $tracked.Keys) {
        if (-not $sourcePaths.ContainsKey($relative)) {
            [pscustomobject]@{ Action = 'Remove'; Relative = $relative; Source = $null; Target = (Get-TargetFile $relative) }
        }
    }
)

if ($Preview) {
    if (-not $changes.Count) { Write-Output 'No skill files need synchronization.' }
    foreach ($change in $changes) { Write-Output "$($change.Action) $($change.Relative)" }
    return
}

if (-not $NoPush) {
    $remote = Invoke-RepoGit @('ls-remote', '--exit-code', '--heads', 'origin', 'refs/heads/main') @(0, 2)
    if ($remote.Code -eq 0) {
        $null = Invoke-RepoGit @('fetch', '--no-tags', 'origin', 'refs/heads/main')
        if ((Invoke-RepoGit @('merge-base', '--is-ancestor', 'FETCH_HEAD', 'HEAD') @(0, 1)).Code -ne 0) {
            throw 'origin/main has commits absent from this checkout. Integrate them before syncing.'
        }
    }
}
Assert-Clean

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
    if ((Invoke-RepoGit (@('diff', '--cached', '--quiet', '--') + $scope) @(0, 1)).Code -eq 1) {
        (Invoke-RepoGit (@('commit', '--only', '-m', $Message, '--') + $scope)).Output
    }
}
if (-not $NoPush) { (Invoke-RepoGit @('push', 'origin', 'refs/heads/main:refs/heads/main')).Output }
