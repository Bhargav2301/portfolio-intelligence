import pandas as pd
import pytest

from pi_agent_runtime.ingestion import NormalizationError, normalize_qber_rows


def source_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Stock": "Adani Ports - NSE - 25/08 (12:01)",
                "Latest Price": 100,
                "Quantity": 2,
                "Inv. Price": 80,
                "Inv. Date": "24-08-2026",
                "Inv. Amt": 160,
                "Overall Gain": 40,
                "Latest Value": 200,
                "allocation": None,
            },
            {
                "Stock": None,
                "Latest Price": None,
                "Quantity": None,
                "Inv. Price": None,
                "Inv. Date": None,
                "Inv. Amt": None,
                "Overall Gain": None,
                "Latest Value": None,
                "allocation": 1,
            },
            {
                "Stock": "TOTAL",
                "Latest Price": None,
                "Quantity": 2,
                "Inv. Price": None,
                "Inv. Date": None,
                "Inv. Amt": 160,
                "Overall Gain": 40,
                "Latest Value": 200,
                "allocation": None,
            },
            {
                "Stock": None,
                "Latest Price": None,
                "Quantity": None,
                "Inv. Price": None,
                "Inv. Date": None,
                "Inv. Amt": None,
                "Overall Gain": None,
                "Latest Value": None,
                "allocation": 1,
            },
        ]
    )


def test_normalizer_reconciles_and_preserves_lot() -> None:
    result = normalize_qber_rows(
        source_frame(), filename="portfolio.xls", source_hash="a" * 64
    )
    assert result["format"] == "pi-portfolio-import/v1"
    assert result["quality"]["status"] == "validated"
    assert result["holdings"] == [
        {
            "symbol": "ADANIPORTS",
            "name": "Adani Ports and Special Economic Zone",
            "exchange": "NSE",
            "analysis_symbol": "ADANIPORTS.NS",
            "quantity": 2.0,
            "average_cost": 80.0,
            "current_price": 100.0,
        }
    ]
    assert result["lots"][0]["source_row_number"] == 2


def test_normalizer_blocks_unmapped_instrument() -> None:
    frame = source_frame()
    frame.loc[0, "Stock"] = "Unknown Co - NSE - 25/08 (12:01)"
    with pytest.raises(NormalizationError, match="no confirmed instrument mapping"):
        normalize_qber_rows(frame, filename="portfolio.xls", source_hash="a" * 64)
