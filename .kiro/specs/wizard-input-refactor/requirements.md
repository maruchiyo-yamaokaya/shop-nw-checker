# Requirements Document

## Introduction

店舗ネットワークテスト自動化ツールの Setup Wizard における対話入力の動作変更リファクタリング。
現在5ステップある対話入力のうち、質問1（店舗名の自由テキスト入力）を店舗コード（4桁数字 `[0-9]{4}`）の入力に変更し、質問2（NW領域の選択）をVLAN種別（店舗・POS・公共）の選択に変更する。
これに伴い、現在の質問3（VLAN自由テキスト入力）、質問2（NW領域選択）、質問5（テストプロファイル選択）は削除される。
また、WAN経路選択は「両方」オプションを廃止しFTTH/LTEの2択とする。
WAN経路選択は「両方」オプションを廃止しFTTH/LTEの2択とする。
ウィザードは3ステップ構成（店舗コード → VLAN種別 → WAN経路）となる。
データモデル・レポーター・テストランナーなど、影響を受ける全モジュールを整合的に更新する。

## Glossary

- **Wizard**: `wizard.py` の `run_wizard()` 関数が提供する対話入力インターフェース
- **Store_Code**: 店舗を一意に識別する4桁の数字コード（正規表現 `[0-9]{4}`）
- **VLAN_Type**: ネットワークのVLAN種別。「店舗」「POS」「公共」の3種から選択する列挙型
- **WizardInput**: ウィザードの入力結果を保持するデータクラス（`models.py`）
- **SuiteResult**: テストスイート全体の結果を保持するデータクラス（`models.py`）
- **Local_Reporter**: テスト結果をローカルJSONファイルに保存するモジュール（`reporters/local.py`）
- **Airtable_Reporter**: テスト結果をAirtable Webhookに投入するモジュール（`reporters/airtable.py`）
- **Runner**: テストスイートを実行しSuiteResultを構築するモジュール（`runner.py`）

## Requirements

### Requirement 1: 店舗コード入力への変更

**User Story:** As a テスト実施者, I want to 店舗コード（4桁数字）で店舗を指定する, so that 入力ミスを防ぎ店舗を一意に特定できる

#### Acceptance Criteria

1. WHEN Wizard のステップ1が表示される, THE Wizard SHALL 「店舗コードを入力してください（4桁数字）:」というプロンプトを表示する
2. WHEN テスト実施者が4桁の数字（`[0-9]{4}`）を入力する, THE Wizard SHALL 入力を受け付けて次のステップに進む
3. WHEN テスト実施者が4桁の数字以外の値を入力する, THE Wizard SHALL 「店舗コードは4桁の数字で入力してください（例: 0001）」というエラーメッセージを表示し再入力を求める
4. WHEN テスト実施者が空文字列を入力する, THE Wizard SHALL 「店舗コードは4桁の数字で入力してください（例: 0001）」というエラーメッセージを表示し再入力を求める
5. THE Wizard SHALL 入力された店舗コードの前後の空白を除去してから保存する

### Requirement 2: VLAN種別選択への変更

**User Story:** As a テスト実施者, I want to VLAN種別を選択肢から選ぶ, so that VLAN入力の手間とミスを減らせる

#### Acceptance Criteria

1. WHEN Wizard のステップ2が表示される, THE Wizard SHALL 「VLAN種別を選択してください:」というプロンプトとともに「店舗」「POS」「公共」の3つの選択肢を表示する
2. WHEN テスト実施者が選択肢から1つを選択する, THE Wizard SHALL 選択されたVLAN_Typeを保存して次のステップに進む
3. THE Wizard SHALL VLAN種別の選択に questionary.select を使用する

### Requirement 3: 不要な質問の削除とステップ簡素化

**User Story:** As a テスト実施者, I want to 不要になった質問が削除される, so that ウィザードの入力ステップが簡潔になる

#### Acceptance Criteria

1. THE Wizard SHALL NW領域の選択ステップ（旧ステップ2）を含まない
2. THE Wizard SHALL VLAN自由テキスト入力ステップ（旧ステップ3）を含まない
3. THE Wizard SHALL テストプロファイル選択ステップ（旧ステップ5）を含まない
4. THE Wizard SHALL 店舗コード入力 → VLAN種別選択 → WAN経路選択 の3ステップで構成される
5. THE Wizard SHALL テストプロファイルとして最初に読み込まれたプロファイルを自動的に使用する

### Requirement 4: WizardInput データモデルの更新

**User Story:** As a 開発者, I want to WizardInput のフィールドがリファクタリング後の入力に対応する, so that データの整合性が保たれる

#### Acceptance Criteria

1. THE WizardInput SHALL `store_name: str` フィールドの代わりに `store_code: str` フィールドを持つ
2. THE WizardInput SHALL `nw_area: str` フィールドを持たない
3. THE WizardInput SHALL `vlan: str` フィールドの代わりに `vlan_type: str` フィールドを持つ（値は「店舗」「POS」「公共」のいずれか）
4. THE WizardInput SHALL `wan_paths: list[WANPath]` フィールドの代わりに `wan_path: WANPath` フィールドを持つ（FTTHまたはLTEの単一値）
5. THE WizardInput SHALL `test_profile: str` フィールドを持たない

### Requirement 5: SuiteResult データモデルの更新

**User Story:** As a 開発者, I want to SuiteResult のフィールドがリファクタリング後の入力に対応する, so that テスト結果にリファクタリング後のデータが正しく記録される

