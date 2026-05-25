"""
Covers the output rendering: the machine-readable TSV (header + one row per sample,
value/color columns per metric, "na" for a missing optional metric), the standalone
HTML (contains the verdict, sample IDs and the label), and the stdout summary (the
PATIENT VERDICT line + per-sample verdicts).
"""

import csv

import pytest

from vargate.report import render_html, stdout_summary, write_tsv
from vargate.scoring import patient_verdict, score_sample


@pytest.fixture
def patient(make_sample, sv_profile):
    tumor = score_sample(make_sample(role="tumor"), sv_profile)
    normal = score_sample(
        make_sample(sample_id="N1", role="normal", at_dropout=None, gc_dropout=None),
        sv_profile,
    )
    return patient_verdict(tumor, normal)


def test_write_tsv_shape(patient, sv_profile, tmp_path):
    out = tmp_path / "r.tsv"
    write_tsv(patient, sv_profile, out)
    rows = list(csv.DictReader(out.open(), delimiter="\t"))
    assert len(rows) == 2
    assert rows[0]["sample_id"] == "T1"
    assert rows[0]["patient_verdict"] == "PASS"
    assert rows[0]["chimera_rate__color"] in ("dark_green", "light_green")


def test_write_tsv_optional_missing_is_na(patient, sv_profile, tmp_path):
    out = tmp_path / "r.tsv"
    write_tsv(patient, sv_profile, out)
    rows = list(csv.DictReader(out.open(), delimiter="\t"))
    normal = [r for r in rows if r["role"] == "normal"][0]
    assert normal["at_dropout__color"] == "na"
    assert normal["at_dropout__value"] == ""


def test_render_html_contains_verdict_and_ids(patient, sv_profile):
    html = render_html(patient, profile=sv_profile, label="Patient 42")
    assert "PASS" in html
    assert "T1" in html and "N1" in html
    assert "Patient 42" in html


def test_stdout_summary_format(patient):
    text = stdout_summary(patient)
    assert "PATIENT VERDICT: PASS" in text
    assert "T1" in text and "N1" in text
