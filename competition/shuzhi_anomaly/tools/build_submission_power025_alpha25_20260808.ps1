$ErrorActionPreference = 'Stop'

$projectRoot = 'D:\研究生作业\人工智能实践比赛'
$project = Join-Path $projectRoot 'competition\shuzhi_anomaly'
$template = Join-Path $projectRoot 'shuzhi_anomaly_submission_448px_reviewed_v2_20260804_145245.tar.gz'
$candidate = Join-Path $project 'runs\luna_next_route_20260808\submission_power025_prior_alpha25.json'
$stage = Join-Path $project 'runs\luna_next_route_20260808\package_staging_alpha25'
$output = Join-Path $projectRoot 'shuzhi_anomaly_submission_448_v2_power025_prior_alpha25_20260808.tar.gz'
$manifest = Join-Path $project 'generated\test_manifest_v1.csv'
$report = Join-Path $project 'runs\luna_next_route_20260808\PACKAGE_REPORT.md'

foreach ($path in @($template, $candidate, $manifest)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "missing input: $path" }
}
if (Test-Path -LiteralPath $stage) { throw "staging directory already exists: $stage" }
New-Item -ItemType Directory -Force -Path $stage | Out-Null
tar -xzf $template -C $stage

$expected = @(Import-Csv -LiteralPath $manifest)
$items = @(Get-Content -LiteralPath $candidate -Raw | ConvertFrom-Json)
if ($items.Count -ne 695 -or $expected.Count -ne 695) { throw "expected 695 records" }
$allowed = @('乱采', '乱建', '乱堆', '乱占', '有漂浮物', '正常')
for ($i = 0; $i -lt 695; $i++) {
    $item = $items[$i]
    $props = @($item.PSObject.Properties.Name | Sort-Object)
    if (($props -join ',') -ne 'filename,height,label,width') { throw "invalid fields at index $i" }
    if ($item.filename -ne $expected[$i].filename) { throw "filename order mismatch at index $i" }
    if ($item.width -ne [string]$expected[$i].width -or $item.height -ne [string]$expected[$i].height) { throw "dimension mismatch for $($item.filename)" }
    if ($allowed -notcontains $item.label) { throw "invalid label for $($item.filename): $($item.label)" }
}

$resultPath = Join-Path $stage 'result\result.json'
Copy-Item -LiteralPath $candidate -Destination $resultPath -Force
if (Test-Path -LiteralPath $output) { Remove-Item -LiteralPath $output -Force }
tar -czf $output -C $stage code design result

$entries = @(tar -tzf $output)
if ($entries -notcontains 'result/result.json') { throw 'result/result.json missing from archive' }
if ($entries -contains 'result/result.json/') { throw 'result.json is a directory' }
$badTop = @($entries | Where-Object { $_ -notmatch '^(code|design|result)(/|$)' })
if ($badTop.Count -gt 0) { throw "unexpected top-level entries: $($badTop -join ', ')" }

@(
    '# Submission package report'
    ''
    '版本：448 v2 power025 + pile prior alpha=2.5'
    '时间：2026-08-08'
    "文件：$([IO.Path]::GetFileName($output))"
    '格式：.tar.gz'
    '内部目录：code/、design/、result/result.json'
    '结果条数：695'
    '未添加 SHA256 文件；未上传平台。'
) | Set-Content -LiteralPath $report -Encoding UTF8

Get-Item -LiteralPath $output | Select-Object FullName,Length,LastWriteTime | Format-List
Get-Content -LiteralPath $report
