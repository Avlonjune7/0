[CmdletBinding()]
param([string]$FixtureRoot = [IO.Path]::GetTempPath())

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$fixtureRootPath = (Get-Item -LiteralPath $FixtureRoot).FullName
$fixture = [IO.Directory]::CreateDirectory((Join-Path $fixtureRootPath ('zero-sync-test-' + [guid]::NewGuid()))).FullName
$source = [IO.Directory]::CreateDirectory((Join-Path $fixture 'installed skills')).FullName
$checkout = [IO.Directory]::CreateDirectory((Join-Path $fixture 'checkout')).FullName
$remote = [IO.Directory]::CreateDirectory((Join-Path $fixture 'remote.git')).FullName
$scriptDirectory = [IO.Directory]::CreateDirectory((Join-Path $checkout 'scripts')).FullName
$script = Join-Path $scriptDirectory 'sync.ps1'
$gitExecutable = (Get-Command git -CommandType Application | Select-Object -First 1).Source
Copy-Item -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'scripts/sync.ps1') -Destination $script

function Git([string]$Directory, [string[]]$GitArgs) {
    $output = @(& $gitExecutable -C $Directory @GitArgs)
    if ($LASTEXITCODE -ne 0) { throw "Fixture Git command failed: $($GitArgs -join ' ')" }
    $output
}

