import {
  createDemoPortfolio,
  createManualPortfolio,
  getPortfolioResponse,
  ownerFromRequest,
} from "../../../lib/data";
import type { HoldingInput } from "../../../lib/types";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    return Response.json(await getPortfolioResponse(ownerFromRequest(request)));
  } catch (error) {
    return apiError(error);
  }
}

export async function POST(request: Request) {
  try {
    const owner = ownerFromRequest(request);
    const input = await request.json() as {
      mode?: "manual" | "demo";
      name?: string;
      baseCurrency?: "INR";
      holdings?: HoldingInput[];
    };
    if (input.mode === "demo") return Response.json(await createDemoPortfolio(owner), { status: 201 });
    if (input.mode !== "manual") return Response.json({ error: "Choose manual setup or the demo portfolio" }, { status: 400 });
    return Response.json(await createManualPortfolio(owner, {
      name: input.name ?? "",
      baseCurrency: "INR",
      holdings: Array.isArray(input.holdings) ? input.holdings : [],
    }), { status: 201 });
  } catch (error) {
    return apiError(error);
  }
}

function apiError(error: unknown) {
  const message = error instanceof Error ? error.message : "";
  if (message === "AUTHENTICATION_REQUIRED") {
    return Response.json({ error: "Sign in to access your portfolio" }, { status: 401 });
  }
  const safeValidation = [
    "Holding ", "quantity must", "average cost", "current price", "appears more than once",
    "Enter a portfolio", "Add between", "A portfolio already exists",
  ];
  if (safeValidation.some((prefix) => message.includes(prefix))) {
    return Response.json({ error: message }, { status: 400 });
  }
  return Response.json({ error: "We couldn't load the portfolio. Please try again." }, { status: 500 });
}
