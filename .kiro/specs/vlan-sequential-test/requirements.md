# Requirements Document

## Introduction

店舗ネットワークテスト自動化ツールのウィザードおよびテスト実行フローを変更する。
現在の3ステップ構成（店舗コード入力 → VLAN種別選択 → WAN経路選択）から、VLAN種別の選択ステップを削除し、全VLAN種別（店舗・POS・公共）を順次テストする方式に変更する。

現行フロー:
1. 店舗コード入力
2. VLAN種別選択（1つ選ぶ）
3. WAN経路選択（FTTH/LTE）
→ 選択した1つのVLAN種別に対してテスト実行

変更後フロー:
1. 店舗コード入力
2. WAN経路選択（FTTH/LTE）— 全VLANで共通
3. 「店舗VLANに接続してください。準備ができたら[Enter]」→ テスト実行
4. 「POS VLANに接続してください。準備ができたら[Enter]」→ テスト実行
5. 「公共VLANに接続してください。準備ができたら[Enter]」→ テスト実行

テスト結果は各VLANごとに個別の SuiteResult として記録される。
途中スキップは不可で、全VLAN種別のテストが必須となる。

## Glossary

- **Wizard**: `wizard.py` の `run_wizard()` 関数が提供する対話入力インターフェース
- **Store_Code**: 店舗を一意に識別する4桁の数字コード（正規表現 `[0-9]{4}`）
- **VLAN_Type**: ネットワークのVLAN種別。「店舗」「POS」「公共」の3種
- **VLAN_TYPES**: 順次テスト対象のVLAN種別リスト `["店舗", "POS", "公共"]`
- **WizardInput**: ウィザードの入力結果を保持するデータクラス（`models.py`）
- **SuiteResult**: テストスイート全体の結果を保持するデータクラス（`models.py`）
- **Runner**: テストスイートを実行し SuiteResult を構築するモジュール（`runner.py`）
- **Local_Reporter**: テスト結果をローカルJSONファイルに保存するモジュール（`reporters/local.py`）
- **Airtable_Reporter**: テスト結果をAirtable Webhookに投入するモジュール（`reporters/airtable.py`）
- **Sequential_Test_Flow**: 全VLAN種別を順番にテストする実行フロー。各VLANの切替前にユーザーに接続準備を促す

## Requirements

### Requirement 1: VLAN種別選択ステップの削除

**User Story:** As a テスト実施者, I want to VLAN種別を手動で選択する必要がない, so that 全VLANを漏れなくテストできる

#### Acceptance Criteria

1. THE Wizard SHALL VLAN種別の選択ステップを含まない
2. THE Wizard SHALL `VLAN_TYPE_CHOICES` 定数を削除する
3. THE WizardInput SHALL `vlan_type: str` フィールドを持たない

### Requirement 2: ウィザードの2ステップ構成への変更

**User Story:** As a テスト実施者, I want to 店舗コードとWAN経路だけを入力する, so that 入力ステップが簡潔になる

#### Acceptance Criteria

1. THE Wizard SHALL 店舗コード入力 → WAN経路選択 の2ステップで構成される
2. WHEN Wizard のステップ1が表示される, THE Wizard SHALL 「店舗コードを入力してください（4桁数字）:」というプロンプトを表示する
3. WHEN Wizard のステップ2が表示される, THE Wizard SHALL 「WAN経路を選択してください:」というプロンプトとともに「FTTH」「LTE」の2つの選択肢を表示する
4. THE WizardInput SHALL `store_code: str` フィールドと `wan_path: WANPath` フィールドのみを持つ

### Requirement 3: 確認サマリーの更新

**User Story:** As a テスト実施者, I want to 確認サマリーが2ステップの入力内容を表示する, so that テスト開始前に入力を確認できる

#### Acceptance Criteria

1. WHEN Wizard が確認サマリーを表示する, THE Wizard SHALL 「店舗コード」ラベルで store_code の値を表示する
2. WHEN Wizard が確認サマリーを表示する, THE Wizard SHALL 「WAN経路」ラベルで wan_path の値を表示する
3. WHEN Wizard が確認サマリーを表示する, THE Wizard SHALL 「VLAN種別」行を表示しない
4. WHEN Wizard が確認サマリーを表示する, THE Wizard SHALL 「テスト対象: 全VLAN（店舗・POS・公共）」という情報を表示する

### Requirement 4: 順次VLAN接続プロンプトの実装

**User Story:** As a テスト実施者, I want to 各VLANの接続切替タイミングで案内が表示される, so that 正しいVLANに接続してからテストを開始できる

#### Acceptance Criteria

