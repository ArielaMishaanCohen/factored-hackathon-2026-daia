import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { ChatResponse, ChatUI, DisputeCase, Language, TransactionView } from "../api/types";
import { fmtAmount, fmtDate, fmtMs, matchesAmount, matchesMerchant, priorityTone, remaining } from "../format";
import { t, tDyn } from "../i18n";

export type TurnRec = { res: ChatResponse; userText: string | null };

export type Item =
  | { id: number; from: "user"; text: string }
  | { id: number; from: "err"; text: string; retry?: () => void }
  | {
      id: number; from: "bot"; text: string; source: "llm" | "template";
      turn: number;            // índice en `turns`
      lastOfTurn: boolean;     // el último mensaje del turno lleva la tarjeta y la línea de métricas
    };

function useNow(ms: number): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const id = setInterval(() => setNow(Date.now()), ms); return () => clearInterval(id); }, [ms]);
  return now;
}

// --- Comprobante de una transacción candidata ---------------------------------------------

export function TxSlip({ tx, lang, userText, onPick, disabled }: {
  tx: TransactionView; lang: Language; userText: string; onPick?: () => void; disabled?: boolean;
}) {
  const amountHit = userText ? matchesAmount(userText, tx.amount) : false;
  const merchantHit = userText ? matchesMerchant(userText, tx.merchant_name) : false;
  const body = (
    <>
      <div className="slip-main">
        <div className="slip-date">{fmtDate(tx.business_date, lang)}</div>
        <div className={`slip-merchant${tx.merchant_name ? "" : " none"}`}>{tx.merchant_name ?? t(lang, "tx.noMerchant")}</div>
        <div className="slip-amount">{fmtAmount(tx.amount, lang)}<small>{tx.currency}</small></div>
      </div>
      <div className="slip-tear" aria-hidden="true" />
      <div className="slip-foot">
        <span>{tDyn(lang, `tx.${tx.transaction_type}`, tx.transaction_type)} · {tx.channel}</span>
        {tx.card_mask && <span>· {t(lang, "tx.card")} {tx.card_mask}</span>}
        <span className={`chip ${tx.status === "Approved" ? "" : "warn"}`}>{tDyn(lang, `tx.${tx.status}`, tx.status)}</span>
        {amountHit && <span className="chip ok">✓ {t(lang, "tx.matchAmount")}</span>}
        {merchantHit && <span className="chip ok">✓ {t(lang, "tx.matchMerchant")}</span>}
        {onPick && <span className="slip-pick">{t(lang, "tx.pick")}</span>}
      </div>
    </>
  );
  return onPick
    ? <button className="slip" onClick={onPick} disabled={disabled}>{body}</button>
    : <div className="slip static">{body}</div>;
}

// --- Confirmación ----------------------------------------------------------------------------

function Confirmation({ ui, lang, busy, onConfirm, onCancel }: {
  ui: ChatUI; lang: Language; busy: boolean; onConfirm: () => void; onCancel: () => void;
}) {
  const now = useNow(1000);
  const pa = ui.pending_action!;
  const left = remaining(pa.expires_at, now);
  const block = pa.action === "block_card";
  return (
    <section className={`card ${block ? "bad" : ""}`} aria-label={t(lang, block ? "confirm.block" : "confirm.case")}>
      <div className="card-head">
        <span className="ico" aria-hidden="true">{block ? "!" : "✓"}</span>
        <h2>{t(lang, block ? "confirm.block" : "confirm.case")}</h2>
      </div>
      <div className="card-body">
        <p className="big">{pa.summary}</p>
        <p>{t(lang, "confirm.lead")}</p>
      </div>
      <div className="card-actions">
        <button className={`btn ${block ? "danger" : "primary"}`} onClick={onConfirm} disabled={busy || left.overdue}>{t(lang, "chat.confirm")}</button>
        <button className="btn" onClick={onCancel} disabled={busy}>{t(lang, "chat.cancel")}</button>
        <span className="grow" />
        <span className={`chip ${left.overdue ? "bad" : ""}`}>
          {left.overdue ? t(lang, "confirm.expired") : `${t(lang, "confirm.expiresIn")} ${left.ms >= 60000 ? Math.ceil(left.ms / 60000) + " min" : Math.ceil(left.ms / 1000) + " s"}`}
        </span>
      </div>
    </section>
  );
}

