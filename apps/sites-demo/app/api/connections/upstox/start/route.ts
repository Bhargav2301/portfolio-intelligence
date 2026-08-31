import { ownerFromRequest, startUpstoxConnection } from "../../../../../lib/data";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    return Response.redirect(await startUpstoxConnection(ownerFromRequest(request)), 302);
  } catch (error) {
    const code = error instanceof Error ? error.message : "";
    if (code === "AUTHENTICATION_REQUIRED") return Response.json({ error: "Sign in to link Upstox" }, { status: 401 });
    if (code === "CONNECTOR_NOT_CONFIGURED") return Response.json({ error: "The Upstox pilot is not configured on this deployment" }, { status: 503 });
    return Response.json({ error: "The secure connection could not be started" }, { status: 500 });
  }
}
