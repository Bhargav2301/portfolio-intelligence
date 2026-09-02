import { ownerFromRequest, startGoogleMailboxConnection } from "../../../../../lib/data";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    return Response.redirect(await startGoogleMailboxConnection(ownerFromRequest(request)), 302);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Google connection could not start";
    return Response.redirect(new URL(`/?gmail_error=${encodeURIComponent(message)}`, request.url), 302);
  }
}
