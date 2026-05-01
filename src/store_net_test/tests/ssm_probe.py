"""SSM_Client Transport層

boto3を使用してSSM Send Commandを発行し、結果を取得するTransport層モジュール。
Route 53からの店舗DNSレコード取得、AWS認証確認も担当する。

boto3はオプション依存であり、ssm_probeセクション存在時のみインポートする。
未インストール時はエラーメッセージを表示して逆方向チェックをスキップする。

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8,
              3.1, 3.2, 3.3, 3.4, 3.5,
              4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10, 4.11, 4.12, 4.13,
              8.1, 8.2, 8.3, 9.1, 9.2, 9.3
"""

from __future__ import annotations

import logging
import re
import time

from ..models import SSMCommandResult, SSMProbeConfig

logger = logging.getLogger(__name__)

# pingターゲットバリデーション用パターン
# IPv4アドレス形式: 1〜3桁の数字をドットで4つ連結
_IPV4_RE = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
# FQDN形式: 英数字で始まり、英数字・ドット・ハイフンのみ許可
_FQDN_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9.\-]+$")

# シェルメタ文字（シェルインジェクション防止）
_SHELL_META_CHARS = set(";|&`()<>\n")

# SSM StandardOutputContent の上限文字数
_SSM_OUTPUT_LIMIT = 24000

# CloudWatch Logsのログストリーム・ロググループ設定
_CW_LOG_GROUP = "/aws/ssm/netcheck/"

# ポーリング設定
_INITIAL_WAIT_SECONDS = 1.0
_POLL_INTERVAL_SECONDS = 2.0
_INVOCATION_PROPAGATION_MAX_SECONDS = 5.0


def check_boto3_available() -> bool:
    """boto3がインポート可能か確認する

    Returns:
        インポート可能ならTrue、不可ならFalse
    """
    try:
        import boto3  # noqa: F401
        return True
    except ImportError:
        return False


def check_aws_credentials(region: str) -> bool:
    """AWS認証情報が有効か確認する（STS get-caller-identity）

    Args:
        region: AWSリージョン

    Returns:
        認証有効ならTrue、無効ならFalse
    """
    try:
        import boto3

        sts = boto3.client("sts", region_name=region)
        sts.get_caller_identity()
        return True
    except Exception as e:
        logger.error("AWS認証確認失敗: %s", e)
        return False


def validate_ping_target(target: str) -> bool:
    """pingターゲットがIPアドレスまたはFQDN形式か検証する

    シェルインジェクション防止のためのバリデーション。
    IPv4アドレスパターンまたはFQDNパターンのみ許可し、
    シェルメタ文字（;|&`()<>\\n等）を含む文字列は拒否する。

    Args:
        target: 検証対象の文字列

    Returns:
        有効ならTrue、無効ならFalse
    """
    if not target:
        return False

    # シェルメタ文字チェック
    if any(c in target for c in _SHELL_META_CHARS):
        return False

    # IPv4アドレスまたはFQDN形式チェック
    if _IPV4_RE.match(target):
        return True
    if _FQDN_RE.match(target):
        return True

    return False


def build_ping_command(target: str, count: int) -> str:
    """ICMPpingコマンド文字列を構築する

    ホワイトリスト方式でpingコマンドのみ生成する。
    targetはvalidate_ping_targetで事前検証済みであること。

    Args:
        target: pingターゲット（IPアドレスまたはFQDN）
        count: ping回数

    Returns:
        コマンド文字列（例: "ping -c 5 192.168.2.100"）
    """
    return f"ping -c {count} {target}"


def filter_store_records(
    records: list[str],
    store_code: str,
    domain: str,
) -> list[str]:
    """*.s<store_code>.<domain> パターンに一致するレコードを抽出する

    list_store_dns_records の内部ヘルパー。
    Route 53 ListResourceRecordSets の結果からパターンマッチでフィルタリングする。

    Args:
        records: DNSレコード名のリスト（FQDN）
        store_code: 店舗コード（4桁数字）
        domain: ドメイン名（例: "yamaokaya.net"）

    Returns:
        パターンに一致するレコードのみのリスト
    """
    # パターン: <任意のプレフィックス>.s<store_code>.<domain>
    # 末尾のドットはRoute 53のFQDN表記に対応
    suffix = f".s{store_code}.{domain}"
    suffix_dot = f".s{store_code}.{domain}."

    result: list[str] = []
    for record in records:
        # 末尾ドット付き/なし両方に対応
        name = record.rstrip(".")
        if name.endswith(suffix) and len(name) > len(suffix):
            result.append(name)
        elif record.endswith(suffix_dot) and len(record.rstrip(".")) > len(suffix):
            result.append(name)

    return result


