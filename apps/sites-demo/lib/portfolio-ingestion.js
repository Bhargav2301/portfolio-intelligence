import * as XLSX from "xlsx";

const MAX_FILE_BYTES = 10 * 1024 * 1024;
const MAX_SHEETS = 20;
const MAX_ROWS_PER_SHEET = 5_000;
const MAX_COLUMNS = 200;
const MAX_CELL_LENGTH = 1_000;

export const PORTFOLIO_IMPORT_FIELDS = [
  { key: "identity", label: "Instrument / security", required: true },
  { key: "symbol", label: "Ticker / symbol", required: false },
  { key: "name", label: "Instrument name", required: false },
  { key: "exchange", label: "Exchange", required: false },
  { key: "quantity", label: "Quantity", required: true },
  { key: "averageCost", label: "Average or unit cost", required: false },
  { key: "investmentAmount", label: "Invested amount / cost basis", required: false },
  { key: "currentPrice", label: "Current / latest price", required: false },
  { key: "marketValue", label: "Current / market value", required: false },
  { key: "acquiredAt", label: "Acquisition / trade date", required: false },
  { key: "analysisSymbol", label: "Analysis symbol", required: false },
];

const FIELD_ALIASES = {
  identity: ["stock", "instrument", "security", "holding", "scrip", "script", "ticker", "symbol", "stock name", "company", "company name", "security name", "instrument name", "asset"],
  symbol: ["symbol", "ticker", "ticker symbol", "stock symbol", "trading symbol", "tradingsymbol", "scrip code", "security code", "instrument code", "stock code"],
  name: ["name", "stock name", "company", "company name", "security name", "instrument name", "description", "asset name"],
  exchange: ["exchange", "exch", "market", "stock exchange", "venue", "segment"],
  quantity: ["quantity", "qty", "shares", "units", "holding quantity", "balance quantity", "net quantity", "net qty", "total quantity"],
  averageCost: ["average cost", "avg cost", "average price", "avg price", "purchase price", "buy price", "cost price", "unit cost", "investment price", "inv price", "acquisition price", "book price"],
  investmentAmount: ["investment amount", "invested amount", "inv amt", "cost basis", "total cost", "book value", "invested value", "purchase value", "investment value"],
  currentPrice: ["current price", "latest price", "last price", "ltp", "market price", "close price", "closing price", "cmp", "spot price"],
  marketValue: ["market value", "latest value", "current value", "holding value", "valuation", "present value", "total value"],
  acquiredAt: ["acquisition date", "acquired date", "purchase date", "buy date", "investment date", "inv date", "trade date", "transaction date", "date"],
  analysisSymbol: ["analysis symbol", "yahoo symbol", "market data symbol", "quote symbol"],
};

export class PortfolioImportError extends Error {
  constructor(message, issues = []) {
    super(message);
    this.name = "PortfolioImportError";
    this.issues = issues;
  }
}

export async function readPortfolioWorkbook(file) {
  const extension = file.name.toLowerCase().split(".").pop() ?? "";
  if (!["csv", "tsv", "xls", "xlsx"].includes(extension)) {
    throw new PortfolioImportError("Choose a CSV, TSV, XLS, or XLSX portfolio file");
  }
  if (file.size > MAX_FILE_BYTES) {
    throw new PortfolioImportError("Portfolio files must be 10 MB or smaller");
  }
  const bytes = await file.arrayBuffer();
  let parsed;
  try {
    parsed = XLSX.read(bytes, {
      type: "array",
      cellDates: true,
      cellFormula: false,
      cellHTML: false,
      bookVBA: false,
      dense: true,
      sheetRows: MAX_ROWS_PER_SHEET + 1,
    });
  } catch {
    throw new PortfolioImportError("The spreadsheet is damaged, encrypted, or not a supported Excel/CSV file");
  }
  return workbookFromSheetJs(parsed, file.name);
}

export function readPastedPortfolio(input) {
  if (!input.trim()) throw new PortfolioImportError("Paste a delimited table with a header row");
  let parsed;
  try {
    parsed = XLSX.read(input, {
      type: "string",
      cellDates: true,
      cellFormula: false,
      cellHTML: false,
      dense: true,
      sheetRows: MAX_ROWS_PER_SHEET + 1,
    });
  } catch {
    throw new PortfolioImportError("The pasted table could not be parsed as CSV, TSV, or another delimited format");
  }
  return workbookFromSheetJs(parsed, "pasted-portfolio.csv");
}

