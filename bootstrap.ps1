# ============================================================
# 店舗ネットワークテスト自動化ツール — ブートストラップスクリプト
# Windows PowerShell 用
#
# ワンコマンドで以下を実行する:
#   1. インターネット接続確認
#   2. git / uv の存在確認
#   3. リポジトリの clone または pull
#   4. 仮想環境構築 + 依存インストール
#   5. ツール起動案内
#
# 使い方（PowerShellで実行）:
#   $f="$env:TEMP\bootstrap.ps1"; irm https://raw.githubusercontent.com/maruchiyo-yamaokaya/shop-nw-checker/main/bootstrap.ps1 -OutFile $f; powershell -ExecutionPolicy ByPass -File $f; Remove-Item $f
#
# 前提条件:
#   - git がインストール済みであること
#   - uv がインストール済みであること
#
# Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 9.2
# ============================================================

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$REPO_URL = "https://github.com/maruchiyo-yamaokaya/shop-nw-checker.git"
$TARGET_DIR = "shop-nw-checker"

# ---------- ヘルパー関数 ----------
function Write-Info  { param($msg) Write-Host "[INFO]  $msg" -ForegroundColor Cyan }
function Write-Ok    { param($msg) Write-Host "[OK]    $msg" -ForegroundColor Green }
function Write-Warn  { param($msg) Write-Host "[WARN]  $msg" -ForegroundColor Yellow }
function Write-Err   { param($msg) Write-Host "[ERROR] $msg" -ForegroundColor Red }

# ---------- 1. インターネット接続確認 (Req 1.6) ----------
Write-Info "インターネット接続を確認中..."
try {
    if (-not (Test-Connection -ComputerName 8.8.8.8 -Count 1 -Quiet -ErrorAction SilentlyContinue)) {
        throw "接続失敗"
    }
} catch {
    Write-Err "インターネット接続を確認できません。ネットワーク接続を確認してください。"
    exit 1
}
Write-Ok "インターネット接続OK"

# ---------- 2. git の存在確認 ----------
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Err "git が見つかりません。以下のコマンドでインストールしてください:"
    Write-Host ""
    Write-Host "    winget install --id Git.Git -e --source winget" -ForegroundColor White
    Write-Host ""
    Write-Err "インストール後、PowerShellを再起動してからこのスクリプトを再実行してください。"
    exit 1
}
Write-Ok "git 確認OK"

# ---------- 3. uv の存在確認 ----------
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Err "uv が見つかりません。以下のコマンドでインストールしてください:"
    Write-Host ""
    Write-Host '    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"' -ForegroundColor White
    Write-Host ""
    Write-Err "インストール後、PowerShellを再起動してからこのスクリプトを再実行してください。"
    exit 1
}
Write-Ok "uv 確認OK"

# ---------- 4. リポジトリの clone / pull (Req 1.1, 1.5) ----------
if (Test-Path "$TARGET_DIR\.git") {
    Write-Info "既存リポジトリを更新中..."
    git -C $TARGET_DIR pull --ff-only
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "git pull に失敗しました。既存コードで続行します。"
    }
} else {
    Write-Info "リポジトリをクローン中..."
    git clone $REPO_URL $TARGET_DIR
    if ($LASTEXITCODE -ne 0) {
        Write-Err "リポジトリのクローンに失敗しました。"
        exit 1
    }
}
Write-Ok "リポジトリ準備完了"

# ---------- 5. 仮想環境構築 + 依存インストール (Req 1.2, 1.3) ----------
Write-Info "依存パッケージをインストール中..."
Push-Location $TARGET_DIR
try {
    uv sync
    if ($LASTEXITCODE -ne 0) { throw "uv sync 失敗" }
} catch {
    Write-Err "依存パッケージのインストールに失敗しました。"
    Pop-Location
    exit 1
}
Pop-Location
Write-Ok "環境構築完了"

# ---------- 6. ツール起動案内 (Req 1.4) ----------
Write-Host ""
Write-Ok "セットアップ完了！"
Write-Host ""
Write-Info "以下のコマンドでツールを起動してください:"
Write-Host ""
Write-Host "    cd $TARGET_DIR; uv run store-net-test" -ForegroundColor White
Write-Host ""
