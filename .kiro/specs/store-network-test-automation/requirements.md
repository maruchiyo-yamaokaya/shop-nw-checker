# Requirements Document

## Introduction

店舗現場で通信環境（ネットワーク）を構築・変更した後に、各種ネットワークテストを自動実行するCLIツール。ジュニアNWエンジニアや現場作業員が、専門知識なしにワンコマンドで環境構築からテスト実行・結果投入までを完結できることを目的とする。GitHubからのクローン、Python環境（uv）のセットアップ、ウィザード形式の対話入力、テスト結果のクラウド（Airtable）投入を一連の流れで提供する。インターネット接続が必須の前提とする。テスト内容は名前解決（DNS resolution）、NW到達性（ping等の接続テスト）、安定性（パケットロス、ジッター等）の3種類に絞り、「小さく始めて、賢く構築する」方針に従う。

## Glossary

- **Test_Tool**: 店舗ネットワークテスト自動化ツール本体。環境構築・テスト実行・結果投入を行うシステム
- **Operator**: 店舗現場でネットワーク構築・変更作業を行い、本ツールを使用する作業者（ジュニアNWエンジニア、現場作業員）
- **Bootstrap_Script**: ワンコマンドで実行環境の構築（GitHubクローン、uv環境セットアップ、依存インストール）を行うスクリプト
- **Setup_Wizard**: Operatorに対して店舗名・NW領域・VLAN等の情報をステップバイステップで入力させる対話型インターフェース
- **Test_Suite**: 1回のテスト実行で行われるテスト項目の集合
- **Test_Result**: 各テスト項目の実行結果（合格/不合格/警告を含む）
- **Test_Profile**: 店舗タイプや用途に応じたテスト項目・閾値の設定テンプレート
- **Cloud_Reporter**: テスト結果をAirtable等のクラウドサービスに投入するコンポーネント
- **Connectivity_Test**: 指定されたホストへのネットワーク到達性を確認するテスト（ping、DNS解決など）
- **Stability_Test**: 一定期間にわたるパケットロス率、ジッター、接続の安定性を測定するテスト
- **NW_Area**: テスト対象のネットワーク領域（例: バックヤード、客席、POS周辺など）
- **VLAN**: 店舗内の論理ネットワーク区分。店舗には複数のVLANが存在し、テスト実施時にどのVLANに接続しているかを識別するために使用する
- **WAN_Path**: 店舗から外部ネットワークへの接続経路。FTTHとLTEの2種類が存在する
- **FTTH**: 光回線による外部接続経路（主回線）
- **LTE**: モバイル回線による外部接続経路（副回線/バックアップ）
- **Supported_Platform**: Test_Toolが動作対象とするOS。Windows、macOS、Linuxの3プラットフォームを指す

## Requirements

### Requirement 1: ワンコマンド環境構築

**User Story:** As an Operator, I want to 1つのコマンドを実行するだけで環境構築からツール起動までを完了したい, so that 専門知識がなくてもすぐにテストを開始できる。

#### Acceptance Criteria

1. WHEN the Operator executes the Bootstrap_Script, THE Bootstrap_Script SHALL clone the tool repository from GitHub.
2. WHEN the repository clone completes, THE Bootstrap_Script SHALL install uv and set up the Python virtual environment.
3. WHEN the Python environment setup completes, THE Bootstrap_Script SHALL install all required dependencies using uv.
4. WHEN all dependencies are installed, THE Bootstrap_Script SHALL launch the Test_Tool automatically.
5. IF the Operator executes the Bootstrap_Script and the repository already exists locally, THEN THE Bootstrap_Script SHALL pull the latest changes instead of cloning.
6. IF GitHub or the internet is unreachable, THEN THE Bootstrap_Script SHALL display an error message stating that internet connectivity is required.
7. IF uv installation fails, THEN THE Bootstrap_Script SHALL display a descriptive error message with the failure reason.

### Requirement 2: ウィザード形式の対話入力

