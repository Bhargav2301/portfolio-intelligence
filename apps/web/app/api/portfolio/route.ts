import { getDashboard, ownerFromRequest } from "../../../lib/data";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    return Response.json(await getDashboard(ownerFromRequest(request)));
  } catch (error) {
    return Response.json(
      { error: error instanceof Error ? error.message : "Unable to load portfolio" },
      { status: 500 },
    );
  }
}
