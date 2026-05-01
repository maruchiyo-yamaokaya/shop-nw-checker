# 実装計画: SSMプローブ逆方向チェック

## 概要

AWS VPC内のEC2プローブからSSM Run Commandで店舗側へICMP pingを実行する逆方向チェック機能を、3層アーキテクチャ（Transport層・Parse層・Judge層）で実装する。依存関係を考慮し、データモデル → プロファイルパース → Output_Parser → SSM_Client → Runner統合 の順で段階的に構築する。

## タスク

- [ ] 1. データモデル追加とプロファイルパース拡張
  - [x] 1.1 `models.py` に `SSMProbeConfig`・`ReverseCheckTarget`・`PingResult`・`SSMCommandResult` データクラスを追加する
    - `SSMProbeConfig`: region, timeout_seconds, hosted_zone_domain, local_network_ranges, document_name(デフォルト), target_tag_key(デフォルト), target_tag_value(デフォルト), hosted_zone_id(オプション)
    - `ReverseCheckTarget`: target_kind("local_pc"|"named_terminal"), count(デフォルト5), loss_threshold_percent(デフォルト20.0)
    - `PingResult`: packets_transmitted, packets_received, packet_loss_percent, rtt_min_ms, rtt_avg_ms, rtt_max_ms, rtt_mdev_ms（RTT系はNone許容）
    - `SSMCommandResult`: instance_id, status, response_code, stdout, stderr
    - `VlanTestConfig` に `reverse_check_targets: list[ReverseCheckTarget] | None = None` フィールドを追加（後方互換性維持）
    - `TestProfile` に `ssm_probe: SSMProbeConfig | None = None` フィールドを追加（後方互換性維持）
    - `local_network_ranges` のデフォルト値が `192.168.0.0/24` および `192.168.1.0/24` を意図的に除外している理由をドキュメンテーションコメントとして記録する
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.8, 1.9, 2.9, 5.1_

  - [x] 1.2 `profile.py` に `parse_ssm_probe_config`・`ssm_probe_config_to_dict`・`validate_ssm_probe_config` 関数を追加し、`parse_profile`・`profile_to_dict`・`validate_profile` を拡張する
    - `parse_ssm_probe_config`: ssm_probeセクション辞書 → SSMProbeConfig変換。デフォルト値の適用（document_name, target_tag_key, target_tag_value）
    - `ssm_probe_config_to_dict`: SSMProbeConfig → 辞書変換
    - `validate_ssm_probe_config`: 必須フィールド（region, timeout_seconds, hosted_zone_domain）の存在確認、local_network_rangesの形式チェック
    - `parse_profile` 拡張: `ssm_probe` キー存在時にパース、`vlan_tests` 内の `reverse_check_targets` パース
    - `profile_to_dict` 拡張: ssm_probe / reverse_check_targets の直列化
    - `validate_profile` 拡張: ssm_probeセクション存在時のバリデーション、フィールド不足時のエラー報告
    - ssm_probeセクション省略時は既存テストに影響を与えないこと（Req 1.6）
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_

  - [ ]* 1.3 `tests/test_profile.py` にSSMプローブ設定パース・バリデーションのユニットテストを追加する
    - ssm_probeセクションのパース正常系（Req 1.1）
    - ssm_probeデフォルト値の確認（Req 1.3, 1.4）
    - ssm_probeフィールド不足時のバリデーションエラー（Req 1.7）
    - ssm_probe省略時の後方互換性（Req 1.6）
    - reverse_check_targetsのパース（Req 1.8）
    - hosted_zone_id指定時のパース（Req 1.5）
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_

  - [ ]* 1.4 `tests/test_profile.py` にProperty 1（拡張TestProfileのラウンドトリップ）のプロパティベーステストを追加する
    - **Property 1: 拡張TestProfileのラウンドトリップ**
    - hypothesis の `st.builds` で `SSMProbeConfig`・`ReverseCheckTarget` を含む `TestProfile` を生成
    - `profile_to_dict` → `parse_profile` のラウンドトリップで等価性を検証
    - `@pytest.mark.property` マーカーを使用
    - **Validates: Requirements 1.1, 1.2, 1.5, 1.8, 2.9**

- [x] 2. チェックポイント - データモデルとプロファイルパースの確認
  - テストを実行し、既存テストが壊れていないこと、新規テストがパスすることを確認する
  - `uv run pytest tests/test_profile.py -v` で確認
  - 問題があればユーザーに質問する

