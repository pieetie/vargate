"""
Profile loading and (CLI) overriding

A profile is a dict loaded from YAML
The user can override the whole profile file with --config /path/to/custom.yaml, or override
individual thresholds / comfort params via --set 'metrics.dup_rate.thresholds.green=0.05'
"""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any, Optional

import yaml

PROFILES_DIR = Path(__file__).resolve().parent / "profiles"


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #

def packaged_profile_path(profile_name: str) -> Path:
    """
    Path to a shipped profile YAML
    """
    p = PROFILES_DIR / f"{profile_name}.yaml"
    if not p.exists():
        available = sorted(x.stem for x in PROFILES_DIR.glob("*.yaml"))
        raise FileNotFoundError(
            f"profile {profile_name!r} not found in {PROFILES_DIR}. "
            f"Available: {', '.join(available) or '(none)'}"
        )
    return p


def load_profile(
    profile_name: str = "sv_somatic",
    config_path: Optional[Path] = None,
    overrides: Optional[list[str]] = None,
) -> dict:
    """
    Load a profile and apply CLI overrides

    Priority (highest wins):
      1. --set k=v overrides (dotted-path)
      2. --config path (full profile file)
      3. packaged profile by name
    """
    path = Path(config_path) if config_path else packaged_profile_path(profile_name)
    with path.open() as f:
        profile = yaml.safe_load(f)

    if not isinstance(profile, dict):
        raise ValueError(f"{path}: profile must be a mapping at the top level")

    if overrides:
        for spec in overrides:
            apply_override(profile, spec)

    validate(profile)
    return profile


# --------------------------------------------------------------------------- #
# CLI override (dotted path, e.g. metrics.dup_rate.thresholds.green=0.05)
# --------------------------------------------------------------------------- #

_NUM_RE = re.compile(r"^-?\d+(\.\d+)?$")


def _cast(value: str) -> Any:
    """
    Parse '0.05' / '30' / 'true' / 'critical' from the CLI
    """
    v = value.strip()
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    if _NUM_RE.match(v):
        return float(v) if "." in v else int(v)
    return v


def apply_override(profile: dict, spec: str) -> None:
    """
    Apply a single 'a.b.c=value' override, mutating `profile`
    """
    if "=" not in spec:
        raise ValueError(f"--set expects KEY=VALUE, got {spec!r}")
    path, raw_value = spec.split("=", 1)
    keys = path.strip().split(".")
    value = _cast(raw_value)

    node = profile
    for key in keys[:-1]:
        if not isinstance(node, dict) or key not in node:
            raise KeyError(f"override path {path!r}: key {key!r} not in profile")
        node = node[key]
    if not isinstance(node, dict):
        raise KeyError(f"override path {path!r}: parent is not a mapping")
    node[keys[-1]] = value


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #

_VALID_WEIGHTS = {"critical", "major", "minor"}
_VALID_DIRECTIONS = {"higher_better", "lower_better", "band"}


def validate(profile: dict) -> None:
    """
    Raise ValueError on a malformed profile

    Checks structural correctness only, does not check that thresholds are
    biologically sensible (that is a human-review concern)
    """
    if "metrics" not in profile or not isinstance(profile["metrics"], dict):
        raise ValueError("profile: top-level 'metrics' mapping is required")

    for name, spec in profile["metrics"].items():
        ctx = f"metric {name!r}"
        if not isinstance(spec, dict):
            raise ValueError(f"{ctx}: must be a mapping")
        if spec.get("weight") not in _VALID_WEIGHTS:
            raise ValueError(f"{ctx}: weight must be one of {sorted(_VALID_WEIGHTS)}")
        if spec.get("direction") not in _VALID_DIRECTIONS:
            raise ValueError(f"{ctx}: direction must be one of {sorted(_VALID_DIRECTIONS)}")
        thr = spec.get("thresholds")
        if not isinstance(thr, dict):
            raise ValueError(f"{ctx}: thresholds must be a mapping")
        if spec["direction"] == "band":
            g = thr.get("green")
            o = thr.get("orange")
            if not (isinstance(g, list) and isinstance(o, list) and len(g) == 2 and len(o) == 2):
                raise ValueError(f"{ctx}: band thresholds must be 2-element lists")
            if not (o[0] <= g[0] <= g[1] <= o[1]):
                raise ValueError(
                    f"{ctx}: band thresholds must satisfy "
                    f"orange.lo <= green.lo <= green.hi <= orange.hi"
                )


# --------------------------------------------------------------------------- #
# Convenience accessors
# --------------------------------------------------------------------------- #

def thr_of(metric_spec: dict, role: str) -> dict:
    """
    Return the threshold dict for a role-aware or role-agnostic metric
    """
    if metric_spec.get("role_specific"):
        return metric_spec["thresholds"][role]
    return metric_spec["thresholds"]


def scale_of(metric_spec: dict, role: str) -> tuple[float, float]:
    """
    Return the display scale [lo, hi] for a role
    """
    s = metric_spec.get("scale")
    if s is None:
        return (0.0, 1.0)
    if metric_spec.get("role_specific"):
        s = s[role]
    return (float(s[0]), float(s[1]))


def clone(profile: dict) -> dict:
    """
    Deep-copy a profile (useful when test-mutating)
    """
    return copy.deepcopy(profile)