function workbookFromSheetJs(parsed, filename) {
  if (!parsed.SheetNames.length) throw new PortfolioImportError("The spreadsheet has no worksheets");
  if (parsed.SheetNames.length > MAX_SHEETS) throw new PortfolioImportError(`Portfolio imports support at most ${MAX_SHEETS} worksheets`);
  const sheets = parsed.SheetNames.map((name) => {
    const worksheet = parsed.Sheets[name];
    const rawRows = worksheet
      ? XLSX.utils.sheet_to_json(worksheet, { header: 1, defval: null, raw: true, blankrows: true })
      : [];
    if (rawRows.length > MAX_ROWS_PER_SHEET) {
      throw new PortfolioImportError(`${name}: worksheets may contain at most ${MAX_ROWS_PER_SHEET.toLocaleString("en-IN")} rows`);
    }
    const rows = trimMatrix(rawRows.map((row) => {
      if (!Array.isArray(row)) return [];
      if (row.length > MAX_COLUMNS) throw new PortfolioImportError(`${name}: worksheets may contain at most ${MAX_COLUMNS} columns`);
      return row.map(sanitizeCell);
    }));
    return { name, rows };
  }).filter((sheet) => sheet.rows.length > 0);
  if (!sheets.length) throw new PortfolioImportError("The spreadsheet contains no readable cells");
  return { filename, sheets };
}

export function analyzePortfolioWorkbook(workbook, options = {}) {
  const requestedSheet = Number.isInteger(options.sheetIndex) ? options.sheetIndex : null;
  if (requestedSheet !== null) {
    const sheet = workbook.sheets[requestedSheet];
    if (!sheet) throw new PortfolioImportError("The selected worksheet is unavailable");
    return analyzeSheet(workbook, requestedSheet, options.headerRowIndex);
  }
  let best = null;
  workbook.sheets.forEach((_sheet, sheetIndex) => {
    const analysis = analyzeSheet(workbook, sheetIndex, undefined);
    if (!best || analysis.score > best.score) best = analysis;
  });
  return best;
}

function analyzeSheet(workbook, sheetIndex, requestedHeaderRow) {
  const sheet = workbook.sheets[sheetIndex];
  const maxHeader = Math.min(sheet.rows.length, 30);
  const candidates = [];
  const indexes = Number.isInteger(requestedHeaderRow)
    ? [requestedHeaderRow]
    : Array.from({ length: maxHeader }, (_value, index) => index);
  for (const headerRowIndex of indexes) {
    if (headerRowIndex < 0 || headerRowIndex >= sheet.rows.length) continue;
    const headers = buildHeaders(sheet.rows, headerRowIndex);
    const dataRows = sheet.rows.slice(headerRowIndex + 1, headerRowIndex + 101);
    const inferred = inferMapping(headers, dataRows);
    const issues = validateImportMapping(inferred.mapping);
    const nonNumericHeaderRatio = headers.length
      ? headers.filter((header) => header && parseNumber(header) === null).length / headers.length
      : 0;
    const coverage = 4 - issues.length;
    const score = coverage * 100 + inferred.confidence * 60 + nonNumericHeaderRatio * 15 - headerRowIndex * 0.15;
    candidates.push({ headerRowIndex, headers, ...inferred, issues, score });
  }
  const selected = candidates.sort((left, right) => right.score - left.score)[0];
  if (!selected) throw new PortfolioImportError(`${sheet.name}: no possible header row was found`);
  return {
    filename: workbook.filename,
    sheetIndex,
    sheetName: sheet.name,
    sheetNames: workbook.sheets.map((item) => item.name),
    headerRowIndex: selected.headerRowIndex,
    headers: selected.headers,
    mapping: selected.mapping,
    mappingConfidence: selected.confidence,
    mappingScores: selected.mappingScores,
    issues: selected.issues,
    score: selected.score,
    dataRows: sheet.rows.slice(selected.headerRowIndex + 1),
    previewRows: sheet.rows.slice(selected.headerRowIndex + 1).filter((row) => row.some((cell) => !isEmpty(cell))).slice(0, 5),
  };
}

