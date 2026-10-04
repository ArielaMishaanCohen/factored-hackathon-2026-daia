// Cliente del contrato de la API (design.md, sección 6).
import { mockChat, mockCustomers, mockLogin } from "./mock";
import type { ApiErrorBody, CasesResponse, ChatRequest, ChatResponse, DemoCustomer, HandoffPackage, HandoffSummary, HealthResponse, LoginResponse, OpsMetrics, Trace } from "./types";

const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";

export class ApiError extends Error {
  constructor(public status: number, public code: ApiErrorBody["error"]["code"], message: string) {
    super(message);
  }
}

// Dos sesiones a la vez (vista doble): la del cliente y la del agente.
export type Role = "customer" | "agent";
const tokens: Record<Role, string | null> = { customer: null, agent: null };
export const setToken = (t: string | null, role: Role = "customer") => { tokens[role] = t; };

async function call<T>(method: string, path: string, body?: unknown, role: Role = "customer"): Promise<T> {
  const token = tokens[role];
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      method,
      headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "INTERNAL", "No hay conexión con el servidor.");
  }
  if (res.status === 204) return undefined as T;
  let data: unknown;
  try { data = await res.json(); } catch { throw new ApiError(res.status, "INTERNAL", res.statusText || "Respuesta inválida."); }
  if (!res.ok) {
    const e = (data as ApiErrorBody).error;
    throw new ApiError(res.status, e?.code ?? "INTERNAL", e?.message ?? res.statusText);
  }
  return data as T;
}

export const api = {
  demoCustomers: async (): Promise<DemoCustomer[]> =>
    USE_MOCK ? mockCustomers : (await call<{ customers: DemoCustomer[] }>("GET", "/auth/demo-customers")).customers,
  login: (customer_id: string, otp: string): Promise<LoginResponse> =>
    USE_MOCK ? Promise.resolve(mockLogin()) : call("POST", "/auth/login", { customer_id, otp }),
  agentLogin: (agent_id: string, otp: string): Promise<LoginResponse> => call("POST", "/auth/agent-login", { agent_id, otp }, "agent"),
  resetDemo: (): Promise<void> => call("POST", "/auth/demo/reset"),
  expireSession: (): Promise<void> => call("POST", "/auth/demo/expire"),
  chat: (req: ChatRequest): Promise<ChatResponse> => (USE_MOCK ? Promise.resolve(mockChat(req)) : call("POST", "/chat", req)),
  cases: (): Promise<CasesResponse> => (USE_MOCK ? Promise.resolve({ cases: [] }) : call("GET", "/cases")),
  handoffs: async (): Promise<HandoffSummary[]> =>
    USE_MOCK ? [] : (await call<{ handoffs: HandoffSummary[] }>("GET", "/handoffs", undefined, "agent")).handoffs,
  handoff: (id: string): Promise<HandoffPackage> => call("GET", `/handoffs/${id}`, undefined, "agent"),
  trace: (id: string): Promise<Trace> => call("GET", `/traces/${id}`),
  opsMetrics: (): Promise<OpsMetrics> => call("GET", "/ops/metrics", undefined, "agent"),
  health: (): Promise<HealthResponse> => call("GET", "/health"),
};
