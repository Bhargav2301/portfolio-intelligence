import type { NextRequest } from "next/server";


type RouteContext = { params: Promise<{ path: string[] }> };


async function proxy(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  const base = process.env.INTERNAL_AGENT_URL ?? "http://localhost:8001";
  const target = new URL("/" + path.join("/") + request.nextUrl.search, base);
  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.delete("content-length");
  const response = await fetch(target, {
    method: request.method,
    headers,
    body: request.method === "GET" || request.method === "HEAD" ? undefined : request.body,
    duplex: "half",
    cache: "no-store",
  } as RequestInit & { duplex: "half" });
  const outgoing = new Headers(response.headers);
  outgoing.delete("content-encoding");
  outgoing.delete("content-length");
  return new Response(response.body, {
    status: response.status,
    headers: outgoing,
  });
}


export const dynamic = "force-dynamic";
export const GET = proxy;
export const POST = proxy;