1. WHEN 店舗VLANのテスト開始前, THE Runner SHALL 「店舗VLANに接続してください。準備ができたら[Enter]を押してください」というプロンプトを表示し、ユーザーのEnter入力を待つ
2. WHEN POS VLANのテスト開始前, THE Runner SHALL 「POS VLANに接続してください。準備ができたら[Enter]を押してください」というプロンプトを表示し、ユーザーのEnter入力を待つ
3. WHEN 公共VLANのテスト開始前, THE Runner SHALL 「公共VLANに接続してください。準備ができたら[Enter]を押してください」というプロンプトを表示し、ユーザーのEnter入力を待つ
4. THE Runner SHALL VLAN_TYPES の定義順（店舗 → POS → 公共）でテストを実行する
5. THE Runner SHALL 途中のVLANテストをスキップする手段を提供しない

### Requirement 5: 各VLANごとの個別SuiteResult記録

**User Story:** As a テスト実施者, I want to 各VLANのテスト結果が個別に記録される, so that VLAN別にテスト結果を確認・管理できる

#### Acceptance Criteria

1. WHEN Runner が全VLANのテストを完了する, THE Runner SHALL 3つの SuiteResult（店舗・POS・公共 各1つ）を返す
2. THE SuiteResult SHALL `vlan_type: str` フィールドを保持する（値は「店舗」「POS」「公共」のいずれか）
3. WHEN Runner が各VLANのテストを実行する, THE Runner SHALL 共通の WAN経路（WizardInput の wan_path）を使用する
4. THE Runner の `run_test_suite` 関数 SHALL 戻り値の型を `list[SuiteResult]` とする

### Requirement 6: main.py のフロー更新

**User Story:** As a 開発者, I want to main.py が順次テストフローに対応する, so that 全VLANのテスト結果が正しく処理される

#### Acceptance Criteria

1. WHEN main.py がテストスイートを実行する, THE main.py SHALL `run_test_suite` から返される `list[SuiteResult]` を受け取る
2. WHEN main.py が結果サマリーを表示する, THE main.py SHALL 全VLANの SuiteResult に対してサマリーを表示する
3. WHEN main.py が Airtable に結果を投入する, THE main.py SHALL 各 SuiteResult を個別に投入する
4. WHEN main.py が Airtable 投入結果を表示する, THE main.py SHALL 投入成功件数を「{成功数}/3 件」の形式で表示する

### Requirement 7: Local Reporter の複数結果対応

**User Story:** As a テスト実施者, I want to 各VLANのテスト結果が個別のJSONファイルに保存される, so that VLAN別にファイルを管理できる

#### Acceptance Criteria

1. WHEN Local_Reporter が SuiteResult を保存する, THE Local_Reporter SHALL ファイル名に `vlan_type` の値を含める
2. WHEN Local_Reporter が SuiteResult を辞書に変換する, THE Local_Reporter SHALL `vlan_type` キーを出力に含める

### Requirement 8: Airtable Reporter の複数結果対応

**User Story:** As a テスト実施者, I want to 各VLANのテスト結果が個別にAirtableに投入される, so that Airtable上でVLAN別にデータを管理できる

#### Acceptance Criteria

1. WHEN Airtable_Reporter が Webhook レコードを構築する, THE Airtable_Reporter SHALL `vlan_type` キーを出力に含める
2. WHEN main.py が Airtable に投入する, THE main.py SHALL 各 SuiteResult に対して `submit_results` を個別に呼び出す

### Requirement 9: 結果サマリー表示の更新

**User Story:** As a テスト実施者, I want to 全VLANのテスト結果サマリーがまとめて表示される, so that 全体の結果を一覧で確認できる

#### Acceptance Criteria

1. WHEN display_summary が呼び出される, THE Runner SHALL 各 SuiteResult のVLAN種別を見出しとして表示する
2. WHEN display_summary が呼び出される, THE Runner SHALL 引数として `list[SuiteResult]` を受け取る
3. WHEN display_summary が各VLANの結果を表示する, THE Runner SHALL WAN経路とVLAN種別の両方をヘッダーに含める

### Requirement 10: テストコードの更新

**User Story:** As a 開発者, I want to 既存テストが順次テストフローに対応する, so that テストスイートが正常に通過する

#### Acceptance Criteria

1. WHEN テストが SuiteResult を生成する, THE テストヘルパー SHALL `vlan_type` フィールドを含む SuiteResult を生成する
2. WHEN テストが `run_test_suite` の戻り値を検証する, THE テスト SHALL `list[SuiteResult]` 型の戻り値を期待する
3. WHEN テストが JSON 出力を検証する, THE テスト SHALL `vlan_type` キーの存在を検証する
