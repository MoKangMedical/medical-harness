export interface OpenClawExecuteRequest {
  target: string;
  kind?: "auto" | "tool" | "toolchain";
  context?: Record<string, unknown>;
  params?: Record<string, unknown>;
  overrides?: Record<string, Record<string, unknown>>;
}

export interface OpenClawClientOptions {
  baseUrl?: string;
  fetchImpl?: typeof fetch;
  headers?: Record<string, string>;
}

export class OpenClawError extends Error {
  details: unknown;
  constructor(message: string, details?: unknown);
}

export class OpenClawClient {
  constructor(options?: OpenClawClientOptions);
  request(path: string, options?: { method?: string; body?: unknown; headers?: Record<string, string> }): Promise<any>;
  healthCheck(): Promise<any>;
  listTools(): Promise<any>;
  listToolchains(): Promise<any>;
  execute(request: OpenClawExecuteRequest): Promise<any>;
  executeTool(target: string, options?: { context?: Record<string, unknown>; params?: Record<string, unknown> }): Promise<any>;
  executeToolchain(
    target: string,
    options?: { context?: Record<string, unknown>; overrides?: Record<string, Record<string, unknown>> },
  ): Promise<any>;
  diagnose(payload: Record<string, unknown>): Promise<any>;
  drugDiscovery(payload: Record<string, unknown>): Promise<any>;
  health(payload: Record<string, unknown>): Promise<any>;
  mediaRuntime(): Promise<any>;
}