function inferMapping(headers, dataRows) {
  const profiles = headers.map((_header, columnIndex) => profileColumn(dataRows, columnIndex));
  const mapping = Object.fromEntries(PORTFOLIO_IMPORT_FIELDS.map((field) => [field.key, null]));
  const mappingScores = {};
  const used = new Set();

  function select(field, threshold = 48, allowIdentityColumn = false) {
    const candidates = headers.map((header, columnIndex) => ({
      columnIndex,
      score: fieldScore(field, header, profiles[columnIndex]),
    })).filter((candidate) => !used.has(candidate.columnIndex) || (allowIdentityColumn && candidate.columnIndex === mapping.identity));
    candidates.sort((left, right) => right.score - left.score);
    const best = candidates[0];
    if (!best || best.score < threshold) return;
    mapping[field] = best.columnIndex;
    mappingScores[field] = best.score;
    if (!(allowIdentityColumn && best.columnIndex === mapping.identity)) used.add(best.columnIndex);
  }

  select("identity", 50);
  select("quantity", 50);
  select("averageCost", 50);
  select("investmentAmount", 50);
  select("currentPrice", 50);
  select("marketValue", 50);
  select("exchange", 50);
  select("acquiredAt", 50);
  select("analysisSymbol", 55);
  select("symbol", 62, true);
  select("name", 62, true);

  if (mapping.identity !== null) {
    const identityHeader = normalizeHeader(headers[mapping.identity]);
    if (mapping.symbol === null && FIELD_ALIASES.symbol.some((alias) => normalizeHeader(alias) === identityHeader)) {
      mapping.symbol = mapping.identity;
      mappingScores.symbol = mappingScores.identity;
    }
    if (mapping.name === null && FIELD_ALIASES.name.some((alias) => normalizeHeader(alias) === identityHeader)) {
      mapping.name = mapping.identity;
      mappingScores.name = mappingScores.identity;
    }
  }
  const confidenceFields = ["identity", "quantity", mapping.averageCost !== null ? "averageCost" : "investmentAmount", mapping.currentPrice !== null ? "currentPrice" : "marketValue"];
  const confidence = confidenceFields.reduce((sum, field) => sum + Math.min(100, mappingScores[field] ?? 0), 0) / (confidenceFields.length * 100);
  return { mapping, mappingScores, confidence };
}

export function validateImportMapping(mapping) {
  const issues = [];
  if (!Number.isInteger(mapping.identity)) issues.push("Map an instrument, security, or symbol column");
  if (!Number.isInteger(mapping.quantity)) issues.push("Map a quantity column");
  if (!Number.isInteger(mapping.averageCost) && !Number.isInteger(mapping.investmentAmount)) {
    issues.push("Map either unit/average cost or invested amount");
  }
  if (!Number.isInteger(mapping.currentPrice) && !Number.isInteger(mapping.marketValue)) {
    issues.push("Map either current price or market value");
  }
  const numericFields = ["quantity", "averageCost", "investmentAmount", "currentPrice", "marketValue"];
  const numericColumns = new Map();
  numericFields.forEach((field) => {
    const column = mapping[field];
    if (!Number.isInteger(column)) return;
    const existing = numericColumns.get(column);
    if (existing) issues.push(`${humanField(existing)} and ${humanField(field)} cannot use the same column`);
    else numericColumns.set(column, field);
  });
  return issues;
}

