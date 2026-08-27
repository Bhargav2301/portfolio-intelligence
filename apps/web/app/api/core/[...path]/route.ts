import type { NextRequest } from "next/server";

import { proxyToService } from "@/lib/server/proxy";


type RouteContext = { params: Promise<{ path: string[] }> };


async function proxy(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  const base = process.env.INTERNAL_API_URL ?? "http://localhost:8000";
  return proxyToService(request, path, base);
}


export const dynamic = "force-dynamic";
export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const PUT = proxy;
export const DELETE = proxy;

