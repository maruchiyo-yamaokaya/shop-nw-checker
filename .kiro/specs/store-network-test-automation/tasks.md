# 実装計画: 店舗ネットワークテスト自動化ツール（Phase 1）

## 概要

Phase 1では、基本テスト（DNS解決・Ping到達性・安定性）の自動実行、ウィザード形式の対話入力、テスト結果のAirtable投入、ワンコマンド環境構築を実装する。「小さく始めて、賢く構築する」方針に従い、コアデータモデル → テスト実装 → ウィザード → レポーター → ランナー → ブートストラップの順で段階的に構築する。

## タスク

- [x] 1. プロジェクト構造とコアデータモデルの構築
  - [x] 1.1 プロジェクト初期構成を作成する
    - `pyproject.toml`を作成し、依存関係（icmplib, dnspython, httpx, rich, questionary, hypothesis, pytest, pytest-mock, pytest-asyncio）を定義する
    - 設計ドキュメントのディレクトリ構成に従い、`src/store_net_test/`配下のパッケージ構造と`__init__.py`を作成する
    - `tests/`ディレクトリと`__init__.py`を作成する
    - _Requirements: 9.1_

  - [x] 1.2 コアデータモデル（Enum・dataclass）を定義する
    - `WANPath` Enum、`TestStatus` Enum を定義する
    - `WizardInput`, `PingTarget`, `StabilityConfig`, `TestProfile`, `TestResult`, `SuiteResult` dataclassを定義する
    - `SuiteResult.overall_status`プロパティと`SuiteResult.summary`プロパティを実装する
    - _Requirements: 3.3, 3.6, 7.1_

  - [ ]* 1.3 Property 7のプロパティテストを作成する
    - **Property 7: 結果サマリーの正確性**
    - SuiteResult.summaryのpass/fail/warningカウントがresults内のstatus集計と一致すること、overall_statusのロジックが正しいことを検証する
    - **Validates: Requirements 3.6**

- [x] 2. テストプロファイル管理の実装
  - [x] 2.1 テストプロファイルの読み込み・バリデーション・変換を実装する（`profile.py`）
    - `load_profiles`: プロファイルディレクトリからJSONファイルを読み込む
    - `parse_profile`: 辞書からTestProfileオブジェクトを生成する
    - `profile_to_dict`: TestProfileオブジェクトを辞書に変換する
    - `validate_profile`: プロファイルのバリデーション（必須フィールド、閾値の範囲チェック）
    - 不正JSON・ファイル欠損時のエラーハンドリング
    - _Requirements: 7.1, 7.3, 7.4, 7.5_

  - [x] 2.2 デフォルトテストプロファイル（`profiles/default.json`）を作成する
    - 設計ドキュメントのJSONスキーマに従い、標準的な閾値を設定する
    - _Requirements: 7.4_

  - [ ]* 2.3 Property 1のプロパティテストを作成する
    - **Property 1: テストプロファイルのラウンドトリップ**
    - 任意の有効なTestProfileに対して`profile_to_dict` → `parse_profile`のラウンドトリップが等価であることを検証する
    - **Validates: Requirements 7.5**

- [x] 3. チェックポイント - プロファイル管理の動作確認
  - 全テストがパスすることを確認し、不明点があればユーザーに質問する。

