import type { Language, Priority } from "./api/types";
import { locale, type UiLang } from "./i18n";

/** Mismo formato que el backend (templates.fmt_amount): 1952832.76 → '1.952.832,76' en ES y PT, para que la
 *  tarjeta y el texto del bot muestren el monto idéntico. */
export function fmtAmount(amount: number, _lang: Language): string {
  return amount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    .replace(/,/g, "_").replace(/\./g, ",").replace(/_/g, ".");
}

/** '2026-05-13' (fecha de negocio, sin zona) → '13 de mayo de 2026' / '13 de maio de 2026'. */
export function fmtDate(iso: string, lang: UiLang): string {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Intl.DateTimeFormat(locale(lang), { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" })
    .format(new Date(Date.UTC(y, m - 1, d)));
}

export function fmtDateTime(iso: string, lang: UiLang): string {
  return new Intl.DateTimeFormat(locale(lang), { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })
    .format(new Date(iso));
}

export function fmtMs(ms: number | null | undefined): string {
  if (ms == null) return "—";
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${ms} ms`;
}

export function fmtUsd(v: number | null | undefined): string {
  if (v == null) return "—";
  return v === 0 ? "$0" : `$${v < 0.01 ? v.toFixed(4) : v.toFixed(2)}`;
}

/** Tiempo restante hasta `iso`: { text: '2 d 4 h', overdue } */
export function remaining(iso: string, now: number): { text: string; overdue: boolean; ms: number } {
  const ms = new Date(iso).getTime() - now;
  const abs = Math.abs(ms);
  const d = Math.floor(abs / 86_400_000);
  const h = Math.floor((abs % 86_400_000) / 3_600_000);
  const m = Math.floor((abs % 3_600_000) / 60_000);
  const text = d > 0 ? `${d} d ${h} h` : h > 0 ? `${h} h ${m} min` : `${m} min`;
  return { text, overdue: ms < 0, ms };
}

export type Tone = "ok" | "warn" | "bad" | "neutral";

/** Semántica de color compartida con las slides: verde seguro/resuelto, ámbar escalado/abstenido, rojo inseguro/bloqueado. */
export function actionTone(action: string | null | undefined): Tone {
  switch (action) {
    case "AUTO_REGISTER":
    case "INFORM":
      return "ok";
    case "ESCALATE":
    case "NOT_FOUND":
    case "REAUTH":
      return "warn";
    case "FRAUD":
      return "bad";
    default:
      return "neutral";
  }
}

export function priorityTone(p: Priority): Tone {
  return p === "critical" ? "bad" : p === "high" ? "warn" : p === "medium" ? "neutral" : "ok";
}

// --- Coincidencias entre lo que escribió el cliente y una candidata (solo para explicar la tarjeta) ---

function canonical(raw: string): number | null {
  let s = raw.replace(/[^\d.,]/g, "").replace(/^[.,]+|[.,]+$/g, "");
  if (!s) return null;
  if (s.includes(".") && s.includes(",")) {
    const dec = s.lastIndexOf(".") > s.lastIndexOf(",") ? "." : ",";
    s = s.replace(dec === "." ? /,/g : /\./g, "").replace(dec, ".");
  } else if (s.includes(".") || s.includes(",")) {
    const sep = s.includes(".") ? "." : ",";
    const parts = s.split(sep);
    s = parts.length > 2 || parts[1].length === 3 ? parts.join("") : s.replace(sep, ".");
  }
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

export function numbersIn(text: string): number[] {
  return (text.match(/\d[\d.,]*/g) ?? []).map(canonical).filter((n): n is number => n !== null);
}

const strip = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

export function matchesAmount(text: string, amount: number, tolerancePct = 2): boolean {
  return numbersIn(text).some((n) => n > 0 && Math.abs(n - amount) / amount <= tolerancePct / 100);
}

export function matchesMerchant(text: string, merchant: string | null): boolean {
  return !!merchant && strip(text).includes(strip(merchant));
}
