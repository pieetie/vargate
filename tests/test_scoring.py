"""
Covers the scoring engine: per-metric classification by direction (higher_better /
lower_better / band) with the dark/light green/orange/red zones, the weighted
weakest-link rule (critical red -> sample FAIL, major red capped at WARN, minor with
no effect), the patient verdict = worst of the two samples with weakest_role, the
comfort bounded to 0-100, and missing metrics (optional -> n/a excluded from the
score, required -> ValueError). Also includes pos_pct (clamp).
"""

import pytest

from vargate.scoring import (
    COLOR_DARK_GREEN,
    COLOR_LIGHT_GREEN,
    COLOR_ORANGE,
    COLOR_RED,
    GREEN,
    ORANGE,
    RED,
    classify,
    patient_verdict,
    pos_pct,
    score_sample,
)

HIGHER = {"direction": "higher_better", "thresholds": {"green": 30, "orange": 20}, "scale": [0, 60]}
LOWER = {"direction": "lower_better", "thresholds": {"green": 0.10, "orange": 0.20}, "scale": [0, 0.30]}
BAND = {"direction": "band", "thresholds": {"green": [300, 550], "orange": [250, 650]}, "scale": [200, 700]}


def test_classify_higher_better():
    assert classify(50, HIGHER, "tumor", 0.15) == COLOR_DARK_GREEN
    assert classify(30, HIGHER, "tumor", 0.15) == COLOR_LIGHT_GREEN
    assert classify(25, HIGHER, "tumor", 0.15) == COLOR_ORANGE
    assert classify(10, HIGHER, "tumor", 0.15) == COLOR_RED


def test_classify_lower_better():
    assert classify(0.0, LOWER, "tumor", 0.15) == COLOR_DARK_GREEN
    assert classify(0.10, LOWER, "tumor", 0.15) == COLOR_LIGHT_GREEN
    assert classify(0.15, LOWER, "tumor", 0.15) == COLOR_ORANGE
    assert classify(0.25, LOWER, "tumor", 0.15) == COLOR_RED


def test_classify_band():
    assert classify(425, BAND, "tumor", 0.15) == COLOR_DARK_GREEN
    assert classify(305, BAND, "tumor", 0.15) == COLOR_LIGHT_GREEN
    assert classify(260, BAND, "tumor", 0.15) == COLOR_ORANGE
    assert classify(700, BAND, "tumor", 0.15) == COLOR_RED


def test_all_green_sample_passes(make_sample, sv_profile):
    res = score_sample(make_sample(), sv_profile)
    assert res.verdict == GREEN
    assert res.verdict_label == "PASS"
    assert res.n_green == res.n_total == 12


def test_critical_red_fails_sample(make_sample, sv_profile):
    res = score_sample(make_sample(chimera_rate=0.10), sv_profile)
    assert res.verdict == RED
    assert res.verdict_label == "FAIL"


def test_major_red_caps_at_warn(make_sample, sv_profile):
    res = score_sample(make_sample(align_rate=0.50), sv_profile)
    assert res.verdict == ORANGE
    assert res.verdict_label == "WARN"


def test_minor_red_has_no_effect(make_sample, sv_profile):
    res = score_sample(make_sample(fold80=5.0), sv_profile)
    assert res.verdict == GREEN


def test_optional_missing_is_na_and_excluded(make_sample, sv_profile):
    res = score_sample(make_sample(at_dropout=None, gc_dropout=None), sv_profile)
    assert res.n_total == 10
    na = [r for r in res.rows if r.name == "at_dropout"][0]
    assert na.color is None
    assert na.formatted == "n/a"


def test_required_missing_raises(make_sample, sv_profile):
    with pytest.raises(ValueError):
        score_sample(make_sample(chimera_rate=None), sv_profile)


def test_comfort_in_range(make_sample, sv_profile):
    res = score_sample(make_sample(), sv_profile)
    assert 0 <= res.comfort <= 100


def test_patient_verdict_is_worst(make_sample, sv_profile):
    tumor = score_sample(make_sample(role="tumor", chimera_rate=0.10), sv_profile)
    normal = score_sample(make_sample(sample_id="N1", role="normal"), sv_profile)
    patient = patient_verdict(tumor, normal)
    assert patient.verdict == RED
    assert patient.verdict_label == "FAIL"
    assert patient.weakest_role == "tumor"


def test_weakest_role_none_when_both_pass(make_sample, sv_profile):
    tumor = score_sample(make_sample(role="tumor"), sv_profile)
    normal = score_sample(make_sample(sample_id="N1", role="normal"), sv_profile)
    assert patient_verdict(tumor, normal).weakest_role is None


def test_pos_pct_clamped():
    assert pos_pct(5, 0, 10) == 50.0
    assert pos_pct(-5, 0, 10) == 0.0
    assert pos_pct(50, 0, 10) == 100.0
