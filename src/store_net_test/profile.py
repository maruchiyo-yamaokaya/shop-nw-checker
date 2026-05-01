"""テストプロファイルの読み込み・バリデーション・変換

JSONファイルからテストプロファイルを読み込み、バリデーションする。
Requirements: 7.1, 7.3, 7.4, 7.5
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import (
    GatewayDnsTarget,
    PingTarget,
    PosDevice,
    ReverseCheckTarget,
    SSMProbeConfig,
    StabilityConfig,
    TestProfile,
    VlanTestConfig,
)


def parse_ssm_probe_config(data: dict) -> SSMProbeConfig:
    """ssm_probeセクション辞書からSSMProbeConfigオブジェクトを生成する

    デフォルト値の適用: document_name, target_tag_key, target_tag_value

    Args:
        data: ssm_probeセクションの辞書

    Returns:
        SSMProbeConfigオブジェクト

    Raises:
        KeyError: 必須フィールドが欠損している場合
    """
    return SSMProbeConfig(
        region=data["region"],
        timeout_seconds=data["timeout_seconds"],
        hosted_zone_domain=data["hosted_zone_domain"],
        local_network_ranges=list(data["local_network_ranges"]),
        document_name=data.get("document_name", "AWS-RunShellScript"),
        target_tag_key=data.get("target_tag_key", "NetCheckProbe"),
        target_tag_value=data.get("target_tag_value", "true"),
        hosted_zone_id=data.get("hosted_zone_id"),
    )


def ssm_probe_config_to_dict(config: SSMProbeConfig) -> dict:
    """SSMProbeConfigオブジェクトを辞書に変換する

    Args:
        config: SSMProbeConfigオブジェクト

    Returns:
        JSON直列化可能な辞書
    """
    return {
        "region": config.region,
        "timeout_seconds": config.timeout_seconds,
        "hosted_zone_domain": config.hosted_zone_domain,
        "local_network_ranges": list(config.local_network_ranges),
        "document_name": config.document_name,
        "target_tag_key": config.target_tag_key,
        "target_tag_value": config.target_tag_value,
        "hosted_zone_id": config.hosted_zone_id,
    }


def validate_ssm_probe_config(config: SSMProbeConfig) -> list[str]:
    """SSMProbeConfigのバリデーション

    必須フィールドの存在確認とlocal_network_rangesの形式チェックを行う。

    Args:
        config: 検証対象のSSMProbeConfig

    Returns:
        エラーメッセージのリスト（空リストなら有効）
    """
    import ipaddress

    errors: list[str] = []

    # 必須フィールドの存在確認
    if not config.region or not config.region.strip():
        errors.append("ssm_probe.regionが空です")
    if not config.timeout_seconds or config.timeout_seconds <= 0:
        errors.append(f"ssm_probe.timeout_secondsは正の値である必要があります: {config.timeout_seconds}")
    if not config.hosted_zone_domain or not config.hosted_zone_domain.strip():
        errors.append("ssm_probe.hosted_zone_domainが空です")

    # local_network_rangesの形式チェック
    if not config.local_network_ranges:
        errors.append("ssm_probe.local_network_rangesが空です")
    else:
        for i, cidr in enumerate(config.local_network_ranges):
            try:
                ipaddress.ip_network(cidr, strict=False)
            except ValueError:
                errors.append(f"ssm_probe.local_network_ranges[{i}]のCIDR形式が不正です: {cidr}")

    return errors


def parse_profile(data: dict) -> TestProfile:
    """辞書からTestProfileオブジェクトを生成する

    Args:
        data: プロファイル定義の辞書

    Returns:
        TestProfileオブジェクト

    Raises:
        KeyError: 必須フィールドが欠損している場合
        TypeError: フィールドの型が不正な場合
    """
    ping_targets = [
        PingTarget(host=t["host"], timeout_ms=t["timeout_ms"])
        for t in data["ping_targets"]
    ]
    stability_data = data["stability"]
    stability = StabilityConfig(
        target_host=stability_data["target_host"],
        duration_seconds=stability_data["duration_seconds"],
        max_packet_loss_percent=stability_data["max_packet_loss_percent"],
        max_jitter_ms=stability_data["max_jitter_ms"],
        # ping_intervalはキー不在時にデフォルト0.2を使用（後方互換性）
        ping_interval=stability_data.get("ping_interval", 0.2),
    )
    # VLAN固有テスト設定のパース（存在する場合のみ）
    vlan_tests: VlanTestConfig | None = None
    if "vlan_tests" in data:
        vt = data["vlan_tests"]
        # reverse_check_targetsのパース（存在する場合のみ）
        reverse_check_targets: list[ReverseCheckTarget] | None = None
        if "reverse_check_targets" in vt:
            reverse_check_targets = [
                ReverseCheckTarget(
                    target_kind=t["target_kind"],
                    count=t.get("count", 5),
                    loss_threshold_percent=t.get("loss_threshold_percent", 20.0),
                    terminal_prefixes=t.get("terminal_prefixes"),
                )
                for t in vt["reverse_check_targets"]
            ]
        vlan_tests = VlanTestConfig(
            https_urls=list(vt["https_urls"]),
            store_gateway_dns_targets=[
                GatewayDnsTarget(hostname=t["hostname"], expect=t["expect"])
                for t in vt["store_gateway_dns_targets"]
            ],
            store_printer_host=vt["store_printer_host"],
            store_whereami_url=vt["store_whereami_url"],
            pos_devices=[
                PosDevice(name=d["name"], ip=d["ip"])
                for d in vt["pos_devices"]
            ],
            public_dns_negative_targets=list(vt["public_dns_negative_targets"]),
            reverse_check_targets=reverse_check_targets,
        )

    # SSMプローブ設定のパース（存在する場合のみ）
    ssm_probe: SSMProbeConfig | None = None
    if "ssm_probe" in data:
        ssm_probe = parse_ssm_probe_config(data["ssm_probe"])

    return TestProfile(
        name=data["name"],
        description=data["description"],
        ping_targets=ping_targets,
        dns_targets=list(data["dns_targets"]),
        stability=stability,
        vlan_tests=vlan_tests,
        ssm_probe=ssm_probe,
    )


def profile_to_dict(profile: TestProfile) -> dict:
    """TestProfileオブジェクトを辞書に変換する

    Args:
        profile: TestProfileオブジェクト

    Returns:
        JSON直列化可能な辞書
    """
    result = {
        "name": profile.name,
        "description": profile.description,
        "ping_targets": [
            {"host": t.host, "timeout_ms": t.timeout_ms}
            for t in profile.ping_targets
        ],
        "dns_targets": list(profile.dns_targets),
        "stability": {
            "target_host": profile.stability.target_host,
            "duration_seconds": profile.stability.duration_seconds,
            "max_packet_loss_percent": profile.stability.max_packet_loss_percent,
            "max_jitter_ms": profile.stability.max_jitter_ms,
            "ping_interval": profile.stability.ping_interval,
        },
    }

    # VLAN固有テスト設定の直列化（存在する場合のみ）
    if profile.vlan_tests is not None:
        vt = profile.vlan_tests
        vlan_dict: dict = {
            "https_urls": list(vt.https_urls),
            "store_gateway_dns_targets": [
                {"hostname": t.hostname, "expect": t.expect}
                for t in vt.store_gateway_dns_targets
            ],
            "store_printer_host": vt.store_printer_host,
            "store_whereami_url": vt.store_whereami_url,
            "pos_devices": [
                {"name": d.name, "ip": d.ip}
                for d in vt.pos_devices
            ],
            "public_dns_negative_targets": list(vt.public_dns_negative_targets),
        }
        # reverse_check_targetsの直列化（存在する場合のみ）
        if vt.reverse_check_targets is not None:
            vlan_dict["reverse_check_targets"] = [
                {
                    "target_kind": t.target_kind,
                    "count": t.count,
                    "loss_threshold_percent": t.loss_threshold_percent,
                    **({"terminal_prefixes": t.terminal_prefixes} if t.terminal_prefixes is not None else {}),
                }
                for t in vt.reverse_check_targets
            ]
        result["vlan_tests"] = vlan_dict

    # SSMプローブ設定の直列化（存在する場合のみ）
    if profile.ssm_probe is not None:
        result["ssm_probe"] = ssm_probe_config_to_dict(profile.ssm_probe)

    return result


def validate_profile(profile: TestProfile) -> list[str]:
    """プロファイルのバリデーション

    必須フィールドの存在確認と閾値の範囲チェックを行う。

    Args:
        profile: 検証対象のTestProfile

    Returns:
        エラーメッセージのリスト（空リストなら有効）
    """
    errors: list[str] = []

    # 名前チェック
    if not profile.name or not profile.name.strip():
        errors.append("プロファイル名が空です")

    # Pingターゲットチェック
    if not profile.ping_targets:
        errors.append("ping_targetsが空です。最低1つのターゲットが必要です")
    for i, target in enumerate(profile.ping_targets):
        if not target.host or not target.host.strip():
            errors.append(f"ping_targets[{i}].hostが空です")
        if target.timeout_ms <= 0:
            errors.append(f"ping_targets[{i}].timeout_msは正の値である必要があります: {target.timeout_ms}")

    # DNSターゲットチェック
    if not profile.dns_targets:
        errors.append("dns_targetsが空です。最低1つのターゲットが必要です")
    for i, target in enumerate(profile.dns_targets):
        if not target or not target.strip():
            errors.append(f"dns_targets[{i}]が空です")

    # 安定性設定チェック
    stab = profile.stability
    if not stab.target_host or not stab.target_host.strip():
        errors.append("stability.target_hostが空です")
    if stab.duration_seconds <= 0:
        errors.append(f"stability.duration_secondsは正の値である必要があります: {stab.duration_seconds}")
    if not (0.0 <= stab.max_packet_loss_percent <= 100.0):
        errors.append(f"stability.max_packet_loss_percentは0〜100の範囲である必要があります: {stab.max_packet_loss_percent}")
    if stab.max_jitter_ms < 0.0:
        errors.append(f"stability.max_jitter_msは0以上である必要があります: {stab.max_jitter_ms}")
    # ping_intervalの正値チェック
    if stab.ping_interval <= 0:
        errors.append(f"stability.ping_intervalは正の値である必要があります: {stab.ping_interval}")

    # VLAN固有テスト設定チェック（存在する場合のみ）
    if profile.vlan_tests is not None:
        vt = profile.vlan_tests
        if not vt.https_urls:
            errors.append("vlan_tests.https_urlsが空です")
        if not vt.store_printer_host or not vt.store_printer_host.strip():
            errors.append("vlan_tests.store_printer_hostが空です")
        if not vt.store_whereami_url or not vt.store_whereami_url.strip():
            errors.append("vlan_tests.store_whereami_urlが空です")
        if not vt.pos_devices:
            errors.append("vlan_tests.pos_devicesが空です")
        if not vt.public_dns_negative_targets:
            errors.append("vlan_tests.public_dns_negative_targetsが空です")
        if not vt.store_gateway_dns_targets:
            errors.append("vlan_tests.store_gateway_dns_targetsが空です")

    # SSMプローブ設定チェック（存在する場合のみ）
    if profile.ssm_probe is not None:
        ssm_errors = validate_ssm_probe_config(profile.ssm_probe)
        errors.extend(ssm_errors)

    return errors


def load_profiles(profiles_dir: Path) -> list[TestProfile]:
    """プロファイルディレクトリから全JSONファイルを読み込む

    Args:
        profiles_dir: プロファイルJSONファイルが格納されたディレクトリ

    Returns:
        読み込んだTestProfileのリスト

    Raises:
        FileNotFoundError: ディレクトリが存在しない場合
        ValueError: JSONパースエラーまたはバリデーションエラーの場合
    """
    if not profiles_dir.exists():
        raise FileNotFoundError(f"プロファイルディレクトリが見つかりません: {profiles_dir}")

    json_files = sorted(profiles_dir.glob("*.json"))
    if not json_files:
        raise FileNotFoundError(f"プロファイルディレクトリにJSONファイルがありません: {profiles_dir}")

    profiles: list[TestProfile] = []
    for json_file in json_files:
        try:
            text = json_file.read_text(encoding="utf-8")
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"プロファイルのJSONパースに失敗しました ({json_file.name}): {e}"
            ) from e

        try:
            profile = parse_profile(data)
        except (KeyError, TypeError) as e:
            raise ValueError(
                f"プロファイルの構造が不正です ({json_file.name}): {e}"
            ) from e

        errors = validate_profile(profile)
        if errors:
            raise ValueError(
                f"プロファイルのバリデーションエラー ({json_file.name}): {'; '.join(errors)}"
            )

        profiles.append(profile)

    return profiles
