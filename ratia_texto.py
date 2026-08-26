# -*- coding: utf-8 -*-
"""Rat.IA · los textos de una publicación de Instagram, escritos con Haiku.

DOS TRABAJOS DISTINTOS
==============================================================================
1. `nombre_corto()` — acorta el título de la ficha para que entre en la pieza.
2. `caption()` — el texto del post.

POR QUÉ SE ACORTA EL NOMBRE (26-ago-2026, corrección de Joaquín)
==============================================================================
Los títulos de retail vienen armados para el buscador, no para leerse:

    "Audífonos Inalámbricos Bluetooth 5.3 con Cancelación de Ruido"

Puesto entero en la pieza ocupa tres líneas, obliga a bajar el cuerpo de la
tipografía y le come el espacio al "¡70% OFF!", que es lo que de verdad para
el scroll. Joaquín lo pidió así, textual: *"tampoco es importante subir el
nombre del producto completo en la imagen […] mejor resumirlo a: audifonos
bluetooth cancelacion ruido"*.

Verificado con las dos piezas del 26-ago: con el título largo el titular sale
en 3 líneas y el OFF chico; con el corto entra en una y el OFF queda grande.

QUÉ LLEVA EL CAPTION, Y QUÉ NO
==============================================================================
Lleva el COMERCIO donde está la oferta. No lleva link, no pide comentar, no
manda al DM — decisión de Joaquín del 26-ago, que reemplaza al caption
anterior (el de "comenta OFERTA y te paso el link por DM"). Un link saliente
le baja el alcance al post y el flujo de DM todavía no existe.

POR QUÉ HAIKU Y NO SONNET
==============================================================================
Acortar un título y escribir dos líneas de caption es exactamente la clase de
tarea acotada donde Haiku rinde igual: a USD 1/5 por millón de tokens contra
USD 2/10 de Sonnet, y con ~250 tokens por pieza el costo mensual del catálogo
completo queda en centavos (ver `costo_mensual_estimado()`).

SI FALLA, NO SE QUEDA SIN TEXTO
==============================================================================
Las dos funciones tienen respaldo determinista. Que la API esté caída no
puede dejar una pieza sin caption ni frenar una publicación — el respaldo es
peor de leer, pero es correcto y no inventa nada.
"""
from __future__ import annotations

import os
import re

MODELO = "claude-haiku-4-5"

# Palabras de relleno que los títulos de retail arrastran y que no aportan
# nada leídas en una pieza. Se usan sólo en el respaldo sin IA.
RUIDO = {
    "de", "del", "la", "el", "los", "las", "con", "para", "por", "y", "en",
    "sin", "un", "una", "unos", "unas", "al", "a", "su", "sus",
    "sabor", "unidades", "unidad", "pack", "set", "kit", "nuevo", "nueva",
    "original", "importado", "envio", "envío", "gratis", "oferta",
}


def _cliente():
    """El cliente del SDK. Se importa perezoso para que un módulo sin la
    librería instalada no rompa el import de todo el bot."""
    import anthropic
    clave = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if not clave:
        raise RuntimeError("falta ANTHROPIC_API_KEY")
    return anthropic.Anthropic(api_key=clave)


def _plata(n) -> str:
    return "$" + format(int(round(float(n))), ",d").replace(",", ".")


# ══════════════════════════════════════════════════════════════════════════
# 1 · NOMBRE CORTO PARA LA PIEZA
# ══════════════════════════════════════════════════════════════════════════

def _nombre_corto_sin_ia(titulo: str, max_palabras: int = 5) -> str:
    """Respaldo: quita relleno y corta. No es elegante, pero nunca falla."""
    limpio = re.sub(r"[^\wáéíóúñüÁÉÍÓÚÑÜ\s.]", " ", titulo or "")
    palabras = [p for p in limpio.split() if p]
    # Fuera medidas y códigos sueltos ("60ml", "X3", "500g"), que en la pieza
    # no dicen nada y ocupan igual.
    palabras = [p for p in palabras
                if not re.fullmatch(r"(?i)[xX]?\d+([.,]\d+)?(ml|g|kg|cc|mg|un|u|cm|mm|w|v)?", p)]
    utiles = [p for p in palabras if p.lower() not in RUIDO]
    return " ".join((utiles or palabras)[:max_palabras]).strip()


