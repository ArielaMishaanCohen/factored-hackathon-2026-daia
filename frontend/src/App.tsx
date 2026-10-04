// Vista doble (Fase 5, rol D): barra de escenarios · chat del cliente · inspector (auditoría | consola del agente).
// Todo el estado de la conversación vive aquí para sobrevivir a una sesión expirada (design.md 7.4):
// al volver a entrar el mismo cliente, la conversación continúa con el mismo conversation_id.
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, setToken } from "./api/client";
import type { DemoCustomer, Language, LoginResponse, TransactionView, UIAction } from "./api/types";
import { AgentConsole, useAgent } from "./components/Agent";
import { AuditPanel } from "./components/Audit";
import { Chat, type Item, type TurnRec } from "./components/Chat";
import { Login } from "./components/Login";
import { ScenarioRail, SCENARIOS, type Scenario } from "./components/Scenarios";
import { fmtAmount } from "./format";
import { t, type UiLang } from "./i18n";

type Session = { customerId: string; displayName: string; segment: string; country: string };
const TEST_OTP = "123456"; // OTP de prueba documentado (design.md 7.1)

export default function App() {
  const [lang, setLang] = useState<Language>("es");          // idioma del chat = el del cliente
  const [uiLang, setUiLang] = useState<UiLang>("en");          // idioma del panel (escenarios, auditoría, agente)
  const [customers, setCustomers] = useState<DemoCustomer[]>([]);
  const [loadState, setLoadState] = useState<"loading" | "ok" | "fail">("loading");
  const [session, setSession] = useState<Session | null>(null);
  const [expiredFor, setExpiredFor] = useState<string | null>(null);
  const [revoked, setRevoked] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);

  const [items, setItems] = useState<Item[]>([]);
  const [turns, setTurns] = useState<TurnRec[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [lastTyped, setLastTyped] = useState("");
  const [selTurn, setSelTurn] = useState<number | null>(null);
  const [caseRefresh, setCaseRefresh] = useState(0);
  const [staleBefore, setStaleBefore] = useState(0);   // confirmaciones de turnos anteriores a este quedan anuladas (design.md 7.4)

  const [inspector, setInspector] = useState<"audit" | "agent">("audit");
  const [view, setView] = useState<"chat" | "inspector">("chat");
  const [agentRefresh, setAgentRefresh] = useState(0);
  const [agentSel, setAgentSel] = useState<string | null>(null);
  const [seenCount, setSeenCount] = useState<number | null>(null);   // null = aún no cargó la cola
  const [missing, setMissing] = useState(false);

  // Refs espejo: evitan cierres con valores viejos dentro de los handlers async.
  const convRef = useRef<string | null>(null);
  const convOwner = useRef<string | null>(null);
  const busyRef = useRef(false);
  const sessionRef = useRef<Session | null>(null);
  const turnsCount = useRef(0);
  const nextId = useRef(1);
  const pendingText = useRef<string | null>(null);

  const agent = useAgent(agentRefresh);

  useEffect(() => {
    api.demoCustomers().then((c) => { setCustomers(c); setLoadState("ok"); }).catch(() => setLoadState("fail"));
  }, []);
  useEffect(() => { document.documentElement.lang = lang; }, [lang]);
  useEffect(() => {
    // La cola que ya existía al abrir la app no cuenta como "nueva"; solo lo que llega después.
    if (agent.status === "ok" && (seenCount === null || inspector === "agent")) setSeenCount(agent.handoffs.length);
  }, [agent.status, agent.handoffs.length, inspector, seenCount]);

  const resetConversation = useCallback(() => {
    convRef.current = null; convOwner.current = null; turnsCount.current = 0;
    setItems([]); setTurns([]); setSelTurn(null); setStaleBefore(0); setLastTyped(""); setInput(""); setRevoked(false);
  }, []);

  const doLogin = useCallback(async (c: DemoCustomer, otp: string): Promise<boolean> => {
    setLoginError(null);
    let r: LoginResponse;
    try {
      r = await api.login(c.customer_id, otp);
    } catch (e) {
      setLoginError(e instanceof ApiError && e.status === 401 ? t(lang, "login.badOtp") : (e as Error).message);
      return false;
    }
    setToken(r.access_token, "customer");
    if (convOwner.current !== c.customer_id) resetConversation();   // otro cliente: conversación nueva
    const s: Session = { customerId: c.customer_id, displayName: c.display_name, segment: c.segment, country: c.country };
    sessionRef.current = s;
    setSession(s);
    setExpiredFor(null);
    setRevoked(false);
    setLang(r.customer?.language ?? c.suggested_language);
    if (pendingText.current) { setInput(pendingText.current); pendingText.current = null; }
    return true;
  }, [lang, resetConversation]);

  const send = useCallback(async (message?: string, ui_action?: UIAction, echo?: string) => {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(true);
    const userLine = echo ?? message;
    const userItemId = nextId.current++;
    if (userLine) setItems((l) => [...l, { id: userItemId, from: "user", text: userLine }]);
    if (message) setLastTyped(message);
    try {
      const r = await api.chat({ conversation_id: convRef.current, message, ui_action });
      convRef.current = r.conversation_id;
      convOwner.current = sessionRef.current?.customerId ?? convOwner.current;
      const turnIdx = turnsCount.current++;
      setTurns((ts) => [...ts, { res: r, userText: message ?? null }]);
      setSelTurn(null);
      setLang(r.language);
      setItems((l) => [
        ...l,
        ...r.messages.map((m, i) => ({
          id: nextId.current++, from: "bot" as const, text: m.text, source: m.source,
          turn: turnIdx, lastOfTurn: i === r.messages.length - 1,
        })),
      ]);
      if (r.handoff_id || r.case) setAgentRefresh((n) => n + 1);   // lo que escala aparece en la consola
      if (r.case) setCaseRefresh((n) => n + 1);
    } catch (e) {
      if (e instanceof ApiError && (e.code === "SESSION_EXPIRED" || e.code === "UNAUTHENTICATED")) {
        // R0: volver al login sin perder la conversación; el mensaje no enviado queda para reintentarlo.
        pendingText.current = message ?? null;
        setStaleBefore(turnsCount.current);
        setItems((l) => l.filter((x) => x.id !== userItemId));
        setExpiredFor(sessionRef.current?.customerId ?? null);
        setSession(null); sessionRef.current = null; setToken(null, "customer");
      } else {
        setItems((l) => [...l, { id: nextId.current++, from: "err", text: `${t(lang, "chat.error")} ${(e as Error).message}`, retry: () => send(message, ui_action, echo) }]);
      }
    } finally {
      busyRef.current = false; setBusy(false);
    }
  }, [lang]);

  const runScenario = useCallback(async (s: Scenario) => {
    const c = s.pick(customers);
    if (!c) { setMissing(true); return; }
    setMissing(false);
    if (busyRef.current) return;
    resetConversation();
    setExpiredFor(null);
    setView("chat");
    if (await doLogin(c, TEST_OTP)) await send(s.message);
  }, [customers, doLogin, resetConversation, send]);

  const pick = (tx: TransactionView) =>
    send(undefined, { type: "select_transaction", transaction_id: tx.transaction_id },
      `${tx.merchant_name ?? t(lang, "tx.noMerchant")} · ${fmtAmount(tx.amount, lang)} ${tx.currency}`);

  const leave = () => {
    setToken(null, "customer"); sessionRef.current = null; setSession(null); resetConversation(); setExpiredFor(null);
  };

  const expire = async () => {
    try { await api.expireSession(); setRevoked(true); } catch { /* si ya expiró, el próximo envío lo muestra */ }
  };

  const shownTurn = turns.length ? turns[selTurn ?? turns.length - 1] : null;
  const unseen = seenCount === null ? 0 : Math.max(0, agent.handoffs.length - seenCount);

  return (
    <div className="app" data-view={view}>
      <aside className="rail" aria-label={t(uiLang, "sc.title")}>
        <ScenarioRail lang={uiLang} customers={customers} busy={busy} missing={missing} onRun={runScenario} />
      </aside>

      <main className="center">
        {session ? (
          <>
            <header className="topbar">
              <div className="who"><b>{session.displayName}</b><span>{session.segment} · {session.country}</span></div>
              <span className="chip accent" title={t(lang, "chat.detected")}>{lang.toUpperCase()}</span>
              <span className="sp" />
              <button className="btn small mobile-nav" onClick={() => setView("inspector")}>{t(uiLang, "ins.audit")}</button>
              <button className="btn small" onClick={expire} disabled={revoked}>{t(lang, "chat.endSession")}</button>
              <button className="btn small ghost" onClick={leave}>{t(lang, "chat.leave")}</button>
            </header>
            {revoked && <div className="notice warn" role="status" style={{ margin: "12px 20px 0" }}>{t(lang, "chat.revoked")}</div>}
            <Chat lang={lang} items={items} turns={turns} busy={busy} input={input} setInput={setInput}
              onSend={(text) => { setInput(""); send(text); }} onPick={pick}
              onConfirm={(id) => send(undefined, { type: "confirm", pending_action_id: id }, t(lang, "chat.confirm"))}
              onCancel={(id) => send(undefined, { type: "cancel", pending_action_id: id }, t(lang, "chat.cancel"))}
              selTurn={selTurn} onSelectTurn={(i) => { setSelTurn(i); setInspector("audit"); }}
              lastTyped={lastTyped} caseRefresh={caseRefresh} staleBefore={staleBefore} />
          </>
        ) : (
          <Login lang={lang} setLang={setLang} customers={customers} loadState={loadState} expiredFor={expiredFor}
            error={loginError} busy={busy} onLogin={(c, otp) => { doLogin(c, otp); }} />
        )}
      </main>

      <aside className="inspector">
        <div className="tabs" role="tablist">
          <button className="tab mobile-nav" onClick={() => setView("chat")}>← {t(uiLang, "nav.chat")}</button>
          <button className="tab" role="tab" aria-selected={inspector === "audit"} onClick={() => setInspector("audit")}>{t(uiLang, "ins.audit")}</button>
          <button className="tab" role="tab" aria-selected={inspector === "agent"} onClick={() => setInspector("agent")}>
            {t(uiLang, "ins.agent")}{unseen > 0 && inspector !== "agent" && <span className="badge">{unseen}</span>}
          </button>
          <div className="seg ui-lang" role="group" aria-label="Panel language">
            {(["en", "es", "pt"] as const).map((l) => (
              <button key={l} type="button" aria-pressed={uiLang === l} onClick={() => setUiLang(l)}>{l.toUpperCase()}</button>
            ))}
          </div>
        </div>
        {inspector === "audit"
          ? <AuditPanel rec={shownTurn} lang={uiLang} />
          : <AgentConsole agent={agent} lang={uiLang} selected={agentSel} setSelected={setAgentSel}
              onTrace={() => { /* la traza completa del agente se ve en /api/traces/{id}; aquí basta el resumen */ }} />}
      </aside>
    </div>
  );
}

export { SCENARIOS };
