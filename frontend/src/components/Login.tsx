import { useEffect, useState } from "react";
import type { DemoCustomer, Language } from "../api/types";
import { t } from "../i18n";

export function Login({ lang, setLang, customers, loadState, expiredFor, error, busy, onLogin }: {
  lang: Language; setLang: (l: Language) => void; customers: DemoCustomer[]; loadState: "loading" | "ok" | "fail";
  expiredFor: string | null; error: string | null; busy: boolean; onLogin: (c: DemoCustomer, otp: string) => void;
}) {
  const [selected, setSelected] = useState<string | null>(expiredFor);
  const [otp, setOtp] = useState("123456");
  useEffect(() => { if (!selected && customers.length) setSelected(expiredFor ?? customers[0].customer_id); }, [customers, expiredFor, selected]);
  const chosen = customers.find((c) => c.customer_id === selected) ?? null;

  return (
    <div className="login">
      <form className="login-card" onSubmit={(e) => { e.preventDefault(); if (chosen) onLogin(chosen, otp); }}>
        <div className="login-head">
          <div>
            <h1>{t(lang, "login.title")}</h1>
            <p className="lead">{t(lang, "login.lead")}</p>
          </div>
          <div className="seg" role="group" aria-label="Idioma / Idioma">
            <button type="button" aria-pressed={lang === "es"} onClick={() => setLang("es")}>ES</button>
            <button type="button" aria-pressed={lang === "pt"} onClick={() => setLang("pt")}>PT</button>
          </div>
        </div>

        {expiredFor && <div className="notice warn" role="status">{t(lang, "login.expired")}</div>}
        {error && <div className="notice bad" role="alert">{error}</div>}
        {loadState === "loading" && <p className="muted">{t(lang, "login.loading")}</p>}
        {loadState === "fail" && <div className="notice bad" role="alert">{t(lang, "login.empty")}</div>}

        <div className="cust-grid">
          {customers.map((c) => (
            <button type="button" key={c.customer_id} className="cust" aria-pressed={selected === c.customer_id} onClick={() => setSelected(c.customer_id)}>
              <b>{c.display_name}</b>
              <small>{c.scenario}</small>
              <span className="tags">
                <span className="chip">{c.segment}</span>
                <span className="chip">{c.country}</span>
                <span className="chip accent">{c.suggested_language.toUpperCase()}</span>
              </span>
            </button>
          ))}
        </div>

        <div className="login-actions">
          <label className="field">
            {t(lang, "login.otp")}
            <input className="input" value={otp} onChange={(e) => setOtp(e.target.value)} inputMode="numeric" autoComplete="one-time-code" maxLength={12} style={{ width: 160 }} />
          </label>
          <button className="btn primary" type="submit" disabled={!chosen || busy}>{t(lang, "login.enter")}</button>
        </div>
        <div className="login-foot"><span>{t(lang, "login.wake")}</span></div>
      </form>
    </div>
  );
}