- [ ] 3. Output_Parser（Parse層）の実装
  - [x] 3.1 `src/store_net_test/tests/ping_output_parser.py` を新規作成し、`parse_ping_output`・`format_ping_output` 関数を実装する
    - `parse_ping_output`: Linux pingコマンド標準出力をパースし `PingResult` を返す。パース失敗時は `ValueError` を raise
    - パケット統計行: `N packets transmitted, M received, X% packet loss, time Yms`
    - RTT統計行: `rtt min/avg/max/mdev = A/B/C/D ms`（全パケットロス時はRTT行なし → RTTフィールドはNone）
    - `format_ping_output`: `PingResult` → pingコマンド出力形式の文字列に変換（ラウンドトリップ検証用）
    - _Requirements: 5.1, 5.3, 7.1, 7.2, 7.3_

  - [ ]* 3.2 `tests/test_ping_output_parser.py` を新規作成し、Output_Parserのユニットテストを追加する
    - 正常なpingコマンド出力のパース（0%ロス、部分ロス）
    - 全パケットロス時のパース（RTT統計なし）
    - 不正な出力での `ValueError` 発生確認
    - `format_ping_output` の出力形式確認
    - _Requirements: 5.1, 5.3, 7.1, 7.2_

  - [ ]* 3.3 `tests/test_ping_output_parser.py` にProperty 2（pingコマンド出力のラウンドトリップ）のプロパティベーステストを追加する
    - **Property 2: pingコマンド出力のラウンドトリップ**
    - `@composite` で整合性の取れた `PingResult` を生成（transmitted >= received, loss率計算整合性, RTTはreceived>0時のみ）
    - `format_ping_output` → `parse_ping_output` のラウンドトリップで判定フィールド（packet_loss_percent, rtt_avg_ms）の等価性を検証
    - `@pytest.mark.property` マーカーを使用
    - **Validates: Requirements 5.1, 7.1, 7.2, 7.3**

- [x] 4. チェックポイント - Output_Parserの確認
  - テストを実行し、Output_Parserが正しく動作することを確認する
  - `uv run pytest tests/test_ping_output_parser.py -v` で確認
  - 問題があればユーザーに質問する

- [ ] 5. ユーティリティ関数とJudge層関数の実装
  - [x] 5.1 `src/store_net_test/utils/network.py` に `is_ip_in_ranges` 関数を追加する
    - Python標準ライブラリの `ipaddress` モジュールを使用
    - IPアドレスがCIDR範囲リストのいずれかに含まれるか判定
    - _Requirements: 6.3, 6.4_

  - [x] 5.2 `src/store_net_test/runner.py` に `evaluate_reverse_ping_status` 関数を追加する
    - パケットロス率 <= 閾値 → PASS、超過 → FAIL
    - _Requirements: 5.2_

  - [ ]* 5.3 `tests/test_network.py` に `is_ip_in_ranges` のユニットテストを追加する
    - 範囲内IP → True、範囲外IP → False
    - 空の範囲リスト → False
    - デフォルトlocal_network_ranges（192.168.2.0〜192.168.255.255）での判定確認
    - 192.168.0.x / 192.168.1.x が除外されることの確認
    - _Requirements: 6.3, 6.4_

  - [ ]* 5.4 `tests/test_runner.py` にProperty 3（パケットロス率の閾値判定）のプロパティベーステストを追加する
    - **Property 3: パケットロス率の閾値判定**
    - loss_percent（0〜100）と threshold（0〜100）の全組み合わせで判定が正しいことを検証
    - `@pytest.mark.property` マーカーを使用
    - **Validates: Requirements 5.2**

  - [ ]* 5.5 `tests/test_network.py` にProperty 4（IPアドレスのネットワーク範囲内判定）のプロパティベーステストを追加する
    - **Property 4: IPアドレスのネットワーク範囲内判定**
    - 任意のIPv4アドレスとCIDR範囲リストの組み合わせで `is_ip_in_ranges` の結果が `ipaddress` モジュールの直接計算と一致することを検証
    - `@pytest.mark.property` マーカーを使用
    - **Validates: Requirements 6.3, 6.4**

- [x] 6. チェックポイント - ユーティリティ関数とJudge層の確認
  - テストを実行し、ユーティリティ関数とJudge層が正しく動作することを確認する
  - `uv run pytest tests/test_network.py tests/test_runner.py -v` で確認
  - 問題があればユーザーに質問する

