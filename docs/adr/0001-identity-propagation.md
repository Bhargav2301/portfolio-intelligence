# ADR 0001: Opaque BFF sessions and verified identity propagation

- Status: Accepted
- Date: 2026-08-27

The public browser authenticates with Amazon Cognito authorization code plus PKCE. The Next.js
BFF validates returned tokens, stores them only in Redis, and sends an opaque signed session
identifier in a `Secure`, `HttpOnly`, `SameSite=Lax` cookie. State-changing requests require an
exact-origin check and a session-bound CSRF token. Browser-provided authorization, user, workspace,
host, and length headers are discarded.

The BFF forwards the validated access token and selected workspace. Core verifies issuer,
signature, expiry, token use, client, and scope, derives the internal user from issuer plus `sub`,
then revalidates active membership and role on every request. Workspace selection is never proof
of authority. Publication requires owner role, authentication no older than five minutes, and an
MFA/passkey method in `amr`.

Production and staging fail to start when this configuration is incomplete. Logout deletes the
server session and attempts Cognito refresh-token revocation.
