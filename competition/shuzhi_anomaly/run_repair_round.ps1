param(
    [Parameter(Mandatory=$true)][string]$SourceRoot,
    [string]$ProjectDir = "competition/shuzhi_anomaly",
    [int]$Fold = 0
)

$TrainIndex = Join-Path $ProjectDir "generated/train_index.csv"
$CvManifest = Join-Path $ProjectDir "generated/internal_cv_duplicate_near_4fold.csv"
$RunRoot = Join-Path $ProjectDir "runs/repair_v2"

# 1) Strong checkpoint, frozen head-only transfer baseline.
python (Join-Path $ProjectDir "train_classifier.py") `
  --source-root $SourceRoot `
  --train-index $TrainIndex `
  --cv-manifest $CvManifest `
  --fold $Fold `
  --out-dir (Join-Path $RunRoot "fold${Fold}_head") `
  --model convnext_tiny_384 `
  --image-size 384 `
  --freeze-mode head `
  --epochs 20 `
  --batch-size 16 `
  --head-lr 3e-4 `
  --label-smoothing 0 `
  --sampler standard `
  --amp

# 2) Unfreeze last ConvNeXt stage from the best head-only checkpoint.
python (Join-Path $ProjectDir "train_classifier.py") `
  --source-root $SourceRoot `
  --train-index $TrainIndex `
  --cv-manifest $CvManifest `
  --fold $Fold `
  --out-dir (Join-Path $RunRoot "fold${Fold}_last_stage") `
  --model convnext_tiny_384 `
  --init-checkpoint (Join-Path $RunRoot "fold${Fold}_head/best.pt") `
  --image-size 384 `
  --freeze-mode last_stage `
  --epochs 15 `
  --batch-size 12 `
  --backbone-lr 2e-5 `
  --head-lr 2e-4 `
  --label-smoothing 0 `
  --sampler standard `
  --amp
