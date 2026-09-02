import type { ChatPresentation, DashboardData } from "./types";

const money = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

const percent = (value: number) => `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;

export function buildChatPresentation(
  dashboard: DashboardData,
  intent: string,
): ChatPresentation {
  const byGain = [...dashboard.positions].sort((left, right) => right.unrealizedGain - left.unrealizedGain);
  const byAllocation = [...dashboard.positions].sort((left, right) => right.allocationPercent - left.allocationPercent);
  const tone = dashboard.metrics.returnPercent > 0 ? "positive" : dashboard.metrics.returnPercent < 0 ? "negative" : "neutral";
  const overviewKpis: ChatPresentation["kpis"] = [
    {
      label: "Portfolio value",
      value: money.format(dashboard.metrics.totalValue),
      detail: `${dashboard.positions.length} current holding${dashboard.positions.length === 1 ? "" : "s"}`,
      tone: "neutral",
    },
    {
      label: "Unrealized return",
      value: percent(dashboard.metrics.returnPercent),
      detail: `${money.format(dashboard.metrics.totalGain)} versus cost basis`,
      tone,
    },
    {
      label: "Verified coverage",
      value: `${dashboard.metrics.evidenceCoverage.toFixed(0)}%`,
      detail: "Positions with reviewed evidence",
      tone: dashboard.metrics.evidenceCoverage >= 70 ? "positive" : "neutral",
    },
  ];

  if (intent === "risk_analysis") {
    return {
      title: "Concentration and exposure",
      kpis: [
        overviewKpis[0],
        {
          label: "Largest position",
          value: byAllocation[0] ? `${byAllocation[0].allocationPercent.toFixed(1)}%` : "—",
          detail: byAllocation[0]?.symbol ?? "No position",
          tone: byAllocation[0] && byAllocation[0].allocationPercent > dashboard.agentPolicy.maxPositionWeightPercent ? "negative" : "neutral",
        },
        {
          label: "Policy position cap",
          value: `${dashboard.agentPolicy.maxPositionWeightPercent.toFixed(0)}%`,
          detail: "Descriptive guardrail, not a trade instruction",
          tone: "neutral",
        },
      ],
      chart: {
        type: "bar",
        title: "Allocation by holding",
        unit: "percent",
        categories: byAllocation.slice(0, 10).map((position) => position.symbol),
        series: [{ name: "Portfolio weight", values: byAllocation.slice(0, 10).map((position) => position.allocationPercent) }],
      },
      table: {
        title: "Largest exposures",
        columns: ["Holding", "Allocation", "Market value", "Unrealized return"],
        rows: byAllocation.slice(0, 8).map((position) => [
          position.symbol,
          `${position.allocationPercent.toFixed(2)}%`,
          money.format(position.marketValue),
          percent(position.returnPercent),
        ]),
      },
      note: "Allocation is calculated from the current authenticated portfolio snapshot.",
    };
  }

  if (intent === "performance_attribution") {
    return {
      title: "Return attribution",
      kpis: overviewKpis,
      chart: {
        type: "bar",
        title: "Unrealized gain contribution",
        unit: "currency",
        categories: byGain.slice(0, 10).map((position) => position.symbol),
        series: [{ name: "Unrealized gain", values: byGain.slice(0, 10).map((position) => position.unrealizedGain) }],
      },
      table: {
        title: "Holding-level attribution",
        columns: ["Holding", "Cost basis", "Market value", "Gain / loss", "Return"],
        rows: byGain.slice(0, 8).map((position) => [
          position.symbol,
          money.format(position.costBasis),
          money.format(position.marketValue),
          money.format(position.unrealizedGain),
          percent(position.returnPercent),
        ]),
      },
      note: "These are unrealized snapshot changes, not time-weighted or money-weighted returns.",
    };
  }

  if (intent === "evidence_lookup" || intent === "market_research") {
    const sourceRows = dashboard.evidence.slice(0, 10).map((item) => [
      item.symbol,
      item.publisher,
      item.title,
      item.status,
      new Date(item.publishedAt).toLocaleDateString("en-IN"),
    ]);
    return {
      title: intent === "market_research" ? "Live research with portfolio context" : "Evidence register",
      kpis: [
        overviewKpis[2],
        {
          label: "Verified records",
          value: String(dashboard.evidence.filter((item) => item.status === "verified").length),
          detail: "Attached to the current workspace",
          tone: "neutral",
        },
        {
          label: "Registered documents",
          value: String(dashboard.documents.length),
          detail: "May still require parsing and review",
          tone: "neutral",
        },
      ],
      table: sourceRows.length ? {
        title: "Portfolio evidence",
        columns: ["Holding", "Publisher", "Source", "Status", "Published"],
        rows: sourceRows,
      } : undefined,
      note: "Live web results appear as citations below the answer; portfolio evidence remains separately provenance-tracked.",
    };
  }

  if (intent === "scenario_simulation") {
    return {
      title: "Scenario preparation",
      kpis: overviewKpis,
      table: {
        title: "Current scenario inputs",
        columns: ["Holding", "Current price", "Market value", "Portfolio weight"],
        rows: byAllocation.slice(0, 8).map((position) => [
          position.symbol,
          money.format(position.currentPrice),
          money.format(position.marketValue),
          `${position.allocationPercent.toFixed(2)}%`,
        ]),
      },
      note: "Use Scenario lab for deterministic shocks. The copilot does not turn a scenario into a forecast.",
    };
  }

  return {
    title: "Portfolio overview",
    kpis: overviewKpis,
    chart: dashboard.valueHistory.length > 1 ? {
      type: "line",
      title: "Tracked portfolio value",
      unit: "currency",
      categories: dashboard.valueHistory.map((point) => point.label),
      series: [{ name: "Portfolio", values: dashboard.valueHistory.map((point) => point.value) }],
    } : {
      type: "bar",
      title: "Current market value by holding",
      unit: "currency",
      categories: byAllocation.slice(0, 10).map((position) => position.symbol),
      series: [{ name: "Market value", values: byAllocation.slice(0, 10).map((position) => position.marketValue) }],
    },
    table: {
      title: "Current holdings",
      columns: ["Holding", "Quantity", "Market value", "Allocation", "Return"],
      rows: byAllocation.slice(0, 8).map((position) => [
        position.symbol,
        position.quantity.toLocaleString("en-IN"),
        money.format(position.marketValue),
        `${position.allocationPercent.toFixed(2)}%`,
        percent(position.returnPercent),
      ]),
    },
    note: dashboard.valueHistory.length > 1
      ? "The chart uses stored portfolio snapshots only."
      : "Portfolio history begins after tracked updates; no backfilled series was invented.",
  };
}
