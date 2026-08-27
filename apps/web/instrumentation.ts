export async function register() {
  if (process.env.NEXT_RUNTIME !== "nodejs") return;
  const { authConfiguration, requiresOidc } = await import("@/lib/server/session");
  if (requiresOidc()) authConfiguration();
}
