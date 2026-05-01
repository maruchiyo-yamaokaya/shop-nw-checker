# Requirements Document

## Introduction

AWS VPC内に配置されたSSM Run Command対応のEC2プローブインスタンスを活用し、ローカルPC（店舗側）からboto3（AWS SDK for Python）を使って`ssm.send_command()`を発行し、VPC側から店舗ネットワークへの接続性を逆方向からチェックする機能を追加する。

現在のツールは「ローカルPC → 外部」の片方向テストのみ対応しているが、本機能により「AWS VPC → 店舗」の逆方向テストが可能となり、双方向のネットワーク接続性を検証できるようになる。

プローブインスタンス上でICMP pingコマンドを実行させ、その結果を取得・解析してTestResultとして返す。チェック対象は以下の2種類:
1. チェック端末（ローカルPC）へのICMP ping
2. 指定店舗に存在する名前付き端末（Route 53から動的取得）へのICMP ping

### Dependencies

このspecは `devops-agent-mcp-server` specが提供するEC2上のSSM Managed Instanceプローブを共有して利用する。本specはプローブインフラを所有せず、以下を親spec側に依存する:

- プローブEC2のプロビジョニングとライフサイクル管理
- SSM Agentのインストールおよび `AmazonSSMManagedInstanceCore` IAM権限
- プローブイメージ/AMIに含まれる必要バイナリ（`ping`）
- ICMP ping実行可能性の保証（セキュリティグループ egress、OSレベルでのICMP送信許可、`ping`バイナリのcapabilities設定）

本specが親spec側に追加で要求する事項（design.mdに記載すること）:

- 共有プローブを識別するタグ `NetCheckProbe=true` の付与（親spec側にspec変更要求として記録）
- セキュリティグループのegress設定: 店舗ネットワーク（社内VLAN範囲、IPsec/Magic WAN経由）への到達許可（ICMP含む）
- CloudWatch Log Groupの分離: 本spec実行分は `/aws/ssm/netcheck/` 配下に出力

また、store_code の取得は既存の `WizardInput.store_code`（ウィザードで入力済み）を使用する。

### 親spec `devops-agent-mcp-server` への変更要求事項

1. プローブEC2へのタグ追加: `NetCheckProbe=true`
2. プローブEC2のセキュリティグループのegress設定: 店舗ネットワーク（社内VLAN範囲、IPsec/Magic WAN経由）へのICMP到達許可を追加
3. プローブAMIへの必要バイナリ確認: `ping` の存在保証およびICMP送信capabilities設定
4. CloudWatch Log Group `/aws/ssm/netcheck/` の作成（または本spec側で作成する責務分担を決定）
5. Route 53 アクセス権限の不要性確認: 本specはRoute 53クエリをローカルPC側で実行するため、プローブEC2にはRoute 53アクセス権限を付与する必要がない

これら親spec側の変更が完了するまで、本specの実装は親spec側の現状実装に対して **追加変更を要求している状態** であることを明示する。

## Glossary

- **SSM_Client**: boto3のSSMクライアントを使用してSend Commandを実行し、結果を取得するTransport層モジュール
- **Output_Parser**: プローブ上のpingコマンド出力を構造化データ（パケットロス率、RTT統計）に変換するParse層モジュール。判定（Judge）は行わない
- **Probe_Instance**: AWS VPC内に配置された、タグ`NetCheckProbe=true`を持つSSM Run Command実行可能なEC2インスタンス
- **Reverse_Check**: VPC内のProbe_InstanceからローカルPC側（店舗ネットワーク）への接続性テスト
- **SSM_Probe_Config**: AWSリージョン、タイムアウト、ターゲットタグ、ドキュメント名などのSSMプローブ設定
- **Test_Runner**: テストスイートを順次実行するエンジン（既存のrunner.py）
- **Test_Profile**: テスト対象・閾値を定義するJSONプロファイル（既存のprofiles/default.json）
- **TestResult**: 個別テスト結果を表すデータクラス（既存のmodels.py）
- **Reverse_Check_Target**: プローブから店舗側へICMP pingチェックする対象の定義

## Requirements

### Requirement 1: SSMプローブ設定の管理

**User Story:** As a ネットワーク管理者, I want to プロファイルにSSMプローブの設定を定義する, so that プローブインスタンスの情報を一元管理できる。

#### Acceptance Criteria