def resolve_hosted_zone_id(
    hosted_zone_domain: str,
    hosted_zone_id: str | None,
    region: str,
) -> str | None:
    """Route 53のHosted Zone IDを解決する

    hosted_zone_idが指定されている場合はそちらを優先。
    未指定の場合はroute53:ListHostedZonesByNameで検索する。

    Args:
        hosted_zone_domain: ドメイン名（例: "yamaokaya.net"）
        hosted_zone_id: 直接指定のHosted Zone ID（オプション）
        region: AWSリージョン

    Returns:
        Hosted Zone ID文字列、取得失敗時はNone
    """
    # 直接指定がある場合はそちらを優先（Req 2.4）
    if hosted_zone_id is not None:
        logger.info("Hosted Zone ID直接指定: %s", hosted_zone_id)
        return hosted_zone_id

    try:
        import boto3

        route53 = boto3.client("route53", region_name=region)

        # ドメイン名の末尾にドットを付与（Route 53の正規化形式）
        dns_name = hosted_zone_domain if hosted_zone_domain.endswith(".") else f"{hosted_zone_domain}."

        response = route53.list_hosted_zones_by_name(DNSName=dns_name, MaxItems="1")

        hosted_zones = response.get("HostedZones", [])
        if not hosted_zones:
            logger.warning("Hosted Zoneが見つかりません: %s", hosted_zone_domain)
            return None

        # 返却されたHosted Zoneのドメイン名が一致するか確認
        zone = hosted_zones[0]
        zone_name = zone["Name"].rstrip(".")
        if zone_name != hosted_zone_domain.rstrip("."):
            logger.warning(
                "Hosted Zoneドメイン不一致: 期待=%s, 取得=%s",
                hosted_zone_domain,
                zone_name,
            )
            return None

        # Hosted Zone IDからプレフィックス "/hostedzone/" を除去
        zone_id = zone["Id"].replace("/hostedzone/", "")
        logger.info("Hosted Zone ID解決: %s -> %s", hosted_zone_domain, zone_id)
        return zone_id

    except Exception as e:
        logger.error("Hosted Zone ID解決失敗: %s", e)
        return None


def list_store_dns_records(
    hosted_zone_id: str,
    store_code: str,
    hosted_zone_domain: str,
    region: str,
) -> list[str]:
    """Route 53から店舗の名前付き端末レコードを列挙する

    *.s<store_code>.<hosted_zone_domain> パターンに一致するレコードを返す。
    Route 53クエリはローカルPC側でboto3経由で実行する（Req 2.3）。

    Args:
        hosted_zone_id: Hosted Zone ID
        store_code: 店舗コード（4桁数字）
        hosted_zone_domain: ドメイン名
        region: AWSリージョン

    Returns:
        FQDNのリスト（例: ["rt.s1234.yamaokaya.net", "pos.s1234.yamaokaya.net"]）
    """
    try:
        import boto3

        route53 = boto3.client("route53", region_name=region)

        # StartRecordNameを *.s<store_code>.<domain> の先頭に設定
        # Route 53はアルファベット順なので、"a.s1233.yamaokaya.net" から開始すれば
        # "ap.s1233...", "cam.s1233...", ... と名前付き端末が先頭に来る
        suffix = f".s{store_code}.{hosted_zone_domain}"
        start_name = f"a{suffix}"

        all_records: list[str] = []
        paginator_kwargs: dict = {
            "HostedZoneId": hosted_zone_id,
            "StartRecordName": start_name,
            "StartRecordType": "CNAME",
        }

        done = False
        while not done:
            response = route53.list_resource_record_sets(**paginator_kwargs)

            record_sets = response.get("ResourceRecordSets", [])
            for record_set in record_sets:
                name = record_set["Name"].rstrip(".")

                # パターン外のレコードに到達したら早期終了
                # Route 53はアルファベット順なので、s<store_code>.<domain> を超えたら終了
                # 例: "z.s1233.yamaokaya.net" の次は "s1234..." や別のドメインになる
                if not name.endswith(suffix):
                    # まだsuffix以前のレコードの可能性もあるのでスキップ
                    # ただし、既にマッチするレコードを見つけた後なら終了
                    if all_records:
                        done = True
                        break
                    continue

                # CNAMEレコードのみ取得（名前付き端末はCNAME、IPベースはAレコード）
                if record_set.get("Type") != "CNAME":
                    continue
                all_records.append(name)

            if done:
                break

            # ページネーション処理
            if response.get("IsTruncated"):
                paginator_kwargs["StartRecordName"] = response["NextRecordName"]
                if "NextRecordType" in response:
                    paginator_kwargs["StartRecordType"] = response["NextRecordType"]
                else:
                    paginator_kwargs.pop("StartRecordType", None)
            else:
                break

        # パターンフィルタリング（念のため）
        filtered = filter_store_records(all_records, store_code, hosted_zone_domain)
        logger.info(
            "Route 53レコード取得: store_code=%s, 件数=%d, レコード=%s",
            store_code,
            len(filtered),
            filtered,
        )
        return filtered

    except Exception as e:
        logger.error("Route 53レコード取得失敗: store_code=%s, エラー=%s", store_code, e)
        return []



