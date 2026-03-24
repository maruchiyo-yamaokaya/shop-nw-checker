"""テストプロファイル管理のテスト

profile.pyの読み込み・バリデーション・変換機能を検証する。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from store_net_test.models import PingTarget, StabilityConfig, TestProfile
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
        """profiles/default.jsonが正しく読み込めることを確認"""
        profiles_dir = Path(__file__).parent.parent / "profiles"
        profiles = load_profiles(profiles_dir)
        assert len(profiles) >= 1
        assert any(p.name == "standard" for p in profiles)
