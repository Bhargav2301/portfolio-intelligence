import pandas as pd

from pi_agent_runtime.ingestion import normalize_consolidated_rows


def source_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Stock": "Example Ports - NSE - 25/08 (12:01)",
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
    result = normalize_consolidated_rows(
        source_frame(),
        filename="portfolio.xls",
        source_hash="a" * 64,
        instrument_mappings={
            "Example Ports": ("EXMPL", "Example Ports Limited", "EXMPL.NS")
        },
    )
    assert result["format"] == "pi-portfolio-import/v1"
    assert result["quality"]["status"] == "validated"
    assert result["holdings"] == [
        {
            "symbol": "EXMPL",
            "name": "Example Ports Limited",
            "exchange": "NSE",
            "analysis_symbol": "EXMPL.NS",
            "quantity": 2.0,
            "average_cost": 80.0,
            "current_price": 100.0,
        }
    ]
    assert result["lots"][0]["source_row_number"] == 2


def test_normalizer_derives_unmapped_instrument_for_owner_review() -> None:
    frame = source_frame()
    frame.loc[0, "Stock"] = "Unmapped Example - NSE - 25/08 (12:01)"
    result = normalize_consolidated_rows(
        frame, filename="portfolio.xls", source_hash="a" * 64
    )
    assert result["holdings"][0]["symbol"] == "UNMAPPEDEXAMPLE"
    assert result["holdings"][0]["analysis_symbol"] is None
    assert result["quality"]["status"] == "validated_with_warnings"
    assert "confirm exchange tickers" in " ".join(result["quality"]["warnings"])
