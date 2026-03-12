import unittest

import pandas as pd

from src.board_interconnectedness_analysis import (
    build_analysis_panel,
    classify_effect,
    compute_interlock_metrics,
)


class DummyModel:
    def __init__(self, coef, pval):
        self.params = {"avg_outside_board_seats": coef}
        self.pvalues = {"avg_outside_board_seats": pval}


class BoardInterlockTests(unittest.TestCase):
    def test_compute_interlock_metrics(self):
        sp500 = pd.DataFrame(
            {
                "gvkey": ["1001", "1002"],
                "permno": [1, 2],
                "year": [2020, 2020],
            }
        )
        directors = pd.DataFrame(
            {
                "gvkey": ["1001", "1001", "1002", "1002"],
                "director_id": ["A", "B", "A", "C"],
                "year": [2020, 2020, 2020, 2020],
            }
        )

        out = compute_interlock_metrics(sp500, directors)
        row_1001 = out[out["gvkey"] == "1001"].iloc[0]
        self.assertEqual(row_1001["board_size"], 2)
        self.assertAlmostEqual(row_1001["pct_interlocked_directors"], 0.5)
        self.assertAlmostEqual(row_1001["avg_outside_board_seats"], 0.5)

    def test_build_analysis_panel_forward_return_merge(self):
        interlocks = pd.DataFrame(
            {
                "gvkey": ["1001"],
                "year": [2020],
                "board_size": [8],
                "avg_outside_board_seats": [1.2],
                "pct_interlocked_directors": [0.6],
                "total_outside_board_seats": [10],
            }
        )
        sp500 = pd.DataFrame({"gvkey": ["1001"], "permno": [1], "year": [2020]})
        annual = pd.DataFrame({"permno": [1, 1], "year": [2020, 2021], "annual_bhar": [0.1, 0.2]})

        panel = build_analysis_panel(interlocks, sp500, annual)
        self.assertEqual(panel.iloc[0]["fwd_1y_bhar"], 0.2)

    def test_classify_effect(self):
        self.assertEqual(classify_effect(DummyModel(0.2, 0.03)), "Helps stock performance")
        self.assertEqual(classify_effect(DummyModel(-0.2, 0.03)), "Hurts stock performance")
        self.assertEqual(
            classify_effect(DummyModel(0.2, 0.5)), "No statistically significant effect"
        )


if __name__ == "__main__":
    unittest.main()
