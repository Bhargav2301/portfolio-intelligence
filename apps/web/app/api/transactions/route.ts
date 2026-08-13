import { addTransaction, getDashboard, ownerFromRequest, reverseTransaction } from "../../../lib/data";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  try {
    const owner = ownerFromRequest(request);
    const payload = await request.json() as Record<string, unknown>;
    if (payload.action === "reverse") {
      if (typeof payload.transactionId !== "string") throw new Error("transactionId is required");
      await reverseTransaction(owner, payload.transactionId);
    } else {
      if (payload.type !== "buy" && payload.type !== "sell") throw new Error("Transaction type must be buy or sell");
      await addTransaction(owner, {
        symbol: String(payload.symbol ?? "").toUpperCase(),
        type: payload.type,
        quantity: Number(payload.quantity),
        unitPrice: Number(payload.unitPrice),
        fees: Number(payload.fees ?? 0),
        occurredAt: String(payload.occurredAt ?? ""),
        idempotencyKey: String(payload.idempotencyKey ?? crypto.randomUUID()),
      });
    }
    return Response.json(await getDashboard(owner), { status: 201 });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to record transaction";
    return Response.json({ error: message }, { status: message.includes("UNIQUE") ? 409 : 400 });
  }
}
