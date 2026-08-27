import "server-only";

import {
  createHash,
  createHmac,
  randomBytes,
  timingSafeEqual,
} from "node:crypto";

import { createRemoteJWKSet, jwtVerify, type JWTPayload } from "jose";
import { createClient, type RedisClientType } from "redis";


export const SESSION_COOKIE = "spi_session";
export const CSRF_COOKIE = "spi_csrf";
export const OAUTH_COOKIE = "spi_oauth";

const SESSION_PREFIX = "spi:session:";
const OAUTH_PREFIX = "spi:oauth:";
const OAUTH_TTL_SECONDS = 600;

export type BrowserSession = {
  id: string;
  subject: string;
  accessToken: string;
  refreshToken?: string;
  workspaceId: string;
  csrfToken: string;
  authTime: number;
  amr: string[];
  expiresAt: number;
  createdAt: number;
};

export type OAuthTransaction = {
  state: string;
  nonce: string;
  verifier: string;
  returnTo: string;
  stepUp: boolean;
};

let redisClient: RedisClientType | undefined;
let jwks: ReturnType<typeof createRemoteJWKSet> | undefined;


export function requiresOidc(): boolean {
  return ["staging", "production"].includes((process.env.APP_ENV ?? "development").toLowerCase());
}


export function isSecureCookie(): boolean {
  return requiresOidc() || (process.env.PUBLIC_APP_ORIGIN ?? "").startsWith("https://");
}


export function authConfiguration() {
  const issuer = process.env.OIDC_ISSUER_URL?.replace(/\/$/, "");
  const clientId = process.env.OIDC_CLIENT_ID;
  const clientSecret = process.env.OIDC_CLIENT_SECRET;
  const oauthBaseUrl = process.env.OIDC_OAUTH_BASE_URL?.replace(/\/$/, "");
  const redirectUri = process.env.OIDC_REDIRECT_URI;
  const sessionSecret = process.env.SESSION_SECRET;
  const redisUrl = process.env.REDIS_URL;
  const missing = [
    ["OIDC_ISSUER_URL", issuer],
    ["OIDC_CLIENT_ID", clientId],
    ["OIDC_CLIENT_SECRET", clientSecret],
    ["OIDC_OAUTH_BASE_URL", oauthBaseUrl],
    ["OIDC_REDIRECT_URI", redirectUri],
    ["SESSION_SECRET", sessionSecret],
    ["REDIS_URL", redisUrl],
  ].filter(([, value]) => !value).map(([name]) => name);
  if (missing.length > 0) {
    throw new Error(`Production authentication is incomplete: ${missing.join(", ")}`);
  }
  if ((sessionSecret?.length ?? 0) < 32) {
    throw new Error("SESSION_SECRET must contain at least 32 characters.");
  }
  return {
    issuer: issuer!,
    clientId: clientId!,
    clientSecret: clientSecret!,
    oauthBaseUrl: oauthBaseUrl!,
    redirectUri: redirectUri!,
    sessionSecret: sessionSecret!,
    redisUrl: redisUrl!,
  };
}


async function redis(): Promise<RedisClientType> {
  if (!redisClient) {
    const config = authConfiguration();
    redisClient = createClient({ url: config.redisUrl });
    redisClient.on("error", (error) => {
      console.error(JSON.stringify({
        event: "session_store.error",
        code: "REDIS_ERROR",
        message: error instanceof Error ? error.name : "RedisError",
      }));
    });
  }
  if (!redisClient.isOpen) await redisClient.connect();
  return redisClient;
}


function signature(value: string): string {
  const secret = authConfiguration().sessionSecret;
  return createHmac("sha256", secret).update(value).digest("base64url");
}


export function signOpaque(value: string): string {
  return `${value}.${signature(value)}`;
}


export function verifyOpaque(value: string | undefined): string | null {
  if (!value) return null;
  const separator = value.lastIndexOf(".");
  if (separator < 1) return null;
  const candidate = value.slice(0, separator);
  const supplied = Buffer.from(value.slice(separator + 1));
  const expected = Buffer.from(signature(candidate));
  if (supplied.length !== expected.length || !timingSafeEqual(supplied, expected)) return null;
  return candidate;
}


export function randomToken(bytes = 32): string {
  return randomBytes(bytes).toString("base64url");
}


export function pkceChallenge(verifier: string): string {
  return createHash("sha256").update(verifier).digest("base64url");
}


