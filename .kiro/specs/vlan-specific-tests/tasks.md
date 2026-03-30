# 実装計画: VLAN種別固有テスト

## 概要

VLAN種別ごとの固有テストを追加する。コアデータモデル拡張 → ユーティリティ → テストモジュール → Runner統合の順で段階的に構築する。

## タスク

- [x] 1. コアデータモデルとプロファイル管理の拡張
  - [x] 1.1 `models.py`にVLAN固有テスト用データクラスを追加する
    - `GatewayDnsTarget` dataclass（hostname, expect）を追加する
    - `PosDevice` dataclass（name, ip）を追加する
    - `VlanTestConfig` dataclass（https_urls, store_gateway_dns_targets, store_printer_host, store_whereami_url, pos_devices, public_dns_negative_targets）を追加する
    - `TestProfile`に`vlan_tests: VlanTestConfig | None = None`フィールドを追加する
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [x] 1.2 `profile.py`の`parse_profile`と`profile_to_dict`をVLAN固有フィールドに対応させる
    - `parse_profile`: `vlan_tests`キーが存在する場合に`VlanTestConfig`をパースする
    - `profile_to_dict`: `vlan_tests`が非Noneの場合に辞書に含める
    - 既存プロファイル（`vlan_tests`なし）との後方互換性を維持する
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [x] 1.3 `profile.py`の`validate_profile`をVLAN固有フィールドに対応させる
    - `vlan_tests`が非Noneの場合: https_urlsが空でないこと、store_printer_hostが空でないこと、store_whereami_urlが空でないこと、pos_devicesが空でないこと、public_dns_negative_targetsが空でないこと等を検証する
    - `vlan_tests`がNoneの場合: バリデーションをスキップする
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [x] 1.4 `profiles/default.json`にVLAN固有テスト設定のデフォルト値を追加する
    - 設計ドキュメントのJSONスキーマに従い、`vlan_tests`セクションを追加する
    - _Requirements: 7.7_

  - [x] 1.5 既存テスト（`tests/test_profile.py`）を更新し、VLAN固有フィールドの読み込み・バリデーションを検証する
    - `parse_profile`でvlan_testsを含むプロファイルが正しくパースされること
    - `validate_profile`でvlan_testsのバリデーションが動作すること
    - vlan_testsなしの既存プロファイルとの後方互換性
    - `profiles/default.json`の読み込みテストが引き続きパスすること
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_

  - [ ]* 1.6 Property 5のプロパティテストを作成する
    - **Property 5: 拡張TestProfileのラウンドトリップ**
    - 任意の有効なTestProfile（vlan_testsフィールドを含む）に対して`profile_to_dict` → `parse_profile`のラウンドトリップが等価であることを検証する
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5, 7.6**

- [x] 2. チェックポイント - プロファイル拡張の動作確認
  - 全テストがパスすることを確認し、不明点があればユーザーに質問する。

- [x] 3. ネットワークユーティリティの拡張
  - [x] 3.1 `utils/network.py`に`is_private_ip`関数を追加する
    - Python標準ライブラリの`ipaddress`モジュールを使用する
    - RFC 1918プライベートIPアドレス範囲（10.0.0.0/8、172.16.0.0/12、192.168.0.0/16）を判定する
    - 不正なIPアドレス文字列に対してはFalseを返す
    - _Requirements: 10.1, 10.2, 10.3_

  - [x] 3.2 `utils/network.py`に`get_default_gateway`関数を追加する
    - Windows: `ipconfig`コマンドの出力をパースする
    - macOS/Linux: `ip route`または`netstat -rn`の出力をパースする
    - 取得失敗時はNoneを返す
    - _Requirements: 9.1, 9.2, 9.3_

  - [x] 3.3 `tests/test_network.py`にユニットテストを作成する
    - `is_private_ip`: プライベートIP範囲内/範囲外の具体例テスト
    - `is_private_ip`: 不正なIPアドレス文字列のエッジケース
    - `get_default_gateway`: コマンド出力のモックによるパーステスト
    - `get_default_gateway`: コマンド失敗時のNone返却テスト
    - _Requirements: 9.1, 9.2, 9.3, 10.1, 10.2, 10.3_

  - [ ]* 3.4 Property 4のプロパティテストを作成する
    - **Property 4: プライベートIPアドレス判定の正確性**
    - 任意の有効なIPv4アドレスに対して、RFC 1918範囲内ならTrue、範囲外ならFalseを返すことを検証する
    - **Validates: Requirements 10.1, 10.2, 10.3**

