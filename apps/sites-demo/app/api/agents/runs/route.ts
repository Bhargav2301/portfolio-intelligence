import { startAgentRun } from "../../../../lib/agent-runtime";
import { ownerFromRequest } from "../../../../lib/data";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  try {
    const owner = ownerFromRequest(request);
    const input = await request.json().catch(() => ({})) as { selectedSymbols?: string[] };
    const selected = Array.isArray(input.selectedSymbols)
      ? input.selectedSymbols.filter((symbol): symbol is string => typeof symbol === "string")
      : undefined;
    return Response.json(await startAgentRun(owner, selected), { status: 202 });
  } catch (error) {
    return agentError(error);
  }
}

function agentError(error: unknown) {
  const message = error instanceof Error ? error.message : "Agent run could not be started";
  if (message === "AUTHENTICATION_REQUIRED") return Response.json({ error: "Sign in to run analysis" }, { status: 401 });
  if (message === "AGENT_RUNTIME_NOT_CONFIGURED") return Response.json({ error: "TradingAgents runtime is not configured" }, { status: 503 });
  return Response.json({ error: message }, { status: 502 });
}