1. THE Test_Profile SHALL プロファイルJSON内で `ssm_probe` をオプションのトップレベルキーとして受け付け、SSM_Probe_Configスキーマに沿ってパースする
2. THE SSM_Probe_Config SHALL `region`（AWSリージョン）、`timeout_seconds`（コマンド実行タイムアウト秒数、キュー待ち時間を含む）、`hosted_zone_domain`（Route 53のドメイン名、例: `yamaokaya.net`）、`local_network_ranges`（逆方向チェック実行条件となるローカルNWのアドレス範囲リスト、デフォルト: 192.168.2.0〜192.168.255.255）のフィールドを含む
3. THE SSM_Probe_Config SHALL `document_name` フィールドを持ち、デフォルト値は `AWS-RunShellScript` とする
4. THE SSM_Probe_Config SHALL `target_tag_key`（デフォルト: `NetCheckProbe`）および `target_tag_value`（デフォルト: `true`）フィールドを持ち、プローブ特定に使用するタグを設定可能とする
5. THE SSM_Probe_Config SHALL `hosted_zone_id`（オプション）フィールドを持ち、同名のHosted Zoneが複数存在する場合に直接指定可能とする
6. WHERE `ssm_probe`セクションが省略されている場合, THE Test_Profile SHALL 逆方向チェック機能を無効として扱い、既存テストに影響を与えない
7. WHEN `ssm_probe`セクションが存在するがフィールドが不足している場合, THE Test_Profile SHALL バリデーションエラーを報告する
8. THE Test_Profile SHALL 各VLAN定義内に `reverse_check_targets` 配列をオプションフィールドとして持つ。`reverse_check_targets` を持つVLANに対してのみ、当該VLANのテスト末尾で逆方向チェックを実行する
9. THE Test_Profile SHALL `local_network_ranges` のデフォルト値が `192.168.0.0/24` および `192.168.1.0/24` を意図的に除外していることをドキュメンテーションコメントとして記録する。除外理由: 家庭用ルーターのデフォルトIP範囲との衝突を避け、店舗LAN環境でのみ動作させるため

### Requirement 2: 逆方向チェック対象の定義

**User Story:** As a ネットワーク管理者, I want to プローブから店舗側へチェックする対象を定義する, so that 店舗ごとの構成に合わせたテストができる。

#### Acceptance Criteria

1. THE SSM_Client SHALL 逆方向チェックとして以下の2種類のICMP pingテストを実行する: (a) チェック端末（ローカルPC）のIPアドレスへのICMP ping、(b) 指定店舗の名前付き端末（Route 53から動的取得）へのICMP ping
2. THE SSM_Client SHALL チェック端末テストにおいて、ローカルPCの現在のIPアドレスをpingターゲットとして使用する。IPアドレス取得はデフォルトルートが向いているNICのIPアドレスを採用する（既存の`get_local_ip()`を使用）
3. THE SSM_Client SHALL Route 53へのクエリをローカルPC側でboto3経由で実行する（プローブEC2上では実行しない）
4. THE SSM_Client SHALL `route53:ListHostedZonesByName` を使い、`hosted_zone_domain` の値からHosted Zone IDを解決する。`hosted_zone_id` が SSM_Probe_Config で直接指定されている場合はそちらを優先する
5. THE SSM_Client SHALL 名前付き端末テストにおいて、Route 53のHosted Zoneから `*.s<store_code>.<hosted_zone_domain>` パターン（例: `rt.s1234.yamaokaya.net`）に一致するレコードを列挙し、各レコードのホスト名をpingターゲットとして使用する
6. THE SSM_Client SHALL store_code を既存の `WizardInput.store_code`（ウィザードで入力済み）から取得する
7. THE SSM_Client SHALL Route 53から取得したレコードリストをテストスイート実行内でキャッシュし、同一store_codeに対する重複クエリを避ける
8. WHEN Route 53からレコードが取得できない場合, THE SSM_Client SHALL WARNING状態のTestResultを返し、名前付き端末テストをスキップする
9. THE Reverse_Check_Target SHALL `target_kind`（"local_pc" | "named_terminal"）、`count`（ping回数、デフォルト5）、`loss_threshold_percent`（許容パケットロス率、デフォルト20）のフィールドを含む。`target`フィールドは`target_kind`に応じて動的に決定される: `local_pc`の場合は`get_local_ip()`の戻り値、`named_terminal`の場合はRoute 53から取得した各レコード名

### Requirement 3: boto3前提条件とIAM権限の確認

**User Story:** As a テスト実行者, I want to SSMコマンド実行前にboto3の利用可否と認証状態を確認する, so that 実行環境の問題を早期に検出できる。

