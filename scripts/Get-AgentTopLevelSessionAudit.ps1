[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$RepoRoot,
    [Parameter(Mandatory)][string]$WorktreeRoot
)

$repo = [System.IO.Path]::GetFullPath($RepoRoot)
$root = [System.IO.Path]::GetFullPath($WorktreeRoot)
if (-not (Test-Path (Join-Path $repo '.git'))) { throw "RepoRoot is not a Git worktree: $repo" }

$expected = @(
    @{ Id = 'agent-a'; Pattern = 'feature/agent-a-*' },
    @{ Id = 'agent-b'; Pattern = 'feature/agent-b-*' },
    @{ Id = 'agent-c'; Pattern = 'feature/agent-c-*' },
    @{ Id = 'agent-d'; Pattern = 'feature/agent-d-*' },
    @{ Id = 'agent-e'; Pattern = 'feature/agent-e-*' }
)

$raw = git -C $repo worktree list --porcelain
if ($LASTEXITCODE -ne 0) { throw 'Unable to read Git worktrees' }
$rows = @()
$current = @{}
foreach ($line in $raw) {
    if ($line -like 'worktree *') {
        if ($current.Count -gt 0) { $rows += [pscustomobject]$current }
        $current = @{ Path = $line.Substring(9) }
    } elseif ($line -like 'HEAD *') { $current.HEAD = $line.Substring(5) }
    elseif ($line -like 'branch *') { $current.Branch = $line.Substring(7) -replace '^refs/heads/','' }
}
if ($current.Count -gt 0) { $rows += [pscustomobject]$current }

$failed = $false
foreach ($item in $expected) {
    $path = [System.IO.Path]::GetFullPath((Join-Path $root $item.Id))
    $row = $rows | Where-Object { [System.IO.Path]::GetFullPath($_.Path) -eq $path } | Select-Object -First 1
    if (-not $row) {
        $failed = $true
        [pscustomobject]@{ Agent = $item.Id; Worktree = $path; Branch = '<missing>'; Status = 'MISSING' }
        continue
    }
    $branchOk = $row.Branch -like $item.Pattern
    $dirty = (git -C $path status --porcelain)
    $status = if (-not $branchOk) { 'BRANCH_MISMATCH' } elseif ($dirty) { 'DIRTY' } else { 'OK' }
    if ($status -ne 'OK') { $failed = $true }
    [pscustomobject]@{ Agent = $item.Id; Worktree = $path; Branch = $row.Branch; Status = $status }
}

if ($failed) { exit 1 }
Write-Output 'TOP_LEVEL_SESSION_WORKTREE_AUDIT_PASSED'
