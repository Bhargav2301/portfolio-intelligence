import { ownerFromRequest } from "../../../../lib/data";
import { getPortfolioLlmStatus } from "../../../../lib/portfolio-llm";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    ownerFromRequest(request);
    return Response.json({ llm: getPortfolioLlmStatus() }, { headers: { "cache-control": "no-store" } });
  } catch {
    return Response.json({ error: "Sign in to view account settings" }, { status: 401 });
  }
}