export function normalizePortfolioImport(analysis, mapping, options = {}) {
  const mappingIssues = validateImportMapping(mapping);
  Object.entries(mapping).forEach(([field, column]) => {
    if (Number.isInteger(column) && (column < 0 || column >= analysis.headers.length)) {
      mappingIssues.push(`${humanField(field)} points outside the selected worksheet`);
    }
  });
  if (mappingIssues.length) throw new PortfolioImportError("Complete the required column mapping", mappingIssues);
  const defaultExchange = normalizeExchange(options.defaultExchange || "NSE");
  if (!defaultExchange) throw new PortfolioImportError("Choose a valid default exchange");
  const errors = [];
  const warnings = new Set();
  const lots = [];
  const seenLots = new Set();
  let skippedRows = 0;
  const summaries = [];
  let usedDefaultExchange = 0;
  let derivedSymbols = 0;
  let possibleDuplicateLots = 0;

  analysis.dataRows.forEach((row, rowIndex) => {
    const sourceRowNumber = analysis.headerRowIndex + rowIndex + 2;
    if (row.every((cell) => isEmpty(cell)) || isRepeatedHeader(row, analysis.headers)) {
      skippedRows += 1;
      return;
    }
    const identityValue = cellText(row[mapping.identity]);
    if (!identityValue) {
      skippedRows += 1;
      return;
    }
    if (/^(grand )?totals?( inr)?$/.test(normalizeHeader(identityValue))) {
      summaries.push({
        isGrand: /^grand\s+/i.test(identityValue.trim()),
        quantity: optionalNumber(row[mapping.quantity]),
        investmentAmount: Number.isInteger(mapping.investmentAmount) ? optionalNumber(row[mapping.investmentAmount]) : null,
        marketValue: Number.isInteger(mapping.marketValue) ? optionalNumber(row[mapping.marketValue]) : null,
      });
      return;
    }

    try {
      const mappedFinancialColumns = [mapping.quantity, mapping.averageCost, mapping.investmentAmount, mapping.currentPrice, mapping.marketValue]
        .filter((column) => Number.isInteger(column));
      if (!mappedFinancialColumns.some((column) => !isEmpty(row[column]))) {
        skippedRows += 1;
        return;
      }
      const quantity = requiredNumber(row[mapping.quantity], "quantity");
      if (quantity <= 0) throw new Error("quantity must be positive");
      const unitCostValue = Number.isInteger(mapping.averageCost) ? optionalNumber(row[mapping.averageCost]) : null;
      const investmentAmount = Number.isInteger(mapping.investmentAmount) ? optionalNumber(row[mapping.investmentAmount]) : null;
      const currentPriceValue = Number.isInteger(mapping.currentPrice) ? optionalNumber(row[mapping.currentPrice]) : null;
      const marketValue = Number.isInteger(mapping.marketValue) ? optionalNumber(row[mapping.marketValue]) : null;
      const unitCost = unitCostValue ?? (investmentAmount !== null ? investmentAmount / quantity : null);
      const currentPrice = currentPriceValue ?? (marketValue !== null ? marketValue / quantity : null);
      if (unitCost === null || !Number.isFinite(unitCost) || unitCost < 0) throw new Error("cost is missing or invalid");
      if (currentPrice === null || !Number.isFinite(currentPrice) || currentPrice < 0) throw new Error("current price is missing or invalid");
      if (investmentAmount !== null && Math.abs(quantity * unitCost - investmentAmount) > Math.max(1, Math.abs(investmentAmount) * 0.001)) {
        throw new Error("quantity × cost does not reconcile to invested amount");
      }
      if (marketValue !== null && Math.abs(quantity * currentPrice - marketValue) > Math.max(1, Math.abs(marketValue) * 0.001)) {
        throw new Error("quantity × current price does not reconcile to market value");
      }

      const identity = resolveIdentity(row, mapping, identityValue, defaultExchange);
      if (identity.usedDefaultExchange) usedDefaultExchange += 1;
      if (identity.derivedSymbol) derivedSymbols += 1;
      const acquiredAt = Number.isInteger(mapping.acquiredAt) ? parseAcquiredAt(row[mapping.acquiredAt], sourceRowNumber) : null;
      const lotKey = [identity.exchange, identity.symbol, acquiredAt ?? "", quantity, unitCost].join("|");
      if (seenLots.has(lotKey)) possibleDuplicateLots += 1;
      seenLots.add(lotKey);
      lots.push({
        symbol: identity.symbol,
        name: identity.name,
        exchange: identity.exchange,
        analysisSymbol: identity.analysisSymbol,
        quantity,
        unitCost,
        currentPrice,
        acquiredAt,
        sourceRowNumber,
        investmentAmount: investmentAmount ?? quantity * unitCost,
        marketValue: marketValue ?? quantity * currentPrice,
      });
    } catch (error) {
      errors.push(`Row ${sourceRowNumber}: ${error instanceof Error ? error.message : "invalid holding row"}`);
    }
  });

  if (errors.length) {
    throw new PortfolioImportError(`The spreadsheet has ${errors.length} invalid holding row${errors.length === 1 ? "" : "s"}`, errors.slice(0, 20));
  }
  if (!lots.length) throw new PortfolioImportError("No valid holding rows were found below the selected header");
  if (lots.length > 1_000) throw new PortfolioImportError("Portfolio imports support at most 1,000 lot rows");

  const grouped = new Map();
  lots.forEach((lot) => {
    const key = `${lot.exchange}:${lot.symbol}`;
    const current = grouped.get(key) ?? { lots: [], quantity: 0, cost: 0 };
    if (current.lots.length && normalizeIdentity(current.lots[0].name) !== normalizeIdentity(lot.name)) {
      throw new PortfolioImportError(`${lot.symbol}: different instrument names resolve to the same symbol; map an explicit ticker column`);
    }
    current.lots.push(lot);
    current.quantity += lot.quantity;
    current.cost += lot.quantity * lot.unitCost;
    grouped.set(key, current);
  });
  if (grouped.size > 100) throw new PortfolioImportError("Portfolio imports support at most 100 unique holdings");

  const holdings = [...grouped.values()].map((group) => {
    const first = group.lots[0];
    const minPrice = Math.min(...group.lots.map((lot) => lot.currentPrice));
    const maxPrice = Math.max(...group.lots.map((lot) => lot.currentPrice));
    if (maxPrice - minPrice > Math.max(0.01, maxPrice * 0.001)) {
      throw new PortfolioImportError(`${first.symbol}: consolidated rows contain conflicting current prices`);
    }
    return {
      symbol: first.symbol,
      name: first.name,
      exchange: first.exchange,
      quantity: group.quantity,
      averageCost: group.cost / group.quantity,
      currentPrice: group.lots.at(-1).currentPrice,
      analysisSymbol: first.analysisSymbol,
    };
  }).sort((left, right) => left.symbol.localeCompare(right.symbol));

  const computedQuantity = lots.reduce((sum, lot) => sum + lot.quantity, 0);
  const computedInvestment = lots.reduce((sum, lot) => sum + lot.investmentAmount, 0);
  const computedMarketValue = lots.reduce((sum, lot) => sum + lot.marketValue, 0);
  const priceCalculatedMarketValue = lots.reduce((sum, lot) => sum + lot.quantity * lot.currentPrice, 0);
  const grandSummary = [...summaries].reverse().find((item) => item.isGrand);
  const matchingSummary = [...summaries].reverse().find((item) => summaryMatches(item, computedQuantity, computedInvestment, computedMarketValue, lots.length));
  const summary = grandSummary ?? (summaries.length === 1 ? summaries[0] : matchingSummary ?? null);
  if (!summary && summaries.length > 1) warnings.add(`${summaries.length} subtotal rows were excluded from whole-portfolio reconciliation`);
  if (summary && summary.quantity !== null && Math.abs(summary.quantity - computedQuantity) > 1e-6) {
    throw new PortfolioImportError("The source TOTAL quantity does not reconcile to the imported rows");
  }
  if (summary && summary.investmentAmount !== null) {
    const delta = computedInvestment - summary.investmentAmount;
    if (Math.abs(delta) > Math.max(5, lots.length * 0.51)) throw new PortfolioImportError("The source TOTAL invested amount does not reconcile to the imported rows");
    if (Math.abs(delta) > 1) warnings.add(`Source invested total differs from rounded lot sum by INR ${delta.toFixed(2)}`);
  }
  if (summary && summary.marketValue !== null) {
    const delta = computedMarketValue - summary.marketValue;
    if (Math.abs(delta) > Math.max(1, lots.length * 0.51)) {
      throw new PortfolioImportError("The source TOTAL market value does not reconcile to the imported rows");
    }
    if (Math.abs(delta) > 1) warnings.add(`Source market-value total differs from rounded lot sum by INR ${Math.abs(delta).toFixed(2)}`);
  }
  const priceRoundingDelta = priceCalculatedMarketValue - computedMarketValue;
  if (Math.abs(priceRoundingDelta) > 1) {
    warnings.add(`Normalized price-based market value differs from rounded source rows by INR ${Math.abs(priceRoundingDelta).toFixed(2)}`);
  }
  if (usedDefaultExchange) warnings.add(`Default exchange ${defaultExchange} was applied to ${usedDefaultExchange} row${usedDefaultExchange === 1 ? "" : "s"}`);
  if (derivedSymbols) warnings.add(`${derivedSymbols} row${derivedSymbols === 1 ? " uses" : "s use"} a derived symbol; review ticker mappings before saving`);
  if (possibleDuplicateLots) warnings.add(`${possibleDuplicateLots} possible duplicate lot row${possibleDuplicateLots === 1 ? " was" : "s were"} retained; verify them before saving`);
  if (skippedRows) warnings.add(`${skippedRows} blank, metadata, allocation, or repeated-header row${skippedRows === 1 ? " was" : "s were"} skipped`);
  if (analysis.mappingConfidence < 0.75) warnings.add("Automatic column confidence is below 75%; verify every mapped field");

  return {
    holdings,
    lots: lots.map((lot) => ({
      symbol: lot.symbol,
      name: lot.name,
      exchange: lot.exchange,
      quantity: lot.quantity,
      unitCost: lot.unitCost,
      acquiredAt: lot.acquiredAt,
      sourceRowNumber: lot.sourceRowNumber,
    })),
    warnings: [...warnings],
    quality: {
      sheetName: analysis.sheetName,
      headerRowNumber: analysis.headerRowIndex + 1,
      sourceRows: analysis.dataRows.length,
      lotRows: lots.length,
      holdingRows: holdings.length,
      skippedRows,
      mappingConfidence: analysis.mappingConfidence,
    },
  };
}

