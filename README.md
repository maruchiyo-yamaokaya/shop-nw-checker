# 🏪 店舗ネットワークテスト自動化ツール

店舗現場でネットワーク構築・変更後に、名前解決・到達性・安定性テストを自動実行するCLIツールです。

## クイックスタート

### macOS / Linux

ターミナルで以下を実行してください:

```bash
curl -fsSL https://raw.githubusercontent.com/maruchiyo-yamaokaya/shop-nw-checker/main/bootstrap.sh | bash
```

セットアップ完了後、以下でツールを起動してください:
```bash
uv run --project shop-nw-checker store-net-test
```

### Windows

#### 1. 事前準備（初回のみ）

PowerShellを開いて、以下を1行ずつコピペして実行してください。

**① git のインストール:**
```
winget install --id Git.Git -e --source winget
```

**② uv のインストール:**
```
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**③ PowerShellを閉じて、再度開いてください。**

#### 2. ブートストラップ実行

以下をコピペして実行してください:
```
$f="$env:TEMP\bs.ps1"; irm "https://raw.githubusercontent.com/maruchiyo-yamaokaya/shop-nw-checker/main/bootstrap.ps1?v=$(Get-Date -f yyyyMMddHHmmss)" -OutFile $f; powershell -ExecutionPolicy ByPass -File $f; Remove-Item $f
```

ブートストラップスクリプトが以下を自動で行います:

1. インターネット接続確認
2. git / uv の存在確認
3. リポジトリのクローン（または更新）
4. 依存パッケージのインストール
5. ツールの自動起動

## 2回目以降の実行

同じコマンドを再実行すると、リポジトリを最新に更新してからツールを自動起動します。

## 前提条件

- インターネット接続（必須）
- git
- macOS / Linux: 未導入の場合、スクリプトが自動インストールを試みます
- Windows: 事前にインストールが必要です（上記手順参照）

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
