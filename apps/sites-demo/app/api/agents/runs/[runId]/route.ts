import { getAgentRun } from "../../../../../lib/agent-runtime";
import { ownerFromRequest } from "../../../../../lib/data";

export const dynamic = "force-dynamic";

export async function GET(request: Request, context: { params: Promise<{ runId: string }> }) {
  try {
    const { runId } = await context.params;
    return Response.json(await getAgentRun(ownerFromRequest(request), runId));
  } catch (error) {
    return Response.json({ error: error instanceof Error ? error.message : "Agent run unavailable" }, { status: 502 });
  }
}