function resolveIdentity(row, mapping, identityValue, defaultExchange) {
  const composite = parseCompositeIdentity(identityValue);
  const explicitSymbolText = Number.isInteger(mapping.symbol) ? cellText(row[mapping.symbol]) : "";
  const explicitName = Number.isInteger(mapping.name) ? cellText(row[mapping.name]) : "";
  const explicitExchange = Number.isInteger(mapping.exchange) ? normalizeExchange(cellText(row[mapping.exchange])) : "";
  const mappedAnalysis = Number.isInteger(mapping.analysisSymbol) ? cellText(row[mapping.analysisSymbol]).toUpperCase() : "";
  const parsedSymbol = parseSymbol(explicitSymbolText || (mapping.symbol === mapping.identity ? identityValue : ""));
  const sourceName = explicitName || composite.name || identityValue;
  const exchange = explicitExchange || parsedSymbol.exchange || composite.exchange || defaultExchange;
  if (!exchange) throw new Error("exchange is missing");
  let symbol = parsedSymbol.symbol || "";
  const derivedSymbol = !symbol;
  if (!symbol) symbol = deriveSymbol(sourceName);
  if (!symbol) throw new Error("instrument symbol could not be derived");
  const name = sourceName.trim();
  const analysisSymbol = mappedAnalysis || parsedSymbol.analysisSymbol || null;
  if (analysisSymbol) {
    const expectedSuffix = exchange === "NSE" ? ".NS" : exchange === "BSE" ? ".BO" : "";
    if (expectedSuffix && !analysisSymbol.endsWith(expectedSuffix)) throw new Error(`analysis symbol conflicts with exchange ${exchange}`);
  }
  return {
    symbol: symbol.toUpperCase(),
    name,
    exchange,
    analysisSymbol,
    derivedSymbol,
    usedDefaultExchange: !explicitExchange && !parsedSymbol.exchange && !composite.exchange,
  };
}

