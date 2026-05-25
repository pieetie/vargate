<h1>
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/pieetie/vargate/main/docs/assets/vector-svg/logo-dark-bg.svg">
  <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/pieetie/vargate/main/docs/assets/vector-svg/logo-black-transparent.svg">
  <img src="https://raw.githubusercontent.com/pieetie/vargate/main/docs/assets/vector-svg/logo-black-transparent.svg" alt="VarGate logo" width="450">
</picture>
</h1>

### Turn post-alignment QC metrics into a PASS / WARN / FAIL verdict you can act on

[![PyPI version](https://img.shields.io/pypi/v/vargate.svg)](https://pypi.org/project/vargate/)
[![License](https://img.shields.io/pypi/l/vargate)](https://github.com/pieetie/vargate/blob/main/LICENSE)

---

**VarGate** reads post-alignment QC metrics (Picard + biobambam2 markdup) for one tumor/normal pair and returns an actionable verdict (PASS / WARN / FAIL), calibrated via a YAML profile for the downstream analysis.

It was built for somatic variant calling and defaults to that workflow, but YAML profiles allow thresholds and rules to be customized for other workflows. It processes one patient at a time and fits into Snakemake loops over wildcards.

<p align="center">
  <img src="https://raw.githubusercontent.com/pieetie/vargate/main/docs/assets/preview/preview.png" alt="VarGate QC report preview" width="800" style="border-radius: 12px;">
</p>

VarGate ingests Picard `CollectWgsMetrics`, `CollectAlignmentSummaryMetrics`, `CollectInsertSizeMetrics`, and optionally `CollectGcBiasMetrics`, plus biobambam2 `bammarkduplicates2`, and writes a self-contained HTML report and a TSV summary.

Custom profiles can be added under `src/vargate/profiles/`.

## Installation

```bash
pip install vargate
```

Or from source:

```bash
git clone https://github.com/pieetie/vargate
cd vargate
pip install -e ".[dev]"
```

## Quick start

```bash
vargate \
  --tumor  T1 \
  --normal N1 \
  --input  metrics/ \
  --output patient1_qc \
  --label  "Patient 1"
```

Produces `patient1_qc.html` (self-contained report) and `patient1_qc.tsv`.

## Credits

- **Logo and visual identity** - [Elisa Perrin](https://www.linkedin.com/in/elisaperrin/)
- **Claude** (Anthropic) - assisted with tests, documentation, refactoring, HTML report styling, script cleanup, and CLI extensions to cover more use cases

## License

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/pieetie/vargate/main/docs/assets/png/logo-05.png">
  <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/pieetie/vargate/main/docs/assets/png/logo-08.png">
  <img src="https://raw.githubusercontent.com/pieetie/vargate/main/docs/assets/png/logo-08.png" alt="VarGate icon" width="14" style="vertical-align: -1px; border-radius: 3px;">
</picture> Distributed under the <a href="./LICENSE">MIT License</a>.