- [x] 4. チェックポイント - ユーティリティの動作確認
  - 全テストがパスすることを確認し、不明点があればユーザーに質問する。

- [x] 5. HTTPS疎通確認テストモジュールの実装
  - [x] 5.1 `tests/https_check.py`を新規作成する
    - `run_https_check(urls, wan_path)` → `list[TestResult]`を実装する
    - `httpx`を同期モードで使用し、各URLにGETリクエストを送信する
    - ステータスコード200ならPASS、それ以外ならFAIL
    - 接続エラー・タイムアウト時はFAILとしerror_messageに詳細記録
    - 各URLに対して個別のTestResultを生成する
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_

  - [x] 5.2 `tests/test_https_check.py`にユニットテストを作成する
    - ステータスコード200でPASS判定
    - ステータスコード404/500等でFAIL判定
    - 接続エラー時のFAIL判定とerror_message記録
    - 複数URLに対する個別TestResult生成
    - _Requirements: 1.3, 1.4, 1.5, 1.6_

  - [ ]* 5.3 Property 1のプロパティテストを作成する
    - **Property 1: HTTPS疎通確認テストのステータスコード判定**
    - 任意のHTTPステータスコードに対して、200ならPASS、それ以外ならFAILであることを検証する
    - **Validates: Requirements 1.3, 1.4**

  - [ ]* 5.4 Property 7のプロパティテストを作成する
    - **Property 7: HTTPS疎通確認テストの結果数**
    - 任意のURLリスト（長さN）に対して、返されるTestResultのリスト長がNと等しいことを検証する
    - **Validates: Requirements 1.6**

- [x] 6. デフォルトゲートウェイDNS解決テストモジュールの実装
  - [x] 6.1 `tests/gateway_dns.py`を新規作成する
    - `GatewayDnsTarget`データクラスは`models.py`で定義済み
    - `run_gateway_dns_test(targets, wan_path)` → `list[TestResult]`を実装する
    - `get_default_gateway()`でゲートウェイIPを取得し、`dnspython`でDNSサーバーを指定して名前解決する
    - 期待値（`private_ip` / `nxdomain` / `resolve_success`）に基づいてpass/failを判定する
    - ゲートウェイ取得失敗時は全テスト項目をFAILとする
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10_

  - [x] 6.2 `tests/test_gateway_dns.py`にユニットテストを作成する
    - private_ip期待値: プライベートIP解決でPASS、パブリックIP解決でFAIL
    - nxdomain期待値: 解決失敗でPASS、解決成功でFAIL
    - resolve_success期待値: 解決成功でPASS、解決失敗でFAIL
    - ゲートウェイ取得失敗時の全テスト項目FAIL
    - _Requirements: 2.4, 2.5, 2.6, 2.7, 2.8_

  - [ ]* 6.3 Property 2のプロパティテストを作成する
    - **Property 2: ゲートウェイDNS解決テストの期待値判定**
    - 任意のGatewayDnsTargetと名前解決結果の組み合わせに対して、期待値に基づく判定が正しいことを検証する
    - **Validates: Requirements 2.4, 2.5, 2.6, 2.7**

