# Run from PowerShell: .\start_windows.ps1
# One CPU worker; no reload so the checkpoint is loaded once.
[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = $(if ($env:PORT) { [int]$env:PORT } else { 8000 }),
    [string]$BindAddress = $(if ($env:HOST) { $env:HOST } else { '127.0.0.1' })
)

$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        throw 'Python environment missing. Follow docs/WINDOWS.md to install Python 3.11 and create .venv.'
    }

    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 2
    } catch {
        $health = $null
    }
    if ($health -and $health.status -eq 'ok' -and $health.PSObject.Properties['model_ready']) {
        Write-Host "Lumi is already running: http://localhost:$Port (model_ready=$($health.model_ready))"
        return
    }

    $dbPath = if ($env:DATABASE_PATH) { $env:DATABASE_PATH } else { Join-Path $PSScriptRoot 'data\shopee_muse.db' }
    if (-not (Test-Path -LiteralPath $dbPath -PathType Leaf) -or (Get-Item -LiteralPath $dbPath).Length -eq 0) {
        throw 'Database missing or empty. Copy the existing SQLite database as described in docs/WINDOWS.md.'
    }
    $datasetPath = if ($env:MUSE_DATASET_DIR) { $env:MUSE_DATASET_DIR } else { Join-Path $PSScriptRoot 'data' }
    $checkpointPath = if ($env:MUSE_CHECKPOINT_DIR) { $env:MUSE_CHECKPOINT_DIR } else { Join-Path $PSScriptRoot 'checkpoints' }
    $requiredFiles = @(
        (Join-Path $checkpointPath 'muse_full_training_dense.ckpt'),
        (Join-Path $checkpointPath 'muse_full_training_sparse.ckpt')
    )
    foreach ($field in @('129_1', '130_1', '130_2', '130_3', '130_4', '130_5', '151_2_180', '213', '214')) {
        $requiredFiles += Join-Path $datasetPath "feature_map\${field}_sorted_map.npy"
    }
    $requiredFiles += Join-Path $datasetPath 'feature_map\150_2_180_sorted_map_p90.npy'
    $requiredFiles += Join-Path $datasetPath 'feature_map\scl_emb_int8_p90_keys.npy'
    $requiredFiles += Join-Path $datasetPath 'feature_map\scl_emb_int8_p90_values.npy'
    $missingFiles = @($requiredFiles | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) })
    if ($missingFiles.Count -gt 0) {
        throw ("Model files missing. Follow docs/WINDOWS.md and copy the trained files:`n" + ($missingFiles -join "`n"))
    }

    if (-not $env:OMP_NUM_THREADS) { $env:OMP_NUM_THREADS = '2' }
    if (-not $env:MKL_NUM_THREADS) { $env:MKL_NUM_THREADS = '2' }
    Write-Host "Starting Lumi: http://localhost:$Port"
    Write-Host 'One CPU worker. Stop with Ctrl+C. Startup may take longer on the first run.'
    & $python -m uvicorn app.main:app --host $BindAddress --port $Port --workers 1
    if ($LASTEXITCODE -ne 0) { throw "Server exited with code $LASTEXITCODE." }
} finally {
    Pop-Location
}
