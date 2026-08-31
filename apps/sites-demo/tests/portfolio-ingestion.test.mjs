import assert from "node:assert/strict";
import { File } from "node:buffer";
import test from "node:test";
import * as XLSX from "xlsx";

import {
  analyzePortfolioWorkbook,
  normalizePortfolioImport,
  PortfolioImportError,
  readPastedPortfolio,
  readPortfolioWorkbook,
  validateImportMapping,
} from "../lib/portfolio-ingestion.js";

function analyzeDelimited(input) {
  return analyzePortfolioWorkbook(readPastedPortfolio(input));
}

test("preserves the original canonical CSV contract with reordered columns", () => {
  const analysis = analyzeDelimited([
    "current_price,name,quantity,symbol,average_cost,exchange",
    "140,Example Industries,12,EXMPL,125,NSE",
  ].join("\n"));

  assert.equal(analysis.issues.length, 0);
  const result = normalizePortfolioImport(analysis, analysis.mapping);
  assert.deepEqual(result.holdings, [{
    symbol: "EXMPL",
    name: "Example Industries",
    exchange: "NSE",
    quantity: 12,
    averageCost: 125,
    currentPrice: 140,
    analysisSymbol: null,
  }]);
  assert.equal(result.lots.length, 1);
});

test("flattens a consolidated export into holdings and tax lots", () => {
  const analysis = analyzeDelimited([
    "Stock,Latest Price,Change,Quantity,Inv. Price,Inv. Date,Inv. Amt,Overall Gain,Overall Gain%,Latest Value,allocation",
    "Sample Ports,100,,10,80,01-01-2024,800,200,25%,999.2,",
    "Sample Ports,100,,5,100,15-02-2024,500,0,0%,499.4,",
    ",,,,,,,,,,12.5%",
    "TOTAL,,,15,,,1300,,,1498.6,100%",
  ].join("\n"));

  assert.equal(analysis.issues.length, 0);
  const result = normalizePortfolioImport(analysis, analysis.mapping);
  assert.equal(result.holdings.length, 1);
  assert.equal(result.lots.length, 2);
  assert.equal(result.holdings[0].symbol, "SAMPLEPORTS");
  assert.equal(result.holdings[0].quantity, 15);
  assert.equal(result.holdings[0].averageCost, 1300 / 15);
  assert.equal(result.holdings[0].currentPrice, 100);
  assert.equal(result.quality.skippedRows, 1);
  assert.match(result.warnings.join(" "), /price-based market value differs/i);
});

test("detects metadata, an arbitrary header vocabulary, and a non-first header row", () => {
  const analysis = analyzeDelimited([
    "Portfolio export\t\t\t\t",
    "Generated 2026-08-30\t\t\t\t",
    "Security Description\tUnits Held\tBook Price\tCMP\tTrading Venue",
    "Acme Solar\t12\t45.5\t51\tNSE",
  ].join("\n"));

  assert.equal(analysis.headerRowIndex, 2);
  assert.equal(analysis.issues.length, 0);
  const result = normalizePortfolioImport(analysis, analysis.mapping);
  assert.deepEqual(result.holdings[0], {
    symbol: "ACMESOLAR",
    name: "Acme Solar",
    exchange: "NSE",
    quantity: 12,
    averageCost: 45.5,
    currentPrice: 51,
    analysisSymbol: null,
  });
  assert.match(result.warnings.join(" "), /derived symbol/i);
});

test("selects the most portfolio-like worksheet from XLS and XLSX workbooks", async () => {
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.aoa_to_sheet([
    ["Notes"],
    ["Generated for internal review"],
  ]), "Read me");
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.aoa_to_sheet([
    ["Ticker", "Shares", "Cost Basis", "Market Value", "Market"],
    ["DEMO", 2, 600, 820, "NASDAQ"],
  ]), "Holdings");
  for (const bookType of ["xls", "xlsx"]) {
    const bytes = XLSX.write(workbook, { type: "buffer", bookType });
    const file = new File([bytes], `arbitrary-layout.${bookType}`, {
      type: bookType === "xls" ? "application/vnd.ms-excel" : "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    const parsed = await readPortfolioWorkbook(file);
    const analysis = analyzePortfolioWorkbook(parsed);
    assert.equal(analysis.sheetName, "Holdings", bookType);
    const result = normalizePortfolioImport(analysis, analysis.mapping);
    assert.deepEqual(result.holdings[0], {
      symbol: "DEMO",
      name: "DEMO",
      exchange: "NASDAQ",
      quantity: 2,
      averageCost: 300,
      currentPrice: 410,
      analysisSymbol: null,
    }, bookType);
  }
});

test("requires cost and price mappings and rejects incompatible shared columns", () => {
  const analysis = analyzeDelimited("Security,Units\nABC,10");
  assert.deepEqual(analysis.issues, [
    "Map either unit/average cost or invested amount",
    "Map either current price or market value",
  ]);
  assert.throws(
    () => normalizePortfolioImport(analysis, analysis.mapping),
    (error) => error instanceof PortfolioImportError && /required column mapping/.test(error.message),
  );

  const duplicateNumeric = { ...analysis.mapping, averageCost: 1, currentPrice: 1 };
  assert.match(validateImportMapping(duplicateNumeric).join(" "), /same column/i);
});

test("reports row-level numeric and reconciliation errors", () => {
  const badType = analyzeDelimited([
    "symbol,quantity,average_cost,current_price",
    "ABC,ten,100,110",
  ].join("\n"));
  assert.throws(
    () => normalizePortfolioImport(badType, badType.mapping),
    (error) => error instanceof PortfolioImportError
      && error.issues.some((issue) => /Row 2: quantity is missing or not numeric/.test(issue)),
  );

  const badTotal = analyzeDelimited([
    "symbol,quantity,average_cost,current_price",
    "ABC,10,100,110",
    "TOTAL,9,,",
  ].join("\n"));
  assert.throws(
    () => normalizePortfolioImport(badTotal, badTotal.mapping),
    (error) => error instanceof PortfolioImportError && /TOTAL quantity/.test(error.message),
  );
});
