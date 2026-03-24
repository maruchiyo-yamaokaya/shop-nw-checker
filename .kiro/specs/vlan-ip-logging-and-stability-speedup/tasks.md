# 実装計画: VLAN IPアドレス記録 & 安定性テスト高速化

## 概要

2つの機能改善を段階的に実装する。データモデル変更 → ユーティリティ追加 → ロジック層統合 → 入出力層対応 → プロファイル更新の順で構築する。

## タスク

- [x] 1. データモデルの拡張
  - [x] 1.1 `models.py`の`SuiteResult`に`local_ip: str | None = None`フィールドを追加する
    - 後方互換性のためデフォルトNone
    - _Requirements: 2.1, 2.2_

  - [x] 1.2 `models.py`の`StabilityConfig`に`ping_interval: float = 0.2`フィールドを追加する
    - デフォルト0.2秒（後方互換性維持）
    - _Requirements: 4.1, 4.2_

- [x] 2. ネットワークユーティリティの拡張
  - [x] 2.1 `utils/network.py`に`get_local_ip()`関数を追加する
    - UDPソケットで`8.8.8.8:80`にconnectし、`getsockname()[0]`でローカルIPを取得する
    - 取得失敗時はNoneを返し、例外を発生させない
    - _Requirements: 1.1, 1.2_

  - [x] 2.2 `tests/test_network.py`に`get_local_ip`のユニットテストを追加する
    - ソケット正常時に有効なIPv4文字列を返すことをモックで検証
    - ソケットエラー時にNoneを返すことを検証
    - _Requirements: 1.1, 1.2_

  - [ ]* 2.3 Property 1のプロパティテストを作成する
    - **Property 1: get_local_ipは有効なIPv4文字列またはNoneを返す**
    - 任意の実行環境において、戻り値が`ipaddress.ip_address()`でパース可能なIPv4文字列またはNoneであることを検証する
    - **Validates: Requirements 1.1, 1.2**

- [x] 3. チェックポイント - データモデルとユーティリティの動作確認
  - 全テストがパスすることを確認し、不明点があればユーザーに質問する。

- [x] 4. 安定性テストの高速化
  - [x] 4.1 `tests/stability.py`の`run_stability_test`を修正する
    - `interval`パラメータに`config.ping_interval`を使用する
    - 送信パケット数を`int(config.duration_seconds / config.ping_interval)`で算出する
    - _Requirements: 4.3, 4.4_

  - [x] 4.2 `profile.py`の`parse_profile`で`ping_interval`を読み込む
    - `stability`辞書から`ping_interval`を読み込む（キー不在時はデフォルト0.2）
    - _Requirements: 4.1, 4.2_

  - [x] 4.3 `profile.py`の`profile_to_dict`で`ping_interval`を出力する
    - `stability`辞書に`ping_interval`を含める
    - _Requirements: 4.1_

  - [x] 4.4 `profile.py`の`validate_profile`で`ping_interval`が正の値であることを検証する
    - `ping_interval`が0以下の場合にエラーメッセージを追加する
    - _Requirements: 4.1_

  - [x] 4.5 `tests/test_profile.py`にping_interval関連のユニットテストを追加する
    - `parse_profile`: `ping_interval`未指定時にデフォルト0.2が設定されること
    - `parse_profile`: `ping_interval`指定時に値が正しく読み込まれること
    - `profile_to_dict` → `parse_profile`のラウンドトリップで`ping_interval`が保持されること
    - `validate_profile`: `ping_interval`が0以下でエラーになること
    - _Requirements: 4.1, 4.2_

  - [ ]* 4.6 Property 4のプロパティテストを作成する
    - **Property 4: 安定性テストのパケット数計算**
    - 任意の正の`duration_seconds`と正の`ping_interval`に対して、算出されるパケット数が1以上であることを検証する
    - **Validates: Requirements 4.3**

  - [ ]* 4.7 Property 5のプロパティテストを作成する
    - **Property 5: StabilityConfig付きプロファイルのラウンドトリップ**
    - 任意の有効なTestProfile（`ping_interval`を含むStabilityConfig付き）に対して、`profile_to_dict` → `parse_profile`のラウンドトリップが等価であることを検証する
    - **Validates: Requirements 4.1**

