import { askAgentRun } from "../../../../lib/agent-runtime";
import { ownerFromRequest } from "../../../../lib/data";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  try {
    const input = await request.json() as { prompt?: string; runId?: string };
    const prompt = input.prompt?.trim();
    if (!prompt) return Response.json({ error: "Ask a question about an agent run" }, { status: 400 });
    return Response.json(await askAgentRun(ownerFromRequest(request), prompt, input.runId));
  } catch (error) {
    const message = error instanceof Error ? error.message : "Agent answer unavailable";
    return Response.json({ error: message }, { status: message === "AGENT_RUNTIME_NOT_CONFIGURED" ? 503 : 502 });
  }
}
