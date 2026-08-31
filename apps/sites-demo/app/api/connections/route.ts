import { getConnections, ownerFromRequest, syncUpstoxHoldings } from "../../../lib/data";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    return Response.json({ connections: await getConnections(ownerFromRequest(request)) });
  } catch (error) {
    return connectionError(error);
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json() as { action?: string; provider?: string };
    if (body.action !== "sync" || body.provider !== "upstox") {
      return Response.json({ error: "Unsupported connection action" }, { status: 400 });
    }
    return Response.json(await syncUpstoxHoldings(ownerFromRequest(request)));
  } catch (error) {
    return connectionError(error);
  }
}

function connectionError(error: unknown) {
  const code = error instanceof Error ? error.message : "";
  if (code === "AUTHENTICATION_REQUIRED") return Response.json({ error: "Sign in to manage connections" }, { status: 401 });
  if (code === "CONNECTOR_NOT_CONFIGURED") return Response.json({ error: "The Upstox pilot is not configured on this deployment" }, { status: 503 });
  if (code === "BROKER_NOT_CONNECTED") return Response.json({ error: "Connect Upstox before refreshing holdings" }, { status: 409 });
  if (code === "BROKER_SESSION_EXPIRED") return Response.json({ error: "Your Upstox session expired. Reconnect to resume updates." }, { status: 409 });
  return Response.json({ error: "Holdings could not be refreshed. Existing data was kept." }, { status: 502 });
}
