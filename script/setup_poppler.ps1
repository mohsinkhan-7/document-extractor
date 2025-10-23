Param(
    [string]$PopplerZipUrl = 'https://github.com/oschwartz10612/poppler-windows/releases/latest/download/Release-23.11.0-0.zip',
    [string]$InstallDir = 'C:\poppler',
    [switch]$Download,
    [switch]$Persist
)

Write-Host '--- Poppler Setup Helper ---' -ForegroundColor Cyan
Write-Host "Target install directory: $InstallDir"

if ($Download) {
    if (-not (Test-Path $InstallDir)) { New-Item -ItemType Directory -Path $InstallDir | Out-Null }
    $zipFile = Join-Path $env:TEMP 'poppler.zip'
    Write-Host 'Downloading Poppler ZIP...' -ForegroundColor Yellow
    Invoke-WebRequest -Uri $PopplerZipUrl -OutFile $zipFile
    Write-Host 'Extracting...' -ForegroundColor Yellow
    Expand-Archive -Path $zipFile -DestinationPath $InstallDir -Force
    Remove-Item $zipFile -Force
}

# Try to locate bin folder (some archives nest another folder)
$binCandidates = @(
    (Join-Path $InstallDir 'bin'),
    Get-ChildItem -Directory -Path $InstallDir | ForEach-Object { Join-Path $_.FullName 'bin' }
)

$validBin = $binCandidates | Where-Object { Test-Path (Join-Path $_ 'pdfinfo.exe') } | Select-Object -First 1

if (-not $validBin) {
    Write-Error 'Could not locate a bin folder containing pdfinfo.exe. Please check extraction.'
    exit 1
}

Write-Host "Detected Poppler bin: $validBin" -ForegroundColor Green
$env:POPPLER_PATH = $validBin
Write-Host "Set POPPLER_PATH for this session: $env:POPPLER_PATH" -ForegroundColor Green

if ($Persist) {
    [Environment]::SetEnvironmentVariable('POPPLER_PATH', $validBin, 'User')
    Write-Host 'Persisted POPPLER_PATH as user environment variable. Open a new shell to inherit.' -ForegroundColor Green
}

Write-Host 'Verifying pdfinfo...' -ForegroundColor Yellow
& (Join-Path $validBin 'pdfinfo.exe') --version
if ($LASTEXITCODE -ne 0) {
    Write-Error 'pdfinfo test failed.'
    exit 1
}

Write-Host 'Success. Restart your FastAPI server if it is already running.' -ForegroundColor Cyan