"""WRDS pipeline for S&P 500 board interlock and stock-performance analysis (1993-2024)."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

try:
    import wrds
except ImportError as exc:  # pragma: no cover
    raise ImportError("wrds package is required. Install dependencies from requirements.txt") from exc


@dataclass
class AnalysisConfig:
    start_year: int = 1993
    end_year: int = 2024
    output_dir: Path = Path("output")
    director_table: str = "risk.directors"
    director_id_col: str = "dirid"
    director_gvkey_col: str = "gvkey"
    director_year_col: str = "year"
    min_board_size: int = 3


VALID_SQL_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_\.]*$")


def _validate_sql_name(name: str, label: str) -> str:
    if not VALID_SQL_NAME.match(name):
        raise ValueError(f"Invalid {label}: {name!r}. Use only letters, numbers, underscores, and dots.")
    return name


def connect_wrds(username: Optional[str]) -> wrds.Connection:
    if username:
        return wrds.Connection(wrds_username=username)
    return wrds.Connection()


def pull_sp500_membership(conn: wrds.Connection, start_year: int, end_year: int) -> pd.DataFrame:
    """Pull S&P 500 membership by firm-year using CRSP constituent history and CCM links."""
    query = f"""
        SELECT m.permno, m.start, m.ending
        FROM crsp.msp500list AS m
        WHERE m.ending >= '{start_year}-01-01'
          AND m.start <= '{end_year}-12-31'
    """
    spx = conn.raw_sql(query, date_cols=["start", "ending"])

    ccm = conn.raw_sql(
        """
        SELECT gvkey, lpermno AS permno, linkdt, linkenddt, linktype, linkprim
        FROM crsp.ccmxpf_linktable
        WHERE lpermno IS NOT NULL
          AND linktype IN ('LU', 'LC')
          AND linkprim IN ('P', 'C')
        """,
        date_cols=["linkdt", "linkenddt"],
    )
    ccm["linkenddt"] = ccm["linkenddt"].fillna(pd.Timestamp("today").normalize())

    rows: list[tuple[int, int, pd.Timestamp]] = []
    for row in spx.itertuples(index=False):
        start_year_i = max(row.start.year, start_year)
        end_year_i = min(row.ending.year, end_year)
        for year in range(start_year_i, end_year_i + 1):
            rows.append((row.permno, year, pd.Timestamp(year=year, month=12, day=31)))

    if not rows:
        return pd.DataFrame(columns=["gvkey", "permno", "year"])

    panel = pd.DataFrame(rows, columns=["permno", "year", "asof_date"]).drop_duplicates()
    panel = panel.merge(ccm[["gvkey", "permno", "linkdt", "linkenddt"]], on="permno", how="left")
    panel = panel[(panel["asof_date"] >= panel["linkdt"]) & (panel["asof_date"] <= panel["linkenddt"])].copy()
    panel["gvkey"] = panel["gvkey"].astype(str)
    return panel[["gvkey", "permno", "year"]].drop_duplicates()


def pull_director_memberships(
    conn: wrds.Connection,
    director_table: str,
    director_id_col: str,
    director_gvkey_col: str,
    director_year_col: str,
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    """Pull director-firm-year rows from a WRDS table with configurable identifiers."""
    table_name = _validate_sql_name(director_table, "director_table")
    id_col = _validate_sql_name(director_id_col, "director_id_col")
    gvkey_col = _validate_sql_name(director_gvkey_col, "director_gvkey_col")
    year_col = _validate_sql_name(director_year_col, "director_year_col")

    query = f"""
        SELECT
            CAST({gvkey_col} AS TEXT) AS gvkey,
            CAST({id_col} AS TEXT) AS director_id,
            CAST({year_col} AS INT) AS year
        FROM {table_name}
        WHERE {year_col} BETWEEN {start_year} AND {end_year}
          AND {gvkey_col} IS NOT NULL
          AND {id_col} IS NOT NULL
    """
    df = conn.raw_sql(query)
    return df.drop_duplicates()


def compute_interlock_metrics(sp500_firm_year: pd.DataFrame, director_panel: pd.DataFrame) -> pd.DataFrame:
    """Build board interlock intensity metrics by firm-year."""
    board = sp500_firm_year.merge(director_panel, on=["gvkey", "year"], how="left")
    board = board.dropna(subset=["director_id"]).drop_duplicates()
    if board.empty:
        return pd.DataFrame(
            columns=[
                "gvkey",
                "year",
                "board_size",
                "avg_outside_board_seats",
                "pct_interlocked_directors",
                "total_outside_board_seats",
            ]
        )

    seats = board.groupby(["year", "director_id"])["gvkey"].nunique().rename("n_sp500_boards").reset_index()
    board = board.merge(seats, on=["year", "director_id"], how="left")
    board["outside_seats"] = (board["n_sp500_boards"] - 1).clip(lower=0)
    board["is_interlocked"] = (board["outside_seats"] > 0).astype(int)

    return (
        board.groupby(["gvkey", "year"])
        .agg(
            board_size=("director_id", "nunique"),
            avg_outside_board_seats=("outside_seats", "mean"),
            pct_interlocked_directors=("is_interlocked", "mean"),
            total_outside_board_seats=("outside_seats", "sum"),
        )
        .reset_index()
    )


def pull_annual_returns(conn: wrds.Connection, start_year: int, end_year: int) -> pd.DataFrame:
    """Compute annual buy-and-hold returns by permno from CRSP monthly returns."""
    query = f"""
        SELECT permno, date, ret
        FROM crsp.msf
        WHERE date BETWEEN '{start_year}-01-01' AND '{end_year}-12-31'
    """
    msf = conn.raw_sql(query, date_cols=["date"])
    msf["ret"] = pd.to_numeric(msf["ret"], errors="coerce")
    msf = msf.dropna(subset=["ret"]).copy()
    msf["year"] = msf["date"].dt.year

    return (
        msf.groupby(["permno", "year"])["ret"]
        .apply(lambda s: float(np.prod(1 + s) - 1))
        .rename("annual_bhar")
        .reset_index()
    )


def build_analysis_panel(interlocks: pd.DataFrame, sp500: pd.DataFrame, annual_returns: pd.DataFrame) -> pd.DataFrame:
    panel = sp500.merge(interlocks, on=["gvkey", "year"], how="left")
    panel = panel.merge(annual_returns, on=["permno", "year"], how="left")
    panel = panel.drop_duplicates(subset=["gvkey", "year", "permno"]).copy()

    next_returns = annual_returns.rename(columns={"year": "return_year", "annual_bhar": "fwd_1y_bhar"}).copy()
    next_returns["year"] = next_returns["return_year"] - 1
    return panel.merge(next_returns[["permno", "year", "fwd_1y_bhar"]], on=["permno", "year"], how="left")


def run_regression(panel: pd.DataFrame, min_board_size: int):
    model_df = panel.dropna(
        subset=["fwd_1y_bhar", "avg_outside_board_seats", "pct_interlocked_directors", "board_size"]
    ).copy()
    model_df = model_df[model_df["board_size"] >= min_board_size].copy()
    if model_df.empty:
        raise ValueError("No observations available for regression after filtering.")

    formula = "fwd_1y_bhar ~ avg_outside_board_seats + pct_interlocked_directors + board_size + C(year)"
    model = smf.ols(formula, data=model_df).fit(cov_type="cluster", cov_kwds={"groups": model_df["gvkey"]})
    return model, model_df


def classify_effect(model) -> str:
    coef = model.params.get("avg_outside_board_seats", np.nan)
    pval = model.pvalues.get("avg_outside_board_seats", np.nan)
    if np.isnan(coef) or np.isnan(pval) or pval >= 0.05:
        return "No statistically significant effect"
    if coef > 0:
        return "Helps stock performance"
    return "Hurts stock performance"


def save_outputs(panel: pd.DataFrame, model_df: pd.DataFrame, model, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(output_dir / "sp500_board_interlock_panel.parquet", index=False)

    summary = (
        model_df.groupby("year")
        .agg(
            n_firms=("gvkey", "nunique"),
            mean_fwd_1y_bhar=("fwd_1y_bhar", "mean"),
            mean_interlock=("avg_outside_board_seats", "mean"),
            mean_pct_interlocked=("pct_interlocked_directors", "mean"),
        )
        .reset_index()
    )
    summary.to_csv(output_dir / "board_interlock_yearly_summary.csv", index=False)

    with open(output_dir / "board_interlock_regression.txt", "w", encoding="utf-8") as f:
        f.write("S&P 500 BOARD INTERLOCKEDNESS AND FUTURE STOCK PERFORMANCE\n")
        f.write(model.summary().as_text())
        f.write("\n\nINTERPRETATION\n")
        f.write(classify_effect(model))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="S&P 500 board interconnectedness analysis using WRDS")
    parser.add_argument("--wrds-username", default=None)
    parser.add_argument("--start-year", type=int, default=1993)
    parser.add_argument("--end-year", type=int, default=2024)
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--director-table", default="risk.directors")
    parser.add_argument("--director-id-col", default="dirid")
    parser.add_argument("--director-gvkey-col", default="gvkey")
    parser.add_argument("--director-year-col", default="year")
    parser.add_argument("--min-board-size", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = AnalysisConfig(
        start_year=args.start_year,
        end_year=args.end_year,
        output_dir=Path(args.output_dir),
        director_table=args.director_table,
        director_id_col=args.director_id_col,
        director_gvkey_col=args.director_gvkey_col,
        director_year_col=args.director_year_col,
        min_board_size=args.min_board_size,
    )

    conn = connect_wrds(args.wrds_username)
    try:
        sp500 = pull_sp500_membership(conn, cfg.start_year, cfg.end_year)
        directors = pull_director_memberships(
            conn,
            cfg.director_table,
            cfg.director_id_col,
            cfg.director_gvkey_col,
            cfg.director_year_col,
            cfg.start_year,
            cfg.end_year,
        )
        interlocks = compute_interlock_metrics(sp500, directors)
        annual_returns = pull_annual_returns(conn, cfg.start_year, cfg.end_year + 1)
        panel = build_analysis_panel(interlocks, sp500, annual_returns)
        model, model_df = run_regression(panel, cfg.min_board_size)
        save_outputs(panel, model_df, model, cfg.output_dir)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
