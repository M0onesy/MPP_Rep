# MPP_Rep

This repository contains a Python research prototype for auditing and studying U.S. equity securities-lending data, CRSP matching, descriptive borrow-fee patterns, and an M0-M3 portfolio-cost prototype.

本仓库是一个面向论文复刻与机制验证的公开代码仓库。它重点保留可复现脚本、数据字典、目录说明、描述性统计图表和小型成品统计表；不包含受许可限制的原始商业数据库文件。

## What This Repository Is

- A public code and documentation release for the local `mainProj` research workspace.
- A Python prototype that processes Markit/S&P Securities Finance-style securities-lending data, CRSP daily/header files, matching outputs, and M0-M3 cost-aware portfolio experiments.
- A reproducibility scaffold: directory structure, `.gitkeep` placeholders, reports, figures, and scripts are present so the project can be rebuilt when licensed raw data are placed locally.

## What This Repository Is Not

- It is not an official JKMP full replication package.
- It does not include licensed raw data from CRSP, Compustat, Markit/S&P, Capital IQ, 13F, or related vendors.
- It does not include large generated Parquet files from `data/mid` or large panel files from `data/prod`.
- It does not claim that the full official anomaly/factor signal panel, DGTW/factor returns, R/HPC environment, or all paper inputs are complete.

## Public Data Policy

The original raw files are intentionally excluded from Git:

- `data/raw/**` is ignored, except `.gitkeep` placeholders.
- `data/mid/**` is ignored, except `.gitkeep` placeholders, because it contains generated intermediate Parquet partitions.
- Large `data/prod/**/*.parquet` files are ignored.
- Small `data/prod/*.csv` and `data/prod/*.json` summary outputs are kept to make the repository readable without shipping proprietary raw data.

This policy keeps the project structure visible while avoiding accidental publication of licensed or oversized files.

## Repository Layout

```text
.
├── data/
│   ├── raw/       # Licensed raw vendor files go here locally; public repo keeps .gitkeep only
│   ├── mid/       # Generated intermediate partitions; public repo keeps .gitkeep only
│   └── prod/      # Small CSV/JSON outputs are tracked; large Parquet files are ignored
├── docs/          # Data dictionaries, inventory reports, reproduction status, structure report
├── reports/
│   └── figures/   # Generated descriptive and prototype figures
└── scripts/       # Reproducible processing, analysis, and report-generation scripts
```

For a detailed directory guide, see [`docs/project_structure_report.md`](docs/project_structure_report.md).

## Key Documentation

- [`docs/raw_data_dictionary_and_reproduction_status.md`](docs/raw_data_dictionary_and_reproduction_status.md)
  Detailed raw-data dictionary, field explanations, reproduction status matrix, and interpretation of all existing figures.

- [`docs/raw_data_inventory_report.md`](docs/raw_data_inventory_report.md)
  Inventory of local raw files from the private workspace, including sizes, row counts, hashes, and duplicate-file notes.

- [`docs/research_pipeline_readme.md`](docs/research_pipeline_readme.md)
  Pipeline order, major outputs, modeling assumptions, figure package, and current limitations.

- [`docs/project_structure_report.md`](docs/project_structure_report.md)
  Recommended project structure, canonical outputs, non-canonical test outputs, and file-placement rules.

## Main Scripts

| Script | Purpose |
|---|---|
| `scripts/raw_data_inventory.py` | Recursively inventories `data/raw` without loading huge CSVs into memory. |
| `scripts/markit_coverage.py` | Processes securities-lending data, builds Markit coverage summaries, monthly fee tables, and Markit figures. |
| `scripts/build_crsp_panel.py` | Builds a CRSP monthly common-stock panel and joins Markit borrow-fee information. |
| `scripts/run_m0_m3_prototype.py` | Runs the M0-M3 cost-aware portfolio prototype. |
| `scripts/make_research_reports.py` | Produces research summary tables and supporting reports. |
| `scripts/make_presentation_visuals.py` | Builds presentation-oriented figures from `data/prod`. |
| `scripts/raw_data_dictionary_report.py` | Generates the raw-data dictionary, reproduction status, and figure-interpretation report. |
| `scripts/project_structure_report.py` | Generates the project-structure report. |