function parseCompositeIdentity(value) {
  const trimmed = value.trim();
  const separated = trimmed.match(/^(.+?)\s+-\s+(NSE|BSE|NASDAQ|NYSE)(?:\s+-\s+.+)?$/i);
  if (separated) return { name: separated[1].trim(), exchange: separated[2].toUpperCase() };
  const bracketed = trimmed.match(/^(.+?)\s*[[(]\s*(NSE|BSE|NASDAQ|NYSE)\s*[\])]/i);
  if (bracketed) return { name: bracketed[1].trim(), exchange: bracketed[2].toUpperCase() };
  return { name: trimmed, exchange: "" };
}

function parseSymbol(value) {
  const trimmed = value.trim().toUpperCase();
  if (!trimmed) return { symbol: "", exchange: "", analysisSymbol: "" };
  const qualified = trimmed.match(/^(NSE|BSE|NASDAQ|NYSE)\s*[:/]\s*([A-Z0-9&._-]+)$/);
  if (qualified) return { symbol: qualified[2], exchange: qualified[1], analysisSymbol: "" };
  if (/^[A-Z0-9&._-]+\.NS$/.test(trimmed)) return { symbol: trimmed.slice(0, -3), exchange: "NSE", analysisSymbol: trimmed };
  if (/^[A-Z0-9&._-]+\.BO$/.test(trimmed)) return { symbol: trimmed.slice(0, -3), exchange: "BSE", analysisSymbol: trimmed };
  if (/^[A-Z0-9&._-]{1,32}$/.test(trimmed)) return { symbol: trimmed, exchange: "", analysisSymbol: "" };
  return { symbol: "", exchange: "", analysisSymbol: "" };
}

