import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, setToken } from "../api/client";
import type { HandoffPackage, HandoffSummary, OpsMetrics } from "../api/types";
import { actionTone, fmtDateTime, fmtMs, fmtUsd, priorityTone, remaining } from "../format";
import { t, tDyn, type UiLang } from "../i18n";

// Identidad SIMULADA de la demo (design.md 7.2; README: AGT-DEMO / 123456).
const AGENT_ID = "AGT-DEMO";
const AGENT_OTP = "123456";
const POLL_MS = 3000;

export type AgentState = {
  status: "connecting" | "ok" | "fail";
  handoffs: HandoffSummary[];
  metrics: OpsMetrics | null;
  fresh: Set<string>;   // handoffs que aparecieron después de la primera carga
};

/** Sesión de agente + sondeo de la cola. `refreshKey` fuerza una lectura inmediata (p. ej. cuando el chat escala). */
export function useAgent(refreshKey: number): AgentState {
  const [state, setState] = useState<AgentState>({ status: "connecting", handoffs: [], metrics: null, fresh: new Set() });
  const logged = useRef(false);
  const known = useRef<Set<string> | null>(null);

  const load = useCallback(async () => {
    try {
      if (!logged.current) {
        const r = await api.agentLogin(AGENT_ID, AGENT_OTP);
        setToken(r.access_token, "agent");
        logged.current = true;
      }
      const [h, m] = await Promise.all([api.handoffs(), api.opsMetrics()]);
      const sorted = [...h].sort((a, b) => b.created_at.localeCompare(a.created_at));
      setState((prev) => {
        const fresh = new Set(prev.fresh);
        if (known.current === null) known.current = new Set(sorted.map((x) => x.handoff_id));
        else for (const x of sorted) if (!known.current.has(x.handoff_id)) { known.current.add(x.handoff_id); fresh.add(x.handoff_id); }
        return { status: "ok", handoffs: sorted, metrics: m, fresh };
      });
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) logged.current = false;
      setState((prev) => ({ ...prev, status: "fail" }));
    }
  }, []);

  useEffect(() => { load(); const id = setInterval(load, POLL_MS); return () => clearInterval(id); }, [load]);
  useEffect(() => { if (refreshKey > 0) load(); }, [refreshKey, load]);
  return state;
}

function useNow(ms: number): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const id = setInterval(() => setNow(Date.now()), ms); return () => clearInterval(id); }, [ms]);
  return now;
}

function Metrics({ m, lang }: { m: OpsMetrics; lang: UiLang }) {
  const rules = Object.entries(m.rules).sort((a, b) => b[1] - a[1]);
  return (
    <section>
      <h3 style={{ marginBottom: 8 }}>{t(lang, "ag.metrics")}</h3>
      <div className="ag-metrics">
        <div className="stat"><b>{m.conversations}</b><span>{t(lang, "ag.m.conversations")}</span></div>
        <div className="stat"><b>{m.cases_created}</b><span>{t(lang, "ag.m.cases")}</span></div>
        <div className="stat"><b>{m.handoff_rate != null ? `${Math.round(m.handoff_rate * 100)} %` : "—"}</b><span>{t(lang, "ag.m.handoffRate")}</span></div>
        <div className="stat"><b>{fmtMs(m.latency_ms.p50)}</b><span>{t(lang, "ag.m.p50")}</span></div>
        <div className="stat"><b>{fmtMs(m.latency_ms.p95)}</b><span>{t(lang, "ag.m.p95")}</span></div>
        <div className="stat"><b>{fmtUsd(m.cost_usd)}</b><span>{t(lang, "ag.m.cost")}</span></div>
      </div>
      {rules.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <p className="muted" style={{ fontSize: 12, marginBottom: 6 }}>{t(lang, "ag.m.rules")}</p>
          <div className="rules-row">
            {rules.map(([r, n]) => <span key={r} className="chip" title={tDyn(lang, `rule.${r}`, "")}>{r} · {n}</span>)}
          </div>
        </div>
      )}
    </section>
  );
}

