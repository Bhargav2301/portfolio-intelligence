import { deleteAllAccountData, ownerFromRequest } from "../../../../lib/data";

export const dynamic = "force-dynamic";

export async function DELETE(request: Request) {
  try {
    const origin = request.headers.get("origin");
    if (origin && origin !== new URL(request.url).origin) {
      return Response.json({ error: "Cross-origin deletion is not allowed" }, { status: 403 });
    }
    const input = await request.json() as { confirmation?: string };
    if (input.confirmation !== "DELETE") {
      return Response.json({ error: "Type DELETE to confirm account data removal" }, { status: 400 });
    }
    const result = await deleteAllAccountData(ownerFromRequest(request));
    return Response.json(result, { headers: { "cache-control": "no-store" } });
  } catch (error) {
    const code = error instanceof Error ? error.message : "";
    if (code === "AUTHENTICATION_REQUIRED") {
      return Response.json({ error: "Sign in to delete your portfolio data" }, { status: 401 });
    }
    return Response.json({ error: "Portfolio data could not be deleted. No partial result is shown." }, { status: 500 });
  }
}
