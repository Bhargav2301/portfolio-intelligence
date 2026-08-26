import { getAgentEvents } from "../../../../../../lib/agent-runtime";
import { ownerFromRequest } from "../../../../../../lib/data";

export const dynamic = "force-dynamic";

export async function GET(request: Request, context: { params: Promise<{ runId: string }> }) {
  try {
    const { runId } = await context.params;
    const after = Number(new URL(request.url).searchParams.get("after") ?? 0);
    return Response.json(await getAgentEvents(ownerFromRequest(request), runId, Number.isFinite(after) ? after : 0));
  } catch (error) {
    return Response.json({ error: error instanceof Error ? error.message : "Agent events unavailable" }, { status: 502 });
  }
}