function Detail({ id, lang, onTrace }: { id: string; lang: UiLang; onTrace: (traceId: string) => void }) {
  const [pkg, setPkg] = useState<HandoffPackage | null>(null);
  const now = useNow(30_000);
  useEffect(() => { setPkg(null); api.handoff(id).then(setPkg).catch(() => setPkg(null)); }, [id]);
  if (!pkg) return <div className="ag-detail"><p className="muted">{t(lang, "au.loading")}</p></div>;
  const sla = pkg.sla_due_at ? remaining(pkg.sla_due_at, now) : null;
  const tone = pkg.policy_decision ? actionTone(pkg.policy_decision.action) : "neutral";
  return (
    <article className="ag-detail" aria-label={pkg.handoff_id}>
      <header>
        <span className={`chip ${priorityTone(pkg.priority) === "neutral" ? "" : priorityTone(pkg.priority)}`}>{tDyn(lang, `prio.${pkg.priority}`)}</span>
        <span className="chip accent">{tDyn(lang, `queue.${pkg.suggested_queue}`)}</span>
        <span className="chip">{t(lang, "ag.agentLang")} {pkg.suggested_agent_language.toUpperCase()}</span>
        {sla && <span className={`chip ${sla.overdue ? "bad" : "ok"}`}>{t(lang, "ag.sla")} {sla.overdue ? `${t(lang, "ag.overdue")} ${sla.text}` : sla.text}</span>}
      </header>

      <section>
        <h3>{t(lang, "ag.original")}</h3>
        <p className="quote">{pkg.original_request}</p>
      </section>
      <section>
        <h3>{t(lang, "ag.summary")}</h3>
        <p>{pkg.summary}</p>
      </section>

      <section>
        <h3>{t(lang, "ag.facts")}</h3>
        <dl className="facts">
          <dt>{t(lang, "ag.customer")}</dt><dd>{pkg.customer.customer_id} · {pkg.customer.segment} · {pkg.customer.country}</dd>
          {pkg.verified_facts.map((f, i) => (
            <FactRow key={i} lang={lang} fact={f.fact} value={f.value} />
          ))}
        </dl>
      </section>

      {pkg.policy_decision && (
        <section>
          <h3>{t(lang, "ag.decision")}</h3>
          <div className={`col policy ${tone}`}>
            <p><b>{pkg.policy_decision.rule_id}</b> · {tDyn(lang, `action.${pkg.policy_decision.action}`)}</p>
            <p className="muted" style={{ color: "inherit", fontSize: 13 }}>{pkg.policy_decision.reason}</p>
            <p className="mono-small">policy {pkg.policy_decision.policy_version}</p>
          </div>
        </section>
      )}

      <section>
        <h3>{t(lang, "ag.taken")}</h3>
        {pkg.actions_taken.length === 0 ? <p className="muted">—</p> : (
          <ul className="list-plain">
            {pkg.actions_taken.map((a, i) => (
              <li key={i}>
                <span className={`chip ${a.status === "verified" ? "ok" : a.status === "failed" ? "bad" : "warn"}`}>{tDyn(lang, `ag.status.${a.status}`)}</span>{" "}
                {tDyn(lang, `ag.action.${a.action}`)}
              </li>
            ))}
          </ul>
        )}
        {pkg.actions_declined.length > 0 && (
          <>
            <h3 style={{ marginTop: 8 }}>{t(lang, "ag.declined")}</h3>
            <ul className="list-plain">{pkg.actions_declined.map((a, i) => <li key={i}><span className="chip warn">{tDyn(lang, `ag.action.${a}`)}</span></li>)}</ul>
          </>
        )}
      </section>

      <section>
        <h3>{t(lang, "ag.open")}</h3>
        {pkg.open_questions.length === 0
          ? <p className="muted">{t(lang, "ag.noneOpen")}</p>
          : <ul className="list-plain">{pkg.open_questions.map((q, i) => <li key={i}>{q}</li>)}</ul>}
      </section>

      <footer style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <span className="mono-small">{pkg.handoff_id} · {tDyn(lang, `ag.reason.${pkg.handoff_reason}`)} · {fmtDateTime(pkg.created_at, lang)}</span>
        <button className="btn small" onClick={() => onTrace(pkg.trace_id)}>{t(lang, "ag.trace")}</button>
      </footer>
    </article>
  );
}

function FactRow({ lang, fact, value }: { lang: UiLang; fact: string; value: string | number }) {
  return (<><dt>{tDyn(lang, `ag.fact.${fact}`, fact)}</dt><dd>{value === "nulo" ? t(lang, "ag.null") : String(value)}</dd></>);
}

export function AgentConsole({ agent, lang, selected, setSelected, onTrace }: {
  agent: AgentState; lang: UiLang; selected: string | null; setSelected: (id: string) => void; onTrace: (traceId: string) => void;
}) {
  const { status, handoffs, metrics, fresh } = agent;
  const current = selected ?? handoffs[0]?.handoff_id ?? null;
  return (
    <div className="panel">
      {status !== "ok" && handoffs.length === 0 && (
        <p className="muted">{t(lang, status === "fail" ? "ag.connectFail" : "ag.connecting")}</p>
      )}
      {metrics && <Metrics m={metrics} lang={lang} />}
      <section>
        <h3 style={{ marginBottom: 8 }}>{t(lang, "ag.queue")}</h3>
        {status === "ok" && handoffs.length === 0 && <p className="muted">{t(lang, "ag.empty")}</p>}
        <div className="ag-queue">
          {handoffs.map((h) => {
            const tone = priorityTone(h.priority);
            return (
              <button key={h.handoff_id} className={`ag-item${fresh.has(h.handoff_id) ? " fresh" : ""}`}
                aria-current={current === h.handoff_id} onClick={() => setSelected(h.handoff_id)}>
                <span className={`dot ${tone === "neutral" ? "" : tone}`} aria-hidden="true" />
                <span className="t1">{h.case_id ?? t(lang, "ag.noSla")} · {tDyn(lang, `queue.${h.suggested_queue}`)}</span>
                <span style={{ display: "flex", gap: 6 }}>
                  {fresh.has(h.handoff_id) && <span className="chip warn">{t(lang, "ag.new")}</span>}
                  <span className="chip">{h.language.toUpperCase()}</span>
                </span>
                <span className="t2">{tDyn(lang, `ag.reason.${h.handoff_reason}`, h.handoff_reason)} · {tDyn(lang, `prio.${h.priority}`)} · {fmtDateTime(h.created_at, lang)}</span>
              </button>
            );
          })}
        </div>
      </section>
      {current ? <Detail id={current} lang={lang} onTrace={onTrace} /> : status === "ok" && handoffs.length > 0 ? <p className="panel-empty">{t(lang, "ag.pick")}</p> : null}
    </div>
  );
}