def nombre_corto(titulo: str, max_palabras: int = 5, log=print) -> str:
    """El nombre del producto, listo para el titular de la pieza.

    Devuelve como máximo `max_palabras`. Nunca inventa: sólo puede quitar
    palabras del título original, nunca agregar información que no venga en
    él (un modelo que "completa" el nombre de un producto es justo el modo de
    falla del 24-ago con el frasco inventado).
    """
    titulo = (titulo or "").strip()
    if not titulo:
        return ""
    if len(titulo.split()) <= max_palabras:
        return titulo

    try:
        r = _cliente().messages.create(
            model=MODELO,
            max_tokens=60,
            system=(
                "Acortás títulos de productos de retail chileno para ponerlos "
                "en una pieza gráfica. Devolvés SOLO el título corto, sin "
                "comillas, sin explicación, sin punto final."
            ),
            messages=[{"role": "user", "content":
                f"Título original: {titulo}\n\n"
                f"Acortalo a un máximo de {max_palabras} palabras dejando lo que "
                "identifica al producto: qué es y su rasgo distintivo. "
                "Quitá medidas, códigos, cantidades, 'sin sabor' y relleno de "
                "buscador. NO agregues ninguna palabra que no esté en el "
                "título original. Mantené las tildes."}],
        )
        txt = "".join(b.text for b in r.content if b.type == "text").strip()
        txt = txt.strip('"').strip("'").rstrip(".").strip()
        # Si devolvió algo raro (vacío, o más largo que el original), se cae
        # al respaldo en vez de arruinar la pieza.
        if txt and len(txt.split()) <= max_palabras + 1 and len(txt) <= len(titulo):
            return txt
        log("[texto] Haiku devolvió un nombre inservible, se usa el respaldo")
    except Exception as e:                                    # noqa: BLE001
        log("[texto] no se pudo acortar con Haiku (%s), se usa el respaldo"
            % str(e)[:90])
    return _nombre_corto_sin_ia(titulo, max_palabras)


# ══════════════════════════════════════════════════════════════════════════
# 2 · CAPTION DEL POST
# ══════════════════════════════════════════════════════════════════════════

HASHTAGS = {
    "oferta": "#ofertas #chile #descuentos #ofertasreales",
    "error": "#errordeprecio #chile #ofertas #ofertasreales",
    "convenio": "#convenios #chile #descuentos #ofertasreales",
}


def _caption_sin_ia(nombre: str, tienda: str, antes, ahora, tipo: str) -> str:
    desc = ""
    try:
        if antes and float(antes) > 0:
            desc = " (%d%% menos)" % round((1 - float(ahora) / float(antes)) * 100)
    except Exception:                                         # noqa: BLE001
        pass
    cabeza = "🐀 Error de precio" if tipo == "error" else "🐀"
    return ("%s %s a %s%s.\n"
            "📍 Disponible en %s.\n\n%s"
            % (cabeza, nombre, _plata(ahora), desc, tienda or "la tienda",
               HASHTAGS.get(tipo, HASHTAGS["oferta"])))


