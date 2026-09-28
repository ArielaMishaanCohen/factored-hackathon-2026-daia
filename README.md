# LATAM Bank · Intake de disputas con IA

Factored AI & Data Hackathon 2026 · equipo DAIA.

Asistente que recibe reclamos por cargos en español y portugués, identifica la transacción del cliente autenticado, aplica una política determinista y registra el caso (con confirmación) o escala a un humano con un handoff estructurado. El LLM entiende y redacta; el código decide y actúa.

> **Estado: Fase 1 terminada.** El repo tiene la estructura final, los contratos en código y **stubs** que los cumplen. Ninguna pieza "real" (pipeline, clasificador, Gemini, SQLite) está implementada todavía.

## Documentos

| Documento | Qué tiene |
| :-- | :-- |
| [docs/design.md](docs/design.md) | **Contratos congelados (v1.0):** alcance, intenciones, política, herramientas, handoff, API, auth |
| [docs/decisions.md](docs/decisions.md) | Cada decisión con alternativas y evidencia |
| [docs/decisions_fase_0.md](docs/decisions_fase_0.md) | Por qué este flujo (matriz de decisión) |
| [docs/roadmap_fases_1_a_8.md](docs/roadmap_fases_1_a_8.md) | Plan por fases y roles |
| [docs/NOTAS_DATOS.md](docs/NOTAS_DATOS.md) | Hallazgos del EDA |

## Cómo correrlo

```bash
cp .env.example .env          # completar JWT_SECRET (y GEMINI_API_KEY cuando haga falta)
make setup                    # .venv + dependencias + npm install
make test                     # tests de contrato
make dev-backend              # API en http://localhost:8000  (docs: /docs)
make dev-frontend             # UI en http://localhost:5173
```

Con Docker (una sola imagen: FastAPI sirve la API y el build de React):

```bash
make up                       # http://localhost:8000
```

Para trabajar el frontend sin backend: `VITE_USE_MOCK=true` en `frontend/.env`.

**Demo con los stubs** (OTP de prueba `123456`):

| Cliente | Mensaje | Qué pasa |
| :-- | :-- | :-- |
| Cliente demo 1 | "No reconozco un cargo de 350 en Oxxo" | Una candidata → confirmación → caso creado y verificado (R12) |
| Cliente demo 2 | "Me cobraron dos veces 120000" | Dos candidatas → el cliente elige |
| Cliente demo 3 | "Não reconheço uma compra de 3.500" | R7: bloqueo con confirmación → caso → handoff a fraude |
| Cualquiera | "Quiero un préstamo" | Se abstiene y explica qué sí puede hacer |

Agente humano: `POST /api/auth/agent-login` con `AGT-DEMO` / `123456`.

## Estructura

```
config/policy.yaml        umbrales y reglas versionados (fuente única)
backend/app/
  schemas.py              contratos Pydantic (design.md 2–6) ← fuente única en código
  main.py                 endpoints de la API (design.md 6)
  auth.py                 identidad simulada + JWT (design.md 7)
  confirmations.py        acciones pendientes y tokens de confirmación
  orchestrator.py         máquina de estados            [STUB]
  policy/engine.py        motor de política              [STUB: R2–R4, R7, R12]
  nlu/stub.py             intención por palabras clave   [STUB]
  tools/                  transactions, cases, cards, handoff sobre datos falsos [STUB]
  responder/templates.py  plantillas ES/PT
  tracing.py              traza por turno                [en memoria]
  store.py                estado operativo               [en memoria → SQLite]
frontend/src/api/         types.ts (espejo de schemas.py), client.ts, mock.ts
data_pipeline/            contracts.py (transactions, products), run_pipeline.py [esqueleto]
ml/intent/                labeling_guide.md, data/
eval/, tests/, prompts/   (Fases 6 y 7)
```

## Qué sigue por rol

La regla: **se reemplaza el stub sin cambiar su firma.** `tests/test_api_contract.py` tiene que seguir pasando.

| Rol | Empieza por | Reemplaza |
| :-- | :-- | :-- |
| **A · Datos** | `run_pipeline.py` → bronze/silver/gold; completar `amount_usd` en ARS/COP con `daily_exchange_rates` (el contrato ya falla sin eso); elegir los `demo_customers` reales | `tools/stub_data.py` → `gold.duckdb` (columnas de design.md 4.5) |
| **B · ML** | Set etiquetado siguiendo `ml/intent/labeling_guide.md`; baselines; cliente de Gemini con fallback | `nlu/stub.py` → clasificador + extracción (misma salida `NLUResult`) |
| **C · Backend** | R0–R12 completas con tests por regla; SQLite; aclaraciones con contador; fallas de herramienta y reintentos | `policy/engine.py`, `store.py`, `orchestrator.py`, `tools/*` |
| **D · Frontend** | Diseño del chat, tarjetas de transacciones, consola del agente, panel de auditoría, textos ES/PT | `frontend/src/App.tsx` (el cliente y los tipos ya están) |

Cambiar un contrato: PR que toque `design.md` + `schemas.py` + `types.ts` juntos, y aviso al equipo.

## Datos

Los datos del reto son sintéticos (LATAM Bank v1.0.0, S3 del organizador). No se suben al repo (`data/` está en `.gitignore`). Las frases en portugués y el set de evaluación los genera el equipo y se declaran como tales.