def _fetch_cloudwatch_output(
    command_id: str,
    instance_id: str,
    region: str,
) -> str | None:
    """CloudWatch Logsからコマンド出力を取得する（フォールバック）

    StandardOutputContentが24,000文字上限に到達した場合のフォールバックパス。
    CloudWatch Logsから完全な出力を取得する。

    Args:
        command_id: SSMコマンドID
        instance_id: EC2インスタンスID
        region: AWSリージョン

    Returns:
        コマンド出力文字列、取得失敗時はNone
    """
    try:
        import boto3

        logs_client = boto3.client("logs", region_name=region)

        # CloudWatch Logsのログストリーム名はSSMの規約に従う
        # /aws/ssm/netcheck/<command_id>/<instance_id>/aws-runShellScript/stdout
        log_group = _CW_LOG_GROUP
        log_stream = f"{command_id}/{instance_id}/aws-runShellScript/stdout"

        # ログストリームの存在確認
        streams_response = logs_client.describe_log_streams(
            logGroupName=log_group,
            logStreamNamePrefix=log_stream,
            limit=1,
        )

        streams = streams_response.get("logStreams", [])
        if not streams:
            logger.warning(
                "CloudWatch Logsストリームが見つかりません: group=%s, stream=%s",
                log_group,
                log_stream,
            )
            return None

        # ログイベントを取得
        events_response = logs_client.get_log_events(
            logGroupName=log_group,
            logStreamName=streams[0]["logStreamName"],
            startFromHead=True,
        )

        events = events_response.get("events", [])
        if not events:
            return None

        # 全イベントのメッセージを結合
        output = "\n".join(event["message"] for event in events)
        logger.info(
            "CloudWatch Logsから出力取得: CommandId=%s, InstanceId=%s, 文字数=%d",
            command_id,
            instance_id,
            len(output),
        )
        return output

    except Exception as e:
        logger.error(
            "CloudWatch Logs取得失敗: CommandId=%s, InstanceId=%s, エラー=%s",
            command_id,
            instance_id,
            e,
        )
        return None


