"""
Per-metric classification, per-sample scoring, patient-level verdict

The verdict uses the *weakest-link, weighted* rule:
  - a critical metric in RED  -> sample is RED
  - a major metric in RED     -> sample is at worst ORANGE
  - a minor metric            -> displayed, but never affects the verdict 
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean
from typing import Optional

from .model import SampleMetrics
from .profile import scale_of, thr_of


# Severity ordering. Use these instead of bare strings inside the engine.
GREEN, ORANGE, RED = 0, 1, 2

# Four UI colors. Two greens (dark / light), one orange, one red.
COLOR_DARK_GREEN  = "dark_green"
COLOR_LIGHT_GREEN = "light_green"
COLOR_ORANGE      = "orange"
COLOR_RED         = "red"

_SEVERITY = {
    COLOR_DARK_GREEN:  GREEN,
    COLOR_LIGHT_GREEN: GREEN,
    COLOR_ORANGE:      ORANGE,
    COLOR_RED:         RED,
}

_VERDICT_LABEL = {GREEN: "PASS", ORANGE: "WARN", RED: "FAIL"}


# --------------------------------------------------------------------------- #
# Per-metric classification
# --------------------------------------------------------------------------- #

def classify(value: float, metric_spec: dict, role: str, tolerance: float) -> str:
    """
    Return one of dark_green / light_green / orange / red
    """
    direction = metric_spec["direction"]
    thr = thr_of(metric_spec, role)
    lo, hi = scale_of(metric_spec, role)

    if direction == "higher_better":
        g, o = thr["green"], thr["orange"]
        if value >= g:
            return COLOR_LIGHT_GREEN if value < g + tolerance * max(hi - g, 0) else COLOR_DARK_GREEN
        return COLOR_ORANGE if value >= o else COLOR_RED

    if direction == "lower_better":
        g, o = thr["green"], thr["orange"]
        if value <= g:
            return COLOR_LIGHT_GREEN if value > g - tolerance * max(g - lo, 0) else COLOR_DARK_GREEN
        return COLOR_ORANGE if value <= o else COLOR_RED

    # band
    g_lo, g_hi = thr["green"]
    o_lo, o_hi = thr["orange"]
    if g_lo <= value <= g_hi:
        span = (g_hi - g_lo) * tolerance
        if value < g_lo + span or value > g_hi - span:
            return COLOR_LIGHT_GREEN
        return COLOR_DARK_GREEN
    if o_lo <= value <= o_hi:
        return COLOR_ORANGE
    return COLOR_RED


def severity_of(color: str) -> int:
    return _SEVERITY[color]


# --------------------------------------------------------------------------- #
# Display helpers (also reused by the HTML renderer)
# --------------------------------------------------------------------------- #

def pos_pct(value: float, lo: float, hi: float) -> float:
    """
    Map `value` into [0, 100] for the display scale [lo, hi], clamped
    """
    if hi == lo:
        return 0.0
    p = (value - lo) / (hi - lo) * 100.0
    return max(0.0, min(100.0, p))


def zones(metric_spec: dict, role: str) -> tuple[list[tuple[float, float, str]], list[float]]:
    """
    Return the colored segments (start%, end%, kind) and threshold markers
    """
    direction = metric_spec["direction"]
    thr = thr_of(metric_spec, role)
    lo, hi = scale_of(metric_spec, role)
    p = lambda x: pos_pct(x, lo, hi)

    if direction == "higher_better":
        g, o = thr["green"], thr["orange"]
        segs = [(p(lo), p(o), "red"), (p(o), p(g), "orange"), (p(g), p(hi), "green")]
        marks = [g]
    elif direction == "lower_better":
        g, o = thr["green"], thr["orange"]
        segs = [(p(lo), p(g), "green"), (p(g), p(o), "orange"), (p(o), p(hi), "red")]
        marks = [g]
    else:
        g_lo, g_hi = thr["green"]
        o_lo, o_hi = thr["orange"]
        segs = [
            (p(lo),  p(o_lo), "red"),
            (p(o_lo), p(g_lo), "orange"),
            (p(g_lo), p(g_hi), "green"),
            (p(g_hi), p(o_hi), "orange"),
            (p(o_hi), p(hi),  "red"),
        ]
        marks = [g_lo, g_hi]

    segs = [(a, b, k) for a, b, k in segs if b - a > 0.01]
    return segs, [p(m) for m in marks]


# --------------------------------------------------------------------------- #
# Per-sample scoring
# --------------------------------------------------------------------------- #

@dataclass
class MetricResult:
    name: str
    label: str
    weight: str
    direction: str
    value: Optional[float]
    color: Optional[str]                 # None when n/a (optional + missing)
    formatted: str                       # display string
    segs: list                           # [(start%, end%, kind), ...]
    marks: list                          # [pos%, ...]
    vpos: Optional[float]                # marker position in %


@dataclass
class SampleResult:
    sample: SampleMetrics
    rows: list = field(default_factory=list)
    verdict: int = GREEN                 # GREEN / ORANGE / RED
    comfort: float = 0.0                 # in percent
    n_green: int = 0
    n_total: int = 0                     # scored (not n/a)

    @property
    def verdict_label(self) -> str:
        return _VERDICT_LABEL[self.verdict]


def score_sample(sample: SampleMetrics, profile: dict) -> SampleResult:
    """
    Apply the profile to a single sample
    Returns a SampleResult
    """
    comfort_params = profile.get("comfort", {})
    tol = float(comfort_params.get("tolerance", 0.15))
    cw = comfort_params.get("weights", {
        "dark_green":  1.0,
        "light_green": 0.9,
        "orange":      0.5,
        "red":         0.0,
    })

    result = SampleResult(sample=sample)
    comfort_vals: list[float] = []

    for name, spec in profile["metrics"].items():
        value = sample.metric_value(name)

        if value is None:
            if spec.get("optional"):
                result.rows.append(MetricResult(
                    name=name, label=spec.get("label", name), weight=spec["weight"],
                    direction=spec["direction"], value=None, color=None,
                    formatted="n/a", segs=[], marks=[], vpos=None,
                ))
                continue
            raise ValueError(f"metric {name!r} is required but missing for {sample.sample_id}")

        color = classify(value, spec, sample.role, tol)
        sev = severity_of(color)
        comfort_vals.append(float(cw.get(color, 0.0)))

        # Aggregate verdict
        if spec["weight"] == "critical":
            result.verdict = max(result.verdict, sev)
        elif spec["weight"] == "major":
            result.verdict = max(result.verdict, min(sev, ORANGE))
        # minor: no effect

        # Display computations
        segs, marks = zones(spec, sample.role)
        lo, hi = scale_of(spec, sample.role)
        fmt = spec.get("format", "{}")
        try:
            formatted = fmt.format(value)
        except (ValueError, TypeError):
            formatted = str(value)

        result.rows.append(MetricResult(
            name=name, label=spec.get("label", name), weight=spec["weight"],
            direction=spec["direction"], value=value, color=color,
            formatted=formatted, segs=segs, marks=marks,
            vpos=pos_pct(value, lo, hi),
        ))

        if color in (COLOR_DARK_GREEN, COLOR_LIGHT_GREEN):
            result.n_green += 1
        result.n_total += 1

    if comfort_vals:
        result.comfort = round(mean(comfort_vals) * 100)
    return result


# --------------------------------------------------------------------------- #
# Patient verdict (worst of tumor + normal)
# --------------------------------------------------------------------------- #

@dataclass
class PatientResult:
    tumor: SampleResult
    normal: SampleResult
    verdict: int = GREEN

    @property
    def verdict_label(self) -> str:
        return _VERDICT_LABEL[self.verdict]

    @property
    def weakest_role(self) -> Optional[str]:
        """
        Which sample drives the patient verdict
        None if both PASS
        """
        if self.tumor.verdict > self.normal.verdict:
            return "tumor"
        if self.normal.verdict > self.tumor.verdict:
            return "normal"
        if self.verdict == GREEN:
            return None
        return "both"


def patient_verdict(tumor: SampleResult, normal: SampleResult) -> PatientResult:
    return PatientResult(
        tumor=tumor,
        normal=normal,
        verdict=max(tumor.verdict, normal.verdict),
    )