function CaseCard({ c, lang }: { c: DisputeCase; lang: Language }) {
  return (
    <section className="card ok" aria-label={t(lang, "case.title")}>
      <div className="card-head"><span className="ico" aria-hidden="true">✓</span><h2>{t(lang, "case.title")}</h2></div>
      <div className="card-body">
        <p className="big">{c.case_id}</p>
        <dl className="kv">
          <dt>{t(lang, "case.priority")}</dt><dd>{tDyn(lang, `prio.${c.priority}`)}</dd>
          <dt>{t(lang, "case.sla")}</dt><dd>{fmtDate(c.sla_due_at, lang)}</dd>
          <dt>{t(lang, "case.rule")}</dt><dd>{c.rule_id}</dd>
        </dl>
      </div>
    </section>
  );
}

function HandoffCard({ ui, caseId, lang }: { ui: ChatUI; caseId: string | null; lang: Language }) {
  return (
    <section className="card warn" aria-label={t(lang, "handoff.title")}>
      <div className="card-head"><span className="ico" aria-hidden="true">↗</span><h2>{t(lang, "handoff.title")}</h2></div>
      <div className="card-body">
        <p>{t(lang, "handoff.lead")}</p>
        <dl className="kv">
          {caseId && (<><dt>{t(lang, "case.title")}</dt><dd>{caseId}</dd></>)}
          <dt>{t(lang, "handoff.queue")}</dt><dd>{ui.queue ? tDyn(lang, `queue.${ui.queue}`) : "—"}</dd>
          <dt>Handoff</dt><dd>{ui.handoff_id}</dd>
        </dl>
      </div>
    </section>
  );
}

// --- Estado de los reclamos (estado_disputa) ------------------------------------------------

function stepIndex(status: DisputeCase["status"]): number {
  if (status === "Open") return 0;
  if (status === "In Process" || status === "Escalated") return 1;
  return 2;
}

export function CaseStatus({ lang, refreshKey }: { lang: Language; refreshKey: number }) {
  const [cases, setCases] = useState<DisputeCase[] | null>(null);
  useEffect(() => { api.cases().then((r) => setCases(r.cases)).catch(() => setCases([])); }, [refreshKey]);
  if (cases === null) return null;
  const shown = [...cases].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 3);
  return (
    <div className="stepper-card" aria-label={t(lang, "stepper.title")}>
      {shown.length === 0 && <p className="muted">{t(lang, "stepper.empty")}</p>}
      {shown.map((c) => {
        const idx = stepIndex(c.status);
        const rejected = c.status === "Rejected";
        const labels = [t(lang, "stepper.received"), t(lang, "stepper.review"), rejected ? t(lang, "stepper.rejected") : t(lang, "stepper.resolved")];
        return (
          <article className="stepper-item" key={c.case_id}>
            <header><h2>{c.case_id}</h2><span className="muted">{t(lang, "case.sla")} {fmtDate(c.sla_due_at, lang)}</span></header>
            <div className="steps">
              {labels.map((label, i) => {
                const cls = rejected && i === 2 ? "rejected" : i < idx ? "done" : i === idx ? (idx === 2 ? "done" : "now") : "";
                return <div key={label} className={`step ${cls}`}><i /><span>{label}</span></div>;
              })}
            </div>
          </article>
        );
      })}
    </div>
  );
}

// --- Chat ---------------------------------------------------------------------------------------

