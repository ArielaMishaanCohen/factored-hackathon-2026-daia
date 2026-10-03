"""Proyección offline, no medición en producción. Tasas proporcionadas explícitamente."""
import argparse
from datetime import date
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/runs/20260929T234658Z-7cf922c1/metricas_problema.json"


def project(data, rate, minimum, maximum):
    if not all(math.isfinite(x) for x in (rate, minimum, maximum)) or not 0 <= minimum <= rate <= maximum <= 1:
        raise ValueError("Se requiere 0 <= mínimo <= tasa <= máximo <= 1")
    period = data["populations"]["complaints"]
    days = (date.fromisoformat(period["date_to"]) - date.fromisoformat(period["date_from"])).days + 1
    if days <= 0:
        raise ValueError("Período histórico inválido")
    disputes = data["disputes"]
    contacts = next(x for x in data["call_center_by_category"] if x["reason_category"] == "Queja")
    aht = contacts["mean_duration_seconds"] if contacts["duration_denominator"] else None
    annual = disputes["n"] * 365 / days
    scenarios = {}
    for label, r in (("minimum", minimum), ("central", rate), ("maximum", maximum)):
        scenarios[label] = {"safe_auto_resolution_rate": r, "annual_disputes_without_human": annual * r,
                            "agent_hours_saved": annual * r * aht / 3600 if aht is not None else None}
    return {"label": "proyección offline, no medición en producción", "scenarios": scenarios,
            "annual_disputes": {"value": annual, "numerator": disputes["n"] * 365, "denominator": days,
                                "historical_n": disputes["n"], "period": period},
            "aht_seconds": {"value": aht, "n": contacts["duration_denominator"], "contacts": contacts["contacts"]},
            "historical_followup": {"open_or_in_process": disputes["open_or_in_process"],
                "sla_breached": disputes["sla_breached_numerator"], "n": disputes["n"],
                "union": None, "note": "Grupos posiblemente solapados; no sumar ni afirmar que se evitan todos."},
            "assumptions": [
                "Volumen: disputes.n / días inclusivos de populations.complaints × 365; anualización de todo el histórico, no conteo del último año.",
                "Tasa: parámetro externo; el rango no es un intervalo de confianza. No se etiqueta como resultado final sin las corridas finales.",
                "Se extrapola la tasa del set a disputas históricas; el set estratificado no representa necesariamente su mezcla real.",
                "AHT: call_center_by_category[Queja].mean_duration_seconds, solo duraciones observadas; proxy de atención de disputas.",
                "Un contacto de queja ahorrado por disputa automatizada; no se mide ahorro real, adopción, costos de revisión ni contactos adicionales.",
                "Abiertas y SLA: disputes.open_or_in_process y sla_breached_numerator; descriptivos históricos, sin inferencia causal de reducción.",
            ]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, default=SOURCE)
    p.add_argument("--rate", type=float, required=True)
    p.add_argument("--min-rate", type=float, required=True)
    p.add_argument("--max-rate", type=float, required=True)
    p.add_argument("--rate-source", required=True, help="Corridas de origen o 'escenario ilustrativo'")
    p.add_argument("--output", type=Path, default=ROOT / "eval/reports/impacto.json")
    a = p.parse_args()
    result = project(json.loads(a.source.read_text(encoding="utf-8")), a.rate, a.min_rate, a.max_rate)
    result["source"] = {"path": str(a.source), "sha256": hashlib.sha256(a.source.read_bytes()).hexdigest(), "rate_source": a.rate_source}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    print(a.output)


if __name__ == "__main__":
    main()
