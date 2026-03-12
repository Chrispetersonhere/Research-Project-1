"""End-to-end WRDS pipeline for CEO experience, compensation, and performance analysis.

This script:
1. Pulls CEO compensation records from ExecuComp.
2. Labels CEOs with/without prior CEO experience.
3. Pulls CRSP monthly returns via CCM link table.
4. Builds forward 12-month buy-and-hold returns from fiscal-year end.
5. Runs core regressions on CEO pay-performance sensitivity and performance by experience.
6. Writes clean datasets and model summaries to disk.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

try:
    import wrds
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "wrds package is required. Install dependencies from requirements.txt"
    ) from exc


@dataclass
class AnalysisConfig:
    start_year: int = 1994
    end_year: int = 2023
    output_dir: Path = Path("output")


def connect_wrds(username: Optional[str]) -> wrds.Connection:
    """Open WRDS connection.

    If username is omitted, wrds.Connection() will use local ~/.pgpass defaults.
    """
    if username:
        return wrds.Connection(wrds_username=username)
    return wrds.Connection()


def pull_execucomp_ceos(conn: wrds.Connection, start_year: int, end_year: int) -> pd.DataFrame:
    """Pull annual CEO observations and compensation from ExecuComp."""
    query = f"""
        SELECT
            a.gvkey,
            a.fyear,
            a.datadate,
            a.execid,
            a.exec_fullname,
            a.ceoann,
            a.age,
            a.salary,
            a.bonus,
            a.noneq_incent,
            a.stock_awards,
            a.option_awards,
            a.tdc1,
            a.becameceo,
            a.leftofc
        FROM comp.execucomp_anncomp AS a
        WHERE a.fyear <= {end_year}
          AND a.ceoann = 'CEO'
          AND a.execid IS NOT NULL
          AND a.tdc1 IS NOT NULL
    """
    df = conn.raw_sql(query, date_cols=["datadate", "becameceo", "leftofc"])
    df["fyear"] = df["fyear"].astype(int)
    return df


def add_prior_ceo_experience(df: pd.DataFrame) -> pd.DataFrame:
    """Create indicator for whether executive had prior CEO-year in ExecuComp history."""
    out = df.sort_values(["execid", "fyear", "gvkey"]).copy()
    out["first_ceo_year"] = out.groupby("execid")["fyear"].transform("min")
    out["prior_ceo_experience"] = (out["fyear"] > out["first_ceo_year"]).astype(int)
    return out


def pull_ccm_links(conn: wrds.Connection) -> pd.DataFrame:
    """Pull Compustat-CRSP link table."""
    query = """
        SELECT gvkey, lpermno AS permno, linkdt, linkenddt, linktype, linkprim
        FROM crsp.ccmxpf_linktable
        WHERE lpermno IS NOT NULL
          AND linktype IN ('LU', 'LC')
          AND linkprim IN ('P', 'C')
    """
    return conn.raw_sql(query, date_cols=["linkdt", "linkenddt"])


def pull_monthly_returns(conn: wrds.Connection, start_year: int, end_year: int) -> pd.DataFrame:
    """Pull CRSP monthly returns around analysis window."""
    query = f"""
        SELECT
            m.permno,
            m.date,
            m.ret
        FROM crsp.msf AS m
        WHERE m.date BETWEEN '{start_year - 1}-01-01' AND '{end_year + 2}-12-31'
    """
    return conn.raw_sql(query, date_cols=["date"])


def merge_returns(ceos: pd.DataFrame, ccm: pd.DataFrame, msf: pd.DataFrame) -> pd.DataFrame:
    """Attach 12-month forward buy-and-hold returns after each fiscal year-end."""
    panel = ceos.copy()
    panel["datadate"] = pd.to_datetime(panel["datadate"])

    ccm2 = ccm.copy()
    ccm2["linkdt"] = pd.to_datetime(ccm2["linkdt"])
    ccm2["linkenddt"] = pd.to_datetime(ccm2["linkenddt"]).fillna(pd.Timestamp("today"))
    ccm2["linkprim_rank"] = ccm2["linkprim"].map({"P": 0, "C": 1}).fillna(9)

    panel = panel.merge(
        ccm2[["gvkey", "permno", "linkdt", "linkenddt", "linkprim", "linkprim_rank"]],
        on="gvkey",
        how="left",
    )
    panel = panel[(panel["datadate"] >= panel["linkdt"]) & (panel["datadate"] <= panel["linkenddt"])]
    panel = panel.sort_values(
        ["gvkey", "execid", "fyear", "linkprim_rank", "linkdt", "permno"],
        ascending=[True, True, True, True, False, True],
    )
    panel = panel.drop_duplicates(subset=["gvkey", "execid", "fyear"], keep="first")

    msf2 = msf.copy()
    msf2["ret"] = pd.to_numeric(msf2["ret"], errors="coerce")

    records = []
    for row in panel.itertuples(index=False):
        start = pd.Timestamp(row.datadate) + pd.offsets.MonthEnd(1)
        end = start + pd.DateOffset(months=11)
        sec = msf2[(msf2["permno"] == row.permno) & (msf2["date"] >= start) & (msf2["date"] <= end)]
        sec = sec.dropna(subset=["ret"])
        if sec.empty:
            fwd_ret = np.nan
            n_months = 0
        else:
            fwd_ret = np.prod(1 + sec["ret"].values) - 1
            n_months = sec.shape[0]
        records.append((fwd_ret, n_months))

    ret_df = pd.DataFrame(records, columns=["fwd_12m_bhar", "n_ret_months"], index=panel.index)
    merged = panel.join(ret_df)
    return merged


def run_regressions(df: pd.DataFrame) -> tuple:
    """Run core regressions with year fixed effects and clustered SE by firm."""
    model_df = df.copy()
    model_df = model_df[(model_df["n_ret_months"] >= 9)]
    model_df["ln_tdc1"] = np.log(model_df["tdc1"].clip(lower=1))
    model_df["size_pay"] = np.log(model_df["salary"].clip(lower=1))

    pay_formula = "ln_tdc1 ~ fwd_12m_bhar * prior_ceo_experience + age + C(fyear)"
    perf_formula = "fwd_12m_bhar ~ prior_ceo_experience + age + size_pay + C(fyear)"

    pay_model = smf.ols(pay_formula, data=model_df).fit(
        cov_type="cluster", cov_kwds={"groups": model_df["gvkey"]}
    )
    perf_model = smf.ols(perf_formula, data=model_df).fit(
        cov_type="cluster", cov_kwds={"groups": model_df["gvkey"]}
    )
    return pay_model, perf_model, model_df


def build_summary_table(df: pd.DataFrame) -> pd.DataFrame:
    """Simple descriptive comparison by prior CEO experience."""
    grp = (
        df.groupby("prior_ceo_experience")
        .agg(
            n_obs=("execid", "size"),
            mean_tdc1=("tdc1", "mean"),
            median_tdc1=("tdc1", "median"),
            mean_fwd_12m_bhar=("fwd_12m_bhar", "mean"),
            median_fwd_12m_bhar=("fwd_12m_bhar", "median"),
            avg_age=("age", "mean"),
        )
        .reset_index()
    )
    grp["prior_ceo_experience"] = grp["prior_ceo_experience"].map(
        {0: "No prior CEO experience", 1: "Has prior CEO experience"}
    )
    return grp


def save_outputs(
    model_df: pd.DataFrame,
    summary: pd.DataFrame,
    pay_model,
    perf_model,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    model_df.to_parquet(output_dir / "ceo_panel_enriched.parquet", index=False)
    summary.to_csv(output_dir / "experience_summary.csv", index=False)

    with open(output_dir / "regression_results.txt", "w", encoding="utf-8") as f:
        f.write("PAY-PERFORMANCE SENSITIVITY MODEL\n")
        f.write(pay_model.summary().as_text())
        f.write("\n\nPERFORMANCE DIFFERENCE MODEL\n")
        f.write(perf_model.summary().as_text())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CEO experience and compensation analysis using WRDS")
    parser.add_argument("--wrds-username", default=None, help="WRDS username (optional)")
    parser.add_argument("--start-year", type=int, default=1994)
    parser.add_argument("--end-year", type=int, default=2023)
    parser.add_argument("--output-dir", default="output")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = AnalysisConfig(
        start_year=args.start_year,
        end_year=args.end_year,
        output_dir=Path(args.output_dir),
    )

    conn = connect_wrds(args.wrds_username)
    try:
        ceos = pull_execucomp_ceos(conn, cfg.start_year, cfg.end_year)
        ceos = add_prior_ceo_experience(ceos)
        ceos = ceos[(ceos["fyear"] >= cfg.start_year) & (ceos["fyear"] <= cfg.end_year)].copy()
        ccm = pull_ccm_links(conn)
        msf = pull_monthly_returns(conn, cfg.start_year, cfg.end_year)
        merged = merge_returns(ceos, ccm, msf)

        pay_model, perf_model, model_df = run_regressions(merged)
        summary = build_summary_table(model_df)
        save_outputs(model_df, summary, pay_model, perf_model, cfg.output_dir)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
