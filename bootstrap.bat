@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

REM ============================================================
REM 店舗ネットワークテスト自動化ツール — ブートストラップスクリプト
REM Windows 用
REM
REM ワンコマンドで以下を実行する:
REM   1. インターネット接続確認
REM   2. git の確認・インストール（未導入時）
REM   3. uv のインストール（未導入時）
REM   4. リポジトリの clone または pull
REM   5. 仮想環境構築 + 依存インストール
REM   6. ツール起動
REM
REM Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 9.2
REM ============================================================

set "REPO_URL=https://github.com/maruchiyo-yamaokaya/shop-nw-checker.git"
set "TARGET_DIR=shop-nw-checker"

REM ---------- 1. インターネット接続確認 (Req 1.6) ----------
echo [INFO]  インターネット接続を確認中...
ping -n 1 -w 3000 8.8.8.8 >nul 2>&1
if errorlevel 1 (
    echo [ERROR] インターネット接続を確認できません。ネットワーク接続を確認してください。
    exit /b 1
)
echo [OK]    インターネット接続OK

REM ---------- 2. git の確認・インストール ----------
where git >nul 2>&1
if errorlevel 1 (
    echo [INFO]  git をインストール中...
    where winget >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] git が見つかりません。winget も利用できません。
        echo [ERROR] 手動でインストールしてください: https://git-scm.com/download/win
        exit /b 1
    )
    winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo [ERROR] git の自動インストールに失敗しました。
        echo [ERROR] 手動でインストールしてください: https://git-scm.com/download/win
        exit /b 1
    )
    REM インストール後に PATH を更新
    set "PATH=C:\Program Files\Git\cmd;%PATH%"
)

where git >nul 2>&1
if errorlevel 1 (
    echo [ERROR] git が見つかりません。手動でインストールしてください: https://git-scm.com/download/win
    exit /b 1
)
echo [OK]    git 確認OK

REM ---------- 3. uv のインストール (Req 1.2, 1.3, 1.7) ----------
where uv >nul 2>&1
if errorlevel 1 (
    echo [INFO]  uv をインストール中...
    powershell -ExecutionPolicy ByPass -NoProfile -Command "irm https://astral.sh/uv/install.ps1 | iex"
    if errorlevel 1 (
        echo [ERROR] uv のインストールに失敗しました。
        echo [ERROR] 手動インストール: https://docs.astral.sh/uv/getting-started/installation/
        exit /b 1
    )
    REM インストール後に PATH を更新
    set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%PATH%"
)

where uv >nul 2>&1
if errorlevel 1 (
    echo [ERROR] uv が見つかりません。PATH を確認してください。
    exit /b 1
)
echo [OK]    uv 確認OK

REM ---------- 4. リポジトリの clone / pull (Req 1.1, 1.5) ----------
if exist "%TARGET_DIR%\.git" (
    echo [INFO]  既存リポジトリを更新中...
    git -C "%TARGET_DIR%" pull --ff-only
    if errorlevel 1 (
        echo [WARN]  git pull に失敗しました。既存コードで続行します。
    )
) else (
    echo [INFO]  リポジトリをクローン中...
    git clone "%REPO_URL%" "%TARGET_DIR%"
    if errorlevel 1 (
        echo [ERROR] リポジトリのクローンに失敗しました。
        exit /b 1
    )
)
echo [OK]    リポジトリ準備完了

REM ---------- 5. 仮想環境構築 + 依存インストール (Req 1.2, 1.3) ----------
echo [INFO]  依存パッケージをインストール中...
uv sync --project "%TARGET_DIR%"
if errorlevel 1 (
    echo [ERROR] 依存パッケージのインストールに失敗しました。
    exit /b 1
)
echo [OK]    環境構築完了

REM ---------- 6. ツール起動案内 (Req 1.4) ----------
echo.
echo [OK]    セットアップ完了！
echo.
echo [INFO]  以下のコマンドでツールを起動してください:
echo.
echo     cd %TARGET_DIR% ^&^& uv run store-net-test
echo.

endlocal