def caption(nombre: str, tienda: str, precio_antes, precio_ahora,
            tipo: str = "oferta", log=print) -> str:
    """El texto del post. Dice el comercio; no lleva link ni pide comentar.

    `tipo` es 'oferta', 'error' o 'convenio'.
    """
    tienda = (tienda or "").strip()
    tags = HASHTAGS.get(tipo, HASHTAGS["oferta"])

    try:
        que_es = {
            "error": "un ERROR DE PRECIO detectado por Rat.IA (puede corregirse en cualquier momento)",
            "convenio": "un convenio de banco vigente",
        }.get(tipo, "una oferta real verificada por Rat.IA")

        r = _cliente().messages.create(
            model=MODELO,
            max_tokens=220,
            system=(
                "Escribís captions de Instagram para Rat.IA, una cuenta chilena "
                "que avisa ofertas y errores de precio del retail. Tono directo "
                "y cercano, español de Chile de tuteo ('anda', 'aprovecha'), "
                "nunca voseo argentino.\n"
                "FORMATO: máximo 2 líneas, sin líneas en blanco entre ellas.\n"
                "PROHIBIDO: pedir que comenten, mencionar DM o mensajes "
                "privados, poner links o decir 'link en bio'.\n"
                "PROHIBIDO inventar o insinuar datos que no te pasen: si hay "
                "stock, cuánto queda, hasta cuándo dura, cuotas, despacho o "
                "condiciones. No sabés nada de eso. Hablá SOLO del producto, "
                "su precio y el comercio.\n"
                "OBLIGATORIO: nombrar el comercio donde está la oferta.\n"
                "Devolvés SOLO el caption, sin hashtags y sin comillas."
            ),
            messages=[{"role": "user", "content":
                f"Producto: {nombre}\n"
                f"Comercio: {tienda or 'no informado'}\n"
                f"Precio antes: {_plata(precio_antes)}\n"
                f"Precio ahora: {_plata(precio_ahora)}\n"
                f"Es {que_es}.\n\n"
                "Escribí el caption."}],
        )
        txt = "".join(b.text for b in r.content if b.type == "text").strip()
        # Red de seguridad: si igual se coló una llamada a DM o un link, se
        # descarta y va el respaldo. La instrucción no basta como garantía.
        # La red de seguridad incluye "stock" y "quedan": el 26-ago Haiku
        # escribió "anda a verificar si quedan stock" — no es un dato que
        # tengamos, y en un post automático se lee como si lo fuera.
        prohibido = ("dm", "mensaje privado", "link en bio", "http", "www.",
                     "comenta", "comentá", "comentario",
                     "stock", "quedan", "últimas unidades", "ultimas unidades",
                     "agot",   # agote / agotar / agotado / se agota
                     "cuotas", "despacho")
        if txt and not any(p in txt.lower() for p in prohibido):
            if tienda and tienda.lower() not in txt.lower():
                txt += "\n📍 En %s." % tienda
            return txt + "\n\n" + tags
        log("[texto] el caption de Haiku traía algo prohibido, se usa el respaldo")
    except Exception as e:                                    # noqa: BLE001
        log("[texto] no se pudo escribir el caption con Haiku (%s), respaldo"
            % str(e)[:90])
    return _caption_sin_ia(nombre, tienda, precio_antes, precio_ahora, tipo)


# ══════════════════════════════════════════════════════════════════════════
# 3 · CUÁNTO CUESTA ESTO AL MES
# ══════════════════════════════════════════════════════════════════════════

# Precios de Haiku 4.5, USD por millón de tokens.
USD_MTOK_IN, USD_MTOK_OUT = 1.00, 5.00
# Medido sobre los prompts de arriba: el system + los datos del producto.
TOK_IN_NOMBRE, TOK_OUT_NOMBRE = 190, 20
TOK_IN_CAPTION, TOK_OUT_CAPTION = 300, 90


def costo_mensual_estimado(piezas_mes: int, usd_clp: float = 913.27) -> dict:
    """Lo que cuestan los textos de N piezas al mes. Las dos llamadas
    (nombre + caption) van por pieza."""
    tin = piezas_mes * (TOK_IN_NOMBRE + TOK_IN_CAPTION)
    tout = piezas_mes * (TOK_OUT_NOMBRE + TOK_OUT_CAPTION)
    usd = tin / 1e6 * USD_MTOK_IN + tout / 1e6 * USD_MTOK_OUT
    return {"piezas": piezas_mes, "tokens_in": tin, "tokens_out": tout,
            "usd": round(usd, 3), "clp": int(round(usd * usd_clp))}
