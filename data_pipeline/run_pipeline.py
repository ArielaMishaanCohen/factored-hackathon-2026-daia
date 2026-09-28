"""CLI del pipeline (Fase 2, rol A). ESQUELETO de Fase 1.

    python -m data_pipeline.run_pipeline --full
    python -m data_pipeline.run_pipeline --incremental --since 2026-06-15

Pasos: ingest (S3 → bronze) → transform (bronze → silver, contratos) → build_gold
(silver → gold) → quality_report.json + manifest.json.
"""
from __future__ import annotations

import argparse
from datetime import date


def main() -> None:
    p = argparse.ArgumentParser(description="S3 → bronze → silver → gold")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--full", action="store_true", help="Reprocesa todo")
    mode.add_argument("--incremental", action="store_true", help="Solo particiones nuevas + ventana de reproceso")
    p.add_argument("--since", type=date.fromisoformat, help="Fecha de corte (AAAA-MM-DD) para --incremental")
    p.add_argument("--reprocess-days", type=int, default=3, help="Ventana para llegadas tardías")
    args = p.parse_args()
    if args.incremental and not args.since:
        p.error("--incremental requiere --since")

    # TODO Fase 2 (A):
    # 1. ingest.py      → bronze con _source_file, _ingested_at, _file_hash
    # 2. transform.py   → silver: dedup por PK, tipos, zona horaria, business_date, amount_usd; valida contracts.py
    # 3. build_gold.py  → gold.duckdb: dispute_transactions, cards, customer_profile, demo_customers
    #                     (columnas acordadas en docs/design.md 4.5; sin PII)
    # 4. quality.py     → reports/quality_report.json
    # 5. lineage.py     → data/manifest.json
    raise SystemExit(f"Pipeline aún no implementado (modo: {'full' if args.full else 'incremental'}).")


if __name__ == "__main__":
    main()
