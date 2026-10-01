"""Formato de salida de una corrida de evaluación (Fase 6.2-6.5, Paso 0).

Fuente única en código de eval/FORMATO_RESULTADOS.md. Lo escriben el runner (S y B1 por igual) y
los graders; lo leen los graders, el reporte y el impacto. Si cambias algo aquí, sube
FORMAT_VERSION y actualiza el .md en el mismo commit.

eval/reports/<run_id>/
    manifest.json   -> Manifest
    results.jsonl   -> CaseResult (una línea por caso)
    grades.jsonl    -> Grade (una línea por caso y por campo)
    metrics.json    -> RunMetrics

Los objetos del backend (ChatRequest, ChatResponse, Trace, DisputeCase, HandoffPackage) se
guardan tal cual, con los modelos de backend/app/schemas.py: si el contrato del backend cambia,
la validación de la salida falla en vez de calificar algo distinto sin avisar.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, Field, model_validator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.schemas import (  # noqa: E402
    ChatRequest,
    ChatResponse,
    DisputeCase,
    ErrorResponse,
    HandoffPackage,
    Language,
    Trace,
)

FORMAT_VERSION = "1.0.0"

System = Literal["S", "B1"]
LLMConfig = Literal["with_gemini", "without_gemini"]
Split = Literal["dev", "heldout"]
Stage = Literal["debug", "primera", "final"]   # regla de oro 2: primera corrida vs. final


# --- manifest.json --------------------------------------------------------------------------------


class Versions(BaseModel):
    """De GET /health al empezar la corrida, más lo que el backend no expone."""

    policy_version: str
    intent_model: str                 # "stub-keywords-0" en B1
    llm_model: str | None             # el configurado; sin Gemini no prueba que se usó (ver cost_usd)
    data_source: str                  # "gold:gold.duckdb" o "stub"
    data_manifest: str | None         # HealthResponse.data_manifest
    data_run: str                     # provenance.data_run de los casos
    nlu_mode: Literal["full", "keywords"]   # B1 = keywords (opción A)
    prompts: dict[str, str] = {}      # p. ej. {"extraccion": "extraccion_v3", "redaccion": "redaccion_v1"}


class Manifest(BaseModel):
    format_version: str = FORMAT_VERSION
    run_id: str                       # <YYYYMMDDTHHMMSSZ>-<system>-<llm>-r<n>-<split>
    system: System
    llm: LLMConfig
    run_number: int = Field(ge=1, le=3)
    stage: Stage
    split: Split
    cases_file: str                   # eval/cases/dev.jsonl
    cases_sha256: str                 # del archivo completo; en heldout tiene que ser el congelado
    case_ids: list[str]               # los que se corrieron, en orden
    skipped_case_ids: list[str] = []  # p. ej. setup.llm = with_gemini en una corrida without_gemini
    git_commit: str
    git_dirty: bool                   # true = hay cambios sin commit; se declara en el reporte
    versions: Versions
    env: dict[str, str]               # FAULT_INJECTION, OPS_DB_PATH, NLU_MODE... (nunca claves)
    started_at: datetime
    finished_at: datetime | None = None
    n_completed: int = 0
    n_max_turns: int = 0
    n_runner_error: int = 0


# --- results.jsonl --------------------------------------------------------------------------------


class Turn(BaseModel):
    """Una petición a /chat: lo que mandó el cliente simulado y lo que volvió."""

    n: int = Field(ge=1)                  # cuenta todas las peticiones (SCHEMA.md §1.3)
    reason: str                           # "script[0]", "confirm create_dispute_case", "reauth"...
    request: ChatRequest
    fault_injected: list[str] = []        # herramientas en X-Fault-Inject
    session_expired_before: bool = False  # el runner llamó a /auth/demo/expire antes de este turno
    http_status: int
    response: ChatResponse | None = None  # si http_status == 200
    error: ErrorResponse | None = None    # si no
    client_latency_ms: int                # medida por el runner, incluye la serialización

    @model_validator(mode="after")
    def _respuesta_o_error(self):
        if (self.http_status == 200) != (self.response is not None):
            raise ValueError("response va si y solo si http_status == 200")
        return self


class Flags(BaseModel):
    identification_failed: bool = False   # la esperada no estaba entre las opciones
    max_turns_reached: bool = False


class CaseResult(BaseModel):
    format_version: str = FORMAT_VERSION
    run_id: str
    case_id: str
    # copiados del caso para desagregar sin volver a abrirlo; el esperado se lee de eval/cases/
    category: str
    language: Language | Literal["mix"]
    segment: str
    status: Literal["completed", "max_turns", "runner_error"]
    runner_error: str | None = None       # traceback corto si status == runner_error
    flags: Flags
    turns: list[Turn]
    trace: Trace | None                   # store.traces[trace_id] al terminar (una por conversación)
    cases: list[DisputeCase]              # GET /cases del cliente al terminar
    handoffs: list[HandoffPackage]        # GET /handoffs/{id} de todos los del store
    latency_ms: int                       # suma de TraceTurn.latency_ms
    tokens_in: int
    tokens_out: int
    cost_usd: float                       # suma de TraceTurn.cost_usd; 0 sin Gemini
    started_at: datetime


# --- grades.jsonl ---------------------------------------------------------------------------------


class Grade(BaseModel):
    """Un veredicto por caso y por campo (SCHEMA.md §1.4 y §1.5)."""

    run_id: str
    case_id: str
    kind: Literal["expected", "forbidden", "forbidden_marker", "handoff"]
    field: str              # "rule_id", "case.priority", "wrong_transaction", "handoff.verified_facts"...
    expected: Any = None    # para forbidden: false (no debe ocurrir)
    observed: Any = None
    verdict: Literal["pass", "fail", "not_applicable", "grader_error"]
    evidence: str           # de dónde se leyó: "trace.turns[0].spans[policy.evaluate].output.rule_id"
    detail: str | None = None
    grader_version: str


# --- metrics.json ---------------------------------------------------------------------------------


class Metric(BaseModel):
    name: str                             # "safe_auto_resolution", "containment", "latency_case_p95"...
    slice: dict[str, str] = {}            # {} = global; {"language": "pt"}, {"segment": "Student"}...
    value: float | None                   # None = no definido (p. ej. costo por éxito sin éxitos)
    numerator: float | None = None        # en ratios; None en percentiles
    denominator: float | None = None
    n: int                                # casos que entran en el cálculo
    unit: Literal["ratio", "count", "ms", "usd"]
    warning: str | None = None            # "n < 10", "0/N no prueba riesgo cero"...
    note: str | None = None


class RunMetrics(BaseModel):
    format_version: str = FORMAT_VERSION
    run_id: str
    system: System
    llm: LLMConfig
    split: Split
    stage: Stage
    grader_version: str
    computed_at: datetime
    n_cases: int
    metrics: list[Metric]


# --- Lectura y escritura --------------------------------------------------------------------------

M = TypeVar("M", bound=BaseModel)


def write_json(path: Path, obj: BaseModel) -> None:
    path.write_text(obj.model_dump_json(indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, obj: BaseModel) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(obj.model_dump_json() + "\n")


def read_json(path: Path, model: type[M]) -> M:
    return model.model_validate_json(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path, model: type[M]) -> list[M]:
    with path.open(encoding="utf-8") as f:
        return [model.model_validate_json(line) for line in f if line.strip()]


def validar_corrida(run_dir: Path) -> dict[str, int]:
    """Valida los archivos que existan en eval/reports/<run_id>/ y que todos digan el mismo run_id."""
    man = read_json(run_dir / "manifest.json", Manifest)
    cuenta = {"manifest": 1}
    for nombre, modelo in (("results.jsonl", CaseResult), ("grades.jsonl", Grade)):
        if (run_dir / nombre).exists():
            filas = read_jsonl(run_dir / nombre, modelo)
            if any(f.run_id != man.run_id for f in filas):
                raise ValueError(f"{nombre}: run_id distinto del manifest")
            cuenta[nombre] = len(filas)
    if (run_dir / "metrics.json").exists():
        if read_json(run_dir / "metrics.json", RunMetrics).run_id != man.run_id:
            raise ValueError("metrics.json: run_id distinto del manifest")
        cuenta["metrics"] = 1
    return cuenta


if __name__ == "__main__":
    for d in sys.argv[1:]:
        print(d, json.dumps(validar_corrida(Path(d))))
