# -*- coding: utf-8 -*-
"""Rat.IA · qué se sube a Instagram, y cuándo.

PARA QUÉ EXISTE
------------------------------------------------------------------------------
El Telegram de Rat.IA puede recibir cientos de hallazgos al día — ahí la vara
es "¿es una caída real?". Instagram es otra cosa: es la cara pública de la
marca, entran 2-8 piezas por día, y cada una que se equivoca (un % inflado,
un producto que a nadie le importa) se ve para siempre. La vara acá es
curaduría, no validez.

Reglas dadas por Joaquín el 25-ago-2026, textuales:

  OFERTAS — máximo 2 al día. Tiene que ser "producto novedoso/viral/
  tecnológico/hogar" Y al menos 50% de descuento (las dos cosas, no basta
  una). Se suben 1-2 horas después de aparecer en el Telegram. Corte a las
  23:30 — nada se publica después de esa hora.

  ERRORES DE PRECIO — se suben 30 minutos después de aparecer en el
  Telegram, a cualquier hora. Ahí sí se pide correo por DM (ver
  `ratia_leads.py`); en ofertas el DM manda el link directo, sin ese paso.

DE DÓNDE SALEN LOS CANDIDATOS
------------------------------------------------------------------------------
De las DOS fuentes que ya alimentan el Telegram de Rat.IA, sin construir nada
nuevo para leerlas — el trabajo de archivarlas con nombre/tienda/precio/fecha
ya se hizo el 25-ago de madrugada:

  · `alertas` en precios.db      — los hallazgos PROPIOS de Héctor.
  · `anuncios` en hector2.db     — los reenvíos verificados del aliado.

Ambas ya tienen todo lo que hace falta: nombre, tienda, precio, referencia,
caída y el momento exacto en que se avisó por Telegram. Ese momento es el
"primera_vez_vista" del que se cuentan las 1-2h o los 30 min.

QUÉ CUENTA COMO "NOVEDOSO/VIRAL/TECNOLÓGICO/HOGAR"
------------------------------------------------------------------------------
Se reusan los patrones que YA existen y ya están calibrados con casos reales,
en vez de inventar una lista nueva desde cero:

  · `categorias.RE_ELECTRONICOS` / `RE_HOGAR` — lo tecnológico y lo hogar,
    tal cual.
  · `caliente.IMANES` — la lista de "esto genera cola" (Apple, gaming,
    marcas de reventa, drones, LEGO…), que es exactamente la definición de
    "novedoso/viral": productos que la gente comparte porque quiere tener
    uno, no porque sean baratos.

ERROR DE PRECIO: LA VARA YA EXISTÍA
------------------------------------------------------------------------------
`baseprecios.UMBRAL_ERROR_GRAVE` (0.85) es justo el corte que se definió esa
misma madrugada para separar "oferta muy buena" de "error real" en el propio
Telegram. Se reusa acá tal cual: no hace falta un segundo número que definir
ni mantener sincronizado.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

import baseprecios
import caliente
import categorias

Tipo = Literal["oferta", "error"]
Estado = Literal["pendiente", "publicado", "descartado", "vencido"]

# ── LOS NÚMEROS DE LA REGLA, EN UN SOLO LUGAR ──────────────────────────────

UMBRAL_OFERTA_IG = 0.50          # "al menos 50% de descuento"

DEMORA_OFERTA_MIN_SEG = 60 * 60      # 1h — no antes
DEMORA_OFERTA_MAX_SEG = 2 * 60 * 60  # 2h — ventana objetivo
# Sobre esto, la oferta ya no es noticia y se descarta en vez de publicarla
# tarde. Sin techo, un candidato de un día tranquilo podría postearse a
# las 40 horas — y a esa altura probablemente ya se corrigió el precio.
VENCE_OFERTA_SEG = 6 * 60 * 60

DEMORA_ERROR_SEG = 30 * 60       # "30 minutos después que aparezca"
# Los errores viven minutos, no horas. Si a las 2h nadie lo publicó (cupo
# lleno, el proceso estaba caído), ya no vale la pena: se descarta.
VENCE_ERROR_SEG = 2 * 60 * 60

TOPE_OFERTAS_DIA = 2
# No pedido explícitamente — válvula de seguridad para no saturar el feed
# si algo falla y hay una racha de errores reales el mismo día. Fácil de
# subir si en la práctica se queda corto.
TOPE_ERRORES_DIA = 6

# "Corte a las 23:30": nada se PUBLICA después de esa hora. Un candidato que
# ya estaba listo simplemente espera a que abra la ventana del día
# siguiente (siempre que no haya vencido para entonces).
HORA_CORTE = (23, 30)

ZONA_CHILE = "America/Santiago"


def _hora_chile(ahora: float):
    from zoneinfo import ZoneInfo
    import datetime
    return datetime.datetime.fromtimestamp(ahora, tz=ZoneInfo(ZONA_CHILE))


def antes_del_corte(ahora: float) -> bool:
    h = _hora_chile(ahora)
    return (h.hour, h.minute) < HORA_CORTE


def medianoche_chile_epoch(ahora: float) -> int:
    """El epoch de las 00:00 de HOY en Chile -- para `publicados_hoy`.

    Sin esto, "los que se publicaron hoy" en un servidor en UTC contaría
    parte de ayer o de mañana según la hora, y el tope de 2 ofertas/día se
    reiniciaría en el momento equivocado."""
    h = _hora_chile(ahora)
    return int(h.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())


def _categoria_ig(nombre: str) -> bool:
    """"novedoso/viral/tecnológico/hogar" — ver el encabezado del archivo."""
    n = nombre or ""
    return bool(categorias.RE_ELECTRONICOS.search(n)
                or categorias.RE_HOGAR.search(n)
                or caliente.IMANES.search(n))


@dataclass
class Candidato:
    url: str
    tipo: Tipo
    fuente: str              # "hector" | "aliado"
    tienda: str | None
    nombre: str | None
    precio: float
    referencia: float
    caida: float
    primera_vez_vista: int   # epoch: cuándo se avisó en el Telegram
    puntaje: float = field(default=0.0)

    @property
    def ahorro(self) -> float:
        return max(0.0, (self.referencia or 0) - (self.precio or 0))

    @property
    def elegible_en(self) -> int:
        if self.tipo == "error":
            return self.primera_vez_vista + DEMORA_ERROR_SEG
        return self.primera_vez_vista + DEMORA_OFERTA_MIN_SEG

    @property
    def vence_en(self) -> int:
        vent = VENCE_ERROR_SEG if self.tipo == "error" else VENCE_OFERTA_SEG
        return self.primera_vez_vista + vent


def clasificar(caida: float) -> Tipo:
    """A qué carril entra, según la caída — mismo corte que ya usa el
    Telegram de Rat.IA (`baseprecios.UMBRAL_ERROR_GRAVE`)."""
    return "error" if caida >= baseprecios.UMBRAL_ERROR_GRAVE else "oferta"


def calificado_para_ig(c: Candidato) -> tuple[bool, str]:
    """(califica, motivo). El motivo sirve para loguear/archivar por qué NO
    entró, igual que `diag` en `baseprecios.evaluar` — para poder responder
    "¿por qué no se publicó tal cosa?" sin adivinar."""
    if not c.url or not c.precio or not c.referencia:
        return False, "datos incompletos"
    if c.tipo == "error":
        if c.caida < baseprecios.UMBRAL_ERROR_GRAVE:
            return False, "no llega al umbral de error (%.0f%%)" % (
                baseprecios.UMBRAL_ERROR_GRAVE * 100)
        return True, "califica como error de precio"
    # tipo == "oferta": las DOS condiciones, no una.
    if c.caida < UMBRAL_OFERTA_IG:
        return False, "menos del 50%% de descuento (%.0f%%)" % (c.caida * 100)
    if not _categoria_ig(c.nombre or ""):
        return False, "no es tecnológico/hogar/novedoso"
    return True, "califica como oferta"


def puntaje_oferta(c: Candidato) -> float:
    """Solo para el carril de ofertas: de los que califican, cuáles van
    primero cuando hay más candidatos que cupo (2 al día).

    Tres señales, cada una con su motivo:
      · la caída en sí (una mejor oferta gana);
      · el ahorro en PESOS, normalizado — un producto caro con buen % ahorra
        mucho dinero real, y eso también vende;
      · si además es de la lista de "imanes" (Apple, gaming, marcas de
        reventa…) suma un extra: esos son los que de verdad generan
        comentarios, más allá del % o el precio.
    """
    imán = 15.0 if caliente.IMANES.search(c.nombre or "") else 0.0
    return (c.caida * 100) + min(40.0, c.ahorro / 5_000) + imán


def evaluar_candidatos(filas, ahora: float | None = None) -> list[Candidato]:
    """`filas` es un iterable de dicts con: url, tienda, nombre, precio,
    referencia, caida, primera_vez_vista (epoch). Viene de leer `alertas` y
    `anuncios` — ver `candidatos_desde_bd` en `hector2_db.py` y
    `baseprecios.py`.

    Devuelve solo los que CALIFICAN, ya clasificados en su carril.
    """
    ahora = ahora if ahora is not None else time.time()
    salida = []
    for f in filas:
        caida = float(f.get("caida") or 0)
        c = Candidato(
            url=f["url"], tipo=clasificar(caida), fuente=f.get("fuente", ""),
            tienda=f.get("tienda"), nombre=f.get("nombre"),
            precio=float(f.get("precio") or 0),
            referencia=float(f.get("referencia") or 0),
            caida=caida, primera_vez_vista=int(f["primera_vez_vista"]))
        ok, _motivo = calificado_para_ig(c)
        if not ok:
            continue
        if c.tipo == "oferta":
            c.puntaje = puntaje_oferta(c)
        salida.append(c)
    return salida


def listos_para_publicar(candidatos: list[Candidato], ahora: float | None,
                          ya_publicados_hoy: dict[Tipo, int]) -> list[Candidato]:
    """De los candidatos que YA calificaron, cuáles se publican EN ESTE
    INSTANTE: pasó su demora, no venció, hay cupo del día, y no es después
    del corte (sólo aplica a ofertas — un error de precio no espera a
    mañana, se pierde si no se publica a tiempo).

    Ofertas: las mejores primero (`puntaje`), hasta llenar el cupo restante.
    Errores: el más urgente primero (el que lleva más tiempo esperando) —
    acá no se rankea por calidad, se rankea por que no se muera.
    """
    ahora = ahora if ahora is not None else time.time()
    listos = [c for c in candidatos
             if c.elegible_en <= ahora <= c.vence_en]

    ofertas = [c for c in listos if c.tipo == "oferta"]
    errores = [c for c in listos if c.tipo == "error"]

    salida = []
    if antes_del_corte(ahora):
        cupo = TOPE_OFERTAS_DIA - ya_publicados_hoy.get("oferta", 0)
        if cupo > 0:
            ofertas.sort(key=lambda c: -c.puntaje)
            salida += ofertas[:cupo]

    cupo_e = TOPE_ERRORES_DIA - ya_publicados_hoy.get("error", 0)
    if cupo_e > 0:
        errores.sort(key=lambda c: c.primera_vez_vista)
        salida += errores[:cupo_e]

    return salida
