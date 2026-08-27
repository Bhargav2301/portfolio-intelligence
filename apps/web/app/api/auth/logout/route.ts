import { NextRequest, NextResponse } from "next/server";

import {
  csrfMatches,
  authConfiguration,
  CSRF_COOKIE,
  deleteBrowserSession,
  getBrowserSession,
  isSecureCookie,
  SESSION_COOKIE,
} from "@/lib/server/session";


export async function POST(request: NextRequest) {
  const expectedOrigin = process.env.PUBLIC_APP_ORIGIN ?? request.nextUrl.origin;
  if (request.headers.get("origin") !== expectedOrigin) {
    return Response.json(
      { detail: { code: "ORIGIN_REJECTED", message: "Request origin was rejected." } },
      { status: 403 },
    );
  }
  const cookie = request.cookies.get(SESSION_COOKIE)?.value;
  const session = await getBrowserSession(cookie);
  if (session && !csrfMatches(session, request.headers.get("x-csrf-token"))) {
    return Response.json({ detail: { code: "CSRF_REJECTED", message: "The request could not be verified." } }, { status: 403 });
  }
  if (session?.refreshToken) {
    const config = authConfiguration();
    await fetch(`${config.oauthBaseUrl}/oauth2/revoke`, {
      method: "POST",
      headers: {
        Authorization: `Basic ${Buffer.from(`${config.clientId}:${config.clientSecret}`).toString("base64")}`,
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: new URLSearchParams({ token: session.refreshToken, client_id: config.clientId }),
      cache: "no-store",
    }).catch(() => null);
  }
  await deleteBrowserSession(cookie);
  const response = NextResponse.json({ logged_out: true });
  response.cookies.set(SESSION_COOKIE, "", {
    httpOnly: true,
    secure: isSecureCookie(),
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });
  response.cookies.set(CSRF_COOKIE, "", {
    httpOnly: false,
    secure: isSecureCookie(),
    sameSite: "strict",
    path: "/",
    maxAge: 0,
  });
  return response;
}
