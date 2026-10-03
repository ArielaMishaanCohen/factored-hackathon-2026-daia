"""Audita resultados B1 sin volver a ejecutar el sistema."""
import argparse
import json
from pathlib import Path
from eval.formato import CaseResult, Manifest, read_json, read_jsonl


def verify(run_dir):
    manifest = read_json(run_dir / "manifest.json", Manifest)
    results = read_jsonl(run_dir / "results.jsonl", CaseResult)
    errors = []
    if (manifest.system, manifest.llm, manifest.versions.nlu_mode) != ("B1", "without_gemini", "keywords"):
        errors.append("Configuración distinta de B1/without_gemini/keywords")
    if set(manifest.case_ids) != {r.case_id for r in results} or len(results) != len(manifest.case_ids):
        errors.append("Resultados faltantes o duplicados")
    nlu_count = 0
    for r in results:
        def error(message):
            errors.append(f"{r.case_id}: {message}")
        if r.status == "runner_error" or r.trace is None:
            error("resultado sin traza válida")
        if r.cost_usd != 0 or r.tokens_in != 0 or r.tokens_out != 0:
            error("costo o tokens distintos de cero")
        for t in r.trace.turns if r.trace else []:
            version = t.versions.get("intent_model", "")
            nlu_used = any(s.name == "nlu.understand" for s in t.spans)
            valid_version = version.startswith("stub-keywords-0") if nlu_used else version == "none"
            if not valid_version or t.versions.get("nlu_mode") != "keywords":
                error("versión del NLU distinta de palabras clave")
            if t.cost_usd or t.tokens_in or t.tokens_out:
                error("uso de LLM en turno")
            for span in t.spans:
                if span.cost_usd or span.tokens_in or span.tokens_out or span.model:
                    error("span con uso de modelo")
                if span.name == "nlu.understand":
                    nlu_count += 1
                    if span.output.get("extractor") != "rules":
                        error("extractor distinto de rules")
                if span.name.startswith("llm.") and span.output.get("source") not in (None, "template"):
                    error("composición distinta de plantilla")
        for t in r.turns:
            if t.response and any(m.source != "template" for m in t.response.messages):
                error("mensaje no generado con plantilla")
    if not results or not nlu_count:
        errors.append("No hay evidencia de ejecución del NLU")
    return {"passed": not errors, "run_id": manifest.run_id, "n_cases": len(results),
            "n_nlu_spans": nlu_count, "errors": errors,
            "scope": "Auditoría de versiones, extractor, plantillas, tokens y costo registrados; comparte orquestador y política con S."}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run_dir", type=Path)
    a = p.parse_args()
    result = verify(a.run_dir)
    (a.run_dir / "b1_audit.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
