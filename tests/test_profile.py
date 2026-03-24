"""テストプロファイル管理のテスト

profile.pyの読み込み・バリデーション・変換機能を検証する。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from store_net_test.models import (
    GatewayDnsTarget,
    PingTarget,
    PosDevice,
    StabilityConfig,
    TestProfile,
    VlanTestConfig,
)
from store_net_test.profile import (
    load_profiles,
    parse_profile,
    profile_to_dict,
    validate_profile,
)


# --- テストデータ ---

def _make_profile(**overrides) -> TestProfile:
    """テスト用のデフォルトTestProfileを生成する"""
    defaults = {
        "name": "test-profile",
        "description": "テスト用プロファイル",
        "ping_targets": [PingTarget(host="8.8.8.8", timeout_ms=1000)],
        "dns_targets": ["www.google.com"],
        "stability": StabilityConfig(
            target_host="8.8.8.8",
            duration_seconds=30,
            max_packet_loss_percent=5.0,
            max_jitter_ms=50.0,
        ),
    }
    defaults.update(overrides)
    return TestProfile(**defaults)


def _make_profile_dict(**overrides) -> dict:
    """テスト用のデフォルトプロファイル辞書を生成する"""
    defaults = {
        "name": "test-profile",
        "description": "テスト用プロファイル",
        "ping_targets": [{"host": "8.8.8.8", "timeout_ms": 1000}],
        "dns_targets": ["www.google.com"],
        "stability": {
            "target_host": "8.8.8.8",
            "duration_seconds": 30,
            "max_packet_loss_percent": 5.0,
            "max_jitter_ms": 50.0,
        },
    }
    defaults.update(overrides)
    return defaults


def _make_vlan_test_config() -> VlanTestConfig:
    """テスト用のVlanTestConfigを生成する"""
    return VlanTestConfig(
        https_urls=["https://www.google.com"],
        store_gateway_dns_targets=[
            GatewayDnsTarget(hostname="api.yamaokaya.net", expect="private_ip"),
        ],
        store_printer_host="prn.myshop.yamaokaya.net",
        store_whereami_url="https://api.yamaokaya.net/wb/whereami",
        pos_devices=[PosDevice(name="券売機1", ip="192.168.1.81")],
        public_dns_negative_targets=["nx.yamaokaya.net"],
    )


def _make_vlan_tests_dict() -> dict:
    """テスト用のvlan_tests辞書を生成する"""
    return {
        "https_urls": ["https://www.google.com"],
        "store_gateway_dns_targets": [
            {"hostname": "api.yamaokaya.net", "expect": "private_ip"},
        ],
        "store_printer_host": "prn.myshop.yamaokaya.net",
        "store_whereami_url": "https://api.yamaokaya.net/wb/whereami",
        "pos_devices": [{"name": "券売機1", "ip": "192.168.1.81"}],
        "public_dns_negative_targets": ["nx.yamaokaya.net"],
    }


# --- parse_profile テスト ---

class TestParseProfile:
    """parse_profile: 辞書からTestProfileオブジェクトを生成"""

    def test_有効な辞書からプロファイルを生成できる(self):
        data = _make_profile_dict()
        profile = parse_profile(data)
        assert profile.name == "test-profile"
        assert profile.description == "テスト用プロファイル"
        assert len(profile.ping_targets) == 1
        assert profile.ping_targets[0].host == "8.8.8.8"
        assert profile.ping_targets[0].timeout_ms == 1000
        assert profile.dns_targets == ["www.google.com"]
        assert profile.stability.target_host == "8.8.8.8"
        assert profile.stability.duration_seconds == 30

    def test_複数のpingターゲットを持つプロファイル(self):
        data = _make_profile_dict(ping_targets=[
            {"host": "8.8.8.8", "timeout_ms": 1000},
            {"host": "1.1.1.1", "timeout_ms": 500},
        ])
        profile = parse_profile(data)
        assert len(profile.ping_targets) == 2
        assert profile.ping_targets[1].host == "1.1.1.1"

    def test_必須フィールド欠損でKeyError(self):
        data = {"name": "incomplete"}
        with pytest.raises(KeyError):
            parse_profile(data)

    def test_stability欠損でKeyError(self):
        data = _make_profile_dict()
        del data["stability"]
        with pytest.raises(KeyError):
            parse_profile(data)

    def test_vlan_testsなしの辞書はvlan_testsがNone(self):
        """vlan_testsキーがない場合、後方互換性を維持してNoneになる"""
        data = _make_profile_dict()
        profile = parse_profile(data)
        assert profile.vlan_tests is None

    def test_ping_interval未指定時にデフォルト0_2が設定される(self):
        """ping_intervalキーがない場合、デフォルト値0.2が使用される"""
        data = _make_profile_dict()
        # stability辞書にping_intervalキーがないことを確認
        assert "ping_interval" not in data["stability"]
        profile = parse_profile(data)
        assert profile.stability.ping_interval == 0.2

    def test_ping_interval指定時に値が正しく読み込まれる(self):
        """ping_intervalキーが存在する場合、指定値が使用される"""
        data = _make_profile_dict()
        data["stability"]["ping_interval"] = 0.5
        profile = parse_profile(data)
        assert profile.stability.ping_interval == 0.5

    def test_vlan_testsありの辞書からVlanTestConfigをパースできる(self):
        """vlan_testsキーが存在する場合、ネストされたオブジェクトを正しくパースする"""
        data = _make_profile_dict(vlan_tests=_make_vlan_tests_dict())
        profile = parse_profile(data)
        assert profile.vlan_tests is not None
        assert profile.vlan_tests.https_urls == ["https://www.google.com"]
        assert len(profile.vlan_tests.store_gateway_dns_targets) == 1
        assert profile.vlan_tests.store_gateway_dns_targets[0].hostname == "api.yamaokaya.net"
        assert profile.vlan_tests.store_gateway_dns_targets[0].expect == "private_ip"
        assert profile.vlan_tests.store_printer_host == "prn.myshop.yamaokaya.net"
        assert profile.vlan_tests.store_whereami_url == "https://api.yamaokaya.net/wb/whereami"
        assert len(profile.vlan_tests.pos_devices) == 1
        assert profile.vlan_tests.pos_devices[0].name == "券売機1"
        assert profile.vlan_tests.pos_devices[0].ip == "192.168.1.81"
        assert profile.vlan_tests.public_dns_negative_targets == ["nx.yamaokaya.net"]


# --- profile_to_dict テスト ---

class TestProfileToDict:
    """profile_to_dict: TestProfileオブジェクトを辞書に変換"""

    def test_辞書に正しく変換される(self):
        profile = _make_profile()
        result = profile_to_dict(profile)
        assert result["name"] == "test-profile"
        assert result["ping_targets"] == [{"host": "8.8.8.8", "timeout_ms": 1000}]
        assert result["dns_targets"] == ["www.google.com"]
        assert result["stability"]["target_host"] == "8.8.8.8"

    def test_ラウンドトリップで等価(self):
        """Property 1: profile_to_dict → parse_profile のラウンドトリップ"""
        original = _make_profile()
        roundtripped = parse_profile(profile_to_dict(original))
        assert roundtripped == original

    def test_vlan_testsがNoneの場合は辞書に含まれない(self):
        """vlan_testsがNoneの場合、出力辞書にvlan_testsキーが含まれない"""
        profile = _make_profile()
        result = profile_to_dict(profile)
        assert "vlan_tests" not in result

    def test_vlan_testsが非Noneの場合は辞書に含まれる(self):
        """vlan_testsが設定されている場合、ネストされたオブジェクトが正しく直列化される"""
        profile = _make_profile(vlan_tests=_make_vlan_test_config())
        result = profile_to_dict(profile)
        assert "vlan_tests" in result
        vt = result["vlan_tests"]
        assert vt["https_urls"] == ["https://www.google.com"]
        assert vt["store_gateway_dns_targets"] == [
            {"hostname": "api.yamaokaya.net", "expect": "private_ip"},
        ]
        assert vt["store_printer_host"] == "prn.myshop.yamaokaya.net"
        assert vt["pos_devices"] == [{"name": "券売機1", "ip": "192.168.1.81"}]

    def test_vlan_tests付きラウンドトリップで等価(self):
        """vlan_testsを含むプロファイルのラウンドトリップが等価であること"""
        original = _make_profile(vlan_tests=_make_vlan_test_config())
        roundtripped = parse_profile(profile_to_dict(original))
        assert roundtripped == original

    def test_ping_interval付きラウンドトリップで保持される(self):
        """ping_intervalを含むプロファイルのラウンドトリップでping_intervalが保持されること"""
        original = _make_profile(
            stability=StabilityConfig(
                target_host="8.8.8.8",
                duration_seconds=5,
                max_packet_loss_percent=5.0,
                max_jitter_ms=50.0,
                ping_interval=0.5,
            )
        )
        d = profile_to_dict(original)
        # 辞書にping_intervalが含まれていること
        assert d["stability"]["ping_interval"] == 0.5
        roundtripped = parse_profile(d)
        assert roundtripped.stability.ping_interval == 0.5
        assert roundtripped == original


# --- validate_profile テスト ---

class TestValidateProfile:
    """validate_profile: プロファイルのバリデーション"""

    def test_有効なプロファイルはエラーなし(self):
        profile = _make_profile()
        errors = validate_profile(profile)
        assert errors == []

    def test_空の名前はエラー(self):
        profile = _make_profile(name="")
        errors = validate_profile(profile)
        assert any("プロファイル名" in e for e in errors)

    def test_空白のみの名前はエラー(self):
        profile = _make_profile(name="   ")
        errors = validate_profile(profile)
        assert any("プロファイル名" in e for e in errors)

    def test_空のping_targetsはエラー(self):
        profile = _make_profile(ping_targets=[])
        errors = validate_profile(profile)
        assert any("ping_targets" in e for e in errors)

    def test_ping_targetのtimeout_msが0以下はエラー(self):
        profile = _make_profile(
            ping_targets=[PingTarget(host="8.8.8.8", timeout_ms=0)]
        )
        errors = validate_profile(profile)
        assert any("timeout_ms" in e for e in errors)

    def test_空のdns_targetsはエラー(self):
        profile = _make_profile(dns_targets=[])
        errors = validate_profile(profile)
        assert any("dns_targets" in e for e in errors)

    def test_stability_duration_secondsが0以下はエラー(self):
        profile = _make_profile(
            stability=StabilityConfig(
                target_host="8.8.8.8",
                duration_seconds=0,
                max_packet_loss_percent=5.0,
                max_jitter_ms=50.0,
            )
        )
        errors = validate_profile(profile)
        assert any("duration_seconds" in e for e in errors)

    def test_packet_loss_percentが範囲外はエラー(self):
        profile = _make_profile(
            stability=StabilityConfig(
                target_host="8.8.8.8",
                duration_seconds=30,
                max_packet_loss_percent=101.0,
                max_jitter_ms=50.0,
            )
        )
        errors = validate_profile(profile)
        assert any("max_packet_loss_percent" in e for e in errors)

    def test_jitter_msが負の値はエラー(self):
        profile = _make_profile(
            stability=StabilityConfig(
                target_host="8.8.8.8",
                duration_seconds=30,
                max_packet_loss_percent=5.0,
                max_jitter_ms=-1.0,
            )
        )
        errors = validate_profile(profile)
        assert any("max_jitter_ms" in e for e in errors)

    def test_複数エラーを同時に検出(self):
        profile = _make_profile(
            name="",
            ping_targets=[],
            dns_targets=[],
        )
        errors = validate_profile(profile)
        assert len(errors) >= 3

    # --- VLAN固有テストバリデーション ---

    def test_vlan_testsがNoneの場合はバリデーションスキップ(self):
        """vlan_testsがNoneの場合、VLAN関連のエラーが出ないこと"""
        profile = _make_profile(vlan_tests=None)
        errors = validate_profile(profile)
        assert errors == []

    def test_ping_intervalが0以下はエラー(self):
        """ping_intervalが0の場合にバリデーションエラーになること"""
        profile = _make_profile(
            stability=StabilityConfig(
                target_host="8.8.8.8",
                duration_seconds=30,
                max_packet_loss_percent=5.0,
                max_jitter_ms=50.0,
                ping_interval=0,
            )
        )
        errors = validate_profile(profile)
        assert any("ping_interval" in e for e in errors)

    def test_ping_intervalが負の値はエラー(self):
        """ping_intervalが負の値の場合にバリデーションエラーになること"""
        profile = _make_profile(
            stability=StabilityConfig(
                target_host="8.8.8.8",
                duration_seconds=30,
                max_packet_loss_percent=5.0,
                max_jitter_ms=50.0,
                ping_interval=-0.1,
            )
        )
        errors = validate_profile(profile)
        assert any("ping_interval" in e for e in errors)

    def test_有効なvlan_testsはエラーなし(self):
        """全フィールドが有効なvlan_testsはバリデーションエラーなし"""
        profile = _make_profile(vlan_tests=_make_vlan_test_config())
        errors = validate_profile(profile)
        assert errors == []

    def test_vlan_testsのhttps_urlsが空はエラー(self):
        vt = _make_vlan_test_config()
        vt.https_urls = []
        profile = _make_profile(vlan_tests=vt)
        errors = validate_profile(profile)
        assert any("vlan_tests.https_urls" in e for e in errors)

    def test_vlan_testsのstore_printer_hostが空はエラー(self):
        vt = _make_vlan_test_config()
        vt.store_printer_host = ""
        profile = _make_profile(vlan_tests=vt)
        errors = validate_profile(profile)
        assert any("vlan_tests.store_printer_host" in e for e in errors)

    def test_vlan_testsのstore_whereami_urlが空はエラー(self):
        vt = _make_vlan_test_config()
        vt.store_whereami_url = ""
        profile = _make_profile(vlan_tests=vt)
        errors = validate_profile(profile)
        assert any("vlan_tests.store_whereami_url" in e for e in errors)

    def test_vlan_testsのpos_devicesが空はエラー(self):
        vt = _make_vlan_test_config()
        vt.pos_devices = []
        profile = _make_profile(vlan_tests=vt)
        errors = validate_profile(profile)
        assert any("vlan_tests.pos_devices" in e for e in errors)

    def test_vlan_testsのpublic_dns_negative_targetsが空はエラー(self):
        vt = _make_vlan_test_config()
        vt.public_dns_negative_targets = []
        profile = _make_profile(vlan_tests=vt)
        errors = validate_profile(profile)
        assert any("vlan_tests.public_dns_negative_targets" in e for e in errors)

    def test_vlan_testsのstore_gateway_dns_targetsが空はエラー(self):
        vt = _make_vlan_test_config()
        vt.store_gateway_dns_targets = []
        profile = _make_profile(vlan_tests=vt)
        errors = validate_profile(profile)
        assert any("vlan_tests.store_gateway_dns_targets" in e for e in errors)


# --- load_profiles テスト ---

class TestLoadProfiles:
    """load_profiles: ディレクトリからプロファイルを読み込む"""

    def test_有効なプロファイルを読み込める(self, tmp_path: Path):
        data = _make_profile_dict()
        (tmp_path / "default.json").write_text(json.dumps(data), encoding="utf-8")
        profiles = load_profiles(tmp_path)
        assert len(profiles) == 1
        assert profiles[0].name == "test-profile"

    def test_複数プロファイルを読み込める(self, tmp_path: Path):
        for name in ["alpha", "beta"]:
            data = _make_profile_dict(name=name)
            (tmp_path / f"{name}.json").write_text(json.dumps(data), encoding="utf-8")
        profiles = load_profiles(tmp_path)
        assert len(profiles) == 2
        # ソート順で読み込まれる
        assert profiles[0].name == "alpha"
        assert profiles[1].name == "beta"

    def test_存在しないディレクトリでFileNotFoundError(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError, match="プロファイルディレクトリが見つかりません"):
            load_profiles(tmp_path / "nonexistent")

    def test_JSONファイルなしでFileNotFoundError(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError, match="JSONファイルがありません"):
            load_profiles(tmp_path)

    def test_不正JSONでValueError(self, tmp_path: Path):
        (tmp_path / "bad.json").write_text("{invalid json", encoding="utf-8")
        with pytest.raises(ValueError, match="JSONパースに失敗"):
            load_profiles(tmp_path)

    def test_構造不正でValueError(self, tmp_path: Path):
        (tmp_path / "bad.json").write_text('{"name": "only-name"}', encoding="utf-8")
        with pytest.raises(ValueError, match="構造が不正"):
            load_profiles(tmp_path)

    def test_バリデーションエラーでValueError(self, tmp_path: Path):
        data = _make_profile_dict(name="")
        (tmp_path / "invalid.json").write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="バリデーションエラー"):
            load_profiles(tmp_path)

    def test_実際のデフォルトプロファイルを読み込める(self):
        """profiles/default.jsonが正しく読み込めることを確認（vlan_tests含む）"""
        profiles_dir = Path(__file__).parent.parent / "profiles"
        profiles = load_profiles(profiles_dir)
        assert len(profiles) >= 1
        default = next(p for p in profiles if p.name == "standard")
        assert default is not None
        # 安定性テスト設定が高速化対応していること
        assert default.stability.duration_seconds == 5
        assert default.stability.ping_interval == 0.2
        # default.jsonにはvlan_testsが含まれていること
        assert default.vlan_tests is not None
        assert len(default.vlan_tests.https_urls) >= 1
        assert len(default.vlan_tests.store_gateway_dns_targets) >= 1
        assert default.vlan_tests.store_printer_host != ""
        assert default.vlan_tests.store_whereami_url != ""
        assert len(default.vlan_tests.pos_devices) >= 1
        assert len(default.vlan_tests.public_dns_negative_targets) >= 1
