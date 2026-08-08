param(
    [int[]]$Folds = @(0, 2),
    [string]$OutRootOverride = '',
    [ValidateSet('weighted_f1', 'macro_f1', 'mIoU', 'accuracy')]
    [string]$SelectionMetric = 'weighted_f1'
)

$ErrorActionPreference = 'Stop'
$project = 'D:\研究生作业\人工智能实践比赛\competition\shuzhi_anomaly'
$sourceRoot = 'D:\研究生作业\人工智能实践比赛\水域综合异常识别_训练集+验证集'
$outRoot = if ($OutRootOverride) { $OutRootOverride } else { Join-Path $project 'runs\camera_group_v2_power025_screen_20260808' }
$trainer = Join-Path $project 'train_classifier.py'
$trainJson = Join-Path $project 'generated\train_reviewed_v2.json'
$manifest = Join-Path $project 'generated\data_manifest.csv'
$trainIndex = Join-Path $project 'generated\train_index.csv'
$cvManifest = Join-Path $project 'generated\camera_groups_v2_reviewed\groupfold_review\camera_groupfold_manifest.csv'
$cacheDir = Join-Path $project 'weights\timm'

New-Item -ItemType Directory -Force -Path $outRoot | Out-Null

$common = @(
    '--source-root', $sourceRoot,
    '--train-json', $trainJson,
    '--manifest', $manifest,
    '--train-index', $trainIndex,
    '--cv-manifest', $cvManifest,
    '--label-version', 'reviewed_v2',
    '--model', 'convnext_tiny_384',
    '--cache-dir', $cacheDir,
    '--image-size', '448',
    '--batch-size', '8',
    '--workers', '0',
    '--seed', '42',
    '--backbone-lr', '5e-6',
    '--head-lr', '5e-5',
    '--weight-decay', '0.05',
    '--label-smoothing', '0',
    '--logit-adjustment', '0',
    '--loss', 'ce',
    '--sampler', 'power_balanced',
    '--sampling-alpha', '0.25',
    '--selection-metric', $SelectionMetric,
    '--amp'
)

$lastDirs = @()
foreach ($fold in $Folds) {
    $foldRoot = Join-Path $outRoot ("fold{0}" -f $fold)
    $headDir = Join-Path $foldRoot 'head'
    $lastDir = Join-Path $foldRoot 'last_stage'
    New-Item -ItemType Directory -Force -Path $foldRoot | Out-Null
    $lastDirs += $lastDir

    $headOof = Join-Path $headDir 'oof_predictions.csv'
    if (Test-Path -LiteralPath $headOof) {
        Write-Host ("SKIP fold{0} head-only (existing result)" -f $fold)
    } else {
        Write-Host ("START fold{0} head-only power025" -f $fold)
        & python -u $trainer @common '--fold' "$fold" '--freeze-mode' 'head' '--epochs' '5' '--early-stopping-patience' '2' '--out-dir' $headDir
        if ($LASTEXITCODE -ne 0) { throw "head-only failed for fold $fold with exit code $LASTEXITCODE" }
    }

    $headCheckpoint = Join-Path $headDir 'best.pt'
    if (-not (Test-Path -LiteralPath $headCheckpoint)) { throw "missing head checkpoint: $headCheckpoint" }

    $lastOof = Join-Path $lastDir 'oof_predictions.csv'
    if (Test-Path -LiteralPath $lastOof) {
        Write-Host ("SKIP fold{0} last-stage (existing result)" -f $fold)
    } else {
        Write-Host ("START fold{0} last-stage power025" -f $fold)
        & python -u $trainer @common '--fold' "$fold" '--freeze-mode' 'last_stage' '--epochs' '8' '--early-stopping-patience' '3' '--init-checkpoint' $headCheckpoint '--out-dir' $lastDir
        if ($LASTEXITCODE -ne 0) { throw "last-stage failed for fold $fold with exit code $LASTEXITCODE" }
    }
}

$oofDir = Join-Path $outRoot 'screen_oof'
$aggregateArgs = @()
$aggregateArgs += $lastDirs
$expectedCount = (Import-Csv $cvManifest | Where-Object {
    $_.split -eq 'train' -and $Folds -contains ([int]$_.fold)
}).Count
$aggregateArgs += @('--out-dir', $oofDir, '--expected-count', "$expectedCount")
& python -u (Join-Path $project 'aggregate_oof.py') @aggregateArgs
if ($LASTEXITCODE -ne 0) { throw 'partial OOF aggregation failed' }

Write-Host "COMPLETED v2 power025 screen: $outRoot"