- [x] 5. チェックポイント - 安定性テスト高速化の動作確認
  - 全テストがパスすることを確認し、不明点があればユーザーに質問する。

- [x] 6. Runner統合とレポーター対応
  - [x] 6.1 `runner.py`の`_run_tests_for_wan_path`にIP取得・表示・格納ロジックを追加する
    - テスト開始前に`get_local_ip()`を呼び出す
    - 取得したIPをコンソールに表示する（None時は警告メッセージ表示）
    - `SuiteResult`の`local_ip`フィールドに格納する
    - _Requirements: 1.1, 2.1, 3.1, 3.2_

  - [x] 6.2 `reporters/local.py`の`suite_result_to_dict`に`local_ip`フィールドを追加する
    - 出力辞書に`local_ip`キーを含める
    - _Requirements: 2.3_

  - [x] 6.3 `reporters/airtable.py`の`build_airtable_record`に`local_ip`フィールドを追加する
    - Webhookペイロードに`local_ip`キーを含める
    - _Requirements: 2.4_

  - [x] 6.4 `tests/test_runner.py`にIP取得・表示のユニットテストを追加する
    - `get_local_ip`が呼ばれ、結果が`SuiteResult.local_ip`に格納されること
    - IP取得成功時にコンソール表示されること
    - IP取得失敗（None）時に警告メッセージが表示されること
    - _Requirements: 1.1, 3.1, 3.2_

  - [x] 6.5 `tests/test_reporter.py`にlocal_ip直列化のユニットテストを追加する
    - `suite_result_to_dict`の出力に`local_ip`キーが含まれること
    - `build_airtable_record`の出力に`local_ip`キーが含まれること
    - `local_ip=None`の場合にnullとして出力されること
    - _Requirements: 2.3, 2.4_

  - [ ]* 6.6 Property 2のプロパティテストを作成する
    - **Property 2: SuiteResultのローカルレポーター直列化にlocal_ipが含まれる**
    - 任意の`SuiteResult`（`local_ip`がstr or None）に対して、`suite_result_to_dict()`の出力辞書に`local_ip`キーが存在し、元の値と等しいことを検証する
    - **Validates: Requirements 2.1, 2.3**

  - [ ]* 6.7 Property 3のプロパティテストを作成する
    - **Property 3: SuiteResultのAirtableレポーター直列化にlocal_ipが含まれる**
    - 任意の`SuiteResult`（`local_ip`がstr or None）に対して、`build_airtable_record()`の出力辞書に`local_ip`キーが存在し、元の値と等しいことを検証する
    - **Validates: Requirements 2.1, 2.4**

- [x] 7. チェックポイント - Runner統合とレポーター対応の動作確認
  - 全テストがパスすることを確認し、不明点があればユーザーに質問する。

- [x] 8. デフォルトプロファイルの更新
  - [x] 8.1 `profiles/default.json`の安定性テスト設定を更新する
    - `stability.duration_seconds`を`5`に変更する
    - `stability.ping_interval`を`0.2`に追加する
    - _Requirements: 5.1, 5.2_

  - [x] 8.2 `tests/test_profile.py`の`test_実際のデフォルトプロファイルを読み込める`テストを更新する
    - `duration_seconds`が5であることを検証する
    - `ping_interval`が0.2であることを検証する
    - _Requirements: 5.1, 5.2, 5.3_

- [x] 9. 最終チェックポイント - 全体統合テスト
  - 全テストがパスすることを確認し、不明点があればユーザーに質問する。

## 備考

- `*`マーク付きタスクはオプションであり、MVP優先時はスキップ可能
- 各タスクは対応する要件番号を参照しトレーサビリティを確保
- チェックポイントで段階的に動作を検証
- プロパティテストはHypothesisで普遍的な正しさを検証、ユニットテストは具体例・エッジケースを検証
- 既存テスト（`test_profile.py`, `test_reporter.py`, `test_runner.py`）が引き続きパスすることを各チェックポイントで確認する
