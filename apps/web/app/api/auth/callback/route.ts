import { NextRequest, NextResponse } from "next/server";

import {
  authConfiguration,
  consumeOAuthTransaction,
  createBrowserSession,
  CSRF_COOKIE,
  deleteBrowserSession,
  isSecureCookie,
  OAUTH_COOKIE,
  SESSION_COOKIE,
  signOpaque,
  validateCognitoTokens,
  verifyOpaque,
} from "@/lib/server/session";


type TokenResponse = {
  access_token?: string;
  id_token?: string;
  refresh_token?: string;
  error?: string;
};


function failed(request: NextRequest, code: string): NextResponse {
  const target = new URL("/", request.nextUrl.origin);
  target.searchParams.set("auth_error", code);
  return NextResponse.redirect(target);
}


export async function GET(request: NextRequest) {
  const code = request.nextUrl.searchParams.get("code");
  const state = request.nextUrl.searchParams.get("state");
  const cookieState = verifyOpaque(request.cookies.get(OAUTH_COOKIE)?.value);
  if (!code || !state || !cookieState || state !== cookieState) return failed(request, "state");

  const transaction = await consumeOAuthTransaction(state);
  if (!transaction || transaction.state !== state) return failed(request, "expired");
  const config = authConfiguration();
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    client_id: config.clientId,
    code,
    redirect_uri: config.redirectUri,
    code_verifier: transaction.verifier,
  });
  const tokenResponse = await fetch(`${config.oauthBaseUrl}/oauth2/token`, {
    method: "POST",
    headers: {
      Authorization: `Basic ${Buffer.from(`${config.clientId}:${config.clientSecret}`).toString("base64")}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body,
    cache: "no-store",
  });
  const tokens = await tokenResponse.json() as TokenResponse;
  if (!tokenResponse.ok || !tokens.access_token || !tokens.id_token) return failed(request, "exchange");

  try {
    const identity = await validateCognitoTokens(tokens.access_token, tokens.id_token, transaction.nonce);
    const session = await createBrowserSession({
      ...identity,
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token,
    });
    await deleteBrowserSession(request.cookies.get(SESSION_COOKIE)?.value);
    const response = NextResponse.redirect(new URL(transaction.returnTo, request.nextUrl.origin));
    response.cookies.delete(OAUTH_COOKIE);
    response.cookies.set(SESSION_COOKIE, signOpaque(session.id), {
      httpOnly: true,
      secure: isSecureCookie(),
      sameSite: "lax",
      path: "/",
      expires: new Date(session.expiresAt * 1000),
    });
    response.cookies.set(CSRF_COOKIE, session.csrfToken, {
      httpOnly: false,
      secure: isSecureCookie(),
      sameSite: "strict",
      path: "/",
      expires: new Date(session.expiresAt * 1000),
    });
    return response;
  } catch {
    return failed(request, "identity");
  }
}


export const dynamic = "force-dynamic";
