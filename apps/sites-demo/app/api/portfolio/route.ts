import {
  createManualPortfolio,
  getPortfolioResponse,
  ownerFromRequest,
} from "../../../lib/data";
import type { HoldingInput, HoldingLotInput, PortfolioImportSource } from "../../../lib/types";

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
      mode?: "manual";
      name?: string;
      baseCurrency?: "INR";
      holdings?: HoldingInput[];
      lots?: HoldingLotInput[];
      source?: PortfolioImportSource;
    };
    if (input.mode !== "manual") return Response.json({ error: "Choose manual setup or import a normalized portfolio file" }, { status: 400 });
    return Response.json(await createManualPortfolio(owner, {
      name: input.name ?? "",
      baseCurrency: "INR",
      holdings: Array.isArray(input.holdings) ? input.holdings : [],
      lots: Array.isArray(input.lots) ? input.lots : undefined,
      source: input.source,
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
    "Holding ", "Lot ", "quantity must", "average cost", "current price", "appears more than once",
    "lot quantity", "lot cost", "lot acquisition", "source row", "lot is absent", "lot quantities",
    "lot costs", "analysis symbol", "Normalized imports", "Enter a portfolio", "Add between", "A portfolio already exists",
    "Import source hash", "Import filename",
  ];
  if (safeValidation.some((prefix) => message.includes(prefix))) {
    return Response.json({ error: message }, { status: 400 });
  }
  return Response.json({ error: "We couldn't load the portfolio. Please try again." }, { status: 500 });
}