**User Story:** As an Operator, I want to ウィザード形式で店舗名・NW領域・VLAN・WAN経路を順番に入力したい, so that 入力ミスなく必要な情報を漏れなく設定できる。

#### Acceptance Criteria

1. WHEN the Test_Tool starts, THE Setup_Wizard SHALL prompt the Operator for the store name as the first step.
2. WHEN the store name is entered, THE Setup_Wizard SHALL prompt the Operator to select the NW_Area from a predefined list.
3. WHEN the NW_Area is selected, THE Setup_Wizard SHALL prompt the Operator to enter or select the VLAN identifier for the network segment being tested.
4. WHEN the VLAN is entered, THE Setup_Wizard SHALL prompt the Operator to select the WAN_Path to test from the following options: FTTH only, LTE only, or both (FTTH and LTE).
5. WHEN the WAN_Path is selected, THE Setup_Wizard SHALL prompt the Operator to select a Test_Profile from available profiles.
6. WHEN all required inputs are collected, THE Setup_Wizard SHALL display a confirmation summary including store name, NW_Area, VLAN, WAN_Path, and Test_Profile, and ask the Operator to confirm before proceeding.
7. IF the Operator rejects the confirmation, THEN THE Setup_Wizard SHALL restart the input process from the first step.
8. THE Setup_Wizard SHALL validate each input at the time of entry and display a clear error message for invalid inputs.
9. THE Setup_Wizard SHALL provide default values for optional inputs to minimize the number of decisions the Operator must make.
10. THE Setup_Wizard SHALL default the WAN_Path selection to "both" (FTTH and LTE) to encourage comprehensive testing.

### Requirement 3: テストスイートの実行

**User Story:** As an Operator, I want to ウィザード入力完了後にテストスイートを自動実行したい, so that 追加操作なしでネットワーク品質を検証できる。

#### Acceptance Criteria

1. WHEN the Operator confirms the wizard inputs, THE Test_Tool SHALL execute all test items defined in the selected Test_Profile sequentially for each WAN_Path selected by the Operator.
2. WHEN the Operator selects "both" WAN_Paths, THE Test_Tool SHALL execute the full Test_Suite first on the FTTH path, then on the LTE path.
3. WHEN a test item completes, THE Test_Tool SHALL record the Test_Result with a timestamp, test item name, WAN_Path, and pass/fail/warning status.
4. WHEN a test item starts, THE Test_Tool SHALL display the test item name, the current WAN_Path, and a progress indicator to the Operator.
5. IF a test item fails to execute due to a system error, THEN THE Test_Tool SHALL log the error, skip the failed test item, and continue executing the remaining test items.
6. WHEN all test items complete for all selected WAN_Paths, THE Test_Tool SHALL display a summary of results to the console including overall status per WAN_Path and count of passed/failed/warning items.

### Requirement 4: 接続テスト

**User Story:** As an Operator, I want to 指定したホストへのネットワーク接続性を自動で確認したい, so that 基本的なネットワーク到達性の問題を素早く検出できる。

#### Acceptance Criteria

1. WHEN a Connectivity_Test is executed for a given WAN_Path, THE Test_Tool SHALL send ICMP ping requests to each target host defined in the Test_Profile via that WAN_Path.
2. WHEN a Connectivity_Test is executed for a given WAN_Path, THE Test_Tool SHALL perform DNS resolution for each target hostname defined in the Test_Profile via that WAN_Path.
3. WHEN a target host responds to ping within the threshold defined in the Test_Profile, THE Test_Tool SHALL mark the Connectivity_Test for that host and WAN_Path as "pass".
4. WHEN a target host does not respond to ping within the threshold defined in the Test_Profile, THE Test_Tool SHALL mark the Connectivity_Test for that host and WAN_Path as "fail".
5. IF DNS resolution fails for a target hostname, THEN THE Test_Tool SHALL mark the DNS test for that hostname and WAN_Path as "fail" and include the error detail in the Test_Result.

