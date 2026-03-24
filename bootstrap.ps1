# ============================================================
# Store Network Test Tool - Bootstrap Script (Windows)
#
# Steps:
#   1. Check internet connectivity
#   2. Verify git / uv are installed
#   3. Clone or pull the repository
#   4. Install dependencies
#   5. Show launch instructions
#
# Usage (PowerShell):
#   $f="$env:TEMP\bootstrap.ps1"; irm https://raw.githubusercontent.com/maruchiyo-yamaokaya/shop-nw-checker/main/bootstrap.ps1 -OutFile $f; powershell -ExecutionPolicy ByPass -File $f; Remove-Item $f
#
# Prerequisites: git, uv
# ============================================================

$ErrorActionPreference = "Stop"

$REPO_URL = "https://github.com/maruchiyo-yamaokaya/shop-nw-checker.git"
$TARGET_DIR = "shop-nw-checker"

function Write-Info  { param($msg) Write-Host "[INFO]  $msg" -ForegroundColor Cyan }
function Write-Ok    { param($msg) Write-Host "[OK]    $msg" -ForegroundColor Green }
function Write-Warn  { param($msg) Write-Host "[WARN]  $msg" -ForegroundColor Yellow }
function Write-Err   { param($msg) Write-Host "[ERROR] $msg" -ForegroundColor Red }

# ---------- 1. Internet check ----------
Write-Info "Checking internet connectivity..."
try {
    if (-not (Test-Connection -ComputerName 8.8.8.8 -Count 1 -Quiet -ErrorAction SilentlyContinue)) {
        throw "no connection"
    }
} catch {
    Write-Err "No internet connection. Please check your network."
    exit 1
}
Write-Ok "Internet OK"

# ---------- 2. git check ----------
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Err "git not found. Install it first:"
    Write-Host ""
    Write-Host "    winget install --id Git.Git -e --source winget" -ForegroundColor White
    Write-Host ""
    Write-Err "Then restart PowerShell and re-run this script."
    exit 1
}
Write-Ok "git OK"

# ---------- 3. uv check ----------
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Err "uv not found. Install it first:"
    Write-Host ""
    Write-Host '    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"' -ForegroundColor White
    Write-Host ""
    Write-Err "Then restart PowerShell and re-run this script."
    exit 1
}
Write-Ok "uv OK"

# ---------- 4. Clone / pull ----------
if (Test-Path "$TARGET_DIR\.git") {
    Write-Info "Updating repository..."
    git -C $TARGET_DIR pull --ff-only
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "git pull failed. Continuing with existing code."
    }
} else {
    Write-Info "Cloning repository..."
    git clone $REPO_URL $TARGET_DIR
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Failed to clone repository."
        exit 1
    }
}
Write-Ok "Repository ready"

# ---------- 5. Install dependencies ----------
Write-Info "Installing dependencies..."
Push-Location $TARGET_DIR
try {
    uv sync
    if ($LASTEXITCODE -ne 0) { throw "uv sync failed" }
} catch {
    Write-Err "Failed to install dependencies."
    Pop-Location
    exit 1
}
Pop-Location
Write-Ok "Dependencies installed"

# ---------- 6. Done ----------
Write-Host ""
Write-Ok "Setup complete!"
Write-Host ""
Write-Info "Run the tool with:"
Write-Host ""
Write-Host "    cd $TARGET_DIR; uv run store-net-test" -ForegroundColor White
Write-Host ""
