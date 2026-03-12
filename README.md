# CEO Labor Market Analysis (WRDS): Experience, Compensation, and Performance

This repository contains a full, reproducible pipeline to test whether boards overpay for prior CEO experience when market-price signals (future stock returns) are weakly linked to CEO pay.

## Research Question
Do CEOs with prior CEO experience:
1. Deliver stronger future stock performance than first-time CEOs?
2. Receive a stronger pay-performance slope (or just higher pay regardless of outcomes)?

## Data Sources (WRDS)
- **ExecuComp** (`comp.execucomp_anncomp`): CEO identity and compensation (`tdc1`, salary, bonus, equity components, age).
- **CRSP/Compustat link** (`crsp.ccmxpf_linktable`): firm-security mapping.
- **CRSP monthly stock file** (`crsp.msf`): monthly stock returns used to build forward 12-month BHAR.

## Key Variable Construction
- **Prior CEO experience**: indicator that the executive has at least one prior CEO-year in ExecuComp before year `t`.
- **Forward performance**: 12-month buy-and-hold return after fiscal-year end.

Full formulas are in `docs/formulas.md`.

## Project Structure
- `src/ceo_market_analysis.py`: end-to-end extraction, cleaning, merging, modeling, and outputs.
- `docs/formulas.md`: model equations and variable definitions.
- `output/`: generated datasets and regression summaries.

## Setup
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Configure WRDS credentials (either interactive first run or `~/.pgpass`).

## Run
```bash
python src/ceo_market_analysis.py --start-year 1994 --end-year 2023 --output-dir output
```

Optional:
```bash
python src/ceo_market_analysis.py --wrds-username YOUR_WRDS_ID
```

## Outputs
- `output/ceo_panel_enriched.parquet`: CEO-year panel with experience and forward return fields.
- `output/experience_summary.csv`: descriptive comparison by CEO experience group.
- `output/regression_results.txt`: OLS estimates with year FE and firm-clustered SE.

## Notes on Identification and Interpretation
- Prior CEO experience is observed within ExecuComp coverage; external/private CEO history may be missed.
- Regressions are observational and should be interpreted as conditional associations.
- You can extend with firm fixed effects, instrument strategies, or event-study designs around CEO hiring.