- [x] 7. WhereAmI APIテストモジュールの実装
  - [x] 7.1 `tests/whereami.py`を新規作成する
    - `run_whereami_test(api_url, store_code, wan_path)` → `TestResult`を実装する
    - `httpx`を同期モードで使用し、APIエンドポイントにGETリクエストを送信する
    - レスポンスJSONの`shopCode`フィールドを`store_code`と整数比較する
    - 一致ならPASS、不一致ならFAIL（期待値と実際の値をdetailsに記録）
    - 接続エラー・タイムアウト・JSONパースエラー時はFAILとしerror_messageに詳細記録
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

  - [x] 7.2 `tests/test_whereami.py`にユニットテストを作成する
    - shopCode一致でPASS判定
    - shopCode不一致でFAIL判定（detailsに期待値・実際値が含まれること）
    - 接続エラー時のFAIL判定とerror_message記録
    - JSONパースエラー時のFAIL判定
    - _Requirements: 4.3, 4.4, 4.5, 4.6_

  - [ ]* 7.3 Property 3のプロパティテストを作成する
    - **Property 3: WhereAmI shopCode照合の正確性**
    - 任意のshopCode（整数）とstore_code（文字列）の組み合わせに対して、整数比較で一致ならPASS、不一致ならFAILであることを検証する
    - **Validates: Requirements 4.3, 4.4, 4.5**

- [x] 8. チェックポイント - テストモジュールの動作確認
  - 全テストがパスすることを確認し、不明点があればユーザーに質問する。

- [x] 9. Runner拡張とVLAN固有テストの統合
  - [x] 9.1 `runner.py`の`_run_tests_for_wan_path`にHTTPS疎通確認テストを追加する
    - 安定性テストの後にHTTPS疎通確認テストを実行する
    - `profile.vlan_tests`がNoneの場合はスキップする
    - エラー発生時はスキップして次に進む（既存パターン）
    - _Requirements: 1.1, 8.1_

  - [x] 9.2 `runner.py`の`_run_tests_for_wan_path`にVLAN種別固有テストのディスパッチを追加する
    - `vlan_type == "店舗"`: `run_gateway_dns_test` → `run_ping_test`（複合機） → `run_whereami_test`を順次実行する
    - `vlan_type == "POS"`: `run_ping_test`（ローカル機材）を実行する
    - `vlan_type == "公共"`: ネガティブDNSテスト（`run_dns_test`の結果をpass/fail反転）を実行する
    - 各テスト項目でエラー発生時はスキップして次に進む
    - `profile.vlan_tests`がNoneの場合はVLAN固有テストをスキップする
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x] 9.3 `runner.py`にネガティブDNSテストのラッパー関数を追加する
    - 既存の`run_dns_test`を呼び出し、結果のpass/failを反転させる
    - テスト名にプレフィックス`negative_`を付与する
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 9.4 `tests/test_runner.py`にRunner拡張のユニットテストを作成する
    - 店舗VLANで固有テスト3種（GW DNS、複合機ping、WhereAmI）が実行されること
    - POS VLANでローカル機材pingが実行されること
    - 公共VLANでネガティブDNSが実行されること
    - vlan_testsがNoneの場合にVLAN固有テストがスキップされること
    - VLAN固有テストでエラー発生時にスキップして次に進むこと
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [ ]* 9.5 Property 6のプロパティテストを作成する
    - **Property 6: ネガティブDNSテストのpass/fail反転**
    - 任意のホスト名とDNS解決結果に対して、ネガティブDNSテストでは通常のDNSテストの逆の判定が行われることを検証する
    - **Validates: Requirements 6.3, 6.4**

- [x] 10. 最終チェックポイント - 全体統合テスト
  - 全テストがパスすることを確認し、不明点があればユーザーに質問する。

## 備考

- `*`マーク付きタスクはオプションであり、MVP優先時はスキップ可能
- 各タスクは対応する要件番号を参照しトレーサビリティを確保
- チェックポイントで段階的に動作を検証
- プロパティテストはhypothesisで普遍的な正しさを検証、ユニットテストは具体例・エッジケースを検証
- 既存テスト（`test_profile.py`, `test_reporter.py`）が引き続きパスすることを各チェックポイントで確認する

