import { completeUpstoxConnection } from "../../../../../lib/data";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const requestUrl = new URL(request.url);
  const destination = new URL("/", request.url);
  try {
    const denied = requestUrl.searchParams.get("error");
    if (denied) throw new Error("AUTHORIZATION_DENIED");
    await completeUpstoxConnection(
      requestUrl.searchParams.get("code") ?? "",
      requestUrl.searchParams.get("state") ?? "",
    );
    destination.searchParams.set("connection", "upstox-ready");
  } catch (error) {
    const code = error instanceof Error ? error.message : "";
    destination.searchParams.set("connection", code === "AUTHORIZATION_DENIED" ? "upstox-denied" : "upstox-error");
  }
  return Response.redirect(destination, 302);
}
