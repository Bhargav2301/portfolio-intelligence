import "server-only";

import type { NextRequest } from "next/server";

import {
  csrfMatches,
  getBrowserSession,
  requiresOidc,
  SESSION_COOKIE,
} from "@/lib/server/session";


const SAFE_REQUEST_HEADERS = [
  "accept",
  "content-type",
  "if-match",
  "idempotency-key",
  "traceparent",
];


function mutation(method: string): boolean {
  return !["GET", "HEAD", "OPTIONS"].includes(method.toUpperCase());
}


function sameOrigin(request: NextRequest): boolean {
  const origin = request.headers.get("origin");
  if (!origin) return false;
  const expected = process.env.PUBLIC_APP_ORIGIN ?? request.nextUrl.origin;
  return origin === expected;
}


export async function proxyToService(
  request: NextRequest,
  path: string[],
  base: string,
): Promise<Response> {
  const headers = new Headers();
  for (const name of SAFE_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  headers.set("X-Request-Id", crypto.randomUUID());
  if (!headers.has("traceparent")) {
    headers.set("traceparent", `00-${crypto.randomUUID().replaceAll("-", "")}-${crypto.randomUUID().replaceAll("-", "").slice(0, 16)}-01`);
  }

  if (requiresOidc()) {
    const session = await getBrowserSession(request.cookies.get(SESSION_COOKIE)?.value);
    if (!session) {
      return Response.json({ detail: { code: "AUTH_REQUIRED", message: "Sign in again." } }, { status: 401 });
    }
    if (mutation(request.method)) {
      if (!sameOrigin(request)) {
        return Response.json({ detail: { code: "ORIGIN_REJECTED", message: "Request origin was rejected." } }, { status: 403 });
      }
      if (!csrfMatches(session, request.headers.get("x-csrf-token"))) {
        return Response.json({ detail: { code: "CSRF_REJECTED", message: "The request could not be verified." } }, { status: 403 });
      }
    }
    headers.set("Authorization", `Bearer ${session.accessToken}`);
    headers.set("X-Workspace-Id", session.workspaceId);
  } else {
    headers.set(
      "X-Workspace-Id",
      process.env.DEV_WORKSPACE_ID ?? "00000000-0000-0000-0000-000000000001",
    );
    headers.set(
      "X-User-Id",
      process.env.DEV_USER_ID ?? "00000000-0000-0000-0000-000000000002",
    );
  }

  const target = new URL(`/${path.join("/")}${request.nextUrl.search}`, base);
  const response = await fetch(target, {
    method: request.method,
    headers,
    body: mutation(request.method) ? request.body : undefined,
    duplex: "half",
    cache: "no-store",
  } as RequestInit & { duplex: "half" });
  const outgoing = new Headers(response.headers);
  outgoing.delete("content-encoding");
  outgoing.delete("content-length");
  outgoing.delete("set-cookie");
  return new Response(response.body, {
    status: response.status,
    headers: outgoing,
  });
}
