export type Portfolio = {
  id: string;
  name: string;
  portfolio_type: "self_managed" | "pms" | "model" | "interest";
  base_currency: string;
  benchmark_code: string;
  valuation_timezone: string;
  status: string;
  version: number;
  ledger_version: number;
  rules: {
    equal_weighting_allowed: boolean;
    protected_cash: { amount: string; currency: string };
    review_cadence: string;
  };
  created_at: string;
  updated_at: string;
};

export type UploadResult = {
  id: string;
  original_name: string;
  detected_type: string;
  source_role: string;
  authority_level: string;
  state: string;
  size_bytes: number;
  parser_summary: {
    warnings?: string[];
    structure?: Record<string, unknown>;
  };
};

export type AgentResult = {
  run_id: string;
  thread_id: string;
  state: string;
  answer: string;
  stages: string[];
  policy: { decision?: string; reasons?: string[] };
  evidence: Array<Record<string, unknown>>;
  citations: Array<{
    claim_key: string;
    evidence_id: string;
    value: string;
    unit: string;
    as_of: string;
    locator: string;
  }>;
  limitations: string[];
  proposal: {
    type?: string;
    status?: string;
    title?: string;
    candidate_actions?: Array<Record<string, string>>;
    constraints?: string[];
    can_execute: false;
  };
  perspectives: Record<string, string>;
  telemetry: Record<string, unknown>;
  as_of: string;
};

export type UploadInitiated = {
  upload_id: string;
  state: "initiated";
  upload_url: string;
  method: "POST" | "PUT";
  fields: Record<string, string>;
  required_headers: Record<string, string>;
  expires_at: string;
  version: number;
};

export type UploadCompleted = {
  job_id: string;
  state: string;
  resource_type: "upload";
  resource_id: string;
  document_id: string;
  extraction_run_id: string;
  import_batch_id: string;
};

export type ExtractedRecord = {
  id: string;
  extraction_run_id: string;
  source_row: number;
  raw_hash: string;
  normalized_data: Record<string, string | null>;
  confidence: string;
  state: string;
  version: number;
  edited_by: string | null;
  edited_at: string | null;
};

export type ReconciliationCase = {
  id: string;
  portfolio_id: string;
  extracted_record_id: string | null;
  kind: string;
  severity: string;
  state: string;
  details: Record<string, unknown>;
  resolution: Record<string, unknown>;
  resolved_by: string | null;
  resolved_at: string | null;
  created_at: string;
};

export type ImportBatch = {
  id: string;
  portfolio_id: string;
  document_id: string;
  extraction_run_id: string;
  state: string;
  version: number;
  base_ledger_version: number;
  content_hash: string;
  validated_hash: string | null;
  validation_summary: Record<string, unknown>;
  published_ledger_version: number | null;
  created_by: string;
  approved_by: string | null;
  published_at: string | null;
  created_at: string;
  updated_at: string;
};

export type PublicationAccepted = {
  job_id: string;
  import_batch_id: string;
  ledger_version: number;
  state: "completed";
  audit_event_id: string;
};

export type AnalyticsSnapshot = {
  snapshot_id?: string | null;
  portfolio_id: string;
  quality_state: "trusted" | "needs_review" | "partial" | "stale";
  as_of: string;
  known_at?: string | null;
  ledger_version: number;
  market_data_version?: string | null;
  methodology_version?: string | null;
  input_hash?: string | null;
  metrics: Record<string, string | null>;
  limitations: string[];
};

export type Holding = {
  instrument_reference: string;
  quantity: string;
  average_cost: string;
  last_price: string | null;
  market_value: string | null;
  cost_basis: string;
  unrealized_pnl: string | null;
  weight_percent: string | null;
  price_as_of: string | null;
};

export type LedgerSnapshot = {
  portfolio_id: string;
  as_of: string;
  ledger_version: number;
  cash_balance: string;
  available_cash: string;
  protected_cash: string;
  net_invested_capital: string;
  securities_market_value: string;
  total_value: string;
  realized_pnl: string;
  holdings: Holding[];
  limitations: string[];
};

export type MonitorAlert = {
  id: string;
  severity: "info" | "warning" | "critical";
  kind: string;
  title: string;
  detail: string;
  instrument_reference?: string | null;
  observed_value?: string | null;
  threshold_value?: string | null;
  evidence_ids: string[];
};

export type MonitorSnapshot = {
  portfolio_id: string;
  as_of: string;
  state: "clear" | "attention" | "blocked";
  alerts: MonitorAlert[];
  checked_rules: string[];
  limitations: string[];
};

export async function requestJson<T>(
  url: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers: {
      ...(options?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...csrfHeader(options?.method),
      ...options?.headers,
    },
    credentials: "same-origin",
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = payload?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail?.message ?? "Request failed with status " + response.status + ".";
    throw new Error(message);
  }
  return (await response.json()) as T;
}


function csrfHeader(method: string | undefined): Record<string, string> {
  if (!method || ["GET", "HEAD", "OPTIONS"].includes(method.toUpperCase())) return {};
  if (typeof document === "undefined") return {};
  const token = document.cookie
    .split("; ")
    .find((part) => part.startsWith("spi_csrf="))
    ?.slice("spi_csrf=".length);
  return token ? { "X-CSRF-Token": decodeURIComponent(token) } : {};
}


export async function requestJsonWithMetadata<T>(
  url: string,
  options?: RequestInit,
): Promise<{ data: T; etag: string | null }> {
  const response = await fetch(url, {
    ...options,
    headers: {
      ...(options?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...csrfHeader(options?.method),
      ...options?.headers,
    },
    credentials: "same-origin",
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = payload?.detail;
    const message = typeof detail === "string" ? detail : detail?.message ?? `Request failed with status ${response.status}.`;
    throw new Error(message);
  }
  return { data: await response.json() as T, etag: response.headers.get("etag") };
}


export async function uploadObject(
  initiated: UploadInitiated,
  file: File,
): Promise<void> {
  if (initiated.method === "POST") {
    const body = new FormData();
    for (const [key, value] of Object.entries(initiated.fields)) body.set(key, value);
    body.set("file", file);
    const response = await fetch(initiated.upload_url, { method: "POST", body });
    if (!response.ok) throw new Error("The quarantined object upload failed.");
    return;
  }
  const localUrl = initiated.upload_url.startsWith("/")
    ? `/api/core${initiated.upload_url}`
    : initiated.upload_url;
  const sameOrigin = localUrl.startsWith("/") || new URL(localUrl).origin === window.location.origin;
  const response = await fetch(localUrl, {
    method: "PUT",
    headers: {
      ...initiated.required_headers,
      ...(sameOrigin ? csrfHeader("PUT") : {}),
    },
    body: file,
    credentials: sameOrigin ? "same-origin" : "omit",
  });
  if (!response.ok) throw new Error("The quarantined object upload failed.");
}