function Assert([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

function Assert-Rejected([scriptblock]$Action, [string]$ErrorText) {
    try { & $Action | Out-Null }
    catch {
        if ($_.Exception.Message -notmatch [regex]::Escape($ErrorText)) { throw }
        return
    }
    throw "Expected sync to reject the operation: $ErrorText"
}

try {
    $null = Git $remote @('init', '--bare', '-b', 'main')
    $null = Git $checkout @('init', '-b', 'main')
    $null = Git $checkout @('config', 'user.name', 'Sync Test')
    $null = Git $checkout @('config', 'user.email', 'sync-test@example.invalid')
    $null = Git $checkout @('config', 'core.autocrlf', 'false')
    $null = Git $checkout @('remote', 'add', 'origin', $remote)
    [IO.File]::WriteAllText((Join-Path $checkout 'README.md'), '# Fixture')
    $null = Git $checkout @('add', '--', 'README.md', 'scripts/sync.ps1')
    $null = Git $checkout @('commit', '-m', 'Bootstrap fixture')
    $initial = Git $checkout @('rev-parse', 'HEAD')

    foreach ($name in @('0-setup', '0-plan', '0-build', '0-review', '0-sync', '0-handoff', '0-retro')) {
        $folder = [IO.Directory]::CreateDirectory((Join-Path $source $name)).FullName
        $null = [IO.Directory]::CreateDirectory((Join-Path $folder 'agents'))
        [IO.File]::WriteAllText((Join-Path $folder 'SKILL.md'), "---`nname: $name`ndescription: Fixture.`n---`n")
        [IO.File]::WriteAllText((Join-Path $folder 'agents/openai.yaml'), "policy:`n  allow_implicit_invocation: false`n")
    }
    foreach ($name in @('me-ui', 'me-tools')) {
        $folder = [IO.Directory]::CreateDirectory((Join-Path $source $name)).FullName
        [IO.File]::WriteAllText((Join-Path $folder 'SKILL.md'), "---`nname: $name`ndescription: Fixture.`n---`n")
    }
    $null = [IO.Directory]::CreateDirectory((Join-Path $source 'me-ui/references'))
    $personalReference = Join-Path $source 'me-ui/references/components.md'
    $targetReference = Join-Path $checkout 'skills/me-ui/references/components.md'
    [IO.File]::WriteAllText($personalReference, 'Personal UI reference')
    # Construct the non-ASCII filename by code point for Windows PowerShell 5.1.
    $extra = ([string][char]0x6307) + ([string][char]0x5357) + ' with spaces.md'
    $sourceExtra = Join-Path $source "0-setup/$extra"
    $targetExtra = Join-Path $checkout "skills/0-setup/$extra"
    [IO.File]::WriteAllText($sourceExtra, 'Document to remove later')
    $cache = [IO.Directory]::CreateDirectory((Join-Path $source '0-setup/__pycache__')).FullName
    [IO.File]::WriteAllText((Join-Path $cache 'helper.pyc'), 'Generated file')

    $index = Join-Path $checkout '.git/index'
    $initialIndex = (Get-FileHash -LiteralPath $index).Hash
    $preview = @(& $script -SkillsRoot $source -Preview)
    Assert ($preview.Count -eq 18) 'Preview must report publishable files from both skill groups.'
    Assert ((Get-FileHash -LiteralPath $index).Hash -eq $initialIndex) 'Preview must preserve index bytes.'
    Assert (-not (Test-Path -LiteralPath (Join-Path $checkout 'skills'))) 'Preview must preserve the worktree.'
    Assert (-not (Test-Path -LiteralPath (Join-Path $checkout '.git/FETCH_HEAD'))) 'Preview must not fetch.'
    Assert ((Git $checkout @('rev-parse', 'HEAD')) -eq $initial) 'Preview must preserve HEAD.'

    & $script -SkillsRoot $source -Message 'First skill synchronization' | Out-Null
    $first = Git $checkout @('rev-parse', 'HEAD')
    Assert ($first -ne $initial) 'First sync must commit the imported skills.'
    Assert ((Git $remote @('rev-parse', 'refs/heads/main')) -eq $first) 'First sync must push to the empty remote.'
    Assert (Test-Path -LiteralPath $targetExtra) 'Unicode filename must be copied.'
    Assert (-not (Test-Path -LiteralPath (Join-Path $checkout 'skills/0-setup/__pycache__'))) 'Cache files must not be published.'
    Assert (Test-Path -LiteralPath (Join-Path $checkout 'skills/me-ui/SKILL.md')) 'Personal UI skill must be published without agent metadata.'
    Assert (Test-Path -LiteralPath (Join-Path $checkout 'skills/me-tools/SKILL.md')) 'Personal tools skill must be published without agent metadata.'
    Assert (Test-Path -LiteralPath $targetReference) 'Personal skill references must be published.'

    $sourceEntry = Join-Path $source '0-build/SKILL.md'
    [IO.File]::AppendAllText($sourceEntry, "`n# A real change`n")
    Remove-Item -LiteralPath $sourceExtra
    Remove-Item -LiteralPath $personalReference
    $personalEntry = Join-Path $source 'me-tools/SKILL.md'
    [IO.File]::AppendAllText($personalEntry, "`n# Updated tool preference`n")
    $null = [IO.Directory]::CreateDirectory((Join-Path $source 'me-tools/agents'))
    $personalPolicy = "policy:`n  allow_implicit_invocation: true`n"
    [IO.File]::WriteAllText((Join-Path $source 'me-tools/agents/openai.yaml'), $personalPolicy)
    $null = Git $checkout @('remote', 'set-url', 'origin', (Join-Path $fixture 'missing.git'))
    & $script -SkillsRoot $source -NoPush -Message 'Change and delete skill files' | Out-Null
    $second = Git $checkout @('rev-parse', 'HEAD')
    Assert ($second -ne $first) 'Offline sync must commit without a reachable origin.'
    Assert (-not (Test-Path -LiteralPath $targetExtra)) 'A deleted source file must be removed from the checkout.'
    Assert (-not (Test-Path -LiteralPath $targetReference)) 'A deleted personal skill reference must be removed from the checkout.'
    Assert ([IO.File]::ReadAllText((Join-Path $checkout 'skills/me-tools/SKILL.md')) -eq [IO.File]::ReadAllText($personalEntry)) 'Personal skill updates must be copied.'
    Assert ([IO.File]::ReadAllText((Join-Path $checkout 'skills/me-tools/agents/openai.yaml')) -eq $personalPolicy) 'Optional personal agent metadata must retain implicit invocation.'
    Assert ((Git $remote @('rev-parse', 'refs/heads/main')) -eq $first) 'NoPush must leave the remote branch unchanged.'
    $null = Git $checkout @('remote', 'set-url', 'origin', $remote)
    & $script -SkillsRoot $source | Out-Null
    Assert ((Git $remote @('rev-parse', 'refs/heads/main')) -eq $second) 'A subsequent run must push the pending commit.'
    & $script -SkillsRoot $source | Out-Null
    Assert ((Git $checkout @('rev-parse', 'HEAD')) -eq $second) 'A repeated sync must not create an empty commit.'

    $workflowPolicy = Join-Path $source '0-build/agents/openai.yaml'
    $savedWorkflowPolicy = [IO.File]::ReadAllText($workflowPolicy)
    Remove-Item -LiteralPath $workflowPolicy
    Assert-Rejected { & $script -SkillsRoot $source -NoPush } '0-build requires agents/openai.yaml'
    [IO.File]::WriteAllText($workflowPolicy, $personalPolicy)
    Assert-Rejected { & $script -SkillsRoot $source -NoPush } '0-build must retain policy.allow_implicit_invocation: false'
    [IO.File]::WriteAllText($workflowPolicy, $savedWorkflowPolicy)

    $untracked = Join-Path $checkout 'other-session.txt'
    [IO.File]::WriteAllText($untracked, 'Untracked work')
    Assert-Rejected { & $script -SkillsRoot $source -NoPush } 'checkout has local changes'
    Assert ([IO.File]::ReadAllText($untracked) -eq 'Untracked work') 'Untracked work must be preserved.'
    Remove-Item -LiteralPath $untracked

    $private = Join-Path $source '0-plan/.env.local'
    [IO.File]::WriteAllText($private, 'Fixture only')
    Assert-Rejected { & $script -SkillsRoot $source -NoPush } 'private-looking file'
    Remove-Item -LiteralPath $private

    $other = Join-Path $fixture 'other checkout'
    $null = Git $fixture @('clone', '--branch', 'main', $remote, $other)
    $null = Git $other @('config', 'user.name', 'Sync Test')
    $null = Git $other @('config', 'user.email', 'sync-test@example.invalid')
    [IO.File]::WriteAllText((Join-Path $other 'remote-change.md'), 'Remote work')
    $null = Git $other @('add', '--', 'remote-change.md')
    $null = Git $other @('commit', '-m', 'Advance remote')
    $null = Git $other @('push', 'origin', 'main')
    [IO.File]::AppendAllText($sourceEntry, "`n# Another change`n")
    Assert-Rejected { & $script -SkillsRoot $source } 'origin/main has commits absent'
    Assert ((Git $checkout @('rev-parse', 'HEAD')) -eq $second) 'Remote-ahead rejection must preserve HEAD.'
    Assert ((@(Git $checkout @('status', '--porcelain'))).Count -eq 0) 'Remote-ahead rejection must preserve a clean worktree.'

    Write-Output 'Sync integration checks passed.'
} catch {
    Write-Output "Fixture retained for inspection at $fixture"
    throw
}

$expectedPrefix = $fixtureRootPath.TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar + 'zero-sync-test-'
if (-not ([IO.Path]::GetFullPath($fixture)).StartsWith($expectedPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Refusing to remove a test fixture outside FixtureRoot.'
}
Remove-Item -LiteralPath $fixture -Recurse -Force