function parseAcquiredAt(value, rowNumber) {
  if (isEmpty(value)) return null;
  if (value instanceof Date && !Number.isNaN(value.getTime())) return `${value.toISOString().slice(0, 10)}T00:00:00.000Z`;
  if (typeof value === "number" && value > 10_000 && value < 100_000) {
    const parsed = XLSX.SSF.parse_date_code(value);
    if (parsed) return `${String(parsed.y).padStart(4, "0")}-${String(parsed.m).padStart(2, "0")}-${String(parsed.d).padStart(2, "0")}T00:00:00.000Z`;
  }
  const text = cellText(value);
  let match = text.match(/^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$/);
  if (match) return validIsoDate(match[1], match[2], match[3], rowNumber);
  match = text.match(/^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2}|\d{4})$/);
  if (match) {
    const year = match[3].length === 2 ? String(2000 + Number(match[3])) : match[3];
    return validIsoDate(year, match[2], match[1], rowNumber);
  }
  throw new Error("acquisition date is invalid");
}

function validIsoDate(year, month, day) {
  const iso = `${String(year).padStart(4, "0")}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
  const parsed = new Date(`${iso}T00:00:00.000Z`);
  if (Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== iso) throw new Error("acquisition date is invalid");
  return `${iso}T00:00:00.000Z`;
}

function fieldScore(field, header, profile) {
  const normalized = normalizeHeader(header);
  if (!normalized) return 0;
  const aliasScore = Math.max(0, ...FIELD_ALIASES[field].map((alias) => similarity(normalized, normalizeHeader(alias))));
  const typeBonus = field === "exchange" ? profile.exchangeRatio * 18
    : field === "acquiredAt" ? profile.dateRatio * 18
      : ["quantity", "averageCost", "investmentAmount", "currentPrice", "marketValue"].includes(field) ? profile.numericRatio * 12
        : profile.textRatio * 8;
  return aliasScore + typeBonus;
}

function similarity(header, alias) {
  if (header === alias) return 92;
  if (header.startsWith(`${alias} `) || header.endsWith(` ${alias}`)) return 80;
  if (header.includes(alias) && alias.length >= 4) return 73;
  const left = new Set(header.split(" "));
  const right = new Set(alias.split(" "));
  const overlap = [...left].filter((token) => right.has(token)).length;
  const union = new Set([...left, ...right]).size;
  return union ? (overlap / union) * 65 : 0;
}

function profileColumn(rows, columnIndex) {
  const values = rows.map((row) => row[columnIndex]).filter((value) => !isEmpty(value)).slice(0, 50);
  if (!values.length) return { numericRatio: 0, dateRatio: 0, exchangeRatio: 0, textRatio: 0 };
  const numeric = values.filter((value) => parseNumber(value) !== null).length;
  const date = values.filter((value) => looksLikeDate(value)).length;
  const exchange = values.filter((value) => Boolean(normalizeExchange(cellText(value)))).length;
  return {
    numericRatio: numeric / values.length,
    dateRatio: date / values.length,
    exchangeRatio: exchange / values.length,
    textRatio: values.filter((value) => typeof value === "string" && parseNumber(value) === null).length / values.length,
  };
}

function buildHeaders(rows, headerRowIndex) {
  const current = rows[headerRowIndex] ?? [];
  const previous = headerRowIndex > 0 ? rows[headerRowIndex - 1] ?? [] : [];
  const width = Math.max(current.length, previous.length);
  const usePrevious = previous.filter((cell) => !isEmpty(cell)).length >= 2
    && current.filter((cell) => !isEmpty(cell)).length >= 2;
  let carriedGroup = "";
  return Array.from({ length: width }, (_value, columnIndex) => {
    const groupCell = usePrevious ? cellText(previous[columnIndex]) : "";
    if (groupCell) carriedGroup = groupCell;
    const currentCell = cellText(current[columnIndex]);
    const combined = currentCell && carriedGroup && normalizeHeader(currentCell) !== normalizeHeader(carriedGroup)
      ? `${carriedGroup} ${currentCell}`
      : currentCell || carriedGroup;
    return combined || `Column ${columnIndex + 1}`;
  });
}

function summaryMatches(summary, quantity, investmentAmount, marketValue, lotCount) {
  const checks = [];
  if (summary.quantity !== null) checks.push(Math.abs(summary.quantity - quantity) <= 1e-6);
  if (summary.investmentAmount !== null) checks.push(Math.abs(summary.investmentAmount - investmentAmount) <= Math.max(5, lotCount * 0.51));
  if (summary.marketValue !== null) checks.push(Math.abs(summary.marketValue - marketValue) <= Math.max(1, lotCount * 0.51));
  return checks.length > 0 && checks.every(Boolean);
}

function humanField(field) {
  return PORTFOLIO_IMPORT_FIELDS.find((item) => item.key === field)?.label ?? field;
}

function isRepeatedHeader(row, headers) {
  const compared = row.slice(0, headers.length).map((value) => normalizeHeader(cellText(value)));
  const expected = headers.map(normalizeHeader);
  const matches = compared.filter((value, index) => value && value === expected[index]).length;
  return matches >= Math.max(2, Math.ceil(expected.length * 0.6));
}

function normalizeHeader(value) {
  return cellText(value).normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase()
    .replace(/%/g, " percent ").replace(/&/g, " and ").replace(/[^a-z0-9]+/g, " ").trim();
}

function normalizeIdentity(value) {
  return value.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "").trim();
}

function deriveSymbol(name) {
  return name.toUpperCase().replace(/&/g, "AND").replace(/[^A-Z0-9]+/g, "").slice(0, 24);
}

function normalizeExchange(value) {
  const normalized = normalizeHeader(value);
  if (!normalized) return "";
  if (/^(nse|national stock exchange|nse eq|nse equity)$/.test(normalized)) return "NSE";
  if (/^(bse|bombay stock exchange|bse eq|bse equity)$/.test(normalized)) return "BSE";
  if (/^nasdaq/.test(normalized)) return "NASDAQ";
  if (/^(nyse|new york stock exchange)$/.test(normalized)) return "NYSE";
  return "";
}

function requiredNumber(value, field) {
  const number = parseNumber(value);
  if (number === null) throw new Error(`${field} is missing or not numeric`);
  if (!Number.isFinite(number)) throw new Error(`${field} is not finite`);
  return number;
}

function optionalNumber(value) {
  return parseNumber(value);
}

function parseNumber(value) {
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value !== "string") return null;
  let text = value.trim();
  if (!text || /^(na|n\/a|null|none|--|-)$/i.test(text)) return null;
  let negative = false;
  if (/^\(.*\)$/.test(text)) { negative = true; text = text.slice(1, -1); }
  const percent = text.includes("%");
  text = text.replace(/[₹$£€,%\s]/g, "").replace(/,/g, "");
  if (!/^[-+]?\d*\.?\d+(?:e[-+]?\d+)?$/i.test(text)) return null;
  const number = Number(text);
  if (!Number.isFinite(number)) return null;
  const signed = negative ? -Math.abs(number) : number;
  return percent ? signed / 100 : signed;
}

function looksLikeDate(value) {
  if (value instanceof Date && !Number.isNaN(value.getTime())) return true;
  if (typeof value === "number") return value > 10_000 && value < 100_000;
  const text = cellText(value);
  return /^(?:\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.](?:\d{2}|\d{4}))$/.test(text);
}

function sanitizeCell(value) {
  if (value instanceof Date && !Number.isNaN(value.getTime())) return value;
  if (typeof value === "number" || typeof value === "boolean") return value;
  if (value === null || value === undefined) return null;
  const text = String(value).trim();
  if (text.length > MAX_CELL_LENGTH) throw new PortfolioImportError(`A spreadsheet cell exceeds ${MAX_CELL_LENGTH.toLocaleString("en-IN")} characters`);
  return text || null;
}

function trimMatrix(rows) {
  const trimmedRows = [...rows];
  while (trimmedRows.length && trimmedRows.at(-1).every(isEmpty)) trimmedRows.pop();
  let lastColumn = -1;
  trimmedRows.forEach((row) => row.forEach((value, index) => { if (!isEmpty(value)) lastColumn = Math.max(lastColumn, index); }));
  return lastColumn < 0 ? [] : trimmedRows.map((row) => row.slice(0, lastColumn + 1));
}

function isEmpty(value) {
  return value === null || value === undefined || (typeof value === "string" && !value.trim());
}

function cellText(value) {
  if (value === null || value === undefined) return "";
  if (value instanceof Date && !Number.isNaN(value.getTime())) return value.toISOString().slice(0, 10);
  return String(value).trim();
}
