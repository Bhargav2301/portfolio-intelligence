import { ownerFromRequest, registerEvidenceDocument } from "../../../lib/data";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  try {
    const input = await request.json() as {
      filename?: string;
      mimeType?: string;
      sourceHash?: string;
      symbol?: string;
      title?: string;
      publisher?: string;
      publishedAt?: string | null;
    };
    return Response.json(await registerEvidenceDocument(ownerFromRequest(request), {
      filename: input.filename ?? "",
      mimeType: input.mimeType ?? "",
      sourceHash: input.sourceHash ?? "",
      symbol: input.symbol ?? "",
      title: input.title ?? "",
      publisher: input.publisher ?? "",
      publishedAt: input.publishedAt ?? null,
    }), { status: 201 });
  } catch (error) {
    const message = error instanceof Error ? error.message : "";
    if (message === "AUTHENTICATION_REQUIRED") {
      return Response.json({ error: "Sign in to register evidence" }, { status: 401 });
    }
    const validation = [
      "Complete portfolio", "Choose a PDF", "Evidence files", "Evidence source hash",
      "Enter an evidence", "Enter a publisher", "Choose a symbol", "Enter a valid",
      "already registered",
    ];
    if (validation.some((item) => message.includes(item))) {
      return Response.json({ error: message }, { status: 400 });
    }
    return Response.json({ error: "The evidence document could not be registered" }, { status: 500 });
  }
}