def send_ssm_ping_command(
    config: SSMProbeConfig,
    target: str,
    count: int,
) -> list[SSMCommandResult]:
    """SSM Send Commandでpingを実行し、結果を取得する

    タグマッチで全プローブインスタンスにコマンドを送信し、
    ポーリングで完了を待機して結果を返す。

    ポーリング戦略:
    - 初期待機: send_command応答後1秒
    - ポーリング間隔: 2秒固定
    - InvocationDoesNotExist: 最大5秒間リトライ（伝播遅延対応）
    - timeout_seconds超過: クライアントタイムアウトとしてERROR

    CloudWatch Logsフォールバック:
    - CloudWatchOutputConfigは常時設定（/aws/ssm/netcheck/）
    - StandardOutputContentが24,000文字上限到達時のみCloudWatch Logsから取得

    自動リトライなし（各テスト実行は1回のみ試行）。

    Args:
        config: SSMプローブ設定
        target: pingターゲット
        count: ping回数

    Returns:
        各プローブインスタンスのSSMCommandResultリスト
    """
    # ターゲットバリデーション（Req 9.2）
    if not validate_ping_target(target):
        logger.error("無効なpingターゲット: %s", target)
        return [
            SSMCommandResult(
                instance_id="unknown",
                status="Failed",
                response_code=-1,
                stdout="",
                stderr=f"無効なpingターゲット: {target}",
            )
        ]

    # コマンド構築（Req 9.1, 9.3）
    command = build_ping_command(target, count)

    try:
        import boto3
        from botocore.exceptions import ClientError

        ssm = boto3.client("ssm", region_name=config.region)

        # SSM Send Command発行（Req 4.1, 4.10, 4.11）
        send_response = ssm.send_command(
            Targets=[
                {
                    "Key": f"tag:{config.target_tag_key}",
                    "Values": [config.target_tag_value],
                }
            ],
            DocumentName=config.document_name,
            Parameters={"commands": [command]},
            TimeoutSeconds=config.timeout_seconds,
            CloudWatchOutputConfig={
                "CloudWatchLogGroupName": _CW_LOG_GROUP,
                "CloudWatchOutputEnabled": True,
            },
        )

        command_id = send_response["Command"]["CommandId"]
        logger.info(
            "SSM Send Command: CommandId=%s, Command=%s, Targets=tag:%s=%s",
            command_id,
            command,
            config.target_tag_key,
            config.target_tag_value,
        )

        # 初期待機（Req 4.5 ポーリング戦略）
        time.sleep(_INITIAL_WAIT_SECONDS)

        # コマンド対象インスタンスを取得
        invocations = _list_command_invocations(ssm, command_id)

        # 0インスタンス検出時（Req 4.12）
        if not invocations:
            logger.warning(
                "プローブインスタンスが見つかりません: CommandId=%s, タグ=%s=%s",
                command_id,
                config.target_tag_key,
                config.target_tag_value,
            )
            return [
                SSMCommandResult(
                    instance_id="none",
                    status="Failed",
                    response_code=-1,
                    stdout="",
                    stderr=f"プローブインスタンスが見つかりません（タグ: {config.target_tag_key}={config.target_tag_value}）",
                )
            ]

        # 各インスタンスの結果をポーリングで取得
        results: list[SSMCommandResult] = []
        start_time = time.monotonic()

        for instance_id in invocations:
            logger.info(
                "SSM Command対象: CommandId=%s, InstanceId=%s",
                command_id,
                instance_id,
            )
            result = _poll_command_result(
                ssm=ssm,
                command_id=command_id,
                instance_id=instance_id,
                timeout_seconds=config.timeout_seconds,
                start_time=start_time,
                region=config.region,
            )
            results.append(result)

        return results

    except ClientError as e:
        # SSM APIエラー（Req 4.9）
        error_msg = str(e)
        logger.error("SSM Commandエラー: %s", error_msg)
        return [
            SSMCommandResult(
                instance_id="unknown",
                status="Failed",
                response_code=-1,
                stdout="",
                stderr=f"SSM APIエラー: {error_msg}",
            )
        ]
    except Exception as e:
        logger.error("SSM Command予期しないエラー: %s", e)
        return [
            SSMCommandResult(
                instance_id="unknown",
                status="Failed",
                response_code=-1,
                stdout="",
                stderr=f"予期しないエラー: {e}",
            )
        ]


