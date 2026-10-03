"""B0 histórico; no comparte la carga del benchmark conversacional."""
import argparse
import hashlib
import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
NOTE = "datos históricos, no es la misma carga que el set de evaluación"


def metric(numerator, denominator, unit="ratio", *, value=None, note=NOTE):
    return dict(value=value if value is not None else (numerator / denominator if denominator and numerator is not None else None),
                numerator=numerator, denominator=denominator, n=denominator, unit=unit, note=note)


def build(metrics):
    contacts = metrics["call_center_by_category"]
    complaint = next(x for x in contacts if x["reason_category"] == "Queja")
    disputes = metrics["disputes"]
    n = disputes["resolution_denominator"]
    return {"system": "B0", "note": NOTE, "reference_date": metrics["reference_date"],
            "populations": metrics["populations"], "metrics": {
                "fcr_queja": metric(complaint["fcr_numerator"], complaint["fcr_denominator"]),
                "fcr_global": metric(sum(x["fcr_numerator"] for x in contacts), sum(x["fcr_denominator"] for x in contacts)),
                "dispute_resolution_mean_days": metric(disputes["mean_resolution_days"] * n if n else None, n, "days",
                    note=NOTE + "; suma reconstruida de media × n; excluye duraciones nulas"),
                "dispute_resolution_median_days": metric(None, n, "days", value=disputes["median_resolution_days"],
                    note=NOTE + "; mediana, no cociente: numerador no aplica; excluye duraciones nulas"),
                "dispute_sla_breached": metric(disputes["sla_breached_numerator"], disputes["sla_denominator"]),
                "dispute_open_or_in_process": metric(disputes["open_or_in_process"], disputes["n"]),
            }}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--gold", type=Path, default=ROOT / "data/gold/gold.duckdb")
    p.add_argument("--output", type=Path, default=ROOT / "eval/reports/b0.json")
    a = p.parse_args()
    with duckdb.connect(str(a.gold), read_only=True) as db:
        metrics = {k: json.loads(v) for k, v in db.execute("SELECT metric, value_json FROM baseline_metrics").fetchall()}
    result = build(metrics)
    result["source"] = {"gold": str(a.gold), "table": "baseline_metrics",
                        "sha256": hashlib.sha256(a.gold.read_bytes()).hexdigest()}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    print(a.output)


if __name__ == "__main__":
    main()
