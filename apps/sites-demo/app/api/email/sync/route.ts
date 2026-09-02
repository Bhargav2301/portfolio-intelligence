import { ownerFromRequest, syncGoogleMailbox } from "../../../../lib/data";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  try {
    return Response.json(await syncGoogleMailbox(ownerFromRequest(request)));
  } catch (error) {
    return Response.json({ error: error instanceof Error ? error.message : "Mailbox sync failed" }, { status: 400 });
  }
}