## Suggested Environment

The scripts are plain Python scripts. The local development environment used Python 3.12.

Install the main Python dependencies with:

```bash
pip install numpy pandas pyarrow matplotlib scipy
```

Optional:

- `pdftotext` improves extraction of local WRDS PDF field dictionaries.
- Git is required for version control.
- Large-data pipeline steps require enough disk space and memory for local Parquet generation.

## Reproduction Workflow

After cloning the public repository, place licensed raw data into the expected `data/raw` paths. The public repo preserves the directory skeleton with `.gitkeep`, but not the files themselves.

Recommended local execution order:

```bash
python scripts/raw_data_inventory.py --raw-dir data/raw --output docs/raw_data_inventory_report.md
python scripts/markit_coverage.py --input "data/raw/American Equities.csv" --rebuild
python scripts/build_crsp_panel.py --rebuild
python scripts/run_m0_m3_prototype.py
python scripts/make_research_reports.py
python scripts/make_presentation_visuals.py
python scripts/raw_data_dictionary_report.py --no-hash
python scripts/project_structure_report.py
```

The first four computational steps require private data that are not included in this repository. Documentation-generation steps can be rerun only after the expected local outputs exist.

## Expected Local Raw Inputs

The private workspace used these categories of source files:

- Markit/S&P Securities Finance American Equities.
- CRSP daily stock files and stock header information.
- CRSP distribution and delisting files.
- Compustat quarterly fundamentals.
- CCM-like link table.
- Compustat supplemental short interest.
- 13F institutional holdings files.
- Capital IQ Key Developments.

The exact local inventory and field explanations are documented in [`docs/raw_data_dictionary_and_reproduction_status.md`](docs/raw_data_dictionary_and_reproduction_status.md).

## Tracked Outputs

This public repository keeps small outputs that help readers understand the current prototype:

- Markit and CRSP coverage summaries in `data/prod/*.csv` and `data/prod/*.json`.
- Prototype summary, monthly metrics, sensitivity, and metadata CSV/JSON files.
- Descriptive and presentation figures under `reports/figures`.
- Data dictionary and project-structure documentation under `docs`.

Large local outputs such as `markit_stock_monthly.parquet`, `crsp_monthly_panel.parquet`, and intermediate yearly Parquet partitions are excluded.

## Figures

The repository includes 17 PNG figures:

- Markit descriptive figures under `reports/figures/markit`.
- Presentation figures under `reports/figures/presentation`.
- Prototype cumulative-return figures under `reports/figures/prototype`.
- A historical short-test figure under `reports/figures/prototype_test3`, documented as non-canonical.

Each figure's source data, generation script, reading guide, interpretation, and limitation are explained in the figure section of [`docs/raw_data_dictionary_and_reproduction_status.md`](docs/raw_data_dictionary_and_reproduction_status.md).

## Current Research Scope

The current Python prototype focuses on:

- Borrow-fee coverage and distribution.
- Markit-CRSP matching and sample construction.
- Borrow-fee persistence and cross-sectional heterogeneity.
- A simplified M0-M3 mechanism comparison:
  - M0: no transaction costs or borrow fees.
  - M1: transaction costs included.
  - M2: M1 weights with ex-post short borrow-fee deduction.
  - M3: transaction costs and short borrow-fee costs included in the optimization objective.

The M0-M3 outputs are mechanism checks, not final official paper replication results.

## Limitations

- Official JKMP inputs such as `usa.csv`, `usa_dsf.csv`, full signal panels, factor-return files, and related metadata are not included.
- The official R/Rscript and HPC/SLURM environment is not reproduced here.
- Some vendor fields, especially non-CRSP/Compustat fields, are interpreted from field names and project usage and still require vendor dictionary confirmation.
- The public repository includes small derived summaries, but full rebuilds require locally available licensed raw data.

## Citation and Data Access

If using this repository as a research scaffold, cite the original data providers and papers according to their licensing and academic requirements. This repository does not redistribute raw vendor data and does not grant data access rights.

## License

No explicit open-source license has been added yet. Until a license file is provided, treat the code and documentation as publicly visible but not automatically relicensed for unrestricted reuse.
