"""
CLI entry point. 
One tumor/normal pair = one invocation = one patient.
Designed to be looped over by Snakemake wildcards.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .parsers import load_sample
from .profile import load_profile
from .report import stdout_summary, write_html, write_tsv
from .scoring import GREEN, ORANGE, RED, patient_verdict, score_sample


_FAIL_LEVEL = {"red": RED, "orange": ORANGE, "fail": RED, "warn": ORANGE}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="vargate",
        description="Context-aware QC scoring for variant calling. "
                    "Reads Picard + biobambam2 markdup outputs for one tumor/normal "
                    "pair and emits a HTML report + TSV, with an actionable verdict.",
    )
    p.add_argument("--tumor",  required=True, help="Tumor sample ID (file prefix).")
    p.add_argument("--normal", required=True, help="Normal sample ID (file prefix).")
    p.add_argument("--input",  required=True, type=Path,
                   help="Directory containing the QC files (searched recursively).")
    p.add_argument("--output", required=True, type=Path,
                   help="Output prefix. Writes {prefix}.html and {prefix}.tsv.")
    p.add_argument("--profile", default="sv_somatic",
                   help="Packaged profile name (default: sv_somatic).")
    p.add_argument("--config", type=Path, default=None,
                   help="Path to a custom profile YAML (overrides --profile).")
    p.add_argument("--set", dest="overrides", action="append", default=[],
                   metavar="DOTTED.PATH=VALUE",
                   help="Override a single profile key, e.g. "
                        "'metrics.dup_rate.thresholds.green=0.05'. Repeatable.")
    p.add_argument("--label", default=None,
                   help="Free-text patient/run label shown in the report. "
                        "Defaults to the profile's report.default_label.")
    p.add_argument("--fail-on", choices=("red", "orange", "fail", "warn"),
                   default=None,
                   help="If the PATIENT verdict reaches this level, exit non-zero. "
                        "'red'/'fail' = exit 2 on FAIL. 'orange'/'warn' = exit 1 on WARN or worse.")
    p.add_argument("--no-html", action="store_true", help="Skip the HTML output.")
    p.add_argument("--no-tsv",  action="store_true", help="Skip the TSV output.")
    p.add_argument("--quiet",   action="store_true",
                   help="Do not print the stdout summary.")
    p.add_argument("--version", action="version", version=f"vargate {__version__}")
    return p


def _exit_code_for(patient_verdict_severity: int, fail_on: str | None) -> int:
    if fail_on is None:
        return 0
    threshold = _FAIL_LEVEL[fail_on]
    return 0 if patient_verdict_severity < threshold else (1 if threshold == ORANGE else 2)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.input.is_dir():
        print(f"error: --input {args.input} is not a directory", file=sys.stderr)
        return 2

    profile = load_profile(
        profile_name=args.profile,
        config_path=args.config,
        overrides=args.overrides,
    )

    label = args.label or profile.get("report", {}).get("default_label", "Sample QC report")

    try:
        tumor  = load_sample(args.tumor,  "tumor",  args.input)
        normal = load_sample(args.normal, "normal", args.input)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    tr = score_sample(tumor,  profile)
    nr = score_sample(normal, profile)
    patient = patient_verdict(tr, nr)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not args.no_html:
        write_html(patient, profile, label, args.output.with_suffix(".html"))
    if not args.no_tsv:
        write_tsv(patient, profile, args.output.with_suffix(".tsv"))

    if not args.quiet:
        print(stdout_summary(patient))

    return _exit_code_for(patient.verdict, args.fail_on)


if __name__ == "__main__":
    sys.exit(main())
