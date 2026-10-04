"""Estado operativo: conversaciones, casos, bloqueos, handoffs, trazas… (design.md 4.5).

Cómo funciona:
- Mientras atiende una petición, el backend trabaja con diccionarios en memoria (rápido y simple).
- Al TERMINAR cada petición, main.py llama a flush(): todo se guarda en SQLite.
- Al ARRANCAR, se carga todo desde SQLite. Así un reinicio no borra nada.

SQLite es una base de datos que vive en UN archivo (data/ops.sqlite): no hay que instalar
ni prender ningún servidor. Ideal para una demo; para producción se cambiaría por Postgres
(ver docs/operations.md).

Limitación conocida: pensado para UN proceso (un worker de uvicorn), que es como corre la demo.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .schemas import CardStatus, DisputeCase, HandoffPackage, PendingAction, Trace


@dataclass
class Conversation:
    conversation_id: str
    customer_id: str
    session_id: str
    state: str = "INICIO"
    language: str = "es"
    turn_id: int = 0
    original_request: str | None = None
    trace_id: str = ""
    data: dict = field(default_factory=dict)


@dataclass
class MemoryStore:
    conversations: dict[str, Conversation] = field(default_factory=dict)
    pending_actions: dict[str, PendingAction] = field(default_factory=dict)
    cases: dict[str, DisputeCase] = field(default_factory=dict)
    card_blocks: dict[str, CardStatus] = field(default_factory=dict)
    handoffs: dict[str, HandoffPackage] = field(default_factory=dict)
    traces: dict[str, Trace] = field(default_factory=dict)
    revoked_sessions: set[str] = field(default_factory=set)
    used_confirmation_tokens: set[str] = field(default_factory=set)
    _seq: dict[str, int] = field(default_factory=dict)

    def next_id(self, prefix: str, width: int = 6) -> str:
        self._seq[prefix] = self._seq.get(prefix, 0) + 1
        return f"{prefix}-{self._seq[prefix]:0{width}d}"


# --- Cómo se guarda cada cosa en SQLite -------------------------------------------------
# tabla -> (atributo del store, función para convertir el JSON de vuelta en objeto)
_OBJECT_TABLES = {
    "conversations": ("conversations", lambda d: Conversation(**d)),
    "pending_actions": ("pending_actions", PendingAction.model_validate),
    "cases": ("cases", DisputeCase.model_validate),
    "card_blocks": ("card_blocks", CardStatus.model_validate),
    "handoffs": ("handoffs", HandoffPackage.model_validate),
    "traces": ("traces", Trace.model_validate),
}
_SET_TABLES = {"revoked_sessions": "revoked_sessions", "used_confirmation_tokens": "used_confirmation_tokens"}


def _to_json(obj) -> str:
    if hasattr(obj, "model_dump_json"):          # modelos Pydantic
        return obj.model_dump_json()
    return json.dumps(asdict(obj), default=str)  # dataclasses (Conversation)


store = MemoryStore()
_lock = threading.Lock()
_db: sqlite3.Connection | None = None


def _connect(path: str | Path) -> sqlite3.Connection:
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path), check_same_thread=False)
    for table in [*_OBJECT_TABLES, *_SET_TABLES]:
        if table in _SET_TABLES:
            con.execute(f"CREATE TABLE IF NOT EXISTS {table} (id TEXT PRIMARY KEY)")
        else:
            con.execute(f"CREATE TABLE IF NOT EXISTS {table} (id TEXT PRIMARY KEY, data TEXT NOT NULL)")
    con.execute("CREATE TABLE IF NOT EXISTS sequences (prefix TEXT PRIMARY KEY, value INTEGER NOT NULL)")
    con.commit()
    return con


def _load() -> None:
    """Llena la memoria con lo que hay en SQLite."""
    store.__init__()
    for table, (attr, parse) in _OBJECT_TABLES.items():
        target = getattr(store, attr)
        for key, data in _db.execute(f"SELECT id, data FROM {table}"):
            target[key] = parse(json.loads(data))
    for table, attr in _SET_TABLES.items():
        getattr(store, attr).update(r[0] for r in _db.execute(f"SELECT id FROM {table}"))
    store._seq.update(dict(_db.execute("SELECT prefix, value FROM sequences")))


def flush() -> None:
    """Guarda en SQLite todo lo que hay en memoria. main.py lo llama al final de cada petición."""
    with _lock:
        with _db:  # una transacción: o se guarda todo, o nada
            for table, (attr, _) in _OBJECT_TABLES.items():
                _db.executemany(f"INSERT OR REPLACE INTO {table} (id, data) VALUES (?, ?)",
                                [(k, _to_json(v)) for k, v in getattr(store, attr).items()])
            for table, attr in _SET_TABLES.items():
                _db.executemany(f"INSERT OR IGNORE INTO {table} (id) VALUES (?)",
                                [(v,) for v in getattr(store, attr)])
            _db.executemany("INSERT OR REPLACE INTO sequences (prefix, value) VALUES (?, ?)",
                            list(store._seq.items()))


def use_database(path: str | Path) -> None:
    """Abre (o crea) la base en `path` y carga su contenido. ':memory:' = base temporal."""
    global _db
    with _lock:
        if _db is not None:
            _db.close()
        _db = _connect(path)
        _load()


def simulate_restart() -> None:
    """Para tests y demo: olvida la memoria y recarga desde SQLite, como un reinicio real."""
    with _lock:
        _load()


def reset_demo_customer(customer_id: str, product_ids: set[str], session_id: str) -> None:
    """Reinicia solo este cliente en memoria y SQLite; conserva secuencias y revocaciones."""
    with _lock:
        sessions = {c.session_id for c in store.conversations.values() if c.customer_id == customer_id}
        sessions.add(session_id)
        targets = {
            "conversations": [k for k, v in store.conversations.items() if v.customer_id == customer_id],
            "cases": [k for k, v in store.cases.items() if v.customer_id == customer_id],
            "card_blocks": [k for k in store.card_blocks if k in product_ids],
            "pending_actions": [k for k, v in store.pending_actions.items() if v.session_id in sessions],
            "handoffs": [k for k, v in store.handoffs.items() if v.customer.customer_id == customer_id],
            "traces": [k for k, v in store.traces.items() if v.customer_id == customer_id],
        }
        with _db:
            for table, ids in targets.items():
                _db.executemany(f"DELETE FROM {table} WHERE id = ?", [(k,) for k in ids])
        for table, ids in targets.items():
            for k in ids:
                getattr(store, table).pop(k, None)


def reset_store() -> None:
    """Borra TODO (memoria y SQLite). Lo usan los tests y la evaluación entre casos."""
    with _lock:
        with _db:
            for table in [*_OBJECT_TABLES, *_SET_TABLES, "sequences"]:
                _db.execute(f"DELETE FROM {table}")
        store.__init__()


# Al importar: abrir la base configurada (OPS_DB_PATH; por defecto data/ops.sqlite).
def _default_path() -> str:
    env = os.environ.get("OPS_DB_PATH")
    if env:
        return env
    from .config import get_settings
    return str(get_settings().ops_db_path)


use_database(_default_path())
