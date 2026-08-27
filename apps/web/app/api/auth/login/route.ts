import { NextRequest, NextResponse } from "next/server";

import {
  authConfiguration,
  isSecureCookie,
  OAUTH_COOKIE,
  pkceChallenge,
  randomToken,
  safeReturnTo,
  signOpaque,
  storeOAuthTransaction,
} from "@/lib/server/session";


export async function GET(request: NextRequest) {
  const config = authConfiguration();
  const state = randomToken();
  const verifier = randomToken(48);
  const nonce = randomToken();
  const stepUp = request.nextUrl.searchParams.get("step_up") === "1";
  const returnTo = safeReturnTo(request.nextUrl.searchParams.get("return_to"));
  await storeOAuthTransaction({ state, verifier, nonce, returnTo, stepUp });

  const authorize = new URL(`${config.oauthBaseUrl}/oauth2/authorize`);
  authorize.searchParams.set("response_type", "code");
  authorize.searchParams.set("client_id", config.clientId);
  authorize.searchParams.set("redirect_uri", config.redirectUri);
  authorize.searchParams.set("scope", process.env.OIDC_SCOPES ?? "openid email profile");
  authorize.searchParams.set("state", state);
  authorize.searchParams.set("nonce", nonce);
  authorize.searchParams.set("code_challenge_method", "S256");
  authorize.searchParams.set("code_challenge", pkceChallenge(verifier));
  if (stepUp) {
    authorize.searchParams.set("prompt", "login");
    authorize.searchParams.set("max_age", "0");
  }

  const response = NextResponse.redirect(authorize);
  response.cookies.set(OAUTH_COOKIE, signOpaque(state), {
    httpOnly: true,
    secure: isSecureCookie(),
    sameSite: "lax",
    path: "/api/auth/callback",
    maxAge: 600,
  });
  return response;
}


export const dynamic = "force-dynamic";
