"""Baseline 1 (Paso 4 de la guía 4.2): palabras clave ES/PT.

Las reglas salen de ml/intent/labeling_guide.md (v1.4), en su orden de precedencia,
y de sinónimos comunes. No se ajustaron mirando frases de val ni de test.

    1. robo, pérdida, clonación o varias compras en poco tiempo -> tarjeta_comprometida
    2. pregunta por un reclamo ya hecho al banco                -> estado_disputa
    3. reconoce el comercio pero el cobro está mal              -> cobro_incorrecto
    4. no reconoce el cargo                                     -> cargo_no_reconocido
    5. otro pedido (incluye las aclaraciones 1.2)               -> fuera_de_alcance

Si pega una regla, confianza 0,9. Si no pega ninguna, fuera_de_alcance con 0,3.
fit no aprende nada: existe solo para cumplir la interfaz común.
"""

import re
import unicodedata

import numpy as np

from ml.intent.evaluate import CLASES

CONF_REGLA = 0.9
CONF_SIN_REGLA = 0.3


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes ni signos, y algunas abreviaturas de chat."""
    t = unicodedata.normalize("NFKD", texto.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\b(pq|xq|porq)\b", "por que", t)
    t = re.sub(r"\bq\b", "que", t)
    t = re.sub(r"\b(vc|vcs)\b", "voce", t)
    t = re.sub(r"\b(naum|nn)\b", "nao", t)
    return re.sub(r"\s+", " ", t).strip()


def _re(*partes: str) -> re.Pattern:
    return re.compile("|".join(partes))


# --- Regla 1: tarjeta_comprometida -----------------------------------------------

_ROBO_PERDIDA = _re(
    r"\brob(aron|o|ada|ado|ar)\b", r"\bhurt", r"\basalt",
    r"\bperd(i|io|ida|ido|imos|eu|emos)\b", r"\bextravi", r"\bse me (cayo|perdio)",
    r"\bno (encuentro|la encuentro|se donde (esta|deje))", r"\bnao (acho|encontro|sei onde)",
    r"\bclon", r"\bskimm", r"\bhacke", r"\bme copiaron", r"\bcopiaram",
    r"\broub(aram|ou|ado|ada|o)\b", r"\bfurt", r"\bassalt",
)
_VARIAS_COMPRAS = _re(
    r"\b(varias|muchas|varios|muchos|monton de|un chingo de|un monton de|bastantes|vari[ao]s|muit[ao]s)\s+"
    r"(\w+\s+)?(compras|cargos|cobros|transacciones|movimientos|cobrancas|transacoes|debitos)",
    r"\b(compras|cargos|cobros|transacciones|cobrancas|transacoes)\s+(seguid[oa]s|en cadena|em sequencia)",
)
_POCO_TIEMPO = _re(
    r"\bultim[ao]s?\s+(hora|horas|minutos|dias|dos dias|dois dias|2 dias)",
    r"\ben (una|la ultima|pocas) horas?\b", r"\bem (uma|poucas) horas?\b",
    r"\b(hoy|hoje|anoche|esta (manana|madrugada)|de madrugada|nesta madrugada)\b",
    r"\ben (pocos|unos) (minutos|dias)\b", r"\bem (poucos|alguns) (minutos|dias)\b",
    r"\bde (golpe|repente)\b", r"\bseguid[oa]s\b", r"\buno tras otro\b", r"\buma atras da outra\b",
)

# --- Regla 2: estado_disputa -------------------------------------------------------

_RECLAMO = (r"(reclamo|reclamacion|reclamacao|disputa|aclaracion|contracargo|chargeback|"
            r"contestacao|folio|ticket|protocolo|chamado|solicitud de devolucion)")
_ESTADO_DISPUTA = _re(
    rf"\b(mi|mis|meu|minha|meus|minhas|el|la|o|a|del|da|do)\s+{_RECLAMO}",
    rf"\b(numero|n) de\s+{_RECLAMO}", r"\b(mi|meu) caso\b",
    rf"\b{_RECLAMO}\b.{{0,40}}\b(que (hice|abri|puse|levante|meti|fiz)|ja abri|ya abri)",
    rf"\b(ya|ja)\s+(abri|hice|puse|levante|meti|fiz|reporte|reclame|contestei|registrei)\b.{{0,30}}\b{_RECLAMO}",
    r"\b(como va|en que va|en que quedo|como (esta|anda|ta) (o|a|meu|minha|mi))\b.{0,30}\b"
    rf"({_RECLAMO[1:-1]}|caso|pedido)",
    rf"\b(estado|status|estatus|seguimiento|andamento|avance|novedades)\b.{{0,30}}\b{_RECLAMO}",
)

# --- Regla 3: cobro_incorrecto -----------------------------------------------------

_COBRO = r"(cobr|carg|debit|descont)"
_COBRO_INCORRECTO = _re(
    # duplicado
    r"\b(dos|2|duas|tres|3) veces\b", r"\b(duas|2|tres|3) vezes\b", r"\bem dobro\b", r"\bdoble\b",
    r"\bduplicad", r"\brepetid", r"\b(dos|2|duas) (cobros|cargos|cobrancas|compras) iguales?\b",
    # monto distinto
    r"\bde mas\b", r"\ba mais\b", r"\bmas de lo que\b", r"\bmais do que\b",
    r"\b(monto|cantidad|importe|precio|valor|total)\s+(incorrect|distint|equivocad|diferente|errad|mal\b|mayor)",
    r"\b(en vez de|en lugar de|em vez de|ao inves de)\b",
    r"\b(me )?cobr\w*\s+(mal|errado|incorrectamente|erroneamente|equivocadamente)\b",
    r"\b(cobro|cargo|cobranca) (incorrect|equivocad|errad|erroneo)",
    # tipo de cambio
    r"\b(tipo|tasa|taxa) de cambio\b", r"\bconversao\b", r"\bconversion\b", r"\bcotizacion\b", r"\bcotacao\b",
    r"\bcambio de (moneda|divisa)\b",
    # cobro tras cancelar
    rf"\bcancel\w*\b.{{0,60}}\b{_COBRO}", rf"\b{_COBRO}\w*\b.{{0,60}}\bcancel",
    r"\b(di|dei) de baja\b", r"\b(di|dei) baixa\b",
    r"\b(siguen|sigue|continuan|continua|seguem|continuam|segue)\s+(me\s+)?(cobrando|cargando|debitando)\b",
    # comisión que considera indebida
    r"\b(comision|taxa|tarifa|cargo por servicio)\b.{0,40}\b(indebid|indevid|no deb|nao dev|no corresponde|"
    r"incorrect|injust|sin avisar|sem avisar|no me avisaron|errad|abusiv)",
    r"\b(indebid|indevid|injust)\w*\b.{0,30}\b(comision|taxa|tarifa)\b",
)

# --- Regla 4: cargo_no_reconocido --------------------------------------------------

_NO_RECONOCIDO = _re(
    r"\bno (lo |la )?(reconozco|reconoz|reconoci|reconozc)", r"\bdesconoz", r"\bdesconoc", r"\bdesconhe",
    r"\bno (hice|realice|autorice|compre|fui yo|he hecho|he comprado|solicite)\b",
    r"\bnunca (compre|hice|he comprado|autorice|estuve|fui)\b",
    r"\bno (es|era|son) mi[oa]s?\b", r"\bno me suena\b", r"\bni idea de\b",
    r"\bno se (que es|de que es|de donde|que compra)\b",
    r"\b(cargo|cobro|compra|movimiento|transaccion)s?\s+(raro|extran|desconocid|sospechos|fantasma)",
    r"\balguien (uso|usa|esta usando|compro|hizo)\b",
    r"\bnao (o |a )?(reconhe|reconheci|fiz|autorizei|comprei|fui eu|solicitei)",
    r"\bnunca (comprei|fiz|autorizei|estive)\b",
    r"\bnao (e|eh|sao) m(eu|inha|eus|inhas)\b", r"\bnao sei (o que e|de onde|que compra)\b",
    r"\b(compra|cobranca|transacao|debito|lancamento)s?\s+(estranh|desconhecid|suspeit)",
    r"\balguem (usou|esta usando|ta usando|comprou|fez)\b",
    r"\bunrecogni", r"\bdidn t make\b",
)

# --- Regla 5 y aclaraciones 1.2: fuera_de_alcance explícito ---------------------------

_FUERA = _re(
    r"\bprestamo", r"\bemprestimo", r"\bcredito (personal|hipotecario|pessoal)\b",
    r"\blimite", r"\bpin\b", r"\bnip\b", r"\bsenha", r"\bcontrasena", r"\bclave\b",
    r"\bsaldo", r"\bextracto\b", r"\bextrato\b", r"\bestado de cuenta\b",
    r"\bsucursal", r"\bagencia\b", r"\bhorario", r"\bcajer[oa] (automatico )?(me )?(trago|retuvo|se quedo)",
    r"\b(engoliu|reteve|prendeu)\b", r"\bretenid",
    r"\brechaz", r"\bdeclin", r"\brecusad", r"\bnegad", r"\bno (pasa|paso|pasa la|me deja)\b", r"\bnao passa\b",
    r"\bpendiente", r"\bpendente", r"\bno (se )?(ha )?acredit", r"\bnao (caiu|foi creditad)",
    r"\btransferencia", r"\bdeposito", r"\bpix\b",
    r"\b(abrir|cerrar|abrir una|fechar) (cuenta|conta)\b", r"\b(tarjeta|cartao) (nueva|nuevo|novo|adicional)\b",
    r"\bactivar", r"\bativar", r"\bdesbloque", r"\bpuntos\b", r"\bcashback\b", r"\bseguro\b", r"\binversion",
    r"\b(por que|cuanto cuesta|cuanto cobran|quanto custa|quanto e)\b.{0,30}\b(comision|taxa|tarifa|anualidad|anuidade)\b",
    r"\b(tienda|comercio|vendedor|negocio|loja|lojista|aerolinea|restaurante)\b.{0,60}\b(devol|reembols|estorn|reintegr)",
    r"\b(devol|reembols|estorn|reintegr)\w*\b.{0,60}\b(tienda|comercio|vendedor|loja|lojista)\b",
)

# Orden de precedencia de la guía. Las aclaraciones de fuera_de_alcance van al final:
# solo cuentan si no pegó ninguna regla 1-4.
REGLAS = [
    ("tarjeta_comprometida", lambda t: bool(_ROBO_PERDIDA.search(t))
        or bool(_VARIAS_COMPRAS.search(t) and _POCO_TIEMPO.search(t))),
    ("estado_disputa", lambda t: bool(_ESTADO_DISPUTA.search(t))),
    ("cobro_incorrecto", lambda t: bool(_COBRO_INCORRECTO.search(t))),
    ("cargo_no_reconocido", lambda t: bool(_NO_RECONOCIDO.search(t))),
    ("fuera_de_alcance", lambda t: bool(_FUERA.search(t))),
]


def clasificar(texto: str) -> tuple[str, float]:
    t = normalizar(texto)
    for clase, regla in REGLAS:
        if regla(t):
            return clase, CONF_REGLA
    return "fuera_de_alcance", CONF_SIN_REGLA


class Reglas:
    costo_por_1000_usd = 0.0

    def fit(self, textos, labels):
        return self

    def predict_proba(self, textos):
        probs = np.zeros((len(textos), len(CLASES)))
        for i, texto in enumerate(textos):
            clase, conf = clasificar(texto)
            probs[i] = (1 - conf) / (len(CLASES) - 1)
            probs[i, CLASES.index(clase)] = conf
        return probs


def crear(**params):
    return Reglas(**params)
