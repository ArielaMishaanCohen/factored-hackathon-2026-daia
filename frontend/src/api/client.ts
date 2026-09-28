// Cliente del contrato de la API (design.md, sección 6).
import { mockChat, mockCustomers, mockLogin } from "./mock";
import type { ApiErrorBody, CasesResponse, ChatRequest, ChatResponse, DemoCustomer, HandoffPackage, HandoffSummary, LoginResponse, Trace } from "./types";

const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";

export class ApiError extends Error {
  constructor(public status: number, public code: ApiErrorBody["error"]["code"], message: string) {
    super(message);
  }
}

let token: string | null = null;
export const setToken = (t: string | null) => { token = t; };

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.status === 204) return undefined as T;
  const data = await res.json();
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
  agentLogin: (agent_id: string, otp: string): Promise<LoginResponse> => call("POST", "/auth/agent-login", { agent_id, otp }),
  expireSession: (): Promise<void> => call("POST", "/auth/demo/expire"),
  chat: (req: ChatRequest): Promise<ChatResponse> => (USE_MOCK ? Promise.resolve(mockChat(req)) : call("POST", "/chat", req)),
  cases: (): Promise<CasesResponse> => call("GET", "/cases"),
  handoffs: async (): Promise<HandoffSummary[]> => (await call<{ handoffs: HandoffSummary[] }>("GET", "/handoffs")).handoffs,
  handoff: (id: string): Promise<HandoffPackage> => call("GET", `/handoffs/${id}`),
  trace: (id: string): Promise<Trace> => call("GET", `/traces/${id}`),
};
