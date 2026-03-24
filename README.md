# 🏪 店舗ネットワークテスト自動化ツール

店舗現場でネットワーク構築・変更後に、名前解決・到達性・安定性テストを自動実行するCLIツールです。

## クイックスタート

### macOS / Linux

ターミナルで以下を実行してください:

```bash
curl -fsSL https://raw.githubusercontent.com/maruchiyo-yamaokaya/shop-nw-checker/main/bootstrap.sh | bash
```

### Windows

PowerShellで以下を実行してください:

```powershell
irm https://raw.githubusercontent.com/maruchiyo-yamaokaya/shop-nw-checker/main/bootstrap.ps1 | iex
```

ブートストラップスクリプトが以下を自動で行います:

1. インターネット接続確認
2. git の確認・インストール（未導入時）
3. uv（Pythonパッケージマネージャ）のインストール
4. リポジトリのクローン
5. 依存パッケージのインストール
6. ツールの起動

## 2回目以降の実行

同じコマンドを再実行すると、リポジトリを最新に更新してからツールを起動します。

## 前提条件

- インターネット接続（必須）
- git（未導入の場合、スクリプトが自動インストールを試みます）

> **Note**: Python のインストールは不要です。uv が自動でPython環境を構築します。

## Airtable連携（オプション）

テスト結果をAirtableに自動投入するには、プロジェクトルートの `.env` ファイルに以下を設定してください:

```
AIRTABLE_WEBHOOK_URL=https://hooks.airtable.com/workflows/your-webhook-url
```

未設定の場合、Airtable投入はスキップされます。

## 開発者向け

### ローカル開発環境のセットアップ

```bash
git clone https://github.com/maruchiyo-yamaokaya/shop-nw-checker.git
cd shop-nw-checker
uv sync
```

### テスト実行

```bash
uv run pytest tests/ -v
```

### ツールの直接実行

```bash
uv run store-net-test
```
