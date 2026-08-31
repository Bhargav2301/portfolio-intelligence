import { getChatGPTUser } from "./chatgpt-auth";
import PortfolioApp from "./portfolio-app";

export const dynamic = "force-dynamic";

export default async function Home() {
  const user = await getChatGPTUser();

  return (
    <PortfolioApp
      user={{
        displayName: user?.displayName ?? "Demo workspace",
        email: user?.email ?? null,
      }}
    />
  );
}
