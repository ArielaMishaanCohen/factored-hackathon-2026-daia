// Espejo de backend/app/schemas.py (docs/design.md, secciones 4 a 6).
// Si cambia un contrato, se actualizan los tres en el mismo PR.

export type Language = "es" | "pt";
export type Currency = "ARS" | "COP" | "USD";
export type Intent =
  | "cargo_no_reconocido"
  | "cobro_incorrecto"
  | "tarjeta_comprometida"
  | "estado_disputa"
  | "fuera_de_alcance";
export type DisputeType = "cargo_no_reconocido" | "cobro_incorrecto" | "fraude";
export type Priority = "critical" | "high" | "medium" | "low";
export type Queue = "fraude" | "disputas" | "general";
export type RuleId = `R${0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12}`;
export type PolicyAction = "REAUTH" | "NOT_FOUND" | "INFORM" | "AUTO_REGISTER" | "FRAUD" | "ESCALATE";
export type ConversationState =
  | "INICIO" | "PEDIR_REAUTENTICACION" | "ENTENDER" | "ACLARAR" | "ABSTENERSE" | "INFORMAR_ESTADO"
  | "IDENTIFICAR_TRANSACCION" | "EVALUAR" | "CONFIRMAR_ACCION" | "EJECUTAR" | "VERIFICAR" | "CERRAR" | "HANDOFF";

export interface DemoCustomer {
  customer_id: string;
  display_name: string;
  segment: string;
  country: string;
  suggested_language: Language;
  scenario: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: "bearer";
  expires_at: string;
  customer: { customer_id: string; segment: string; country: string; language: Language } | null;
}

export interface TransactionView {
  transaction_id: string;
  business_date: string;
  amount: number;
  currency: Currency;
  merchant_name: string | null;
  transaction_type: string;
  channel: string;
  status: "Approved" | "Declined" | "Pending" | "Reversed";
  product_id: string;
  card_mask: string | null;
}

export interface DisputeCase {
  case_id: string;
  customer_id: string;
  transaction_id: string;
  product_id: string;
  dispute_type: DisputeType;
  category: string;
  subcategory: string;
  priority: Priority;
  status: "Open" | "In Process" | "Escalated" | "Resolved" | "Closed" | "Rejected";
  rule_id: RuleId;
  policy_version: string;
  channel: "chat";
  language: Language;
  created_at: string;
  sla_due_at: string;
}

export interface PendingActionView {
  pending_action_id: string;
  action: "create_dispute_case" | "block_card";
  summary: string;
  expires_at: string;
}

export type UIAction =
  | { type: "select_transaction"; transaction_id: string }
  | { type: "confirm"; pending_action_id: string }
  | { type: "cancel"; pending_action_id: string };

export interface ChatRequest {
  conversation_id: string | null;
  message?: string;
  ui_action?: UIAction;
}

export interface ChatUI {
  type: "transaction_options" | "confirmation" | "case_created" | "handoff" | "reauth";
  options?: TransactionView[] | null;
  pending_action?: PendingActionView | null;
  case?: DisputeCase | null;
  handoff_id?: string | null;
  queue?: Queue | null;
}

export interface ChatResponse {
  conversation_id: string;
  turn_id: number;
  trace_id: string;
  state: ConversationState;
  language: Language;
  messages: { role: "assistant"; text: string; source: "llm" | "template" }[];
  ui: ChatUI | null;
  case: DisputeCase | null;
  handoff_id: string | null;
  audit: {
    intent: Intent | null;
    intent_confidence: number | null;
    rule_id: RuleId | null;
    tools: string[];
    latency_ms: number;
    fallback_used: boolean;
  };
}

export interface Decision {
  rule_id: RuleId;
  action: PolicyAction;
  reason: string;
  priority: Priority | null;
  queue: Queue | null;
  policy_version: string;
}

export interface CasesResponse {
  cases: DisputeCase[];
}

export interface HandoffSummary {
  handoff_id: string;
  case_id: string | null;
  priority: Priority;
  suggested_queue: Queue;
  language: Language;
  created_at: string;
  handoff_reason: string;
}

export interface HandoffPackage {
  handoff_id: string;
  case_id: string | null;
  created_at: string;
  handoff_reason: "POLICY_ESCALATION" | "CLARIFICATION_EXHAUSTED" | "NO_TRANSACTION_FOUND" | "TOOL_FAILURE" | "CUSTOMER_REQUEST";
  priority: Priority;
  sla_due_at: string | null;
  language: Language;
  customer: { customer_id: string; segment: string; country: string };
  original_request: string;
  summary: string;
  verified_facts: { fact: string; value: string | number; source: string }[];
  policy_decision: Decision | null;
  actions_taken: { action: "create_dispute_case" | "block_card"; status: "verified" | "failed" | "not_attempted"; at: string | null }[];
  actions_declined: string[];
  open_questions: string[];
  suggested_queue: Queue;
  suggested_agent_language: Language;
  conversation_id: string;
  trace_id: string;
}

export interface Span {
  name: string;
  latency_ms: number;
  output?: Record<string, unknown> | null;
  model?: string | null;
  tokens_in?: number | null;
  tokens_out?: number | null;
  cost_usd?: number | null;
  error?: string | null;
}

export interface ActionRecord {
  action: "create_dispute_case" | "block_card";
  status: "verified" | "failed" | "not_attempted";
  at: string | null;
}

export interface TraceTurn {
  turn_id: number;
  state_from: ConversationState;
  state_to: ConversationState;
  spans: Span[];
  // Resumen del turno (backend/app/schemas.py, Fase 7). Todos opcionales en el contrato.
  started_at?: string | null;
  latency_ms?: number | null;
  input_kind?: "message" | "ui_action" | null;
  language?: Language | null;
  intent?: Intent | null;
  intent_confidence?: number | null;
  rule_id?: RuleId | null;
  transaction_id?: string | null;
  input_action?: "select_transaction" | "confirm" | "cancel" | null;
  confirmation?: "yes" | "no" | null;
  assistant_messages?: string[];
  ui_type?: string | null;
  ui_transaction_ids?: string[];
  pending_action?: "create_dispute_case" | "block_card" | null;
  actions?: ActionRecord[];
  case_id?: string | null;
  handoff_id?: string | null;
  tokens_in?: number;
  tokens_out?: number;
  cost_usd?: number;
  versions?: Record<string, string> | null;
}

export interface Trace {
  trace_id: string;
  conversation_id: string;
  customer_id: string;
  turns: TraceTurn[];
}

/** GET /api/ops/metrics (solo agente). docs/operations.md §5. */
export interface OpsMetrics {
  conversations: number;
  turns: number;
  latency_ms: { p50: number | null; p95: number | null; max: number | null };
  rules: Record<string, number>;
  intents: Record<string, number>;
  languages: Record<string, number>;
  cases_created: number;
  actions: Record<string, number>;
  handoffs: number;
  handoff_rate: number | null;
  handoffs_by_reason: Record<string, number>;
  tool_errors: Record<string, number>;
  cost_usd: number;
}

export interface HealthResponse {
  status: "ok";
  policy_version: string;
  intent_model: string;
  llm_model: string;
  data_manifest: string | null;
  nlu_mode: "full" | "keywords";
}

export interface ApiErrorBody {
  error: {
    code: "UNAUTHENTICATED" | "SESSION_EXPIRED" | "FORBIDDEN" | "NOT_FOUND" | "VALIDATION_ERROR" | "INTERNAL";
    message: string;
  };
}
