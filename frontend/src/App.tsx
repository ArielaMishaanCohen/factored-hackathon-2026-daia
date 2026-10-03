// Esqueleto de Fase 1: login de demo + chat mínimo contra el contrato.
// Fase 5 (D): diseño real, consola del agente, panel de auditoría, i18n ES/PT.
import { useEffect, useState } from "react";
import { api, ApiError, setToken } from "./api/client";
import type { ChatResponse, ChatUI, DemoCustomer, UIAction } from "./api/types";

type Line = { from: "user" | "bot"; text: string };

export default function App() {
  const [customers, setCustomers] = useState<DemoCustomer[]>([]);
  const [loggedIn, setLoggedIn] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [lines, setLines] = useState<Line[]>([]);
  const [ui, setUi] = useState<ChatUI | null>(null);
  const [last, setLast] = useState<ChatResponse | null>(null);
  const [input, setInput] = useState("");

  useEffect(() => { api.demoCustomers().then(setCustomers).catch(() => setCustomers([])); }, []);

  async function login(id: string) {
    const r = await api.login(id, "123456");
    setToken(r.access_token);
    setLoggedIn(true);
    setLines([]); setUi(null); setConversationId(null);
  }

  async function send(message?: string, ui_action?: UIAction) {
    if (message) setLines((l) => [...l, { from: "user", text: message }]);
    try {
      const r = await api.chat({ conversation_id: conversationId, message, ui_action });
      setConversationId(r.conversation_id);
      setLines((l) => [...l, ...r.messages.map((m) => ({ from: "bot" as const, text: m.text }))]);
      setUi(r.ui);
      setLast(r);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) { setLoggedIn(false); setToken(null); }
      else throw e;
    }
  }

  if (!loggedIn) {
    return (
      <main style={{ maxWidth: 560, margin: "40px auto", fontFamily: "system-ui", padding: 16 }}>
        <h1>LATAM Bank · Disputas</h1>
        <p>Elige un cliente de demo (OTP de prueba: 123456).</p>
        {customers.map((c) => (
          <button key={c.customer_id} style={{ display: "block", margin: "8px 0" }} onClick={() => login(c.customer_id)}>
            {c.display_name} · {c.segment} · {c.country} · {c.scenario}
          </button>
        ))}
      </main>
    );
  }

  return (
    <main style={{ maxWidth: 560, margin: "40px auto", fontFamily: "system-ui", padding: 16 }}>
      <header style={{ display: "flex", justifyContent: "space-between" }}>
        <strong>Chat</strong>
        <button onClick={() => api.expireSession()}>Expirar sesión</button>
      </header>
      {lines.map((l, i) => (
        <p key={i} style={{ textAlign: l.from === "user" ? "right" : "left" }}>{l.text}</p>
      ))}
      {ui?.type === "transaction_options" && ui.options?.map((t) => (
        <button key={t.transaction_id} style={{ display: "block", margin: "4px 0" }}
          onClick={() => send(undefined, { type: "select_transaction", transaction_id: t.transaction_id })}>
          {t.business_date} · {t.merchant_name ?? t.transaction_type} · {t.amount.toLocaleString()} {t.currency}
        </button>
      ))}
      {ui?.type === "confirmation" && ui.pending_action && (
        <div>
          <p><em>{ui.pending_action.summary}</em></p>
          <button onClick={() => send(undefined, { type: "confirm", pending_action_id: ui.pending_action!.pending_action_id })}>Confirmar</button>
          <button onClick={() => send(undefined, { type: "cancel", pending_action_id: ui.pending_action!.pending_action_id })}>Cancelar</button>
        </div>
      )}
      <form onSubmit={(e) => { e.preventDefault(); if (input.trim()) { send(input.trim()); setInput(""); } }}>
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Escribe tu mensaje" style={{ width: "80%" }} />
        <button type="submit">Enviar</button>
      </form>
      {last && (
        <pre style={{ fontSize: 12, background: "#f4f4f4", padding: 8 }}>
          {JSON.stringify({ state: last.state, ...last.audit }, null, 2)}
        </pre>
      )}
    </main>
  );
}
