import { completeGoogleMailboxConnection } from "../../../../../lib/data";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const url = new URL(request.url);
  try {
    await completeGoogleMailboxConnection(url.searchParams.get("code") ?? "", url.searchParams.get("state") ?? "");
    return Response.redirect(new URL("/?gmail=connected", request.url), 302);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Google authorization failed";
    return Response.redirect(new URL(`/?gmail_error=${encodeURIComponent(message)}`, request.url), 302);
  }
}