#### Acceptance Criteria

1. WHEN 逆方向チェックが有効な場合, THE SSM_Client SHALL テスト実行前にboto3がインポート可能か確認する
2. IF boto3がインストールされていない場合, THEN THE SSM_Client SHALL エラーメッセージを表示し、逆方向チェックをスキップする
3. WHEN 逆方向チェックが有効な場合, THE SSM_Client SHALL テスト実行前にboto3セッションでAWS認証情報が有効か確認する（STS get-caller-identity）
4. IF AWS認証情報が無効または期限切れの場合, THEN THE SSM_Client SHALL エラーメッセージを表示し、逆方向チェックをスキップする
5. THE SSM_Client SHALL 実行に以下のIAM権限を必要とする: `ssm:SendCommand`（リソース: タグ `NetCheckProbe=true` のEC2）、`ssm:GetCommandInvocation`、`ssm:ListCommandInvocations`、`sts:GetCallerIdentity`、`route53:ListHostedZonesByName`、`route53:ListResourceRecordSets`、`logs:DescribeLogStreams`、`logs:GetLogEvents`（CloudWatch出力使用時）

### Requirement 4: SSM Send Commandの実行

**User Story:** As a テスト実行者, I want to ローカルPCからSSM Send Commandを発行してプローブ上でICMP pingを実行する, so that VPC側から店舗ネットワークへの接続性を検証できる。

#### Acceptance Criteria

1. WHEN 逆方向チェックが実行される場合, THE SSM_Client SHALL boto3の`ssm.send_command()`をTargets=[{"Key":"tag:<target_tag_key>","Values":["<target_tag_value>"]}]で呼び出し、該当する全プローブインスタンスにコマンドを送信する
2. THE SSM_Client SHALL コマンド結果取得に `ssm.get_command_invocation()` を使用する。出力が24,000文字を超える可能性がある場合、`CloudWatchOutputConfig` で `/aws/ssm/netcheck/` に出力し、CloudWatch Logsから取得する
3. WHEN 複数のプローブインスタンスがタグに一致する場合, THE SSM_Client SHALL send_commandにより全インスタンスで並列実行し、各インスタンスの結果を個別にTestResultとして返す
4. THE SSM_Client SHALL 各TestResultのdetailsにプローブのインスタンスIDを含め、どのプローブからの結果か識別可能にする
5. WHILE コマンドが実行中の場合, THE SSM_Client SHALL ポーリングにより完了を待機する
6. THE SSM_Client SHALL `timeout_seconds` をキュー待ち時間を含めた総時間として扱う。WHEN プローブ上で他のSSMコマンドが実行中の場合、send_commandの応答を待ってから次の処理に進む
7. THE SSM_Client SHALL `get_command_invocation` の Status を以下のようにTestResultへ変換する: `Success`(ResponseCode=0)はOutput_Parserに処理を委譲、`Success`(ResponseCode≠0)/`Failed`はコマンド実行失敗としてFAIL（StandardErrorContentをdetailsに含める）、`TimedOut`/`DeliveryTimedOut`/`ExecutionTimedOut`はタイムアウトとしてERROR、`Cancelled`はキャンセルとしてERROR
8. IF コマンド送信から `timeout_seconds` を超えても完了しない場合、またはプローブのSSM Agentが応答しない場合, THEN THE SSM_Client SHALL タイムアウトエラーとしてTestResultを返す
9. IF SSM APIがエラーを返した場合（ClientError等）, THEN THE SSM_Client SHALL エラー内容を含むTestResultを返す
10. THE SSM_Client SHALL boto3セッション作成時にSSM_Probe_Configのregionを使用する
11. THE SSM_Client SHALL send_command時にSSM_Probe_Configの`document_name`を`DocumentName`パラメータとして使用する
12. WHEN `send_command` がタグマッチで0インスタンスを対象とした場合（`list_command_invocations`の結果が空）, THE SSM_Client SHALL 「プローブインスタンスが見つからない」旨のERROR状態のTestResultを返す
13. THE SSM_Client SHALL コマンド実行のタイムアウトまたはエラー発生時、自動リトライは行わない。各テスト実行は1回のみ試行する

### Requirement 5: コマンド実行結果の解析

**User Story:** As a テスト実行者, I want to プローブ上で実行されたpingコマンドの結果を解析する, so that 逆方向チェックの結果を既存テストと同じ形式で確認できる。

#### Acceptance Criteria

