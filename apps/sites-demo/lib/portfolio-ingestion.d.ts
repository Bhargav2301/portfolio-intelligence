import type { HoldingInput, HoldingLotInput } from "./types";

export type PortfolioImportField =
  | "identity"
  | "symbol"
  | "name"
  | "exchange"
  | "quantity"
  | "averageCost"
  | "investmentAmount"
  | "currentPrice"
  | "marketValue"
  | "acquiredAt"
  | "analysisSymbol";

export type PortfolioImportMapping = Record<PortfolioImportField, number | null>;
export type PortfolioCell = string | number | boolean | Date | null;
export type PortfolioWorkbook = {
  filename: string;
  sheets: Array<{ name: string; rows: PortfolioCell[][] }>;
};

export type PortfolioImportAnalysis = {
  filename: string;
  sheetIndex: number;
  sheetName: string;
  sheetNames: string[];
  headerRowIndex: number;
  headers: string[];
  mapping: PortfolioImportMapping;
  mappingConfidence: number;
  mappingScores: Record<string, number>;
  issues: string[];
  score: number;
  dataRows: PortfolioCell[][];
  previewRows: PortfolioCell[][];
};

export type PortfolioImportResult = {
  holdings: HoldingInput[];
  lots: HoldingLotInput[];
  warnings: string[];
  quality: {
    sheetName: string;
    headerRowNumber: number;
    sourceRows: number;
    lotRows: number;
    holdingRows: number;
    skippedRows: number;
    mappingConfidence: number;
  };
};

export const PORTFOLIO_IMPORT_FIELDS: Array<{
  key: PortfolioImportField;
  label: string;
  required: boolean;
}>;

export class PortfolioImportError extends Error {
  issues: string[];
  constructor(message: string, issues?: string[]);
}

export function readPortfolioWorkbook(file: File): Promise<PortfolioWorkbook>;
export function readPastedPortfolio(input: string): PortfolioWorkbook;
export function analyzePortfolioWorkbook(
  workbook: PortfolioWorkbook,
  options?: { sheetIndex?: number; headerRowIndex?: number },
): PortfolioImportAnalysis;
export function validateImportMapping(mapping: PortfolioImportMapping): string[];
export function normalizePortfolioImport(
  analysis: PortfolioImportAnalysis,
  mapping: PortfolioImportMapping,
  options?: { defaultExchange?: string },
): PortfolioImportResult;
