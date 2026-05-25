"""
Covers the CLI end to end on the fixture pair: a normal run -> exit 0 and writing
{prefix}.html + {prefix}.tsv, the --no-html / --no-tsv / --quiet flags, an invalid
input or a missing sample -> exit 2, and the _exit_code_for exit-code matrix
(--fail-on red/warn) plus a real --fail-on run that forces a FAIL via --set.
"""

import pytest

from vargate.cli import _exit_code_for, main
from vargate.scoring import GREEN, ORANGE, RED


def _args(pair_dir, out, *extra):
    return ["--tumor", "T1", "--normal", "N1",
            "--input", str(pair_dir), "--output", str(out), *extra]


def test_run_writes_html_and_tsv(pair_dir, tmp_path):
    out = tmp_path / "qc"
    code = main(_args(pair_dir, out, "--quiet"))
    assert code == 0
    assert out.with_suffix(".html").exists()
    assert out.with_suffix(".tsv").exists()


def test_no_html_no_tsv(pair_dir, tmp_path):
    out = tmp_path / "qc"
    main(_args(pair_dir, out, "--quiet", "--no-html", "--no-tsv"))
    assert not out.with_suffix(".html").exists()
    assert not out.with_suffix(".tsv").exists()


def test_quiet_suppresses_stdout(pair_dir, tmp_path, capsys):
    main(_args(pair_dir, tmp_path / "qc", "--quiet"))
    assert capsys.readouterr().out == ""


def test_invalid_input_dir_returns_2(tmp_path):
    code = main(["--tumor", "T1", "--normal", "N1",
                 "--input", str(tmp_path / "nope"), "--output", str(tmp_path / "qc")])
    assert code == 2


def test_missing_sample_returns_2(pair_dir, tmp_path):
    code = main(["--tumor", "GHOST", "--normal", "N1",
                 "--input", str(pair_dir), "--output", str(tmp_path / "qc"), "--quiet"])
    assert code == 2


def test_fail_on_red_exits_nonzero(pair_dir, tmp_path):
    out = tmp_path / "qc"
    code = main(_args(pair_dir, out, "--quiet", "--fail-on", "red",
                      "--set", "metrics.chimera_rate.thresholds.green=0.001",
                      "--set", "metrics.chimera_rate.thresholds.orange=0.002"))
    assert code == 2


@pytest.mark.parametrize("verdict,fail_on,expected", [
    (GREEN, None, 0),
    (RED, None, 0),
    (GREEN, "red", 0),
    (ORANGE, "red", 0),
    (RED, "red", 2),
    (GREEN, "warn", 0),
    (ORANGE, "warn", 1),
    (RED, "warn", 1),
])
def test_exit_code_matrix(verdict, fail_on, expected):
    assert _exit_code_for(verdict, fail_on) == expected