def send_ssm_ping_commands_parallel(
    config: SSMProbeConfig,
    targets: list[tuple[str, int]],
) -> dict[str, list[SSMCommandResult]]:
    """複数ターゲットに対してSSM Send Commandを並列発行し、結果をまとめて取得する

    全ターゲットのsend_commandを先に一括発行し、その後まとめてポーリングする。
    これにより、N個のターゲットを直列実行する場合の N×15秒 が、
    max(各ping時間) + SSMオーバーヘッド ≈ 15秒 に短縮される。

    Args:
        config: SSMプローブ設定
        targets: (ターゲット文字列, ping回数) のタプルリスト

    Returns:
        ターゲット文字列をキー、SSMCommandResultリストを値とする辞書
    """
    import boto3
    from botocore.exceptions import ClientError

    results: dict[str, list[SSMCommandResult]] = {}

    # バリデーション
    valid_targets: list[tuple[str, int]] = []
    for target, count in targets:
        if not validate_ping_target(target):
            logger.error("無効なpingターゲット: %s", target)
            results[target] = [SSMCommandResult(
                instance_id="unknown", status="Failed", response_code=-1,
                stdout="", stderr=f"無効なpingターゲット: {target}",
            )]
        else:
            valid_targets.append((target, count))

    if not valid_targets:
        return results

    try:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _send_poll_one(target: str, count: int) -> tuple[str, list[SSMCommandResult]]:
            """1ターゲットの送信→待機→ポーリングを1スレッドで完結させる"""
            import boto3 as _boto3
            thread_ssm = _boto3.client("ssm", region_name=config.region)
            command = build_ping_command(target, count)

            try:
                send_response = thread_ssm.send_command(
                    Targets=[{
                        "Key": f"tag:{config.target_tag_key}",
                        "Values": [config.target_tag_value],
                    }],
                    DocumentName=config.document_name,
                    Parameters={"commands": [command]},
                    TimeoutSeconds=config.timeout_seconds,
                    CloudWatchOutputConfig={
                        "CloudWatchLogGroupName": _CW_LOG_GROUP,
                        "CloudWatchOutputEnabled": True,
                    },
                )
                command_id = send_response["Command"]["CommandId"]
                logger.info(
                    "SSM Send Command (並列): CommandId=%s, Target=%s",
                    command_id, target,
                )
            except ClientError as e:
                logger.error("SSM Send Command失敗: target=%s, エラー=%s", target, e)
                return (target, [SSMCommandResult(
                    instance_id="unknown", status="Failed", response_code=-1,
                    stdout="", stderr=f"SSM APIエラー: {e}",
                )])

            # 初期待機
            time.sleep(_INITIAL_WAIT_SECONDS)

            # インスタンスID取得
            invocations = _list_command_invocations(thread_ssm, command_id)
            if not invocations:
                logger.warning(
                    "プローブインスタンスが見つかりません (並列): CommandId=%s, target=%s",
                    command_id, target,
                )
                return (target, [SSMCommandResult(
                    instance_id="none", status="Failed", response_code=-1,
                    stdout="",
                    stderr=f"プローブインスタンスが見つかりません（タグ: {config.target_tag_key}={config.target_tag_value}）",
                )])

            # ポーリング
            poll_start = time.monotonic()
            target_results: list[SSMCommandResult] = []
            for inst_id in invocations:
                result = _poll_command_result(
                    ssm=thread_ssm,
                    command_id=command_id,
                    instance_id=inst_id,
                    timeout_seconds=config.timeout_seconds,
                    start_time=poll_start,
                    region=config.region,
                )
                target_results.append(result)
            return (target, target_results)

        # 全ターゲットを完全並列実行
        with ThreadPoolExecutor(max_workers=min(len(valid_targets), 15)) as executor:
            futures = [
                executor.submit(_send_poll_one, target, count)
                for target, count in valid_targets
            ]
            for future in as_completed(futures):
                try:
                    target, target_results = future.result()
                    results[target] = target_results
                except Exception as e:
                    logger.error("並列実行スレッドエラー: %s", e)

        return results

    except Exception as e:
        logger.error("SSM並列実行エラー: %s", e)
        # 未処理のターゲットにエラー結果を設定
        for target, count in valid_targets:
            if target not in results:
                results[target] = [SSMCommandResult(
                    instance_id="unknown", status="Failed", response_code=-1,
                    stdout="", stderr=f"予期しないエラー: {e}",
                )]
        return results


def _list_command_invocations(ssm: object, command_id: str) -> list[str]:
    """コマンド対象のインスタンスIDリストを取得する

    Args:
        ssm: boto3 SSMクライアント
        command_id: SSMコマンドID

    Returns:
        インスタンスIDのリスト
    """
    try:
        response = ssm.list_command_invocations(  # type: ignore[union-attr]
            CommandId=command_id,
        )
        invocations = response.get("CommandInvocations", [])
        return [inv["InstanceId"] for inv in invocations]
    except Exception as e:
        logger.error("list_command_invocations失敗: CommandId=%s, エラー=%s", command_id, e)
        return []