### Requirement 5: 安定性テスト

**User Story:** As an Operator, I want to 一定期間のネットワーク安定性を自動測定したい, so that 断続的な接続問題やパケットロスを検出できる。

#### Acceptance Criteria

1. WHEN a Stability_Test is executed for a given WAN_Path, THE Test_Tool SHALL send continuous ping requests to the target host via that WAN_Path for the duration defined in the Test_Profile.
2. WHEN a Stability_Test completes, THE Test_Tool SHALL calculate and record the packet loss rate as a percentage for the tested WAN_Path.
3. WHEN a Stability_Test completes, THE Test_Tool SHALL calculate and record the jitter value in milliseconds for the tested WAN_Path.
4. WHEN the packet loss rate exceeds the maximum threshold defined in the Test_Profile, THE Test_Tool SHALL mark the stability test for that WAN_Path as "fail".
5. WHEN the jitter value exceeds the maximum threshold defined in the Test_Profile, THE Test_Tool SHALL mark the stability test for that WAN_Path as "fail".

### Requirement 6: テスト結果のクラウド投入

**User Story:** As an Operator, I want to テスト結果がクラウド（Airtable）に自動投入されるようにしたい, so that 手動でのデータ転記作業を省き、結果を即座にチームで共有できる。

#### Acceptance Criteria

1. WHEN all test items in the Test_Suite complete, THE Cloud_Reporter SHALL send the Test_Results to the configured Airtable base.
2. THE Cloud_Reporter SHALL include the following fields in each Airtable record: store name, NW_Area, VLAN, WAN_Path, execution timestamp, Test_Profile name, overall pass/fail status, and individual Test_Results.
3. WHEN the Operator selects multiple WAN_Paths, THE Cloud_Reporter SHALL create separate Airtable records for each WAN_Path's Test_Results.
4. IF the Airtable API returns an error, THEN THE Cloud_Reporter SHALL retry the request up to 3 times with exponential backoff.
5. IF all retry attempts fail, THEN THE Cloud_Reporter SHALL save the Test_Results to a local JSON file as a fallback and display an error message to the Operator.
6. WHEN the Cloud_Reporter successfully submits results, THE Cloud_Reporter SHALL display a confirmation message with the Airtable record URL to the Operator.
7. THE Cloud_Reporter SHALL read the Airtable API key and base configuration from environment variables or a local configuration file.

### Requirement 7: テストプロファイル管理

**User Story:** As an Operator, I want to 店舗タイプや用途に応じたテストプロファイルを選択したい, so that 適切な閾値とテスト項目でテストを実行できる。

#### Acceptance Criteria

1. THE Test_Tool SHALL load Test_Profile definitions from a JSON configuration file bundled in the repository.
2. WHEN the Setup_Wizard presents Test_Profile options, THE Setup_Wizard SHALL display each profile's name and description.
3. IF the Test_Profile configuration file is missing or contains invalid JSON, THEN THE Test_Tool SHALL display a descriptive error message indicating the parse failure reason.
4. THE Test_Tool SHALL provide a default Test_Profile that includes Connectivity_Test and Stability_Test with standard thresholds.
5. FOR ALL valid Test_Profile JSON files, parsing then formatting then parsing SHALL produce an equivalent Test_Profile object (round-trip property).

### Requirement 8: インターネット接続の前提確認

**User Story:** As an Operator, I want to ツール起動時にインターネット接続が確認されるようにしたい, so that テスト実行中に接続不良で失敗することを事前に防げる。

#### Acceptance Criteria

1. WHEN the Test_Tool starts, THE Test_Tool SHALL verify internet connectivity before launching the Setup_Wizard.
2. IF internet connectivity is not available, THEN THE Test_Tool SHALL display an error message stating that internet connectivity is required and terminate gracefully.
3. WHEN internet connectivity is confirmed, THE Test_Tool SHALL proceed to the Setup_Wizard.

### Requirement 9: クロスプラットフォーム対応

