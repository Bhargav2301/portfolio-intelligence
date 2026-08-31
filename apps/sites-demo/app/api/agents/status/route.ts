import { getAgentRuntimeStatus } from "../../../../lib/agent-runtime";

export const dynamic = "force-dynamic";

export async function GET() {
  return Response.json(await getAgentRuntimeStatus());
}
