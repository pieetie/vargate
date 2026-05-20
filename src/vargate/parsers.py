"""
PicardQC + biobambam2 metrics file parsers
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .model import SampleMetrics, Role


# --------------------------------------------------------------------------- #
# Low-level helpers
# --------------------------------------------------------------------------- #

def _metrics_block(path: Path, marker: str = "## METRICS CLASS") -> list[dict]:
    """
    Return all data rows in the first METRICS block of a Picard-style file

    Picard files: marker is "## METRICS CLASS ..."
    biobambam2 markdup: marker is "##METRICS" (no space)
    The caller can pass that explicitly

    Stops at the next blank line or the next `##` section header
    """
    lines = path.read_text().splitlines()
    i = 0
    while i < len(lines) and not lines[i].startswith(marker):
        i += 1
    if i >= len(lines):
        raise ValueError(f"{path.name}: METRICS block not found (marker={marker!r})")
    header = lines[i + 1].split("\t")
    rows: list[dict] = []
    j = i + 2
    while j < len(lines):
        line = lines[j]
        if not line.strip():
            break
        if line.startswith("##") or line.startswith("# "):
            break
        values = line.split("\t")
        # Pad / truncate to header length (last Picard columns are often empty)
        if len(values) < len(header):
            values = values + [""] * (len(header) - len(values))
        rows.append(dict(zip(header, values)))
        j += 1
    return rows


def _as_float(value: str) -> float:
    """
    “?” → 0 only if handled 
    else raise
    """
    v = value.strip()
    if v in ("", "?"):
        raise ValueError(f"undefined metric value: {value!r}")
    return float(v)


# --------------------------------------------------------------------------- #
# Picard parsers
# --------------------------------------------------------------------------- #

def parse_wgs(path: Path) -> dict:
    """
    Picard CollectWgsMetrics -> dict with the canonical fields we score
    """
    rows = _metrics_block(path)
    if not rows:
        raise ValueError(f"{path.name}: empty METRICS block")
    r = rows[0]
    return {
        "median_coverage": _as_float(r["MEDIAN_COVERAGE"]),
        "pct_20x":         _as_float(r["PCT_20X"]),       # already a fraction
        "fold80":          _as_float(r["FOLD_80_BASE_PENALTY"]),
        "pct_exc_mapq":    _as_float(r["PCT_EXC_MAPQ"]),  # already a fraction
    }


def parse_alignment(path: Path) -> dict:
    """
    Picard CollectAlignmentSummaryMetrics -> dict (PAIR row only)
    """
    rows = _metrics_block(path)
    pair = next((r for r in rows if r.get("CATEGORY") == "PAIR"), None)
    if pair is None:
        raise ValueError(f"{path.name}: no PAIR row in alignment summary")
    return {
        "align_rate":    _as_float(pair["PCT_PF_READS_ALIGNED"]),
        "chimera_rate":  _as_float(pair["PCT_CHIMERAS"]),
        "mismatch_rate": _as_float(pair["PF_MISMATCH_RATE"]),
    }


def parse_insert(path: Path) -> dict:
    """
    Picard CollectInsertSizeMetrics -> dict (first METRICS row)
    """
    rows = _metrics_block(path)
    if not rows:
        raise ValueError(f"{path.name}: empty METRICS block")
    r = rows[0]
    return {
        "insert_median": _as_float(r["MEDIAN_INSERT_SIZE"]),
        "insert_sd":     _as_float(r["STANDARD_DEVIATION"]),
    }


def parse_gcbias(path: Path) -> dict:
    """
    Picard CollectGcBiasMetrics summary -> dict
    """
    rows = _metrics_block(path)
    if not rows:
        raise ValueError(f"{path.name}: empty METRICS block")
    r = rows[0]
    return {
        "at_dropout": _as_float(r["AT_DROPOUT"]),
        "gc_dropout": _as_float(r["GC_DROPOUT"]),
    }


# --------------------------------------------------------------------------- #
# biobambam2 / Picard MarkDuplicates parser
# --------------------------------------------------------------------------- #

def parse_markdup(path: Path) -> dict:
    """
    biobambam2 bammarkduplicates2 OR Picard MarkDuplicates -> dict
    """
    text = path.read_text()
    marker = "## METRICS CLASS" if "## METRICS CLASS" in text else "##METRICS"
    rows = _metrics_block(path, marker=marker)
    if not rows:
        raise ValueError(f"{path.name}: empty METRICS block")
    r = rows[0]
    return {
        "dup_rate": _as_float(r["PERCENT_DUPLICATION"]),  # already a fraction
    }


# --------------------------------------------------------------------------- #
# Sample assembly
# --------------------------------------------------------------------------- #

# Default filename suffixes — matches what the lab pipeline writes.
DEFAULT_SUFFIXES = {
    "wgs":       ".wgs_metrics.txt",
    "alignment": ".alignment_summary_metrics.txt",
    "insert":    ".insert_size_metrics.txt",
    "markdup":   ".markdup_metrics.txt",
    "gcbias":    ".gc_bias_summary.txt",
}


def find_sample_files(
    sample_id: str,
    input_dir: Path,
    suffixes: Optional[dict] = None,
) -> dict:
    """
    Locate the QC files for a sample under `input_dir` (custom for my use case sry)
    """
    sfx = dict(DEFAULT_SUFFIXES)
    if suffixes:
        sfx.update(suffixes)

    found: dict = {k: None for k in sfx}
    for path in input_dir.rglob(f"{sample_id}.*"):
        for kind, suffix in sfx.items():
            if path.name == f"{sample_id}{suffix}":
                found[kind] = path
                break
    return found


def load_sample(
    sample_id: str,
    role: Role,
    input_dir: Path,
    suffixes: Optional[dict] = None,
) -> SampleMetrics:
    """
    Locate, parse and assemble a SampleMetrics for one sample
    """
    files = find_sample_files(sample_id, input_dir, suffixes)

    missing = [k for k in ("wgs", "alignment", "insert", "markdup") if files[k] is None]
    if missing:
        raise FileNotFoundError(
            f"sample {sample_id!r}: missing required QC files for: {', '.join(missing)} "
            f"(searched under {input_dir})"
        )

    wgs = parse_wgs(files["wgs"])
    ali = parse_alignment(files["alignment"])
    ins = parse_insert(files["insert"])
    dup = parse_markdup(files["markdup"])
    gcb = parse_gcbias(files["gcbias"]) if files["gcbias"] else {"at_dropout": None, "gc_dropout": None}

    return SampleMetrics(
        sample_id=sample_id,
        role=role,
        **wgs,
        **ali,
        **ins,
        **dup,
        **gcb,
    )
