export class OpenClawError extends Error {
  constructor(message, details = null) {
    super(message);
    this.name = "OpenClawError";
    this.details = details;
  }
}

async function readJson(response) {
  const text = await response.text();
  if (!text) {
    return {};
  }
  try {
    return JSON.parse(text);
  } catch {
    return { raw: text };
  }
}

export class OpenClawClient {
  constructor(options = {}) {
    const {
      baseUrl = "http://127.0.0.1:8001",
      fetchImpl = globalThis.fetch?.bind(globalThis),
      headers = {},
    } = options;

    if (!fetchImpl) {
      throw new OpenClawError("No fetch implementation available. Pass fetchImpl explicitly.");
    }

    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.fetch = fetchImpl;
    this.headers = { ...headers };
  }

  async request(path, options = {}) {
    const { method = "GET", body, headers = {} } = options;
    const response = await this.fetch(`${this.baseUrl}${path}`, {
      method,
      headers: {
        ...this.headers,
        ...headers,
        ...(body ? { "Content-Type": "application/json" } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });

    const payload = await readJson(response);
    if (!response.ok) {
      const detail = payload?.detail ?? payload;
      const message =
        typeof detail === "string"
          ? detail
          : detail?.error || `OpenClaw request failed with status ${response.status}`;
      throw new OpenClawError(message, detail);
    }
    return payload;
  }

  healthCheck() {
    return this.request("/health-check");
  }

  listTools() {
    return this.request("/api/tools");
  }

  listToolchains() {
    return this.request("/api/toolchains");
  }

  execute({ target, kind = "auto", context = {}, params = {}, overrides = {} }) {
    return this.request("/api/openclaw/execute", {
      method: "POST",
      body: { target, kind, context, params, overrides },
    });
  }

  executeTool(target, { context = {}, params = {} } = {}) {
    return this.execute({ target, kind: "tool", context, params });
  }

  executeToolchain(target, { context = {}, overrides = {} } = {}) {
    return this.execute({ target, kind: "toolchain", context, overrides });
  }

  diagnose(payload) {
    return this.request("/diagnose", { method: "POST", body: payload });
  }

  drugDiscovery(payload) {
    return this.request("/drug-discovery", { method: "POST", body: payload });
  }

  health(payload) {
    return this.request("/health", { method: "POST", body: payload });
  }

  mediaRuntime() {
    return this.request("/media/runtime");
  }
}
