# Requirements Document

## Introduction

店舗ネットワークテスト自動化ツールにおいて、VLAN種別ごとに異なる追加テストを実装する。
現在の共通テスト（DNS解決、Ping到達性、安定性）に加えて、各VLAN種別に固有のテストを追加する。

現行テストフロー（全VLAN共通）:
1. DNS解決テスト
2. Ping到達性テスト
3. 安定性テスト

変更後テストフロー:
1. DNS解決テスト（共通）
2. Ping到達性テスト（共通）
3. 安定性テスト（共通）
4. HTTPS疎通確認テスト（全VLAN共通追加）
5. VLAN種別固有テスト（店舗 / POS / 公共 それぞれ異なる）

VLAN種別固有テストの内容:
- 店舗VLAN: デフォルトゲートウェイDNS解決テスト、複合機ping疎通テスト、WhereAmI APIテスト
- POS VLAN: ローカル機材ping疎通テスト（券売機1〜3、DL）
- 公共VLAN: 内部NWリソースDNS解決不可テスト

## Glossary

- **Runner**: テストスイートを実行し SuiteResult を構築するモジュール（`runner.py`）
- **TestProfile**: テストプロファイル定義。テスト対象ホスト・閾値等を保持するデータクラス（`models.py`）
- **SuiteResult**: テストスイート全体の結果を保持するデータクラス（`models.py`）
- **TestResult**: 個別テスト結果を保持するデータクラス（`models.py`）
- **WizardInput**: ウィザードの入力結果を保持するデータクラス（`models.py`、`store_code` と `wan_path` を含む）
- **VLAN_Type**: ネットワークのVLAN種別。「店舗」「POS」「公共」の3種
- **HTTPS_Test**: 指定URLにHTTPSリクエストを送信し、ステータスコード200の応答を確認するテスト
- **Gateway_DNS_Test**: デフォルトゲートウェイIPをDNSサーバーとして使用し、特定ホスト名の名前解決結果を検証するテスト
- **WhereAmI_API_Test**: `https://api.yamaokaya.net/wb/whereami` にGETリクエストを送信し、レスポンスJSONの `shopCode` を検証するテスト
- **Private_IP**: RFC 1918で定義されたプライベートIPアドレス（10.0.0.0/8、172.16.0.0/12、192.168.0.0/16）
- **Default_Gateway**: システムのネットワーク設定から取得されるデフォルトゲートウェイのIPアドレス

## Requirements

### Requirement 1: HTTPS疎通確認テスト（全VLAN共通追加）

**User Story:** As a テスト実施者, I want to 全VLANでHTTPS疎通を確認する, so that インターネットへのHTTPS通信が正常であることを検証できる

#### Acceptance Criteria

1. WHEN Runner が任意のVLAN種別のテストを実行する, THE Runner SHALL 共通テスト（DNS、Ping、安定性）の後にHTTPS疎通確認テストを実行する
2. THE HTTPS_Test SHALL 以下の3つのURLに対してHTTPSリクエストを送信する: `https://www.google.com`、`https://www.cloudflare.com`、`https://www.amazon.co.jp`
3. WHEN HTTPS_Test が対象URLにリクエストを送信する, THE HTTPS_Test SHALL HTTPステータスコード200の応答を受信した場合にPASSと判定する
4. WHEN HTTPS_Test が対象URLからステータスコード200以外の応答を受信する, THE HTTPS_Test SHALL FAILと判定する
5. IF HTTPS_Test がリクエスト送信中に接続エラーまたはタイムアウトが発生する, THEN THE HTTPS_Test SHALL FAILと判定し、エラーメッセージをTestResultに記録する
6. THE HTTPS_Test SHALL 各URLに対して個別のTestResultを生成する
7. THE HTTPS_Test SHALL テスト対象URLリストをTestProfileから取得する

### Requirement 2: 店舗VLANデフォルトゲートウェイDNS解決テスト

**User Story:** As a テスト実施者, I want to 店舗VLANでデフォルトゲートウェイをDNSサーバーとして使用した名前解決を検証する, so that 店舗内DNSフィルタリングが正しく機能していることを確認できる

#### Acceptance Criteria

