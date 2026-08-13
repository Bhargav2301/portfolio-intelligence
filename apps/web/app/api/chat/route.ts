import { getDashboard, ownerFromRequest } from "../../../lib/data";
import type { ChatResponse } from "../../../lib/types";

export const dynamic = "force-dynamic";

function money(value: number) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(value);
}

export async function POST(request: Request) {
  try {
    const { prompt } = await request.json() as { prompt?: string };
    const query = prompt?.trim().toLowerCase() ?? "";
    if (!query) return Response.json({ error: "Ask a portfolio question" }, { status: 400 });
    const dashboard = await getDashboard(ownerFromRequest(request));
    const top = dashboard.positions[0];
    const weakest = [...dashboard.positions].sort((a, b) => a.returnPercent - b.returnPercent)[0];
    let intent = "portfolio_overview";
    let status: ChatResponse["status"] = "grounded";
    let answer = `The demo portfolio is valued at ${money(dashboard.metrics.totalValue)}, with an unrealized return of ${dashboard.metrics.returnPercent.toFixed(1)}%. ${top.symbol} is the largest position at ${top.allocationPercent.toFixed(1)}% of current value.`;
    let evidence = dashboard.evidence.slice(0, 3);

    if (/buy|sell|hold|recommend|should i/.test(query)) {
      intent = "recommendation_request";
      status = "restricted";
      answer = "Personalized buy, sell, or hold advice is disabled in this test release. The deterministic policy returns ‘insufficient evidence’ rather than turning a demo snapshot into advice. I can still explain allocation, performance, risk, scenarios, and the cited research record.";
    } else if (/risk|concentr|exposure/.test(query)) {
      intent = "risk_analysis";
      answer = `${top.symbol} is the largest allocation at ${top.allocationPercent.toFixed(1)}%. ${weakest.symbol} has the weakest unrealized return at ${weakest.returnPercent.toFixed(1)}%. This is concentration and performance analysis, not a direction to trade.`;
      evidence = dashboard.evidence.filter((item) => item.symbol === top.symbol || item.symbol === weakest.symbol);
    } else if (/perform|gain|return|profit|loss/.test(query)) {
      intent = "performance_attribution";
      const best = [...dashboard.positions].sort((a, b) => b.unrealizedGain - a.unrealizedGain)[0];
      answer = `Unrealized gain is ${money(dashboard.metrics.totalGain)} on a cost basis of ${money(dashboard.metrics.totalCost)}. ${best.symbol} contributes the largest unrealized gain at ${money(best.unrealizedGain)}. Values come from the time-stamped demo price observations shown in the evidence drawer.`;
      evidence = dashboard.evidence.filter((item) => item.symbol === best.symbol);
    } else if (/news|evidence|source|filing|research/.test(query)) {
      intent = "evidence_lookup";
      answer = `${dashboard.evidence.length} demo research records are attached to the current holdings, and ${dashboard.metrics.evidenceCoverage.toFixed(0)}% of positions have a Tier 1 demo source. These records demonstrate provenance behavior; they are not live market news.`;
    } else if (/scenario|what if|drop|rise|change/.test(query)) {
      intent = "scenario_simulation";
      answer = "Use the Scenario Lab to apply a price shock to one position. The result is a deterministic arithmetic impact on portfolio value; it does not predict that the shock will occur.";
      evidence = [];
    }

    const response: ChatResponse = { answer, intent, status, evidence, asOf: dashboard.asOf };
    return Response.json(response);
  } catch (error) {
    return Response.json(
      { error: error instanceof Error ? error.message : "Unable to answer" },
      { status: 500 },
    );
  }
}
