export type Portfolio = {
  id: string;
  name: string;
  portfolio_type: "self_managed" | "pms" | "model" | "interest";
  base_currency: string;
  benchmark_code: string;
  valuation_timezone: string;
  status: string;
  version: number;
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
  state: string;
  answer: string;
  stages: string[];
  policy: { decision?: string; reasons?: string[] };
  evidence: Array<Record<string, unknown>>;
  limitations: string[];
  as_of: string;
};

export async function requestJson<T>(
  url: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers: {
      ...(options?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...options?.headers,
    },
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

