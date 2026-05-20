"""
Canonical sample-level QC schema
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional


Role = str  # "tumor" | "normal"


@dataclass
class SampleMetrics:
    sample_id: str
    role: Role

    # Coverage (Picard CollectWgsMetrics)
    median_coverage: float
    pct_20x: float        # fraction 0-1
    fold80: float
    pct_exc_mapq: float   # fraction 0-1

    # Insert size (Picard CollectInsertSizeMetrics)
    insert_median: float
    insert_sd: float      # CV = insert_sd / insert_median (derived in scoring)

    # Alignment (Picard CollectAlignmentSummaryMetrics, PAIR row)
    align_rate: float     # fraction 0-1
    chimera_rate: float   # fraction 0-1
    mismatch_rate: float  # fraction 0-1

    # Duplicates (biobambam2 markdup OR Picard MarkDuplicates)
    dup_rate: float       # fraction 0-1

    # GC bias (Picard CollectGcBiasMetrics — optional)
    at_dropout: Optional[float] = None
    gc_dropout: Optional[float] = None

    # Derived / convenience
    @property
    def insert_cv(self) -> float:
        if self.insert_median == 0:
            return float("inf")
        return self.insert_sd / self.insert_median

    def metric_value(self, name: str) -> Optional[float]:
        """
        Lookup a metric by canonical name used in the profile YAML
        """
        if name == "insert_cv":
            return self.insert_cv
        return getattr(self, name, None)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["insert_cv"] = self.insert_cv
        return d