- [x] 4. ネットワークテスト実装モジュールの構築
  - [x] 4.1 DNSテストモジュール（`tests/dns.py`）を実装する
    - `dnspython`を使用したクロスプラットフォームDNS解決テスト
    - DNS解決失敗時のfailマークとエラー詳細記録
    - TestResult形式での結果返却
    - _Requirements: 4.2, 4.5, 9.6_

  - [x] 4.2 Pingテストモジュール（`tests/ping.py`）を実装する
    - `icmplib`を使用したクロスプラットフォームICMP ping実装
    - 閾値に基づくpass/fail判定ロジック
    - TestResult形式での結果返却
    - _Requirements: 4.1, 4.3, 4.4, 9.4_

  - [ ]* 4.3 Property 8のプロパティテストを作成する
    - **Property 8: Ping閾値判定の正確性**
    - 任意のRTTと閾値の組み合わせに対して、RTT ≤ 閾値なら"pass"、RTT > 閾値なら"fail"であることを検証する
    - **Validates: Requirements 4.3, 4.4**

  - [x] 4.4 安定性テストモジュール（`tests/stability.py`）を実装する
    - `icmplib`を使用した継続的pingによるパケットロス率・ジッター計測
    - 閾値に基づくpass/fail判定ロジック
    - TestResult形式での結果返却
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 9.5_

  - [ ]* 4.5 Property 9のプロパティテストを作成する
    - **Property 9: パケットロス率の計算正確性**
    - 任意のsent > 0, 0 ≤ received ≤ sentに対して、パケットロス率が`(sent - received) / sent * 100`と等しいことを検証する
    - **Validates: Requirements 5.2**

  - [ ]* 4.6 Property 10のプロパティテストを作成する
    - **Property 10: ジッター計算の正確性**
    - 任意の2つ以上のRTT値リストに対して、ジッターが連続RTT差の絶対値の平均と等しいことを検証する
    - **Validates: Requirements 5.3**

  - [ ]* 4.7 Property 11のプロパティテストを作成する
    - **Property 11: 安定性閾値判定の正確性**
    - 任意のパケットロス率・ジッター値と閾値の組み合わせに対して、閾値超過時は"fail"、以内は"pass"であることを検証する
    - **Validates: Requirements 5.4, 5.5**

- [x] 5. チェックポイント - テストモジュールの動作確認
  - 全テストがパスすることを確認し、不明点があればユーザーに質問する。

- [-] 6. ウィザード（対話入力）の実装
  - [x] 6.1 Setup Wizard（`wizard.py`）を実装する
    - `questionary`を使用したステップバイステップの対話入力（店舗名 → NW領域 → VLAN → WAN経路 → テストプロファイル）
    - 各入力のバリデーション（`validate_store_name`, `validate_vlan`）
    - WAN経路のデフォルト値を"both"に設定
    - 確認サマリー表示と承認/却下フロー（却下時は最初から再開）
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10_

  - [ ]* 6.2 Property 2のプロパティテストを作成する
    - **Property 2: 入力バリデーションの一貫性**
    - 任意の文字列に対して、空文字列・空白のみはエラー、非空白文字を含む文字列はNoneを返すことを検証する
    - **Validates: Requirements 2.8**

  - [ ]* 6.3 Property 3のプロパティテストを作成する
    - **Property 3: 確認サマリーの完全性**
    - 任意の有効なWizardInputに対して、サマリー文字列が全フィールドの値を含むことを検証する
    - **Validates: Requirements 2.6**

- [x] 7. レポーター（結果投入）の実装
  - [x] 7.1 ローカルJSONレポーター（`reporters/local.py`）を実装する
    - `suite_result_to_dict`: SuiteResultをJSON直列化可能な辞書に変換する
    - `save_results_to_json`: 結果をローカルJSONファイルに保存する
    - _Requirements: 6.5_

  - [ ]* 7.2 Property 14のプロパティテストを作成する
    - **Property 14: ローカルJSON保存のラウンドトリップ**
    - 任意の有効なSuiteResultに対して、辞書変換 → JSON直列化 → デシリアライズの結果が元の辞書と等価であることを検証する
    - **Validates: Requirements 6.5**

  - [x] 7.3 Airtableレポーター（`reporters/airtable.py`）を実装する
    - `load_airtable_config`: 環境変数またはローカル設定ファイルからAirtable設定を読み込む
    - `build_airtable_record`: SuiteResultからAirtableレコード用辞書を構築する
    - `submit_results`: 指数バックオフ付き最大3回リトライでAirtableに投入する
    - 全リトライ失敗時のローカルJSONフォールバック
    - 成功時のレコードURL表示
    - WAN経路別に個別レコードを作成する
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

  - [ ]* 7.4 Property 12のプロパティテストを作成する
    - **Property 12: Airtableレコードの構造的完全性**
    - 任意の有効なSuiteResultに対して、`build_airtable_record`が全必須フィールドを含むことを検証する
    - **Validates: Requirements 6.2**

  - [ ]* 7.5 Property 13のプロパティテストを作成する
    - **Property 13: WAN経路別レコード分離**
    - 任意の複数WAN経路の結果リストに対して、生成レコード数がWAN経路数と一致し、各レコードが1つのWAN経路のみ含むことを検証する
    - **Validates: Requirements 6.3**

