declare global {
  interface D1Result<T = unknown> {
    results: T[];
    success: boolean;
  }

  interface D1PreparedStatement {
    bind(...values: unknown[]): D1PreparedStatement;
    first<T = Record<string, unknown>>(): Promise<T | null>;
    all<T = Record<string, unknown>>(): Promise<D1Result<T>>;
    run<T = Record<string, unknown>>(): Promise<D1Result<T>>;
  }

  interface D1Database {
    prepare(query: string): D1PreparedStatement;
    batch<T = unknown>(statements: D1PreparedStatement[]): Promise<D1Result<T>[]>;
  }

  interface Fetcher {
    fetch(request: Request): Promise<Response>;
  }

  interface PIConnectorEnv {
    UPSTOX_CLIENT_ID?: string;
    UPSTOX_CLIENT_SECRET?: string;
    UPSTOX_REDIRECT_URI?: string;
    CONNECTOR_ENCRYPTION_KEY?: string;
    TRADING_AGENTS_API_URL?: string;
    TRADING_AGENTS_API_TOKEN?: string;
  }

  var __PI_DB: D1Database | undefined;
  var __PI_ENV: PIConnectorEnv | undefined;
}

export {};
