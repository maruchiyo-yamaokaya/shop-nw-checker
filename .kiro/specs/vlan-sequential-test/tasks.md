# Implementation Plan: VLAN順次テスト

## Overview

ウィザードの3ステップ構成（店舗コード → VLAN種別選択 → WAN経路選択）を2ステップ（店舗コード → WAN経路）に簡素化し、全VLAN種別（店舗・POS・公共）を順次テストする方式に変更する。各モジュールを段階的に変更し、既存テストを更新する。

## Tasks

- [x] 1. models.py の WizardInput から vlan_type フィールドを削除
  - `WizardInput` dataclass から `vlan_type: str` フィールドを削除し、`store_code` と `wan_path` のみにする
  - _Requirements: 1.3, 2.4_

- [x] 2. wizard.py のVLAN種別選択ステップ削除と確認サマリー更新
  - [x] 2.1 VLAN種別選択ステップの削除
    - `VLAN_TYPE_CHOICES` 定数を削除する
    - `run_wizard()` からVLAN種別選択ステップ（ステップ2）を削除し、店舗コード → WAN経路の2ステップ構成にする
    - `WizardInput` 構築時に `vlan_type` 引数を削除する
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 2.3_
  - [x] 2.2 確認サマリーの更新
    - `_build_confirmation_text()` から「VLAN種別」行を削除し、「テスト対象: 全VLAN（店舗・POS・公共）」行を追加する
    - `display_confirmation()` のテーブルから「VLAN種別」行を削除し、「テスト対象」行を追加する
    - _Requirements: 3.1, 3.2, 3.3, 3.4_
  - [ ]* 2.3 Property 2 のプロパティベーステスト作成
    - **Property 2: 確認サマリーの内容が正しい**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4**

- [x] 3. runner.py の順次VLANテストフロー実装
  - [x] 3.1 VLAN_TYPES 定数と prompt_vlan_connection 関数の追加
    - モジュールレベルに `VLAN_TYPES: list[str] = ["店舗", "POS", "公共"]` 定数を定義する
    - `prompt_vlan_connection(vlan_type: str)` 関数を追加し、「{vlan_type}VLANに接続してください。準備ができたら[Enter]を押してください」プロンプトを表示して `input()` でEnter入力を待つ
    - _Requirements: 4.1, 4.2, 4.3, 4.5_
  - [x] 3.2 run_test_suite の戻り値を list[SuiteResult] に変更
    - `run_test_suite` 内で `VLAN_TYPES` をループし、各VLANに対して `prompt_vlan_connection` → `_run_tests_for_wan_path` を実行する
    - `_run_tests_for_wan_path` に `vlan_type` 引数を追加し、`SuiteResult` 構築時に `wizard_input.vlan_type` の代わりに引数の `vlan_type` を使用する
    - 戻り値の型を `list[SuiteResult]` に変更する
    - _Requirements: 4.4, 5.1, 5.2, 5.3, 5.4_
  - [x] 3.3 display_summary の引数を list[SuiteResult] に変更
    - 引数を `suite_results: list[SuiteResult]` に変更し、各 `SuiteResult` のVLAN種別を見出しとして表示する
    - 各VLANの結果ヘッダーにWAN経路とVLAN種別の両方を含める
    - _Requirements: 9.1, 9.2, 9.3_
  - [ ]* 3.4 Property 3 のプロパティベーステスト作成
    - **Property 3: run_test_suite は正しい順序・VLAN種別・WAN経路で3つのSuiteResultを返す**
    - **Validates: Requirements 4.4, 5.1, 5.3, 5.4**

- [x] 4. Checkpoint - 中間確認
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. reporters/local.py のファイル名に vlan_type を追加
  - [x] 5.1 save_results_to_json のファイル名フォーマット変更
    - ファイル名を `{日付}_{店舗コード}_{VLAN種別}_{WAN経路}.json` に変更する
    - _Requirements: 7.1, 7.2_
  - [ ]* 5.2 Property 4 のプロパティベーステスト作成
    - **Property 4: Local Reporter のファイル名に vlan_type が含まれる**
    - **Validates: Requirements 7.1**
  - [ ]* 5.3 Property 5 のプロパティベーステスト作成
    - **Property 5: レポーター出力に vlan_type が含まれる**
    - **Validates: Requirements 7.2, 8.1**

- [x] 6. main.py のフロー更新
  - `run_test_suite` の戻り値を `list[SuiteResult]` で受け取るように変更する
  - `display_summary` に `list[SuiteResult]` を渡すように変更する
  - Airtable投入を各 `SuiteResult` に対して個別に `submit_results` を呼び出すループに変更する
  - 投入結果を `{成功数}/3 件` の形式で表示する
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 8.2_

- [x] 7. 既存テストの更新
  - [x] 7.1 tests/test_reporter.py のテストヘルパー・テストケース更新
    - `_make_suite_result` ヘルパーが `vlan_type` フィールドを含む `SuiteResult` を生成することを確認する（既に対応済みの場合は変更不要）
    - `WizardInput` を使用しているテストがあれば `vlan_type` 引数を削除する
    - JSON出力テストで `vlan_type` キーの存在を検証する
    - _Requirements: 10.1, 10.2, 10.3_
  - [ ]* 7.2 Property 1 のプロパティベーステスト作成
    - **Property 1: WizardInput は store_code と wan_path のみを持つ**
    - **Validates: Requirements 1.3, 2.4**
  - [ ]* 7.3 Property 6 のプロパティベーステスト作成
    - **Property 6: display_summary の出力に WAN経路と VLAN種別が含まれる**
    - **Validates: Requirements 9.1, 9.3**

- [x] 8. Final checkpoint - 最終確認
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- タスクに `*` が付いているものはオプション（プロパティベーステスト）でスキップ可能
- 各タスクは要件への参照を含み、トレーサビリティを確保
- `reporters/airtable.py` は既に `vlan_type` 対応済みのため変更不要
- プロパティベーステストは hypothesis を使用（`pyproject.toml` に定義済み）