- [ ] 7. SSM_Client（Transport層）の実装
  - [x] 7.1 `pyproject.toml` に boto3 をオプション依存として追加する
    - `[project.optional-dependencies]` セクションに `ssm = ["boto3>=1.34"]` を追加
    - boto3は `ssm_probe` セクション存在時のみインポートし、未インストール時はエラーメッセージ表示 + スキップ
    - _Requirements: 3.1, 3.2_

  - [x] 7.2 `src/store_net_test/tests/ssm_probe.py` を新規作成し、SSM_Client Transport層を実装する
    - `check_boto3_available()`: boto3インポート可否確認
    - `check_aws_credentials(region)`: STS get-caller-identity で認証確認
    - `validate_ping_target(target)`: IPアドレスまたはFQDN形式のバリデーション（シェルインジェクション防止）
    - `build_ping_command(target, count)`: ホワイトリスト方式で `ping -c <count> <target>` コマンド構築
    - `filter_store_records(records, store_code, domain)`: `*.s<store_code>.<domain>` パターンフィルタリング
    - `resolve_hosted_zone_id(hosted_zone_domain, hosted_zone_id, region)`: Route 53 Hosted Zone ID解決
    - `list_store_dns_records(hosted_zone_id, store_code, hosted_zone_domain, region)`: Route 53レコード列挙
    - `send_ssm_ping_command(config, target, count)`: SSM Send Command発行 + ポーリング完了待機 + 結果取得
    - ポーリング戦略: 初期待機1秒、間隔2秒固定、`InvocationDoesNotExist` は最大5秒リトライ
    - CloudWatch Logs フォールバック: `StandardOutputContent` が24,000文字上限到達時のみ
    - ロギング: `logging.getLogger(__name__)` で INFO/WARNING/ERROR レベルのログ出力
    - 自動リトライなし（各テスト実行は1回のみ試行）
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10, 4.11, 4.12, 4.13, 8.1, 8.2, 8.3, 9.1, 9.2, 9.3_

  - [ ]* 7.3 `tests/test_ssm_probe.py` を新規作成し、SSM_Clientのユニットテストを追加する
    - boto3未インストール時のスキップ動作（`unittest.mock.patch` でImportErrorをシミュレート）
    - AWS認証情報無効時のスキップ動作（STSモック）
    - `validate_ping_target`: 有効IP/FQDN → True、シェルメタ文字含む → False
    - `build_ping_command`: 出力形式の確認
    - `filter_store_records`: パターンマッチ/非マッチの確認
    - `send_ssm_ping_command`: boto3クライアントをモックし、各SSMステータス（Success/Failed/TimedOut等）のTestResult変換を確認
    - 0インスタンス検出時のERROR TestResult
    - タイムアウト時のERROR TestResult
    - SSM APIエラー（ClientError）時のTestResult
    - Route 53 Hosted Zone ID解決（直接指定 / ListHostedZonesByName）
    - Route 53レコード取得失敗時のWARNING
    - ログ出力の確認（CommandId、InstanceId、コマンド本体）
    - _Requirements: 2.4, 2.5, 2.8, 3.1, 3.2, 3.3, 3.4, 4.1, 4.5, 4.7, 4.8, 4.9, 4.12, 4.13, 8.1, 8.2, 8.3, 9.1, 9.2_

  - [ ]* 7.4 `tests/test_ssm_probe.py` にProperty 5, 6, 7 のプロパティベーステストを追加する
    - **Property 5: pingコマンド構築のホワイトリスト制約**
    - 有効なターゲットとcount（正の整数）に対して `build_ping_command` の出力が常に `ping -c <count> <target>` 形式であることを検証
    - **Validates: Requirements 9.1, 9.3**
    - **Property 6: pingターゲットバリデーション**
    - 有効なIPv4アドレス形式 → True、シェルメタ文字含む文字列 → False を検証
    - **Validates: Requirements 9.2**
    - **Property 7: Route 53レコードのパターンフィルタリング**
    - 任意のstore_code（4桁数字）、domain、レコードリストに対して `filter_store_records` がパターン一致レコードのみを返すことを検証
    - **Validates: Requirements 2.5**
    - 全て `@pytest.mark.property` マーカーを使用

- [x] 8. チェックポイント - SSM_Clientの確認
  - テストを実行し、SSM_Clientが正しく動作することを確認する
  - `uv run pytest tests/test_ssm_probe.py -v` で確認
  - 問題があればユーザーに質問する