#### Acceptance Criteria

1. THE SuiteResult SHALL `store_name: str` フィールドの代わりに `store_code: str` フィールドを持つ
2. THE SuiteResult SHALL `nw_area: str` フィールドを持たない
3. THE SuiteResult SHALL `vlan: str` フィールドの代わりに `vlan_type: str` フィールドを持つ

### Requirement 6: WAN経路選択の変更

**User Story:** As a テスト実施者, I want to WAN経路をFTTHまたはLTEの2択から選ぶ, so that テスト対象の経路を明確に指定できる

#### Acceptance Criteria

1. WHEN Wizard のステップ3が表示される, THE Wizard SHALL 「WAN経路を選択してください:」というプロンプトとともに「FTTH」「LTE」の2つの選択肢を表示する
2. THE Wizard SHALL 「両方（FTTH + LTE）」の選択肢を含まない
3. THE Wizard SHALL WAN経路の選択に questionary.select を使用する
4. THE Wizard SHALL 選択されたWAN経路を単一の `WANPath` 値として保存する

### Requirement 7: Runner モジュールの更新

**User Story:** As a 開発者, I want to Runner が更新後のフィールド名で SuiteResult を構築する, so that テスト実行結果が正しく記録される

#### Acceptance Criteria

1. WHEN Runner が SuiteResult を構築する, THE Runner SHALL WizardInput の `store_code` を SuiteResult の `store_code` に設定する
2. WHEN Runner が SuiteResult を構築する, THE Runner SHALL WizardInput の `vlan_type` を SuiteResult の `vlan_type` に設定する
3. THE Runner SHALL SuiteResult 構築時に `nw_area` フィールドを含めない
4. THE Runner SHALL WizardInput の `wan_path`（単一値）でテストスイートを実行する

### Requirement 8: Local Reporter の更新

**User Story:** As a テスト実施者, I want to ローカルJSON出力が更新後のフィールド名を使用する, so that 出力データが入力と一致する

#### Acceptance Criteria

1. WHEN Local_Reporter が SuiteResult を辞書に変換する, THE Local_Reporter SHALL `store_name` キーの代わりに `store_code` キーを出力する
2. WHEN Local_Reporter が SuiteResult を辞書に変換する, THE Local_Reporter SHALL `nw_area` キーを出力しない
3. WHEN Local_Reporter が SuiteResult を辞書に変換する, THE Local_Reporter SHALL `vlan` キーの代わりに `vlan_type` キーを出力する
4. WHEN Local_Reporter がファイル名を生成する, THE Local_Reporter SHALL `store_code` を使用する

### Requirement 9: Airtable Reporter の更新

**User Story:** As a テスト実施者, I want to Airtable Webhook送信データが更新後のフィールド名を使用する, so that Airtable側のデータが入力と一致する

#### Acceptance Criteria

1. WHEN Airtable_Reporter が Webhook レコードを構築する, THE Airtable_Reporter SHALL `store_name` キーの代わりに `store_code` キーを出力する
2. WHEN Airtable_Reporter が Webhook レコードを構築する, THE Airtable_Reporter SHALL `nw_area` キーを出力しない
3. WHEN Airtable_Reporter が Webhook レコードを構築する, THE Airtable_Reporter SHALL `vlan` キーの代わりに `vlan_type` キーを出力する

### Requirement 10: 確認サマリーの更新

**User Story:** As a テスト実施者, I want to 確認サマリーがリファクタリング後のフィールドを表示する, so that 入力内容を正しく確認できる

#### Acceptance Criteria

1. WHEN Wizard が確認サマリーを表示する, THE Wizard SHALL 「店舗コード」ラベルで store_code の値を表示する
2. WHEN Wizard が確認サマリーを表示する, THE Wizard SHALL 「NW領域」行を表示しない
3. WHEN Wizard が確認サマリーを表示する, THE Wizard SHALL 「VLAN種別」ラベルで vlan_type の値を表示する

### Requirement 11: バリデーション関数の更新

**User Story:** As a 開発者, I want to バリデーション関数がリファクタリング後の入力仕様に対応する, so that 不正な入力を正しく検出できる

#### Acceptance Criteria

1. THE Wizard SHALL `validate_store_code` 関数を提供し、入力が正規表現 `^[0-9]{4}$` に一致する場合のみ None を返す
2. WHEN `validate_store_code` に4桁数字以外の値が渡される, THE Wizard SHALL エラーメッセージを返す
3. THE Wizard SHALL `validate_store_name` 関数を削除する
4. THE Wizard SHALL `validate_vlan` 関数を削除する
5. THE Wizard SHALL `DEFAULT_NW_AREAS` 定数を削除する
6. THE Wizard SHALL `WAN_PATH_CHOICES` 定数を削除し、`_parse_wan_selection` 関数を削除する

### Requirement 12: テストコードの更新

**User Story:** As a 開発者, I want to 既存テストがリファクタリング後のフィールド名・構造に対応する, so that テストスイートが正常に通過する

#### Acceptance Criteria

1. WHEN テストが SuiteResult を生成する, THE テストヘルパー SHALL `store_code`、`vlan_type` フィールドを使用し、`store_name`、`nw_area`、`vlan` フィールドを使用しない
2. WHEN テストが JSON 出力を検証する, THE テスト SHALL `store_code`、`vlan_type` キーの存在を検証する
3. WHEN テストが Airtable レコードを検証する, THE テスト SHALL `store_code`、`vlan_type` キーの存在を検証する
