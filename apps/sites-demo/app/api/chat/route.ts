import { getDashboard, ownerFromRequest } from "../../../lib/data";
import { answerWithPortfolioLlm, type PortfolioChatHistory } from "../../../lib/portfolio-llm";
import type { ChatResponse } from "../../../lib/types";

export const dynamic = "force-dynamic";

function money(value: number) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(value);
}

export async function POST(request: Request) {
  try {
    const { prompt, history } = await request.json() as { prompt?: string; history?: PortfolioChatHistory };
    const query = prompt?.trim().toLowerCase() ?? "";
    if (!query) return Response.json({ error: "Ask a portfolio question" }, { status: 400 });
    if (query.length > 2_000) return Response.json({ error: "Keep portfolio questions under 2,000 characters" }, { status: 400 });
    const dashboard = await getDashboard(ownerFromRequest(request));
    const top = dashboard.positions[0];
    const weakest = [...dashboard.positions].sort((a, b) => a.returnPercent - b.returnPercent)[0];
    let intent = "portfolio_overview";
    let status: ChatResponse["status"] = "grounded";
    let engine: ChatResponse["engine"] = "deterministic";
    let model: string | undefined;
    const sourceDescription = dashboard.sourceMode === "connected" ? "linked holding snapshot" : dashboard.sourceMode === "manual" ? "manual holding snapshot" : "demo portfolio";
    let answer = `The ${sourceDescription} is valued at ${money(dashboard.metrics.totalValue)}, with an unrealized return of ${dashboard.metrics.returnPercent.toFixed(1)}%. ${top.symbol} is the largest position at ${top.allocationPercent.toFixed(1)}% of current value.`;
    let evidence = dashboard.evidence.slice(0, 3);

    const isRestricted = /\b(buy|sell|hold|recommend|should i|trade for me|place (?:a |an )?order)\b/.test(query);
    if (isRestricted) {
      intent = "recommendation_request";
      status = "restricted";
      answer = "Personalized buy, sell, or hold advice is disabled in this test release. The deterministic policy returns ‘insufficient evidence’ rather than turning a portfolio snapshot into advice. I can still explain allocation, performance, risk, scenarios, and the cited research record.";
    } else if (/risk|concentr|exposure/.test(query)) {
      intent = "risk_analysis";
      answer = `${top.symbol} is the largest allocation at ${top.allocationPercent.toFixed(1)}%. ${weakest.symbol} has the weakest unrealized return at ${weakest.returnPercent.toFixed(1)}%. This is concentration and performance analysis, not a direction to trade.`;
      evidence = dashboard.evidence.filter((item) => item.symbol === top.symbol || item.symbol === weakest.symbol);
    } else if (/perform|gain|return|profit|loss/.test(query)) {
      intent = "performance_attribution";
      const best = [...dashboard.positions].sort((a, b) => b.unrealizedGain - a.unrealizedGain)[0];
      answer = `Unrealized gain is ${money(dashboard.metrics.totalGain)} on a cost basis of ${money(dashboard.metrics.totalCost)}. ${best.symbol} contributes the largest unrealized gain at ${money(best.unrealizedGain)}. Values come from the time-stamped ${dashboard.sourceMode} observations shown in the portfolio.`;
      evidence = dashboard.evidence.filter((item) => item.symbol === best.symbol);
    } else if (/news|evidence|source|filing|research/.test(query)) {
      intent = "evidence_lookup";
      answer = `${dashboard.evidence.length} research records are attached to the current holdings, and ${dashboard.metrics.evidenceCoverage.toFixed(0)}% of positions have a verified source in this pilot. The source timestamps determine whether a record can support an explanation.`;
    } else if (/scenario|what if|drop|rise|change/.test(query)) {
      intent = "scenario_simulation";
      answer = "Use the Scenario Lab to apply a price shock to one position. The result is a deterministic arithmetic impact on portfolio value; it does not predict that the shock will occur.";
      evidence = [];
    }

    if (!isRestricted) {
      try {
        const llmAnswer = await answerWithPortfolioLlm({
          dashboard,
          prompt: prompt!.trim(),
          history: Array.isArray(history)
            ? history.filter((item) => item && (item.role === "user" || item.role === "assistant") && typeof item.content === "string")
            : [],
        });
        if (llmAnswer) {
          answer = llmAnswer.answer;
          intent = "llm_account_analysis";
          engine = "llm";
          model = llmAnswer.model;
          const cited = dashboard.evidence.filter((item) => answer.toUpperCase().includes(item.symbol.toUpperCase()));
          evidence = (cited.length > 0 ? cited : dashboard.evidence).slice(0, 3);
        }
      } catch {
        engine = "deterministic-fallback";
      }
    }

    const response: ChatResponse = { answer, intent, status, evidence, asOf: dashboard.asOf, engine, model };
    return Response.json(response);
  } catch {
    return Response.json({ error: "The portfolio answer could not be prepared" }, { status: 500 });
  }
}
