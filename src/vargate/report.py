"""
HTML and TSV rendering for a patient's scoring result
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

import jinja2

from . import __version__
from .scoring import (
    COLOR_DARK_GREEN,
    COLOR_LIGHT_GREEN,
    GREEN,
    ORANGE,
    RED,
    PatientResult,
    SampleResult,
)


TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

_VERDICT_CLASS = {GREEN: "v-pass", ORANGE: "v-warn", RED: "v-fail"}


# --------------------------------------------------------------------------- #
# HTML
# --------------------------------------------------------------------------- #

def _square_color(sr: SampleResult) -> str:
    """
    Pick the overview-square color from the worst metric of the sample
    Mirrors the verdict severity, but downgrades from dark to light green
    when the comfort is below a small threshold (mirrors the per-metric
    light/dark distinction at sample level)
    """
    if sr.verdict == ORANGE:
        return "orange"
    if sr.verdict > ORANGE:
        return "red"
    # GREEN: dark when comfortable, light when just barely
    return "dark-green" if sr.comfort >= 97 else "light-green"


def _sample_ctx(sr: SampleResult) -> dict:
    return {
        "sample_id":     sr.sample.sample_id,
        "role":          sr.sample.role,
        "verdict_label": sr.verdict_label,
        "verdict_class": _VERDICT_CLASS[sr.verdict],
        "comfort":       sr.comfort,
        "n_green":       sr.n_green,
        "n_total":       sr.n_total,
        "square_color":  _square_color(sr),
        "rows":          sr.rows,
    }


def render_html(patient: PatientResult, *, profile: dict, label: str) -> str:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=jinja2.select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("report.html.j2")

    report_cfg = profile.get("report", {})
    title = report_cfg.get("title", "VarGate")

    return template.render(
        title=title,
        version=__version__,
        profile_name=profile.get("profile", "unknown"),
        label=label,
        samples=[_sample_ctx(patient.tumor), _sample_ctx(patient.normal)],
        patient={
            "verdict_label": patient.verdict_label,
            "verdict_class": _VERDICT_CLASS[patient.verdict],
            "weakest_role":  patient.weakest_role,
        },
    )


def write_html(patient: PatientResult, profile: dict, label: str, output_path: Path) -> None:
    html = render_html(patient, profile=profile, label=label)
    output_path.write_text(html, encoding="utf-8")


# --------------------------------------------------------------------------- #
# TSV
# --------------------------------------------------------------------------- #

def _tsv_rows(patient: PatientResult, profile: dict) -> Iterable[dict]:
    metric_names = list(profile["metrics"].keys())
    for sr in (patient.tumor, patient.normal):
        row = {
            "sample_id":      sr.sample.sample_id,
            "role":           sr.sample.role,
            "sample_verdict": sr.verdict_label,
            "comfort_pct":    sr.comfort,
            "n_green":        sr.n_green,
            "n_total":        sr.n_total,
            "patient_verdict": patient.verdict_label,
        }
        by_name = {r.name: r for r in sr.rows}
        for name in metric_names:
            r = by_name.get(name)
            if r is None or r.value is None:
                row[f"{name}__value"] = ""
                row[f"{name}__color"] = "na"
            else:
                row[f"{name}__value"] = r.value
                row[f"{name}__color"] = r.color
        yield row


def write_tsv(patient: PatientResult, profile: dict, output_path: Path) -> None:
    rows = list(_tsv_rows(patient, profile))
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t",
                                quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(rows)


# --------------------------------------------------------------------------- #
# Stdout summary
# --------------------------------------------------------------------------- #

def stdout_summary(patient: PatientResult) -> str:
    """
    Compact human-readable summary, one block per sample + patient line

    + Always printed to stdout by the CLI -> Snakemake captures it in logs
    """
    lines: list[str] = []
    for sr in (patient.tumor, patient.normal):
        lines.append(
            f"{sr.sample.sample_id} ({sr.sample.role:<6}) -> {sr.verdict_label}  "
            f"comfort={sr.comfort}%  green={sr.n_green}/{sr.n_total}"
        )
        flagged = [r for r in sr.rows
                   if r.color not in (COLOR_DARK_GREEN, COLOR_LIGHT_GREEN, None)]
        for r in flagged:
            lines.append(f"    [{r.color:<6}] {r.weight:<8} {r.label:<22} {r.formatted}")
    lines.append("")
    lines.append(f"PATIENT VERDICT: {patient.verdict_label}")
    if patient.weakest_role:
        lines.append(f"  driven by: {patient.weakest_role} sample")
    return "\n".join(lines)
