# Implementation Plan: wizard-input-refactor

## Overview

5ステップ対話入力を3ステップ（店舗コード → VLAN種別 → WAN経路）に再構成する。
データモデル（models.py）を起点に、wizard.py → runner.py → reporters → main.py → tests の順で整合的に更新する。

## Tasks

- [x] 1. データモデルの更新（models.py）
  - [x] 1.1 WizardInput を更新する
    - `store_name: str` → `store_code: str` にリネーム
    - `nw_area: str` フィールドを削除
    - `vlan: str` → `vlan_type: str` にリネーム
    - `wan_paths: list[WANPath]` → `wan_path: WANPath` に変更（単一値）
    - `test_profile: str` フィールドを削除
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 1.2 SuiteResult を更新する
    - `store_name: str` → `store_code: str` にリネーム
    - `nw_area: str` フィールドを削除
    - `vlan: str` → `vlan_type: str` にリネーム
    - _Requirements: 5.1, 5.2, 5.3_

- [x] 2. ウィザードの更新（wizard.py）
  - [x] 2.1 不要な定数・関数・クラスを削除し、新しい定数・関数を追加する
    - `DEFAULT_NW_AREAS`、旧 `WAN_PATH_CHOICES`、`ProfileSummary`、`validate_store_name()`、`validate_vlan()`、`_parse_wan_selection()` を削除
    - `VLAN_TYPE_CHOICES = ["店舗", "POS", "公共"]` を追加
    - `WAN_PATH_CHOICES = [{"name": "FTTH", "value": "ftth"}, {"name": "LTE", "value": "lte"}]` を再定義
    - `validate_store_code(code: str) -> str | None` を追加（正規表現 `^[0-9]{4}$` で検証）
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6_

  - [x] 2.2 `run_wizard()` を3ステップ構成に書き換える
    - `available_profiles` パラメータと `nw_areas` パラメータを削除
    - ステップ1: 店舗コード入力（`validate_store_code` でバリデーション）
    - ステップ2: VLAN種別選択（`questionary.select` で「店舗」「POS」「公共」）
    - ステップ3: WAN経路選択（`questionary.select` で「FTTH」「LTE」の2択）
    - `WizardInput` を新フィールドで構築
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 3.4, 6.1, 6.2, 6.3, 6.4_

  - [x] 2.3 確認サマリー関連関数を更新する
    - `_build_confirmation_text()`: `store_code`、`vlan_type`、`wan_path`（単一値）を使用、`nw_area` 行と `test_profile` 行を削除
    - `display_confirmation()`: テーブル行を同様に更新
    - _Requirements: 10.1, 10.2, 10.3_

  - [ ]* 2.4 validate_store_code のプロパティテストを作成する（tests/test_wizard_validation.py）
    - **Property 1: validate_store_code は正規表現 `^[0-9]{4}$` と等価**
    - `hypothesis.strategies.text()` で任意文字列を生成し、`validate_store_code(s.strip()) is None` ⟺ `re.fullmatch(r"[0-9]{4}", s.strip())` を検証
    - **Validates: Requirements 1.2, 1.3, 1.4, 11.1, 11.2**

  - [ ]* 2.5 確認サマリーのプロパティテストを作成する（tests/test_wizard_validation.py）
    - **Property 5: 確認サマリーのフィールド整合性**
    - `_build_confirmation_text` の出力に「店舗コード」と `store_code` の値、「VLAN種別」と `vlan_type` の値が含まれ、「NW領域」が含まれないことを検証
    - **Validates: Requirements 10.1, 10.2, 10.3**

- [x] 3. テストランナーの更新（runner.py）
  - [x] 3.1 `_run_tests_for_wan_path()` の SuiteResult 構築を更新する
    - `store_name` → `store_code`、`nw_area` 削除、`vlan` → `vlan_type`
    - _Requirements: 7.1, 7.2, 7.3_

  - [x] 3.2 `run_test_suite()` を単一 WAN 経路実行に変更する
    - `wizard_input.wan_paths` のループを削除し、`wizard_input.wan_path` で1回実行
    - 戻り値を `list[SuiteResult]` → `SuiteResult` に変更
    - _Requirements: 7.4_

  - [x] 3.3 `display_summary()` を単一 SuiteResult 対応に変更する
    - 引数を `list[SuiteResult]` → `SuiteResult` に変更
    - _Requirements: 7.1, 7.2, 7.3_

- [x] 4. Checkpoint - models.py、wizard.py、runner.py の変更を確認
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. レポーターの更新
  - [x] 5.1 Local Reporter（reporters/local.py）を更新する
    - `suite_result_to_dict()`: `store_name` → `store_code`、`nw_area` 削除、`vlan` → `vlan_type`
    - `save_results_to_json()`: ファイル名の `store_name` → `store_code`
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [x] 5.2 Airtable Reporter（reporters/airtable.py）を更新する
    - `build_airtable_record()`: `store_name` → `store_code`、`nw_area` 削除、`vlan` → `vlan_type`
    - `_submit_with_retry()` のログメッセージ: `store_name` → `store_code`
    - `submit_results()`: 引数を `list[SuiteResult]` → `SuiteResult` に変更し、ループを削除
    - _Requirements: 9.1, 9.2, 9.3_

  - [ ]* 5.3 Local Reporter のプロパティテストを作成する（tests/test_models.py）
    - **Property 2: Local Reporter の辞書キー整合性**
    - `suite_result_to_dict` の出力に `store_code`、`vlan_type` が含まれ、`store_name`、`nw_area`、`vlan` が含まれないことを検証
    - **Validates: Requirements 8.1, 8.2, 8.3**

  - [ ]* 5.4 Local Reporter のファイル名プロパティテストを作成する（tests/test_models.py）
    - **Property 3: Local Reporter のファイル名に store_code を含む**
    - `save_results_to_json` が生成するファイル名に `store_code` の値が含まれることを検証
    - **Validates: Requirements 8.4**

  - [ ]* 5.5 Airtable Reporter のプロパティテストを作成する（tests/test_models.py）
    - **Property 4: Airtable Reporter のレコードキー整合性**
    - `build_airtable_record` の出力に `store_code`、`vlan_type` が含まれ、`store_name`、`nw_area`、`vlan` が含まれないことを検証
    - **Validates: Requirements 9.1, 9.2, 9.3**

- [x] 6. メインエントリーポイントの更新（main.py）
  - [x] 6.1 `_run()` を更新する
    - `run_wizard()` の呼び出しから `available_profiles` パラメータを削除
    - テストプロファイルは `profiles[0]` を自動使用（`wizard_input.test_profile` による検索を削除）
    - `run_test_suite()` の戻り値が `SuiteResult`（単一）に変更されるため、`display_summary()` と `submit_results()` の引数を調整
    - _Requirements: 3.5, 7.4_

- [x] 7. 既存テストコードの更新
  - [x] 7.1 tests/test_reporter.py を更新する
    - `_make_suite_result()` ヘルパー: `store_name` → `store_code`、`nw_area` 削除、`vlan` → `vlan_type`
    - 全アサーションのキー名を `store_code`、`vlan_type` に更新
    - `store_name`、`nw_area`、`vlan` キーのアサーションを削除
    - `submit_results` テスト: 引数を `list[SuiteResult]` → `SuiteResult` に調整
    - _Requirements: 12.1, 12.2, 12.3_

- [x] 8. Final checkpoint - 全テスト通過を確認
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- タスクは `*` 付きのものはオプション（プロパティテスト）でスキップ可能
- 各タスクは要件番号で追跡可能
- チェックポイントで段階的に動作確認を行う
- プロパティテストは hypothesis を使用
