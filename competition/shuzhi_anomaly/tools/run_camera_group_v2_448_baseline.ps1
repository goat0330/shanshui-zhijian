param(
    [int[]]$Folds = @(0, 1, 2, 3),
    [string]$CvManifestOverride = '',
    [string]$OutRootOverride = ''
)

$ErrorActionPreference = 'Stop'
$project = 'D:\研究生作业\人工智能实践比赛\competition\shuzhi_anomaly'
$sourceRoot = 'D:\研究生作业\人工智能实践比赛\水域综合异常识别_训练集+验证集'
$outRoot = if ($OutRootOverride) { $OutRootOverride } else { Join-Path $project 'runs\camera_group_v2_448_baseline_20260807' }
$trainer = Join-Path $project 'train_classifier.py'
$trainJson = Join-Path $project 'generated\train_reviewed_v2.json'
$manifest = Join-Path $project 'generated\data_manifest.csv'
$trainIndex = Join-Path $project 'generated\train_index.csv'
$cvManifest = if ($CvManifestOverride) { $CvManifestOverride } else { Join-Path $project 'generated\camera_groups_v2_reviewed\groupfold_review\camera_groupfold_manifest.csv' }
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
    '--sampler', 'standard',
    '--selection-metric', 'weighted_f1',
    '--amp'
)

foreach ($fold in $Folds) {
    $foldRoot = Join-Path $outRoot ("fold{0}" -f $fold)
    $headDir = Join-Path $foldRoot 'head'
    $lastDir = Join-Path $foldRoot 'last_stage'
    New-Item -ItemType Directory -Force -Path $foldRoot | Out-Null

    $headOof = Join-Path $headDir 'oof_predictions.csv'
    if (Test-Path -LiteralPath $headOof) {
        Write-Host ("SKIP fold{0} head-only (existing result)" -f $fold)
    } else {
        Write-Host ("START fold{0} head-only" -f $fold)
        & python -u $trainer @common '--fold' "$fold" '--freeze-mode' 'head' '--epochs' '5' '--early-stopping-patience' '2' '--out-dir' $headDir
        if ($LASTEXITCODE -ne 0) { throw "head-only failed for fold $fold with exit code $LASTEXITCODE" }
    }

    $headCheckpoint = Join-Path $headDir 'best.pt'
    if (-not (Test-Path -LiteralPath $headCheckpoint)) { throw "missing head checkpoint: $headCheckpoint" }

    $lastOof = Join-Path $lastDir 'oof_predictions.csv'
    if (Test-Path -LiteralPath $lastOof) {
        Write-Host ("SKIP fold{0} last-stage (existing result)" -f $fold)
    } else {
        Write-Host ("START fold{0} last-stage" -f $fold)
        & python -u $trainer @common '--fold' "$fold" '--freeze-mode' 'last_stage' '--epochs' '8' '--early-stopping-patience' '3' '--init-checkpoint' $headCheckpoint '--out-dir' $lastDir
        if ($LASTEXITCODE -ne 0) { throw "last-stage failed for fold $fold with exit code $LASTEXITCODE" }
    }
}

$oofDir = Join-Path $outRoot 'global_oof'
& python -u (Join-Path $project 'aggregate_oof.py') `
    (Join-Path $outRoot 'fold0\last_stage') `
    (Join-Path $outRoot 'fold1\last_stage') `
    (Join-Path $outRoot 'fold2\last_stage') `
    (Join-Path $outRoot 'fold3\last_stage') `
    '--out-dir' $oofDir '--expected-count' '1139'
if ($LASTEXITCODE -ne 0) { throw "OOF aggregation failed with exit code $LASTEXITCODE" }

Write-Host "COMPLETED 448 fresh-pretrained control: $outRoot"
