"""eval/cases/validar_casos.py (Fase 6.1, Paso 7): el set real pasa, y cada error que debe detectar lo detecta.

Necesita data/gold/gold.duckdb (el esperado se calcula contra el gold); sin él, se salta.
"""
import json

import pytest

from eval.cases import validar_casos as v
from eval.cases.esperado import GOLD

pytestmark = pytest.mark.skipif(not GOLD.exists(), reason="sin data/gold/gold.duckdb")

REFS = ["frase de referencia que no se parece a nada"]


def _lineas(split):
    return [json.loads(l) for l in v.ARCHIVOS[split].read_text(encoding="utf-8").splitlines() if l.strip()]


def _correr(tmp_path, dev, heldout, inventario=None, refs=REFS):
    archivos = {}
    for split, filas in (("dev", dev), ("heldout", heldout)):
        archivos[split] = tmp_path / f"{split}.jsonl"
        archivos[split].write_text("".join(json.dumps(f, ensure_ascii=False) + "\n" for f in filas), encoding="utf-8")
    inv = tmp_path / "inventario.md"
    inv.write_text(inventario if inventario is not None else v.INVENTARIO.read_text(encoding="utf-8"),
                   encoding="utf-8")
    errores, _, _ = v.validar(archivos, inv, refs)
    return errores


def test_el_set_real_pasa():
    assert v.main() == 0


@pytest.fixture
def sets():
    return _lineas("dev"), _lineas("heldout")


def _caso(filas, categoria):
    return next(f for f in filas if f["category"] == categoria)


def test_base_sin_errores(tmp_path, sets):
    assert _correr(tmp_path, *sets) == []


def test_schema(tmp_path, sets):
    dev, held = sets
    _caso(held, "normal")["expected"]["action"] = "REEMBOLSAR"
    assert any("no cumple schema.py" in e for e in _correr(tmp_path, dev, held))


def test_case_id_repetido(tmp_path, sets):
    dev, held = sets
    held.append(dict(held[0]))
    assert any("case_id repetido" in e for e in _correr(tmp_path, dev, held))


def test_tarjeta_bloqueada_sin_tarjeta_comprometida(tmp_path, sets):
    """Fuera de FRAUD, card_blocked solo vale con la intención tarjeta_comprometida (design.md §3.2)."""
    dev, held = sets
    caso = next(f for f in held if f["expected"]["card_blocked"] and f["expected"]["action"] == "INFORM")
    caso["provenance"]["gold_query"]["params"]["intencion"] = "cargo_no_reconocido"
    assert any("no cumple schema.py" in e for e in _correr(tmp_path, dev, held))


def test_tarjeta_bloqueada_con_auto_register(tmp_path, sets):
    dev, held = sets
    _caso(held, "normal")["expected"]["card_blocked"] = True
    assert any("no cumple schema.py" in e for e in _correr(tmp_path, dev, held))


def test_transaccion_en_los_dos_splits(tmp_path, sets):
    dev, held = sets
    tx = _caso(held, "normal")["expected"]["transaction_id"]
    _caso(dev, "normal")["setup"]["open_cases"].append({"transaction_id": tx})
    assert any(f"transacción {tx} en dev y held-out" in e for e in _correr(tmp_path, dev, held))


def test_mensaje_en_los_dos_splits(tmp_path, sets):
    dev, held = sets
    _caso(dev, "normal")["script"][0]["text"] = _caso(held, "normal")["script"][0]["text"].upper()
    assert any("mensaje en dev y held-out" in e for e in _correr(tmp_path, dev, held))


def test_transaccion_inexistente(tmp_path, sets):
    dev, held = sets
    _caso(held, "normal")["expected"]["transaction_id"] = "TRX-NO-EXISTE"
    assert any("no existe en el gold" in e for e in _correr(tmp_path, dev, held))


def test_transaccion_de_otro_cliente(tmp_path, sets):
    dev, held = sets
    otro = _caso(held, "acceso_no_autorizado")["customer_id"]
    caso = _caso(held, "normal")
    caso["customer_id"] = otro if otro != caso["customer_id"] else "CLI-OTRO"
    assert any(f"no de {caso['customer_id']}" in e for e in _correr(tmp_path, dev, held))


def test_acceso_no_autorizado_con_transaccion_propia(tmp_path, sets):
    dev, held = sets
    caso = _caso(held, "acceso_no_autorizado")
    caso["customer_id"] = v.transaccion_gold(caso["expected"]["transaction_id"])["customer_id"]
    assert any("tiene que ser de otro" in e for e in _correr(tmp_path, dev, held))


def test_regla_distinta_de_esperado(tmp_path, sets):
    dev, held = sets
    caso = next(f for f in held if f["expected"]["rule_id"] == "R8")
    caso["expected"]["rule_id"] = "R9"
    assert any("esperado.py da R8" in e for e in _correr(tmp_path, dev, held))


def test_categoria_bajo_el_minimo_sin_anotar(tmp_path, sets):
    dev, held = sets
    sin_tabla = v.INVENTARIO.read_text(encoding="utf-8").replace("Categorías por debajo del mínimo", "Otra cosa")
    errores = _correr(tmp_path, dev, held, inventario=sin_tabla)
    assert any("held-out ambiguo" in e and "no está anotada" in e for e in errores)


def test_categoria_anotada_con_otro_n(tmp_path, sets):
    dev, held = sets
    held.remove(_caso(held, "sesion_expirada"))
    assert any("held-out sesion_expirada: 3 casos, pero inventario.md anota 4" in e
               for e in _correr(tmp_path, dev, held))


def test_anotadas_en_inventario():
    assert v.anotadas_en_inventario(v.INVENTARIO.read_text(encoding="utf-8")) == {
        "ambiguo": 23, "inyeccion": 14, "sesion_expirada": 4, "falla_herramienta": 9}


def test_mensaje_parecido_a_ml(tmp_path, sets):
    dev, held = sets
    frase = _caso(held, "normal")["script"][0]["text"]
    assert any("similitud" in e for e in _correr(tmp_path, dev, held, refs=REFS + [frase + " ."]))