1. WHEN Runner が店舗VLANのテストを実行する, THE Runner SHALL デフォルトゲートウェイDNS解決テストを実行する
2. THE Gateway_DNS_Test SHALL システムのネットワーク設定からデフォルトゲートウェイIPアドレスをプログラム的に取得する
3. THE Gateway_DNS_Test SHALL 取得したデフォルトゲートウェイIPアドレスをDNSサーバーとして使用する
4. WHEN Gateway_DNS_Test が `api.yamaokaya.net` を解決する, THE Gateway_DNS_Test SHALL 解決結果がPrivate_IPであることを検証し、Private_IPに解決された場合にPASSと判定する
5. WHEN Gateway_DNS_Test が `nx.yamaokaya.net` を解決する, THE Gateway_DNS_Test SHALL 解決結果がPrivate_IPであることを検証し、Private_IPに解決された場合にPASSと判定する
6. WHEN Gateway_DNS_Test が `pornhub.com` を解決する, THE Gateway_DNS_Test SHALL 名前解決が失敗することを検証し、名前解決が失敗した場合にPASSと判定する
7. WHEN Gateway_DNS_Test が `yamaokaya.lightning.force.com` を解決する, THE Gateway_DNS_Test SHALL 名前解決が成功することを検証し、名前解決が成功した場合にPASSと判定する
8. IF Gateway_DNS_Test がデフォルトゲートウェイIPアドレスの取得に失敗する, THEN THE Gateway_DNS_Test SHALL FAILと判定し、エラーメッセージをTestResultに記録する
9. THE Gateway_DNS_Test SHALL 各ホスト名に対して個別のTestResultを生成する
10. THE Gateway_DNS_Test SHALL テスト対象ホスト名リストと期待される解決結果をTestProfileから取得する

### Requirement 3: 店舗VLAN複合機ping疎通テスト

**User Story:** As a テスト実施者, I want to 店舗VLANで複合機へのping疎通を確認する, so that 複合機がネットワーク上で到達可能であることを検証できる

#### Acceptance Criteria

1. WHEN Runner が店舗VLANのテストを実行する, THE Runner SHALL 複合機ping疎通テストを実行する
2. THE Runner SHALL `prn.myshop.yamaokaya.net` に対してICMP pingを送信する
3. WHEN ping応答を受信した場合, THE Runner SHALL PASSと判定する
4. WHEN ping応答を受信できない場合, THE Runner SHALL FAILと判定する
5. THE Runner SHALL 複合機のホスト名をTestProfileから取得する

### Requirement 4: 店舗VLAN WhereAmI APIテスト

**User Story:** As a テスト実施者, I want to 店舗VLANでWhereAmI APIの応答を検証する, so that 店舗ネットワークが正しい店舗に紐づいていることを確認できる

#### Acceptance Criteria

1. WHEN Runner が店舗VLANのテストを実行する, THE Runner SHALL WhereAmI APIテストを実行する
2. THE WhereAmI_API_Test SHALL `https://api.yamaokaya.net/wb/whereami` にHTTP GETリクエストを送信する
3. WHEN WhereAmI_API_Test がレスポンスを受信する, THE WhereAmI_API_Test SHALL レスポンスJSONの `shopCode` フィールドをWizardInputの `store_code`（整数として比較）と照合する
4. WHEN `shopCode` がWizardInputの `store_code` と一致する, THE WhereAmI_API_Test SHALL PASSと判定する
5. WHEN `shopCode` がWizardInputの `store_code` と一致しない, THE WhereAmI_API_Test SHALL FAILと判定し、期待値と実際の値をTestResultの詳細に記録する
6. IF WhereAmI_API_Test がリクエスト送信中に接続エラーまたはタイムアウトが発生する, THEN THE WhereAmI_API_Test SHALL FAILと判定し、エラーメッセージをTestResultに記録する
7. THE WhereAmI_API_Test SHALL APIエンドポイントURLをTestProfileから取得する

### Requirement 5: POS VLANローカル機材ping疎通テスト

**User Story:** As a テスト実施者, I want to POS VLANでローカル機材へのping疎通を確認する, so that 券売機およびDLがネットワーク上で到達可能であることを検証できる

#### Acceptance Criteria

1. WHEN Runner が POS VLANのテストを実行する, THE Runner SHALL ローカル機材ping疎通テストを実行する
2. THE Runner SHALL 以下の固定IPアドレスに対してICMP pingを送信する: 券売機1（192.168.1.81）、券売機2（192.168.1.82）、券売機3（192.168.1.83）、DL（192.168.1.110）
3. WHEN 各機材からping応答を受信した場合, THE Runner SHALL 当該機材のテストをPASSと判定する
4. WHEN 各機材からping応答を受信できない場合, THE Runner SHALL 当該機材のテストをFAILと判定する
5. THE Runner SHALL 各機材に対して個別のTestResultを生成する
6. THE Runner SHALL ローカル機材のIPアドレスリストと機材名をTestProfileから取得する

### Requirement 6: 公共VLAN内部NWリソースDNS解決不可テスト

