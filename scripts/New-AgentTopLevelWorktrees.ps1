[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][string]$RepoRoot,
    [Parameter(Mandatory)][string]$WorktreeRoot,
    [string]$BaseBranch = 'integration/g0-g1-contract-freeze'
)

$repo = [System.IO.Path]::GetFullPath($RepoRoot)
$root = [System.IO.Path]::GetFullPath($WorktreeRoot)
if (-not (Test-Path (Join-Path $repo '.git'))) { throw "RepoRoot is not a Git worktree: $repo" }
New-Item -ItemType Directory -Force -Path $root | Out-Null

$agents = @(
    @{ Id = 'agent-a'; Branch = 'feature/agent-a-top-level-session' },
    @{ Id = 'agent-b'; Branch = 'feature/agent-b-top-level-session' },
    @{ Id = 'agent-c'; Branch = 'feature/agent-c-top-level-session' },
    @{ Id = 'agent-d'; Branch = 'feature/agent-d-top-level-session' },
    # Agent E keeps the existing governance branch; A-D use top-level-session branches.
    @{ Id = 'agent-e'; Branch = 'feature/agent-e-dynamic-session-policy' }
)

foreach ($agent in $agents) {
    $target = [System.IO.Path]::GetFullPath((Join-Path $root $agent.Id))
    if (-not $target.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Resolved target escaped WorktreeRoot: $target"
    }
    if (Test-Path $target) {
        Write-Output "EXISTS $($agent.Id): $target"
        continue
    }

    git -C $repo show-ref --verify --quiet "refs/heads/$($agent.Branch)"
    if ($LASTEXITCODE -eq 0) {
        if ($PSCmdlet.ShouldProcess($target, "Create worktree from $($agent.Branch)")) {
            git -C $repo worktree add $target $agent.Branch
        }
    } else {
        git -C $repo show-ref --verify --quiet "refs/remotes/origin/$($agent.Branch)"
        if ($LASTEXITCODE -eq 0) {
            if ($PSCmdlet.ShouldProcess($target, "Track origin/$($agent.Branch)")) {
                git -C $repo worktree add --track -b $agent.Branch $target "origin/$($agent.Branch)"
            }
        } else {
            if ($PSCmdlet.ShouldProcess($target, "Create $($agent.Branch) from $BaseBranch")) {
                git -C $repo worktree add -b $agent.Branch $target $BaseBranch
            }
        }
    }
    if ($LASTEXITCODE -ne 0) { throw "Failed to create worktree for $($agent.Id)" }
    Write-Output "CREATED $($agent.Id): $target [$($agent.Branch)]"
}

Write-Output "Run Get-AgentTopLevelSessionAudit.ps1 after opening the five sessions."
