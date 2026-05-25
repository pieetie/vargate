"""
Covers profile loading and validation: the packaged sv_somatic profile loads, an
unknown profile -> FileNotFoundError, structural validation (metrics required, valid
weight/direction, band bounds constraint o_lo<=g_lo<=g_hi<=o_hi), the dotted-path CLI
override with type casting (--set k=v), and the thr_of/scale_of accessors for
role-specific vs role-agnostic metrics.
"""

import pytest

from vargate.profile import (
    _cast,
    apply_override,
    clone,
    load_profile,
    scale_of,
    thr_of,
    validate,
)


def test_load_packaged_profile():
    p = load_profile("sv_somatic")
    assert p["profile"] == "sv_somatic"
    assert "median_coverage" in p["metrics"]


def test_load_unknown_profile_raises():
    with pytest.raises(FileNotFoundError):
        load_profile("does_not_exist")


def test_validate_accepts_shipped_profile(sv_profile):
    validate(sv_profile)


def test_validate_requires_metrics():
    with pytest.raises(ValueError):
        validate({"profile": "x"})


def test_validate_rejects_bad_weight():
    bad = {"metrics": {"m": {"weight": "huge", "direction": "higher_better",
                             "thresholds": {"green": 1, "orange": 0}}}}
    with pytest.raises(ValueError):
        validate(bad)


def test_validate_rejects_bad_band_bounds():
    bad = {"metrics": {"ins": {"weight": "critical", "direction": "band",
                               "thresholds": {"green": [300, 550], "orange": [400, 650]}}}}
    with pytest.raises(ValueError):
        validate(bad)


@pytest.mark.parametrize("raw,expected", [
    ("0.05", 0.05), ("30", 30), ("true", True), ("false", False), ("critical", "critical"),
])
def test_cast(raw, expected):
    assert _cast(raw) == expected


def test_apply_override_dotted_path(sv_profile):
    p = clone(sv_profile)
    apply_override(p, "metrics.dup_rate.thresholds.green=0.05")
    assert p["metrics"]["dup_rate"]["thresholds"]["green"] == 0.05


def test_apply_override_requires_equals(sv_profile):
    with pytest.raises(ValueError):
        apply_override(clone(sv_profile), "metrics.dup_rate.thresholds.green")


def test_apply_override_unknown_key_raises(sv_profile):
    with pytest.raises(KeyError):
        apply_override(clone(sv_profile), "metrics.nope.green=1")


def test_load_profile_applies_overrides():
    p = load_profile("sv_somatic", overrides=["metrics.dup_rate.thresholds.green=0.05"])
    assert p["metrics"]["dup_rate"]["thresholds"]["green"] == 0.05


def test_thr_of_role_specific(sv_profile):
    spec = sv_profile["metrics"]["median_coverage"]
    assert thr_of(spec, "tumor")["green"] == 30
    assert thr_of(spec, "normal")["green"] == 25


def test_scale_of_role_specific_and_default(sv_profile):
    cov = sv_profile["metrics"]["median_coverage"]
    assert scale_of(cov, "tumor") == (0.0, 60.0)
    assert scale_of({"direction": "lower_better"}, "tumor") == (0.0, 1.0)
