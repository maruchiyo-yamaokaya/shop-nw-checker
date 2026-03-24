# ============================================================
# 店舗ネットワークテスト自動化ツール — ブートストラップスクリプト
# Windows PowerShell 用
#
# ワンコマンドで以下を実行する:
#   1. インターネット接続確認
#   2. git の確認・インストール（未導入時）
#   3. uv のインストール（未導入時）
#   4. リポジトリの clone または pull
#   5. 仮想環境構築 + 依存インストール
#   6. ツール起動案内
#
# 使い方:
#   irm https://raw.githubusercontent.com/maruchiyo-yamaokaya/shop-nw-checker/main/bootstrap.ps1 | iex
#
# Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 9.2
# ============================================================

# iex経由でもウィンドウが閉じないよう、全体を関数でラップする
function Invoke-Bootstrap {
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
        return
    }
    Write-Ok "インターネット接続OK"

    # ---------- 2. git の確認・インストール ----------
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Write-Info "git をインストール中..."
        if (Get-Command winget -ErrorAction SilentlyContinue) {
            & winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements
            # インストール後に PATH を更新
            $env:PATH = "C:\Program Files\Git\cmd;$env:PATH"
        } else {
            Write-Err "git が見つかりません。winget も利用できません。"
            Write-Err "手動でインストールしてください: https://git-scm.com/download/win"
            return
        }
    }

    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Write-Err "git が見つかりません。手動でインストールしてください: https://git-scm.com/download/win"
        return
    }
    Write-Ok "git 確認OK"

    # ---------- 3. uv のインストール (Req 1.2, 1.3, 1.7) ----------
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Info "uv をインストール中..."
        try {
            $installScript = Invoke-RestMethod https://astral.sh/uv/install.ps1
            & ([scriptblock]::Create($installScript))
            # インストール後に PATH を更新
            $env:PATH = "$env:USERPROFILE\.local\bin;$env:USERPROFILE\.cargo\bin;$env:PATH"
        } catch {
            Write-Err "uv のインストールに失敗しました。"
            Write-Err "手動インストール: https://docs.astral.sh/uv/getting-started/installation/"
            return
        }
    }

    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Err "uv が見つかりません。PATH を確認してください。"
        return
    }
    Write-Ok "uv 確認OK"

    # ---------- 4. リポジトリの clone / pull (Req 1.1, 1.5) ----------
    if (Test-Path "$TARGET_DIR\.git") {
        Write-Info "既存リポジトリを更新中..."
        & git -C $TARGET_DIR pull --ff-only
        if ($LASTEXITCODE -ne 0) {
            Write-Warn "git pull に失敗しました。既存コードで続行します。"
        }
    } else {
        Write-Info "リポジトリをクローン中..."
        & git clone $REPO_URL $TARGET_DIR
        if ($LASTEXITCODE -ne 0) {
            Write-Err "リポジトリのクローンに失敗しました。"
            return
        }
    }
    Write-Ok "リポジトリ準備完了"

    # ---------- 5. 仮想環境構築 + 依存インストール (Req 1.2, 1.3) ----------
    Write-Info "依存パッケージをインストール中..."
    Push-Location $TARGET_DIR
    try {
        & uv sync
        if ($LASTEXITCODE -ne 0) { throw "uv sync 失敗" }
    } catch {
        Write-Err "依存パッケージのインストールに失敗しました。"
        Pop-Location
        return
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
}

# 関数を実行する
Invoke-Bootstrap
