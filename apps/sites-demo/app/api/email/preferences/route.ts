import {
  dismissEmailImportPrompt,
  getEmailImportStatus,
  ownerFromRequest,
  saveEmailImportPreference,
} from "../../../../lib/data";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    return Response.json(await getEmailImportStatus(ownerFromRequest(request)));
  } catch (error) {
    return Response.json({ error: error instanceof Error ? error.message : "Unable to load email import settings" }, { status: 400 });
  }
}

export async function POST(request: Request) {
  try {
    const input = await request.json() as { action?: string; wealthManagerEmail?: string; consent?: boolean };
    const owner = ownerFromRequest(request);
    if (input.action === "dismiss") return Response.json(await dismissEmailImportPrompt(owner));
    return Response.json(await saveEmailImportPreference(owner, input.wealthManagerEmail ?? "", Boolean(input.consent)));
  } catch (error) {
    return Response.json({ error: error instanceof Error ? error.message : "Unable to save email import settings" }, { status: 400 });
  }
}
