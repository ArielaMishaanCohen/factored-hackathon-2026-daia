// Mock del contrato (design.md 6.3) para trabajar sin backend: VITE_USE_MOCK=true.
// Responde con la forma exacta de ChatResponse; el guion es fijo.
import type { ChatRequest, ChatResponse, DemoCustomer, LoginResponse } from "./types";

const now = () => new Date().toISOString();
let turn = 0;

export const mockCustomers: DemoCustomer[] = [
  { customer_id: "CUS-DEMO-01", display_name: "Cliente demo 1", segment: "Basic", country: "México", suggested_language: "es", scenario: "Resolución normal" },
];

export function mockLogin(): LoginResponse {
  return {
    access_token: "mock", token_type: "bearer", expires_at: now(),
    customer: { customer_id: "CUS-DEMO-01", segment: "Basic", country: "México", language: "es" },
  };
}

const tx = {
  transaction_id: "TX-DEMO-0001", business_date: "2026-06-10", amount: 350, currency: "USD" as const,
  merchant_name: "OXXO", transaction_type: "Purchase", channel: "POS", status: "Approved" as const,
  product_id: "PRD-DEMO-01", card_mask: "•••• 4821",
};

export function mockChat(req: ChatRequest): ChatResponse {
  turn += 1;
  const base = {
    conversation_id: req.conversation_id ?? "CONV-mock", turn_id: turn, trace_id: "TR-mock", language: "es" as const,
    case: null, handoff_id: null,
    audit: { intent: "cargo_no_reconocido" as const, intent_confidence: 0.91, rule_id: "R12" as const, tools: ["search_transactions"], latency_ms: 120, fallback_used: false },
  };
  if (req.ui_action?.type === "confirm") {
    const c = {
      case_id: "DSP-000123", customer_id: "CUS-DEMO-01", transaction_id: tx.transaction_id, product_id: tx.product_id,
      dispute_type: "cargo_no_reconocido" as const, category: "Transactions", subcategory: "Cargo no reconocido",
      priority: "medium" as const, status: "Open" as const, rule_id: "R12" as const, policy_version: "1.0.0",
      channel: "chat" as const, language: "es" as const, created_at: now(), sla_due_at: now(),
    };
    return { ...base, state: "CERRAR", case: c, ui: { type: "case_created", case: c },
      messages: [{ role: "assistant", text: "Registré tu disputa con el número DSP-000123.", source: "template" }] };
  }
  if (req.ui_action?.type === "cancel") {
    return { ...base, state: "CERRAR", ui: null, messages: [{ role: "assistant", text: "Entendido, no hice ningún cambio.", source: "template" }] };
  }
  if (req.ui_action?.type === "select_transaction" || turn > 1) {
    return { ...base, state: "CONFIRMAR_ACCION",
      messages: [{ role: "assistant", text: "Encontré el cargo. ¿Quieres que registre la disputa?", source: "llm" }],
      ui: { type: "confirmation", pending_action: { pending_action_id: "PA-mock", action: "create_dispute_case", summary: "Registrar disputa por 350,00 USD en OXXO", expires_at: now() } } };
  }
  return { ...base, state: "IDENTIFICAR_TRANSACCION",
    messages: [{ role: "assistant", text: "Encontré varios cargos posibles. ¿Cuál es?", source: "template" }],
    ui: { type: "transaction_options", options: [tx, { ...tx, transaction_id: "TX-DEMO-0009", amount: 352, business_date: "2026-06-03" }] } };
}
