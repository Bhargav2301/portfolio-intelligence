import { NextRequest } from "next/server";

import {
  getBrowserSession,
  requiresOidc,
  SESSION_COOKIE,
} from "@/lib/server/session";


export async function GET(request: NextRequest) {
  if (!requiresOidc()) {
    return Response.json({
      authenticated: true,
      environment: "development",
      workspace_id: process.env.DEV_WORKSPACE_ID,
    });
  }
  const session = await getBrowserSession(request.cookies.get(SESSION_COOKIE)?.value);
  if (!session) return Response.json({ authenticated: false }, { status: 401 });
  return Response.json({
    authenticated: true,
    environment: process.env.APP_ENV,
    workspace_id: session.workspaceId,
    subject: session.subject,
    auth_time: session.authTime,
    amr: session.amr,
    expires_at: session.expiresAt,
  });
}


export const dynamic = "force-dynamic";