1. THE Output_Parser SHALL pingコマンド出力からパケットロス率（パーセント値）およびRTT統計（min/avg/max）を構造化データとして抽出する
2. THE Test_Runner SHALL 抽出されたパケットロス率をReverse_Check_Targetの `loss_threshold_percent` と比較し、閾値以下をPASS、超過をFAILと判定する
3. IF コマンド出力の解析に失敗した場合, THEN THE Output_Parser SHALL ERROR状態のTestResultを返し、生の出力をdetailsに含める

### Requirement 6: テストランナーへの統合

**User Story:** As a テスト実行者, I want to 逆方向チェックが既存のテストフローに統合される, so that 全テスト結果を一括で確認・レポートできる。

#### Acceptance Criteria

1. WHEN 特定VLANテストにおいて `reverse_check_targets` が定義されている場合, THE Test_Runner SHALL 当該VLANテストの最後に逆方向チェックを実行する
2. WHERE VLANテストに `reverse_check_targets` が未定義、または `ssm_probe` セクションが未定義の場合, THE Test_Runner SHALL 当該VLANに対する逆方向チェックをスキップする
3. THE Test_Runner SHALL 逆方向チェック実行前にローカルPCのIPアドレスを確認し、SSM_Probe_Configに定義された `local_network_ranges` のいずれかの範囲内にある場合のみ逆方向チェックを実行する（デフォルト: 192.168.2.0〜192.168.255.255）
4. WHERE ローカルPCのIPアドレスが `local_network_ranges` のいずれの範囲にも含まれない場合, THE Test_Runner SHALL 逆方向チェックをスキップし、その旨をコンソールに表示する
5. THE Test_Runner SHALL 各TestResultの名前を以下の形式とする: チェック端末テストは `reverse_ping_localpc@<instance_id>`、名前付き端末テストは `reverse_ping_<hostname>@<instance_id>`（hostnameはRoute 53から取得したFQDN）
6. THE Test_Runner SHALL 同一ターゲットに対する複数プローブからの結果を、各プローブごとに独立したTestResultとしてSuiteResultに追加する
7. THE Test_Runner SHALL 集約判定（all_pass / any_pass）はレポート層の責務とし、本仕様では個別結果の保持のみを行う
8. IF 逆方向チェックでシステムエラーが発生した場合, THEN THE Test_Runner SHALL エラーをログ出力し、次のテストに進む
9. THE Test_Runner SHALL 逆方向チェック実行時にコンソールに進捗状況を表示する

### Requirement 7: コマンド出力パーサー

**User Story:** As a 開発者, I want to プローブ上のpingコマンド出力を構造化データに変換する, so that テスト結果の判定を正確に行える。

#### Acceptance Criteria

1. THE Output_Parser SHALL pingコマンド出力からパケットロス率（パーセント値）およびRTT統計（min/avg/max/mdev）を抽出するパーサーを持つ
2. THE Output_Parser SHALL パース結果をコマンド出力文字列に戻せるフォーマッターを持つ
3. THE Output_Parser SHALL すべての有効なpingコマンド出力文字列について、parse結果の判定に使用するフィールド（loss率、RTT平均値）に限り、parse → format → parse の結果が初回parse結果と等価である性質を満たす（ラウンドトリップ特性）

### Requirement 8: ロギング

**User Story:** As a 運用者, I want to 逆方向チェックの実行履歴を追跡可能にする, so that 問題発生時に原因調査ができる。

#### Acceptance Criteria

1. THE SSM_Client SHALL 各コマンド実行時にCommandId、対象インスタンスID、実行コマンド本体をログ出力する
2. THE SSM_Client SHALL コマンド完了時に実行結果（成功/失敗）、出力サマリーをログ出力する
3. THE SSM_Client SHALL タイムアウトまたはエラー発生時に詳細なエラー情報をログ出力する

### Requirement 9: セキュリティ

**User Story:** As a セキュリティ管理者, I want to プローブ上で実行されるコマンドが制限される, so that 任意のシェル実行を防止できる。

#### Acceptance Criteria

1. THE SSM_Client SHALL コマンド構築をホワイトリスト方式とし、ICMP pingコマンド（`ping -c <count> <target>`）のテンプレートのみを使用する
2. THE SSM_Client SHALL ユーザー入力値（target等）をコマンドに埋め込む際、シェルインジェクションを防止するバリデーションを行う（IPアドレスまたはFQDN形式のみ許可）
3. THE SSM_Client SHALL 許可されたコマンド以外の実行を拒否する
