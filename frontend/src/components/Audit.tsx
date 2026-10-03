import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Language, Span, Trace, TraceTurn } from "../api/types";
import { actionTone, fmtMs, fmtUsd } from "../format";
import { t, tDyn } from "../i18n";
import type { TurnRec } from "./Chat";

/** La IA propone, la política decide: lo que entendió el NLU frente a lo que la capa determinista permitió. */
export function AuditPanel({ rec, lang }: { rec: TurnRec | null; lang: Language }) {
  const [trace, setTrace] = useState<Trace | null>(null);
  const [failed, setFailed] = useState(false);
  const traceId = rec?.res.trace_id;
  const turnId = rec?.res.turn_id;

  useEffect(() => {
    if (!traceId) { setTrace(null); return; }
    let alive = true;
    setFailed(false);
    api.trace(traceId).then((tr) => { if (alive) setTrace(tr); }).catch(() => { if (alive) setFailed(true); });
    return () => { alive = false; };
  }, [traceId, turnId]);

  if (!rec) return <div className="panel"><p className="panel-empty">{t(lang, "au.empty")}</p></div>;

  const { res } = rec;
  const turn: TraceTurn | undefined = trace?.turns.find((x) => x.turn_id === res.turn_id);
  const spans: Span[] = turn?.spans ?? [];
  const nlu = spans.find((s) => s.name === "nlu.understand");
  const policy = spans.find((s) => s.name === "policy.evaluate");
  const nluOut = (nlu?.output ?? {}) as { intent?: string; confidence?: number; extractor?: string; suspected_injection?: boolean };
  const polOut = (policy?.output ?? {}) as { rule_id?: string; action?: string; priority?: string; queue?: string };

  const intent = res.audit.intent ?? nluOut.intent ?? null;
  const confidence = res.audit.intent_confidence ?? nluOut.confidence ?? null;
  const ruleId = polOut.rule_id ?? res.audit.rule_id;
  const tone = actionTone(polOut.action);
  const totalMs = spans.reduce((a, s) => a + s.latency_ms, 0) || 1;
  const injection = nluOut.suspected_injection === true;
  const fellBack = res.messages.some((m) => m.source === "template");

  return (
    <div className="panel">
      <div>
        <p className="motto">{t(lang, "au.motto")}</p>
        <p className="motto-sub">{t(lang, "au.turn")} {res.turn_id} · {t(lang, "au.state")} {turn ? `${turn.state_from} → ${turn.state_to}` : res.state}</p>
      </div>

      {injection && <div className="alert" role="status">{t(lang, "au.injection")}</div>}

      <div className="split">
        <section className="col ai" aria-label={t(lang, "au.ai")}>
          <h3>{t(lang, "au.ai")}</h3>
          {intent ? (
            <dl className="kvs">
              <div><dt>{t(lang, "au.intent")}</dt><dd>{tDyn(lang, `intent.${intent}`, intent)}</dd></div>
              <div>
                <dt>{t(lang, "au.confidence")}</dt>
                <dd>{confidence != null ? `${Math.round(confidence * 100)} %` : "—"}</dd>
                {confidence != null && <div className="bar" aria-hidden="true"><i style={{ width: `${Math.round(confidence * 100)}%` }} /></div>}
              </div>
              {nluOut.extractor && <div><dt>{t(lang, "au.extractor")}</dt><dd>{t(lang, nluOut.extractor === "llm" ? "au.extractor.llm" : "au.extractor.rules")}</dd></div>}
              <div><dt>{t(lang, "au.language")}</dt><dd>{res.language.toUpperCase()}</dd></div>
            </dl>
          ) : <p className="muted">{t(lang, "au.noNlu")}</p>}
        </section>

        <section className={`col policy ${ruleId ? tone : ""}`} aria-label={t(lang, "au.policy")}>
          <h3>{t(lang, "au.policy")}</h3>
          {ruleId ? (
            <dl className="kvs">
              <div>
                <dt>{t(lang, "au.rule")}</dt>
                <dd className="rule-tag"><b>{ruleId}</b></dd>
                <dd style={{ fontWeight: 500 }}>{tDyn(lang, `rule.${ruleId}`, "")}</dd>
              </div>
              {polOut.action && <div><dt>{t(lang, "au.action")}</dt><dd>{tDyn(lang, `action.${polOut.action}`, polOut.action)}</dd></div>}
              {polOut.priority && <div><dt>{t(lang, "au.priority")}</dt><dd>{tDyn(lang, `prio.${polOut.priority}`, polOut.priority)}</dd></div>}
              {polOut.queue && <div><dt>{t(lang, "au.queue")}</dt><dd>{tDyn(lang, `queue.${polOut.queue}`, polOut.queue)}</dd></div>}
            </dl>
          ) : <p className="muted">{t(lang, "au.noPolicy")}</p>}
        </section>
      </div>

      <section>
        <h3 style={{ marginBottom: 8 }}>{t(lang, "au.actions")}</h3>
        {turn?.actions && turn.actions.length > 0 ? (
          <ul className="list-plain">
            {turn.actions.map((a, i) => (
              <li key={i}>
                <span className={`chip ${a.status === "verified" ? "ok" : a.status === "failed" ? "bad" : "warn"}`}>{tDyn(lang, `ag.status.${a.status}`)}</span>{" "}
                {tDyn(lang, `ag.action.${a.action}`)}
              </li>
            ))}
          </ul>
        ) : <p className="muted">{trace || failed ? t(lang, "au.noActions") : t(lang, "au.loading")}</p>}
      </section>

      <section>
        <h3 style={{ marginBottom: 8 }}>{t(lang, "au.steps")}</h3>
        {failed && <p className="muted">{t(lang, "au.traceFail")}</p>}
        {!trace && !failed && <p className="muted">{t(lang, "au.loading")}</p>}
        <ul className="spans">
          {spans.map((s, i) => {
            const cls = s.error ? "err" : s.name.startsWith("llm.") || s.name === "nlu.understand" ? "llm" : s.name.startsWith("policy.") ? "policy" : "";
            const attempts = (s.output as { attempts?: number } | null)?.attempts;
            return (
              <li key={i} className={cls} title={s.error ?? undefined}>
                <span className="name">{tDyn(lang, `span.${s.name}`, s.name)}{attempts && attempts > 1 ? ` (${attempts} ${t(lang, "au.attempts")})` : ""}</span>
                <span className="track"><i style={{ left: 0, width: `${Math.max(2, (s.latency_ms / totalMs) * 100)}%` }} /></span>
                <span className="ms">{fmtMs(s.latency_ms)}</span>
              </li>
            );
          })}
        </ul>
      </section>

      <div className="stats">
        <div className="stat"><b>{fmtMs(turn?.latency_ms ?? res.audit.latency_ms)}</b><span>{t(lang, "au.latency")}</span></div>
        <div className="stat"><b>{turn ? `${turn.tokens_in ?? 0} / ${turn.tokens_out ?? 0}` : "—"}</b><span>{t(lang, "au.tokens")}</span></div>
        <div className="stat"><b>{turn ? fmtUsd(turn.cost_usd ?? 0) : "—"}</b><span>{t(lang, "au.cost")}</span></div>
      </div>

      <section>
        <h3 style={{ marginBottom: 6 }}>{t(lang, "au.writer")}</h3>
        <span className={`chip ${fellBack ? "warn" : "ok"}`}>{t(lang, fellBack ? "au.writer.template" : "au.writer.llm")}</span>
        {turn?.versions && (
          <p className="mono-small" style={{ marginTop: 10 }}>
            {t(lang, "au.versions")}: {Object.entries(turn.versions).map(([k, v]) => `${k} ${v}`).join(" · ")}
          </p>
        )}
      </section>
    </div>
  );
}