**User Story:** As an Operator, I want to Windows・macOS・Linuxのいずれの環境でもツールを利用したい, so that 現場のPC環境に依存せずネットワークテストを実行できる。

#### Acceptance Criteria

1. THE Test_Tool SHALL operate on Windows, macOS, and Linux without requiring OS-specific modifications by the Operator.
2. THE Bootstrap_Script SHALL provide OS-independent execution by supplying both a shell script (for macOS/Linux) and a batch/PowerShell script (for Windows), or by using a Python-based bootstrap that runs on all Supported_Platforms.
3. THE Test_Tool SHALL use OS-independent path handling (forward slashes or platform-abstracted path APIs) for all file and directory operations.
4. WHEN a Connectivity_Test sends ICMP ping requests, THE Test_Tool SHALL use a cross-platform ping implementation (such as a Python library) instead of invoking OS-native ping commands directly.
5. WHEN a Stability_Test sends continuous ping requests, THE Test_Tool SHALL use the same cross-platform ping implementation to ensure consistent behavior across all Supported_Platforms.
6. THE Test_Tool SHALL use OS-independent methods for all network operations including DNS resolution.
7. IF the Test_Tool detects an unsupported operating system, THEN THE Test_Tool SHALL display an error message listing the Supported_Platforms and terminate gracefully.

### Requirement 10: 網羅テスト（Phase 2）

**User Story:** As an Operator, I want to 全VLANと全WAN経路の組み合わせを自動的にテストしたい, so that 個別に選択しなくても全パターンの網羅的な品質検証ができる。

#### Acceptance Criteria

1. [Phase 2] WHEN the Operator selects the comprehensive test mode, THE Test_Tool SHALL automatically enumerate all VLAN and WAN_Path combinations defined for the store.
2. [Phase 2] WHEN the comprehensive test starts, THE Test_Tool SHALL execute the full Test_Suite for each VLAN × WAN_Path combination sequentially.
3. [Phase 2] WHEN a VLAN × WAN_Path combination test completes, THE Test_Tool SHALL record the Test_Result with the specific VLAN and WAN_Path identifiers.
4. [Phase 2] WHEN all VLAN × WAN_Path combinations complete, THE Test_Tool SHALL display a matrix summary showing pass/fail status for each combination.
5. [Phase 2] WHEN all VLAN × WAN_Path combinations complete, THE Cloud_Reporter SHALL submit results for each combination as separate Airtable records.

### Requirement 11: フェイルオーバーテスト（Phase 2）

**User Story:** As an Operator, I want to FTTH⇔LTE間の回線切り替え時の動作を検証したい, so that 障害発生時のフェイルオーバーが正常に機能することを確認できる。

#### Acceptance Criteria

1. [Phase 2] WHEN the Operator selects the failover test mode, THE Test_Tool SHALL execute a failover test from FTTH to LTE.
2. [Phase 2] WHEN the Operator selects the failover test mode, THE Test_Tool SHALL execute a failover test from LTE to FTTH.
3. [Phase 2] WHEN a failover test is executed, THE Test_Tool SHALL measure and record the switchover time in milliseconds from the primary WAN_Path to the secondary WAN_Path.
4. [Phase 2] WHEN a failover test is executed, THE Test_Tool SHALL measure and record the packet loss count during the switchover period.
5. [Phase 2] WHEN a failover test completes, THE Test_Tool SHALL verify that connectivity is restored on the secondary WAN_Path by executing a Connectivity_Test.
6. [Phase 2] WHEN the switchover time exceeds the threshold defined in the Test_Profile, THE Test_Tool SHALL mark the failover test as "fail".
7. [Phase 2] WHEN the packet loss during switchover exceeds the threshold defined in the Test_Profile, THE Test_Tool SHALL mark the failover test as "warning".
8. [Phase 2] WHEN all failover tests complete, THE Test_Tool SHALL display a summary including switchover time, packet loss, and connectivity restoration status for each direction (FTTH→LTE, LTE→FTTH).
