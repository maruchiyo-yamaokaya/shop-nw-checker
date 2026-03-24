# Requirements Document

## Introduction

店舗ネットワークテスト自動化ツールに2つの機能改善を追加する。

1. **VLAN IPアドレス記録**: 各VLANテスト実行時に、接続中のVLAN NICに割り当てられたローカルIPアドレスを取得し、テスト結果およびログに記録する。これにより、テスト実行時のネットワーク状態を事後に確認可能にする。

2. **安定性テスト高速化**: 現在約30秒かかる安定性テスト（stability test）を約5秒で完了するように高速化する。ping送信間隔を短縮し、送信回数を調整することで、テスト精度を維持しつつ実行時間を大幅に短縮する。

## Glossary

- **Runner**: テストスイート実行エンジン（`runner.py`）。VLAN種別ごとにテストを順次実行する
- **StabilityTest**: 安定性テストモジュール（`stability.py`）。継続的pingによるパケットロス率・ジッター計測を行う
- **TestResult**: 個別テスト結果を格納するデータモデル。`details`辞書にテスト固有の情報を保持する
- **SuiteResult**: テストスイート全体の結果を格納するデータモデル。複数のTestResultを保持する
- **LocalReporter**: ローカルJSONレポーター。SuiteResultをJSON形式でファイルに保存する
- **AirtableReporter**: Airtable Webhookレポーター。SuiteResultをWebhookに投入する
- **NetworkUtil**: ネットワークユーティリティモジュール（`network.py`）。IP取得等のヘルパー関数を提供する
- **StabilityConfig**: 安定性テスト設定データモデル。`duration_seconds`、`max_packet_loss_percent`、`max_jitter_ms`等を保持する
- **VLAN_NIC**: 各VLAN（店舗/POS/公共）に接続されたネットワークインターフェースカード

## Requirements

### Requirement 1: VLANテスト時のローカルIPアドレス取得

**User Story:** As a ネットワーク管理者, I want 各VLANテスト実行時に接続中NICのローカルIPアドレスを自動取得したい, so that テスト実行時のネットワーク状態を事後に確認できる

#### Acceptance Criteria

1. WHEN a VLAN test execution starts, THE NetworkUtil SHALL retrieve the local IP address assigned to the active network interface
2. IF the local IP address cannot be retrieved, THEN THE NetworkUtil SHALL return None and log a warning message instead of raising an exception

### Requirement 2: ローカルIPアドレスのテスト結果への記録

**User Story:** As a ネットワーク管理者, I want 取得したローカルIPアドレスをテスト結果に記録したい, so that レポートからテスト時のIP割り当て状況を確認できる

#### Acceptance Criteria

1. WHEN a VLAN test suite completes, THE SuiteResult SHALL contain the local IP address in a dedicated field
2. WHEN the local IP address is None, THE SuiteResult SHALL store None in the local IP address field without causing errors
3. WHEN the SuiteResult is serialized to JSON by the LocalReporter, THE LocalReporter SHALL include the `local_ip` field in the output
4. WHEN the SuiteResult is submitted by the AirtableReporter, THE AirtableReporter SHALL include the `local_ip` field in the webhook payload

### Requirement 3: ローカルIPアドレスのコンソール表示

**User Story:** As a テスト実行者, I want テスト開始時にコンソールで接続中のIPアドレスを確認したい, so that 正しいVLANに接続されていることを目視確認できる

#### Acceptance Criteria

1. WHEN a VLAN test execution starts, THE Runner SHALL display the retrieved local IP address on the console
2. WHEN the local IP address is None, THE Runner SHALL display a warning message indicating that the IP address could not be retrieved

### Requirement 4: 安定性テストの高速化

**User Story:** As a テスト実行者, I want 安定性テストを約5秒で完了させたい, so that 全体のテスト実行時間を短縮できる

#### Acceptance Criteria

1. THE StabilityConfig SHALL support a `ping_interval` field to configure the interval between ping packets in seconds
2. WHEN `ping_interval` is not specified in the profile, THE StabilityConfig SHALL default to 0.2 seconds
3. WHEN a stability test is executed with `duration_seconds` of 5 and `ping_interval` of 0.2, THE StabilityTest SHALL send approximately 25 ping packets within 5 seconds
4. THE StabilityTest SHALL use the `ping_interval` value from StabilityConfig as the interval parameter for icmplib ping calls

### Requirement 5: 安定性テストのデフォルトプロファイル更新

**User Story:** As a テスト実行者, I want デフォルトプロファイルの安定性テスト設定が高速化に対応していてほしい, so that 設定変更なしで高速テストを利用できる

#### Acceptance Criteria

1. THE default profile SHALL set `duration_seconds` to 5 for the stability test configuration
2. THE default profile SHALL set `ping_interval` to 0.2 for the stability test configuration
3. WHEN the default profile is loaded, THE StabilityConfig SHALL produce a configuration that completes the stability test within approximately 5 seconds