def _poll_command_result(
    ssm: object,
    command_id: str,
    instance_id: str,
    timeout_seconds: int,
    start_time: float,
    region: str,
) -> SSMCommandResult:
    """単一インスタンスのコマンド結果をポーリングで取得する

    ポーリング戦略:
    - ポーリング間隔: 2秒固定
    - InvocationDoesNotExist: 最大5秒間リトライ（伝播遅延対応）
    - timeout_seconds超過: クライアントタイムアウト

    Args:
        ssm: boto3 SSMクライアント
        command_id: SSMコマンドID
        instance_id: EC2インスタンスID
        timeout_seconds: タイムアウト秒数
        start_time: コマンド送信開始時刻（monotonic）
        region: AWSリージョン

    Returns:
        SSMCommandResult
    """
    from botocore.exceptions import ClientError

    propagation_start: float | None = None

    while True:
        elapsed = time.monotonic() - start_time

        # クライアント側タイムアウト（Req 4.6, 4.8）
        if elapsed >= timeout_seconds:
            logger.warning(
                "SSM Commandタイムアウト: CommandId=%s, InstanceId=%s, timeout=%ds",
                command_id,
                instance_id,
                timeout_seconds,
            )
            return SSMCommandResult(
                instance_id=instance_id,
                status="TimedOut",
                response_code=-1,
                stdout="",
                stderr=f"クライアントタイムアウト（ポーリング時間超過: {timeout_seconds}秒）",
            )

        try:
            response = ssm.get_command_invocation(  # type: ignore[union-attr]
                CommandId=command_id,
                InstanceId=instance_id,
            )

            status = response.get("Status", "")

            # 実行中の場合はポーリング継続（Req 4.5）
            if status in ("Pending", "InProgress", "Delayed"):
                time.sleep(_POLL_INTERVAL_SECONDS)
                continue

            # 完了ステータスの処理（Req 4.7）
            response_code = response.get("ResponseCode", -1)
            stdout = response.get("StandardOutputContent", "")
            stderr = response.get("StandardErrorContent", "")

            # CloudWatch Logsフォールバック（Req 4.2）
            # StandardOutputContentが24,000文字上限に到達した場合
            if len(stdout) >= _SSM_OUTPUT_LIMIT:
                logger.info(
                    "StandardOutputContent上限到達（%d文字）、CloudWatch Logsから取得: CommandId=%s, InstanceId=%s",
                    len(stdout),
                    command_id,
                    instance_id,
                )
                cw_output = _fetch_cloudwatch_output(command_id, instance_id, region)
                if cw_output is not None:
                    stdout = cw_output

            logger.info(
                "SSM Command完了: CommandId=%s, InstanceId=%s, Status=%s, ResponseCode=%d",
                command_id,
                instance_id,
                status,
                response_code,
            )

            return SSMCommandResult(
                instance_id=instance_id,
                status=status,
                response_code=response_code,
                stdout=stdout,
                stderr=stderr,
            )

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")

            # InvocationDoesNotExist: 伝播遅延リトライ（最大5秒）
            if error_code == "InvocationDoesNotExist":
                if propagation_start is None:
                    propagation_start = time.monotonic()

                propagation_elapsed = time.monotonic() - propagation_start
                if propagation_elapsed < _INVOCATION_PROPAGATION_MAX_SECONDS:
                    logger.info(
                        "InvocationDoesNotExist（伝播遅延リトライ）: CommandId=%s, InstanceId=%s, 経過=%.1fs",
                        command_id,
                        instance_id,
                        propagation_elapsed,
                    )
                    time.sleep(_POLL_INTERVAL_SECONDS)
                    continue
                else:
                    logger.error(
                        "InvocationDoesNotExist（伝播遅延タイムアウト）: CommandId=%s, InstanceId=%s",
                        command_id,
                        instance_id,
                    )
                    return SSMCommandResult(
                        instance_id=instance_id,
                        status="Failed",
                        response_code=-1,
                        stdout="",
                        stderr=f"InvocationDoesNotExist（伝播遅延タイムアウト: {_INVOCATION_PROPAGATION_MAX_SECONDS}秒）",
                    )
            else:
                # その他のClientError（Req 4.9）
                logger.error(
                    "SSM get_command_invocationエラー: CommandId=%s, InstanceId=%s, エラー=%s",
                    command_id,
                    instance_id,
                    e,
                )
                return SSMCommandResult(
                    instance_id=instance_id,
                    status="Failed",
                    response_code=-1,
                    stdout="",
                    stderr=str(e),
                )

        except Exception as e:
            logger.error(
                "SSM ポーリング予期しないエラー: CommandId=%s, InstanceId=%s, エラー=%s",
                command_id,
                instance_id,
                e,
            )
            return SSMCommandResult(
                instance_id=instance_id,
                status="Failed",
                response_code=-1,
                stdout="",
                stderr=str(e),
            )