- [x] 8. チェックポイント - レポーターの動作確認
  - 全テストがパスすることを確認し、不明点があればユーザーに質問する。

- [x] 9. テストランナーとメインフローの統合
  - [x] 9.1 テストランナー（`runner.py`）を実装する
    - `run_test_suite`: プロファイルに基づきDNS・Ping・安定性テストを順次実行する
    - WAN経路が複数の場合、FTTH → LTEの順で実行する
    - テスト項目のシステムエラー時はスキップして次に進む
    - 進捗表示（テスト名、WAN経路、プログレスインジケータ）
    - `display_summary`: 結果サマリーのコンソール表示
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [ ]* 9.2 Property 4のプロパティテストを作成する
    - **Property 4: テスト実行の網羅性と順序**
    - 任意のN個テスト項目×M個WAN経路に対して、結果数がN×Mであり、FTTH結果のタイムスタンプがLTE結果より前であることを検証する
    - **Validates: Requirements 3.1, 3.2**

  - [ ]* 9.3 Property 5のプロパティテストを作成する
    - **Property 5: テスト結果の構造的完全性**
    - 任意の完了テスト項目に対して、TestResultが全必須フィールド（test_name, wan_path, status, timestamp）を含むことを検証する
    - **Validates: Requirements 3.3**

  - [ ]* 9.4 Property 6のプロパティテストを作成する
    - **Property 6: テスト実行のエラー耐性**
    - テスト項目の一部がエラーで失敗しても、残りの全テスト項目が実行・記録されることを検証する
    - **Validates: Requirements 3.5**

  - [x] 9.5 メインエントリーポイント（`main.py`）を実装する
    - インターネット接続確認 → Setup Wizard → テストスイート実行 → 結果サマリー表示 → Airtable投入の一連フローを統合する
    - _Requirements: 8.1, 8.2, 8.3_

  - [x] 9.6 ユーティリティモジュールを実装する
    - `utils/network.py`: インターネット接続確認（`check_internet_connectivity`）
    - `utils/platform.py`: OS判定、未サポートOS検出時のエラー表示
    - OS非依存のパス処理（`pathlib`使用）
    - _Requirements: 8.1, 8.2, 8.3, 9.1, 9.3, 9.7_

- [x] 10. ブートストラップスクリプトの実装
  - [x] 10.1 Bootstrap Script（`bootstrap.sh` + `bootstrap.bat`）を実装する
    - `bootstrap.sh`（macOS/Linux用）と`bootstrap.bat`（Windows用）の2ファイル構成
    - Pythonが未インストールの環境でも動作する（シェル/バッチで実装）
    - インターネット接続確認、uv自動インストール、リポジトリclone/pull、依存インストール、ツール起動
    - インターネット未接続・uv失敗時のエラーメッセージ表示
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 9.2_

- [x] 11. 最終チェックポイント - 全体統合テスト
  - 全テストがパスすることを確認し、不明点があればユーザーに質問する。

## 備考

- `*`マーク付きタスクはオプションであり、MVP優先時はスキップ可能
- 各タスクは対応する要件番号を参照しトレーサビリティを確保
- チェックポイントで段階的に動作を検証
- プロパティテストはhypothesisで普遍的な正しさを検証、ユニットテストは具体例・エッジケースを検証
- Phase 2（Requirement 10, 11）は本計画のスコープ外
