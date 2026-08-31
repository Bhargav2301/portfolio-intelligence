/** Cloudflare Worker entry point for the vinext-starter template. */
import { handleImageOptimization, DEFAULT_DEVICE_SIZES, DEFAULT_IMAGE_SIZES } from "vinext/server/image-optimization";
import handler from "vinext/server/app-router-entry";

interface Env {
  ASSETS: Fetcher;
  DB: D1Database;
  UPSTOX_CLIENT_ID?: string;
  UPSTOX_CLIENT_SECRET?: string;
  UPSTOX_REDIRECT_URI?: string;
  CONNECTOR_ENCRYPTION_KEY?: string;
  TRADING_AGENTS_API_URL?: string;
  TRADING_AGENTS_API_TOKEN?: string;
  PORTFOLIO_LLM_API_URL?: string;
  PORTFOLIO_LLM_API_KEY?: string;
  PORTFOLIO_LLM_MODEL?: string;
  PORTFOLIO_LLM_PROVIDER?: string;
  PORTFOLIO_RESET_VERSION?: string;
  IMAGES: {
    input(stream: ReadableStream): {
      transform(options: Record<string, unknown>): {
        output(options: { format: string; quality: number }): Promise<{ response(): Response }>;
      };
    };
  };
}

interface ExecutionContext {
  waitUntil(promise: Promise<unknown>): void;
  passThroughOnException(): void;
}

// Image security config. SVG sources with .svg extension auto-skip the
// optimization endpoint on the client side (served directly, no proxy).
// To route SVGs through the optimizer (with security headers), set
// dangerouslyAllowSVG: true in next.config.js and uncomment below:
// const imageConfig: ImageConfig = { dangerouslyAllowSVG: true };

const worker = {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    globalThis.__PI_DB = env.DB;
    globalThis.__PI_ENV = {
      UPSTOX_CLIENT_ID: env.UPSTOX_CLIENT_ID,
      UPSTOX_CLIENT_SECRET: env.UPSTOX_CLIENT_SECRET,
      UPSTOX_REDIRECT_URI: env.UPSTOX_REDIRECT_URI,
      CONNECTOR_ENCRYPTION_KEY: env.CONNECTOR_ENCRYPTION_KEY,
      TRADING_AGENTS_API_URL: env.TRADING_AGENTS_API_URL,
      TRADING_AGENTS_API_TOKEN: env.TRADING_AGENTS_API_TOKEN,
      PORTFOLIO_LLM_API_URL: env.PORTFOLIO_LLM_API_URL,
      PORTFOLIO_LLM_API_KEY: env.PORTFOLIO_LLM_API_KEY,
      PORTFOLIO_LLM_MODEL: env.PORTFOLIO_LLM_MODEL,
      PORTFOLIO_LLM_PROVIDER: env.PORTFOLIO_LLM_PROVIDER,
      PORTFOLIO_RESET_VERSION: env.PORTFOLIO_RESET_VERSION,
    };
    const url = new URL(request.url);

    if (url.pathname === "/_vinext/image") {
      const allowedWidths = [...DEFAULT_DEVICE_SIZES, ...DEFAULT_IMAGE_SIZES];
      return handleImageOptimization(request, {
        fetchAsset: (path) => env.ASSETS.fetch(new Request(new URL(path, request.url))),
        transformImage: async (body, { width, format, quality }) => {
          const result = await env.IMAGES.input(body).transform(width > 0 ? { width } : {}).output({ format, quality });
          return result.response();
        },
      }, allowedWidths);
    }

    return handler.fetch(request, env, ctx);
  },
};

export default worker;