**User Story:** As a テスト実施者, I want to 公共VLANで内部NWリソースが名前解決できないことを確認する, so that 公共VLANから内部ネットワークリソースへのアクセスが遮断されていることを検証できる

#### Acceptance Criteria

1. WHEN Runner が公共VLANのテストを実行する, THE Runner SHALL 内部NWリソースDNS解決不可テストを実行する
2. THE Runner SHALL `nx.yamaokaya.net` に対してDNS名前解決を試みる
3. WHEN `nx.yamaokaya.net` の名前解決が失敗する, THE Runner SHALL PASSと判定する
4. WHEN `nx.yamaokaya.net` の名前解決が成功する, THE Runner SHALL FAILと判定する
5. THE Runner SHALL テスト対象ホスト名をTestProfileから取得する

### Requirement 7: TestProfileへのVLAN種別固有テスト設定の追加

**User Story:** As a 開発者, I want to VLAN種別固有テストの設定をTestProfileで管理する, so that テスト対象ホスト・URL・IPアドレスを設定ファイルで変更できる

#### Acceptance Criteria

1. THE TestProfile SHALL HTTPS疎通確認テスト用のURLリストを保持するフィールドを持つ
2. THE TestProfile SHALL 店舗VLANゲートウェイDNSテスト用のホスト名リストと期待結果を保持するフィールドを持つ
3. THE TestProfile SHALL 店舗VLAN複合機ホスト名を保持するフィールドを持つ
4. THE TestProfile SHALL 店舗VLAN WhereAmI APIエンドポイントURLを保持するフィールドを持つ
5. THE TestProfile SHALL POS VLANローカル機材のIPアドレスリストと機材名を保持するフィールドを持つ
6. THE TestProfile SHALL 公共VLAN内部NWリソーステスト用のホスト名リストを保持するフィールドを持つ
7. THE profiles/default.json SHALL 上記全フィールドのデフォルト値を含む

### Requirement 8: VLAN種別に応じたテスト実行フローの拡張

**User Story:** As a 開発者, I want to Runner が VLAN種別に応じて追加テストを実行する, so that 各VLANに適切なテストが自動的に適用される

#### Acceptance Criteria

1. WHEN Runner が任意のVLAN種別のテストを実行する, THE Runner SHALL 共通テスト（DNS、Ping、安定性）の後にHTTPS疎通確認テストを実行する
2. WHEN Runner が店舗VLANのテストを実行する, THE Runner SHALL HTTPS疎通確認テストの後にデフォルトゲートウェイDNS解決テスト、複合機ping疎通テスト、WhereAmI APIテストを順次実行する
3. WHEN Runner が POS VLANのテストを実行する, THE Runner SHALL HTTPS疎通確認テストの後にローカル機材ping疎通テストを実行する
4. WHEN Runner が公共VLANのテストを実行する, THE Runner SHALL HTTPS疎通確認テストの後に内部NWリソースDNS解決不可テストを実行する
5. IF VLAN種別固有テストの個別テスト項目でエラーが発生する, THEN THE Runner SHALL 当該テスト項目をスキップして次のテスト項目に進む

### Requirement 9: デフォルトゲートウェイIPアドレスの取得

**User Story:** As a 開発者, I want to システムのネットワーク設定からデフォルトゲートウェイIPアドレスをプログラム的に取得する, so that 店舗VLANのDNSテストで使用できる

#### Acceptance Criteria

1. THE Runner SHALL ネットワークユーティリティモジュール（`utils/network.py`）を通じてデフォルトゲートウェイIPアドレスを取得する
2. THE ネットワークユーティリティ SHALL Windows環境とmacOS/Linux環境の両方でデフォルトゲートウェイIPアドレスを取得できる
3. IF デフォルトゲートウェイIPアドレスの取得に失敗する, THEN THE ネットワークユーティリティ SHALL Noneを返す

### Requirement 10: プライベートIPアドレス判定

**User Story:** As a 開発者, I want to IPアドレスがプライベートIPアドレスであるかを判定する, so that 店舗VLANのDNSテストで解決結果を検証できる

#### Acceptance Criteria

1. THE ネットワークユーティリティ SHALL 与えられたIPアドレス文字列がRFC 1918プライベートIPアドレス範囲（10.0.0.0/8、172.16.0.0/12、192.168.0.0/16）に含まれるかを判定する関数を提供する
2. WHEN プライベートIPアドレス範囲に含まれるIPアドレスが渡される, THE ネットワークユーティリティ SHALL Trueを返す
3. WHEN プライベートIPアドレス範囲に含まれないIPアドレスが渡される, THE ネットワークユーティリティ SHALL Falseを返す
