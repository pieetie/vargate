"""
Covers the canonical SampleMetrics schema: the insert_cv derivation (sd/median, and
inf when median is zero), the metric_value lookup (derived insert_cv, direct field,
unknown name -> None), and to_dict exposing insert_cv.
"""

import math

from vargate.model import SampleMetrics


def test_insert_cv_derived(make_sample):
    s = make_sample(insert_median=400.0, insert_sd=100.0)
    assert s.insert_cv == 0.25


def test_insert_cv_zero_median_is_inf(make_sample):
    s = make_sample(insert_median=0.0, insert_sd=100.0)
    assert math.isinf(s.insert_cv)


def test_metric_value_lookup(make_sample):
    s = make_sample(median_coverage=40.0, insert_median=400.0, insert_sd=100.0)
    assert s.metric_value("median_coverage") == 40.0
    assert s.metric_value("insert_cv") == 0.25
    assert s.metric_value("does_not_exist") is None


def test_to_dict_includes_insert_cv(make_sample):
    d = make_sample(insert_median=400.0, insert_sd=100.0).to_dict()
    assert d["insert_cv"] == 0.25
    assert d["sample_id"] == "T1"