export function Chat({ lang, items, turns, busy, input, setInput, onSend, onPick, onConfirm, onCancel,
  selTurn, onSelectTurn, lastTyped, caseRefresh, staleBefore }: {
  lang: Language; items: Item[]; turns: TurnRec[]; busy: boolean; input: string; setInput: (v: string) => void;
  onSend: (text: string) => void; onPick: (tx: TransactionView) => void;
  onConfirm: (id: string) => void; onCancel: (id: string) => void;
  selTurn: number | null; onSelectTurn: (i: number) => void; lastTyped: string; caseRefresh: number; staleBefore: number;
}) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ block: "end" }); }, [items.length, busy]);
  const lastTurn = turns.length - 1;

  return (
    <>
      <div className="thread" role="log" aria-live="polite">
        <div className="thread-inner">
          {items.length === 0 && !busy && <p className="empty">{t(lang, "chat.empty")}</p>}
          {items.map((it) => {
            if (it.from === "user") return <div key={it.id} className="msg user"><div className="bubble">{it.text}</div></div>;
            if (it.from === "err") {
              return (
                <div key={it.id} className="msg bot err">
                  <div className="bubble">{it.text}{it.retry && <> <button className="btn small" onClick={it.retry}>{t(lang, "chat.retry")}</button></>}</div>
                </div>
              );
            }
            const rec = turns[it.turn];
            const res = rec.res;
            const live = it.turn === lastTurn;
            const ui = it.lastOfTurn ? res.ui : null;
            return (
              <div key={it.id} className="msg bot" style={{ maxWidth: "100%" }}>
                <div className="bubble" style={{ alignSelf: "flex-start", maxWidth: "86%" }}>{it.text}</div>
                {ui?.type === "transaction_options" && live && (
                  <div className="slips">
                    {ui.options?.map((tx) => (
                      <TxSlip key={tx.transaction_id} tx={tx} lang={lang} userText={lastTyped} disabled={busy} onPick={() => onPick(tx)} />
                    ))}
                  </div>
                )}
                {ui?.type === "confirmation" && live && ui.pending_action && it.turn < staleBefore && (
                  <p className="notice warn" role="status" style={{ maxWidth: 480 }}>{t(lang, "confirm.invalidated")}</p>
                )}
                {ui?.type === "confirmation" && live && ui.pending_action && it.turn >= staleBefore && (
                  <Confirmation ui={ui} lang={lang} busy={busy}
                    onConfirm={() => onConfirm(ui.pending_action!.pending_action_id)}
                    onCancel={() => onCancel(ui.pending_action!.pending_action_id)} />
                )}
                {ui?.type === "case_created" && ui.case && <CaseCard c={ui.case} lang={lang} />}
                {ui?.type === "handoff" && <HandoffCard ui={ui} caseId={res.case?.case_id ?? null} lang={lang} />}
                {it.lastOfTurn && res.state === "INFORMAR_ESTADO" && <CaseStatus lang={lang} refreshKey={caseRefresh} />}
                {it.lastOfTurn && (
                  <div className="msg-meta">
                    <button aria-pressed={selTurn === it.turn || (selTurn === null && live)} onClick={() => onSelectTurn(it.turn)} title={t(lang, "chat.turnDetail")}>
                      {fmtMs(res.audit.latency_ms)}{res.audit.rule_id ? ` · ${res.audit.rule_id}` : ""} · {t(lang, it.source === "llm" ? "chat.source.llm" : "chat.source.template")}
                    </button>
                  </div>
                )}
              </div>
            );
          })}
          {busy && <div className="typing" aria-live="polite"><i /><i /><i /><span>{t(lang, "chat.thinking")}</span></div>}
          <div ref={end} />
        </div>
      </div>
      <div className="composer">
        <form onSubmit={(e) => { e.preventDefault(); const v = input.trim(); if (v && !busy) onSend(v); }}>
          <input className="input" value={input} onChange={(e) => setInput(e.target.value)}
            placeholder={t(lang, "chat.placeholder")} aria-label={t(lang, "chat.placeholder")} maxLength={2000} autoComplete="off" />
          <button className="btn primary" type="submit" disabled={busy || !input.trim()}>{t(lang, "chat.send")}</button>
        </form>
      </div>
    </>
  );
}

export { priorityTone };
