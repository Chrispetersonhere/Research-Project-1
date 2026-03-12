# CEO Labor Market Analysis (WRDS): Experience, Compensation, and Performance

This repository contains reproducible WRDS pipelines for two related corporate-governance projects:
1. CEO experience, compensation, and forward stock performance.
2. S&P 500 board interconnectedness (director interlocks) and forward stock performance.

## Research Questions
### CEO labor market
Do CEOs with prior CEO experience:
1. Deliver stronger future stock performance than first-time CEOs?
2. Receive a stronger pay-performance slope (or just higher pay regardless of outcomes)?

### Board interconnectedness
For S&P 500 firms (1993-2024), do boards with more directors who also sit on other S&P 500 boards have better, worse, or similar future stock performance?

## Data Sources (WRDS)
- **ExecuComp** (`comp.execucomp_anncomp`): CEO identity and compensation (`tdc1`, salary, bonus, equity components, age).
- **CRSP/Compustat link** (`crsp.ccmxpf_linktable`): firm-security mapping.
- **CRSP monthly stock file** (`crsp.msf`): monthly stock returns used to build annual and forward returns.
- **CRSP S&P 500 constituents** (`crsp.msp500list`): historical S&P 500 membership.
- **Directors table** (default `risk.directors`): director-firm-year memberships used to compute interlocks. You can override table/column names via CLI flags.

## Project Structure
- `src/ceo_market_analysis.py`: CEO extraction, cleaning, merging, modeling, and outputs.
- `src/board_interconnectedness_analysis.py`: S&P 500 board-interlock pipeline and regression outputs.
- `docs/formulas.md`: model equations and variable definitions.
- `output/`: generated datasets and regression summaries.

## Setup
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Configure WRDS credentials (either interactive first run or `~/.pgpass`).

## Run
### CEO analysis
```bash
python src/ceo_market_analysis.py --start-year 1994 --end-year 2023 --output-dir output
```

### Board interconnectedness analysis (S&P 500, 1993-2024)
```bash
python src/board_interconnectedness_analysis.py --start-year 1993 --end-year 2024 --output-dir output
```

If your WRDS directors table has different names (identifiers are validated before query construction):
```bash
python src/board_interconnectedness_analysis.py \
  --director-table your_schema.your_table \
  --director-id-col your_director_id \
  --director-gvkey-col your_gvkey \
  --director-year-col your_year \
  --min-board-size 3
```

## Outputs
### CEO pipeline
- `output/ceo_panel_enriched.parquet`: CEO-year panel with experience and forward return fields.
- `output/experience_summary.csv`: descriptive comparison by CEO experience group.
- `output/regression_results.txt`: OLS estimates with year FE and firm-clustered SE.

### Board pipeline
- `output/sp500_board_interlock_panel.parquet`: firm-year panel with interlock and return fields.
- `output/board_interlock_yearly_summary.csv`: yearly means of interlock intensity and returns (after board-size filter used for estimation).
- `output/board_interlock_regression.txt`: regression output and interpretation (`helps`, `hurts`, or `no statistically significant effect`).

## Notes on Identification and Interpretation
- Director coverage depends on your WRDS directors source and can vary by years/firms.
- Interlocks are measured inside the observed S&P 500 firm-year sample.
- Regressions are observational and should be interpreted as conditional associations.

## PR Targeting (avoid opening PRs in the wrong repository)
Before creating a pull request from this local checkout, verify that `origin` points to the intended GitHub repo:

```bash
git remote -v
```

If `origin` is not the repo you want, set it explicitly (example for Research-Project-2):

```bash
git remote remove origin
git remote add origin https://github.com/Chrispetersonhere/Research-Project-2.git
git remote -v
```

This check helps ensure PR tooling uses the correct destination repository.
