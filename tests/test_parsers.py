"""
Covers the Picard/biobambam2 parsers: extracting the canonical fields from each
file, picking the PAIR row in alignment, supporting the two markdup markers
(biobambam2 "##METRICS" and Picard "## METRICS CLASS"), handling undefined values
("?"/empty -> error), the recursive search for a sample's files, the SampleMetrics
assembly, a missing optional GcBias, and an error when a required file is missing.
"""

import pytest

from vargate.parsers import (
    _as_float,
    find_sample_files,
    load_sample,
    parse_alignment,
    parse_gcbias,
    parse_insert,
    parse_markdup,
    parse_wgs,
)


def test_parse_wgs(pair_dir):
    wgs = parse_wgs(pair_dir / "T1.wgs_metrics.txt")
    assert wgs == {
        "median_coverage": 40.0,
        "pct_20x": 0.95,
        "fold80": 1.10,
        "pct_exc_mapq": 0.05,
    }


def test_parse_alignment_picks_pair_row(pair_dir):
    ali = parse_alignment(pair_dir / "T1.alignment_summary_metrics.txt")
    assert ali == {
        "align_rate": 0.990,
        "chimera_rate": 0.010,
        "mismatch_rate": 0.005,
    }


def test_parse_insert_stops_before_histogram(pair_dir):
    ins = parse_insert(pair_dir / "T1.insert_size_metrics.txt")
    assert ins == {"insert_median": 420.0, "insert_sd": 140.0}


def test_parse_markdup_biobambam2_marker(pair_dir):
    dup = parse_markdup(pair_dir / "T1.markdup_metrics.txt")
    assert dup == {"dup_rate": 0.060}


def test_parse_markdup_picard_marker(tmp_path):
    f = tmp_path / "s.markdup_metrics.txt"
    f.write_text(
        "## METRICS CLASS\tpicard.sam.DuplicationMetrics\n"
        "LIBRARY\tPERCENT_DUPLICATION\n"
        "lib\t0.123\n"
    )
    assert parse_markdup(f) == {"dup_rate": 0.123}


def test_parse_gcbias(pair_dir):
    gcb = parse_gcbias(pair_dir / "T1.gc_bias_summary.txt")
    assert gcb == {"at_dropout": 2.0, "gc_dropout": 0.5}


@pytest.mark.parametrize("bad", ["?", "", "   "])
def test_as_float_rejects_undefined(bad):
    with pytest.raises(ValueError):
        _as_float(bad)


def test_find_sample_files_recursive(tmp_path):
    nested = tmp_path / "deep" / "PICARD"
    nested.mkdir(parents=True)
    (nested / "S.wgs_metrics.txt").write_text("x")
    found = find_sample_files("S", tmp_path)
    assert found["wgs"] == nested / "S.wgs_metrics.txt"
    assert found["alignment"] is None


def test_load_sample_assembles_metrics(pair_dir):
    s = load_sample("T1", "tumor", pair_dir)
    assert s.sample_id == "T1"
    assert s.role == "tumor"
    assert s.median_coverage == 40.0
    assert s.dup_rate == 0.060
    assert s.at_dropout == 2.0


def test_load_sample_gcbias_optional_absent(pair_dir):
    s = load_sample("N1", "normal", pair_dir)
    assert s.at_dropout is None
    assert s.gc_dropout is None


def test_load_sample_missing_required_raises(tmp_path):
    (tmp_path / "S.wgs_metrics.txt").write_text("x")
    with pytest.raises(FileNotFoundError):
        load_sample("S", "tumor", tmp_path)
