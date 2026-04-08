"""Tests for Appliance Fingerprinting (v5.12.0)."""

import pytest
from datetime import datetime, timedelta
from copilot_core.energy.fingerprint import (
    ApplianceFingerprinter,
    Fingerprint,
    DeviceMatch,
    UsageStats,
    PowerSample,
    POWER_CHANGE_THRESHOLD,
    CONFIDENCE_MEDIUM,
)


@pytest.fixture
def fp():
    return ApplianceFingerprinter()


@pytest.fixture
def washer_samples():
    """Simulated washer power signature: heat → wash → spin."""
    now = datetime.now()
    samples = []
    # Heating phase (15 min @ ~2000W)
    for i in range(15):
        samples.append({
            "timestamp": (now + timedelta(minutes=i)).isoformat(),
            "watts": 1800 + (i % 3) * 100,
        })
    # Washing phase (45 min @ ~300W)
    for i in range(15, 60):
        samples.append({
            "timestamp": (now + timedelta(minutes=i)).isoformat(),
            "watts": 250 + (i % 4) * 25,
        })
    # Spinning phase (20 min @ ~500W)
    for i in range(60, 80):
        samples.append({
            "timestamp": (now + timedelta(minutes=i)).isoformat(),
            "watts": 450 + (i % 5) * 30,
        })
    return samples


# ═══════════════════════════════════════════════════════════════════════════
# Bootstrap / Archetypes
# ═══════════════════════════════════════════════════════════════════════════


class TestBootstrap:
    def test_has_archetypes(self, fp):
        all_fp = fp.get_all_fingerprints()
        assert len(all_fp) >= 6  # washer, dryer, dishwasher, oven, ev_charger, heat_pump

    def test_archetype_fields(self, fp):
        all_fp = fp.get_all_fingerprints()
        for f in all_fp:
            assert "device_id" in f
            assert "device_name" in f
            assert "avg_power_watts" in f
            assert "phases" in f

    def test_archetype_types(self, fp):
        types = {f["device_type"] for f in fp.get_all_fingerprints()}
        assert "washer" in types
        assert "dryer" in types
        assert "ev_charger" in types

    def test_get_specific_archetype(self, fp):
        f = fp.get_fingerprint("archetype_washer")
        assert f is not None
        assert f.device_type == "washer"


# ═══════════════════════════════════════════════════════════════════════════
# Record Signature
# ═══════════════════════════════════════════════════════════════════════════


class TestRecordSignature:
    def test_returns_fingerprint(self, fp, washer_samples):
        result = fp.record_signature("my_washer", "Waschmaschine", "washer", washer_samples)
        assert isinstance(result, Fingerprint)

    def test_fingerprint_has_stats(self, fp, washer_samples):
        result = fp.record_signature("my_washer", "Waschmaschine", "washer", washer_samples)
        assert result.avg_power_watts > 0
        assert result.peak_power_watts > 0
        assert result.sample_count == 1

    def test_multiple_recordings(self, fp, washer_samples):
        fp.record_signature("my_washer", "Waschmaschine", "washer", washer_samples)
        result = fp.record_signature("my_washer", "Waschmaschine", "washer", washer_samples)
        assert result.sample_count == 2

    def test_custom_device(self, fp):
        samples = [{"timestamp": datetime.now().isoformat(), "watts": 1500}
                    for _ in range(20)]
        result = fp.record_signature("my_oven", "Backofen", "oven", samples)
        assert result.device_name == "Backofen"
        assert result.device_type == "oven"

    def test_phases_detected(self, fp, washer_samples):
        result = fp.record_signature("my_washer", "Waschmaschine", "washer", washer_samples)
        assert len(result.phases) >= 1

    def test_typical_kwh_positive(self, fp, washer_samples):
        result = fp.record_signature("my_washer", "Waschmaschine", "washer", washer_samples)
        assert result.typical_kwh > 0

    def test_stored_in_library(self, fp, washer_samples):
        fp.record_signature("my_washer", "Waschmaschine", "washer", washer_samples)
        stored = fp.get_fingerprint("my_washer")
        assert stored is not None
        assert stored.device_name == "Waschmaschine"


# ═══════════════════════════════════════════════════════════════════════════
# Identify
# ═══════════════════════════════════════════════════════════════════════════