export async function storeOAuthTransaction(transaction: OAuthTransaction): Promise<void> {
  const client = await redis();
  await client.set(`${OAUTH_PREFIX}${transaction.state}`, JSON.stringify(transaction), {
    EX: OAUTH_TTL_SECONDS,
    NX: true,
  });
}


export async function consumeOAuthTransaction(state: string): Promise<OAuthTransaction | null> {
  const client = await redis();
  const key = `${OAUTH_PREFIX}${state}`;
  const serialized = await client.getDel(key);
  return serialized ? JSON.parse(serialized) as OAuthTransaction : null;
}


export async function createBrowserSession(
  input: Omit<BrowserSession, "id" | "csrfToken" | "createdAt">,
): Promise<BrowserSession> {
  const session: BrowserSession = {
    ...input,
    id: randomToken(),
    csrfToken: randomToken(),
    createdAt: Math.floor(Date.now() / 1000),
  };
  const ttl = Math.max(1, session.expiresAt - Math.floor(Date.now() / 1000));
  const client = await redis();
  await client.set(`${SESSION_PREFIX}${session.id}`, JSON.stringify(session), { EX: ttl, NX: true });
  return session;
}


export async function getBrowserSession(cookieValue: string | undefined): Promise<BrowserSession | null> {
  const id = verifyOpaque(cookieValue);
  if (!id) return null;
  const client = await redis();
  const serialized = await client.get(`${SESSION_PREFIX}${id}`);
  if (!serialized) return null;
  const session = JSON.parse(serialized) as BrowserSession;
  if (session.expiresAt <= Math.floor(Date.now() / 1000)) {
    await client.del(`${SESSION_PREFIX}${id}`);
    return null;
  }
  return session;
}


export async function deleteBrowserSession(cookieValue: string | undefined): Promise<void> {
  const id = verifyOpaque(cookieValue);
  if (!id) return;
  const client = await redis();
  await client.del(`${SESSION_PREFIX}${id}`);
}


function tokenWorkspace(payload: JWTPayload): string | null {
  const direct = payload["custom:workspace_id"];
  if (typeof direct === "string" && direct) return direct;
  const listed = payload["custom:workspace_ids"];
  if (typeof listed === "string" && listed) return listed.split(",")[0]?.trim() || null;
  return process.env.DEFAULT_WORKSPACE_ID ?? null;
}


export async function validateCognitoTokens(
  accessToken: string,
  idToken: string,
  expectedNonce: string,
): Promise<{
  subject: string;
  workspaceId: string;
  authTime: number;
  amr: string[];
  expiresAt: number;
}> {
  const config = authConfiguration();
  jwks ??= createRemoteJWKSet(new URL(`${config.issuer}/.well-known/jwks.json`));
  const [accessResult, idResult] = await Promise.all([
    jwtVerify(accessToken, jwks, { issuer: config.issuer }),
    jwtVerify(idToken, jwks, {
      issuer: config.issuer,
      audience: config.clientId,
    }),
  ]);
  if (accessResult.payload.token_use !== "access" || accessResult.payload.client_id !== config.clientId) {
    throw new Error("The access token is not valid for this application.");
  }
  if (idResult.payload.token_use !== "id" || idResult.payload.nonce !== expectedNonce) {
    throw new Error("The identity token could not be bound to this login attempt.");
  }
  const subject = accessResult.payload.sub;
  const expiresAt = accessResult.payload.exp;
  const workspaceId = tokenWorkspace(idResult.payload);
  if (!subject || !expiresAt || !workspaceId) {
    throw new Error("The authenticated identity has no active workspace selector.");
  }
  const rawAmr = accessResult.payload.amr ?? idResult.payload.amr;
  return {
    subject,
    workspaceId,
    authTime: Number(idResult.payload.auth_time ?? 0),
    amr: Array.isArray(rawAmr) ? rawAmr.filter((item): item is string => typeof item === "string") : [],
    expiresAt,
  };
}


export function safeReturnTo(value: string | null): string {
  return value?.startsWith("/") && !value.startsWith("//") ? value : "/";
}


export function csrfMatches(session: BrowserSession, supplied: string | null): boolean {
  if (!supplied) return false;
  const left = Buffer.from(session.csrfToken);
  const right = Buffer.from(supplied);
  return left.length === right.length && timingSafeEqual(left, right);
}
