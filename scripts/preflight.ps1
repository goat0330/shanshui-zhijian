param(
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"
$pass = 0
$fail = 0
$warn = 0

function Check-Item {
    param([string]$Label, [scriptblock]$Block)
    try {
        $result = &$Block
        if (-not $Quiet) { Write-Host "  [PASS] $Label" -ForegroundColor Green }
        $script:pass++
        return $result
    } catch {
        if (-not $Quiet) { Write-Host "  [FAIL] $Label : $_" -ForegroundColor Red }
        $script:fail++
        return $null
    }
}

function Check-Warn {
    param([string]$Label, [scriptblock]$Block)
    try {
        $result = &$Block
        if ($result) {
            if (-not $Quiet) { Write-Host "  [WARN] $Label : $result" -ForegroundColor Yellow }
            $script:warn++
        } else {
            if (-not $Quiet) { Write-Host "  [PASS] $Label" -ForegroundColor Green }
            $script:pass++
        }
        return $result
    } catch {
        if (-not $Quiet) { Write-Host "  [WARN] $Label : $_" -ForegroundColor Yellow }
        $script:warn++
        return $null
    }
}

function Is-PostgresPath {
    param([string]$Path)
    return $Path -match '[Pp]ostgres[^\\]*\\' -or $Path -match '[Pp]ostgis'
}

Write-Host "=== Geospatial Environment Preflight ===" -ForegroundColor Cyan

# 1. Python version >= 3.11
Check-Item "Python version >= 3.11" {
    $ver = [Version](python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    if ($ver -lt [Version]"3.11") { throw "Python $ver < 3.11" }
    "Python $ver"
}

# 2. Dangerous environment variables
Check-Warn "Environment: PROJ_LIB" {
    $val = [Environment]::GetEnvironmentVariable("PROJ_LIB")
    if (-not $val) { return $null }
    if (Is-PostgresPath $val) { return "PostgreSQL path detected: $val" }
    return $null
}

Check-Warn "Environment: GDAL_DATA" {
    $val = [Environment]::GetEnvironmentVariable("GDAL_DATA")
    if (-not $val) { return $null }
    if (Is-PostgresPath $val) { return "PostgreSQL path detected: $val" }
    return $null
}

Check-Warn "Environment: PROJ_DATA" {
    $val = [Environment]::GetEnvironmentVariable("PROJ_DATA")
    if (-not $val) { return $null }
    if (Is-PostgresPath $val) { return "PostgreSQL path detected: $val" }
    return $null
}

# 3. pyproj data directory
Check-Item "pyproj CRS 4545" {
    $out = python -c "
import pyproj
crs = pyproj.CRS.from_epsg(4545)
print(f'pyproj CRS 4545 OK: {crs.to_wkt()[:60]}...')
print(f'pyproj datadir: {pyproj.datadir.get_data_dir()}')
"
    $out -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" }
}

# 4. pyproj data dir not from PostgreSQL
Check-Warn "pyproj datadir NOT PostgreSQL" {
    $dir = python -c "import pyproj; print(pyproj.datadir.get_data_dir())"
    if (Is-PostgresPath $dir) { return "pyproj datadir is from PostgreSQL: $dir" }
    return $null
}

# 5. rasterio CRS parsing (cleans environment first)
Check-Item "rasterio CRS 4545" {
    $out = python -c "
import os
os.environ.pop('PROJ_LIB', None)
os.environ.pop('GDAL_DATA', None)
os.environ.pop('PROJ_DATA', None)
import rasterio
crs = rasterio.crs.CRS.from_epsg(4545)
print(f'rasterio CRS 4545 OK: {crs}')
print(f'rasterio version: {rasterio.__version__}')
"
    $out -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" }
}

# 6. GDAL version
Check-Item "GDAL version" {
    $out = python -c "
import os
os.environ.pop('PROJ_LIB', None)
os.environ.pop('GDAL_DATA', None)
os.environ.pop('PROJ_DATA', None)
from osgeo import gdal
print(f'GDAL {gdal.VersionInfo()}')
"
    $out.Trim()
}

# 7. pytest collection pre-check (environment-isolated)
Check-Item "pytest collection" {
    $oldProjLib = $env:PROJ_LIB
    $oldGdalData = $env:GDAL_DATA
    $oldProjData = $env:PROJ_DATA
    Remove-Item Env:\PROJ_LIB -ErrorAction SilentlyContinue
    Remove-Item Env:\GDAL_DATA -ErrorAction SilentlyContinue
    Remove-Item Env:\PROJ_DATA -ErrorAction SilentlyContinue
    try {
        $out = python -m pytest --collect-only -q 2>&1
        $exitCode = $LASTEXITCODE
        # Exit code 5 = no tests collected, acceptable for preflight
        if ($exitCode -ne 0 -and $exitCode -ne 5) { throw "pytest collection failed (exit $exitCode)`n$out" }
        "pytest collection OK"
    } finally {
        if ($oldProjLib) { $env:PROJ_LIB = $oldProjLib }
        if ($oldGdalData) { $env:GDAL_DATA = $oldGdalData }
        if ($oldProjData) { $env:PROJ_DATA = $oldProjData }
    }
}

# 8. CUDA availability (optional)
Check-Item "CUDA availability" {
    $out = python -c "
import os
os.environ.pop('PROJ_LIB', None)
os.environ.pop('GDAL_DATA', None)
os.environ.pop('PROJ_DATA', None)
try:
    import torch
    print(f'CUDA available: {torch.cuda.is_available()}')
except ImportError:
    print('torch not installed — skipping')
"
    $out.Trim()
}

# Summary
Write-Host ""
Write-Host "=== Summary ===" -ForegroundColor Cyan
Write-Host "  Pass: $pass" -ForegroundColor Green
Write-Host "  Warn: $warn" -ForegroundColor Yellow
Write-Host "  Fail: $fail" -ForegroundColor Red

if ($fail -gt 0) {
    exit 1
}