- [ ] 9. Runner統合（Judge層）とプロファイル更新
  - [x] 9.1 `src/store_net_test/runner.py` に逆方向チェック統合ロジックを追加する
    - `_should_run_reverse_check(profile, vlan_type, local_ip)`: 実行条件判定（ssm_probe存在 + reverse_check_targets存在 + local_ipがlocal_network_ranges内）
    - `_expand_reverse_check_targets(targets, local_ip, named_terminal_hosts)`: target_kindに応じて実ターゲットに展開
    - `_run_reverse_check(config, targets, store_code, local_ip, wan_path)`: 逆方向チェック実行メイン関数
      - Route 53から名前付き端末リスト取得（キャッシュ利用: `run_test_suite` ローカル変数 `dict[str, list[str]]`）
      - `_expand_reverse_check_targets` で実ターゲットに展開
      - 各ターゲットに対して `send_ssm_ping_command` 発行
      - `parse_ping_output` で結果解析（ValueError時はERROR TestResult化）
      - `evaluate_reverse_ping_status` で閾値判定
      - TestResult名: `reverse_ping_localpc@<instance_id>` / `reverse_ping_<hostname>@<instance_id>`
    - `_run_tests_for_wan_path` の各VLANテスト末尾に逆方向チェック呼び出しを追加
    - `run_test_suite` にRoute 53キャッシュ辞書を追加し `_run_reverse_check` に伝搬
    - `WizardInput.store_code` を `_run_reverse_check` に伝搬
    - boto3利用可否・AWS認証確認を逆方向チェック実行前に実施
    - エラー発生時はログ出力して次のテストに進む（既存パターン準拠）
    - コンソール進捗表示（richライブラリ使用）
    - _Requirements: 2.1, 2.2, 2.3, 2.6, 2.7, 2.8, 3.1, 3.2, 3.3, 3.4, 5.2, 5.3, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9_

  - [x] 9.2 `profiles/default.json` に `ssm_probe` セクションと `reverse_check_targets` を追加する
    - ssm_probe: region, timeout_seconds, hosted_zone_domain, local_network_ranges（デフォルト値）
    - vlan_tests内に reverse_check_targets: local_pc + named_terminal
    - _Requirements: 1.1, 1.2, 1.8, 2.9_

  - [x] 9.3 `pyproject.toml` の `[tool.pytest.ini_options]` に `markers = ["property: property-based tests"]` を追加する
    - プロパティベーステスト用の `@pytest.mark.property` マーカーを登録
    - 既存の `filterwarnings` 設定は維持

  - [ ]* 9.4 `tests/test_runner.py` に逆方向チェック統合のユニットテストを追加する
    - ssm_probe未定義時の逆方向チェックスキップ（Req 6.2）
    - reverse_check_targets未定義時のスキップ（Req 6.2）
    - ローカルIPがlocal_network_ranges外時のスキップ + コンソール表示（Req 6.4）
    - TestResult名の形式確認（Req 6.5）
    - 複数プローブの独立TestResult（Req 6.6）
    - 逆方向チェックエラー時の継続動作（Req 6.8）
    - コンソール進捗表示（Req 6.9）
    - boto3未インストール時のスキップ（Req 3.1, 3.2）
    - AWS認証無効時のスキップ（Req 3.3, 3.4）
    - Route 53キャッシュ動作（同一store_codeで重複クエリなし）（Req 2.7）
    - _Requirements: 2.7, 3.1, 3.2, 3.3, 3.4, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9_

- [x] 10. 最終チェックポイント - 全テスト実行
  - 全テストを実行し、既存テスト・新規テストが全てパスすることを確認する
  - `uv run pytest tests/ -v` で確認
  - プロパティベーステストのみ: `uv run pytest tests/ -v -m property` で確認
  - 問題があればユーザーに質問する

## 備考

- `*` マークのタスクはオプションであり、MVP実装時にはスキップ可能
- 各タスクは前のタスクの成果物に依存するため、順序通りに実行すること
- チェックポイントで既存テストの破壊がないことを確認すること
- プロパティベーステストは設計ドキュメントの Correctness Properties セクションに基づく
- boto3はオプション依存であり、未インストール環境でも既存テストは正常動作すること
- 親spec `devops-agent-mcp-server` への変更要求事項（タグ追加、SG設定等）は本specの実装範囲外
