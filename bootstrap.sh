#!/usr/bin/env bash
# ============================================================
# 店舗ネットワークテスト自動化ツール — ブートストラップスクリプト
# macOS / Linux 用
#
# ワンコマンドで以下を実行する:
#   1. インターネット接続確認
#   2. git の確認・インストール（未導入時）
#   3. uv のインストール（未導入時）
#   4. リポジトリの clone または pull
#   5. 仮想環境構築 + 依存インストール
#   6. ツール起動
#
# Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 9.2
# ============================================================

set -euo pipefail

# ---------- 設定 ----------
REPO_URL="https://github.com/maruchiyo-yamaokaya/shop-nw-checker.git"
TARGET_DIR="shop-nw-checker"

# ---------- ヘルパー関数 ----------
info()  { printf '\033[1;34m[INFO]\033[0m  %s\n' "$*"; }
ok()    { printf '\033[1;32m[OK]\033[0m    %s\n' "$*"; }
warn()  { printf '\033[1;33m[WARN]\033[0m  %s\n' "$*"; }
err()   { printf '\033[1;31m[ERROR]\033[0m %s\n' "$*" >&2; }

# ---------- 1. インターネット接続確認 (Req 1.6) ----------
check_internet() {
    info "インターネット接続を確認中..."
    # DNS (8.8.8.8:53) への TCP 接続で判定
    if command -v curl >/dev/null 2>&1; then
        curl -s --max-time 5 https://www.google.com >/dev/null 2>&1 && return 0
    elif command -v wget >/dev/null 2>&1; then
        wget -q --timeout=5 -O /dev/null https://www.google.com 2>/dev/null && return 0
    fi
    # curl/wget どちらもない場合は /dev/tcp で試行
    (echo >/dev/tcp/8.8.8.8/53) 2>/dev/null && return 0
    return 1
}

if ! check_internet; then
    err "インターネット接続を確認できません。ネットワーク接続を確認してください。"
    exit 1
fi
ok "インターネット接続OK"

# ---------- 2. git の確認・インストール ----------
install_git() {
    info "git をインストール中..."
    case "$(uname -s)" in
        Darwin)
            # macOS: Xcode Command Line Tools で git を導入
            if ! xcode-select --install 2>/dev/null; then
                err "git の自動インストールに失敗しました。"
                err "手動でインストールしてください: https://git-scm.com/download/mac"
                exit 1
            fi
            info "Xcode Command Line Tools のインストールダイアログが表示されます。"
            info "インストール完了後、このスクリプトを再実行してください。"
            exit 0
            ;;
        Linux)
            # Linux: apt / yum / dnf を試行
            if command -v apt-get >/dev/null 2>&1; then
                sudo apt-get update && sudo apt-get install -y git
            elif command -v yum >/dev/null 2>&1; then
                sudo yum install -y git
            elif command -v dnf >/dev/null 2>&1; then
                sudo dnf install -y git
            else
                err "git の自動インストールに失敗しました。"
                err "手動でインストールしてください: https://git-scm.com/download/linux"
                exit 1
            fi
            ;;
        *)
            err "git が見つかりません。手動でインストールしてください: https://git-scm.com/"
            exit 1
            ;;
    esac
}

if ! command -v git >/dev/null 2>&1; then
    install_git
fi

if ! command -v git >/dev/null 2>&1; then
    err "git が見つかりません。手動でインストールしてください: https://git-scm.com/"
    exit 1
fi
ok "git 確認OK ($(git --version))"

# ---------- 3. uv のインストール (Req 1.2, 1.3, 1.7) ----------
install_uv() {
    info "uv をインストール中..."
    if ! curl -LsSf https://astral.sh/uv/install.sh | sh; then
        err "uv のインストールに失敗しました。"
        err "手動インストール: https://docs.astral.sh/uv/getting-started/installation/"
        exit 1
    fi
    # インストール直後に PATH を通す
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
}

if ! command -v uv >/dev/null 2>&1; then
    install_uv
fi

if ! command -v uv >/dev/null 2>&1; then
    err "uv が見つかりません。PATH を確認してください。"
    exit 1
fi
ok "uv 確認OK ($(uv --version))"

# ---------- 4. リポジトリの clone / pull (Req 1.1, 1.5) ----------
if [ -d "$TARGET_DIR/.git" ]; then
    info "既存リポジトリを更新中..."
    git -C "$TARGET_DIR" pull --ff-only || {
        warn "git pull に失敗しました。既存コードで続行します。"
    }
else
    info "リポジトリをクローン中..."
    if ! git clone "$REPO_URL" "$TARGET_DIR"; then
        err "リポジトリのクローンに失敗しました: $REPO_URL"
        exit 1
    fi
fi
ok "リポジトリ準備完了"

# ---------- 5. 仮想環境構築 + 依存インストール (Req 1.2, 1.3) ----------
info "依存パッケージをインストール中..."
if ! uv sync --project "$TARGET_DIR"; then
    err "依存パッケージのインストールに失敗しました。"
    exit 1
fi
ok "環境構築完了"

# ---------- 6. ツール起動案内 (Req 1.4) ----------
echo ""
ok "セットアップ完了！"
echo ""
info "以下のコマンドでツールを起動してください:"
echo ""
echo "    uv run --project $TARGET_DIR store-net-test"
echo ""
