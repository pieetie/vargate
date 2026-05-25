"""
Shared fixtures: path to the small synthetic Picard/markdup files (the all-green
T1/N1 pair), the loaded sv_somatic profile, and a SampleMetrics factory that is
green by default and that each test degrades field by field.
"""

from pathlib import Path

import pytest

from vargate.model import SampleMetrics
from vargate.profile import load_profile

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def pair_dir() -> Path:
    return FIXTURES / "pair"


@pytest.fixture
def sv_profile() -> dict:
    return load_profile("sv_somatic")


@pytest.fixture
def make_sample():
    def _make(**overrides) -> SampleMetrics:
        base = dict(
            sample_id="T1",
            role="tumor",
            median_coverage=40.0,
            pct_20x=0.95,
            fold80=1.10,
            pct_exc_mapq=0.05,
            insert_median=420.0,
            insert_sd=140.0,
            align_rate=0.99,
            chimera_rate=0.010,
            mismatch_rate=0.005,
            dup_rate=0.060,
            at_dropout=2.0,
            gc_dropout=0.5,
        )
        base.update(overrides)
        return SampleMetrics(**base)

    return _make