class TestIdentify:
    def test_no_match_low_power(self, fp):
        matches = fp.identify(10.0)
        assert matches == []

    def test_matches_washer_heating(self, fp):
        matches = fp.identify(2000.0)
        assert len(matches) > 0
        types = {m.device_type for m in matches}
        # Should match washer heating or oven or similar high-power device
        assert len(types) > 0

    def test_matches_sorted_by_confidence(self, fp):
        matches = fp.identify(500.0)
        if len(matches) > 1:
            confidences = [m.confidence for m in matches]
            assert confidences == sorted(confidences, reverse=True)

    def test_match_fields(self, fp):
        matches = fp.identify(2500.0)
        if matches:
            m = matches[0]
            assert isinstance(m, DeviceMatch)
            assert m.confidence > 0
            assert m.device_name != ""
            assert m.current_power_watts == 2500.0

    def test_ev_charger_match(self, fp):
        matches = fp.identify(7400.0)
        ev_matches = [m for m in matches if m.device_type == "ev_charger"]
        assert len(ev_matches) > 0
        assert ev_matches[0].confidence > CONFIDENCE_MEDIUM

    def test_estimated_remaining(self, fp):
        matches = fp.identify(2000.0)
        for m in matches:
            assert m.estimated_remaining_minutes >= 0

    def test_below_threshold_empty(self, fp):
        matches = fp.identify(POWER_CHANGE_THRESHOLD - 1)
        assert matches == []

    def test_custom_fingerprint_match(self, fp, washer_samples):
        fp.record_signature("my_washer", "Waschmaschine", "washer", washer_samples)
        # Record has ~300W washing phase
        matches = fp.identify(300.0)
        custom = [m for m in matches if m.device_id == "my_washer"]
        assert len(custom) > 0


# ═══════════════════════════════════════════════════════════════════════════
# Usage Stats
# ═══════════════════════════════════════════════════════════════════════════


class TestUsageStats:
    def test_no_logs_returns_defaults(self, fp):
        stats = fp.get_usage_stats("archetype_washer")
        assert stats is not None
        assert stats.total_runs == 0

    def test_unknown_device_none(self, fp):
        stats = fp.get_usage_stats("nonexistent")
        assert stats is None

    def test_log_and_retrieve(self, fp):
        fp.log_device_run("archetype_washer", 90, 1.5, 500)
        fp.log_device_run("archetype_washer", 85, 1.4, 480)
        stats = fp.get_usage_stats("archetype_washer")
        assert stats.total_runs == 2
        assert stats.total_kwh == pytest.approx(2.9, abs=0.1)
        assert stats.avg_duration_minutes == pytest.approx(87.5, abs=0.1)

    def test_runs_this_week(self, fp):
        fp.log_device_run("archetype_washer", 90, 1.5, 500)
        stats = fp.get_usage_stats("archetype_washer")
        assert stats.runs_this_week >= 1

    def test_runs_this_month(self, fp):
        fp.log_device_run("archetype_dryer", 120, 5.0, 2500)
        stats = fp.get_usage_stats("archetype_dryer")
        assert stats.runs_this_month >= 1

    def test_last_run_set(self, fp):
        fp.log_device_run("archetype_washer", 90, 1.5, 500)
        stats = fp.get_usage_stats("archetype_washer")
        assert stats.last_run != ""

    def test_all_usage_stats(self, fp):
        fp.log_device_run("archetype_washer", 90, 1.5, 500)
        all_stats = fp.get_all_usage_stats()
        assert len(all_stats) >= 6  # all archetypes
        washer_stats = [s for s in all_stats if s["device_id"] == "archetype_washer"]
        assert washer_stats[0]["total_runs"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# All Fingerprints
# ═══════════════════════════════════════════════════════════════════════════


class TestAllFingerprints:
    def test_list_all(self, fp):
        all_fp = fp.get_all_fingerprints()
        assert isinstance(all_fp, list)
        assert all(isinstance(f, dict) for f in all_fp)

    def test_custom_included(self, fp, washer_samples):
        fp.record_signature("custom_1", "My Device", "washer", washer_samples)
        all_fp = fp.get_all_fingerprints()
        ids = {f["device_id"] for f in all_fp}
        assert "custom_1" in ids

    def test_archetype_included(self, fp):
        all_fp = fp.get_all_fingerprints()
        ids = {f["device_id"] for f in all_fp}
        assert "archetype_washer" in ids


# ═══════════════════════════════════════════════════════════════════════════
# Phase Detection
# ═══════════════════════════════════════════════════════════════════════════


class TestPhaseDetection:
    def test_mixed_phases(self, fp, washer_samples):
        result = fp.record_signature("pw", "W", "washer", washer_samples)
        # Should detect at least 2 phases (high-load heating vs low-load washing)
        assert len(result.phases) >= 2

    def test_constant_power(self, fp):
        samples = [{"timestamp": datetime.now().isoformat(), "watts": 500}
                    for _ in range(50)]
        result = fp.record_signature("const", "C", "other", samples)
        # Constant power → single phase
        assert len(result.phases) >= 1

    def test_phase_percentages_sum(self, fp, washer_samples):
        result = fp.record_signature("pw", "W", "washer", washer_samples)
        total_pct = sum(p["duration_pct"] for p in result.phases)
        assert pytest.approx(total_pct, abs=1.0) == 100.0
